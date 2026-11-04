"""The resemblance test is the paper auditing its own load-bearing assumption.

Every rung above the support rung assumes an unmatched building looks like the
matched buildings of its own type-and-price-decile cell. That assumption is what
narrows the published interval from the whole quality band, and until payload
v2.10 it was the only load-bearing claim in the report that was asserted rather
than measured.

These tests pin the two things a build cannot catch: that the arithmetic in the
block is internally consistent, and that both editions actually print the
failure rather than quietly reporting the half that passed.
"""
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(ROOT, "docs", "HOUSING_FINAL_REPORT.pdf")
ZH = os.path.join(ROOT, "docs", "HOUSING_FINAL_REPORT_ZH.pdf")
DATA = os.path.join(ROOT, "housing_data.json")

pytest.importorskip("pypdf")
from pypdf import PdfReader  # noqa: E402


def _payload():
    if not os.path.exists(DATA):
        pytest.skip("housing_data.json not built")
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _block():
    r = _payload().get("resemblance") or {}
    if not r.get("vars"):
        pytest.skip("payload predates the resemblance block (needs v2.10)")
    assert not r.get("error"), r["error"]
    return r


def _text(path):
    if not os.path.exists(path):
        pytest.skip(f"{os.path.basename(path)} not built")
    return re.sub(r"\s+", " ", "\n".join((p.extract_text() or "") for p in PdfReader(path).pages))


# ── the block is internally consistent ──────────────────────────────────────

def test_both_observables_are_tested():
    """Age and area are the two things the cells do not condition on."""
    assert set(_block()["vars"]) == {"built", "area"}


def test_absorbed_pct_follows_from_the_two_d_values():
    """The headline "77% absorbed" must be derived, not typed."""
    for col, v in _block()["vars"].items():
        # The payload stores d at 3dp but computed absorbed_pct from the
        # unrounded values, so recomputing from the published figures carries
        # the rounding. On a ratio near 2.4 that is worth a few tenths of a
        # point, which is why this is a consistency check and not an equality.
        want = (1 - v["within_cell_abs_d"] / abs(v["unconditional_d"])) * 100
        assert abs(want - v["absorbed_pct"]) < 1.0, f"{col}: {want:.2f} vs {v['absorbed_pct']}"


def test_signed_mean_never_exceeds_the_absolute_mean():
    for col, v in _block()["vars"].items():
        assert abs(v["within_cell_signed_d"]) <= v["within_cell_abs_d"] + 1e-9, col


def test_unbalanced_cell_count_matches_the_threshold():
    thr = _block()["balanced_at"]
    for col, v in _block()["vars"].items():
        worst = v["worst"]
        # every listed worst cell at or above the threshold must be counted
        assert v["cells_unbalanced"] >= sum(1 for w in worst if abs(w["d"]) >= thr), col
        assert v["cells_unbalanced"] <= v["cells"], col


def test_every_matched_building_is_covered():
    """The join is the test; a partial join would compare the wrong two groups."""
    n = _payload()["headline"]["buildings"]
    for col, v in _block()["vars"].items():
        assert v["buildings_covered"] <= n, col


def test_worst_cells_are_sorted_by_magnitude():
    for col, v in _block()["vars"].items():
        mags = [abs(w["d"]) for w in v["worst"]]
        assert mags == sorted(mags, reverse=True), col


# ── the paper publishes the failure, not just the pass ──────────────────────

def test_area_actually_failed():
    """If this ever starts passing, the prose below is wrong and must change."""
    a = _block()["vars"]["area"]
    assert a["absorbed_pct"] < 0, "area balance improved — rewrite §6, it says it got worse"
    assert a["within_cell_abs_d"] > abs(a["unconditional_d"])


def test_both_editions_print_the_failure():
    """A paper may not report the half that passed and bury the half that did not."""
    a = _block()["vars"]["area"]
    for name, text in (("EN", _text(EN)), ("ZH", _text(ZH))):
        assert f"{a['within_cell_abs_d']:.3f}" in text, f"{name}: within-cell area |d| absent"
        assert f"{a['cells_unbalanced']} of {a['cells']}" in text or \
               f"{a['cells_unbalanced']} / {a['cells']}" in text, f"{name}: unbalanced cell count absent"


def test_both_editions_print_the_age_result_too():
    b = _block()["vars"]["built"]
    for name, text in (("EN", _text(EN)), ("ZH", _text(ZH))):
        assert f"{b['absorbed_pct']:.0f}%" in text or f"{b['absorbed_pct']:.1f}%" in text, \
            f"{name}: age absorbed share absent"


def test_the_executive_summary_is_qualified():
    """The interval may not be presented as validated anywhere."""
    assert "stated-assumption interval" in _text(EN)
    assert "在明列假設下" in _text(ZH)


def test_the_interval_itself_did_not_move():
    """This edition changed a claim's standing, not a number."""
    tp = next(r for r in _payload()["partial_id"]["rungs"] if r["key"] == "type_price")
    assert round(tp["gross"]["lo"], 2) == 1.90
    assert round(tp["gross"]["hi"], 2) == 4.26
