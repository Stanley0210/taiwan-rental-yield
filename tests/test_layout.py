"""No line of text may run past the page frame, in any of the four documents.

This exists because one did. Payload 2.11 added "transcribed, not derived: the
CBC publishes no CSV for this series" to a table cell whose column did not
wrap, and the sentence ran 188pt past the right margin in the English report
and off the page in the Chinese one. Both shipped to the live site. The overflow
scan had been run by hand -- before that change, not after it.

Text extraction cannot see this: the words are all there. Only the geometry
shows it, so this reads glyph rectangles and compares their right edge with the
frame. Right-aligned table cells legitimately sit a point or two past the edge
(cell padding), which is what the tolerance is for; the real failures were 16pt
and up.
"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ["HOUSING_FINAL_REPORT.pdf", "HOUSING_FINAL_REPORT_ZH.pdf",
        "HOUSING_BRIEF.pdf", "HOUSING_BRIEF_ZH.pdf"]
RIGHT_MARGIN_PT = 20 / 25.4 * 72      # every document is built with a 20mm margin
TOLERANCE_PT = 5.0

pdfium = pytest.importorskip("pypdfium2")


@pytest.mark.parametrize("name", DOCS)
def test_no_text_runs_past_the_frame(name):
    path = os.path.join(ROOT, "docs", name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not built")
    doc = pdfium.PdfDocument(path)
    offenders = []
    for i in range(len(doc)):
        page = doc[i]
        limit = page.get_width() - RIGHT_MARGIN_PT + TOLERANCE_PT
        tp = page.get_textpage()
        for j in range(tp.count_rects()):
            left, bottom, right, top = tp.get_rect(j)
            if right > limit:
                text = " ".join(tp.get_text_bounded(left, bottom, right, top).split())
                offenders.append(f"p{i + 1}: +{right - limit + TOLERANCE_PT:.0f}pt  …{text[-40:]}")
    assert not offenders, f"{name} has text past the right margin:\n  " + "\n  ".join(offenders[:6])
