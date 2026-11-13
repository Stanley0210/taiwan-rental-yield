"""The /housing surface: routes, payload shape, and the front-end tripwires.

Two of this repo's past outages are the reason most of these exist:

* A root-level .js file with no Flask route 404s in production while every test
  stays green, and the surface silently dies (commit 239e758, /systemic.js).
* A smart quote used as a string delimiter killed a whole inline block and 473
  tests still passed (commit f771988).

So the routes are asserted to actually serve, and the shipped JS is scanned.
"""

import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The pipeline modules live under src/ in this repository; in the project
# this was extracted from they sit at the root.
SRC = os.path.join(ROOT, "src")
JS = os.path.join(ROOT, "housing.js")
CSS = os.path.join(ROOT, "housing.css")
HTML = os.path.join(ROOT, "index.html")   # housing.html in the source project


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# ── routes ───────────────────────────────────────────────────────────────

def test_housing_page_serves(client):
    r = client.get("/housing")
    assert r.status_code == 200
    assert b"hs-root" in r.data


@pytest.mark.parametrize("path,ctype", [
    ("/housing.js", "javascript"),
    ("/housing.css", "text/css"),
])
def test_assets_serve(client, path, ctype):
    """The 404-that-ships-green check. Every root-level asset needs its own
    route because there is no catch-all."""
    r = client.get(path)
    assert r.status_code == 200, f"{path} returned {r.status_code}"
    assert ctype in r.headers["Content-Type"]
    assert len(r.data) > 500


def test_every_asset_referenced_by_the_shell_is_actually_served(client):
    html = _read(HTML)
    refs = re.findall(r'(?:src|href)="(/[^"]+)"', html)
    assert refs, "shell references no local assets -- did the markup change?"
    for ref in refs:
        assert client.get(ref).status_code == 200, f"{ref} is referenced but not served"


def test_data_route_is_json_or_a_clean_503(client):
    """503 (not 500) when the payload has not been built, with a runnable hint."""
    r = client.get("/housing_data.json")
    assert r.status_code in (200, 503)
    body = json.loads(r.data)
    if r.status_code == 503:
        assert "underwrite.py" in body["hint"]
    else:
        assert {"meta", "headline", "ladder", "buildings"} <= set(body)


def test_housing_needs_no_account(client):
    """Nothing is gated: the page is a research surface, not a product tier."""
    assert client.get("/housing").status_code == 200


def test_the_citable_artefacts_are_reachable_by_url(client):
    """The PDF and the payload digest were tracked but had no route, so the
    "citable" report could not be cited. Both ship from the same build as the
    payload; the footer links them."""
    pdf = client.get("/housing_report.pdf")
    assert pdf.status_code == 200 and pdf.headers["Content-Type"] == "application/pdf"
    assert pdf.data[:5] == b"%PDF-"
    sha = client.get("/housing_data.json.sha256")
    assert sha.status_code == 200 and sha.data.decode().split()[0] == \
        __import__("hashlib").sha256(open(os.path.join(ROOT, "housing_data.json"), "rb").read()).hexdigest()
    js = _read(JS)
    assert 'href="/housing_report.pdf"' in js and 'href="/housing_data.json.sha256"' in js


def test_health_goes_green_in_housing_mode(client, appmod, monkeypatch):
    """Under QUANTS_SUBJECT=housing the stock DataFrame never warms by design,
    so a readiness probe keyed on it would hold a deploy at 503 forever."""
    monkeypatch.setattr(appmod, "_SUBJECT", "housing")
    appmod._cache.pop("data", None)
    r = client.get("/health")
    body = r.get_json()
    assert r.status_code == 200 and body["status"] == "ok"
    assert body["subject"] == "housing" and body["housing_ready"] is True
    assert body["data_warm"] is False
    # and the stock probe still waits for its data
    monkeypatch.setattr(appmod, "_SUBJECT", "stocks")
    assert client.get("/health").status_code == 503


# ── payload contract ─────────────────────────────────────────────────────

@pytest.fixture
def payload():
    p = os.path.join(ROOT, "housing_data.json")
    if not os.path.exists(p):
        pytest.skip("housing_data.json not built (run: python underwrite.py)")
    return json.loads(_read(p))


def test_headline_is_a_plausible_gross_yield(payload):
    y = payload["headline"]["yield"]
    assert 0.5 < y < 8.0, f"headline yield {y}% is outside any believable range"
    assert payload["headline"]["buildings"] > 100


def test_ladder_is_cumulative_and_ends_at_the_headline(payload):
    """The ladder is a staircase plus ONE alternative.

    Rungs raw..park_impute each add one more correction and can only ever
    remove records, and the last staircase rung must BE the headline — it is
    the headline's own code path, which is why the ladder cannot quietly drift
    from it. (From v2.1 that rung is `park_impute`: an imputed space rent
    subtracted from un-itemised bundled leases; `building` sits just before it.)

    `parking_drop` is not another step down that staircase. It is the treatment
    the site used to apply, and every other published Taiwanese yield still
    applies: throw away the whole transaction rather than subtract the parking
    the registry itemised. It is kept because the difference is the point —
    6,043 buildings against 10,148 — so it is exempt from the monotonic check.
    """
    lad = payload["ladder"]
    assert len(lad) >= 4
    stair = [r for r in lad if r["key"] != "parking_drop"]
    assert stair[0]["unit"] == "pair" and stair[-1]["unit"] == "building"
    for a, b in zip(stair, stair[1:]):
        assert b["pairs"] <= a["pairs"], f"{b['key']} has MORE pairs than {a['key']}"
    assert stair[-1]["key"] == "park_impute"
    assert stair[-1]["yield"] == pytest.approx(payload["headline"]["yield"], abs=0.01)
    assert stair[-1]["buildings"] == payload["headline"]["buildings"]
    # the old default is the rung before it, and the step between them is the
    # parking correction -- published, not hidden
    assert stair[-2]["key"] == "building"
    assert stair[-1]["yield_building"] < stair[-2]["yield_building"]

    alt = [r for r in lad if r["key"] == "parking_drop"]
    if alt:
        # The old treatment must show FEWER buildings, or subtracting parking
        # bought nothing and the change was not worth making.
        assert alt[0]["buildings"] < stair[-1]["buildings"], (
            "dropping parking-bundled rows should cost buildings, not add them")


def test_pair_level_and_building_level_differ(payload):
    """If these ever coincide the last ladder rung is doing nothing, which would
    mean the cartesian blowup is no longer being corrected."""
    h = payload["headline"]
    assert h["pair_level_yield"] != h["yield"]
    assert h["pairs"] > h["buildings"]


def test_coverage_shows_the_walkup_gap(payload):
    cov = {c["type"]: c for c in payload["coverage"]}
    assert set(cov) == {"住宅大樓", "華廈", "公寓"}
    assert cov["公寓"]["match_rate"] < cov["住宅大樓"]["match_rate"], \
        "the finding is that walk-ups match far less often than towers"
    for c in cov.values():
        assert 0 <= c["match_rate"] <= 100
        assert c["matched"] <= c["all_buildings"]


def test_every_cost_assumption_is_sourced(payload):
    """Net yield is only publishable because each input has a citation. An
    assumption without a source is a guess wearing a number."""
    keys = {a["key"] for a in payload["assumptions"]}
    assert {"tax", "mgmt", "vacancy", "repairs"} <= keys
    for a in payload["assumptions"]:
        assert a["src_zh"] and a["src_en"], f"{a['key']} has no source"
        assert a["min"] <= a["default"] <= a["max"], f"{a['key']} default out of range"
        assert len(a["src_en"]) > 40, f"{a['key']} source is too thin to audit"


def test_net_yield_is_published_and_below_gross(payload):
    h = payload["headline"]
    assert h["net"] is not None
    assert h["net"] < h["yield"], "costs must reduce the yield"
    assert 0 < h["net"] < h["yield"]


def test_net_yield_matches_the_module_that_made_it(payload):
    """Every building's stored net must be reproducible from net_yield(). This is
    the Python half of the twin; the JS half is asserted structurally below."""
    import underwrite as U
    checked = 0
    for b in payload["buildings"][:400]:
        if b["nt"] is None:
            continue
        age = None if b["b"] is None else 115 - b["b"]
        got = U.net_yield(b["pa"], b["rm"] * 12, b["ar"], b["m"], age, b["c"])
        assert abs(got - b["nt"]) < 0.01, f"{b['a']}: {got} vs {b['nt']}"
        checked += 1
    assert checked > 100


def test_the_walk_up_prediction_is_on_the_record(payload):
    """The prediction the project set out to test stays in the payload with its
    numbers, whichever way it lands.

    This test used to assert `verdict == "dead"`. That was measured on Taipei
    and New Taipei, where the gross gap was 0.041pp; it was hard-coded into the
    build AND into this test, so neither could notice when going national made
    it false. Asserting the ANSWER is how a stale conclusion survives a change
    of scope -- so this now asserts the record and the derivation instead.
    """
    dh = payload["dead_hypothesis"]
    assert len(dh["by_type"]) == 3 and len(dh["by_manager"]) == 2
    assert dh["verdict"] in {"alive", "dead", "reversed", "untested"}
    gci = dh["gross_ci"]
    assert gci["lo"] is not None and gci["lo"] <= dh["gross_gap"] <= gci["hi"]
    # The verdict must follow the interval, not a string someone typed.
    if dh["verdict"] == "alive":
        assert gci["lo"] > 0
    elif dh["verdict"] == "reversed":
        assert gci["hi"] < 0
    elif dh["verdict"] == "dead":
        assert gci["lo"] <= 0 <= gci["hi"]


def test_rent_bias_is_measured_not_asserted(payload):
    rb = payload["rent_bias"]
    assert rb["social"]["n"] > 0 and rb["market"]["n"] > 0
    assert rb["gap_pct"] < 0, "social housing must rent BELOW market"
    assert 0 < rb["social_share_pct"] <= 100


def test_price_index_negative_result_is_kept(payload):
    """The index made the residual slope worse. That is a result, so it ships,
    and the index must be OFF."""
    assert payload["meta"]["price_index_on"] is False
    rows = {(r["window"], r["index"]): r["slope"] for r in payload["index_test"]}
    assert rows, "index_test is empty"
    for w in (2, 4):
        if (w, "on") in rows and (w, "off") in rows:
            assert rows[(w, "on")] > rows[(w, "off")], \
                f"at +-{w} the index no longer hurts -- re-evaluate switching it on"


def test_coverage_share_is_published(payload):
    """The honest denominator: matched buildings over every building that sold."""
    h = payload["headline"]
    assert h["universe_buildings"] > h["buildings"]
    assert 0 < h["coverage_pct"] < 25
    assert abs(h["coverage_pct"] - h["buildings"] / h["universe_buildings"] * 100) < 0.05


def test_unparseable_address_rate_is_published(payload):
    """Normaliser recall is only ever measured on addresses that HAVE a number,
    so the share carrying none has to be visible."""
    a = payload["meta"]["addr"]
    assert a["no_key_pct"] < 1.0
    assert a["sale_total"] > 0 and a["rent_total"] > 0


def test_window_starts_at_the_schema_boundary(payload):
    assert payload["meta"]["seasons"][0] == "112S4"


def test_districts_respect_the_minimum_sample(payload):
    n = payload["meta"]["min_district_n"]
    for d in payload["districts"]:
        assert d["buildings"] >= n
        assert 0.3 < d["yield"] < 12


def test_buildings_are_unique_and_well_formed(payload):
    b = payload["buildings"]
    assert len(b) == payload["headline"]["buildings"]
    assert len({x["a"] for x in b}) == len(b), "one row per building"
    for x in b[:200]:
        assert x["a"].endswith("號") and x["y"] > 0 and x["p"] > 0 and x["n"] >= 1


# ── front-end tripwires ──────────────────────────────────────────────────

def test_no_smart_quotes_in_shipped_front_end():
    for path in (JS, CSS, HTML):
        src = _read(path)
        for ch in ("‘", "’", "“", "”"):
            assert ch not in src, f"smart quote {ch!r} in {os.path.basename(path)}"


def test_the_gzipped_payload_matches_the_json_one():
    """/housing_data.json serves the .gz to anyone sending Accept-Encoding: gzip,
    which is every browser — so a stale .gz is not a cache artefact, it is the
    site.

    This shipped: five commits took the payload national while housing_data.json.gz
    stayed on the two-city build, so the deployed page would have served 2,549
    buildings to everyone while the repo said 6,043 — and the new JS would have
    reached for map.counties and mortgage keys that build does not contain.
    Locally it looked perfect, because underwrite.py rewrites both.
    """
    import gzip
    j = os.path.join(ROOT, "housing_data.json")
    g = os.path.join(ROOT, "housing_data.json.gz")
    if not os.path.exists(j):
        pytest.skip("payload not built")
    assert os.path.exists(g), "the pre-gzipped payload is missing"
    with open(j, encoding="utf-8") as fh:
        plain = json.load(fh)
    with gzip.open(g, "rt", encoding="utf-8") as fh:
        packed = json.load(fh)
    assert packed.keys() == plain.keys(), (
        "the .gz has different top-level keys — it is a different build")
    assert len(packed["buildings"]) == len(plain["buildings"]), (
        f"the .gz holds {len(packed['buildings'])} buildings and the .json "
        f"{len(plain['buildings'])} — rebuild with underwrite.py and stage BOTH")
    assert packed["headline"] == plain["headline"]


def test_the_map_draws_what_it_had_to_throw_away(payload):
    """The map draws 6,043 of 157,594 buildings and reads as empty. That is true,
    and on its own it is unhelpful.

    The missing split in two, and only one half is recoverable. 113,761 have NO
    lease record at all — there is no rent, so there is nothing to draw and no
    amount of work changes that. The other 31,812 have BOTH records and are
    removed by our own filters; those can be drawn, and drawing them is the
    site's argument made visible rather than merely asserted.

    They carry a reason and no yield, so they can never be mistaken for a
    measurement."""
    E = payload["map"]["excluded"]
    assert len(E) > 20000, f"only {len(E)} excluded buildings shipped"
    for row in E[:200]:
        assert len(row) == 4, "rows are [x, y, type, why], not objects"
        x, y, t, why = row
        assert -120000 < x < 400000 and 2_400_000 < y < 2_950_000, "not TWD97 metres"
        assert t in (0, 1, 2) and why in (1, 2, 3)
    reasons = {r[3] for r in E}
    assert reasons == {1, 2, 3}, f"expected all three exclusion reasons, got {reasons}"

    src = _read(JS)
    fn = src[src.index("function exclHtml"):src.index("  // ── map search")]
    # One path per reason, not one node per building: 31,812 elements is a DOM
    # the browser has to lay out, three paths is three.
    assert "'<path class=\"hs-ex hs-ex'" in fn, "excluded buildings must batch into paths"
    assert "V.w > EXCL_W" in fn, "they must stay hidden at country scale"
    # And they must never reach a yield.
    assert "yield" not in fn and "gross" not in fn


def test_furniture_and_floor_are_measured_within_a_building(payload):
    """Two fields the registry has carried all along and this pipeline ignored.

    A furnished let is dearer and a high floor is dearer, but both concentrate in
    newer, better-located buildings — so a raw cross-sample comparison measures
    the buildings, not the furniture or the floor. The same-building design that
    produced the site's main finding controls for location, age, type, management
    and lift in one step.

    The floor result is a negative one and the reason this is worth printing:
    within a building the RENT premium per floor is small, and far smaller than
    the SALE premium per floor -- the floor premium people believe in is mostly
    newer towers being dearer in the first place, plus a price effect the rent
    does not follow. The figures are not restated here: this docstring used to
    say "0.06% per floor, under 1.2% across twenty" and the payload had long
    since moved to 0.11% and 2.2%, so a test meant to guard a published number
    was itself publishing a stale one."""
    w = payload.get("within_building") or {}
    f, fl = w.get("furnished"), w.get("floor")
    assert f and fl, "the within-building block is missing"

    # Measured as the median of PER-BUILDING differences, so one large building
    # cannot carry the result.
    assert f["buildings"] > 500, f"only {f['buildings']} buildings let both ways"
    assert 0 < f["pct"] < 25, f"furnished premium of {f['pct']}% is not credible"
    # The raw gap and the within-building gap must both be reported, because the
    # distance between them is the composition this design removes.
    assert "raw_pct" in f and "share_furnished" in f

    assert fl["buildings"] > 500
    assert abs(fl["pct_per_floor"]) < 1.0, (
        f"{fl['pct_per_floor']}% per floor would compound to something absurd "
        "over a tower and almost certainly means the floor parse is wrong")
    # The slope must be the one the page and the PDF print, derived from the two
    # figures it is built from -- 1.0 of slack on a 0.11 value is a parse guard,
    # not a check on the published number. The tolerance is one unit in the last
    # published place, because `slope_ppp_per_floor` and `base_ppp` ship rounded
    # (0.85 and 809.7) while pct_per_floor was computed before rounding, so the
    # reconstruction lands at 0.105 against a published 0.11.
    assert abs(fl["pct_per_floor"] - fl["slope_ppp_per_floor"] / fl["base_ppp"] * 100) < 0.01
    fs = w.get("floor_sale")
    if fs:
        assert abs(fs["pct_per_floor"] - fs["slope_ppp_per_floor"] / fs["base_ppp"] * 100) < 0.01
        # the sale side is the larger of the two; that gap IS the finding
        assert fs["pct_per_floor"] > fl["pct_per_floor"]
        assert abs(w["floor_gap_pp"] - (fs["pct_per_floor"] - fl["pct_per_floor"])) < 5e-3

    src = _read(JS)
    assert "function secWithin" in src
    fn = src[src.index("function secWithin"):src.index("function secDead")]
    assert "wbFloorNote" in fn, "the negative result must be stated, not just plotted"


def test_the_headline_ratio_matches_the_measured_coverage(payload):
    """The hero states the coverage as "one building in N".

    N used to be TYPED, and it drifted every time the method improved: 二十分之一
    against a measured 3.66%, then 二十六 against 3.83%, then wrong again when
    subtracting parking took coverage to 6.44%. This test used to pin the typed
    word to the payload. The headline is DERIVED now -- `Sf('heroH',
    Math.round(100 / h.coverage_pct))` -- which removes the failure mode instead
    of policing it, so the test asserts the derivation and only falls back to
    checking a word if someone types one again.
    """
    src = _read(JS)
    i = src.index("heroH:")
    line = src[i:src.index("],", i)]
    actual = 1.0 / (payload["headline"]["coverage_pct"] / 100.0)

    if "%s" in line:
        assert "Sf('heroH'" in src, "heroH takes a placeholder but nothing fills it"
        m = re.search(r"Sf\('heroH',\s*([^)]*\)?[^)]*)\)", src)
        assert m and "coverage_pct" in m.group(1), \
            f"heroH is not derived from coverage: {m.group(1) if m else None}"
        assert abs(round(actual) - actual) < 0.6, (
            f"coverage {payload['headline']['coverage_pct']}% rounds to "
            f"1-in-{round(actual)}, which is a stretch to state as a round ratio")
        return

    words = {"十": 10, "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
             "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
             "二十一": 21, "二十二": 22, "二十四": 24, "二十五": 25, "二十六": 26,
             "三十": 30, "四十": 40}
    en_words = {"ten": 10, "twelve": 12, "fourteen": 14, "fifteen": 15,
                "sixteen": 16, "eighteen": 18, "twenty": 20, "twenty-four": 24,
                "twenty-five": 25, "twenty-six": 26, "thirty": 30}
    zh = [n for w, n in words.items() if w + "棟裡只有一棟" in line]
    assert zh, f"the zh headline states no ratio: {line[:120]}"
    en = [n for w, n in en_words.items() if "in " + w in line]
    assert en, f"the en headline states no ratio: {line[:160]}"
    assert abs(max(zh) - actual) < 1.0 and abs(max(en) - actual) < 1.0, (
        f"headline says 1-in-{max(zh)}/{max(en)}, payload says 1-in-{actual:.1f}")

def test_every_str_entry_is_a_well_formed_pair():
    """An apostrophe inside a single-quoted string ends it.

    "does not describe Taiwan's housing market" shipped in the copy for the
    national switch and took the WHOLE FILE down with SyntaxError: Unexpected
    identifier 's' — a blank page, and pytest stayed green because nothing here
    executes JavaScript. This walks the STR table entry by entry and checks each
    one is exactly two closed single-quoted literals, which is the shape that
    breaks first when a quote leaks.
    """
    src = _read(JS)
    i = src.index("var STR = {")
    block = src[i:src.index("\n  };", i)]
    # Strip line comments so an apostrophe in prose about the code is ignored.
    block = re.sub(r"^\s*//.*$", "", block, flags=re.M)

    def literals(text):
        """Yield each single-quoted literal, honouring backslash escapes."""
        out, i2, n = [], 0, len(text)
        while i2 < n:
            if text[i2] != "'":
                i2 += 1
                continue
            j, buf = i2 + 1, []
            while j < n and text[j] != "'":
                if text[j] == "\\":
                    j += 1
                buf.append(text[j] if j < n else "")
                j += 1
            if j >= n:
                return out, False          # ran off the end: a quote leaked
            out.append("".join(buf))
            i2 = j + 1
        return out, True

    lits, closed = literals(block)
    assert closed, "an unterminated string literal in the STR table"

    entries = re.findall(r"^\s*(\w+):\s*\[", block, flags=re.M)
    assert len(entries) > 100, f"only found {len(entries)} STR entries — parser drifted"
    # Two literals per entry, and no literal may itself contain a bare quote.
    assert len(lits) == 2 * len(entries), (
        f"{len(entries)} entries but {len(lits)} string literals — "
        "an apostrophe has ended a string early")


def test_js_uses_css_variables_not_literal_colours():
    """Consequence: the light/dark toggle needs no re-render. #fff is the one
    allowed literal (text on a filled segment)."""
    # Strip HTML numeric entities first: &#9662; (the ▾ chevron) is not a colour,
    # and matching it was the same over-broad-substring mistake as searching the
    # file for the word "leaflet".
    src = re.sub(r"&#\d+;", "", _read(JS))
    found = set(re.findall(r"#[0-9a-fA-F]{3,6}\b", src))
    assert found <= {"#fff"}, f"literal colours in housing.js: {found}"


def test_css_defines_dark_under_both_scopes():
    css = _read(CSS)
    assert "prefers-color-scheme: dark" in css
    assert ':root[data-theme="dark"]' in css
    assert ':root:not([data-theme="light"])' in css, \
        "an explicit light stamp must beat OS dark"


def test_page_is_responsive_not_blocked_on_small_screens():
    assert re.search(r"@media\s*\(max-width:\s*900px\)", _read(CSS))


def test_every_string_has_both_languages():
    """The STR table is zh/en pairs. A one-element entry renders as undefined in
    the other language."""
    src = _read(JS)
    block = src[src.index("var STR = {"):src.index("function S(k)")]
    entries = re.findall(r"^\s{4}(\w+):\s*\[", block, re.M)
    assert len(entries) > 50
    # every bracketed literal in the table must contain a top-level comma
    for m in re.finditer(r"^\s{4}(\w+):\s*\[(.*?)\],\s*$", block, re.M | re.S):
        assert "'," in m.group(2) or '",' in m.group(2), \
            f"STR.{m.group(1)} looks like it has only one language"


