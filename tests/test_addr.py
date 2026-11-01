"""Address normalisation — the load-bearing join key for the housing pipeline.

A weak normaliser and a thin market look identical from the outside: both show
up as "not many matches". So this file exists to make the normaliser's own
failure visible before anyone concludes something about the data.

The labelled fixture (tests/fixtures/addr_pairs.csv) holds pairs of raw 門牌
strings that a human confirmed refer to the same building. Recall on that
fixture is the guard: below ~90% the normaliser is the problem, not the market.
"""

import csv
import os

import pytest

from normalize_addr import addr_key, addr_parts, street_key

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "addr_pairs.csv")


# ── the grammar, case by case ────────────────────────────────────────────

@pytest.mark.parametrize("raw,expect", [
    # full-width digits (the registry writes every number this way)
    ("臺北市中山區復興北路３８０巷１１號４樓", "台北市中山區復興北路380巷11號"),
    # 段 in Chinese numerals, floor in Chinese numerals, descriptive tail
    ("臺北市中山區南京東路三段８９巷２０號二樓等共有部分", "台北市中山區南京東路3段89巷20號"),
    # 巷 AND 弄 nesting
    ("新北市板橋區文化路一段１８８巷１弄５號３樓", "新北市板橋區文化路1段188巷1弄5號"),
    # a 號 range collapses to its first member
    ("台北市大安區和平東路2段5~7號", "台北市大安區和平東路2段5號"),
    ("台北市大安區和平東路2段5、7號", "台北市大安區和平東路2段5號"),
    # 之N belongs to the 門牌 and must survive
    ("臺北市信義區松高路12之3號8樓", "台北市信義區松高路12之3號"),
    # 臺 and 台 are the same city
    ("臺北市大安區復興南路1段1號", "台北市大安區復興南路1段1號"),
    # whitespace anywhere
    ("台北市 大安區 復興南路 1段 1號 2樓", "台北市大安區復興南路1段1號"),
])
def test_grammar(raw, expect):
    assert addr_key(raw) == expect


@pytest.mark.parametrize("raw", ["", "   ", None, "台北市中正區", "台北市中正區水源段三小段", 123])
def test_unparseable_returns_empty(raw):
    """No 號 means no building key. That is a category, not a crash: land-only
    records genuinely cannot be matched by address, and returning '' lets the
    caller drop them instead of silently matching them to each other."""
    assert addr_key(raw) == ""


def test_empty_keys_never_collide():
    a, b = "台北市中正區", "新北市板橋區"
    assert addr_key(a) == addr_key(b) == ""   # so the matcher MUST filter these out


def test_floor_is_discarded_so_units_collapse_to_one_building():
    same = ["台北市信義區松仁路100號4樓", "台北市信義區松仁路100號12樓",
            "台北市信義區松仁路100號地下一層", "臺北市信義區松仁路１００號"]
    keys = {addr_key(s) for s in same}
    assert len(keys) == 1, keys


def test_different_numbers_do_not_collapse():
    """The near-miss case. 2號 and 12號 on one lane are different buildings and
    must stay tier 2, or the whole match tier is meaningless."""
    assert addr_key("台北市中山區農安街77巷2號") != addr_key("台北市中山區農安街77巷12號")


def test_parts_and_street_key():
    p = addr_parts("新北市板橋區文化路一段１８８巷１弄５號３樓")
    assert p["number"] == 5 and p["sub"] is None
    assert p["street"] == "新北市板橋區文化路1段188巷1弄"
    assert street_key("台北市中山區農安街77巷2號") == street_key("台北市中山區農安街77巷12號")


def test_sub_number_parsed():
    p = addr_parts("臺北市信義區松高路12之3號8樓")
    assert (p["number"], p["sub"]) == (12, 3)


def test_idempotent():
    once = addr_key("臺北市中山區南京東路三段８９巷２０號二樓等共有部分")
    assert addr_key(once) == once


# ── the recall guard ─────────────────────────────────────────────────────

