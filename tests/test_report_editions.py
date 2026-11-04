"""The English and Chinese editions must state the same numbers.

The two generators deliberately keep their own f-strings instead of sharing a
bilingual template table. That buys safety on one axis -- a shared positional
template is how housing.js printed a count as a percentage four times, same
placeholder arity, different order -- and costs it on another: nothing in the
language stops the two files drifting apart.

So the drift is what gets pinned. Both read one payload, so a disagreement is
a bug in one of the write-ups, not a data question. Prose may differ freely;
the numbers may not.
"""
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
EN = os.path.join(ROOT, "docs", "HOUSING_FINAL_REPORT.pdf")
ZH = os.path.join(ROOT, "docs", "HOUSING_FINAL_REPORT_ZH.pdf")
# The two-page briefs are a third and fourth place a figure can go stale, which
# is exactly why they are generated from the payload rather than written. Same
# rule: prose may differ freely between the four, numbers may not.
BRIEF_EN = os.path.join(ROOT, "docs", "HOUSING_BRIEF.pdf")
BRIEF_ZH = os.path.join(ROOT, "docs", "HOUSING_BRIEF_ZH.pdf")
DATA = os.path.join(ROOT, "housing_data.json")

pytest.importorskip("pypdf")
from pypdf import PdfReader  # noqa: E402


def _text(path):
    if not os.path.exists(path):
        pytest.skip(f"{os.path.basename(path)} not built")
    return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)


def _payload():
    if not os.path.exists(DATA):
        pytest.skip("housing_data.json not built (run: python src/underwrite.py)")
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _headline_figures(D):
    """The numbers a reader would quote. Formatted exactly as both editions print them."""
    h, pid, pre, wf = D["headline"], D["partial_id"], D["presale"], D["coverage_waterfall"]
    rung = {r["key"]: r for r in pid["rungs"]}["type_price"]
    age, rb = D["age"], D["rent_bias"]
    return {
        "gross yield": f"{h['yield']:.2f}",
        "net yield": f"{h['net']:.2f}",
        "coverage": f"{h['coverage_pct']:.2f}",
        "coverage ceiling": f"{h['coverage_ceiling_pct']:.2f}",
        "matched buildings": f"{h['buildings']:,}",
        "universe buildings": f"{h['universe_buildings']:,}",
        "pairs": f"{h['pairs']:,}",
        "bound low": f"{rung['gross']['lo']:.2f}",
        "bound high": f"{rung['gross']['hi']:.2f}",
        "registry-side loss": f"{wf['law_pp']:.1f}",
        "selection effect": f"{age['ppp_diff_pct']:.1f}",
        "social share": f"{rb['social_share_pct']:.1f}",
        "pre-sale gap": f"{pre['curve'][0]['gap_pct']:.1f}",
    }


def test_both_editions_state_the_same_headline_numbers():
    en, zh = _text(EN), _text(ZH)
    missing = []
    for label, value in _headline_figures(_payload()).items():
        for name, body in (("EN", en), ("ZH", zh)):
            if value not in body:
                missing.append(f"{label} ({value}) absent from the {name} edition")
    assert not missing, "the two editions disagree:\n  " + "\n  ".join(missing)


def test_the_chinese_edition_is_actually_in_chinese():
    """A build that silently fell back to the English strings would still be a PDF."""
    zh = _text(ZH)
    cjk = len(re.findall(r"[一-鿿]", zh))
    latin = len(re.findall(r"[A-Za-z]", zh))
    assert cjk > latin, f"ZH edition is not Chinese-primary ({cjk} CJK vs {latin} Latin)"
    assert cjk > 5000, f"ZH edition has only {cjk} CJK characters -- did a section drop out?"