def test_series_marks_are_assigned_in_fixed_order():
    """Identity follows the entity, never its rank: a filter that changes which
    types are on screen must not re-mark the survivors.

    The channel changed from colour to texture when the palette collapsed to one
    ink, but the rule did not. 建物型態 is CATEGORICAL, so it gets three
    different KINDS of mark — hatch, cross, stipple — indexed off TYPES. It must
    never borrow density, which is the ordinal channel and is spent on yield: if
    a type were drawn denser, a reader would rank the types.
    """
    src = _read(JS)
    assert "var TYPES = ['住宅大樓', '華廈', '公寓']" in src
    assert "'url(#hxt' + (i < 0 ? 1 : i + 1) + ')'" in src, (
        "series marks must be indexed off TYPES, not off sort order"
    )
    for pid in ("hxt1", "hxt2", "hxt3"):
        assert 'id="%s"' % pid in src, f"series texture {pid} is not defined"
    # hxt3 is the stipple: it must be dots, not a third line density.
    i = src.index('id="hxt3"')
    assert "circle" in src[i:i + 260], (
        "the third series mark must be a different KIND of mark, not a denser hatch"
    )


def test_scatter_drops_out_of_range_points_rather_than_clamping():
    """Clamping stacks outliers on the axis, which reads as a real cluster at
    exactly the value that is not real."""
    src = _read(JS)
    assert "var inRange = B.filter(" in src
    assert "scatDrop" in src


# ── simple / advanced ────────────────────────────────────────────────────

def test_page_has_two_depths_and_defaults_to_simple():
    """Most visitors are not underwriters. A page that opens on a residual-slope
    chart has already lost them, so simple is the default and advanced is opt-in."""
    src = _read(JS)
    assert "var MODE = 'simple';" in src
    assert "localStorage.getItem('hs-mode') || 'simple'" in src
    assert 'data-mode="simple"' in src and 'data-mode="advanced"' in src


def test_simple_mode_hides_the_method_sections():
    """The advanced-only sections must be built ONLY in the advanced branch --
    hiding them with CSS would still ship them to a reader who cannot use them."""
    src = _read(JS)
    branch = src[src.index("if (adv) parts.push("):src.index("parts.push(secMoi(), secTable()")]
    for fn in ("secLadder", "secBias", "secNet", "secDead", "secScatter", "secMethodChecks"):
        assert fn in branch, f"{fn} should be advanced-only"
    simple = src[src.index("var parts = [secHero()"):src.index("if (adv) parts.push(")]
    for fn in ("secLadder", "secNet", "secDead", "secMethodChecks"):
        assert fn not in simple, f"{fn} leaked into the simple view"


def test_simple_view_leads_with_the_finding_not_the_number():
    """Hierarchy carries the argument. The headline yield describes a 5% slice, so
    the coverage share is the hero and the yield is the supporting figure."""
    src = _read(JS)
    hero = src[src.index("function secHero()"):src.index("function stat(")]
    assert hero.index("coverage_pct") < hero.index("h.yield"), \
        "the yield is being presented ahead of the coverage caveat it depends on"


def test_js_net_yield_is_a_twin_of_the_python_one():
    """The page recomputes net yield live, so its arithmetic must match the file
    that produced the payload -- term for term."""
    src = _read(JS)
    fn = src[src.index("function netYield("):src.index("function medianOf(")]
    for term in ("vac / 100", "a.tax / 100", "a.repairs / 100", "1 + age / 50", "b.m ?",
                 "mode === 'flag'"):
        assert term in fn, f"netYield lost the {term} term"
    # v2.4: the vacancy term gained a per-building SHAPE. It must stay opt-in,
    # or the page's default stops matching the payload underwrite.py produced.
    assert "var vac = a.vacancy * (state.vshape && b.vs ? b.vs : 1);" in fn,         "the vacancy level must still come from the slider, shaped only on request"


def test_ladder_is_framed_as_a_measurement_not_an_accusation():
    """Rung 1 is not what anyone publishes. Claiming otherwise would be a
    strawman, so the copy has to say so in both languages."""
    src = _read(JS)
    assert "NOT a claim that anyone publishes rung 1" in src
    assert "沒有人真的那樣算" in src


# ── the pivot switch ─────────────────────────────────────────────────────

def test_subject_flag_makes_the_pivot_real_not_additive(client, appmod, monkeypatch):
    """With QUANTS_SUBJECT=housing the root URL IS the housing surface. Without
    it the stock site is untouched -- a flag, not a demolition, so it is safe to
    throw before anyone has decided the new thing is good enough."""
    monkeypatch.setattr(appmod, "_SUBJECT", "stocks")
    assert b"hs-root" not in client.get("/").data

    monkeypatch.setattr(appmod, "_SUBJECT", "housing")
    root = client.get("/")
    assert root.status_code == 200 and b"hs-root" in root.data
    legacy = client.get("/stocks-legacy")
    assert legacy.status_code == 200 and b"hs-root" not in legacy.data


# ── bias, uncertainty, sensitivity ───────────────────────────────────────

def test_coverage_loss_is_attributed_not_blamed_on_the_law(payload):
    """The headline reads as "this is what the law lets you see". Only ~80% of it
    is; the rest is our own filtering, and the split has to be published or the
    page is taking credit for a limitation it partly imposed."""
    wf = payload["coverage_waterfall"]
    assert wf["universe"] > wf["final"]
    assert wf["law_pp"] > 0 and wf["ours_pp"] > 0
    # every stage is a real reduction, and they reconcile to the final count
    assert [s["from"] for s in wf["steps"][1:]] == [s["to"] for s in wf["steps"][:-1]]
    assert wf["steps"][-1]["to"] == wf["final"]
    assert wf["steps"][0]["from"] == wf["universe"]
    for s in wf["steps"]:
        assert s["to"] <= s["from"] and s["whose"] in ("law", "ours")
    assert wf["ceiling_pct"] > wf["coverage_pct"], \
        "the no-filter ceiling must exceed what we actually publish"


def test_headline_denominator_is_every_building_that_sold(payload):
    """Filtering our own denominator would flatter the coverage figure."""
    assert payload["headline"]["universe_buildings"] == payload["coverage_waterfall"]["universe"]
    assert payload["headline"]["coverage_pct"] == payload["coverage_waterfall"]["coverage_pct"]


def test_selection_bias_is_corrected_not_just_described(payload):
    """Post-stratify the matched sample back onto the composition of the stock."""
    ps = payload["post_strat"]
    assert ps["by_both"]["n"] > 100
    assert ps["shift_pp"] != 0
    # price is where the bias lives; type-only reweighting barely moves it
    by_price = abs(ps["by_price"]["gross"] - ps["visible_gross"])
    by_type = abs(ps["by_type"]["gross"] - ps["visible_gross"])
    assert by_price > by_type, "if type ever dominates price, revisit the strata"
    top = [d for d in ps["deciles"] if d["d"] == 10][0]
    assert top["ratio"] > 1.5, "the expensive-decile over-representation is the finding"


def test_district_ranking_ships_with_intervals(payload):
    """A 23-way ranking with no uncertainty invites conclusions the sample cannot
    support. Most adjacent pairs are expected to overlap."""
    bs = payload["bootstrap"]
    o = bs["overall"]
    assert o["lo"] < o["median"] < o["hi"]
    assert bs["adjacent_pairs"] > 10
    assert 0 <= bs["adjacent_overlaps"] <= bs["adjacent_pairs"]
    for d in payload["districts"]:
        ci = bs["district"].get(d["county"] + "|" + d["district"])
        assert ci and ci["lo"] is not None and ci["hi"] is not None, \
            f"{d['district']} is ranked without an interval"
        assert ci["lo"] <= d["yield"] <= ci["hi"]


def test_within_building_dispersion_is_measured(payload):
    """The strongest claim against district averages -- so it must be computed,
    not asserted."""
    dp = payload["dispersion"]
    assert dp["buildings"] > 100 and dp["min_pairs"] >= 4
    assert dp["within_iqr"] > 0 and dp["between_iqr"] > 0
    assert dp["ratio"] == pytest.approx(dp["within_iqr"] / dp["between_iqr"], abs=0.02)


def test_repairs_conclusion_is_shown_under_both_specs(payload):
    """Age-scaled repairs could have manufactured the walk-up gap. Publishing the
    flat-rate number too is what makes that checkable."""
    rs = payload["repairs_spec"]
    assert {"gross", "age_scaled", "flat"} <= set(rs)
    assert abs(rs["flat"]) > abs(rs["age_scaled"]), \
        "age-scaling should be the conservative spec; if it flips, say so on the page"


def test_vacancy_breakeven_replaces_data_that_does_not_exist(payload):
    """District 空屋率 stopped being produced in ROC 109. Rather than plug a stale
    number, the page states what vacancy the top district would need."""
    vb = payload["vacancy_breakeven"]
    assert vb["breakeven_vacancy_pct"] > vb["default_vacancy_pct"]
    assert "109" in vb["note_zh"] and vb["note_en"]


def test_matched_buildings_are_compared_on_price(payload):
    """Price per ping is the yield denominator, so it is the comparison a critic
    reaches for first."""
    a = payload["age"]
    assert a["matched_ppp"] and a["unmatched_ppp"]
    assert a["ppp_diff_pct"] == pytest.approx(
        (a["matched_ppp"] / a["unmatched_ppp"] - 1) * 100, abs=0.2)


def test_page_renders_the_new_evidence():
    src = _read(JS)
    for fn in ("secPostStrat", "secDispersion"):
        assert "function " + fn in src
    branch = src[src.index("if (adv) parts.push("):src.index("parts.push(secMoi(), secTable()")]
    assert "secPostStrat" in branch and "secDispersion" in branch
    # the district chart must draw the CI, not the interquartile range
    dist = src[src.index("function secDistrict"):src.index("function secLadder")]
    assert "d._lo" in dist and "D.bootstrap" in dist
    assert "x(d.q1), y, x(d.q3)" not in dist, "still drawing the IQR instead of the CI"


def test_shell_evicts_the_stock_service_worker():
    """The stock SPA registers a service worker on this same origin. Any visitor
    who ever loaded the old site would otherwise be served a stale housing.js and
    a stale payload, silently and permanently. Caught in dev serving a 52 KB
    housing.js against a 64 KB file on disk."""
    html = _read(HTML)
    assert "serviceWorker" in html and "unregister" in html
    assert "caches.delete" in html


# ── the map ──────────────────────────────────────────────────────────────

def test_buildings_carry_surveyed_coordinates(payload):
    """Geocoding here is a JOIN against the government's own 門牌 file, not an
    API estimate, so coverage should be near-total rather than best-effort."""
    geo = payload["meta"]["geo"]
    # National scope changed what this can assert. Address-point files exist for
    # five counties, so the OVERALL rate is now a coverage fact, not a health
    # check. What still has to hold is that WHERE a county has a source, the join
    # lands -- a broken normaliser shows up as a county at 60%, not at 0%.
    by_county = {}
    for b in payload["buildings"]:
        c = by_county.setdefault(b["c"], [0, 0])
        c[1] += 1
        if b.get("mx") is not None:
            c[0] += 1
    sourced = {c: v for c, v in by_county.items() if v[0]}
    assert sourced, "no county placed a single building"
    # Six counties have an address-point file. Measured: 臺北 100.0%,
    # 桃園 99.8%, 新北 99.4%, 高雄 98.8%, 臺中 98.7%, 臺南 88.0%.
    #
    # 臺南 is the outlier and it is their file, not our normaliser: 19 of its 62
    # misses are 之N sub-numbers the registry records and the address file does
    # not carry. Falling back to the parent 門牌 would place the dot on a
    # neighbouring unit and turn a join into an estimate for 0.3% of buildings,
    # so the join stays strict and the gap stays visible.
    assert len(sourced) == 6, f"expected 6 sourced counties, got {sorted(sourced)}"
    for c, (hit, tot) in sorted(sourced.items()):
        assert hit / tot > 0.85, f"county {c} only geocoded {hit}/{tot}"
    hit = sum(v[0] for v in sourced.values())
    tot = sum(v[1] for v in sourced.values())
    assert hit / tot > 0.97, f"sourced counties only geocoded {hit}/{tot}"
    # 87.24% nationally, once 臺中 was wired. The rest are the 16 counties with
    # no address-point file at all.
    assert geo["rate"] > 85, f"only {geo['rate']}% of buildings geocoded overall"
    assert geo["district_agreement"] == 100.0, (
        "the district code->name maps in geocode.py are hard-coded and are only "
        "safe while every joined building agrees with the district 實價登錄 states")
    withxy = [b for b in payload["buildings"] if b.get("mx") is not None]
    assert len(withxy) == geo["matched"]


def test_map_coordinates_are_not_confused_with_the_yield(payload):
    """`y` is the gross yield on a building record. Naming the map coordinate `y`
    too silently blanked the yield on all 2,549 buildings, because the later key
    in a dict literal wins."""
    for b in payload["buildings"][:300]:
        assert 0.3 < b["y"] < 12, f"{b['a']} has y={b['y']} -- yield overwritten?"
        if b.get("mx") is not None:
            assert b["mx"] > 200000 and b["my"] > 2000000, "TWD97 metres expected"


def test_map_bounds_and_density_grid(payload):
    m = payload["map"]
    x0, y0, x1, y1 = m["bounds"]
    assert x1 > x0 and y1 > y0
    # Taiwan's main island is ~204 x 393 km. Anything past 500 km means a
    # far-flung record (東沙, 南沙太平島, 釣魚臺) has leaked into the extent.
    assert (x1 - x0) < 500000 and (y1 - y0) < 500000, "bounds exceed Taiwan"
    g = m["grid"]
    assert g["cell"] == 400 and len(g["cells"]) > 100
    for c in g["cells"][:50]:
        assert len(c) == 3 and c[0] >= 0 and c[1] >= 0 and c[2] > 0


def test_density_layer_counts_the_whole_universe_not_the_sample(payload):
    """The faint layer is the point of the map: it has to be every building that
    sold, or the contrast with the bright layer means nothing."""
    total = sum(c[2] for c in payload["map"]["grid"]["cells"])
    assert total > payload["headline"]["buildings"] * 5
    assert total <= payload["headline"]["universe_buildings"]


def test_map_is_rendered_without_a_tile_layer_or_a_dependency():
    """A basemap would put a third-party request on a page whose entire argument
    is that every number can be checked from open data."""
    src = _read(JS)
    assert "function secMap" in src and "function wireMap" in src
    # Test what the file DOES, not what it mentions: an earlier version of this
    # assertion searched for the substring "leaflet" and tripped on a comment
    # saying we deliberately do not use Leaflet.
    urls = re.findall(r"https?://[^\s\"\')]+", src)
    assert not urls, f"housing.js reaches off-origin: {urls[:3]}"
    assert "fetch(" in src and src.count("fetch(") == 1, \
        "the page should make exactly one request, for its own payload"
    assert "secMap()" in src[src.index("var parts = [secHero()"):src.index("if (adv)")], \
        "the map is a core surface, not advanced-only"


def test_map_has_zoom_and_reset():
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function rerender")]
    for h in ("pointerdown", "pointermove", "pointerup", "dblclick"):
        assert h in fn, f"map is missing the {h} handler"
    assert 'data-zoom="home"' in src, "no way back out of a zoom"


# ── map geometry ─────────────────────────────────────────────────────────

def test_district_outlines_are_real_geometry(payload):
    """365 records from the official national boundary shapefile, in-process."""
    ds = payload["map"]["districts"]
    # 368 districts nationally, less the two cities the registry reports at city
    # granularity: 新竹市's 3 polygons and 嘉義市's 2 fuse to one record each.
    assert len(ds) == 365, f"expected 365 national districts, got {len(ds)}"
    cs = {d["county"] for d in ds}
    assert len(cs) == 22, f"expected all 22 counties, got {len(cs)}"
    assert {"a", "f", "e", "h", "d"} <= cs, "a geocoded county is missing an outline"
    for d in ds:
        assert d["rings"] and all(len(r) >= 4 for r in d["rings"])
        for x, y in d["rings"][0][:5]:
            # National TWD97/TM2 extent, measured: x -39,041 (金門烈嶼)..361,423,
            # y 2,422,005 (屏東恆春)..2,919,171 (連江東引). The box is
            # boundaries.POPULATED -- 東沙, 南沙太平島 and 釣魚臺列嶼 are clipped
            # out of it, or one record's bbox spans 1,700 km and its label
            # anchor, centroid and zoom-to-fit all become meaningless.
            assert -120000 < x < 400000 and 2_400_000 < y < 2_950_000, "not TWD97 metres"


def test_every_reported_district_has_an_outline_and_a_label(payload):
    """A district in the ranking with no polygon would be invisible on the map."""
    have = {d["county"] + "|" + d["district"] for d in payload["map"]["districts"]}
    labels = payload["map"]["labels"]
    for d in payload["districts"]:
        k = d["county"] + "|" + d["district"]
        assert k in have, f"{k} is ranked but has no outline"
        assert k in labels, f"{k} has no label anchor"


def test_projection_is_validated_by_containment():
    """The only real test of the projection: a wrong datum or central meridian
    puts points somewhere plausible but in the WRONG polygon, and nothing else
    in the pipeline notices."""
    import json as _json
    import boundaries as BD
    p = os.path.join(ROOT, "housing_data.json")
    if not os.path.exists(p):
        pytest.skip("payload not built")
    d = _json.loads(_read(p))
    if not d["map"]["districts"]:
        pytest.skip("no boundaries in payload")
    # Validate the FINE geometry, never the shipped LOD.
    #
    # The payload ships districts simplified to 150 m so 365 of them can be
    # rasterised. Simplification alone walks containment down (99.88% at 45 m to
    # roughly 99% at 150 m and 97% at 400 m), so pointing this assertion at the
    # shipped geometry would turn a rendering decision into what looks like a
    # broken datum -- the exact failure this test exists to catch.
    shp = os.path.join(ROOT, "data", "geo", "twn")
    if not os.path.isdir(shp):
        pytest.skip("boundary shapefile not present")
    counties = {b["c"] for b in d["buildings"]}
    fine = BD.build(shp, tolerance=45.0, counties=counties,
                    dissolve={"i", "o"})
    res = BD.validate(fine, d["buildings"])
    assert res["rate"] > 98.0, f"only {res['rate']}% of buildings fall in their own district"
    # And the shipped set must be the same places, just coarser.
    shipped = {(x["county"], x["district"]) for x in d["map"]["districts"]}
    assert {(x["county"], x["district"]) for x in fine} <= shipped, \
        "the shipped LOD is missing districts the fine geometry has"


def test_forward_projection_round_trips_against_a_known_point():
    """臺北車站 sits near TM2 (302_000, 2_771_000). A sign error or a swapped
    axis moves this by kilometres."""
    import boundaries as BD
    x, y = BD.lonlat_to_tm2(121.5170, 25.0478)
    assert 301_000 < x < 303_500, x
    assert 2_770_000 < y < 2_772_500, y


def test_map_pans_and_zooms_by_viewbox_not_by_rerender():
    """Rebuilding 2,541 points plus 4,831 boundary vertices on every drag frame
    would stutter; the browser transform is free."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "setAttribute('viewBox'" in fn
    for h in ("wheel", "pointerdown", "pointermove", "dblclick"):
        assert h in fn, f"map missing the {h} handler"
    assert "data-zoom" in src and "hs-scale" in src, "no zoom controls or scale bar"
    # screen-sized marks must be restated in metres when the scale changes
    assert "metres per CSS pixel" in fn or "mpp" in fn


def test_map_strokes_do_not_scale_with_zoom():
    """Geometry is drawn in metres, so a 1-unit stroke would be a 1-metre stroke
    and district borders would vanish when zoomed out."""
    css = _read(CSS)
    assert "vector-effect: non-scaling-stroke" in css


# ── basemap layers and symbols ───────────────────────────────────────────

def test_basemap_ships_streets_mrt_and_water(payload):
    base = payload["map"]["base"]
    for layer in ("major", "secondary", "mrt", "river", "water"):
        assert isinstance(base[layer], str) and len(base[layer]) > 500, \
            f"{layer} layer is empty"
        assert base[layer].startswith("M"), "layers are pre-built SVG path data"
    assert len(base["stations"]) > 100, "MRT stations missing"
    # 4-tuples now: x, y, name, kind (0 = heavy rail, 1 = 輕軌). The kind is
    # load-bearing -- whether 輕軌 counts decides the yield-vs-distance result.
    assert all(len(s) == 4 and isinstance(s[2], str) and s[3] in (0, 1)
               for s in base["stations"])
    assert any(s[3] == 1 for s in base["stations"]), "no 輕軌 stations in the layer"
    assert base["quant"] >= 1


def test_basemap_credits_openstreetmap(payload):
    """OSM data is ODbL: attribution is a licence condition, not decoration."""
    assert "OpenStreetMap" in payload["map"]["base"]["attribution"]
    src = _read(JS)
    assert "OpenStreetMap" in src, "the page must display the attribution"


def test_basemap_is_delta_encoded_not_nested_arrays(payload):
    """A nested [[[x,y],...]] structure cost 467 KB for the same geometry: OSM
    splits roads into thousands of 2-point ways, so brackets and repeated
    7-digit coordinates outweighed the shape."""
    d = payload["map"]["base"]["major"]
    assert "l" in d and "[" not in d
    assert len(d) < 200_000, f"major roads layer is {len(d)} chars"


def test_building_type_is_encoded_by_shape_not_colour_alone():
    """Colour carries yield, shape carries type. Two variables, two channels --
    and type stays readable for someone who cannot separate the hues."""
    src = _read(JS)
    fn = src[src.index("function symbolPath"):src.index("function secMap")]
    assert "circle" in fn and "rect" in fn and "path" in fn, "need three distinct marks"
    for t in ("公寓", "華廈"):
        assert t in fn, f"{t} has no symbol branch"
    assert "symbolPath(b.t" in src, "the map still draws plain dots"


def test_wheel_zoom_is_normalised_across_input_devices():
    """A fixed per-event factor made one trackpad flick cross four zoom levels."""
    src = _read(JS)
    assert "deltaMode" in src, "wheel zoom does not normalise line vs pixel scrolling"


def test_detail_layers_are_zoom_gated():
    """3,700 secondary roads and 131 station names at full extent are a smear."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "hs-rd2" in fn and "hs-stnlab" in fn
    assert "V.w <" in fn, "no zoom threshold controls the detail layers"


def test_map_strokes_are_rescaled_rather_than_non_scaling():
    """This assertion used to demand vector-effect: non-scaling-stroke, which is
    the textbook answer for geometry drawn in world units -- and which measured
    at 8.5 SECONDS per zoom here, because the browser recomputes stroke geometry
    per segment in device space on paths with ~11,000 points.

    Widths are now set in metres by commit() on each zoom: a handful of
    setAttribute calls. Kept as a test so nobody reinstates the textbook answer.
    """
    css = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    assert "non-scaling-stroke" not in css
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "stroke-width" in fn and "mpp" in fn


def test_delegated_listeners_bind_exactly_once():
    """#hs-root survives a re-render (only its innerHTML changes), so binding the
    delegated click handler inside wire() stacked one listener per render. A
    single click then ran the handler N times, and any handler that FLIPS state
    -- `_layers[k] = !_layers[k]`, `state.desc` -- landed back where it started
    on an even count. Symptom: layer toggles silently did nothing."""
    src = _read(JS)
    assert "var _bound = false" in src
    w = src[src.index("function wire(root)"):src.index("function wirePerRender")]
    assert "if (_bound) return" in w, "root listeners can stack again"
    assert "root.addEventListener('click'" in w
    # per-render wiring must attach to nodes the render REPLACES, so it cannot stack
    pr = src[src.index("function wirePerRender"):src.index("function setRung")]
    for fn in ("wireScatter", "wireDistrict", "wireMap"):
        assert fn in pr, f"{fn} must be re-bound per render"
    assert "wireScatter()" not in w, "per-render wiring leaked into the once-only block"