def _fixture_rows():
    with open(FIXTURE, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("a") and r.get("b")]


def test_fixture_exists_and_is_substantial():
    rows = _fixture_rows()
    assert len(rows) >= 100, f"only {len(rows)} labelled pairs; the guard needs ~100"


def test_normaliser_recall_on_labelled_pairs():
    """Every labelled pair refers to the same building, so every pair must
    produce one key. Below 90% the normaliser is broken and NO conclusion about
    market thinness may be drawn from a low match count."""
    # Positives only. The fixture also carries negative pairs, which are SUPPOSED
    # to produce different keys; counting them here would cap recall at the
    # positive share and make the threshold meaningless.
    pos = [r for r in _fixture_rows() if r.get("same") != "0"]
    assert pos, "fixture has no positive pairs"
    hits = [r for r in pos if addr_key(r["a"]) == addr_key(r["b"]) != ""]
    recall = len(hits) / len(pos)
    misses = [(r["a"], r["b"], addr_key(r["a"]), addr_key(r["b"]))
              for r in pos if addr_key(r["a"]) != addr_key(r["b"])][:5]
    assert recall >= 0.90, f"recall {recall:.1%} of {len(pos)} pairs; first misses: {misses}"


def test_negative_pairs_stay_separate():
    """Guard against the opposite failure: a normaliser that matches everything
    would score 100% recall and be useless."""
    rows = _fixture_rows()
    neg = [r for r in rows if r.get("same") == "0"]
    if not neg:
        pytest.skip("no negative pairs in fixture")
    bad = [r for r in neg if addr_key(r["a"]) == addr_key(r["b"])]
    assert not bad, f"{len(bad)} negative pairs collapsed: {bad[:3]}"


# ── the two assumptions this module used to state and the registry falsifies ──

@pytest.mark.parametrize("raw,want", [
    # a unit designator CAN contain 號 -- the flat's own number
    ("臺中市西區昇平街１４６號五樓１號", "台中市西區昇平街146號"),
    ("臺中市南區民生路９巷１號５樓３號", "台中市南區民生路9巷1號"),
    ("臺中市南屯區東興西街１１號四樓之１５號", "台中市南屯區東興西街11號"),
    ("臺東縣台東市開封街３０１號八樓之２號", "台東縣台東市開封街301號"),
    # a record can carry a SECOND 門牌 after a separator
    ("臺北市士林區承德路四段２９６號十二樓、２９８號十二樓", "台北市士林區承德路4段296號"),
    ("臺中市南屯區永春路８０巷１０號五樓、永春路８０巷１６號", "台中市南屯區永春路80巷10號"),
    # ...but 「5、7號」 is a RANGE, not a second 門牌, and must still collapse
    ("台北市大安區和平東路2段5、7號", "台北市大安區和平東路2段5號"),
    ("台北市大安區和平東路2段5~7號", "台北市大安區和平東路2段5號"),
])
def test_the_building_號_is_not_always_the_last_one(raw, want):
    """addr_key cut at the LAST 號 on the stated assumption that a unit
    designator never contains one. Measured in the pinned window, 343 distinct
    keys falsify it -- they keyed a flat, or two buildings at once, and so
    matched nothing on the other side of the join."""
    assert addr_key(raw) == want


@pytest.mark.parametrize("variant,plain", [
    ("屏東縣屏東巿公裕街２４２號十樓之二", "屏東縣屏東市公裕街242號"),
    ("屏東縣屏東巿武立街４２巷１１之２號", "屏東縣屏東市武立街42巷11之2號"),
])
def test_the_巿_mis_encoding_folds_to_市(variant, plain):
    """NFKC does NOT merge 巿 (U+5DFF) and 市 (U+5E02) -- they are separate CJK
    ideographs. 3,456 sale rows in the pinned window carry the variant and ZERO
    lease rows do, so a sale spelled 巿 could never find its own lease."""
    assert addr_key(variant) == plain
    assert addr_key(variant) == addr_key(variant.replace("巿", "市"))
