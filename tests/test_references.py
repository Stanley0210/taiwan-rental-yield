"""The bibliography is derived, not typed, and both editions carry the same one.

A paper's references are the one place where "I'll just write it out" is the
normal practice, and it is the same mistake as typing a number: the inline
label and the entry drift, a citation survives a cut paragraph and becomes an
orphan, or one language edition quietly cites something the other does not.

So the same rule applies here as to every figure in the report. `cite()` builds
the label from the entry, both reports refuse to build while an entry is
uncited, and the tests below pin the parts a build cannot catch.
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

sys.path.insert(0, SRC)
import references as R  # noqa: E402

pytest.importorskip("pypdf")
from pypdf import PdfReader  # noqa: E402


def _text(path):
    if not os.path.exists(path):
        pytest.skip(f"{os.path.basename(path)} not built")
    return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)


def _flat(s):
    """Whitespace-normalised, because a PDF breaks lines wherever it likes.

    Matching a journal line against raw extracted text fails on wrapping alone,
    which says nothing about whether the citation is on the page.
    """
    return re.sub(r"\s+", " ", s)


# ── the entries themselves ───────────────────────────────────────────────────

def test_every_entry_is_complete():
    """A half-filled entry prints a half-filled citation."""
    for key, r in R.REFERENCES.items():
        for field in ("group", "year", "authors", "full", "title", "where", "why"):
            assert r.get(field), f"{key} is missing {field}"
        assert isinstance(r["authors"], list) and r["authors"], f"{key}: authors must be a list"
        assert isinstance(r["year"], int), f"{key}: year must be an int"
        assert r["group"] in R.GROUP_ORDER, f"{key}: unknown group {r['group']!r}"


def test_every_entry_has_both_languages():
    """A Chinese edition must not hand its reader English annotations."""
    for key in R.REFERENCES:
        assert R.why(key, "zh"), f"{key} has no Chinese note"
        assert R.why(key, "en"), f"{key} has no English note"
        assert R.why(key, "zh") != R.why(key, "en")


def test_years_are_plausible():
    for key, r in R.REFERENCES.items():
        assert 1950 <= r["year"] <= 2026, f"{key}: implausible year {r['year']}"


def test_groups_partition_the_entries():
    """Every entry reachable through the rendering path the reports use."""
    seen = {k for g in R.GROUP_ORDER for k, _ in R.entries(g)}
    assert seen == set(R.REFERENCES)


# ── the label is derived ─────────────────────────────────────────────────────

def test_cite_refuses_an_unknown_work():
    with pytest.raises(KeyError):
        R.cite("no_such_paper_2099")


def test_author_forms():
    assert "Manski 2003" in R.cite("manski2003").replace("&nbsp;", " ")
    assert "Horowitz and Manski 1995" in R.cite("horowitz1995").replace("&nbsp;", " ")
    assert "Himmelberg et al. 2005" in R.cite("himmelberg2005").replace("&nbsp;", " ")


def test_textual_form_puts_the_year_in_parentheses():
    assert R.cite_t("chang2018").replace("&nbsp;", " ") == "Chang and Chen (2018)"


def test_a_citation_never_breaks_across_lines():
    """reportlab will split "Himmelberg et al." from "2005" otherwise.

    It did, in the Chinese edition, where a CJK line's only breakable spaces are
    the ones bracketing Latin text.
    """
    for key in R.REFERENCES:
        for label in (R.cite(key), R.cite_t(key)):
            assert " " not in label.replace("&nbsp;", ""), f"{key}: breakable space in {label!r}"


def test_multiple_works_separate_but_stay_individually_whole():
    both = R.cite("manski1989", "manski2003")
    assert "; " in both
    for part in both.strip("()").split("; "):
        assert " " not in part.replace("&nbsp;", "")


# ── the reports ──────────────────────────────────────────────────────────────

def test_both_editions_render_every_work():
    """An entry that exists but never reaches the page is not a reference."""
    en, zh = _text(EN), _text(ZH)
    for key, r in R.REFERENCES.items():
        surname = r["authors"][0]
        for name, text in (("EN", en), ("ZH", zh)):
            assert surname in text, f"{name}: {key} ({surname}) absent from the references"


def test_bibliographic_fields_are_not_translated():
    """A citation has to be copyable into a reference manager as published."""
    en, zh = _text(EN), _text(ZH)
    for key, r in R.REFERENCES.items():
        if r["group"] == "data":
            continue
        where = _flat(r["where"].split(";")[0].strip())
        assert where in _flat(en), f"EN: {key} journal line missing ({where!r})"
        assert where in _flat(zh), f"ZH: {key} journal line missing ({where!r})"


def test_titles_reach_both_editions():
    en, zh = _flat(_text(EN)), _flat(_text(ZH))
    for key, r in R.REFERENCES.items():
        title = _flat(r["title"])
        assert title in en, f"EN: {key} title missing"
        assert title in zh, f"ZH: {key} title missing"


def test_no_entry_is_an_orphan():
    """Mirrors the check both generators run at build time.

    Importing the report module is not enough -- cite() only records a key when
    the prose actually runs -- so this reads the sources instead.
    """
    src = ""
    for f in ("housing_final_report.py", "housing_final_report_zh.py"):
        with open(os.path.join(SRC, f), encoding="utf-8") as fh:
            src += fh.read()
    cited = set(re.findall(r"cite(?:_t)?\(\s*((?:'[a-z0-9_]+'\s*,?\s*)+)", src))
    keys = {k.strip().strip("'") for group in cited for k in group.split(",") if k.strip()}
    missing = set(R.REFERENCES) - keys
    assert not missing, f"nothing cites: {sorted(missing)}"


def test_both_editions_cite_the_same_works():
    """One edition quietly citing something the other does not is drift."""
    per = {}
    for f in ("housing_final_report.py", "housing_final_report_zh.py"):
        with open(os.path.join(SRC, f), encoding="utf-8") as fh:
            src = fh.read()
        groups = re.findall(r"cite(?:_t)?\(\s*((?:'[a-z0-9_]+'\s*,?\s*)+)", src)
        per[f] = {k.strip().strip("'") for g in groups for k in g.split(",") if k.strip()}
    en, zh = per["housing_final_report.py"], per["housing_final_report_zh.py"]
    assert en == zh, f"only EN: {sorted(en - zh)}; only ZH: {sorted(zh - en)}"


# ── the one typed table in the paper says so ────────────────────────────────

def test_external_figures_are_disclosed_as_typed():
    """The GPG comparison cannot be derived from any payload, so the report has
    to admit it rather than let it pass for a computed figure."""
    assert "typed, not derived" in _text(EN)
    assert "手寫的" in _text(ZH)
    assert R.EXTERNAL_READ_ON in _text(EN)


def test_external_city_figures_are_present_in_both():
    for city, pct in R.GPG_CITIES.items():
        assert f"{pct:.2f}%" in _text(EN)
        assert city in _text(ZH)