def test_search_input_is_delegated_not_bound_per_render():
    """Same class of bug: a direct listener on #hs-q would be lost the moment a
    filter re-rendered the table controls."""
    src = _read(JS)
    assert "closest('#hs-q')" in src


def test_map_layers_are_individually_toggleable():
    src = _read(JS)
    assert "var _layers = {" in src
    for k in ("roads", "mrt", "water", "dens", "labels"):
        assert "'" + k + "'" in src or '"' + k + '"' in src, f"no {k} layer toggle"
    assert "_layers[lk] = !_layers[lk]" in src


# ── map redesign: clustering, panel, compact chrome ──────────────────────

def test_map_groups_by_district_not_by_a_screen_grid():
    """2,549 marks at full extent is a texture, not information -- but the first
    fix, a screen-space grid, grouped by an artefact of the current zoom. A grid
    bucket has no name and no boundary, so "23" over a road named nothing the
    reader could act on, and membership changed with every scale step. Groups are
    administrative districts: the unit the rest of the page already reports in."""
    src = _read(JS)
    assert "function districtGroups" in src
    assert "function clusterBuildings" not in src, "the screen grid must be gone"
    fn = src[src.index("function districtGroups"):src.index("function districtView")]
    assert "b.c + '|' + b.d" in fn, "group key must be county+district, not a cell"
    assert "med" in fn, "a badge needs a representative yield, not just a count"
    assert "bb" in fn, "a badge needs its extent, to zoom to fit on click"


