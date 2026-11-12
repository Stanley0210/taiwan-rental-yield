"""A pair is the same building, not the same unit, and the paper has to say so.

Every sale in a building is paired with every lease in that building, and the
headline yield is total rent over total price. Nothing makes the two units the
same size. Three editions shipped without mentioning it; it was found by
stress-testing the paper before sending it to anyone, and it is the first thing
an appraiser would ask.

The measurement lives in payload block `size_robust`: the same median three
ways (headline, per 坪, size-matched pairs only), nationally and by city. These
tests pin what a build cannot catch -- that the block is internally consistent,
that both editions and both briefs print the readings that are LESS flattering
than the headline, and that no city gap is ever quoted from one reading alone.
"""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DOCS = {name: os.path.join(ROOT, "docs", name) for name in (
    "HOUSING_FINAL_REPORT.pdf", "HOUSING_FINAL_REPORT_ZH.pdf",
    "HOUSING_BRIEF.pdf", "HOUSING_BRIEF_ZH.pdf")}
DATA = os.path.join(ROOT, "housing_data.json")

sys.path.insert(0, SRC)
import references as R  # noqa: E402

pytest.importorskip("pypdf")
from pypdf import PdfReader  # noqa: E402


def _payload():
    if not os.path.exists(DATA):
        pytest.skip("housing_data.json not built")
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _block():
    z = _payload().get("size_robust") or {}
    if not z.get("per_ping"):
        pytest.skip("payload predates the size_robust block (needs v2.12)")
    return z


def _text(name):
    path = DOCS[name]
    if not os.path.exists(path):
        pytest.skip(f"{name} not built")
    return re.sub(r"\s+", " ", "\n".join((p.extract_text() or "") for p in PdfReader(path).pages))


# ── the block ────────────────────────────────────────────────────────────────

def test_the_headline_reading_is_the_published_headline():
    """The block's own "headline" must be the number on the cover, or the
    comparison is between two things nobody published."""
    z, h = _block(), _payload()["headline"]
    assert z["headline"]["gross"] == h["yield"]
    assert z["headline"]["buildings"] == h["buildings"]
    assert z["headline"]["pairs"] == h["pairs"]


def test_shifts_follow_from_the_medians():
    z = _block()
    for key in ("per_ping", "size_matched"):
        assert abs((z[key]["gross"] - z["headline"]["gross"]) - z[key]["shift_pp"]) < 1e-3, key


def test_size_matched_is_a_subset():
    """Filtering pairs by size can only remove pairs and buildings."""
    z = _block()
    assert z["size_matched"]["pairs"] <= z["headline"]["pairs"]
    assert z["size_matched"]["buildings"] <= z["headline"]["buildings"]
    assert abs(z["size_matched"]["pairs"] / z["headline"]["pairs"] * 100
               - z["size_matched"]["kept_pairs_pct"]) < 0.1


def test_the_three_pair_shares_partition_the_pairs():
    r = _block()["ratio"]
    total = r["pairs_within_band_pct"] + r["pairs_sold_bigger_pct"] + r["pairs_leased_bigger_pct"]
    assert abs(total - 100) < 0.3, total


def test_every_compared_city_has_all_three_readings():
    """A city in the listings comparison with a reading missing would force the
    table back to quoting one number, which is the thing this block replaced."""
    by_city = {r["city"]: r for r in _block()["counties"]}
    for city in R.GPG_CITIES:
        r = by_city[city]
        for key in ("headline", "per_ping", "size_matched", "pp_lo", "pp_hi"):
            assert r.get(key) is not None, f"{city} is missing {key}"


def test_the_footprint_split_covers_both_merged_cities():
    rows = {(r["city"], r["part"]): r for r in _block()["footprint"]}
    for city in ("臺南市", "高雄市"):
        proper, county = rows[(city, "city_proper")], rows[(city, "former_county")]
        whole = next(r for r in _block()["counties"] if r["city"] == city)
        assert proper["buildings"] + county["buildings"] == whole["buildings"], city


# ── the claims that rest on it ──────────────────────────────────────────────

def _gaps(city):
    r = next(x for x in _block()["counties"] if x["city"] == city)
    g = R.GPG_CITIES[city]
    return sorted([r["headline"] - g, r["per_ping"] - g, r["size_matched"] - g])


def test_the_direction_survives_every_reading():
    """The paper says the registered measure is higher in all five cities under
    all three readings. If that ever stops being true the sentence must go."""
    for city in R.GPG_CITIES:
        assert _gaps(city)[0] > 0, f"{city}: a reading puts the registry at or below listings"


def test_tainan_is_the_largest_gap_under_every_reading():
    """"Widening southward, largest in 臺南" is quoted in the brief and the
    emails; it has to hold at the bottom of the range, not just the top."""
    lows = {city: _gaps(city)[0] for city in R.GPG_CITIES}
    assert max(lows, key=lows.get) == "臺南市", lows


@pytest.mark.parametrize("name", list(DOCS))
def test_no_document_quotes_a_city_gap_from_one_reading(name):
    """Every document that carries the comparison prints the BOTTOM of 臺南's
    range, not only the headline gap that v1.1 and v1.2 quoted alone."""
    lo, _mid, hi = _gaps("臺南市")
    text = _text(name)
    assert f"{lo:+.2f}" in text, f"{name}: the size-controlled 臺南 gap ({lo:+.2f}) is absent"
    assert f"{hi:+.2f}" in text, f"{name}: the headline 臺南 gap ({hi:+.2f}) is absent"


@pytest.mark.parametrize("name", list(DOCS))
def test_both_less_flattering_readings_are_printed(name):
    z, text = _block(), _text(name)
    assert f"{z['per_ping']['gross']:.2f}%" in text, f"{name}: per-坪 national median absent"
    assert f"{z['size_matched']['gross']:.2f}%" in text, f"{name}: size-matched national median absent"


def test_the_correction_is_in_the_register():
    """A published number that moved is recorded, not silently replaced."""
    assert "pre-send stress test" in _text("HOUSING_FINAL_REPORT.pdf")
    assert "寄出前的壓力測試" in _text("HOUSING_FINAL_REPORT_ZH.pdf")


def test_the_filing_rule_cites_the_statutes():
    """Section 5's central institutional fact was asserted for three editions."""
    for name in ("HOUSING_FINAL_REPORT.pdf", "HOUSING_FINAL_REPORT_ZH.pdf"):
        text = _text(name)
        assert "不動產經紀業管理條例" in text and "§24-1" in text.replace(" ", ""), name
        assert "租賃住宅市場發展及管理條例" in text, name
        assert "三十日內" in text, f"{name}: the statutes are named but not quoted"


def test_the_readme_quotes_the_range_not_one_reading():
    """The README is hand-maintained, so its comparison is pinned here: it must
    carry the bottom of 臺南's range, which is the number v1.1 and v1.2 left out."""
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    for city in R.GPG_CITIES:
        lo, _mid, hi = _gaps(city)
        assert f"{lo:+.2f} to {hi:+.2f}pp" in readme, f"README: {city} gap range is stale or missing"
