"""A figure that cannot be derived must say so, and say where it came from.

Almost everything in this payload is computed from the registry. A few numbers
cannot be, because the series has no machine-readable source — the CBC's
五大銀行新承做購屋貸款 rate is published as a per-release PDF and nothing else.

Those are allowed. What is not allowed is a transcribed number that looks
derived. Section 18 carried "the mortgage rate is a typed constant" as an open
item for two editions without saying why it was one, and the risk is not that
the number is wrong — it is that nobody can tell it is a transcription, so
nobody knows to re-read it.

So: typed figures declare themselves, carry their source, and are printed as
transcriptions in both editions. These tests pin all three.
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


def _text(path):
    if not os.path.exists(path):
        pytest.skip(f"{os.path.basename(path)} not built")
    return re.sub(r"\s+", " ", "\n".join((p.extract_text() or "") for p in PdfReader(path).pages))


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


def test_the_mortgage_rate_declares_itself_transcribed():
    """It is the one reference rate with no pinned source file."""
    m = _payload()["mortgage"]
    assert m.get("typed") is True, "the CBC mortgage rate is transcribed and must say so"


def test_every_typed_figure_carries_its_source():
    """A transcription without a source is just a number someone remembered."""
    blocks = _typed_blocks(_payload())
    assert blocks, "no typed figures found — did the marker get dropped?"
    for where, b in blocks:
        for field in ("src_zh", "src_en", "url"):
            assert b.get(field), f"{where}: typed figure missing {field}"
        assert b.get("period_en") or b.get("period_zh"), f"{where}: typed figure missing its period"
        assert b.get("source_format"), f"{where}: typed figure must say why it cannot be derived"


def test_a_typed_figure_names_a_real_source_url():
    for where, b in _typed_blocks(_payload()):
        assert b["url"].startswith("https://"), f"{where}: {b['url']!r} is not a source a reader can open"


def test_both_editions_print_that_it_is_transcribed():
    """Marking it in the payload is no use if the page still looks derived."""
    assert "transcribed, not derived" in _text(EN)
    assert "手抄，非推導" in _text(ZH)


def test_its_two_siblings_are_not_typed():
    """The deposit and rediscount rates ARE derived, from pinned CSVs. If one of
    them ever acquires the marker, something has quietly stopped being read."""
    bm = _payload()["benchmarks"]
    by_key = {b["key"]: b for b in bm} if isinstance(bm, list) else bm
    for key in ("deposit_1y", "rediscount"):
        b = by_key.get(key)
        if b is None:
            continue
        assert not b.get("typed"), f"{key} should be read from data/ref/cbc/, not transcribed"


def test_the_pinned_cbc_files_are_still_hashed_in_the_provenance():
    """The siblings' claim to be derived rests on these being pinned."""
    refs = (_payload()["meta"]["provenance"].get("refs") or {}).get("files") or []
    paths = {r["path"] for r in refs}
    for want in ("data/ref/cbc/A13Rate.csv", "data/ref/cbc/webF1.csv"):
        assert any(p.endswith(want.split("/")[-1]) for p in paths), f"{want} not hashed in provenance"