def test_clicking_drills_one_level_and_fits_what_it_opened():
    """The mark is a door, not a label — and with 365 districts nationally it is
    a door into a HIERARCHY. One click always means "go one level deeper into the
    thing I clicked": country -> county -> district -> buildings."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "function focusCounty" in fn and "function focusDistrict" in fn
    assert "function drillTo" in fn, "one click, one level"
    assert "districtView(g)" in fn, "click must fit what it opened, not zoom a step"
    assert "_focus = { c: c, d: null }" in fn
    assert "_focus = { c: c, d: key }" in fn
    # allDistricts, not districtGroups: a district with no matched pair is still
    # a place a reader can ask to look at, and bouncing them back up to the
    # county reads as a dead click.
    assert "var gs = allDistricts(c);" in fn
    # Stepping back one level is the move a reader wants after drilling in.
    assert "function popFocus" in fn and "popFocus()" in fn
    # Both the mark and the polygon do the same thing. Two meanings for two
    # parts of one shape is not a distinction a reader can discover.
    assert "closest('.hs-dg')" in fn and "drillTo(dg.getAttribute" in fn
    assert "drillTo(t.getAttribute('data-dkey'))" in fn
    marks = src[src.index("function marksHtml"):src.index("  // \u2500\u2500 detail panel")]
    assert "g.key === _focus.d" in marks, "a focused district must render individually"
    # A county view must not also expand districts into buildings, or opening
    # 高雄市 puts 1,305 dots under 38 labels.
    assert "_level = 0" in marks and "_level = _focus.d ? 2 : 1" in marks


def test_the_map_is_a_county_district_building_hierarchy():
    """365 districts cannot share one canvas. Measured before the hierarchy, at
    national zoom: 166 marks, 356 overlapping label pairs out of 13,695, and
    label ink at 27.9% of the canvas while the country covered ~14% of it.

    After: 20 county marks, 0 overlaps, 3.4% ink; opening 高雄市 gives 43 marks
    (its 24 districts plus the other 19 counties, so a reader can step sideways
    without going home) and still 0 overlaps."""
    src = _read(JS)
    assert "function countyGroups" in src
    fn = src[src.index("function countyGroups"):src.index("  // Fit the BUILDINGS")]
    # Count and median over EVERY building; centroid over the ones we can place.
    assert "g.ys.push(b.y); g.items.push(b);" in fn
    assert "if (b.mx == null) continue;" in fn
    # A county with no address-point source has no building to average. Leaving
    # x=y=0 stacked all 17 unsourced counties on the origin, which drew 基隆市 on
    # top of 嘉義市 and 苗栗縣 on top of 屏東縣 -- 34 overlaps that looked like
    # crowding and were not.
    assert "D.map.labels" in fn, "unsourced counties need a polygon-derived anchor"
    assert "o.x = NaN" in fn, "a county with no anchor at all must drop out, not sit at 0,0"


def test_an_area_with_no_dots_still_fits_its_outline():
    """Clicking 臺中市 — 475 buildings, no address-point file yet — flew to a
    200 m scale bar in the middle of nowhere, because a group with nothing
    placeable fell back to its centroid as a ZERO-SIZE box and districtView()'s
    900 m floor did the rest. A county has an outline even when it has no dots,
    and the outline is the right thing to fit: it now opens at 20 km."""
    src = _read(JS)
    assert "function polyBBox" in src
    fn = src[src.index("function polyBBox"):src.index("  // Counties, on the same terms")]
    assert "D.map && D.map.districts" in fn, "the extent must come from the drawn rings"
    # A county key is the union of its districts', so both levels can fit.
    assert "_pbb[d.county]" in fn and "_pbb[dk]" in fn
    # And the reader is told which of the two empty-looking cases they are in.
    assert "noCoords" in src, "counts without coordinates must say so"


def test_a_city_is_one_block_at_national_zoom(payload):
    """臺南市 was drawn as the 37 districts it is made of, so the national view
    was a patchwork of tiny tiles rather than a map of cities. Painting them one
    colour is not enough on its own — the borders between them still draw.

    The shapefile turns out to support a real union: neighbouring districts share
    their common border vertex for vertex (measured on 臺南市: 37,396 edges used
    twice, 9,823 used once), so an edge used ONCE is on the county outline. That
    is what dissolve_counties() keeps, and it needs the RAW rings — RDP moves
    vertices per district and destroys the shared topology it depends on."""
    cs = payload["map"]["counties"]
    assert len(cs) == 22, f"expected 22 county outlines, got {len(cs)}"
    # A dissolve that failed to close its rings shows up as a point explosion.
    pts = sum(len(r) for c in cs for r in c["rings"])
    assert pts < 12000, f"county outlines cost {pts} points — the union leaked"
    for c in cs:
        assert c["rings"] and all(len(r) >= 4 for r in c["rings"])
    src = _read(JS)
    assert "hs-cland" in src and "hs-counties" in src
    # The two layers swap on level, or both draw and the tiles come back.
    fn = src[src.index("function commit"):src.index("function scaleBar")]
    assert "_level === 0 ? '' : 'none'" in fn and "_level === 0 ? 'none' : ''" in fn


def test_no_mark_is_pushed_off_the_canvas():
    """Displacement pushed 基隆市 seven pixels off the top edge, 屏東縣 off the
    bottom and 澎湖縣 off the left — three marks that were simply not on the map,
    one of them a city. Clamped flush to the edge 基隆市 then sat under the page's
    sticky header instead, so the clamp insets."""
    src = _read(JS)
    fn = src[src.index("function layoutLabels"):src.index("function labelHtml")]
    assert "vp[0] + q.hw" in fn and "vp[3] - q.hh" in fn, "labels must be clamped"
    assert "0.02" in fn, "the clamp must inset, not sit flush against the edge"


def test_the_ranking_is_two_level_like_the_map(payload):
    """59 district rows in one fixed-height card is a 1,594 px column, and a
    reader comparing 高雄 with 臺北 has to scroll past forty rows that are
    neither. Counties rank first (13 rows, 398 px); opening one ranks its
    districts. Both levels obey the same n >= MIN_DISTRICT_N floor, and both
    carry a bootstrap CI rather than a bare dot — otherwise the top level would
    be the only place on the page showing a median with no uncertainty."""
    cs, ds = payload["counties"], payload["districts"]
    floor = payload["meta"]["min_district_n"]
    assert cs and len(cs) < len(ds), "the county level must be the shorter one"
    for c in cs:
        assert c["buildings"] >= floor, f"{c['city']} ranked on {c['buildings']}"
        assert c["districts"] >= 1
    assert [c["yield"] for c in cs] == sorted(c["yield"] for c in cs)
    # Every ranked county has an interval, and so does every ranked district.
    bc = payload["bootstrap"]["county"]
    assert {c["county"] for c in cs} <= set(bc), "a ranked county has no CI"
    bd = payload["bootstrap"]["district"]
    assert {d["county"] + "|" + d["district"] for d in ds} <= set(bd)
    # Every district that ranks belongs to a county that ranks, or opening the
    # county it belongs to would show rows the county level never listed.
    assert {d["county"] for d in ds} <= {c["county"] for c in cs}

    src = _read(JS)
    fn = src[src.index("function secDistrict"):src.index("function secLadder")]
    assert "var atCounty = !_rankCounty" in fn
    assert 'data-rank="' in fn, "a county row must be a door, not a filter"
    # Opening a county must not leave another county's district filter applied.
    wire = src[src.index("var rk = e.target.closest('[data-rank]')"):]
    assert "state.district = null" in wire[:600]


def test_district_polygon_does_not_carry_data_d():
    """It used to. The root-level delegated [data-d] handler matched it as well,
    so the svg handler set state.district and rerendered, the event bubbled to
    #hs-root -- which survives a rerender -- and toggled it straight back.
    Clicking a district on the map did nothing at all."""
    src = _read(JS)
    i = src.index("class=\"hs-land")
    land = src[i:src.index("}).join('');", i)]
    assert "data-d=" not in land, "collides with the root [data-d] handler"
    assert "data-dkey=" in land


def test_pointer_capture_is_taken_lazily_not_on_pointerdown():
    """Capturing on pointerdown retargets pointerup AND the click to the <svg>
    itself, so e.target.closest('.hs-dg' / '.hs-mdot' / '.hs-land') matched
    nothing and EVERY click on the map was silently dead. Capture only exists to
    keep receiving moves after the pointer leaves the element, which cannot
    happen before it has moved -- so take it on the first real move."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    down = fn[fn.index("sv.addEventListener('pointerdown'"):fn.index("sv.addEventListener('pointermove'")]
    single = down[down.index("if (pointerCount() === 1)"):down.index("else if (pointerCount() === 2)")]
    assert "setPointerCapture" not in single and "grab(" not in single, \
        "a single pointer must not be captured before it moves"
    # Pinch genuinely needs both pointers captured from the start.
    assert "grab(+k[z])" in down


def test_a_tap_is_not_treated_as_a_drag():
    """Any pointermove at all used to set moved=true, and the click handler bails
    when moved is set -- so the smallest tremor between down and up swallowed the
    click."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "Math.abs(e.clientX - panStart.cx) < 4" in fn
    assert "Math.abs(e.clientY - panStart.cy) < 4" in fn


def test_svg_height_attribute_tracks_the_target_aspect():
    """With `height: auto` an SVG takes its intrinsic ratio from the width/height
    ATTRIBUTES, not from the viewBox. A hard-coded 640 pinned the surface to
    landscape, so the portrait phone box was computed and then ignored -- the map
    stayed 341x248 on a 375 px screen."""
    src = _read(JS)
    assert "var W = MAP_W, H = Math.round(MAP_W / mapAR());" in src
    assert "function mapAR" in src
    # A cached home box of the wrong shape survives a rotation; it must not.
    assert "_mapHomeAR === mapAR()" in src


def test_density_grid_is_hidden_once_zoomed_into_a_district():
    """Its 400 m cells are the coverage argument at city scale and a grey
    checkerboard the size of city blocks at street scale, where they bury the
    buildings the reader just asked to see."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "hs-dens" in fn and "V.w < 20000 ? 'none' : ''" in fn


def test_district_marks_are_type_not_discs():
    """The mark was a filled disc with the count inside it -- the conventional
    cluster glyph, and wrong twice over on a map this size. 33 discs cover the
    geography the map exists to show, and the disc was spending its fill on a
    value the polygon underneath now carries. The number is the mark."""
    src, css = _read(JS), _read(CSS)
    assert "hs-clust" not in src and "hs-clust" not in css, "the disc is back"
    assert "hs-dcount" in src and ".hs-dcount" in css
    # A glyph's own ink is a thin thing to ask a thumb to hit.
    assert "hs-dhit" in src and ".hs-dhit { fill: none; pointer-events: all; }" in css


def test_district_labels_are_displaced_and_never_dropped():
    """Placed honestly on their own centroid, 27 of 528 pairs overlapped and the
    Taipei core was an unreadable pile -- so marks are displaced, on a leash, and
    the leash is what keeps a name inside the district it names.

    The badge layout then DROPPED any name it could not place: 9 of 33 at full
    extent, and always the dense ones in the core, which are exactly the names a
    reader wants most. Names are part of the mark now, so the layout has to make
    room instead of giving up. Nothing in here may drop one."""
    src = _read(JS)
    fn = src[src.index("function layoutLabels"):src.index("function labelHtml")]
    assert "LEASH" in fn, "displacement must be bounded"
    assert ".name = false" not in fn and "slots" not in fn, "a name must never be dropped"
    assert "markScale" in src, "mark size must scale to the canvas, not be fixed px"
    # Separation along the cheaper axis: a wide, short block almost always wants
    # to move vertically, and pushing it radially wasted most of the leash.
    assert "a.hw + b.hw" in fn and "a.hh + b.hh" in fn


def test_district_polygons_are_a_median_yield_choropleth():
    """One flat surface colour behind a hairline border made 33 districts read as
    a single shape on a dark map, and left the value to be carried by a disc
    drawn on top of the geography. The area map puts the value on the area."""
    src, css = _read(JS), _read(CSS)
    i = src.index("class=\"hs-land")
    land = src[i:src.index("}).join('');", i)]
    # yieldFillAt(_, 1), not yieldFill: a DISTRICT median is a different quantity
    # from a building and gets its own ramp domain, or the choropleth flattens.
    assert "yieldFillAt(dmed[dk].med, 1)" in land, "the polygon must carry its median yield"
    # A CSS `fill` beats a presentation attribute and would flatten the ramp.
    block = css[css.index(".hs-land {"):css.index(".hs-dlabel")]
    assert "fill:" not in block.split(".hs-land.on")[0], \
        "an unconditional fill in CSS overrides the per-district attribute"
    assert "fill-opacity" in block


def test_district_boundaries_are_drawn_above_the_other_layers():
    """Stroked as part of the fill, the edges were painted over by the roads and
    by the density grid -- which is why there was no visible separation between
    districts at all."""
    src, css = _read(JS), _read(CSS)
    assert "hs-bounds" in src and ".hs-bound {" in css
    svg = src[src.index("'<g transform=\"scale(1,-1)\">'"):]
    svg = svg[:svg.index("</g>")]
    assert svg.index("bounds") > svg.index("roads"), "boundaries must sit above the roads"
    assert svg.index("bounds") > svg.index("cells"), "boundaries must sit above the density grid"
    assert svg.index("bounds") < svg.index("marks"), "boundaries must sit under the marks"
    # Every decorative layer is click-through, or a click that lands on a road
    # hits the road instead of the district it is drawn on.
    assert "pointer-events: none; }" in css[css.index(".hs-water, .hs-river"):]


def test_a_focused_district_is_the_only_housing_on_the_map():
    """The viewport rule opened every district near the viewport once zoomed in.
    After clicking one, that meant its neighbours opened too -- which answers a
    question nobody asked and buries the district that was just clicked."""
    src = _read(JS)
    fn = src[src.index("function marksHtml"):src.index("  // \u2500\u2500 detail panel")]
    assert "var detail = !_focus" in fn, "focus must suppress the viewport rule"
    css = _read(CSS)
    assert ".hs-land.dim" in css and ".hs-land.foc" in css, "the rest must step back"
    commit = src[src.index("function commit"):src.index("function scaleBar")]
    assert "classList.toggle('dim'" in commit, "dimming must be class work, not a re-render"


def test_css_never_restates_what_commit_sets_as_an_attribute():
    """An author CSS declaration beats a presentation attribute, and the map is
    drawn in TWD97 METRES -- so every "placeholder" width and size in the CSS
    silently won over the value commit() computes, and won as a length in metres.
    `stroke-width: 1.9` was a 1.9-metre road: 0.03 px at city scale.

    Every stroke on this map rendered as a sub-pixel ghost that way, the district
    boundaries could not be seen at all, and the eight districts whose only name
    comes from .hs-dlabel were drawn at a seventh of a pixel. The halo on
    .hs-dgname was the only one that ever worked, because it was the only rule
    that left the property out."""
    css = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    src = _read(JS)
    # Whatever commit() rescales, plus the two mark layers it sizes.
    managed = re.findall(r"\['(\.[a-z0-9-]+)(?: path)?',", src)
    assert ".hs-bound" in managed and ".hs-rd1" in managed, "STROKES table not found"
    for sel in set(managed) | {".hs-dlabel", ".hs-stnlab", ".hs-mdot"}:
        # (?![\w-]) or the selector matches a LONGER class that starts with it:
        # ".hs-ex" matched ".hs-exlab" and failed on that rule's font-size. Same
        # over-broad-substring mistake the handoff records twice, this time in
        # the test that exists to catch a different one.
        for m in re.finditer(re.escape(sel) + r"(?![\w-])[^{]*\{([^}]*)\}", css):
            body = m.group(1)
            assert "stroke-width" not in body, f"{sel} restates stroke-width in CSS"
            assert "font-size" not in body, f"{sel} restates font-size in CSS"


def test_focus_control_lives_inside_the_map():
    """Once you are zoomed into a district the page header has scrolled away, and
    nothing else on screen names the district you are looking at."""
    src = _read(JS)
    assert "hs-focuspill" in src
    sec = src[src.index("function secMap"):src.index("function countSize")]
    head = sec[sec.index("hs-maphead"):sec.index("hs-mapwrap")]
    assert "hs-focuspill" not in head, "the pill must not sit in the scrollable header"
    css = _read(CSS)
    assert ".hs-focuspill" in css and "position: absolute" in css


def test_detail_panel_becomes_a_bottom_sheet_on_a_phone():
    """A 330 px side panel is the entire map on a 375 px screen."""
    css = _read(CSS)
    i = css.index("@media (max-width: 700px)")
    block = css[i:css.index("}\n", css.index(".hs-panel.on { transform: translateY(0); }", i))]
    assert "translateY(100%)" in block and "max-height" in block


def test_mark_rebuilds_are_thresholded_not_per_frame():
    """Rebuilding marks mid-drag was what made panning stutter, and rebuilding
    via rerender() was what made zooming take 8.5 seconds. District grouping does
    make a pan able to change the answer -- a new district scrolls into view --
    so the pan key is quantised to a third of the viewport rather than removed."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "lastMarkMpp" in fn, "no scale threshold guards the mark rebuild"
    assert "var pq = V.w / 3" in fn, "pan key must be quantised, not per-pixel"
    pan = fn[fn.index("if (panStart) {"):fn.index("if (e.pointerType === 'touch')")]
    assert "schedule(false)" in pan, "panning must not force a mark rebuild"


def test_yield_ramp_is_sequential_and_tokenised():
    """Six ordered steps of HATCH DENSITY, and the key must describe the map.

    The ramp used to be one hue light->dark (--y1..--y6). It is now hatch
    pitch, for the same reason the old rainbow proposal was declined: density,
    like luminance, can only be read one way, so a reader never has to consult
    the key to learn which end means "more".

    Three things are guarded here, and the third is new. The ramp may not be
    hard-coded hex in JS; the pattern ink must stay a token so a theme flip
    repaints the whole choropleth with no re-render (the property the --yN
    tokens used to provide); and HATCH[] in housing.js must stay numerically
    identical to .hs-y1..6 in housing.css, because those two are the map and
    its legend and a drift between them makes the key a lie.
    """
    import re

    src, css = _read(JS), _read(CSS)

    assert "url(#hx" in src, "the ramp must reference the hatch patterns"
    assert re.search(r"return 'var\(--y", src) is None, "the colour ramp is gone"
    assert 'stroke="var(--text)"' in src, (
        "hatch ink must be a token, or a theme flip needs a full re-render"
    )

    # JS side: [pitch, nib] per step.
    m = re.search(r"var HATCH = (\[\[.*?\]\]);", src, re.S)
    assert m, "HATCH[] not found in housing.js"
    steps = json.loads(m.group(1))
    assert len(steps) == 6, f"expected 6 ramp steps, found {len(steps)}"

    # Coverage must increase monotonically or the ramp is not ordinal.
    cover = [nib / pitch for pitch, nib in steps]
    assert all(b > a for a, b in zip(cover, cover[1:])), (
        f"hatch coverage is not monotonic: {[round(c, 3) for c in cover]}"
    )
    # Below ~2.5 CSS px a hatch moires on non-retina displays and vanishes in print.
    assert min(p for p, _ in steps) >= 2.5, "hatch pitch below the moire floor"

    # CSS side: the legend swatches, which must match JS step for step.
    for i, (pitch, nib) in enumerate(steps, 1):
        mm = re.search(
            r"\.hs-y%d\s*\{[^}]*?var\(--text\)\s*0\s*([\d.]+)px,\s*transparent\s*"
            r"[\d.]+px\s*([\d.]+)px" % i,
            css,
        )
        assert mm, f"legend swatch .hs-y{i} missing or not a hatch"
        assert float(mm.group(1)) == nib, (
            f".hs-y{i} nib {mm.group(1)} != HATCH nib {nib} — the key lies about the map"
        )
        assert float(mm.group(2)) == pitch, (
            f".hs-y{i} pitch {mm.group(2)} != HATCH pitch {pitch} — the key lies about the map"
        )


def test_hatch_tiles_are_scaled_in_metres():
    """The map's user unit is a METRE, so a 9-unit tile is a NINE-METRE tile.

    Left unscaled that is ~0.02 px at national zoom and ~18 px on one building:
    the same class of bug as the CSS stroke-width that once drew every road as
    a sub-pixel ghost. commit() must re-cut the tiles from mpp on every zoom.
    """
    src = _read(JS)
    assert "function sizeHatch" in src, "hatch tiles are never resized"
    assert "sizeHatch(mpp)" in src, "commit() does not re-cut the hatch on zoom"
    assert "HATCH[i][0] * mpp" in src, "tile pitch is not converted to metres"
    assert "HATCH[i][1] * mpp" in src, "tile nib is not converted to metres"
    # The pattern is referenced from inside <g transform="scale(1,-1)">, which
    # mirrors every angle. Written as +28 the map would hatch against the page.
    assert "rotate(-28)" in src, "hatch angle is not corrected for the y-flip"


def test_presale_never_reports_a_yield():
    """A flat that does not exist cannot be rented, so it can never have a yield.

    This is not a data gap to be filled later — it is the nature of the thing,
    and it is the reason pre-sale belongs on this page at all: 180,835 dwellings
    the headline is structurally blind to. If a yield ever appears in this block
    it means something was matched that should not have been.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def presale_block")
    whole = src[i:src.index("\ndef ", i + 1)]
    assert "can never have a yield" in whole, "the reason is undocumented"
    # Check the CODE, not the docstring — the docstring is where the words
    # "lease" and "yield" are supposed to appear, at length.
    a = whole.index('"""')
    b = whole.index('"""', a + 3) + 3
    code = whole[:a] + whole[b:]
    for bad in ("gross", "net_yield", "match_pairs", "rents", "lease"):
        assert bad not in code, f"presale_block touches {bad}; pre-sale has no lease"


def test_presale_curve_never_ships_without_its_placebo():
    """The falling curve is not evidence, and the first version of this treated
    it as if it were.

    Pushing the completed comparison forward collapses the gap from +30.2% to
    +4.3%, which looks like proof that the gap is the three-year delivery wait
    being priced in. Run the identical shift between two COMPLETED groups, where
    no delivery wait exists, and it falls almost as fast (-20.6% at two years) —
    because prices rise, which is what every comparison across time does. Divide
    that out and the residual premium is FLAT at about +31% at every lag.

    So "pre-sale prices the delivery date" and "a persistent ~30% premium on top
    of ordinary growth" predict the same curve, and this data cannot separate
    them. The placebo is what makes that visible, so the curve may never ship
    without it, and the block must not claim the question is settled.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def presale_block")
    body = src[i:src.index("\ndef ", i + 1)]
    assert "placebo_pct" in body, "the placebo curve is not computed"
    assert '"separable": False' in body, (
        "the block must record that the two explanations cannot be told apart"
    )
    assert "residual_pct" in body, "the time-adjusted residual is not computed"

    js = _read(JS)
    k = js.index("function secPresale")
    sec = js[k:js.index("\n  function ", k + 1)]
    assert "naive_gap_pct" in sec, "the naive figure is not shown"
    assert "placebo_pct" in sec, "the placebo is not drawn beside the gap"
    assert "prePlac" in sec, "the placebo is drawn but never explained"
    # and the heading must not assert the conclusion the placebo removed
    assert "that is not a premium" not in js, (
        "the page still asserts the retracted conclusion"
    )


def test_presale_comparison_group_excludes_contracts_signed_before_completion():
    """交易年月日 in the 買賣 file is the CONTRACT date, not the handover date.

    Two published versions of this section filtered "age <= 2" on the completion
    year alone. Measured: 168,426 of the 186,550 rows that selected — 90.3% —
    were contracts signed BEFORE the building existed, median age at contract
    -2.17 years. The comparison group was the previous pre-sale cohort, so the
    published +30.2% was pre-sale against pre-sale, and no placebo could catch it
    because both placebo arms came from the same contaminated group. Corrected,
    the gap is +5.4%.

    The `age >= 0` floor is the load-bearing half. Re-anchoring the year alone —
    the fix two independent reviewers prescribed — keeps every one of those rows
    and moves the headline by about a point.

    This asserts the PROPERTY, not a source string. The previous test asserted
    that the literal text "C.age <= 2" appeared, which was true of the defective
    filter and false of the correct one: it defended the bug.
    """
    def ym(v):
        """ROC yyyymmdd -> decimal ROC year, the same arithmetic presale_block uses."""
        return (v // 10000) + (min(max((v // 100) % 100, 1), 12) - 1) / 12.0

    def age(txn, built):
        return ym(txn) - ym(built)

    # sold in 113, built in 111 -> two years old, in.
    assert 0 <= age(1130601, 1110601) <= 2
    # sold in 113, built in 113 -> brand new, in.
    assert 0 <= age(1131201, 1130101) <= 2
    # sold in 110, built in 113 -> contract signed three years before the
    # building existed. This is the row that broke it, and it must be OUT.
    a = age(1100601, 1130601)
    assert a < 0, "a pre-completion contract must have negative age"
    assert not (0 <= a <= 2), "the filter must exclude contracts signed pre-completion"

    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def presale_block")
    body = src[i:src.index("\ndef ", i + 1)]
    assert "115 - pd.to_numeric" not in body, "the hardcoded year anchor is back"
    assert "age.between(0, 2)" in body, "the age >= 0 floor is missing"
    assert "MIN_DISTRICT_N" in body, "the sample floor is not applied"
    # both sides must be indexed on the contract quarter, never the zip season
    assert 'P["cq"]' in body and 'C["cq"]' in body, "sides are not on a contract clock"
    assert "P.season.map" not in body, "the publication season is still the clock"


def test_quiet_text_tiers_meet_contrast_in_both_themes():
    """--subtle carries sample sizes and ladder rung numbers, not decoration.

    Measured in a browser: at the old values it ran 2.53-2.74:1 in light and
    3.15-3.47:1 in dark, on 11.5-12px text, against a 4.5:1 requirement. The
    text it carries is 「across 3,206 buildings letting furnished and
    unfurnished」 — the sample size, which is exactly the figure this page
    insists a reader should be able to check.

    There is no room on this ground between passing 4.5:1 and --muted, so the two
    tiers have converged. That is the honest outcome: a quieter grey a reader
    cannot read is not a tier, it is a defect.
    """
    import re

    css = _read(CSS)

    def lum(h):
        h = h.lstrip("#")
        ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        f = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]

    def ratio(a, b):
        la, lb = lum(a), lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    def block(pat):
        m = re.search(pat, css)
        i = css.index("{", m.start())
        d = 0
        for k in range(i, len(css)):
            if css[k] == "{":
                d += 1
            elif css[k] == "}":
                d -= 1
                if d == 0:
                    return css[i:k]
        return ""

    def tok(b, name):
        m = re.search(r"--%s:\s*(#[0-9a-fA-F]{6})" % name, b)
        return m.group(1) if m else None

    light = block(r"(?m)^:root\s*\{")
    dark = block(r':root\[data-theme="dark"\]')

    # every quiet tier, against every ground it can land on in its own theme
    for theme, blk, grounds in (
        ("light", light, ["paper", "surface2"]),
        ("dark", dark, ["paper", "surface2"]),
    ):
        for tier in ("subtle", "muted", "text2"):
            fg = tok(blk, tier)
            assert fg, f"--{tier} missing from the {theme} block"
            for g in grounds:
                bg = tok(blk, g)
                assert bg, f"--{g} missing from the {theme} block"
                r = ratio(fg, bg)
                assert r >= 4.5, (
                    f"{theme}: --{tier} {fg} on --{g} {bg} is {r:.2f}:1, "
                    f"below the 4.5:1 needed for body-size text"
                )


def test_building_panel_is_keyboard_dismissable_and_returns_focus():
    """The panel is a dialog in everything but name, and behaved like a div.

    Three defects, all of which a keyboard user hits immediately: opening it
    left focus on the map so there was nothing to read; Escape reached the map's
    handler and zoomed the country out from under the reader instead of closing
    the thing they had just opened; and closing it dropped focus to <body>, with
    two thousand marks between the reader and the one they had been on.
    """
    src = _read(JS)
    assert 'el.setAttribute(\'role\', \'dialog\')' in src, "the panel is not announced as a dialog"
    assert "_panelReturn" in src, "focus is never returned to where it came from"
    assert "back.isConnected" in src, (
        "a re-render can detach the return target, and focusing a detached node "
        "silently sends focus to body"
    )
    # And the detached case is the COMMON one: opening a building from the map
    # search closes the result list, so the button the reader came from is gone
    # by the time the panel shuts. Verified in a browser before this was written.
    i = src.index("function closePanel")
    body = src[i:i + 1600]
    assert "hs-mapsvg" in body and "tabindex" in body, (
        "closePanel must fall back to the map when the return target is gone, "
        "not drop the reader at the top of the document"
    )
    # Escape must try the panel FIRST, then fall through to the map.
    i = src.index("if (e.key === 'Escape') {")
    assert "closePanel()" in src[i:i + 260], (
        "Escape must close an open panel before it pops the map focus"
    )
    # and it must work from inside the panel, which is a sibling of the svg
    assert "bindPanelEsc" in src, "Escape is only bound on the map"
    assert "closest('#hs-mapsvg')" in src, (
        "the document handler must yield to the map handler while focus is on the map"
    )


def test_presale_curve_publishes_cluster_intervals():
    """261 cells at the first rung are 71 clusters; 55 at the last are 30.

    Cells inside one district and building type are not independent draws — the
    same streets and often the same 建案 supply several quarters of them — so the
    cell count flatters the evidence. The page bootstraps over clusters
    everywhere else and this rung was the odd one out.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def presale_block")
    body = src[i:src.index("\ndef ", i + 1)]
    assert "_cluster_ci" in body, "no cluster bootstrap"
    assert '"ci_lo"' in body and '"clusters"' in body, "intervals are not published"
    js = _read(JS)
    assert "c.ci_lo" in js, "the intervals are computed but never shown"


def test_presale_publishes_its_reach():
    """The lead prints 180,835 dwellings; the gap is computed on a third of them.

    On a page that ships a coverage waterfall with a labelled row for every
    dropped building, a headline computed on 35% of the stock cannot arrive with
    nothing saying so.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def presale_block")
    body = src[i:src.index("\ndef ", i + 1)]
    for k in ("reach_dwellings", "reach_pct", "reach_districts", "floor_sensitivity"):
        assert k in body, f"presale_block does not publish {k}"
    js = _read(JS)
    assert "preReach" in js, "the reach is computed but never shown to the reader"

def test_tolerant_read_is_presale_only_and_reports_what_it_skipped():
    """12 pre-sale files have ragged rows; sale and rent files have none.

    A tolerant read on the sale side would turn a future export bug into silent
    data loss, so it is off there and there is no way to turn it on by accident.
    And a recovery that does not say what it cost is just a quieter kind of loss,
    so the skipped-row count is printed.
    """
    src = _read(os.path.join(SRC, "fetch_lvr.py"))
    assert "def read_csv_from_zip(zpath, member, tolerant=False)" in src, (
        "tolerant reading must be opt-in and default off"
    )
    assert 'read_csv_from_zip(zpath, f"{c}_lvr_land_b.csv", tolerant=True)' in src, (
        "pre-sale must be the one caller that opts in"
    )
    # the sale/rent loader must not pass it
    i = src.index("def load_season")
    body = src[i:src.index("\ndef ", i + 1)] if "\ndef " in src[i:] else src[i:]
    assert "tolerant" not in body, "load_season must never read tolerantly"
    assert "skipped" in src, "the tolerant path does not report what it dropped"


def test_auction_source_is_labelled_as_金拍_not_法拍():
    """These are different auction systems and conflating them is a real error.

    法拍 is the court auction run by 司法院 under compulsory execution. 金拍 is
    a bank disposing of collateral through TFASC. A reader who takes a 金拍
    number for a 法拍 number has been misled about both the size and the nature
    of the channel, so the distinction is stated in the fetcher, in the block,
    and on the page itself.
    """
    src = _read(os.path.join(SRC, "fetch_fasc.py"))
    assert "This is 金拍, NOT 法拍" in src, "the fetcher does not state which auction system it reads"
    js = _read(JS)
    assert "aucP" in js, "the page does not carry the 金拍/法拍 disclaimer string"
    assert "金拍是銀行透過台灣金服處分抵押品的管道" in js


def test_auction_block_never_reaches_the_network_at_build_time():
    """A build must not depend on a third-party site being up.

    fetch_fasc.py talks to TFASC; fasc_block reads only what that already wrote
    to disk. If the cache is absent the block is empty and the section does not
    render — the page loses a section rather than the build losing a run.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def fasc_block")
    body = src[i:src.index("def within_building_block")]
    for bad in ("requests.", "fetch_sessions", "fetch_items", "load_auctions"):
        assert bad not in body, f"fasc_block reaches the network via {bad}"
    assert "os.path.isdir(cache_dir)" in body, "fasc_block does not guard a missing cache"


def test_auction_block_makes_no_price_comparison():
    """The feed carries no floor area, so a price-per-ping cannot exist here.

    Comparing a total auction price against a market median would compare a
    studio to a townhouse, and reserve prices fall by round, so even a
    like-for-like gap would be measuring the auction calendar. The block reports
    the competition rate and the registry-visibility rate, and no price gap.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def fasc_block")
    body = src[i:src.index("def within_building_block")]
    assert "NOT a price comparison" in body, "the no-price-comparison rule is undocumented"
    for bad in ("discount", "vs_market", "ppp"):
        assert bad not in body, f"fasc_block computes {bad}, which the feed cannot support"


def test_floor_is_measured_on_both_sides():
    """One slope answers half a question.

    Rent rises with floor and so does price; which rises faster is what decides
    whether the yield goes up or down as you climb. Both are measured WITHIN a
    building, so the comparison controls for location, age, type and lift in one
    step — and the sale side must not sit behind the rent guard, or a run with
    no usable rents silently drops it.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def within_building_block")
    j = src.index("\ndef ", i + 1)          # to the next top-level def, not a byte guess
    body = src[i:j]
    assert "floor_sale" in body, "no sale-side floor slope"
    assert "floor_gap_pp" in body, "the two slopes are never compared"
    assert "have_rents" in body, (
        "the sale-side block must guard itself, not inherit the rent guard"
    )
    js = _read(JS)
    assert "wbFloorGap" in js, "the floor gap is computed but never shown"


def test_mrt_section_ships_its_own_composition_control():
    """The transit result compares different buildings, so it must be shown
    beside a within-city panel that holds the biggest confounder constant.

    This used to name mrtTpe (臺北市) specifically. 臺北市 turned out to be the
    wrong control -- it is dense enough that only 4 of its buildings sit beyond
    2.5 km, so its "null" was an empty far group, and this page published that
    null as a retraction. The control is 新北市 now. Asserting the principle
    rather than the county, so the next correction does not fail the test.
    """
    src = _read(JS)
    assert "mrtPanel(S('mrtAll')" in src, "the full panel is gone"
    m = re.search(r"mrtPanel\(S\('(?!mrtAll')(\w+)'\)", src)
    assert m, "the MRT section no longer renders a second, within-city panel"
    # and that panel must be a single county, not a re-slice of everything
    assert re.search(r"var ctl = '\w+';", src), \
        "the control panel is not scoped to one county"

def test_related_party_sales_are_excluded_from_the_measurement():
    """親友間交易 are not market prices, and a yield is rent over PRICE.

    Measured across all 11 seasons and 22 counties: 21,028 of 226,467 clean
    residential sales carry the flag (9.29%), transacting at a median 0.757 of
    comparable arm's-length sales in the same district x type x season. A price
    24.9% low inflates that building's gross yield by 33% — always upward,
    which is the one direction this page cannot afford to be wrong in.
    """
    src = _read(os.path.join(SRC, "fetch_lvr.py"))
    assert "RELATED_PARTY" in src, "no related-party filter"
    assert "exclude_related=True" in src, "the filter must default ON"
    assert "備註" in src, "the filter must read the registry's note column"


def test_related_party_is_a_ladder_rung_and_a_waterfall_step():
    """A correction the reader cannot see is a correction they cannot check.

    The ladder measures what each cleaning decision is worth, and the coverage
    waterfall accounts for every building dropped. A ~9% filter that appeared in
    neither would be silent attrition on the one page built to refuse it.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    assert '"related"' in src, "related-party is not a ladder rung"
    assert "排除親友間交易" in src, "the rung has no Chinese label"
    assert "買賣是親友間交易，不是市場價" in src, "no waterfall step for it"
    # clean_rents has no such parameter; passing **flags straight through would
    # raise. The rent side carries the same note on 0.14% of rows anyway.
    assert 'if k not in ("exclude_related", "impute_parking")' in src, (
        "exclude_related (and impute_parking) must be stripped before **flags reaches clean_rents"
    )


def test_the_coverage_denominator_keeps_related_party_buildings():
    """The honest denominator counts buildings that EXIST, not buildings we kept.

    A flat that only ever sold to a relative is still a flat with a residential
    sale on record. Dropping it from `universe_buildings` would shrink the
    denominator and make coverage look better than it is.
    """
    src = _read(os.path.join(SRC, "underwrite.py"))
    i = src.index("def universe_buildings")
    body = src[i:i + 1400]
    assert "exclude_related=False" in body, (
        "universe_buildings must not filter related-party sales out of the denominator"
    )


def test_no_data_districts_are_bare_paper():
    """"We could not measure this" must never look like "we measured a low value".

    This is the rule the map was rebuilt for: 嘉義縣 was once painted the
    darkest county in Taiwan off 18 buildings, which is the claim the page
    spends two thousand words refuting. Below the sample floor a district now
    carries no texture at all — not the palest step, no step.
    """
    src = _read(JS)
    assert "dmed[dk] ? yieldFillAt(dmed[dk].med, 1) : 'none'" in src, (
        "below-floor districts must be bare paper, not a tone"
    )


def test_layer_controls_are_a_menu_not_five_lit_buttons():
    """Five permanently-visible toggles read as five decisions the reader must
    make before they are allowed to look at the map."""
    src = _read(JS)
    assert "hs-laymenu" in src and 'type="checkbox"' in src
    assert "layersBtn" in src


def test_legend_is_compact_with_type_collapsed():
    src = _read(JS)
    seg = src[src.index("var legend ="):src.index("var menu =")]
    assert "<details>" in seg and "<summary>" in seg, "type key should collapse"
    # The colour key now names the LEVEL it describes (county / district /
    # building medians are three different quantities), so it is one of three
    # strings rather than the old single mapColor.
    assert "rampLeg" in seg and "mapTypeLbl" in seg
    # ...and the other two channels are labelled too. A bare number on a map is
    # not a legend entry; the reader has to be told 2,685 counts buildings.
    assert "numLeg" in seg and "exclLeg" in seg


def test_clicking_a_building_opens_a_detail_panel():
    src = _read(JS)
    assert "function openPanel" in src and "function closePanel" in src
    fn = src[src.index("function openPanel"):src.index("function closePanel")]
    for k in ("pnlNet", "pnlPrice", "pnlRent", "pnlFloors", "pnlMrt", "pnlPairs"):
        assert k in fn, f"panel is missing {k}"
    assert "&middot;" not in fn, "row() escapes its value, so entities render literally"


def test_panel_shows_a_recorded_price_never_a_valuation():
    """不動產估價師法 reserves 估價 for licensed appraisers. A recorded
    transaction is a fact; an 'estimated value' for a named address is not."""
    src = _read(JS)
    assert "pnlNoVal" in src
    fn = src[src.index("pnlNoVal:"):src.index("pnlNoVal:") + 260]
    assert "not a valuation" in fn or "不是估價" in fn
    for banned in ("estimated value", "estimated_value", "valuation:"):
        assert banned not in src.lower(), f"{banned} crosses the appraisal line"


def test_percent_escaping_renders_a_single_percent():
    """%% is an escaped literal percent. Without handling it, every string that
    needed a trailing % after a substitution rendered '3.66%%'."""
    src = _read(JS)
    fn = src[src.index("function Sf(k)"):src.index("function pct(")]
    assert "%%" in fn and "'%'" in fn, "Sf does not collapse %% to %"


def test_payload_is_strict_json_with_no_nan(payload):
    """json.dump writes a bare NaN for a float NaN, which no browser will parse
    and which fails SILENTLY in fetch().json() -- a blank page with a clean
    console. allow_nan=False makes it a build error instead."""
    import underwrite as U
    src = _read(os.path.join(SRC, "underwrite.py"))
    assert "allow_nan=False" in src
    for b in payload["buildings"][:500]:
        for k in ("mrt", "fl"):
            v = b.get(k)
            assert v is None or isinstance(v, (int, float)), f"{k}={v!r}"


# ── map performance ──────────────────────────────────────────────────────

def test_no_duplicate_top_level_functions_in_housing_js():
    """A rewrite that INSERTS instead of replacing leaves two definitions of the
    same function. JS hoists both and the LAST one wins, so the file reads as if
    the new code is live while the old code is what actually runs.

    That happened here: a stale wireMap kept a `setTimeout(rerender)` on zoom,
    so every zoom step rebuilt all 14 sections -- 8.5 SECONDS per click, with
    the new implementation sitting right above it looking correct."""
    src = _read(JS)
    names = re.findall(r"^  function (\w+)", src, re.M)
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate definitions (the later one silently wins): {dupes}"


def test_zoom_redraws_only_the_marks_layer():
    """Re-clustering must not trigger a full page render. Rebuilding a 600-row
    table and a 2,541-point scatter to move ~100 circles cost 8.5s per zoom."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    assert "rerender()" not in fn.split("state.district")[0], \
        "the zoom path must not call rerender()"
    assert "marksG.innerHTML" in fn and "marksHtml(" in fn
    assert "requestAnimationFrame" in fn, "zoom work must be coalesced into one frame"


def test_strokes_are_sized_in_metres_not_non_scaling():
    """vector-effect: non-scaling-stroke makes the browser compute stroke
    geometry per segment in device space. On an 11,000-point road path, and on
    up to 1,881 marks, that hung the renderer."""
    css = _read(CSS)
    live = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert "non-scaling-stroke" not in live, "a hot path still uses non-scaling-stroke"
    src = _read(JS)
    assert "STROKES" in src, "stroke widths are not being rescaled on zoom"


def test_density_grid_is_banded_paths_not_thousands_of_rects():
    src = _read(JS)
    seg = src[src.index("var g = M.grid"):src.index("var stations =")]
    assert "bands" in seg and "<path" in seg
    assert "<rect" not in seg, "2,000 rect nodes was 2,000 things to lay out per frame"


def test_map_supports_touch():
    """The map had only mouse handlers, so on a phone it could not be panned or
    zoomed at all. Pointer events cover mouse, pen and touch in one path."""
    src = _read(JS)
    fn = src[src.index("function wireMap"):src.index("function buildingByAddr")]
    for h in ("pointerdown", "pointermove", "pointerup", "pointercancel"):
        assert h in fn, f"missing {h}"
    assert "pinchStart" in fn, "no pinch-to-zoom"
    assert "mousedown" not in fn, "stale mouse-only handlers remain"


def test_filtered_is_memoised():
    """The hover path re-filtered 2,549 records on every pointermove."""
    src = _read(JS)
    fn = src[src.index("function filtered()"):src.index("function mapFilters")]
    assert "_fKey" in fn and "_fCache" in fn


def test_buyer_filters_exist_and_feed_every_view():
    """A buyer's first two questions are what they can afford and what it
    returns. Both filters live in filtered(), so the map, table, scatter and
    waterfall all agree."""
    src = _read(JS)
    fn = src[src.index("function filtered()"):src.index("function mapFilters")]
    for k in ("maxPrice", "minYield", "maxMrt"):
        assert k in fn, f"{k} does not participate in filtering"
    assert "function mapFilters" in src and "hs-filtbtn" in src


# ── what each filter is worth, independent of the order it is applied ────

def test_filter_marginals_decompose_the_total_exactly(payload):
    """Shapley values sum to the total move. If they do not, they are three
    unrelated sensitivities being passed off as a decomposition."""
    fm = payload.get("filter_marginals")
    assert fm, "filter_marginals missing -- the ladder claim is unbacked again"
    for level in ("pair", "building"):
        got = sum(fm["shapley"][level].values())
        assert abs(got - fm["total"][level]) < 5e-4, (level, got, fm["total"][level])


def test_filter_grid_agrees_with_the_ladder(payload):
    """Four of the eight grid cells ARE ladder rungs. The ladder drifted from
    the real pipeline once; this is the check that catches it next time."""
    cells = {(g["social"], g["rooms"], g["related"]): g
             for g in payload["filter_marginals"]["grid"]}
    want = {"parking": (False, False, False), "social": (True, False, False),
            "rooms": (True, True, False), "related": (True, True, True)}
    for r in payload["ladder"]:
        key = want.get(r["key"])
        if key:
            assert abs(cells[key]["pair"] - r["yield_pair"]) < 1e-9, r["key"]
            assert cells[key]["buildings"] == r["buildings"], r["key"]


def test_removing_social_housing_raises_the_building_level_yield(payload):
    """Social leases run ~28% below market, so excluding them must push the
    yield UP. It read DOWN on the page for months because rungs 1-5 were per
    pair and 6-7 per building."""
    fm = payload["filter_marginals"]
    assert fm["shapley"]["building"]["social"] > 0, fm["shapley"]


def test_every_ladder_rung_carries_both_units_and_an_interval(payload):
    for r in payload["ladder"]:
        assert r["yield_pair"] is not None and r["yield_building"] is not None, r["key"]
        assert r["lo"] is not None and r["hi"] is not None, r["key"]
        assert r["lo"] <= r["yield_building"] <= r["hi"], r["key"]


def test_the_ladder_no_longer_claims_to_measure_each_filter():
    """The old copy said the ladder "measures one thing only: what each cleaning
    decision is worth". It cannot, and saying so is what hid the reversal.

    Scoped to the ladP string, not the whole file: the retracted sentence is
    quoted in a comment above it, on purpose, so the next reader knows what was
    withdrawn and why."""
    js = _read(os.path.join(ROOT, "housing.js"))
    m = re.search(r"^\s{4}ladP:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m, "ladP not found -- did the STR table move?"
    assert "measures one thing only" not in m.group(1)
    assert "PATH" in m.group(1) or "路徑" in m.group(1)
    assert "Order-independent (per building)" in js


def test_payload_is_stamped_for_reproduction(payload):
    pv = payload["meta"].get("provenance")
    assert pv and pv.get("version") and pv.get("built")
    src = pv["source"]
    assert len(src["sha256"]) == 64
    assert src["files"] and all(f.get("sha256") for f in src["files"]), \
        "a season is missing from the cache -- the snapshot is not pinned"


def test_payload_digest_sidecar_matches(payload):
    import hashlib
    p = os.path.join(ROOT, "housing_data.json")
    side = p + ".sha256"
    if not os.path.exists(side):
        pytest.skip("no sidecar digest (build writes one)")
    want = _read(side).split()[0]
    with open(p, "rb") as f:
        got = hashlib.sha256(f.read()).hexdigest()
    assert want == got, "housing_data.json.sha256 is stale -- rerun underwrite.py"


def _count_placeholders(s):
    """%s occurrences, treating %% as an escaped literal percent."""
    n, i = 0, 0
    while i < len(s) - 1:
        if s[i] == "%":
            if s[i + 1] == "s":
                n += 1
                i += 2
                continue
            if s[i + 1] == "%":
                i += 2
                continue
        i += 1
    return n


def test_every_string_has_the_same_placeholder_count_in_both_languages():
    """A zh/en pair with different %s counts renders "undefined" in exactly one
    language. Nothing else on the page would catch that -- the tests are in
    English and the site ships in Chinese."""
    js = _read(os.path.join(ROOT, "housing.js"))
    body = re.findall(
        r"^\s{4}([A-Za-z0-9_]+):\s*\[\s*'((?:[^'\\]|\\.)*)'\s*,\s*\n?\s*'((?:[^'\\]|\\.)*)'\s*\]",
        js, re.M)
    assert len(body) > 200, f"only parsed {len(body)} strings -- regex drifted"
    bad = [(k, _count_placeholders(zh), _count_placeholders(en))
           for k, zh, en in body
           if _count_placeholders(zh) != _count_placeholders(en)]
    assert not bad, f"zh/en placeholder mismatch: {bad}"


def _token_stream(s):
    """The %s / %% tokens in order, exactly as Sf's /%[s%]/g sees them.

    A bare % that is not followed by s or % is a literal and is skipped, which
    is why `ladNote` (which writes one) is not a mismatch.
    """
    out, i = [], 0
    while i < len(s) - 1:
        if s[i] == "%" and s[i + 1] in ("s", "%"):
            out.append(s[i:i + 2])
            i += 2
            continue
        i += 1
    return out


def test_every_string_fills_its_placeholders_in_the_same_ORDER():
    """Same count, wrong slots. Sf() substitutes POSITIONALLY, so a sentence
    whose languages interleave %s and %% differently renders one language's
    count as a percentage and its percentage as a count -- with no undefined,
    no error, and nothing in the payload out of place.

    This has now shipped four separate times (wuCov, pidMid, mgfTrend, and two
    caught pre-release in v2.3). The count test above passes on every one of
    them, because the counts are equal. Comparing the TOKEN STREAM catches the
    whole class mechanically: if zh reads count-then-percent and en reads
    percent-then-count, their streams differ.
    """
    js = _read(os.path.join(ROOT, "housing.js"))
    body = re.findall(
        r"^\s{4}([A-Za-z0-9_]+):\s*\[\s*'((?:[^'\\]|\\.)*)'\s*,\s*\n?\s*'((?:[^'\\]|\\.)*)'\s*\]",
        js, re.M)
    assert len(body) > 200, f"only parsed {len(body)} strings -- regex drifted"
    bad = [(k, "".join(_token_stream(zh)), "".join(_token_stream(en)))
           for k, zh, en in body
           if _token_stream(zh) != _token_stream(en)]
    assert not bad, (
        "zh/en fill their placeholders in a different order -- one language "
        f"will print a count as a percentage: {bad}")


# ── prose audit: claims that went stale when the scope went national ─────
#
# Every one of these was true across Taipei + New Taipei and false nationally,
# and nothing caught them because a conclusion written in prose is not asserted
# anywhere. They are asserted now. Each test names the literal that was wrong so
# a future reader can see what was retracted.

def _js():
    return _read(os.path.join(ROOT, "housing.js"))


def test_walk_up_shares_are_derived_not_typed_in():
    """covP said walk-ups are "49% of the housing that sells -- and 14% of the
    housing you can measure". Nationally that is 36.4% and 7.8%."""
    js = _js()
    m = re.search(r"^\s{4}covP:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m, "covP not found"
    assert "49%" not in m.group(1) and "14%" not in m.group(1)
    assert "將近五成" not in m.group(1) and "一成三" not in m.group(1)


def test_filter_count_in_prose_matches_the_waterfall(payload):
    """wfP said "our own four filters". There are five 'ours' steps."""
    js = _js()
    m = re.search(r"^\s{4}wfP:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m and "four filters" not in m.group(1) and "四道篩選" not in m.group(1)
    n = len([s for s in payload["coverage_waterfall"]["steps"] if s["whose"] == "ours"])
    assert n == 5, f"waterfall now has {n} 'ours' steps -- check the prose reads right"


def test_furniture_premium_is_not_hard_coded():
    """wbH said "Furniture adds 3%". It is 4.2%."""
    m = re.search(r"^\s{4}wbH:\s*\[(.*?)\],\s*$", _js(), re.M | re.S)
    assert m and "3%" not in m.group(1) and "傢俱加 3" not in m.group(1)


def test_geocoding_prose_does_not_name_hsinchu_as_covered(payload):
    """mapGeo claimed the six municipalities AND Hsinchu are above 98%.
    Hsinchu has no address-point file at all and sits at 0%."""
    m = re.search(r"^\s{4}mapGeo:\s*\[(.*?)\],\s*$", _js(), re.M | re.S)
    assert m and "Hsinchu" not in m.group(1) and "新竹" not in m.group(1)
    tot, got = {}, {}
    for b in payload["buildings"]:
        tot[b["c"]] = tot.get(b["c"], 0) + 1
        if b.get("mx") is not None:
            got[b["c"]] = got.get(b["c"], 0) + 1
    zero = [c for c in tot if not got.get(c)]
    assert len(zero) >= 10, "the all-or-nothing geocoding split has changed shape"


def test_parking_prose_describes_subtraction_not_exclusion():
    """f2 still described the treatment the pipeline abandoned: dropping every
    transaction carrying a space. Parking is subtracted now."""
    m = re.search(r"^\s{4}f2:\s*\[(.*?)\],\s*$", _js(), re.M | re.S)
    assert m, "f2 not found"
    assert "SUBTRACTED" in m.group(1) and "扣除" in m.group(1)
    assert "no assumption is needed" not in m.group(1)


def test_transit_section_can_retract_itself():
    """The section has been wrong twice and must carry its own record of that.

    v1 showed a national panel whose distances were meaningless outside the
    Taipei network. v2 (mine) retracted the finding on a 臺北市 comparison with
    4 buildings in the far bin. v3 restricts to real distances and finds the
    gradient holds, including within 新北市. What this asserts is that the
    correction text is present and derived, not which string holds it.
    """
    js = _read(JS)
    assert "MRT_MAX_M" in js, "distances are unbounded again"
    # v4 of this section: one verdict (mrtVerdict), one derived definitional
    # test (mrtDefn), one derived replication (mrtRep), one history note
    # (mrtHist, deliberately number-free so it cannot go stale). The earlier
    # mrtFix/mrtGone carried v1.2's numbers and contradicted the heading.
    for key in ("mrtVerdict", "mrtDefn", "mrtRep", "mrtHist"):
        assert re.search(r"^\s{4}" + key + r":\s*\[", js, re.M), f"{key} missing"
    assert not re.search(r"^\s{4}(mrtFix|mrtGone|mrtWhy):", js, re.M), \
        "a superseded transit paragraph is back"
    defn = re.search(r"^\s{4}mrtDefn:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert defn and defn.group(1).count("%s") >= 4, "mrtDefn hard-codes its figures"
    m = re.search(r"^\s{4}wbFloorGap:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m and "same thing the transit section finds" not in m.group(1), \
        "the within-building floor result cites the transit result as support again"

def test_district_ranking_states_its_true_strength(payload):
    """ciNote said "most of this ranking is not distinguishable". Every adjacent
    pair overlaps, so it is none of it."""
    b = payload["bootstrap"]
    assert b["adjacent_overlaps"] == b["adjacent_pairs"], (
        "not all adjacent pairs overlap any more -- ciNoteAll's wording is now "
        "too strong, check the branch in ciNoteText()")
    assert "ciNoteAll" in _js()


def test_management_fee_exposure_is_published(payload):
    """net_yield charges every county except 臺北市 the NEW TAIPEI rate, from a
    survey covering only those two cities. It cannot be corrected without a
    per-county statistic, so the exposure has to be on the page."""
    m = payload.get("mgmt_exposure")
    assert m, "mgmt_exposure missing -- a sourceless fee is being charged silently"
    assert m["counties_outside"] >= 15, m["counties_outside"]
    cases = {c["case"]: c for c in m["cases"]}
    assert set(cases) == {"default", "half", "zero"}
    # removing a cost cannot lower a net yield
    assert cases["zero"]["net"] >= cases["half"]["net"] >= cases["default"]["net"]
    assert cases["default"]["delta_pp"] == 0


def test_management_fee_label_admits_its_scope():
    """The slider was labelled "Management fee (Taipei)" while charging 22
    counties."""
    a = [x for x in json.loads(_read(os.path.join(ROOT, "housing_data.json")))
         ["assumptions"] if x["key"] == "mgmt"][0]
    assert "New Taipei's rate" in a["src_en"] or "WARNING" in a["src_en"]
    assert "其餘20縣市" in a["src_zh"] or "其餘 20 縣市" in a["src_zh"] \
        or "22縣市" in a["src_zh"]


def test_the_net_distribution_is_actually_drawn(payload):
    """`histogram_net` was computed and shipped in every payload and the page
    never drew it — a distribution withheld on a page that headlines a net
    yield. Any payload block nothing renders is either a caveat being hidden or
    bytes being wasted; this one was the second, but the check is worth keeping.
    """
    js = _read(os.path.join(ROOT, "housing.js"))
    assert "histogram_net" in js, "the net distribution is unrendered again"
    assert payload["histogram_net"], "payload lost histogram_net"
    # both series must share one axis or the comparison is meaningless
    assert "D.histogram_net" in js and "HX(" in js


def test_no_payload_block_is_computed_and_never_rendered(payload):
    """A generalisation of the above: every top-level payload key should appear
    somewhere in housing.js. Finding one that does not is how histogram_net
    surfaced."""
    js = _read(os.path.join(ROOT, "housing.js"))
    unused = [k for k in payload
              if f"D.{k}" not in js and f"'{k}'" not in js and f'"{k}"' not in js]
    assert not unused, f"payload blocks nothing renders: {unused}"


def test_the_histogram_actually_responds_to_the_sliders():
    """The caption says the cost sliders move this chart. They must.

    First version of that caption was false twice over. The chart read
    D.histogram_net / D.headline.net / the precomputed b.nt -- all frozen in the
    payload -- so every slider left it pixel-identical, while the table's net
    column right below it DID respond. Making the data live fixed half of it;
    the chart still never repainted, because the slider handler only called
    renderWaterfall() and renderTable(). Both halves are asserted here."""
    js = _js()
    # data must come from the live assumptions, not the payload's frozen fields
    assert "liveNets" in js and "netYield(b, a)" in js
    m = re.search(r"function histFigure\(\)\s*\{(.*?)\n  \}", js, re.S)
    assert m, "histFigure not found"
    body = m.group(1)
    assert "liveNets()" in body, "the figure is not reading live net yields"
    assert "D.headline.net.toFixed" not in body.split("nets.length ?")[0], \
        "the net median is taken from the payload before the live value"
    # and the sliders must repaint it -- anchor on the handler, not on the
    # `data-asmv` label in the slider markup
    h = re.search(r"e\.target\.closest\('\[data-asm\]'\)(.*?)\}\);", js, re.S)
    assert h, "the assumptions slider handler was not found"
    assert "renderHistogram()" in h.group(1), \
        "the slider handler does not redraw the histogram"


def test_the_histogram_discloses_that_it_clips():
    """underwrite.histogram() clips values into range before binning, so both
    end bars are pile-ups. The right-hand spike is real and it is an artefact,
    and the page has to say so."""
    assert "v.clip(lo, hi)" in _read(os.path.join(SRC, "underwrite.py"))
    assert "histClip" in _js()


def test_the_auction_rate_names_its_own_unit(payload):
    """in_registry_pct is a share of LOTS (hit.mean() over the row-level frame)
    and was printed against a count of BUILDINGS -- the same unit-mixing that
    made the honesty ladder read backwards."""
    a = payload["auction"]
    assert a["addr_keyed"] > a["buildings"], "lots should outnumber buildings"
    assert abs(a["in_registry"] / a["addr_keyed"] * 100 - a["in_registry_pct"]) < 0.05, \
        "in_registry_pct is no longer a per-lot rate; recheck the copy"
    m = re.search(r"^\s{4}aucReg:\s*\[(.*?)\],\s*$", _js(), re.M | re.S)
    assert m and ("auction lots" in m.group(1) or "筆拍定紀錄" in m.group(1)), \
        "the auction sentence does not name the unit its rate is computed on"


# ── second audit pass, 2026-09-11 ────────────────────────────────────────

def test_the_hero_separates_the_law_from_our_own_filters(payload):
    """The headline said "only 6.22% of buildings have both on file". Both
    records exist for 27.8%; 6.22% is what survives THIS SITE's filters. The
    page's own waterfall splits it correctly and the hero contradicted it --
    attributing to the law what is mostly us, in the flattering direction."""
    js = _js()
    # heroP is now the thesis with no numbers; heroBound carries the three
    # thresholds (both records at all / within the window / plus the quality
    # bar). Four cold readers found the funnel told twice; it is told once.
    m = re.search(r"^\s{4}heroBound:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m, "heroBound not found"
    assert m.group(1).count("%s") >= 3, "the hero no longer names all three thresholds"
    assert "bothRecordsPct" in js
    p = re.search(r"^\s{4}heroP:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert p and "%s" not in p.group(1), "heroP carries numbers again -- the funnel is told twice"
    s0 = payload["coverage_waterfall"]["steps"][0]
    both = s0["to"] / s0["from"] * 100
    assert both > payload["headline"]["coverage_pct"] * 3, (
        f"both-records {both:.1f}% vs coverage {payload['headline']['coverage_pct']}% -- "
        "if these converge the hero's two-number framing needs rechecking")


def test_transit_uses_only_real_distances(payload):
    """Every building used to get a "distance to the nearest station" even when
    the nearest station in the layer was 274,843 m away, in another city.

    This asserted `counties <= {a, f, h}` when the layer was Taipei-only. The
    layer now covers the island, so the assertion is the PRINCIPLE instead: the
    section bounds its distances, and no building is kept whose nearest station
    is implausibly far.
    """
    js = _js()
    assert "MRT_MAX_M" in js, "the MRT section no longer bounds its distances"
    m = re.search(r"var MRT_MAX_M = (\d+)", js)
    assert m, "MRT_MAX_M is not a literal any more"
    cap = int(m.group(1))
    B = [b for b in payload["buildings"] if b.get("mrt") is not None]
    kept = [b for b in B if b["mrt"] < cap]
    assert kept, "nothing survives the distance cap"
    assert max(b["mrt"] for b in kept) < cap
    # both station definitions must ship, or the page cannot show what the
    # 輕軌 judgement is worth
    assert any(b.get("mrth") is not None for b in B), "heavy-rail distance missing"
    heavy = [b["mrth"] for b in B if b.get("mrth") is not None]
    allst = [b["mrt"] for b in B if b.get("mrth") is not None]
    assert all(h >= a for h, a in zip(heavy, allst)), (
        "heavy-rail distance is never shorter than the all-stations one")

def test_the_walkup_gap_is_published_with_its_controls():
    """+0.374pp raw is not a clean estimate: it is +0.12pp within price decile
    (reversing at the dear end) and +0.64pp within district. Both cannot be the
    effect, and the page must not present the raw figure alone."""
    js = _js()
    assert "walkupControls" in js and "deadCtl" in js
    m = re.search(r"^\s{4}deadCtl:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m and "%s" in m.group(1)
    # the reversal count must be derived, not typed
    assert "two most expensive" not in m.group(1) and "最貴的兩個分位" not in m.group(1)


def test_the_ci_note_matches_the_level_being_shown(payload):
    """adjacent_overlaps/adjacent_pairs are computed over DISTRICTS, and the
    ranking opens at COUNTY level -- so '79 of 79' was printed under a 14-county
    chart that names two districts as its extremes."""
    js = _js()
    assert "ciNoteCty" in js and "ciNoteText(atCounty)" in js
    cty = payload["bootstrap"].get("county", {})
    rows = sorted([(v["lo"], v["hi"]) for v in cty.values() if v.get("lo") is not None])
    assert len(rows) >= 3
    ov = sum(1 for i in range(len(rows) - 1) if rows[i][1] >= rows[i + 1][0])
    assert ov < len(rows) - 1, "every county pair now overlaps; ciNoteCty's wording assumes some separate"


def test_the_transit_claim_is_withdrawn_and_its_sensitivity_shown(payload):
    """The gradient is not robust to a definitional choice and does not
    replicate, so the section must show both station definitions and an
    independent city rather than pick one and publish it.

    Measured: in 新北市 the nearest-vs-furthest spread is about +0.58pp with
    separated intervals on heavy rail alone, and about +0.02pp with overlapping
    intervals once 淡海輕軌 counts -- 輕軌 serves the outer 淡水 area that WAS
    the far group. 高雄, an independent metro that only entered this dataset
    after the claim was made, shows no gradient under either definition.
    """
    js = _js()
    for k in ("mrtDefn", "mrtRep", "mrtVerdict", "mrtHeavyL", "mrtRepL"):
        assert k in js, f"{k} missing -- the sensitivity is no longer shown"
    # the separate/overlap wording must be derived, not typed
    m = re.search(r"^\s{4}mrtDefn:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m and "區間分得開）變成" not in m.group(1), \
        "mrtDefn hard-codes whether the intervals separate"
    assert "mrtSep" in js and "mrtOv" in js
    # and the heading may only claim the effect holds if it survives everything
    assert "sHeavy.separate && sAll && sAll.separate" in js, \
        "the heading no longer requires the effect to survive both definitions"
    # 高雄 must actually be in the data for the replication to mean anything
    kaoh = [b for b in payload["buildings"]
            if b["c"] == "e" and b.get("mrt") is not None and b["mrt"] < 15000]
    assert len(kaoh) > 500, f"only {len(kaoh)} Kaohsiung buildings near a station"


# ── 內政部 series beside the site's own figures, 2026-09-11 ──────────────

def test_moi_loader_normalises_every_layout():
    """fetch_moi.load_series must return one shape for all four catalogue
    layouts, and must drop the 335 rows the MOI export ships with shuffled
    columns (a building type where the county should be, all value 0)."""
    import fetch_moi as M
    for key in ("court_auction_n", "building_stock", "sale_price_ping"):
        df = M.load_series(key)
        if df.empty:
            continue  # cache absent in CI; the block tolerates it
        assert list(df.columns) == ["period", "county", "district", "kind", "value"], key
        assert not df["county"].str.contains("台").any(), f"{key}: 台 not normalised to 臺"
        types = {"公寓", "別墅", "套房", "透天厝", "電梯大廈", "樓中樓"}
        assert not df["county"].isin(types).any(), f"{key}: shuffled rows survived"


def test_moi_block_keeps_channels_and_units_apart(payload):
    """金拍 and 法拍 are parallel channels, not one inside the other; 住宅拍賣
    移轉筆數 counts transfers, not lots; building stock is in 棟 and housing
    stock in 宅. The block must not present any of these as comparable."""
    m = payload.get("moi")
    if not m:
        return
    a = m.get("auction", {})
    if a:
        assert "fasc_share_pct" not in a, "金拍 presented as a SHARE of 法拍"
        assert "court_resi_lots" not in a, "transfers presented as lots"
        if a.get("fasc_vs_court_pct") is not None:
            assert a["fasc_vs_court_pct"] < 100, "the site's feed cannot exceed the court total"
    st = m.get("stock", {})
    if "building_stock" in st:
        # 建物總量 exceeds the dwelling count in every county, so it is 建號
        # (registered building units), not physical buildings. It was once
        # divided into the site's building count -- "one in 1,086" -- and that
        # division must not come back.
        assert st["building_stock"]["unit"] == "建號"
        assert "no_ratio_zh" in m.get("ours", {})
    js = _js()
    assert "moiStockP" not in js, "the buildings/建號 division is back"
    # the retraction note quotes the withdrawn figure on purpose; what must not
    # return is the DIVISION of the site's building count by 建物總量
    assert not re.search(r"m\.ours\.\w+\s*/\s*bs\.value|bs\.value\s*/\s*m\.ours", js), \
        "the buildings/建號 division is back"
    if "housing_stock" in st:
        assert st["housing_stock"]["unit"] == "宅"
    js = _js()
    assert "moiStockN" in js, "the 棟/宅 caveat is not on the page"


def test_moi_price_check_is_the_central_finding_from_outside(payload):
    """The site's matched median should sit ABOVE the official mean in the big
    cities -- the visible slice is the dearer one. If it ever sits below across
    the large samples, the coverage story on the page is wrong somewhere."""
    m = payload.get("moi")
    if not m or not m.get("price"):
        return
    big = [r for r in m["price"]["rows"] if r["n"] >= 500]
    assert len(big) >= 4
    above = sum(1 for r in big if r["gap_pct"] > 0)
    assert above >= len(big) * 0.6, (
        f"only {above}/{len(big)} large counties have ours above official -- "
        "the 'visible slice is dearer' claim needs rechecking")


def test_moi_price_index_quantifies_the_drift_the_site_leaves_in(payload):
    """USE_PRICE_INDEX is off because the site's own index made the yield-vs-gap
    slope worse. That leaves uncorrected drift in every pair. The official
    index over the window must put a number on it, at the site's median gap."""
    m = payload.get("moi", {})
    pi = m.get("price_index")
    if not pi:
        return
    assert pi["start"]["period"] < pi["end"]["period"]
    assert pi["quarters"] >= 4
    assert pi["median_pair_gap_q"] is not None and 0 <= pi["median_pair_gap_q"] <= 4
    # drift at the median gap must be consistent with the per-quarter rate
    assert abs(pi["drift_at_median_gap_pct"]
               - pi["per_quarter_pct"] * pi["median_pair_gap_q"]) < 0.02


def test_low_use_is_context_not_the_vacancy_input(payload):
    """低度使用 counts empty homes over all dwellings; rental vacancy is unlet
    rentals over rental stock. Different numerator, different denominator.
    The page may print the first beside the second but must not feed it in."""
    m = payload.get("moi", {})
    lu = m.get("low_use")
    if not lu:
        return
    assert lu["site_vacancy_pct"] == payload["assumptions"][2]["default"], \
        "the vacancy default no longer matches what the MOI section quotes"
    nat = [r for r in lu["rows"] if r["county"] == "all"]
    assert nat and 3 < nat[0]["rate_pct"] < 20, nat
    # the stock the rate is divided by must be the matching half-year
    assert lu["stock_period"].endswith("Q2" if lu["period"].endswith("H1") else "Q4")
    js = _js()
    assert "moiLuWhy" in js, "the not-an-input caveat is missing from the page"
    src = _read(os.path.join(SRC, "underwrite.py"))
    assert "DEFAULT_VACANCY_PCT = 5.0" in src, "the vacancy default was changed -- by the MOI figure?"


def test_stock_by_floor_is_compared_as_a_distribution_not_divided(payload):
    """The house-tax roll is in 宅; the site counts 棟. The two may be set side
    by side as shares and must never be divided into a 'match rate'. And the
    1-3 storey band -- mostly 透天 the site cannot see -- must be shown, not
    silently folded into 公寓."""
    m = payload.get("moi", {})
    sf = m.get("stock_by_floor")
    if not sf:
        return
    assert sf["unit"] == "宅"
    types = {r["type"] for r in sf["by_type"]}
    assert types == {"住宅大樓", "華廈", "公寓"}
    inside = sum(r["share_of_inside_pct"] for r in sf["by_type"])
    assert abs(inside - 100) < 0.5, inside
    assert sf["outside_pct"] > 30, "the 透天 share vanished"
    js = _js()
    assert "share_of_inside_pct" in js and "covStockP" in js
    assert "stock_by_floor" in js
    # no 'match_rate' computed against stock anywhere
    assert "stock_match_rate" not in js and "stock_match_rate" not in json.dumps(sf)


def test_stock_by_age_bands_match_the_site_bands(payload):
    """The site's matched buildings are binned into the MOI's own age bands so
    the two distributions are like for like. Each side must sum to ~100, and
    the site must be visibly younger than the stock -- that IS the finding."""
    m = payload.get("moi", {})
    sa = m.get("stock_by_age")
    if not sa:
        return
    assert len(sa["rows"]) == 10
    assert abs(sum(r["stock_pct"] for r in sa["rows"]) - 100) < 1.0
    assert abs(sum(r["ours_pct"] for r in sa["rows"]) - 100) < 1.0
    assert sa["ours_median_age"] < sa["stock_mean_age"] - 5, (
        "the matched set is no longer clearly younger than the stock -- "
        "the coverage narrative needs rechecking")
    old_stock = sum(r["stock_pct"] for r in sa["rows"] if r["band"].startswith(("40", "50")))
    old_ours = sum(r["ours_pct"] for r in sa["rows"] if r["band"].startswith(("40", "50")))
    assert old_stock > 2 * old_ours, (old_stock, old_ours)


def test_fasc_count_is_windowed_when_compared_to_court_lots(payload):
    """The 金拍 feed is fetched live and runs past the registry window; 法拍
    is windowed. A same-window ratio must window both sides."""
    a = payload.get("moi", {}).get("auction", {})
    if not a:
        return
    assert a.get("fasc_windowed") is True
    assert a["fasc_lots"] <= payload["auction"]["items"]
    assert "items_in_window" in payload["auction"]


def test_low_use_rate_reproduces_the_moi_published_base(payload):
    """The MOI publishes its low-use rate over 房屋稅籍住宅類數量. On that base
    114H2 全國 is 9.44%; on 住宅存量 it was 9.31% and matched nothing printed."""
    lu = payload.get("moi", {}).get("low_use")
    if not lu:
        return
    assert lu.get("base_zh") == "房屋稅籍住宅類數量"
    nat = [r for r in lu["rows"] if r["county"] == "all"][0]
    assert abs(nat["rate_pct"] - 9.44) < 0.05, nat["rate_pct"]


def test_moi_strings_with_percent_escapes_go_through_Sf():
    """S() returns the raw string; only Sf() collapses %%. A string carrying
    %% rendered via S() prints '5%%' on the page."""
    js = _js()
    for key in re.findall(r"^\s{4}(\w+):\s*\[[^\]]*%%", js, re.M):
        assert f"S('{key}')" not in js, f"{key} carries %% but is rendered with S()"


# ═══════════════════════════════════════════════════════ v1.9 additions ══
# Three blocks that ship together: transaction volume, the management-fee
# gate on the 備註 field, and the reference-rate strip. Each test reads the
# committed payload, CSVs and source only -- nothing fetches.


def _bm(payload):
    return {b["key"]: b for b in payload.get("benchmarks", [])}


def test_benchmarks_are_three_official_rates(payload):
    B = payload["benchmarks"]
    assert [b["key"] for b in B] == ["deposit_1y", "rediscount", "mortgage"]
    for b in B:
        assert 0.5 <= b["rate"] <= 6, b["key"]
        for k in ("period_zh", "period_en", "src_zh", "src_en", "note_zh", "note_en"):
            assert isinstance(b[k], str) and b[k].strip(), (b["key"], k)
        assert b["url"].startswith("https://www.cbc.gov.tw/"), b["key"]
        assert re.match(r"\d{4}-\d{2}(-\d{2})?$", b["period_iso"]), b["key"]


def test_benchmark_mortgage_is_the_existing_number_not_a_second_one(payload):
    """Corrections accrete: the old `mortgage` key stays, and the strip re-lists
    it rather than re-typing a figure."""
    m, old = _bm(payload)["mortgage"], payload["mortgage"]
    assert m["rate"] == old["rate"] and m["url"] == old["url"]
    assert m["period_zh"] == old["period_zh"] and m["period_en"] == old["period_en"]


def test_reference_files_are_pinned_and_match_disk(payload):
    """provenance.refs hashes every reference CSV the build read. A cited file
    that is not committed, or has changed since the build, fails here."""
    import hashlib
    refs = payload["meta"]["provenance"]["refs"]
    assert len(refs["sha256"]) == 64
    paths = {r["path"] for r in refs["files"]}
    for want in ("data/ref/cbc/A13Rate.csv", "data/ref/cbc/webF1.csv",
                 "data/ref/moi/sale_transfers.csv", "data/ref/dgbas_income.csv"):
        assert want in paths, f"{want} is read by the build but not pinned"
    for r in refs["files"]:
        assert re.match(r"^[0-9a-f]{64}$", r["sha256"]) and r["bytes"] > 0
        # A glob entry is a SET digest -- the 金拍 session cache is 436 files and
        # is pinned as one entry, not 436. Verify it by recomputing the same
        # way, and tolerate its absence: data/fasc/ is gitignored as a
        # rebuildable artefact, so a fresh clone has the payload but not the
        # cache. A missing directory means "cannot check here", not "wrong".
        if r["path"].endswith("/*.json"):
            import glob as _glob
            d = os.path.join(ROOT, r["path"].rsplit("/", 1)[0])
            if not os.path.isdir(d):
                continue
            got = sorted(_glob.glob(os.path.join(d, "*.json")))
            h, total = hashlib.sha256(), 0
            for q in got:
                with open(q, "rb") as fh:
                    raw = fh.read()
                total += len(raw)
                h.update(hashlib.sha256(raw).hexdigest().encode())
            assert h.hexdigest() == r["sha256"], f"{r['path']} has changed since the build"
            assert total == r["bytes"] and len(got) == r.get("files")
            continue
        full = os.path.join(ROOT, r["path"])
        assert os.path.exists(full), f"{r['path']} cited but not committed"
        with open(full, "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == r["sha256"], \
                f"{r['path']} changed since the build"
        if r["path"].startswith("data/ref/cbc/"):
            assert r["url"].startswith("https://") and re.match(r"\d{4}-\d{2}-\d{2}$", r["fetched"])
    # `source` is untouched: still only the season zips
    src = payload["meta"]["provenance"]["source"]
    assert all("season" in f for f in src["files"])
    assert len(src["files"]) == payload["meta"]["n_seasons"]


def test_benchmark_rates_come_from_the_pinned_files(payload):
    import fetch_cbc as C
    dep = C.load_deposit_1y(os.path.join(ROOT, "data/ref/cbc/A13Rate.csv"))
    red = C.load_rediscount(os.path.join(ROOT, "data/ref/cbc/webF1.csv"))
    B = _bm(payload)
    assert B["deposit_1y"]["rate"] == dep["rate"]
    assert B["rediscount"]["rate"] == red["rate"]
    assert B["rediscount"]["period_iso"] == red["effective"]
    assert B["deposit_1y"]["period_zh"] == C.roc_month(dep["period"])[0]
    # the sixth-bank trap: 彰化銀行 stopped filing in 2008 and must never enter the mean
    assert set(dep["banks"]) == set(C.FIVE) and len(dep["banks"]) == 5
    assert "彰化銀行" not in dep["banks"]
    assert all(v is not None for v in dep["banks"].values()), "the month is not common to all five"


def test_js_draws_every_benchmark_and_never_subtracts_one(payload):
    js = _js()
    hist = js[js.index("function histFigure"):js.index("function renderHistogram")]
    assert "D.benchmarks" in hist and "bmLeg" in hist and "var(--surface)" in hist
    for k in ("deposit_1y", "rediscount", "mortgage"):
        assert k in hist
    strip = js[js.index("function benchmarkStrip"):js.index("function secIncome")]
    assert "Sf('bmP'" in strip
    for k in ("bmDep", "bmRed", "bmMort", "bmLDep", "bmLRed", "bmLMort", "bmP", "bmLeg",
              "bmSame", "bmSpread"):
        assert re.search(r"^\s{4}%s:\s*\[" % k, js, re.M), f"STR lacks {k}"
    # the prose sets rates side by side: no spread vocabulary in either language
    for key in ("bmP", "bmLeg"):
        m = re.search(r"^\s{4}%s:\s*\[(.*?)\],\s*$" % key, js, re.M | re.S)
        assert m, key
        body = m.group(1)
        assert not re.search(r"個百分點|percentage point|\bpp\b|差距|spread|\bgap\b|minus|減去|高於|低於|"
                             r"higher than|lower than|beats|outyield", body), key
        assert "不相減" in body and ("does not subtract" in body or "not subtracted" in body), key
    # and no argument passed to a bm* string is a difference of a yield and a rate
    assert re.search(r"(bm\w*(\.rate)?|bmFmt\([^)]*\))\s*-\s|-\s*(h\.net|bm\w*\.rate|bmFmt)", strip) is None


# ── volume ────────────────────────────────────────────────────────────────

def test_volume_is_counted_at_a_fixed_horizon(payload):
    v = payload["volume"]
    Q = v["quarters"]
    assert len(Q) == payload["meta"]["n_seasons"]
    assert Q[0] == payload["meta"]["seasons"][0].replace("S", "Q")
    assert v["horizon_seasons"] == 1
    assert v["censored"] == [Q[-1]]
    for c in v["counties"]:
        for name, ser in v["series"][c].items():
            assert len(ser) == len(Q) and all(isinstance(x, int) and x >= 0 for x in ser), (c, name)
    cap = v["captured_pct"]
    assert cap[Q[-1]] is None and cap[Q[-2]] is None
    for q in Q[:-2]:
        assert 80 <= cap[q] <= 100, q


def test_volume_existing_excludes_presale_origin_rows(payload):
    v = payload["volume"]; k = v["kinds"]
    assert k["existing"] + k["presale_origin"] + k["no_completion"] == k["total"]
    assert v["presale_origin_pct"] == round(k["presale_origin"] / k["total"] * 100, 1)
    assert "建築完成年月" in v["basis"]["existing"]
    assert sum(v["series"]["all"]["existing"]) <= k["existing"]
    src = _read(os.path.join(SRC, "underwrite.py"))
    assert "\ndef roc_ym(" in src, "the existing-home predicate must be one module-level function"
    pb = src[src.index("def presale_block("):src.index("def load_presale_window(") if
             src.index("def load_presale_window(") > src.index("def presale_block(") else len(src)]
    assert "def _ym(" not in pb


def test_volume_county_series_never_exceed_the_national(payload):
    v = payload["volume"]
    counties = [c for c in v["counties"] if c != "all"]
    for name in v["series"]["all"]:
        for i in range(len(v["quarters"])):
            assert sum(v["series"][c][name][i] for c in counties) <= v["series"]["all"][name][i]
    o = v["official"]
    if o:
        for i in range(len(v["quarters"])):
            assert sum(o["series"][c][i] for c in counties if c in o["series"]) <= o["series"]["all"][i]


def test_volume_never_divides_registry_rows_by_official_棟(payload):
    """Rows and 棟 are different units on different clocks. Every pct key in the
    block divides like by like; the official block carries none at all."""
    v = payload["volume"]
    allowed = {"presale_origin_pct", "existing_change_pct", "presale_change_pct", "captured_pct"}
    def keys(d, pre=""):
        for k, x in d.items():
            yield pre + k
            if isinstance(x, dict) and k != "captured_pct":
                yield from keys(x, pre + k + ".")
    for k in keys({kk: vv for kk, vv in v.items() if kk != "official"}):
        leaf = k.split(".")[-1]
        if "pct" in leaf or re.search(r"ratio|share", leaf, re.I):
            assert leaf in allowed, k
    assert v["unit"] == "rows"
    if v["official"]:
        assert v["official"]["unit"] == "棟"
        for k in keys(v["official"]):
            assert not re.search(r"pct|ratio|share", k.split(".")[-1], re.I), k
    js = _js()
    sec = js[js.index("function secVolume"):js.index("function secCoverage")]
    assert "volNoRatio" in sec
    assert re.search(r"official\.series[^;]*/\s*[sv]\.|/\s*o\[", sec) is None
    assert sec.count("S('volFigA')") == 1 and sec.count("S('volFigB')") == 1


def test_volume_events_are_dated_and_not_attributed(payload):
    v = payload["volume"]
    assert [e["date"] for e in v["events"]] == ["2024-06-27", "2024-07-01", "2024-09-19"]
    for e in v["events"]:
        assert e["q"] in ("113Q2", "113Q3") and 0 <= e["frac"] <= 1
    assert v["events"][0]["q"] == "113Q2"
    assert v["attribution"] is False
    js = _js()
    ev = re.search(r"^\s{4}volEvents:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "不歸因" in ev and "does not attribute" in ev
    lim = re.search(r"^\s{4}volLim:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "不是任何政策的效果估計" in lim
    lag = re.search(r"^\s{4}volLag:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "未量測" in lag and "not measured" in lag, "volLag must label its mechanism as unmeasured"


def test_volume_official_series_is_the_moi_export(payload):
    import fetch_moi as M
    assert M.SERIES["sale_transfers"][:3] == ("4", "1", "3") and M.SERIES["sale_transfers"][5] == "棟"
    p = os.path.join(ROOT, "data/ref/moi/sale_transfers.csv")
    if not os.path.exists(p):
        pytest.skip("no MOI cache")
    d = M.load_series("sale_transfers")
    assert list(d.columns) == ["period", "county", "district", "kind", "value"]
    assert not d.county.str.contains("台").any() and (d.district == "").all()
    v = payload["volume"]; o = v["official"]
    assert o and o["sha256"]
    last = v["quarters"][-1]
    assert int(d[(d.period == last) & (d.county == "全國")].value.iloc[0]) == o["series"]["all"][-1]
    refs = {r["path"]: r["sha256"] for r in payload["meta"]["provenance"]["refs"]["files"]}
    assert refs["data/ref/moi/sale_transfers.csv"] == o["sha256"]


def test_volume_arrival_profile_justifies_the_horizon(payload):
    a = payload["volume"]["arrival"]
    assert a["existing"]["0"] + a["existing"]["1"] >= 0.85
    assert abs(a["presale"]["0"] + a["presale"]["1"] - 1.0) < 0.01
    assert abs(a["leases"]["0"] + a["leases"]["1"] - 1.0) < 0.01
    for k in a:
        assert abs(sum(a[k].values()) - 1.0) < 0.01, k


def test_volume_censored_quarter_is_greyed_and_the_section_is_simple_mode():
    js = _js(); css = _read(os.path.join(ROOT, "housing.css"))
    sec = js[js.index("function secVolume"):js.index("function secCoverage")]
    assert "hs-vol-cens" in sec and "volCensL" in sec
    assert re.search(r"\.hs-vol-cens\s*\{[^}]*stroke-dasharray", css)
    assert "var(--subtle)" in sec
    assert 'data-vol="' in sec and "closest('[data-vol]')" in js
    assert "sec('volEy', 'volH', 0," in sec
    assert "MODE === 'advanced'" in sec
    parts = js[js.index("var parts = ["):js.index("];", js.index("var parts = ["))]
    assert "secPresale(), secVolume(), secMortgage()" in parts


def test_volume_rows_are_published_in_exactly_one_season():
    """The horizon logic assumes a row is published once. 編號 overlap between
    adjacent seasons: 0 for sales, <0.1% for rents."""
    import fetch_lvr as L
    if not all(os.path.exists(os.path.join(L.CACHE, f"{s}.zip")) for s in ("114S4", "115S1")):
        pytest.skip("season zips not cached")
    a, b = L.load_season("114S4"), L.load_season("115S1")
    sa, sb = set(a["sale"]["編號"]), set(b["sale"]["編號"])
    assert not (sa & sb)
    ra, rb = set(a["rent"]["編號"]), set(b["rent"]["編號"])
    assert len(ra & rb) < 0.001 * min(len(ra), len(rb))


# ── management-fee gate ───────────────────────────────────────────────────

def test_mgmt_flag_share_is_published_and_bounded(payload):
    Lt = payload["mgmt_flag"]["lets"]
    assert 0 < Lt["incl_pct"] < 100 and 0 <= Lt["excl_pct"] < 100
    assert Lt["incl"] + Lt["excl"] + Lt["unstated"] == Lt["has_mgr"]
    assert abs(Lt["incl_pct"] - round(Lt["incl"] / Lt["has_mgr"] * 100, 1)) < 0.05
    assert Lt["has_mgr"] + Lt["no_mgr"] == payload["meta"]["clean_rents"]


def test_mgmt_flag_within_building_has_enough_buildings(payload):
    wb = payload["mgmt_flag"]["within_building"]
    assert wb["n"] >= 500
    assert wb["q1_pct"] <= wb["median_pct"] <= wb["q3_pct"]
    assert 0 <= wb["share_pos_pct"] <= 100
    assert wb["vs_excl"]["n"] >= 100
    assert "gap_ntd_ping_mo" in wb and "assumed_ntd_ping_mo" in wb


def test_mgmt_flag_bounds_bracket_and_headline_is_untouched(payload):
    mf = payload["mgmt_flag"]
    bounds = {c["case"]: c for c in mf["bounds"]}
    assert set(bounds) == {"all_charged", "flag_only"}
    assert bounds["flag_only"]["net"] >= bounds["all_charged"]["net"]
    assert bounds["all_charged"]["net"] == payload["headline"]["net"]
    assert bounds["all_charged"]["delta_pp"] == 0
    for c in bounds.values():
        assert c["lo"] <= c["net"] <= c["hi"]
    B = payload["buildings"]
    assert bounds["all_charged"]["charged"] == sum(1 for b in B if b["m"])
    assert bounds["flag_only"]["charged"] == sum(1 for b in B if b["m"] and b["mf"])
    assert all(b["mf"] in (0, 1) for b in B)
    bd = mf["buildings"]
    assert bd["flag_any"] >= bd["flag_majority"] and bd["mixed"] <= bd["flag_any"]
    assert bd["excl_any"] <= bd["has_mgr"]
    assert bd["flag_any_pct"] == round(bd["flag_any"] / bd["has_mgr"] * 100, 1)
    assert mf["predicate"]["rule"] == "any"


def test_mgmt_flag_county_rows_are_sum_consistent(payload):
    mf = payload["mgmt_flag"]
    rows, other = mf["by_county"], mf["by_county_other"]
    assert len(rows) == 6 and rows == sorted(rows, key=lambda r: -r["lets"])
    for r in rows:
        assert r["incl"] <= r["lets"] and r["excl"] <= r["lets"] and r["bldgs_flag_any"] <= r["bldgs"]
    for k, tot in (("lets", mf["lets"]["has_mgr"]), ("incl", mf["lets"]["incl"]),
                   ("bldgs", mf["buildings"]["has_mgr"]), ("bldgs_flag_any", mf["buildings"]["flag_any"])):
        assert sum(r[k] for r in rows) + other[k] == tot, k


def test_mgmt_flag_quarters_are_lease_quarters_with_the_edges_labelled(payload):
    rows = payload["mgmt_flag"]["by_quarter"]
    qs = [r["q"] for r in rows]
    assert qs == sorted(qs) and all(re.match(r"^\d{3}Q[1-4]$", q) for q in qs)
    assert all(r["lets"] >= 500 for r in rows)
    assert rows[-1]["q"] == payload["meta"]["seasons"][1].replace("S", "Q") and rows[-1]["censored"] is True
    first = payload["meta"]["seasons"][0].replace("S", "Q")
    for r in rows:
        assert (r["q"] < first) == bool(r["partial"]), r["q"]
        assert 0 < r["incl_pct"] < 100
    # a trend is a finding, not a contract -- deliberately not asserted


def test_mgmt_flag_predicate_is_published_and_matches_the_module(payload):
    import fetch_lvr as L
    p = payload["mgmt_flag"]["predicate"]
    assert p["incl"] == L.MGMT_INCL and p["not_incl"] == L.MGMT_NOT_INCL
    assert p["excl_regex"] == L.MGMT_EXCL.pattern and p["field"] == "備註"


def test_mgmt_flag_copy_says_unstated_not_tenant_pays():
    js = _js()
    rule = re.search(r"^\s{4}mgfRule:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "未註明" in rule and "unstated" in rule
    note = re.search(r"^\s{4}mgfNote:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "不是修正" in note and "not a correction" in note
    for k in ("mgfH", "mgfP", "mgfA", "mgfB", "mgfWb", "mgfQT", "wfMgmtFlag", "pnlMgf"):
        assert re.search(r"^\s{4}%s:\s*\[" % k, js, re.M), f"STR lacks {k}"
    sec = js[js.index("function mgmtFlag"):js.index("function renderWaterfall")]
    assert "hs-scroll" in sec, "the county table must scroll on a phone, not shrink"


# ═══════════════════════════════════════════════════════ v2.0 additions ══
# A parking space as its own asset, and the audit of the lease-side parking
# assumption. Both read the committed payload and source only.

PK_KEYS = ("pkEy", "pkH", "pkP", "pkRungStrict", "pkRungMarket", "pkRungWide", "pkPriceRent", "pkDwelling",
           "pkTypeT", "pkTypeS", "pkTypeNote", "pkLegMarket", "pkLegWide", "pkMech", "pkNoCiN", "pkCountyT",
           "pkThBldgs", "pkThYield", "pkThPrice", "pkThRent", "pkValidH", "pkValidP", "pkV1", "pkV2", "pkV3",
           "pkThN", "pkThin", "pkV3Thin", "pkInside", "pkOutside", "pkWideRule", "pkLicensed", "pkNotLicensed",
           "pkSocialNote", "pkBand", "pkTimeNote", "pkWfT", "pkWfSaleStand", "pkWfSaleBund", "pkWfLeaseStand",
           "pkWfLeaseBund", "pkWfSocial")


def _str_entry(js, key):
    m = re.search(r"^\s{4}%s:\s*\[(.*?)\],\s*$" % key, js, re.M | re.S)
    assert m, f"STR lacks {key}"
    return m.group(1)


def test_parking_rungs_are_ordered_and_bracketed(payload):
    pk = payload["parking"]
    keys = [r["key"] for r in pk["rungs"]]
    assert keys == ["strict", "market", "wide"]
    st, mk, wd = pk["rungs"]
    assert st["buildings"] <= mk["buildings"] <= wd["buildings"]
    assert st["pairs"] <= mk["pairs"] <= wd["pairs"]
    for r in pk["rungs"]:
        assert r["lo"] <= r["yield"] <= r["hi"] and r["q1"] <= r["yield"] <= r["q3"], r["key"]
        assert 0.3 < r["yield"] < 12
        assert sum(r["classes"]["sale"].values()) == r["pairs"] == sum(r["classes"]["lease"].values())
    assert pk["headline_rung"] == "market"
    assert st["social_pairs_pct"] == 0 and mk["social_pairs_pct"] == 0 and wd["social_pairs_pct"] > 50
    assert set(st["classes"]["sale"]) == {"standalone"} == set(st["classes"]["lease"])
    assert pk["unit"] == "space"


def test_parking_unit_is_a_space_never_per_ping(payload):
    """車位面積 is an allocated share of the basement, so a per-坪 space price
    is a category error. No key, and no parking string, may carry one."""
    def keys(d, pre=""):
        if isinstance(d, dict):
            for k, v in d.items():
                yield pre + k
                yield from keys(v, pre + k + ".")
        elif isinstance(d, list):
            for x in d:
                yield from keys(x, pre)
    for k in keys(payload["parking"]):
        leaf = k.split(".")[-1]
        assert not re.search(r"ping|area|坪|m2", leaf), k
    js = _js()
    for k in PK_KEYS:
        body = _str_entry(js, k)
        if k == "pkP":
            assert "不是坪" in body and "not 坪" in body
            continue
        assert not re.search(r"/坪|NT\$/坪|per 坪|per ping|每坪", body), k
    # rent amounts carry a per-month unit where they are stated as a rate
    for k in ("pkPriceRent", "pkThRent"):
        body = _str_entry(js, k)
        assert "/月" in body and "/mo" in body, k


def test_parking_wide_rung_is_shown_on_a_published_rule(payload):
    pk = payload["parking"]
    v = {x["key"]: x for x in pk["validations"]}["social_vs_market_rent"]
    rule = pk["predicate"]["wide_rule"]
    expect = v["n"] >= rule["min_n"] and v["median"] is not None and abs(v["median"] - 1) <= rule["max_abs_dev"]
    assert pk["wide_licensed"] is expect
    assert rule["mechanism_zh"].startswith("假說") and rule["mechanism_en"].startswith("Hypothesis")
    js = _js()
    sec = js[js.index("function secParking"):js.index("function walkupControls")]
    assert "pk.wide_licensed" in sec


def test_parking_validations_and_sensitivity(payload):
    pk = payload["parking"]
    v = {x["key"]: x for x in pk["validations"]}
    assert set(v) == {"bundled_sale_vs_standalone", "social_vs_market_rent", "bundled_lease_vs_standalone"}
    assert v["bundled_sale_vs_standalone"]["n"] >= 500 and v["social_vs_market_rent"]["n"] >= 100
    assert v["bundled_lease_vs_standalone"]["n"] >= 10
    for x in v.values():
        assert x["q1"] <= x["median"] <= x["q3"] and 0 < x["median"] < 3
        assert 0 <= x["share_within_10pct"] <= 100
        assert x["thin"] is (x["n"] < underwrite_MIN_DISTRICT_N())
    cs = v["social_vs_market_rent"]["cross_sample"]
    assert cs["social"] > 0 and cs["market"] > 0
    mk = pk["rungs"][1]
    sens = {x["key"]: x for x in pk["sensitivity"]}
    assert set(sens) == {"market_lease_standalone_only", "market_sale_standalone_only", "market_sale_bundled_only"}
    for x in sens.values():
        assert x["buildings"] < mk["buildings"] and x["lo"] <= x["yield"] <= x["hi"]


def underwrite_MIN_DISTRICT_N():
    import underwrite
    return underwrite.MIN_DISTRICT_N


def test_parking_type_cells_meet_the_floor(payload):
    import fetch_lvr as L
    pk = payload["parking"]
    floor = pk["predicate"]["min_type_buildings"]
    for rung in ("market", "wide"):
        r = {x["key"]: x for x in pk["rungs"]}[rung]
        rows = pk["by_type"][rung]
        assert rows == sorted(rows, key=lambda x: -x["buildings"])
        for row in rows:
            assert row["buildings"] >= floor and row["type"] in L.PARK_TYPES
            assert row["q1"] <= row["yield"] <= row["q3"] and row["price"] > 0 and row["rent"] > 0
            # a building can sit in two type cells (same-type pairs of two types), so per cell, not the sum
            assert row["buildings"] <= r["same_type_buildings"] <= r["buildings"]
        assert 0 < r["same_type_pairs_pct"] <= 100
    tg = pk["type_gap"]
    assert tg["hypothesis"] is True and tg["mechanism_measured"] is False
    if tg["market"]["n_b"] < underwrite_MIN_DISTRICT_N():
        assert tg["market"]["lo"] is None
    if tg["wide"]["lo"] is not None:
        assert tg["wide"]["lo"] <= tg["wide"]["gap_pp"] <= tg["wide"]["hi"]
    for rung in ("market", "wide"):
        bt = {x["type"]: x for x in pk["by_type"][rung]}
        if "坡道機械" in bt and "坡道平面" in bt:
            assert abs(tg[rung]["gap_pp"] - round(bt["坡道機械"]["yield"] - bt["坡道平面"]["yield"], 3)) < 1e-6
    # price_ratio < rent_ratio is the hypothesis: a finding, not a contract -- not asserted


def test_parking_county_rows_and_the_dwelling_headline_are_untouched(payload):
    pk = payload["parking"]
    for rung in ("market", "wide"):
        r = {x["key"]: x for x in pk["rungs"]}[rung]
        rows = pk["by_county"][rung]
        assert len(rows) <= 6 and rows == sorted(rows, key=lambda x: -x["buildings"])
        assert sum(x["buildings"] for x in rows) + pk["by_county"][rung + "_other"]["buildings"] == r["buildings"]
        for x in rows:
            if x["lo"] is not None:
                assert x["lo"] <= x["yield"] <= x["hi"]
            else:
                assert x["buildings"] < pk["predicate"]["min_county_buildings"]
    assert pk["dwelling"]["yield"] == payload["headline"]["yield"]
    assert pk["dwelling"]["buildings"] == payload["headline"]["buildings"]
    def keys(d):
        if isinstance(d, dict):
            for k, v in d.items():
                yield k; yield from keys(v)
        elif isinstance(d, list):
            for x in d: yield from keys(x)
    assert not any(re.search(r"delta|diff", k) for k in keys(pk))


def test_parking_records_waterfall_is_sum_consistent(payload):
    import fetch_lvr as L, underwrite
    pk = payload["parking"]
    s, l = pk["records"]["sale"], pk["records"]["lease"]
    assert s["rows_with_parking"] == s["standalone"] + s["bundled"]
    assert s["single_standalone"] + s["single_bundled"] + s["multi_space"] + s["no_park_row"] == s["rows_with_parking"]
    assert s["single_bundled_itemised"] <= s["single_bundled"]
    assert s["usable_market"] <= s["usable"] <= s["single_standalone"] + s["single_bundled_itemised"]
    assert l["rows_with_parking"] == l["standalone"] + l["bundled"]
    assert l["single_standalone"] + l["single_bundled"] + l["multi_space"] + l["no_park_row"] == l["rows_with_parking"]
    assert l["single_bundled_priced"] <= l["single_bundled"]
    assert l["usable_market"] <= l["usable"]
    assert l["token_rent_lt_500"] <= l["usable"]
    pr = pk["predicate"]
    assert pr["sale_targets"] == list(L.PARK_SALE_TARGETS) and pr["lease_targets"] == list(L.PARK_LEASE_TARGETS)
    assert pr["related_party"] == L.RELATED_PARTY and pr["social_housing"] == sorted(L.SOCIAL_HOUSING)
    assert pr["match_window_q"] == payload["meta"]["match_window_q"]
    assert pr["yield_band"] == list(underwrite.YIELD_BAND)
    st, mk, wd = pk["rungs"]
    assert all(r["band_dropped"] >= 0 for r in pk["rungs"]) and mk["band_dropped"] <= wd["band_dropped"]


def test_parking_copy_is_simple_mode_and_labels_the_hypothesis():
    js = _js()
    parts = js[js.index("var parts = ["):js.index("];", js.index("var parts = ["))]
    assert "secParking()" in parts
    for k in PK_KEYS:
        _str_entry(js, k)
    mech = _str_entry(js, "pkMech")
    assert "假說" in mech and "未量測" in mech and "Hypothesis" in mech and "not measured" in mech
    dw = _str_entry(js, "pkDwelling")
    assert "不相減" in dw and "never subtracted" in dw
    sec = js[js.index("function secParking"):js.index("function walkupControls")]
    # label-heavy horizontal charts keep their natural width and pan (chartW would leave a 49px plot)
    assert "hs-scroll" in sec and "data-rung" not in sec
    assert "sec('pkEy', null, 0," in sec


# ── the parking audit ────────────────────────────────────────────────────

def test_parking_audit_verdict_is_rederived_from_published_fields(payload):
    v = payload["parking_audit"]["verdict"]
    assert v["verdict"] in ("assumption_holds", "assumption_fails", "inconclusive")
    assert v["pre_registered"] is False
    m, hb = v["equal_margin"], v["hold_band"]
    assert abs(hb[0] - round(1 - v["share_s"] - m, 4)) < 1e-6 and abs(hb[1] - round(1 - v["share_s"] + m, 4)) < 1e-6
    n, lo, hi = v["n"], v["lo"], v["hi"]
    if n < v["min_n"] or lo is None:
        expect = "inconclusive"
    elif lo > hb[1]:
        expect = "assumption_fails"
    elif lo <= hb[1] and hi >= hb[0] and hi < 1 - m:
        expect = "assumption_holds"
    else:
        expect = "inconclusive"
    assert v["verdict"] == expect
    P = payload["parking_audit"]["within_building"]["total_unpriced_vs_priced"]
    assert (P["n"], P["lo"], P["hi"], P["median"]) == (n, lo, hi, v["ratio"])


def test_parking_audit_within_building_has_enough_buildings(payload):
    W = payload["parking_audit"]["within_building"]
    assert W["total_unpriced_vs_priced"]["n"] >= 100
    for k in ("total_unpriced_vs_priced", "dwell_unpriced_vs_priced", "dwell_unpriced_vs_nopark", "dwell_priced_vs_nopark",
              "total_unpriced_area_itemised_vs_priced", "total_unpriced_nothing_itemised_vs_priced"):
        r = W[k]
        if r.get("n"):
            assert r["q1"] <= r["median"] <= r["q3"] and r["lo"] <= r["median"] <= r["hi"], k
    assert W["dwell_priced_vs_nopark"]["role"] == "control"
    lets = payload["parking_audit"]["lets"]
    assert lets["priced"] + lets["unpriced"] == lets["bundled"]
    assert lets["unpriced_area_itemised"] + lets["unpriced_nothing_itemised"] == lets["unpriced"]
    assert lets["bundled"] + lets["nopark"] <= lets["clean"]
    assert sum(lets["priced_by_service"].values()) == lets["priced"]


def test_parking_audit_treatments_bracket_and_the_headline_is_the_imputed_one(payload):
    """From v2.1 the headline IS the impute treatment; the old area-only
    treatment stays a published bound (corrections accrete)."""
    pa = payload["parking_audit"]
    T = {t["case"]: t for t in pa["treatments"]}
    assert set(T) == {"area_only", "drop", "impute"}
    assert pa["headline_case"] == "impute" and pa["previous_headline_case"] == "area_only"
    H = T[pa["headline_case"]]
    assert H["gross"] == payload["headline"]["yield"] and H["net"] == payload["headline"]["net"]
    assert H["buildings"] == payload["headline"]["buildings"]
    assert H["gross_delta_pp"] == 0 and H["buildings_delta"] == 0
    assert T["drop"]["buildings"] < T["area_only"]["buildings"]
    # subtracting a rent can only lower a gross yield; a few rows under the
    # floor are dropped, so allow a tolerance rather than a strict pair check
    assert T["impute"]["gross"] <= T["area_only"]["gross"] + 1e-6
    assert T["impute"]["buildings"] <= T["area_only"]["buildings"]
    for t in T.values():
        assert t["gross_lo"] <= t["gross"] <= t["gross_hi"] and t["net_lo"] <= t["net"] <= t["net_hi"], t["case"]
    imp = T["impute"]
    assert sum(imp["source_split"].values()) == imp["imputed_rows"] == pa["lets"]["unpriced"]
    assert all(c["n"] >= imp["min_county_n"] for c in imp["county_medians"])
    cov = pa["coverage"]
    assert cov["impute"] == H["buildings"] and cov["drop"] == T["drop"]["buildings"]
    assert cov["area_only"] == T["area_only"]["buildings"]
    pd_rung = next(r for r in payload["ladder"] if r["key"] == "parking_drop")
    assert cov["parking_drop_rung"] == pd_rung["buildings"]
    # the ladder carries the same step
    lad = {r["key"]: r for r in payload["ladder"]}
    assert lad["building"]["yield_building"] == pytest.approx(T["area_only"]["gross"], abs=0.01)
    assert lad["park_impute"]["yield_building"] == pytest.approx(T["impute"]["gross"], abs=0.01)
    ex = pa["exposure"]
    assert ex["buildings_only_unpriced"] <= ex["buildings_any_unpriced"] <= ex["buildings_total"]
    assert ex["pairs_on_unpriced"] <= ex["pairs_total"]
    B = payload["buildings"]
    assert all(b.get("ro") is None or isinstance(b["ro"], int) for b in B)
    assert sum(1 for b in B if b.get("ro") is not None and b["ro"] != b["rm"]) == T["area_only"]["buildings_rent_moved"]


def test_parking_audit_is_referenced_where_the_assumption_lives():
    import inspect, fetch_lvr as L
    doc = inspect.getdoc(L._subtract_parking)
    assert "parking_audit" in doc and "FAILS" in doc
    js = _js()
    f2 = _str_entry(js, "f2")
    assert "結果不成立" in f2 and "found it false" in f2
    assert "推算" in f2 and "imputed space rent is subtracted" in f2
    for k in ("pkaH", "pkaP", "pkaVerdictFails", "pkaVerdictHolds", "pkaVerdictInc", "pkaRule", "pkaA", "pkaB", "pkaC",
              "pkaTrade", "pkaNote", "wfParkOld", "pnlRentOld", "lim5", "pkaCorr", "pkaMore", "pkaLess"):
        _str_entry(js, k)
    # the copy says which treatment is the headline, and that the old one stays
    assert "v2.1" in _str_entry(js, "pkaC") and "v1.0" in _str_entry(js, "pkaA")
    note = _str_entry(js, "pkaNote")
    assert "不刪" in note and "not deleted" in note
    for k in ("pkaVerdictFails", "pkaVerdictHolds", "pkaVerdictInc", "pkaRule"):
        body = _str_entry(js, k)
        assert "pre-registered" not in body.replace("not call it pre-registered", "") and "預先登錄" not in body.replace("不稱它「預先登錄」", ""), k
    sec = js[js.index("function parkingAudit"):js.index("function secNet")]
    assert "hs-scroll" in sec
    lad = js[js.index("function secLadder"):js.index("function ladMarginals")]
    assert "parkingAudit()" in lad
    wf = js[js.index("function renderWaterfall"):js.index("function secPostStrat")]
    assert "Object.assign({}, b, { rm: b.ro })" in wf
    lim = js[js.index("function secLimits"):]
    assert "lim5" in lim


def test_theme_series_bands_sum_to_their_total():
    """Every banded MOI series ships a TOTAL column and most ship a MEAN one.
    Both must be recognised, or a naive melt returns them as bands and anyone
    summing a series gets roughly double. Measured once: xfer_by_age 115Q2 全國
    summed to 43,056 against a true 21,512. The by-size series also carries a
    typo in the government's own header (住宅平圴面積, 圴 for 均)."""
    import fetch_moi as M
    checked = 0
    for key in ("stock_by_age", "stock_by_floor", "stock_by_size",
                "xfer_by_age", "xfer_by_size", "xfer_by_floor"):
        path = os.path.join(ROOT, "data/ref/moi", key + ".csv")
        if not os.path.exists(path):
            continue
        d = M.load_theme_series(key)
        nat = d[(d.county == "全國") & (d.district == "") & (d.period == "115Q2")]
        total = nat[nat.kind == ""].value
        bands = nat[~nat.kind.isin(["", "mean"])]
        assert len(total) == 1, f"{key}: the total column was not recognised"
        assert len(bands) >= 5, f"{key}: only {len(bands)} bands"
        assert abs(bands.value.sum() - total.iloc[0]) < 1, (
            f"{key}: bands sum to {bands.value.sum():,.0f} against a total of "
            f"{total.iloc[0]:,.0f} -- a total or mean column is leaking in as a band")
        checked += 1
    if not checked:
        pytest.skip("no theme-series cache")


# ═══════════════════════════════════════════════════════ v2.2 additions ══
# The founding hypothesis, closed. Two questions, two verdicts, each by a rule
# re-derivable from what the block prints.


def test_walkup_verdict_is_rederived_from_published_fields(payload):
    w = payload["walkup_resolution"]
    C, pr = w["constants"], w["precision"]
    rep = w["representativeness"]
    assert len(rep) == 2, "both types' representativeness must be published, not just the walk-ups'"
    assert w["pre_registered"] is False
    n_w = w["coverage"]["matched_bldg"]
    gap = pr["gross_gap"]
    binding = [c for c in w["controls"] if c["binding"]]
    sel_bad = any(abs(r["max_abs_diff_pct"]) > C["sel_tol_pct"] for r in rep)
    rwg = w["reweighted"]["gap"]
    flipped = rwg is not None and gap != 0 and rwg * gap < 0
    if n_w < C["min_n"]:
        expect = "inconclusive"
    elif pr["mdd_95"] is not None and abs(gap) < pr["mdd_95"]:
        expect = "unanswerable_precision"
    elif sel_bad or flipped:
        expect = "unanswerable_selection"
    elif any((c["same_sign_pct"] or 0) < C["sign_share"] * 100 for c in binding):
        expect = "inconclusive"
    else:
        expect = "resolved_walkups_higher" if gap > 0 else "resolved_towers_higher"
    assert w["verdict"] == expect, (w["verdict"], expect)
    joint = next(c for c in w["controls"] if c["family"] == "district_x_age_band")
    assert w["mechanism_verdict"] == ("attributable" if joint["cells"] >= C["joint_min_cells"]
                                      else "unanswerable_selection")


def test_walkup_mechanism_is_falsified_on_a_stated_rule(payload):
    """The fee was the hypothesis's own explanation. If the gap survives in
    buildings where the modelled fee is zero, the explanation is wrong."""
    me = payload["walkup_resolution"]["mechanism"]
    cells = {c["has_mgr"]: c for c in me["cells"]}
    assert set(cells) == {0, 1}
    ok = (all(min(c["n_walkup"], c["n_tower"]) >= me["min_cell"] for c in me["cells"])
          and cells[0]["lo"] is not None and cells[0]["lo"] * cells[0]["hi"] > 0)
    assert me["fee_verdict"] == ("falsified" if ok else "not_falsified")
    # the fee variable is nearly the type indicator, which is the point
    assert me["p_mgr_tower_pct"] > 90 > me["p_mgr_walkup_pct"]


def test_walkup_units_are_never_divided(payload):
    """棟 vs 筆 vs 宅. The guard that would have caught 'one building in 1,086'."""
    cov = payload["walkup_resolution"]["coverage"]
    assert payload["walkup_resolution"]["unit_note"]
    # the only ratio involving the stock is dwellings over dwellings
    if cov["stock_4_5f_dwellings"] and cov["stock_total_dwellings"]:
        assert abs(cov["stock_4_5f_share_pct"]
                   - cov["stock_4_5f_dwellings"] / cov["stock_total_dwellings"] * 100) < 0.05
    # the match rate is 棟 over 棟
    assert abs(cov["match_rate_pct"] - cov["matched_bldg"] / cov["universe_bldg"] * 100) < 0.01
    assert cov["matched_bldg"] <= cov["universe_bldg"] <= payload["headline"]["universe_buildings"]
    assert cov["pairs"] <= cov["pairs_all_types"] == payload["headline"]["pairs"]
    js = _js()
    sec = js[js.index("function secWalkup"):js.index("function secAuction")]
    assert "chartW(" in sec, "the controls chart is labelled at one end and should use chartW"
    assert "hs-scroll" in sec


def test_walkup_dead_hypothesis_keys_are_intact(payload):
    """A sibling block may not break the rung it builds on."""
    dh = payload["dead_hypothesis"]
    for k in ("by_type", "by_manager", "gross_gap", "net_gap", "gross_ci", "net_ci",
              "cost_share_pct", "verdict"):
        assert k in dh, k
    assert dh["verdict"] in ("untested", "alive", "reversed", "dead")
    js = _js()
    for k in ("wuEy", "wuH", "wuP1", "wuCov", "wuRep", "wuPrec", "wuCtl", "wuSupp",
              "wuMech", "wuUnans", "wuNeed", "wuRule", "wuAccrete", "lim6"):
        assert re.search(r"^\s{4}%s:\s*\[" % k, js, re.M), f"STR lacks {k}"
    rule = re.search(r"^\s{4}wuRule:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "不是預先註冊" in rule and "not pre-registered" in rule
    parts = js[js.index("if (adv) parts.push(secPostStrat"):js.index("parts.push(secMoi")]
    assert "secDead(), secWalkup()" in parts


def test_the_building_type_map_is_single_sourced(payload):
    """coverage_block read its denominator from the universe frame and its
    numerator from the matched frame, so six buildings were counted under one
    type in one and another in the other. The superseded rate stays visible."""
    src = _read(os.path.join(SRC, "underwrite.py"))
    assert "_ubtype = dict(zip(zip(ub.county, ub.k), ub.bldg_type))" in src
    cov = {c["type"]: c for c in payload["coverage"]}
    for t, c in cov.items():
        assert abs(c["match_rate"] - c["matched"] / c["all_buildings"] * 100) < 0.01, t
        assert c["match_rate_pre_v22"] is not None, t
    # the walk-up count agrees everywhere it appears
    w = payload["walkup_resolution"]["coverage"]
    assert w["matched_bldg"] == cov["公寓"]["matched"]
    assert w["universe_bldg"] == cov["公寓"]["all_buildings"]
    assert w["match_rate_pct"] == cov["公寓"]["match_rate"]


def test_universe_buildings_with_rows_returns_the_same_frame():
    """The row frame is a bonus return, never a different denominator."""
    import underwrite as U, fetch_lvr as L
    season = "115S2"
    if not os.path.exists(os.path.join(L.CACHE, f"{season}.zip")):
        pytest.skip("no season cache")
    raw = L.load_season(season)["sale"]
    a = U.universe_buildings(raw)
    b, rows = U.universe_buildings(raw, with_rows=True)
    assert a.equals(b)
    assert len(rows) >= len(b)


# ═══════════════════════════════════════════════════════ v2.3 additions ══
# Partial identification: what seeing 6% permits anyone to claim.


def test_partial_id_ladder_narrows_and_names_its_assumptions(payload):
    p = payload["partial_id"]
    R = {r["key"]: r for r in p["rungs"]}
    assert R["band"]["gross"]["lo"] == 0.3 and R["band"]["gross"]["hi"] == 12.0, \
        "rung 1 must return the site's own cleaning band exactly"
    order = ["band", "type_support", "type_trim", "type_price"]
    for a, b in zip(order, order[1:]):
        assert R[b]["gross"]["width"] <= R[a]["gross"]["width"] + 1e-9, (a, b)
    for r in p["rungs"]:
        g = r["gross"]
        assert g["lo"] < g["hi"] and abs(g["width"] - (g["hi"] - g["lo"])) < 1e-6, r["key"]
        assert 0.3 <= g["lo"] and g["hi"] <= 12.0, r["key"]
        assert p["assumptions"][r["key"]]["zh"] and p["assumptions"][r["key"]]["en"], r["key"]
    # the matched point sits inside the headline interval and is never the answer
    head = R[p["headline_rung"]]
    mp = p["matched_point"]
    assert head["gross"]["lo"] <= mp["gross"] <= head["gross"]["hi"]
    assert mp["gross"] == payload["headline"]["yield"]
    assert head["net"]["lo"] <= mp["net"] <= head["net"]["hi"]


def test_partial_id_rung_one_is_not_called_assumption_free():
    """It rests on YIELD_BAND, which this site chose. The copy must say so."""
    js = _js()
    band = re.search(r"^\s{4}pidR_band:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "本站自己" in band and "own cleaning band" in band
    assert "無假設" not in band and "assumption-free" not in band and "no assumptions" not in band
    why = re.search(r"^\s{4}pidWhy:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "一半" in why and "half" in why


def test_partial_id_trim_is_named_a_resemblance_assumption(payload):
    """The trim does most of the narrowing and is stronger than 'they resemble
    the matched ones'. Both the copy and the untrimmed rung must say so."""
    p = payload["partial_id"]
    R = {r["key"]: r for r in p["rungs"]}
    assert "type_support" in R, "the untrimmed rung must ship beside the trimmed one"
    assert R["type_support"]["trim"] == 0.0 and R["type_trim"]["trim"] == p["trim"]
    assert R["type_trim"]["buys_pp"] > 1.0, "if the trim stopped mattering, recheck the copy"
    a = p["assumptions"]["type_trim"]
    assert "前 5%" in a["zh"] and "top 5%" in a["en"]
    js = _js()
    warn = re.search(r"^\s{4}pidTrimWarn:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "近似假設" in warn and "resemblance assumption" in warn


def test_partial_id_publishes_the_rung_that_fails(payload):
    """Conditioning on one more variable thins the cells and widens the bound.
    A ladder that only showed its wins would be advertising."""
    R = {r["key"]: r for r in payload["partial_id"]["rungs"]}
    age = R["type_price_age"]
    assert age["cells"] > R["type_price"]["cells"]
    assert age["cells_below_min"] > 0 and age["fellback_universe_n"] > 0
    if age["buys_pp"] is not None and age["buys_pp"] < 0:
        js = _js()
        w = re.search(r"^\s{4}pidAgeWarn:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
        assert "反而" in w and "LONGER" in w


def test_every_partial_id_row_has_a_label_in_both_languages(payload):
    """The chart falls back to the payload key when a label is missing, so a
    forgotten STR entry ships as '↑ mts_up' to readers rather than failing."""
    js = _js()
    p = payload["partial_id"]
    for k in [r["key"] for r in p["rungs"]] + [m["key"] for m in p.get("mts", [])]:
        m = re.search(r"^\s{4}pidR_%s:\s*\[(.*?)\],\s*$" % re.escape(k),
                      js, re.M | re.S)
        assert m, "no pidR_%s label; the chart would print the raw key" % k
        zh, en = [x.strip() for x in re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))][:2]
        assert zh and en and zh != en and k not in (zh, en)


def test_partial_id_never_converts_dwellings_into_buildings(payload):
    """宅 shares as 棟 weights is 'one building in 1,086' in a new hat."""
    p = payload["partial_id"]
    assert p["scope"]["unit"] == "棟"
    def keys(d, pre=""):
        if isinstance(d, dict):
            for k, v in d.items():
                yield pre + k; yield from keys(v, pre + k + ".")
        elif isinstance(d, list):
            for x in d: yield from keys(x, pre)
    assert not any("stock" in k for k in keys(p)), "no rung may weight on the dwelling stock"
    for c in p["composition"]:
        assert c["unit"] == "棟"
        assert abs(c["match_rate_pct"] - c["matched_n"] / c["universe_n"] * 100) < 0.01
    assert "42.7" in p["scope"]["not_taiwan_zh"] and "Taiwan" in p["scope"]["not_taiwan_en"]


def test_partial_id_mts_is_published_both_ways_and_unsigned(payload):
    p = payload["partial_id"]
    assert p["mts_signed"] is False
    m = {x["key"]: x for x in p["mts"]}
    assert set(m) == {"mts_up", "mts_down"}
    head = {r["key"]: r for r in p["rungs"]}[p["headline_rung"]]
    mp = p["matched_point"]["gross"]
    # the one-sided ladders hinge on the matched median and the headline rung's
    # far end; both are published rounded to 3dp
    assert abs(m["mts_up"]["gross"]["lo"] - mp) < 5e-4
    assert abs(m["mts_down"]["gross"]["hi"] - mp) < 5e-4
    assert m["mts_up"]["gross"]["hi"] == head["gross"]["hi"]
    assert m["mts_down"]["gross"]["lo"] == head["gross"]["lo"]
    js = _js()
    t = re.search(r"^\s{4}pidMts:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "不選邊" in t and "does not pick one" in t


def test_partial_id_suppresses_the_midpoint(payload):
    """An interval's middle is no likelier than its ends. The page must not
    draw it, and must say so."""
    js = _js()
    sec = js[js.index("function secPartialId"):js.index("function secMap")]
    assert "pidMid" in sec
    assert "midpoint" not in sec.lower().replace("midpoint of an interval", "")
    # the matched point is drawn as a tick inside the bar, never as its own bar
    assert "never a bar of its own" in sec
    mid = re.search(r"^\s{4}pidMid:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "中點" in mid and "midpoint" in mid
    figs = re.search(r"^\s{4}pidFigS:\s*\[(.*?)\],\s*$", js, re.M | re.S).group(1)
    assert "不畫" in figs and "not drawn" in figs
    # the ladder labels both ends, so it keeps natural width and pans
    assert "chartW(" not in sec
    assert re.search(r"var W = \d{3}, padL", sec), "the ladder keeps a natural width"
    parts = js[js.index("var parts = ["):js.index("];", js.index("var parts = ["))]
    assert "secCoverage(), secPartialId()" in parts
    assert "lim7" in js[js.index("function secLimits"):]


# ── the vacancy prior (v2.4) ─────────────────────────────────────────────
# The level stays an assumption and the shape is measured. These tests exist to
# stop the next session from "improving" the block by adopting the low-use rate
# as the vacancy rate, which would answer one population's question with another
# population's number.

def test_vacancy_prior_never_becomes_the_headline(payload):
    """低度使用 is an empty-HOME rate over all dwellings; rental vacancy asks
    how many LET homes sit unlet. Different numerator, different denominator."""
    v = payload.get("vacancy_prior")
    assert v, "vacancy_prior missing"
    assert v["headline_case"] == "flat"
    C = {c["key"]: c for c in v["cases"]}
    assert C["flat"]["vacancy_mean_pct"] == v["site_default_pct"]
    assert abs(C["flat"]["net"] - payload["headline"]["net"]) < 5e-4, \
        "the flat case IS the headline's code path and must reproduce it"
    for k in ("construct_zh", "construct_en"):
        assert v[k] and len(v[k]) > 40


def test_vacancy_shape_holds_the_level_and_moves_only_who_pays(payload):
    """Normalised on the matched set, so the headline is nearly untouched by
    construction. If this ever moves the headline, the normalisation broke."""
    v = payload["vacancy_prior"]
    C = {c["key"]: c for c in v["cases"]}
    assert abs(C["shape"]["vacancy_mean_pct"] - v["site_default_pct"]) < 1e-6
    assert C["shape"]["vacancy_min_pct"] < v["site_default_pct"] < C["shape"]["vacancy_max_pct"]
    assert abs(C["shape"]["delta_pp"]) < 0.02, C["shape"]["delta_pp"]
    assert C["level"]["vacancy_mean_pct"] > v["site_default_pct"]
    assert C["level"]["net"] < C["flat"]["net"]


def test_every_building_carries_its_shape_and_the_mean_is_one(payload):
    vs = [b.get("vs") for b in payload["buildings"]]
    assert all(x is not None for x in vs), "a building with no shape breaks the twin"
    assert abs(sum(vs) / len(vs) - 1.0) < 2e-3, sum(vs) / len(vs)
    # the joint leg is county x age, so the shape must vary WITHIN a county
    by = {}
    for b in payload["buildings"]:
        by.setdefault(b["c"], set()).add(b["vs"])
    assert max(len(x) for x in by.values()) > 1, \
        "shape is constant within every county — the age leg is not being applied"


def test_the_matched_set_is_emptier_than_the_stock_and_says_why(payload):
    """The finding: the visible slice is NEW, and new dwellings are the emptiest
    band in the country. The copy must state the direction it measured."""
    v = payload["vacancy_prior"]
    assert v["gap_pp"] is not None and v["gap_pp"] > 0, v["gap_pp"]
    assert v["prior_pct"] > v["national_pct"]
    lo, hi = v["prior_ci"]
    assert lo <= v["prior_pct"] <= hi
    prof = {r["band"]: r for r in v["profile"]}
    new, mid = prof["<=5"], prof["10-20"]
    assert new["rate_pct"] > mid["rate_pct"], "the U-shape is the mechanism"
    assert new["matched_share_pct"] > new["stock_share_pct"], \
        "the matched set must be over-weighted in the emptiest band for the finding to hold"


def test_the_county_leg_points_the_other_way_and_is_published(payload):
    """County alone says the matched set is FULLER; age says emptier. Publishing
    only the leg that agrees with the conclusion would be advertising."""
    v = payload["vacancy_prior"]
    cl = v["county_leg"]
    assert cl and cl["gap_pp"] is not None
    assert cl["gap_pp"] < 0 < v["gap_pp"], (cl["gap_pp"], v["gap_pp"])
    assert cl["counties"] >= 20, "the county leg must cover more than the six municipalities"
    assert cl["covered_pct"] > 99.0
    js = _js()
    m = re.search(r"^\s{4}vacCounty:\s*\[(.*?)\],\s*$", js, re.M | re.S)
    assert m and "相反" in m.group(1) and "other way" in m.group(1)


def test_the_age_profile_is_checked_against_the_other_archived_edition(payload):
    """Only two editions are archived. Publishing one without the other would
    hide whether the profile is a fact or that half-year's weather."""
    v = payload["vacancy_prior"]
    st = v["stability"]
    assert st and st["period"] != v["period"]
    assert st["gap_pp"] is not None and st["gap_pp"] > 0, st
    assert abs(st["gap_pp"] - v["gap_pp"]) < 1.0, (st["gap_pp"], v["gap_pp"])


def test_the_two_legs_are_never_multiplied_together(payload):
    """They are different periods. Combining them would invent a number neither
    source publishes."""
    v = payload["vacancy_prior"]
    assert v["period"] != v["county_leg"]["period"]
    for k in ("period_zh", "period_en"):
        assert v[k] and ("不相乘" in v[k] or "never multiplied" in v[k])


def test_the_vacancy_assumption_reaches_simple_mode(payload):
    """The softest number on the page cannot live only behind the advanced
    toggle — lim8 is how a simple-mode reader meets it."""
    js = _js()
    assert re.search(r"^\s{4}lim8:\s*\[", js, re.M)
    assert "Sf('lim8'" in js
    assert "vacancyPrior()" in js


def test_the_shape_is_opt_in_so_the_twins_stay_in_lockstep(payload):
    """netYield() in housing.js is a twin of net_yield() in underwrite.py. The
    Python side charges the flat level on the headline path, so the JS side must
    only apply b.vs when the reader asks for it."""
    js = _js()
    assert "state.vshape && b.vs" in js
    assert "var vac = a.vacancy * (state.vshape && b.vs ? b.vs : 1);" in js
    assert js.count("state.vshape && b.vs ? b.vs : 1") >= 2


def test_the_archived_source_is_pinned_not_just_linked(payload):
    """pip.moi.gov.tw is not reachable from every network and no later edition
    is archived, so the Wayback snapshot IS the source and must be hashed."""
    refs = payload["meta"]["provenance"]["refs"]["files"]
    row = [f for f in refs if f["path"].endswith("low_use_by_age.csv")]
    assert row, "the age cross-table is not in the reference manifest"
    assert row[0]["sha256"] and row[0]["bytes"] > 200
    assert "web.archive.org" in (row[0].get("url") or "")


def test_every_published_net_case_recomputes_from_the_published_payload(payload):
    """The site's contract is "check my numbers", so every published net case
    must be reachable from the payload's own fields with the payload's own
    assumptions — the arithmetic the page's JS twin runs.

    It cannot be reachable EXACTLY. underwrite.py takes its medians over
    full-precision frame values, while `buildings[]` ships rent and price
    rounded to the NT$ and area to 0.1坪. That floor is ~6e-5pp on the flat
    case and ~1.7e-4pp on the shaped one — larger there because charging a
    different vacancy per building changes which buildings sit at the median,
    so the rounding noise lands differently. Neither is a defect; both are
    below the precision anything is published at.

    So this asserts the property that actually matters to a reader: the
    recomputation agrees at the 2dp the page displays, and stays well inside a
    bound that would still catch a real divergence.
    """
    A = {a["key"]: a["default"] for a in payload["assumptions"]}
    B = payload["buildings"]

    def net(b, vac):
        annual = b["rm"] * 12
        eff = annual * (1 - vac / 100.0)
        rate = A["mgmt"] if b["c"] == "a" else A["mgmt"] * (105 / 140.0)
        mgmt = (rate * b["ar"] * 12) if b["m"] else 0.0
        tax = b["pa"] * A["tax"] / 100.0
        age = 0 if b["b"] is None else max(0, 115 - b["b"])
        rep = annual * (A["repairs"] / 100.0) * (1 + age / 50.0)
        return (eff - mgmt - tax - rep) / b["pa"] * 100.0

    def med(v):
        v = sorted(x for x in v if x is not None)
        m = len(v) // 2
        return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2

    # The bound is NOT a constant: the floor is set by how far apart the two
    # values straddling the median are, which is a property of the data. One
    # rank swap from rounding moves the median by about half that spacing. A
    # hard-coded 5e-4 held at 9,805 buildings and failed at 9,843 when the
    # corrected join key changed which buildings sit in the middle -- the gap
    # was 6.8e-4 against a median spacing of 5.3e-4, i.e. exactly one swap.
    _flat = sorted(net(b, A["vacancy"]) for b in B)
    _m = len(_flat) // 2
    _spacing = abs(_flat[_m] - _flat[_m - 1])
    BOUND = max(1e-3, 2 * _spacing)
    C = {c["key"]: c for c in payload["vacancy_prior"]["cases"]}
    # The level case charges each building its own cell's low-use rate. The
    # payload does not ship that rate per building -- but it ships `vs`, which
    # IS that rate over the matched-set mean, so rate = vs * prior_pct. Skipping
    # it left a published figure (the page's higher-vacancy bound) checked by
    # nothing, while the test's name claimed otherwise.
    _prior = payload["vacancy_prior"]["prior_pct"]
    for key, vec in (("flat", [A["vacancy"]] * len(B)),
                     ("shape", [A["vacancy"] * b["vs"] for b in B]),
                     ("level", [b["vs"] * _prior for b in B])):
        got, pub = med([net(b, v) for b, v in zip(B, vec)]), C[key]["net"]
        assert abs(got - pub) < BOUND, (key, got, pub, "median spacing", _spacing)
        assert round(got, 2) == round(pub, 2), (key, got, pub)

    flat = med([net(b, A["vacancy"]) for b in B])
    assert round(flat, 2) == round(payload["headline"]["net"], 2)


def test_the_age_comparison_counts_the_same_unmatched_buildings_as_the_rest_of_the_page(payload):
    """`age` compares matched against unmatched. "Unmatched" has exactly one
    meaning on this page — every building with a sale that the site cannot
    price — and coverage, the waterfall and partial_id all count 147,789 of
    them.

    `age` counted 100,800 for two versions, because coverage_block moved to the
    universe frame in v2.2 and this did not. The cleaned frame drops the
    buildings whose only sales carried un-itemised parking or were related
    party, and those are cheaper, so the page published its own central
    selection effect at 2.7% when the measured figure is 8.5%. Nothing failed.
    """
    age = payload["age"]
    h = payload["headline"]
    assert age["matched_n"] == h["buildings"]
    assert age["unmatched_n"] == h["universe_buildings"] - h["buildings"], (
        "age is comparing against a different population than the rest of the page")
    assert age["matched_n"] + age["unmatched_n"] == h["universe_buildings"]
    # and the one other place that quotes this gap must quote the same number
    pid = payload.get("partial_id") or {}
    if pid.get("ppp_gap_pct") is not None:
        assert pid["ppp_gap_pct"] == age["ppp_diff_pct"]
    for lang in ("zh", "en"):
        txt = pid["assumptions"]["mts"][lang]
        assert f"{age['ppp_diff_pct']:g}%" in txt, (lang, txt[:120])


def test_the_typed_mortgage_rate_cannot_go_quietly_stale(payload):
    """The mortgage rate is compared against the headline net yield on the page
    and printed in the PDF's reference table, so a figure that silently ages is
    a published number that silently becomes wrong.

    Since payload 2.13 it is read from a pinned CBC file rather than typed
    (tests/test_sources.py), but that file has no stable URL -- each month is a
    new release page -- so it cannot refresh itself and can still fall behind.
    This is the guard for that: the pinned month must not trail the data window
    by more than a year. When it does, pin a newer release with
    fetch_cbc.pin_new_loans(). (The name still says "typed"; the hazard it
    guards outlived the constant.)
    """
    m = payload["mortgage"]
    assert m["rate"] and 0 < m["rate"] < 10
    mo = re.match(r"^(\d{3})年(\d{1,2})月$", m["period_zh"])
    assert mo, f"unparseable period {m['period_zh']!r}"
    yr, month = int(mo.group(1)), int(mo.group(2))
    rate_q = yr * 4 + (month - 1) // 3          # ROC year-quarter ordinal

    last = payload["meta"]["seasons"][1]        # e.g. "115S2"
    wy, wq = int(last[:3]), int(last[-1])
    win_q = wy * 4 + (wq - 1)

    # Four quarters of slack: the CBC publishes monthly, so a rate more than a
    # year behind the last season this site reports is not a current comparison.
    assert rate_q >= win_q - 4, (
        f"the pinned mortgage file ends at {m['period_zh']} while the window ends "
        f"at {last} — download the newest release from "
        "https://www.cbc.gov.tw/tw/lp-528-1.html and pin it with fetch_cbc.pin_new_loans()")
    # and it must not claim to be from the future
    assert rate_q <= win_q + 4, f"{m['period_zh']} is ahead of the window {last}"


def _pdf_text():
    """The rendered report as text, or None when it cannot be read here."""
    path = os.path.join(ROOT, "housing_report.pdf")
    if not os.path.exists(path):
        return None
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)


def test_the_pdf_states_the_same_figures_as_the_payload(payload):
    """The PDF is the citable artefact and was, until v2.6, the least tested
    surface on the site: the only assertion on it was that it returns 200 and
    starts with %PDF-. Five prose figures in a 786-line generator were wrong —
    MRT spreads typed at v1.3, a pre-sale residual the site had withdrawn, a
    rent-per-floor slope of 0.12% against the payload's 0.11%, a presale figure
    attributed to the wrong quarter, and the walk-up hypothesis rendered as
    live after v2.2 closed it.

    Extracting the text and checking the headline figures against the payload is
    what would have caught four of the five on the day they were written.
    """
    t = _pdf_text()
    if not t:
        pytest.skip("housing_report.pdf not built, or pypdf unavailable")
    flat = t.replace("\n", "").replace(" ", "")

    h, w = payload["headline"], payload["within_building"]
    must = [
        f"{h['coverage_pct']}%",                       # the denominator, the whole point
        f"{h['yield']:.2f}%",                          # gross
        f"{h['net']:.2f}%",                            # net
        f"{h['buildings']:,}".replace(",", ","),       # matched buildings
        f"+{w['floor_sale']['pct_per_floor']:.2f}%",   # sale slope
        f"+{w['floor']['pct_per_floor']:.2f}%",        # rent slope -- the one that drifted
    ]
    for frag in must:
        assert frag.replace(" ", "") in flat, f"the PDF does not state {frag!r}"

    # the presale figure must be attributed to the quarter the payload gives it
    sm = (payload.get("volume") or {}).get("summary") or {}
    if sm.get("presale_to_q") and sm.get("presale_to"):
        assert (sm["presale_to_q"] + "的" + f"{sm['presale_to']:,}").replace(" ", "") in flat, (
            "the presale trough is printed without, or with the wrong, quarter")

    # v2.2 closed the walk-up hypothesis; the PDF rendered only the older rung
    wr = payload.get("walkup_resolution") or {}
    if wr.get("verdict") == "unanswerable_selection":
        assert "回答不了" in flat or "unanswerable" in flat.lower(), (
            "the PDF asserts the walk-up finding without v2.2's closing")

    # and it must not reassert a withdrawn one as a result
    pre = payload.get("presale") or {}
    if pre.get("separable") is False:
        assert "已更正" in flat or "撤回" in flat


def test_the_pdf_carries_its_own_generator_digest(payload):
    """Every other stamp on the report identifies the PAYLOAD, so a report
    corrected without a rebuild keeps its predecessor's version, date and source
    hash — two byte-different documents claiming to be the same one. The
    generator's own digest is what distinguishes them."""
    t = _pdf_text()
    if not t:
        pytest.skip("housing_report.pdf not built, or pypdf unavailable")
    assert "Generator SHA-256" in t, "the report does not identify the code that made it"
    import hashlib
    with open(os.path.join(SRC, "housing_report.py"), "rb") as f:
        want = hashlib.sha256(f.read()).hexdigest()
    assert want[:8] in t.replace("\n", "").replace(" ", ""), (
        "the report's generator digest is stale -- re-render it")
