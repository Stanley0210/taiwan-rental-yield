"""Every reference rate is read from a pinned, hashed file -- including the one
that was typed for six payload versions.

The new-mortgage rate (中央銀行 五大銀行新承做購屋貸款) sat in underwrite.py as a
hand-typed constant. Payload 2.11 made it declare itself "typed" on the belief
that the series exists only as a PDF. That belief was wrong: the CBC's listing
page has no data file, but each month's release page carries an ODS with the
whole series, and nobody had opened a release page. Since 2.13 the ODS is pinned
under data/ref/cbc/ and the figure is read from it.

These tests pin three things: that the rate really is derived (and from the
file's LATEST month), that the pinned file still reproduces the number that
used to be typed (so the paper's sentence saying so stays true), and that if a
figure ever does have to be transcribed again it must carry its source.
"""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
EN = os.path.join(ROOT, "docs", "HOUSING_FINAL_REPORT.pdf")
ZH = os.path.join(ROOT, "docs", "HOUSING_FINAL_REPORT_ZH.pdf")
DATA = os.path.join(ROOT, "housing_data.json")
ODS = os.path.join(ROOT, "data", "ref", "cbc", "five_bank_new_loans.ods")

sys.path.insert(0, SRC)

pytest.importorskip("pypdf")
from pypdf import PdfReader  # noqa: E402


def _payload():
    if not os.path.exists(DATA):
        pytest.skip("housing_data.json not built")
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _text(path):
    if not os.path.exists(path):
        pytest.skip(f"{os.path.basename(path)} not built")
    return re.sub(r"\s+", " ", "\n".join((p.extract_text() or "") for p in PdfReader(path).pages))


def _series():
    import fetch_cbc as C
    return C.load_new_loans(ODS)


def _typed_blocks(obj, path=""):
    """Every dict in the payload that marks itself as transcribed."""
    out = []
    if isinstance(obj, dict):
        if obj.get("typed") is True:
            out.append((path or "/", obj))
        for k, v in obj.items():
            out += _typed_blocks(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _typed_blocks(v, f"{path}[{i}]")
    return out


# ── the mortgage rate is derived ────────────────────────────────────────────

def test_the_pinned_file_is_committed():
    assert os.path.exists(ODS), "data/ref/cbc/five_bank_new_loans.ods is not committed"


def test_the_payload_rate_is_the_latest_month_in_the_pinned_file():
    """Derived means: change the file and the number changes. Nothing typed."""
    m, last = _payload()["mortgage"], _series()[-1]
    assert not m.get("typed"), "the mortgage rate is read from a pinned file; it must not say typed"
    assert m["rate"] == last["rate"]
    assert m["period_zh"] == f"{last['year']}年{last['month']}月"
    assert m["period_iso"] == f"{last['year'] + 1911}-{last['month']:02d}"
    assert m["source_file"].endswith("five_bank_new_loans.ods")


def test_the_benchmark_strip_carries_the_same_figure():
    """The rate appears twice in the payload; they must be one number."""
    p = _payload()
    strip = {b["key"]: b for b in p["benchmarks"]}["mortgage"]
    for field in ("rate", "period_zh", "period_en", "period_iso"):
        assert strip[field] == p["mortgage"][field], field


def test_the_pinned_file_reproduces_the_figure_that_used_to_be_typed():
    """The paper says the old constant, 2.322% for May 2026, "was never wrong,
    only unverifiable". That sentence is checkable, so it is checked."""
    may = next(r for r in _series() if (r["year"], r["month"]) == (115, 5))
    assert may["rate"] == 2.322


def test_the_series_is_parsed_by_header_not_position():
    """A table that gains a column must not silently return another loan
    type's rate. The loader finds 購屋貸款 by name; this pins that it found a
    plausible mortgage series and not, say, 週轉金貸款."""
    s = _series()
    assert len(s) > 300, "the file should hold the monthly series back to 83/07"
    assert (s[0]["year"], s[0]["month"]) == (83, 7)
    assert all(0 < r["rate"] < 15 for r in s)
    # months are consecutive at the end -- no row skipped by the parser
    a, b = s[-2], s[-1]
    assert (b["year"] * 12 + b["month"]) - (a["year"] * 12 + a["month"]) == 1


def test_the_pinned_cbc_files_are_all_hashed_in_the_provenance():
    """A reference file the build reads but does not hash is the hole the
    manifest exists to close. That includes the .ods, which is not a .csv."""
    refs = (_payload()["meta"]["provenance"].get("refs") or {}).get("files") or []
    paths = {r["path"] for r in refs}
    for want in ("A13Rate.csv", "webF1.csv", "five_bank_new_loans.ods"):
        assert any(p.endswith(want) for p in paths), f"data/ref/cbc/{want} not hashed in provenance"


def test_both_editions_print_the_derived_rate_and_no_longer_call_it_transcribed():
    m = _payload()["mortgage"]
    en, zh = _text(EN), _text(ZH)
    assert f"{m['rate']:.3f}%" in en and f"{m['rate']:.3f}%" in zh
    assert m["period_en"] in en
    assert "transcribed, not derived" not in en
    assert "手抄，非推導" not in zh


# ── and if something ever has to be typed again ─────────────────────────────

def test_any_typed_figure_carries_its_source():
    """No figure in the payload is transcribed today. If one ever is, it must
    say where it came from and why it could not be derived."""
    for where, b in _typed_blocks(_payload()):
        for field in ("src_zh", "src_en", "url", "source_format"):
            assert b.get(field), f"{where}: typed figure missing {field}"
        assert b["url"].startswith("https://"), where
        assert b.get("period_en") or b.get("period_zh"), f"{where}: typed figure missing its period"