def test_the_chinese_edition_draws_every_glyph_it_prints():
    """Codepoints outside the embedded font render as notdef boxes.

    The payload's prose is written for the web, where the system font stack is
    wider than Noto Sans TC. src_zh for the management fee carries U+FE0F after
    its warning sign, and the PDF is the only surface that cannot draw it.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(os.path.join(ROOT, "data", "fonts", "NotoSansTC-Regular.ttf"))
    cmap = set()
    for t in font["cmap"].tables:
        cmap |= set(t.cmap.keys())

    undrawable = sorted({c for c in _text(ZH) if ord(c) > 127 and ord(c) not in cmap})
    assert not undrawable, "glyphs the embedded font cannot draw: " + ", ".join(
        f"U+{ord(c):04X}" for c in undrawable)


def test_the_chinese_edition_derives_its_verdicts():
    """Section 17's own rule: a typed conclusion stops following the data.

    Every verdict the payload can emit needs a Chinese label, or the PDF falls
    back to printing the raw key.
    """
    sys.path.insert(0, SRC)
    import housing_final_report_zh as Z

    D = _payload()
    for got in (D["parking_audit"]["verdict"]["verdict"], D["walkup_resolution"]["verdict"]):
        assert got in Z.VERDICT_ZH, f"verdict {got!r} has no Chinese label"


def test_both_editions_rebuild_from_the_committed_payload():
    """Neither generator may depend on anything outside the repository."""
    if not os.path.exists(DATA):
        pytest.skip("housing_data.json not built")
    import tempfile

    for mod, var in (("housing_final_report", "REPORT_OUT"),
                     ("housing_final_report_zh", "REPORT_OUT_ZH")):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.pdf")
            env = dict(os.environ, **{var: out})
            r = subprocess.run([sys.executable, os.path.join(SRC, mod + ".py")],
                               capture_output=True, text=True, env=env, cwd=ROOT)
            assert r.returncode == 0, f"{mod} failed:\n{r.stderr[-2000:]}"
            assert os.path.getsize(out) > 100_000, f"{mod} produced a suspiciously small PDF"


# ── the briefs ──────────────────────────────────────────────────────────────
# A brief exists to be sent to someone who has not read the paper, so a figure
# that disagrees with the paper is worse here than anywhere else: it is the
# only number that reader will ever see.

@pytest.mark.parametrize("brief", [BRIEF_EN, BRIEF_ZH])
def test_each_brief_fits_on_two_pages(brief):
    """It is a two-page brief. Three pages with one box on the last is not one."""
    if not os.path.exists(brief):
        pytest.skip(f"{os.path.basename(brief)} not built")
    assert len(PdfReader(brief).pages) == 2


@pytest.mark.parametrize("brief", [BRIEF_EN, BRIEF_ZH])
def test_the_brief_agrees_with_the_paper_on_the_headline(brief):
    D = _payload()
    text = _text(brief)
    h = D["headline"]
    for name, want in (("gross yield", f"{h['yield']:.2f}"),
                       ("net yield", f"{h['net']:.2f}"),
                       ("coverage", f"{h['coverage_pct']:.2f}"),
                       ("coverage ceiling", f"{h['coverage_ceiling_pct']:.2f}"),
                       ("matched buildings", f"{h['buildings']:,}"),
                       ("universe buildings", f"{h['universe_buildings']:,}"),
                       ("pairs", f"{h['pairs']:,}")):
        assert want in text, f"{os.path.basename(brief)}: {name} ({want}) absent"


@pytest.mark.parametrize("brief", [BRIEF_EN, BRIEF_ZH])
def test_the_brief_states_the_bounds_and_the_failed_test(brief):
    """The brief may not quote the narrowed interval without the caveat the
    paper attaches to it -- that is the one shortening a summary must not make."""
    D = _payload()
    rung = {r["key"]: r for r in D["partial_id"]["rungs"]}["type_price"]["gross"]
    text = _text(brief)
    assert f"{rung['lo']:.2f}" in text and f"{rung['hi']:.2f}" in text
    rz = (D.get("resemblance") or {}).get("vars")
    if rz:
        assert f"{rz['built']['absorbed_pct']:.0f}" in text, "the brief hides the balance result"


@pytest.mark.parametrize("brief", [BRIEF_EN, BRIEF_ZH])
def test_the_brief_carries_the_doi(brief):
    assert "10.5281/zenodo.23902646" in _text(brief)
