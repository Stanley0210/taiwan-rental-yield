"""Array order in the payload is not a contract, and nothing may rely on it.

This exists because of a real failure, not a hypothetical one. `low_use_rates()`
sorted on a column whose keys are all tied after filtering, with pandas' default
non-stable quicksort, so the surviving row order was a property of the installed
library rather than of the data -- identical inputs and identical code produced
the exact reverse order under pandas 3.0. That alone broke
`bin/rebuild-housing.sh`, which is the repository's headline promise.

Worse, both editions of the paper read that array BY POSITION: the last row as
the national rate, row 5 as Taipei, row 1 as Tainan. Under the other order the
report printed Kaohsiung's rate as the national one and swapped the two cities
-- three confidently labelled wrong numbers, with the PDF building cleanly and
the whole suite green.

Two defences, both pinned here: the reports look rows up by county code, and the
pipeline emits an explicit total order anyway.
"""
import json
import os
import random
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "housing_data.json")

sys.path.insert(0, SRC)

pytest.importorskip("pypdf")
from pypdf import PdfReader  # noqa: E402


def _payload():
    if not os.path.exists(DATA):
        pytest.skip("housing_data.json not built (run: python src/underwrite.py)")
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _rows():
    lu = (_payload().get("moi") or {}).get("low_use") or {}
    if not lu.get("rows"):
        pytest.skip("payload carries no low-use table")
    return lu["rows"]


def _by_code(rows, code):
    return next(r for r in rows if r["county"] == code)


# ── the lookup helper ────────────────────────────────────────────────────────

def test_lookup_finds_the_right_row_whatever_the_order():
    import housing_final_report as H
    rows = _rows()
    moi = {"low_use": {"rows": list(reversed(rows))}}
    for code in (r["county"] for r in rows):
        assert H.lu_rate(moi, code)["county"] == code


def test_a_missing_county_is_an_error_not_a_zero():
    """A silently absent county would otherwise read as a real 0% low-use rate."""
    import housing_final_report as H
    with pytest.raises(KeyError):
        H.lu_rate({"low_use": {"rows": _rows()}}, "zz")


def test_no_report_indexes_the_low_use_rows_by_position():
    for f in ("housing_final_report.py", "housing_final_report_zh.py"):
        with open(os.path.join(SRC, f), encoding="utf-8") as fh:
            src = fh.read()
        assert "low_use']['rows'][" not in src, f"{f} indexes low_use rows by position"
        assert 'low_use"]["rows"][' not in src, f"{f} indexes low_use rows by position"


# ── the pipeline's own order ─────────────────────────────────────────────────

def test_rows_are_in_an_explicit_total_order():
    """全國 first, then county code. Pinned so a rebuild diffs clean."""
    rows = _rows()
    want = sorted(rows, key=lambda r: (r["county"] != "all", r["county"] or ""))
    assert [r["county"] for r in rows] == [r["county"] for r in want]


def test_the_sort_is_stable():
    """The fix, as source: a tied sort key must not decide the output order."""
    with open(os.path.join(SRC, "underwrite.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert 'sort_values("period", kind="stable")' in src


# ── the regression that matters: the rendered numbers ───────────────────────

@pytest.mark.slow
def test_shuffled_rows_do_not_change_what_the_report_prints(tmp_path):
    """Build the paper against a deliberately mangled payload.

    The figures must come out right anyway, because they are looked up by code.
    This is the test that would have caught the original bug.
    """
    D = _payload()
    rows = D["moi"]["low_use"]["rows"]
    shuffled = list(rows)
    random.Random(1).shuffle(shuffled)
    if [r["county"] for r in shuffled] == [r["county"] for r in rows]:
        shuffled.reverse()
    D["moi"]["low_use"]["rows"] = shuffled

    payload = tmp_path / "housing_data.json"
    payload.write_text(json.dumps(D, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "report.pdf"

    env = dict(os.environ, REPORT_DATA=str(payload), REPORT_OUT=str(out))
    r = subprocess.run([sys.executable, os.path.join(SRC, "housing_final_report.py")],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]

    text = "\n".join((p.extract_text() or "") for p in PdfReader(str(out)).pages)
    nat = _by_code(rows, "all")["rate_pct"]
    tp = _by_code(rows, "a")["rate_pct"]
    tn = _by_code(rows, "d")["rate_pct"]
    assert f"national low-use rate {nat}%" in text
    assert f"from {tp}% in Taipei" in text
    assert f"{tn}% in Tainan" in text
