#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The closing report on the housing pivot -- everything it found, written when it was parked.

    venv/bin/python3 docs/housing_final_report.py   -> docs/HOUSING_FINAL_REPORT.pdf

Two kinds of content, kept apart:
  * every NUMBER is read out of housing_data.json (payload v2.8) at build time;
  * the HISTORY -- what was published first, what was retracted, which bugs shipped --
    comes from docs/HOUSING_HANDOFF.md, and is written as history ("was first published
    as ...") because those figures no longer exist in any payload.

Charts are drawn with reportlab.graphics (no matplotlib on this machine). The CJK
font is the embedded Noto Sans TC, for the reason housing_report.py explains.
"""
import json
import math
import os
import statistics
import sys

from reportlab.graphics.shapes import Drawing, Line, Rect, String, PolyLine
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

from references import (EXTERNAL_READ_ON, GPG_CITIES, GPG_NATIONAL, GPG_UPDATED,
                        GROUP_ORDER, byline, cite, cite_t, entries, uncited)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Overridable so a test can build the report against a deliberately mangled
# payload -- that is how the low-use row-order regression is pinned.
DATA = os.environ.get("REPORT_DATA", os.path.join(ROOT, "housing_data.json"))
FONT_VAR = os.path.join(ROOT, "data", "fonts", "NotoSansTC.ttf")
# Static Regular/Bold instances of the variable font. The variable file's DEFAULT
# instance is weight 100 (Thin), which is what reportlab draws, and it has no bold.
#
# These used to be derived by hand outside the project venv and were gitignored,
# which meant a clean clone silently produced a thin, bold-less report -- a
# reproducibility hole in the one document that argues for reproducibility.
# `_ensure_static_fonts()` now derives them on demand from the committed
# variable font, so the only tracked font file is the upstream original.
FONT_REG = os.environ.get("FONT_REG", os.path.join(ROOT, "data", "fonts", "NotoSansTC-Regular.ttf"))
FONT_BOLD = os.environ.get("FONT_BOLD", os.path.join(ROOT, "data", "fonts", "NotoSansTC-Bold.ttf"))
OUT = os.environ.get("REPORT_OUT", os.path.join(ROOT, "docs", "HOUSING_FINAL_REPORT.pdf"))

# The citable edition of this write-up. The payload carries its own version;
# these two move independently and the cover prints both.
PAPER_VERSION = "v1.3"
PAPER_DATE = "2026-11-11"

# Section 16 registers corrections to numbers. This registers editions of the
# write-up, which is a different thing and was missing: v1.0 had no way to say
# what a later version had changed. Newest first; the cover prints the top row.
PAPER_CHANGES = [
    ("v1.3", "2026-11-11",
     "Three things found by stress-testing the paper before sending it to anyone. "
     "A pair is a sale and a lease in the same building, not the same unit, and no "
     "earlier edition said so: section 4 now measures what the size mismatch is "
     "worth, per 坪 and on size-matched pairs. The national headline survives it; "
     "the city comparison does not survive it unchanged, and the gap against the "
     "listings figure is restated on a size-normalised basis, which is smaller in "
     "the south. The hedge about city footprints is replaced by a measurement. And "
     "the registry's lease-filing rule, asserted for three editions, is now cited "
     "to the two statutes it comes from."),
    ("v1.2", "2026-11-04",
     "Tests the resemblance assumption that every rung above the support rung "
     "rests on, and publishes the result, which is that it only half holds: the "
     "cells absorb 77% of the age gap between matched and unmatched buildings "
     "and make the size gap WORSE. No number moved -- the interval is the same "
     "and was always labelled assumption-dependent -- but its standing changed, "
     "from an assumption nobody had checked to one the data contradicts on a "
     "measurable dimension. Section 6 says so."),
    ("v1.1", "2026-11-03",
     "Adds section 19, the references, and with it the first comparison against "
     "published estimates (section 4) -- including that the Taiwan yield in "
     "circulation traces to a listings aggregator rather than to transaction "
     "data. Section 18 rewritten: the project is published, so the items saying "
     "nobody had read it and the repositories were private had stopped being "
     "true. No measured figure changed."),
    ("v1.0", "2026-11-01",
     "First citable edition, written when the project was parked."),
]

INK = colors.HexColor("#191814")
MUTED = colors.HexColor("#6b675c")
RULE = colors.HexColor("#cfc9ba")
ACCENT = colors.HexColor("#2b3ec9")
ACCENT2 = colors.HexColor("#eb6834")
ACCENT3 = colors.HexColor("#1baf7a")
SOFT = colors.HexColor("#dfe3fb")
F = "NotoTC"
FRAME_W = A4[0] - 40 * mm

CITY = {"a": "臺北市", "b": "臺中市", "c": "基隆市", "d": "臺南市", "e": "高雄市",
        "f": "新北市", "g": "宜蘭縣", "h": "桃園市", "i": "嘉義市", "j": "新竹縣",
        "k": "苗栗縣", "m": "南投縣", "n": "彰化縣", "o": "新竹市", "p": "雲林縣",
        "q": "嘉義縣", "t": "屏東縣", "u": "花蓮縣", "v": "臺東縣", "w": "金門縣",
        "x": "澎湖縣", "z": "連江縣"}


# ------------------------------------------------------------------ formatting
def n0(x):
    return f"{x:,.0f}"


def p2(x):
    return f"{x:.2f}%"


def pp(x, d=2):
    return f"{x:+.{d}f}pp"


# ------------------------------------------------------------------ styles
def _ensure_static_fonts():
    """Derive Regular (wght 400) and Bold (wght 700) from the variable font.

    Cached next to it; both are gitignored, because deriving them takes about a
    second and committing two 12 MB binaries to make a 120 KB PDF is the wrong
    trade. Needs `fonttools`.
    """
    import os as _os
    if _os.path.exists(FONT_REG) and _os.path.exists(FONT_BOLD):
        return
    from fontTools.ttLib import TTFont as _TT
    from fontTools.varLib import instancer as _inst
    for path, wght, style in ((FONT_REG, 400, "Regular"), (FONT_BOLD, 700, "Bold")):
        if _os.path.exists(path):
            continue
        inst = _inst.instantiateVariableFont(_TT(FONT_VAR), {"wght": wght})
        # Pinning the axis does NOT rewrite the name table: both instances come
        # out still called "Noto Sans TC Thin". reportlab keys fonts by that
        # name, so the second registration silently overwrites the first and
        # the whole report renders in one weight with no bold at all.
        nm = inst["name"]
        for nid, val in ((1, "Noto Sans TC"), (2, style),
                         (4, f"Noto Sans TC {style}"), (6, f"NotoSansTC-{style}")):
            nm.setName(val, nid, 3, 1, 0x409)   # Windows / Unicode BMP / en-US
            nm.setName(val, nid, 1, 0, 0)       # Macintosh / Roman / English
        inst.save(path)
        print(f"[fonts] derived {_os.path.basename(path)} (wght {wght}, named {style})")


def styles():
    from reportlab.lib.fonts import addMapping
    # Derive BEFORE the existence check, not inside it: on a clean clone the
    # statics do not exist, so gating the deriver on their presence meant it
    # never ran and every fresh build fell through to the thin fallback.
    try:
        _ensure_static_fonts()
    except Exception as e:                       # noqa: BLE001 - reported, not raised
        print(f"[fonts] could not derive static instances: {type(e).__name__} {e}")
    if os.path.exists(FONT_REG) and os.path.exists(FONT_BOLD):
        pdfmetrics.registerFont(TTFont(F, FONT_REG))
        pdfmetrics.registerFont(TTFont(F + "B", FONT_BOLD))
    else:
        print("!! could not build the static font instances (is fonttools installed?) "
              "-- falling back to the thin variable default, no bold")
        pdfmetrics.registerFont(TTFont(F, FONT_VAR))
        pdfmetrics.registerFont(TTFont(F + "B", FONT_VAR))
    addMapping(F, 0, 0, F)
    addMapping(F, 1, 0, F + "B")
    addMapping(F, 0, 1, F)
    addMapping(F, 1, 1, F + "B")
    base = dict(fontName=F, textColor=INK)
    return {
        "title": ParagraphStyle("title", fontSize=27, leading=36, spaceAfter=6, **base),
        "sub": ParagraphStyle("sub", fontSize=12.5, leading=19, textColor=MUTED,
                              fontName=F, spaceAfter=2),
        "part": ParagraphStyle("part", fontSize=11, leading=15, textColor=ACCENT,
                               fontName=F, spaceBefore=4, spaceAfter=2),
        "h1": ParagraphStyle("h1", fontSize=17, leading=24, spaceBefore=6,
                             spaceAfter=8, **base),
        "h2": ParagraphStyle("h2", fontSize=12.5, leading=18, spaceBefore=12,
                             spaceAfter=5, **base),
        "body": ParagraphStyle("body", fontSize=9.6, leading=15.5, spaceAfter=6.5,
                               alignment=TA_JUSTIFY, **base),
        "bullet": ParagraphStyle("bullet", fontSize=9.6, leading=15, spaceAfter=3.5, bulletFontName=F,
                                 leftIndent=12, bulletIndent=2, **base),
        "note": ParagraphStyle("note", fontSize=8.2, leading=12.5, spaceAfter=5,
                               fontName=F, textColor=MUTED),
        "box": ParagraphStyle("box", fontSize=9.6, leading=15, fontName=F,
                              textColor=INK),
        "big": ParagraphStyle("big", fontSize=26, leading=30, fontName=F,
                              textColor=INK, alignment=TA_CENTER),
        "biglab": ParagraphStyle("biglab", fontSize=7.8, leading=11, fontName=F,
                                 textColor=MUTED, alignment=TA_CENTER),
        "cell": ParagraphStyle("cell", fontSize=8.2, leading=11.5, fontName=F,
                               textColor=INK),
        "mono": ParagraphStyle("mono", fontSize=7, leading=10.5, fontName=F,
                               textColor=MUTED),
    }


S = None


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items, style="bullet"):
    return [Paragraph(t, S[style], bulletText="•") for t in items]


def tbl(rows, widths, right=(), size=8.2, wrap=()):
    if sum(widths) > FRAME_W + 0.5:
        raise ValueError(f"table {sum(widths)/mm:.1f}mm > frame {FRAME_W/mm:.1f}mm")
    body = []
    for r_i, r in enumerate(rows):
        row = []
        for c_i, c in enumerate(r):
            if c_i in wrap and r_i > 0 and isinstance(c, str):
                row.append(Paragraph(c, S["cell"]))
            else:
                row.append(c)
        body.append(row)
    t = Table(body, colWidths=widths, hAlign="LEFT", repeatRows=1)
    cmds = [
        ("FONT", (0, 0), (-1, -1), F, size),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.35, RULE),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, INK),
    ]
    for c in right:
        cmds.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(cmds))
    return t


def callout(text, title=None):
    inner = []
    if title:
        inner.append(Paragraph(f"<b>{title}</b>", S["box"]))
        inner.append(Spacer(1, 3))
    inner.append(Paragraph(text, S["box"]))
    t = Table([[inner]], colWidths=[FRAME_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1efe7")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 7)])


def tiles(items):
    w = FRAME_W / len(items)
    row1 = [Paragraph(v, S["big"]) for v, _ in items]
    row2 = [Paragraph(l, S["biglab"]) for _, l in items]
    t = Table([row1, row2], colWidths=[w] * len(items))
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, INK),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def fig(drawing, caption):
    return KeepTogether([Spacer(1, 4), drawing, Paragraph(caption, S["note"]), Spacer(1, 4)])


# ------------------------------------------------------------------ charts
def _s(x, y, text, size=7.2, color=INK, anchor="start"):
    return String(x, y, text, fontName=F, fontSize=size, fillColor=color, textAnchor=anchor)


def hbars(rows, lo=None, hi=None, fmt=p2, label_w=150, width=None, bar_h=11, gap=5,
          color=ACCENT, ref=None, ref_label=None, show_ci=True, zero_axis=False):
    """rows: [(label, value, ci_lo_or_None, ci_hi_or_None, color_or_None)]."""
    width = width or FRAME_W
    vals = [r[1] for r in rows] + [r[2] for r in rows if r[2] is not None] + \
           [r[3] for r in rows if r[3] is not None]
    if ref is not None:
        vals.append(ref)
    lo = min(0, min(vals)) if lo is None else lo
    hi = max(vals) * 1.08 if hi is None else hi
    plot_w = width - label_w - 48
    top_pad = 14 if ref_label else 4
    H = top_pad + len(rows) * (bar_h + gap) + 14
    d = Drawing(width, H)

    def X(v):
        return label_w + (v - lo) / (hi - lo) * plot_w

    y = H - top_pad - bar_h
    x0 = X(0) if lo < 0 else X(lo)
    for lab, v, cl, ch, col in rows:
        d.add(_s(label_w - 6, y + 2.5, lab, anchor="end"))
        xa, xb = sorted((x0, X(v)))
        d.add(Rect(xa, y, max(0.6, xb - xa), bar_h, fillColor=col or color, strokeColor=None))
        if show_ci and cl is not None and ch is not None:
            d.add(Line(X(cl), y + bar_h / 2, X(ch), y + bar_h / 2, strokeColor=INK, strokeWidth=0.9))
            d.add(Line(X(cl), y + 2, X(cl), y + bar_h - 2, strokeColor=INK, strokeWidth=0.9))
            d.add(Line(X(ch), y + 2, X(ch), y + bar_h - 2, strokeColor=INK, strokeWidth=0.9))
        tx = max(X(v), X(ch) if (show_ci and ch is not None) else X(v))
        if v < 0 and zero_axis:
            lx = min(xa, X(cl) if (show_ci and cl is not None) else xa)
            d.add(_s(lx - 3, y + 2.5, fmt(v), anchor="end"))
        else:
            d.add(_s(tx + 3, y + 2.5, fmt(v)))
        y -= bar_h + gap
    d.add(Line(x0, 10, x0, H - top_pad + 2, strokeColor=MUTED, strokeWidth=0.5))
    if ref is not None:
        d.add(Line(X(ref), 10, X(ref), H - 4, strokeColor=ACCENT2, strokeWidth=0.9,
                   strokeDashArray=[3, 2]))
        if ref_label:
            d.add(_s(X(ref) + 2, H - 10, ref_label, size=6.8, color=ACCENT2))
    d.add(_s(label_w, 0, fmt(lo), size=6.4, color=MUTED))
    d.add(_s(label_w + plot_w, 0, fmt(hi), size=6.4, color=MUTED, anchor="end"))
    return d


def histogram(h_gross, h_net, med_g, med_n, width=None, height=150,
              label_g="gross median {:.2f}%", label_n="net median {:.2f}%"):
    """The two median labels are parameters because this chart is shared.

    The Chinese edition imports this helper, so hard-coded English put "gross
    median 2.55%" inside an otherwise Chinese figure. Templates rather than
    finished strings, so the number stays derived in both editions.
    """
    width = width or FRAME_W
    lo = min(h_net[0]["x0"], h_gross[0]["x0"])
    hi = max(h_net[-1]["x1"], h_gross[-1]["x1"])
    ymax = max(max(b["n"] for b in h_gross), max(b["n"] for b in h_net)) * 1.1
    L, B, W, Hh = 36, 18, width - 50, height - 30
    d = Drawing(width, height)

    def X(v):
        return L + (v - lo) / (hi - lo) * W

    def Y(n):
        return B + n / ymax * Hh

    for b in h_gross:
        d.add(Rect(X(b["x0"]) + 0.4, B, X(b["x1"]) - X(b["x0"]) - 0.8, Y(b["n"]) - B,
                   fillColor=SOFT, strokeColor=ACCENT, strokeWidth=0.4))
    pts = []
    for b in h_net:
        pts += [X(b["x0"]), Y(b["n"]), X(b["x1"]), Y(b["n"])]
    d.add(PolyLine(pts, strokeColor=ACCENT2, strokeWidth=1.2))
    for v, c, lab in ((med_g, ACCENT, label_g.format(med_g)),
                      (med_n, ACCENT2, label_n.format(med_n))):
        d.add(Line(X(v), B, X(v), B + Hh, strokeColor=c, strokeWidth=1, strokeDashArray=[3, 2]))
        d.add(_s(X(v) + 3, B + Hh - (8 if c is ACCENT else 18), lab, size=6.8, color=c))
    d.add(Line(L, B, L + W, B, strokeColor=MUTED, strokeWidth=0.5))
    t = math.ceil(lo)
    while t <= hi:
        d.add(_s(X(t), 6, f"{t:.0f}%", size=6.4, color=MUTED, anchor="middle"))
        t += 1
    d.add(_s(4, B + Hh, f"{int(ymax/1.1):,}", size=6.2, color=MUTED))
    d.add(_s(4, B, "0", size=6.2, color=MUTED))
    return d


def lines(series, labels, colors_, width=None, height=160, ymax=None, events=()):
    width = width or FRAME_W
    L, B, W, Hh = 44, 22, width - 60, height - 34
    n = len(labels)
    ymax = ymax or max(max(s) for s in series) * 1.1
    d = Drawing(width, height)

    def X(i):
        return L + i / (n - 1) * W

    def Y(v):
        return B + v / ymax * Hh

    for k, (q, lab) in enumerate(events):
        if q in labels:
            i = labels.index(q)
            d.add(Line(X(i), B, X(i), B + Hh, strokeColor=RULE, strokeWidth=0.8,
                       strokeDashArray=[2, 2]))
            d.add(_s(X(i) + 2, B + Hh - 2 - 9 * k, lab, size=6.2, color=MUTED))
    for s, c in zip(series, colors_):
        d.add(PolyLine([v for i, y in enumerate(s) for v in (X(i), Y(y))],
                       strokeColor=c, strokeWidth=1.4))
    for i, lab in enumerate(labels):
        d.add(_s(X(i), 8, lab, size=6.2, color=MUTED, anchor="middle"))
    for f in (0, 0.5, 1):
        d.add(_s(L - 4, Y(ymax / 1.1 * f) - 2, f"{ymax/1.1*f:,.0f}", size=6.2,
                 color=MUTED, anchor="end"))
    d.add(Line(L, B, L + W, B, strokeColor=MUTED, strokeWidth=0.5))
    return d


def legend(items, width=None):
    width = width or FRAME_W
    d = Drawing(width, 12)
    x = 0
    for lab, c in items:
        d.add(Rect(x, 3, 9, 6, fillColor=c, strokeColor=None))
        d.add(_s(x + 12, 2.5, lab, size=7))
        x += 24 + len(lab) * 4.4
    return d


# ------------------------------------------------------------------ page chrome
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont(F, 7.2)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(20 * mm, 12 * mm,
                          f"實價收益 · the visible range of Taiwan's rental yield · paper {PAPER_VERSION}")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"{doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
    canvas.restoreState()


# ------------------------------------------------------------------ the report
def build(D):
    h = D["headline"]
    meta = D["meta"]
    prov = meta["provenance"]
    wf = D["coverage_waterfall"]
    cov = {c["type"]: c for c in D["coverage"]}
    age = D["age"]
    ps = D["post_strat"]
    pid = D["partial_id"]
    rungs = {r["key"]: r for r in pid["rungs"]}
    lad = D["ladder"]
    fm = D["filter_marginals"]
    mm_ = D["marginal_mechanism"]
    boot = D["bootstrap"]
    rz_meta = D.get("resemblance") or {}
    rz = rz_meta.get("vars") or {}
    disp = D["dispersion"]
    conc = D["concentration"]
    rb = D["rent_bias"]
    dh = D["dead_hypothesis"]
    wr = D["walkup_resolution"]
    wb = D["within_building"]
    pre = D["presale"]
    pa = D["parking_audit"]
    pk = D["parking"]
    mex = D["mgmt_exposure"]
    mfl = D["mgmt_flag"]
    vp = D["vacancy_prior"]
    vb = D["vacancy_breakeven"]
    moi = D["moi"]
    vol = D["volume"]
    auc = D["auction"]
    inc = D["income"]
    bm = {b["key"]: b for b in D["benchmarks"]}
    rep = D["repairs_spec"]
    idx = D["index_test"]
    B = D["buildings"]
    treat = {t["case"]: t for t in pa["treatments"]}
    area_only = treat.get("area_only", {})

    story = []
    A = story.append

    # ------------------------------------------------------------ cover
    A(Spacer(1, 38 * mm))
    A(P("What 9,843 Taiwanese buildings say about rental yield, and about how little "
        "of the market any yield can describe", "title"))
    A(Spacer(1, 4))
    # This used to read "written on the day it was parked", which stopped being a
    # description of the document the first time it was revised.
    A(P(f"A measurement of Taiwan's rental yield from 實價登錄 sales and leases, "
        f"{meta['seasons'][0]}–{meta['seasons'][1]}. First written on 2026-09-29, the day the "
        "project was parked; revised since, and §16 records how.", "sub"))
    A(Spacer(1, 16 * mm))
    A(tiles([(p2(h["yield"]), "median gross yield<br/>(building level)"),
             (p2(h["net"]), "median net yield<br/>(after four stated costs)"),
             (p2(h["coverage_pct"]), f"of {n0(h['universe_buildings'])} buildings<br/>"
                                     "could be priced at all"),
             (n0(h["buildings"]), f"matched buildings<br/>({n0(h['pairs'])} sale–lease pairs)")]))
    A(Spacer(1, 22 * mm))
    A(tbl([["", ""],
           # The PAPER's own version, distinct from the payload's: the payload
           # is the data this build read, this is the citable edition of the
           # write-up. Frozen for SSRN; bump on any revision that changes a
           # claim, and say what changed.
           ["Paper version", f"{PAPER_VERSION}  ·  {PAPER_DATE}"],
           ["Payload version", f"v{prov['version']}  ·  built {prov['built']}"],
           ["Data window", f"{meta['seasons'][0]} → {meta['seasons'][1]}  ({meta['n_seasons']} quarters, "
                           "Q4 2023 → Q2 2026)"],
           ["Source snapshot SHA-256", prov["source"]["sha256"][:32] + "…"],
           # A reader who wants the code needs the public repository, not the
           # parked branch this was written on -- section 18's restart table
           # still names that branch and its tag, which is where it belongs.
           ["Code", "github.com/Stanley0210/taiwan-rental-yield"],
           ["First written", "2026-09-29"]],
          [45 * mm, FRAME_W - 45 * mm], size=7.8))
    A(Spacer(1, 6))
    A(P("Every figure in this report is read from <i>housing_data.json</i> at build time. "
        "Where the report describes numbers that were published earlier and later "
        "withdrawn, it says so; those figures come from the project handoff, not the payload.",
        "note"))
    A(PageBreak())

    # ------------------------------------------------------------ contents
    A(P("Contents", "h1"))
    toc = [
        ("", "Executive summary"),
        ("I", "The project — what it was, why it existed, how it worked"),
        ("", "1  Origin and constraints · 2  The data · 3  The method"),
        ("II", "The findings"),
        ("", "4  The headline yield · 5  Coverage: the central finding · "
             "6  Bounding the 94% nobody can see · 7  What each cleaning step is worth · "
             "8  Geography · 9  Walk-ups vs towers · 10  Inside one building · "
             "11  Transit (withdrawn) · 12  Pre-sale · 13  Parking · 14  The cost model · "
             "15  Market context"),
        ("III", "Reliability"),
        ("", "16  Corrections register · 17  Bug classes and working rules · "
             "18  Open items and how to restart · 19  References"),
        ("", "Appendix A — provenance · Appendix B — glossary"),
    ]
    for a, b in toc:
        A(P(f"<b>{a}</b>  {b}" if a else b, "body" if not a else "h2"))
    A(PageBreak())

    # ------------------------------------------------------------ executive summary
    A(P("Executive summary", "h1"))
    law_pp, ours_pp = wf["law_pp"], wf["ours_pp"]
    A(P("<b>The one-sentence version.</b> Take a real sale from Taiwan's 實價登錄 registry, find a real "
        "lease <i>in the same building</i> within four quarters, and the rental yield falls out with no "
        f"modelling at all. Done nationally, that gives a median gross yield of <b>{p2(h['yield'])}</b> "
        f"(95% CI {boot['overall']['lo']:.2f}–{boot['overall']['hi']:.2f}) and a net yield of "
        f"<b>{p2(h['net'])}</b> (95% CI {boot['overall_net']['lo']:.2f}–{boot['overall_net']['hi']:.2f}) "
        f"— below the {bm['mortgage']['rate']:.3f}% the five big banks charge on "
        "a new mortgage. But the more important number is the denominator: those medians describe "
        f"<b>{n0(h['buildings'])}</b> of <b>{n0(h['universe_buildings'])}</b> buildings that sold in the "
        f"window — <b>{p2(h['coverage_pct'])}</b>, about one in {round(100/h['coverage_pct'])}."))
    A(P("The project's thesis was that <b>the denominator is the point</b>: every "
        "transaction-based yield published about Taiwan describes a small, young, tower-heavy, "
        "investor-owned slice of the market, and nobody says how small. This project measured it."))

    A(P("Ten findings that survived every audit", "h2"))
    tw, mr, wu = cov["住宅大樓"], cov["華廈"], cov["公寓"]
    A(KeepTogether(bullets([
        f"<b>Coverage is structural.</b> {p2(h['coverage_pct'])} of buildings with a sale can be priced. "
        f"{law_pp:.1f} percentage points are lost because no lease exists in the registry at all; the "
        f"project's own quality filters cost {ours_pp:.1f}pp. Even with every filter removed, the "
        f"ceiling is {p2(h['coverage_ceiling_pct'])}.",
        f"<b>Towers are over-represented roughly sevenfold relative to walk-ups.</b> Match rates: towers "
        f"(住宅大樓) {p2(tw['match_rate'])}, mid-rises (華廈) {p2(mr['match_rate'])}, walk-ups (公寓) "
        f"{p2(wu['match_rate'])}. Towers are {tw['share_all']:.1f}% of buildings that sold but "
        f"{tw['share_matched']:.1f}% of those that can be priced.",
        f"<b>The priced slice is newer and dearer.</b> Matched buildings were completed around 民國"
        f"{age['matched_built']:.0f} against {age['unmatched_built']:.0f} for the rest, and cost "
        f"{age['ppp_diff_pct']:.1f}% more per 坪. And 42.7% of Taiwan's dwellings (1–3 storey 透天) "
        "are outside the analysis by construction.",
        f"<b>Re-weighting the visible slice to look like the market raises the yield</b> from "
        f"{p2(ps['visible_gross'])} to {p2(ps['by_both']['gross'])} ({pp(ps['shift_pp'])}). The bias is "
        "published, not silently corrected.",
        f"<b>Under stated assumptions, the yield of all {n0(pid['scope']['n'])} buildings lies in "
        f"[{rungs['type_price']['gross']['lo']:.2f}%, {rungs['type_price']['gross']['hi']:.2f}%].</b> "
        "With no assumptions it is the entire quality band, and no amount of better cleaning can "
        "change that, because a median can only be bounded once more than half the population is seen. "
        f"<b>That assumption is now tested, and it only half holds:</b> the cells absorb "
        f"{rz['built']['absorbed_pct']:.0f}% of the age gap between matched and unmatched buildings "
        f"and make the size gap <i>worse</i> (§6). The interval is a stated-assumption interval, not "
        "a validated one.",
        f"<b>Social housing distorts raw registry rents.</b> {rb['social_share_pct']:.1f}% of whole-unit "
        f"leases are subsidised 社會住宅 lets, renting {abs(rb['gap_pct']):.1f}% below market per 坪. "
        "Anyone computing a yield off raw 實價登錄 rents is mostly measuring the subsidy.",
        f"<b>Yield differences between districts are mostly price.</b> The correlation between a "
        f"district's price per 坪 and its yield is {corr_price_yield(D['districts']):.3f}; rents vary "
        "far less than prices do.",
        f"<b>Inside one building, rent barely rises with floor (+{wb['floor']['pct_per_floor']:.2f}% "
        f"per floor) while price rises five times faster (+{wb['floor_sale']['pct_per_floor']:.2f}%).</b> "
        f"Furnished units rent {wb['furnished']['pct']:.1f}% higher than unfurnished ones in the same "
        "building. These are within-building comparisons, so building quality is held constant.",
        f"<b>Pre-sale (預售屋) is only {pre['curve'][0]['gap_pct']:.1f}% dearer</b> (CI "
        f"{pre['curve'][0]['ci_lo']:.1f}–{pre['curve'][0]['ci_hi']:.1f}) than genuinely completed new "
        "homes sold in the same contract quarter. That is not the widely quoted ~30%. The 30% came from "
        "a comparison group that was 90% pre-sale contracts itself.",
        f"<b>Un-itemised parking is not free.</b> Leases with a space whose rent was never itemised pay the "
        f"same total rent per m² as itemised ones (ratio {pa['verdict']['ratio']:.3f}, CI "
        f"{pa['verdict']['lo']:.3f}–{pa['verdict']['hi']:.3f}). Imputing the space rent moved the "
        f"headline from {p2(area_only.get('gross', 2.68))} to {p2(h['yield'])}.",
    ])))

    A(P("What did not survive", "h2"))
    A(P("The project published several things that later checks withdrew, and it keeps the "
        "withdrawals on the record:"))
    A(KeepTogether(bullets([
        "<b>The founding hypothesis — walk-ups out-yield towers — is closed as unanswerable.</b> The gap "
        f"exists in the matched data ({pp(wr['precision']['gross_gap'],3)}, CI "
        f"{wr['precision']['lo']:.3f}–{wr['precision']['hi']:.3f}), but matched towers are "
        f"{abs(wr['representativeness'][1]['medians']['area_ping']['diff_pct']):.0f}% smaller than "
        "towers that sold and could not be matched. Two differently skewed samples cannot settle a "
        "population question. The proposed mechanism (management fees) was falsified outright.",
        "<b>Distance to the MRT</b> was published, retracted, restored and finally withdrawn. It turned "
        "on whether 輕軌 (light rail) counts as a station, and Kaohsiung showed no gradient.",
        "<b>The \"~30% pre-sale premium\"</b> was built on a contaminated comparison group (see §12).",
        "<b>\"One building in 1,086\"</b> divided buildings by registered 建號 (≈ units). That is a unit "
        "error, and it has been withdrawn.",
        "<b>A price index</b> made the yield-vs-gap slope worse, not better, so it is switched off.",
    ])))
    A(callout(
        f"A landlord who bought a typical priceable Taiwanese flat in this window earns about "
        f"{h['yield']:.1f}% a year in rent before costs and about {h['net']:.1f}% after them, which is "
        f"barely more than a one-year bank deposit ({bm['deposit_1y']['rate']:.2f}%) and less than "
        f"the {bm['mortgage']['rate']:.2f}% mortgage rate. But \"typical\" here means a newer flat in a tower, because that is the only "
        f"kind the public data can price. For about 15 in every 16 buildings the data simply cannot "
        f"say, and this report shows exactly where each of those buildings was lost.",
        "In plain English"))
    A(PageBreak())

    # ================================================================ PART I
    A(P("Part I · The project", "part"))
    A(P("1  Origin and constraints", "h1"))
    A(P("Quants.tw began as a Taiwan-stock chip-flow product. On 2026-08-30 the same repository was "
        "restarted as a <b>Taiwan rental-yield analysis tool</b>: same infrastructure, different "
        "subject. The stock product was frozen at the time, so no live users were affected. The first "
        "version covered Taipei and New Taipei (2,549 matched buildings, gross 2.43%). The scope "
        "constraint was lifted on 2026-08-31 and everything since covers all 22 counties. Over the "
        "following four weeks the payload went from v1.0 to v2.8, the test suite from ~780 to 919, "
        "and the method was audited by independent agents in ten dimensions."))
    A(P("The engine is, in effect, underwriting: pull a real sale, pair it with a real lease in the "
        "same building, and run the net-operating-income arithmetic. Three standing rules came from "
        "Stanley and never changed:"))
    A(KeepTogether(bullets([
        "<b>This was the second start.</b> A third pivot would itself be the signal, so the rule was to "
        "ship badly and iterate, not redesign.",
        "<b>Stay in the data-and-analysis lane.</b> The site analyses housing data. It does not "
        "opine on housing policy.",
        "<b>Yields come from matched pairs, never district averages.</b> Scope went national; this "
        "rule did not move.",
    ])))
    A(P("<b>The legal line.</b> 不動產估價師法 §14 reserves 估價 (valuation) for licensed appraisers, "
        "with fines of NT$30k–150k. The site therefore says \"transactions in this building cleared "
        "at X% on these assumptions\" and never \"this property is worth NT$Y\" or \"this is a good "
        "buy\". Every building panel ends with a line saying the figure is a registered transaction "
        "price, not a valuation."))
    A(P("<b>Status when parked (2026-09-29).</b> The code lives on branch <i>feat/housing</i> and tag "
        "<i>housing-parked-2026-09-29</i> on the <i>quants</i> remote. The quants.tw domain has returned "
        "Railway's \"Application not found\" since late August, because the Railway account that hosted "
        "it lapsed; the code was never the cause. No reader ever saw the housing site live. The stock "
        "site was restored on <i>main</i> the same day this report was written."))

    A(CondPageBreak(70 * mm))
    A(P("2  The data", "h1"))
    A(P("Primary source: 內政部 不動產成交案件實際資訊資料供應系統 (實價登錄). It is free, needs no key, "
        f"and is published under {meta['licence']}. The combined season zip carries sales (a), pre-sales "
        "(b) and leases (c) for every county."))
    A(tbl([["", "raw rows", "after cleaning", "kept"],
           ["Sales (買賣)", n0(meta["raw_sales"]), n0(meta["clean_sales"]),
            p2(meta["clean_sales"] / meta["raw_sales"] * 100)],
           ["Leases (租賃)", n0(meta["raw_rents"]), n0(meta["clean_rents"]),
            p2(meta["clean_rents"] / meta["raw_rents"] * 100)],
           ["Pre-sales (預售屋)", "—", n0(pre["dwellings"]) + " dwellings", f"{n0(pre['projects'])} 建案"]],
          [55 * mm, 35 * mm, 45 * mm, 35 * mm], right=(1, 2, 3)))
    A(Spacer(1, 6))
    A(P("<b>Why the window starts at 112S4 (Q4 2023).</b> Six lease columns first appear that quarter: "
        "出租型態, 有無管理員, 租賃期間, 有無電梯, 附屬設備 and 租賃住宅服務. Every quality filter depends on "
        "them. Using older seasons would silently blend subsidised social housing and room-shares into "
        "the early period and manufacture a fake time trend. The usable window is therefore 11 "
        "quarters, which is too short for any claim about cycles."))
    A(P("<b>The filters</b> (each can be switched off, so the honesty ladder in §7 walks the same code "
        "path):"))
    A(KeepTogether(bullets([
        "Residential types only: 住宅大樓 (11+ floors, lift), 華廈 (≤10 floors, lift), 公寓 (≤5 floors, "
        "no lift). 1–3 storey 透天 are excluded by construction.",
        "Social housing (社會住宅包租轉租 / 代管) excluded, because those rents are subsidised.",
        "Whole-unit lets only (整棟(戶)出租, 獨立套房). This drops room-shares, floor lets and blank "
        "types, whose area field is not comparable to a whole-unit sale.",
        "Related-party sales (親友 / 親屬 / 關係人) excluded, because they are not market prices.",
        "Parking subtracted from both sides; un-itemised space rent imputed (§13).",
        "Sale and lease within ±4 quarters; yields outside 0.3–12% rejected as filing errors.",
    ])))
    A(P("<b>Addresses.</b> A building key is derived from the 門牌 (house number) by a normaliser tested "
        f"on 150 labelled pairs. Only {meta['addr']['no_key_pct']}% of records produce no key. Keys were "
        "corrected in v2.8 for two assumptions the registry falsifies: the variant character 巿 (U+5DFF) "
        "for 市, and unit designators containing 號. Coordinates come from per-county open 門牌 point "
        f"files, because Taiwan has no national open geocoder: {n0(meta['geo']['matched'])} of "
        f"{n0(meta['geo']['total'])} buildings ({meta['geo']['rate']:.2f}%) were placed, with 100% "
        "district agreement. Coordinates feed only the map, never a yield."))
    A(P("<b>Context sources</b>, each hashed in the payload: 內政部 statistics (stock by floor and age, "
        "法拍 volumes, low-use housing, price index, unsold new homes), 中央銀行 (deposit, rediscount and "
        "mortgage rates), 主計總處 household income, 台灣金服 金拍 auction results, and OpenStreetMap "
        "(basemap and 264 metro/light-rail stations)."))

    A(CondPageBreak(70 * mm))
    A(P("3  The method", "h1"))
    A(P("<b>The unit is the building, not the pair.</b> Pairs concentrate heavily in mega-towers: the "
        f"median building has {conc['median_per_building']} pairs, the largest has "
        f"{n0(conc['max_per_building'])}, and the top ten buildings hold {conc['top10_share']:.1f}% of all "
        f"pairs. A pair-level median ({p2(h['pair_level_yield'])}) overweights exactly the buildings that "
        f"are least typical. Every headline figure is a median of per-building medians."))
    A(P(f"Matching a sale to a lease on the same property is not a new idea. {cite_t('bracke2015')} "
        "does it for Central London from a letting agency's own book: 1,922 properties both sold and "
        "let within six months. What differs here is the source and what it lets you say — a public "
        "national registry rather than one firm's clients, and a registry whose non-coverage is "
        "itself measurable, which an agency's book cannot be."))
    A(P("<b>Intervals.</b> All confidence intervals come from one two-stage bootstrap: resample "
        "buildings, then pairs within each building. Pairs inside a building are not independent "
        "draws, and it is the number of buildings, not the number of pairs, that sets the precision "
        f"{cite('cameron2008')} — which is also why districts carry a floor of {meta['min_district_n']} "
        "buildings before they are reported at all. The browser recomputes intervals with a seeded RNG "
        "so they do not move between page loads."))
    A(P("<b>Net yield.</b> Four costs are deducted, each a live slider on the site. The JavaScript "
        "implementation is a twin of the Python one and is tested to agree on every building."))
    rows = [["Cost", "Default", "Range", "Source"]]
    for a in D["assumptions"]:
        rows.append([a["en"].split(" (")[0], f"{a['default']:g} {a['unit']}",
                     f"{a['min']:g}–{a['max']:g}", a["src_en"]])
    A(tbl(rows, [26 * mm, 30 * mm, 17 * mm, FRAME_W - 73 * mm], wrap=(3,), size=7.8))
    A(Spacer(1, 6))
    A(P("<b>Reproducibility.</b> The payload carries a per-season SHA-256 manifest of the source zips, "
        "hashes of every reference CSV and the 金拍 cache, the build commit and a version number. "
        "<i>bin/rebuild-housing.sh</i> rebuilds it and diffs it structurally against the committed hash."))
    A(PageBreak())

    # ================================================================ PART II
    A(P("Part II · The findings", "part"))
    A(P("4  The headline yield", "h1"))
    A(tiles([(p2(h["yield"]), f"gross, 95% CI {boot['overall']['lo']:.2f}–{boot['overall']['hi']:.2f}"),
             (p2(h["net"]), "net of tax, management, vacancy, repairs<br/>"
                            f"95% CI {boot['overall_net']['lo']:.2f}–{boot['overall_net']['hi']:.2f}"),
             (p2(h["pair_level_yield"]), "the same data, pair-weighted<br/>(the wrong unit)")]))
    A(Spacer(1, 6))
    A(fig(histogram(D["histogram"], D["histogram_net"], h["yield"], h["net"]),
          "Figure 4.1 — Distribution of building-level yields. Bars: gross; line: net. The end bars are "
          "pile-ups of everything beyond them (the histogram clips), not counts of their own interval. "
          f"The horizontal distance between the two medians ({h['yield']-h['net']:.2f}pp) is the "
          "cost model."))
    hn = D["histogram_net"]
    below1 = sum(b["n"] for b in hn if b["x1"] <= 1.0)
    neg = sum(b["n"] for b in hn if b["x1"] <= 0)
    A(P(f"{below1:,} buildings ({below1/h['buildings']*100:.1f}%) net less than 1% a year, and {neg} "
        "nets less than zero. Against the reference rates published beside it:"))
    A(tbl([["Reference", "Rate", "Period", "What it is"],
           ["Net yield, this site", p2(h["net"]), "112S4–115S2", "median across matched buildings"],
           ["1-yr time deposit", p2(bm["deposit_1y"]["rate"]), bm["deposit_1y"]["period_en"],
            "five big banks, identical at all five"],
           ["Rediscount rate", p2(bm["rediscount"]["rate"]), bm["rediscount"]["period_en"],
            "policy rate, not investable"],
           ["New mortgage (CBC)", f"{bm['mortgage']['rate']:.3f}%", bm["mortgage"]["period_en"],
            "five big banks, new house-purchase loans — "
            + ("transcribed, not derived: the CBC publishes no CSV for this series"
               if bm["mortgage"].get("typed") else "read from a pinned source file")],
           ["New mortgage (MOI)", p2(moi["mortgage"]["rate"]), moi["mortgage"]["period"],
            "all new loans nationally"]],
          [38 * mm, 18 * mm, 30 * mm, FRAME_W - 86 * mm], right=(1,), wrap=(3,)))
    A(P("A buyer financing with a mortgage in this window pays more in interest than the median "
        "priceable flat returns in net rent. The yield is below the cost of the money that bought it. "
        f"That is an arithmetic statement, not a verdict on whether the price is wrong: under the "
        f"user-cost identity {cite('himmelberg2005')} a low rent-price ratio can be a rational "
        "response to low real rates and expected appreciation, and nothing measured here settles "
        "which it is.", "note"))

    zr = D["size_robust"]
    zrat = zr["ratio"]
    A(CondPageBreak(85 * mm))        # heading, paragraph and table travel together
    A(P("The unit-size objection", "h2"))
    A(P("A pair here is a sale and a lease in the same <i>building</i>, not the same unit, and the "
        "headline divides total rent by total price. Nothing makes the two units the same size: a "
        "leased studio set against a sold three-bedroom reads as a low yield, and the reverse as a "
        "high one. No edition before v1.3 said so, and it is the first thing an appraiser would ask. "
        f"{cite_t('bracke2015')} avoids the problem by matching the same property. This registry "
        "carries no unit identifier, so the same building is as close as it gets — but what the "
        "mismatch is worth can be measured, three ways:"))
    A(tbl([["Reading", "median gross", "95% CI", "buildings", "pairs"],
           ["Headline — total rent ÷ total price", p2(zr["headline"]["gross"]),
            f"{boot['overall']['lo']:.2f}–{boot['overall']['hi']:.2f}",
            n0(zr["headline"]["buildings"]), n0(zr["headline"]["pairs"])],
           ["Per 坪 — rent per 坪 ÷ price per 坪, pair by pair", p2(zr["per_ping"]["gross"]),
            f"{zr['per_ping']['lo']:.2f}–{zr['per_ping']['hi']:.2f}",
            n0(zr["per_ping"]["buildings"]), n0(zr["per_ping"]["pairs"])],
           [f"Size-matched — only pairs whose areas are within {zr['band'][0]:g}–{zr['band'][1]:g}×",
            p2(zr["size_matched"]["gross"]),
            f"{zr['size_matched']['lo']:.2f}–{zr['size_matched']['hi']:.2f}",
            n0(zr["size_matched"]["buildings"]), n0(zr["size_matched"]["pairs"])]],
          [80 * mm, 24 * mm, 24 * mm, 20 * mm, FRAME_W - 148 * mm], right=(1, 2, 3, 4),
          wrap=(0,), size=7.8))
    A(Spacer(1, 5))
    A(P(f"<b>Nationally the headline holds.</b> The size-matched reading is the closest this "
        "registry gets to a same-unit design, and it assumes nothing about how rent scales with "
        f"floor area. It returns {zr['size_matched']['gross']:.2f}% on "
        f"{zr['size_matched']['kept_buildings_pct']:.0f}% of the buildings, a shift of "
        f"{pp(zr['size_matched']['shift_pp'])}; per 坪 moves it by {pp(zr['per_ping']['shift_pp'])}. "
        "The reason is symmetry, not luck. Across pairs the median ratio of sold to leased area is "
        f"{zrat['pair']['median']:.2f}; {zrat['pairs_sold_bigger_pct']:.0f}% of pairs have the sold "
        f"unit larger than the band allows and {zrat['pairs_leased_bigger_pct']:.0f}% the leased one, "
        "so the mismatches cancel in a median."))
    A(P("<b>Locally it holds less well</b>, and the comparison below is where that matters. Where a "
        "city's mismatches are not symmetric the three readings separate, so every city figure in "
        "the next table is given all three ways and each gap is quoted as a range.", "note"))

    A(P("Against other published estimates", "h2"))
    A(P(f"Taiwan already has a rental-yield figure in circulation, and it is worth asking where it "
        f"comes from. {cite_t('chang2018')} give a gross rent multiplier of 64 for Taiwan and a yield "
        "of 1.57%; the stated source of that table is Global Property Guide, a commercial listings "
        f"aggregator. {cite_t('gpg2026')} now publishes {p2(GPG_NATIONAL)} nationally, computed as "
        "median asking rent × 12 ÷ median list price over apartments in five cities. So the "
        "peer-reviewed Taiwan number and the consumer-facing one are the same number, and neither is "
        "built on transaction data. Two differences from the measurement in this report follow. An "
        "asking price is not a sale price. And a ratio of two medians taken over different properties "
        "is not a median of per-property ratios — they are different statistics, and only the second "
        "one is a yield any individual building could have earned."))
    A(CondPageBreak(62 * mm))
    A(P("The comparison city by city, which has not been made before:"))
    gp = sorted([c for c in D["counties"] if c["city"] in GPG_CITIES],
                key=lambda c: -c["buildings"])
    zc = {r["city"]: r for r in zr["counties"]}

    def gaps(city):
        """The gap against the listings figure under each reading, smallest first."""
        g, r = GPG_CITIES[city], zc[city]
        return sorted([r["headline"] - g, r["per_ping"] - g, r["size_matched"] - g])

    crows = [["City", "headline", "95% CI", "per 坪", "size-matched", "buildings",
              f"GPG ({GPG_UPDATED})", "gap, three readings"]]
    for c in gp:
        r, ci = zc[c["city"]], boot["county"].get(c["county"])
        lo_g, _mid, hi_g = gaps(c["city"])
        crows.append([c["city"], p2(r["headline"]),
                      f"{ci['lo']:.2f}–{ci['hi']:.2f}" if ci else "—",
                      p2(r["per_ping"]), p2(r["size_matched"]), n0(c["buildings"]),
                      p2(GPG_CITIES[c["city"]]), f"{lo_g:+.2f} to {hi_g:+.2f}pp"])
    A(tbl(crows, [17 * mm, 17 * mm, 22 * mm, 16 * mm, 22 * mm, 18 * mm, 27 * mm, FRAME_W - 139 * mm],
          right=(1, 2, 3, 4, 5, 6, 7), size=7.4))
    A(Spacer(1, 5))
    worst = max(gp, key=lambda c: gaps(c["city"])[0])
    best = min(gp, key=lambda c: gaps(c["city"])[2])
    wl, _wm, wh = gaps(worst["city"])
    bl, _bm, bh = gaps(best["city"])
    wrow, wg = zc[worst["city"]], GPG_CITIES[worst["city"]]
    A(P(f"The registered measure is higher in all five under all three readings: by {bl:+.2f} to "
        f"{bh:+.2f}pp in {best['city']}, and by {wl:+.2f} to {wh:+.2f}pp in {worst['city']}. The two "
        "sources agree closely in the north and diverge going south, and that ordering does not "
        "depend on the reading. <b>The size of the southern gap does.</b> v1.1 and v1.2 quoted "
        f"{worst['city']} at {pp(wrow['headline'] - wg)} from the headline reading alone. That is the "
        f"top of the range and not the middle of it: once unit size is controlled the gap is "
        f"{pp(wrow['per_ping'] - wg)} per 坪 and {pp(wrow['size_matched'] - wg)} on size-matched pairs. "
        "§16 records the correction."))
    fp = {(r["city"], r["part"]): r for r in zr["footprint"]}
    tn_p, tn_c = fp[("臺南市", "city_proper")], fp[("臺南市", "former_county")]
    kh_p, kh_c = fp[("高雄市", "city_proper")], fp[("高雄市", "former_county")]
    A(P("Earlier editions also hedged that a municipality-wide median covers \"a great deal of "
        "non-urban area\" that a listings site does not. That is checkable, because 臺南 and 高雄 each "
        "merged with their county in 2010 and the old city limits are still district boundaries. In "
        f"臺南 the pre-merger city proper yields {tn_p['headline']:.2f}% ({tn_p['per_ping']:.2f}% per "
        f"坪, {n0(tn_p['buildings'])} buildings) against {tn_c['headline']:.2f}% "
        f"({tn_c['per_ping']:.2f}%) in the former county: the wider footprint <i>lowers</i> the "
        "municipal figure, so it hides part of the gap instead of creating it. In 高雄 it runs the "
        f"other way and is small — {kh_p['headline']:.2f}% ({kh_p['per_ping']:.2f}%) in the city "
        f"proper against {kh_c['headline']:.2f}% ({kh_c['per_ping']:.2f}%). What stays unlike-for-like "
        "is the source and the window: asking prices against registered ones, and a 2026 snapshot "
        "against eleven quarters."))
    A(P(f"Taipei is the one city with three independent estimates, and they agree. "
        f"{cite_t('yang2018')} estimate a Taipei gross rent multiplier of about 50 from 591 asking "
        "rents against 實價登錄 sales for 2013–2016, which inverts to a yield near 2.0% — an "
        "arithmetic inversion of their figure, not one they state. Global Property Guide gives "
        f"{p2(GPG_CITIES['臺北市'])} for 2026. This report gives "
        f"{p2(zc['臺北市']['headline'])} ({zc['臺北市']['per_ping']:.2f}% per 坪, "
        f"{zc['臺北市']['size_matched']:.2f}% size-matched). Three methods, three windows, a "
        "spread of about a tenth of a point."))
    A(P("Set against the bounds in §6 rather than against the point estimate: the current listings "
        "figure and the 2013–2016 multiplier both fall inside the resemblance interval, and the 1.57% "
        "in circulation falls below it — though that figure describes an earlier period than this "
        "window, so it is not a contradiction so much as a reminder that a yield without a date and a "
        "denominator is not a measurement.", "note"))
    A(P(f"<b>This table is typed, not derived.</b> It is the only one in the report that is. These "
        f"figures live on other people's pages and in other people's PDFs; no payload can produce "
        f"them and no test can check them. They were read from the sources on {EXTERNAL_READ_ON} and "
        "the sources are in §19, so a reader can re-check them the way they can re-check everything "
        "else here.", "note"))

    # ------------------------------------------------------------ 5 coverage
    A(CondPageBreak(95 * mm))
    A(P("5  Coverage: the central finding", "h1"))
    A(P(f"Of {n0(wf['universe'])} buildings with a recorded residential sale in the window, "
        f"{n0(wf['final'])} can be priced. The waterfall says where every other building went, and "
        "whose fault each step is."))
    wrows = []
    for s in wf["steps"]:
        short = {"no_lease": "No lease on file (registry)", "window": "Lease >4 quarters away / off-band",
                 "parking": "Parking not itemised", "social": "Social-housing lease",
                 "rooms": "Not a whole-unit let", "related": "Related-party sale"}.get(s["key"], s["en"][:40])
        wrows.append((short, s["lost_pp"], None, None,
                      ACCENT2 if s["whose"] == "law" else ACCENT))
    A(fig(hbars(wrows, lo=0, hi=80, fmt=lambda v: f"{v:.2f}pp", label_w=165),
          f"Figure 5.1 — Percentage points of the {n0(wf['universe'])}-building universe lost at each "
          f"step. Orange: the registry itself (no lease on file), {law_pp:.1f}pp. Blue: this project's "
          f"quality filters, {ours_pp:.1f}pp combined. The law-side share of the loss is "
          f"{wf['law_share']}%."))
    A(P("\"No lease on file\" is not the same as \"unregistered lease\", and the reason is in the law "
        "rather than in the data. Only two duties to register a lease exist. A broker must register "
        f"the leases it brokers or agents {cite('law_broker')}, and a master-lease business must "
        f"register its subleases {cite('law_sublease')}, each within thirty days. A landlord and a "
        "tenant who sign with each other directly have no duty at all, so their lease never reaches "
        "the registry — and most of these buildings are owner-occupied anyway. No amount of cleaning "
        "can recover a lease that was never filed. With every one of this project's filters removed, "
        f"the ceiling is <b>{p2(wf['ceiling_pct'])}</b>."))
    A(P("Which buildings survive", "h2"))
    A(fig(hbars([("住宅大樓 tower", tw["match_rate"], None, None, ACCENT),
                 ("華廈 mid-rise", mr["match_rate"], None, None, ACCENT),
                 ("公寓 walk-up", wu["match_rate"], None, None, ACCENT)],
                lo=0, hi=14, label_w=110),
          "Figure 5.2 — Share of each building type, among those that sold, that could be matched to a "
          "lease."))
    A(tbl([["Type", "sold (棟)", "matched", "match rate", "share of sold", "share of matched",
            "gross", "net"]] +
          [[t, n0(c["all_buildings"]), n0(c["matched"]), p2(c["match_rate"]), p2(c["share_all"]),
            p2(c["share_matched"]), p2(c["yield"]), p2(c["net"])]
           for t, c in cov.items()],
          [22 * mm, 22 * mm, 19 * mm, 21 * mm, 23 * mm, 26 * mm, 18 * mm, 18 * mm],
          right=(1, 2, 3, 4, 5, 6, 7)))
    sbf = moi["stock_by_floor"]
    A(P("Against the whole housing stock", "h2"))
    A(P(f"The government's house-tax roll counts {n0(sbf['total'])} dwellings (宅). "
        f"<b>{sbf['outside_pct']}% are 1–3 storey buildings</b>, mostly 透天厝, which the residential "
        "filter excludes by definition, so no result here speaks for them. Within the 4+ storey stock "
        "the site does describe, towers are "
        f"{[t for t in sbf['by_type'] if t['type']=='住宅大樓'][0]['share_of_inside_pct']}% of dwellings but "
        f"{tw['share_matched']}% of priced buildings, and walk-ups are "
        f"{[t for t in sbf['by_type'] if t['type']=='公寓'][0]['share_of_inside_pct']}% against "
        f"{wu['share_matched']}%. The stock counts dwellings and the site counts buildings; because a "
        "tower holds many more dwellings than a walk-up, this comparison <i>understates</i> the skew. "
        "The two are set side by side and never divided."))
    sba = moi["stock_by_age"]
    agerows = []
    for r in sba["rows"]:
        lab = r["band"].replace("（含）", "").replace("年以下", "y or less").replace("年以上", "y+").replace("年", "y")
        agerows.append((lab + " · stock", r["stock_pct"], None, None, colors.HexColor("#b9b3a3")))
        agerows.append((lab + " · priced", r["ours_pct"], None, None, ACCENT))
    A(fig(hbars(agerows, lo=0, hi=26, fmt=lambda v: f"{v:.1f}%", label_w=120, bar_h=7, gap=2.5),
          f"Figure 5.3 — Age of the dwelling stock (grey, {sba['period']}, mean {sba['stock_mean_age']} "
          f"years) against the buildings this site can price (blue, median {sba['ours_median_age']:.0f} "
          "years). The priced slice is concentrated in buildings under ten years old; over-40s are "
          "nearly absent."))
    A(P("The selection effect in one table", "h2"))
    A(P(f"This is the classical selection problem {cite('heckman1979', 'manski1989')}, and housing "
        "measurement has met it before: an index built only from houses that sell twice is biased "
        f"because selling twice is not random {cite('gatzlaff1997')}. The usual repair is to model "
        "the probability of being observed and correct for it. That repair is unavailable here, and "
        "§6 explains why: being observed depends on whether a lease was filed through a licensed "
        "agency, which is an institutional fact about the registry rather than a behaviour of the "
        "building, and the registry publishes nothing that predicts it."))
    A(tbl([["", "matched", "unmatched", "difference"],
           ["Buildings", n0(age["matched_n"]), n0(age["unmatched_n"]), ""],
           ["Price per 坪 (median)", n0(age["matched_ppp"]), n0(age["unmatched_ppp"]),
            f"+{age['ppp_diff_pct']:.1f}%"],
           ["Completed (民國, median)", f"{age['matched_built']:.0f}", f"{age['unmatched_built']:.0f}",
            f"{age['matched_built']-age['unmatched_built']:+.0f} years newer"],
           ["Area (坪, median)", f"{age['matched_area']:.1f}", f"{age['unmatched_area']:.1f}",
            f"{(age['matched_area']/age['unmatched_area']-1)*100:+.1f}%"]],
          [55 * mm, 35 * mm, 35 * mm, 45 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P(f"This comparison shipped at a third of its size for two versions. It read the "
        "<i>cleaned</i> sale frame, which had already dropped the cheaper stock (un-itemised parking, "
        "related-party), so it compared against 100,800 buildings instead of all of them and printed a "
        f"2.7% price gap. On the full universe the gap is {age['ppp_diff_pct']:.1f}%. A test now pins the "
        "unmatched count to universe minus matched.", "note"))
    A(P("Re-weighting the visible slice", "h2"))
    A(P(f"Post-stratifying the matched buildings to the universe's mix moves the gross yield from "
        f"{p2(ps['visible_gross'])} to {p2(ps['by_price']['gross'])} (price decile alone), "
        f"{p2(ps['by_type']['gross'])} (type alone) and <b>{p2(ps['by_both']['gross'])}</b> "
        f"(both, 95% CI {ps['by_both']['ci_gross'][0]:.2f}–{ps['by_both']['ci_gross'][1]:.2f}); "
        f"net moves to {p2(ps['by_both']['net'])} "
        f"(CI {ps['by_both']['ci_net'][0]:.2f}–{ps['by_both']['ci_net'][1]:.2f}). "
        f"The interval excludes the unweighted {p2(ps['visible_gross'])}, so the "
        f"{pp(ps['shift_pp'])} shift is not a rounding artefact. The cheapest price decile is under-represented "
        f"({ps['deciles'][0]['ratio']:.2f}× its share) and the dearest over-represented "
        f"({ps['deciles'][-1]['ratio']:.2f}×). Because cheaper buildings yield more, the visible "
        "slice understates the yield of the buildings it cannot see — <i>if</i> they resemble their "
        "price-decile neighbours. §6 shows why that \"if\" cannot be removed."))
    A(P("Affordability, as a side result", "h2"))
    A(P(f"Measured as median price over average income per earner (主計總處, {inc['year']}), a home "
        f"costs {inc['national_years']} years of income nationally and {inc['matched_years']} for the "
        f"priceable slice. Taipei is the outlier at "
        f"{[c for c in inc['counties'] if c['county']=='a'][0]['years']} years; 嘉義市 is the most "
        f"affordable at {[c for c in inc['counties'] if c['county']=='i'][0]['years']}. The priced "
        "slice is dearer per 坪 but smaller, so its total price is lower."))

    # ------------------------------------------------------------ 6 partial identification
    A(CondPageBreak(95 * mm))
    A(P("6  Bounding the 94% nobody can see", "h1"))
    A(P("Every number above is a median of the buildings the site can match. Dropping the other "
        f"{n0(pid['scope']['n'] - pid['scope']['matched'])} silently assumes they look like the ones on "
        "file. Partial identification refuses that assumption and <i>bounds</i> them instead. Inside "
        "each cell (type, then type × price decile, then × age band), matched buildings enter at their "
        "observed yields and the unmatched share enters as a mass at the cell's assumed floor or "
        "ceiling. The weighted median of that mixture is a sharp bound for the assumption named on "
        f"each rung. This is the standard construction {cite('manski1989', 'horowitz1995', 'manski2003')}: "
        "put the unobserved mass at the extremes of its support, and what comes out is an interval "
        "that the data cannot narrow rather than a point the data cannot support."))
    names = {"band": "Only the site's own quality band", "type_support": "Inside own type's observed min–max",
             "type_trim": "Inside own type's 5th–95th pct", "type_price": "+ own price decile (headline)",
             "type_price_age": "+ own age band"}
    prows = []
    for r in pid["rungs"]:
        g = r["gross"]
        prows.append((names[r["key"]], g["hi"], g["lo"], g["hi"], ACCENT))
    d = Drawing(FRAME_W, 20 + len(prows) * 19)
    L, W = 185, FRAME_W - 230

    def X(v):
        return L + v / 12.5 * W
    y = d.height - 18
    for lab, _, lo_, hi_, _c in prows:
        d.add(_s(L - 6, y + 2, lab, anchor="end"))
        d.add(Rect(X(lo_), y, X(hi_) - X(lo_), 9, fillColor=SOFT, strokeColor=ACCENT, strokeWidth=0.6))
        d.add(_s(X(hi_) + 3, y + 1.5, f"[{lo_:.2f}, {hi_:.2f}]", size=6.8))
        y -= 19
    d.add(Line(X(h["yield"]), 8, X(h["yield"]), d.height - 4, strokeColor=ACCENT2,
               strokeDashArray=[3, 2], strokeWidth=0.9))
    d.add(_s(X(h["yield"]) + 3, 2, f"matched median {h['yield']:.2f}%", size=6.6, color=ACCENT2))
    for t in (0, 3, 6, 9, 12):
        d.add(_s(X(t), d.height - 6, f"{t}%", size=6.2, color=MUTED, anchor="middle"))
    A(fig(d, "Figure 6.1 — Where the median gross yield of all buildings with a sale can lie, under "
             "each rung's assumption. Each rung is sharp for its assumption, not merely conservative."))
    tp = rungs["type_price"]
    A(P(f"The headline rung puts the median of all buildings in <b>[{tp['gross']['lo']:.2f}%, "
        f"{tp['gross']['hi']:.2f}%]</b> gross and [{tp['net']['lo']:.2f}%, {tp['net']['hi']:.2f}%] "
        "net. Three things constrain how to read it:"))
    A(KeepTogether(bullets([
        f"<b>The trim is a resemblance assumption.</b> \"Inside the 5th–95th percentile\" forbids any "
        f"unmatched building from sitting in its own type's top 5%. It buys {rungs['type_trim']['buys_pp']:.2f}pp "
        "of narrowing, the largest step, so the untrimmed rung stays beside it.",
        f"<b>The age rung fails and is published failing.</b> {rungs['type_price_age']['cells_below_min']} "
        f"of {rungs['type_price_age']['cells']} cells hold too few matched buildings, "
        f"{n0(rungs['type_price_age']['fellback_universe_n'])} buildings fall back to the weaker "
        f"assumption, and the interval <i>widens</i> by {abs(rungs['type_price_age']['buys_pp']):.2f}pp. "
        "Conditioning on more does not always identify more.",
        "<b>The residual selection is unsigned.</b> Matched buildings are "
        f"{pid['ppp_gap_pct']:.1f}% dearer per 坪, which suggests unmatched buildings yield more. But "
        "matching requires both a sale and a lease, which selects liquid investor stock, which suggests "
        "they yield less. Both directions are published, and neither is chosen.",
    ])))
    A(callout(f"A median's worst-case interval only leaves the support band once more than "
              f"{pid['median_bound_requires_coverage_pct']:.0f}% of the population is observed. This site "
              f"observes {p2(h['coverage_pct'])}; with every filter removed the registry allows "
              f"{p2(h['coverage_ceiling_pct'])}. No amount of better cleaning moves the first rung. That is a fact "
              "about the registry, not a disclaimer about the site.", "The quotable result"))
    un = pid["unanswerable"][0]
    A(P(f"Applied to walk-ups alone ({p2(un['coverage_pct'])} matchable), the interval is "
        f"[{un['support'][0]:.2f}%, {un['support'][1]:.2f}%], {un['width']:.2f}pp wide. That is wide "
        "enough to swallow the entire walk-up/tower gap of §9."))

    A(P("Is the resemblance assumption true?", "h2"))
    A(P("Every rung above the support rung rests on one idea: that an unmatched building resembles "
        "the <i>matched</i> buildings of its own cell. Editions up to v1.1 stated that, laddered it "
        "and labelled it honestly — and never tested it, which made it the only load-bearing claim in "
        "this report that was asserted rather than measured. It is testable, on the two things the "
        "cells do not condition on: how old a building is, and how big it is. If the cells do what "
        "the rung claims, the gap between matched and unmatched buildings should close inside them."))
    A(P("Reported as a standardised difference — the mean gap over the pooled standard deviation — "
        f"which is scale-free, with |d| &lt; {rz_meta['balanced_at']} the conventional threshold for "
        f"balanced. Cells need {rz_meta['min_cell']} matched buildings to count, so a handful of "
        "buildings cannot outvote a decile of them.", "note"))
    bz, az = rz["built"], rz["area"]
    A(tbl([["", "age (built year)", "area (坪)"],
           ["Unconditional d, whole universe", f"{bz['unconditional_d']:+.3f}",
            f"{az['unconditional_d']:+.3f}"],
           ["Within-cell |d|, size-weighted", f"{bz['within_cell_abs_d']:.3f}",
            f"{az['within_cell_abs_d']:.3f}"],
           ["Within-cell signed d", f"{bz['within_cell_signed_d']:+.3f}",
            f"{az['within_cell_signed_d']:+.3f}"],
           ["Absorbed by the cells", f"{bz['absorbed_pct']:.1f}%", f"{az['absorbed_pct']:.1f}%"],
           ["Cells not balanced", f"{bz['cells_unbalanced']} of {bz['cells']}",
            f"{az['cells_unbalanced']} of {az['cells']}"]],
          [62 * mm, 30 * mm, 30 * mm], right=(1, 2), size=7.8))
    A(Spacer(1, 6))
    A(P(f"<b>Age: mostly absorbed.</b> Across the whole universe matched buildings are "
        f"{bz['unconditional_d']:+.2f} standard deviations newer. Inside the cells that falls to "
        f"{bz['within_cell_abs_d']:.3f}, so the conditioning removes {bz['absorbed_pct']:.0f}% of it. "
        f"What survives is small but it is not noise: the signed mean is {bz['within_cell_signed_d']:+.3f}, "
        f"the same direction as the raw gap, and {bz['cells_unbalanced']} of {bz['cells']} cells are "
        "still outside the balanced band. Matched buildings are newer than their own cell-mates."))
    A(P(f"<b>Area: made worse, not better.</b> Unconditionally matched buildings are "
        f"{abs(az['unconditional_d']):.2f} standard deviations smaller. Inside the cells that does not "
        f"shrink — it grows to {az['within_cell_abs_d']:.3f}, {abs(az['absorbed_pct']):.0f}% in the "
        f"wrong direction, with {az['cells_unbalanced']} of {az['cells']} cells unbalanced and every "
        "one of the worst six carrying the same sign. The mechanism is not mysterious: the cells are "
        "cut on price per 坪, and 坪 is the denominator of that. Banding on a ratio strips out the "
        "price channel that was partly offsetting the size channel, so within a band the size gap "
        "expresses itself more freely than it did across the whole universe."))
    A(P(f"Worst cells by |d| on area: " + ", ".join(
        f"{w['type']} decile {w['decile']} ({w['d']:+.2f})" for w in az["worst"][:4]) + ".", "note"))
    A(callout(
        "So the headline interval is a <b>stated-assumption</b> interval, not a validated one, and on "
        "one measurable dimension the assumption is not merely unverified but contradicted. Nothing "
        "about the arithmetic changes — the bound is still sharp for the assumption named on its rung "
        "— but a reader should treat the narrowing from the quality band as resting on a condition "
        "the data only half supports.<br/><br/>"
        "It cannot be repaired by conditioning on size as well. The age rung already shows what "
        f"happens: adding a third dimension puts {rungs['type_price_age']['cells_below_min']} of "
        f"{rungs['type_price_age']['cells']} cells below the minimum and sends "
        f"{n0(rungs['type_price_age']['fellback_universe_n'])} buildings back to the weaker "
        f"assumption, which is why it <i>widens</i> the interval by "
        f"{abs(rungs['type_price_age']['buys_pp']):.2f}pp. At {p2(h['coverage_pct'])} coverage the "
        "data runs out before the conditioning does. That is the same wall as the rest of §6, met "
        "from a different direction.",
        "What this does to the interval"))

    # ------------------------------------------------------------ 7 ladder
    A(CondPageBreak(95 * mm))
    A(P("7  What each cleaning step is worth", "h1"))
    A(P("The honesty ladder re-runs the headline with filters added one at a time, all through the "
        "same code path as the headline. Each rung is read per building with a 95% CI; the pair-level "
        "figure is shown beside it to make the unit problem visible."))
    lrows = [["Rung", "per building", "95% CI", "per pair", "buildings", "pairs"]]
    for r in lad:
        lrows.append([r["en"], p2(r["yield_building"]), f"{r['lo']:.2f}–{r['hi']:.2f}",
                      p2(r["yield_pair"]), n0(r["buildings"]), n0(r["pairs"])])
    A(tbl(lrows, [66 * mm, 21 * mm, 22 * mm, 18 * mm, 21 * mm, 22 * mm], right=(1, 2, 3, 4, 5),
          wrap=(0,), size=7.8))
    A(Spacer(1, 6))
    sh = fm["shapley"]["building"]
    A(P(f"Because filter order matters, each filter's contribution is also computed as a <b>Shapley "
        f"value</b> {cite('shorrocks2013')} over all 2³ combinations; the three sum exactly to the total move of "
        f"{pp(fm['total']['building'],3)} per building. Social housing: <b>{pp(sh['social'],3)}</b> "
        f"(the largest, and the sign the subsidy predicts). Whole-unit only: {pp(sh['rooms'],3)}. "
        f"Related-party: {pp(sh['related'],3)}."))
    A(P("The Simpson reversal that forced this", "h2"))
    A(P("An earlier ladder showed removing social housing <i>lowering</i> the yield, which is the wrong "
        "sign for a population renting 28% below market. The filter was correct; two presentation "
        "faults stacked:"))
    cc = mm_["concentration"]
    A(KeepTogether(bullets([
        f"<b>Mixed units.</b> A building holding any social lease carries {cc['with_social']['pairs_per_building']} "
        f"pairs against {cc['without']['pairs_per_building']} for one with none, so a pair-level median "
        f"weights social buildings {cc['pair_weight_ratio']}:1 and a building-level one "
        f"{cc['bldg_weight_ratio']}:1.",
        "<b>Ordering.</b> Room-shares yield ~1.27% (their area field describes the building, not the "
        f"let), are {mm_['by_let_type'][2]['market_share_pct']}% of market leases and "
        f"{mm_['by_let_type'][2]['social_share_pct']}% of social ones. Dropping social housing first "
        "raises the room-share weight.",
    ])))
    A(tbl([["Let type", "social", "market", "social − market"]] +
          [[r["let_type"], p2(r["social"]), p2(r["market"]), pp(r["social"] - r["market"])]
           for r in mm_["by_let_type"]],
          [50 * mm, 30 * mm, 30 * mm, 35 * mm], right=(1, 2, 3)))
    A(P("Within every let type the social lease yields less, yet the aggregate moved the other way. "
        "The page's own sentence claiming the ladder measured \"what each cleaning decision is worth\" "
        "was retracted: a sequential ladder cannot do that, and the Shapley decomposition can.", "note"))
    A(P("The social-housing rent gap", "h2"))
    A(P(f"Social-housing leases rent at NT${rb['social']['rent_ping']:.0f} per 坪 per month against "
        f"NT${rb['market']['rent_ping']:.0f} for market leases ({rb['gap_pct']:.1f}%), and they are "
        f"{rb['social_share_pct']}% of whole-unit registry leases (~58% of all leases). The share is "
        "above 90% in 桃園, 苗栗 and 基隆. Excluding them was the single largest filter decision in the "
        "project, and it is the one most raw-data yield estimates skip."))

    # ------------------------------------------------------------ 8 geography
    A(CondPageBreak(95 * mm))
    A(P("8  Geography", "h1"))
    cn = sorted([c for c in D["counties"] if c["buildings"] >= 25], key=lambda c: c["yield"])
    crow = []
    for c in cn:
        ci = boot["county"].get(c["county"])
        crow.append((f"{c['city']} ({c['buildings']:,})", c["yield"], ci["lo"] if ci else None,
                     ci["hi"] if ci else None, ACCENT))
    A(fig(hbars(crow, lo=0, hi=4.6, label_w=110, bar_h=9, gap=4, ref=h["yield"],
                ref_label=f"national {h['yield']:.2f}%"),
          "Figure 8.1 — Median gross yield by county, with 95% bootstrap intervals (building count in "
          "brackets). Counties with fewer than 25 matched buildings are omitted. 金門 and 連江 have no "
          "clean leases at all; that is a registry fact."))
    A(P(f"Most adjacent counties cannot be told apart statistically "
        f"({boot['adjacent_overlaps']} of {boot['adjacent_pairs']} adjacent district intervals overlap), "
        "but the two extremes genuinely differ. Taipei is the lowest-yielding large city because it "
        "is the most expensive: across districts the correlation between price per 坪 and yield is "
        f"<b>{corr_price_yield(D['districts']):.3f}</b> (over the {len(D['districts'])} published districts). "
        "Rents vary much less than prices do."))
    ds = sorted([x for x in D["districts"] if x["buildings"] >= 25], key=lambda x: x["yield"])
    rows = [["", "District", "gross", "net", "buildings", "price / 坪"]]
    for tag, sub in (("lowest", ds[:6]), ("highest", ds[-6:][::-1])):
        for i, x in enumerate(sub):
            rows.append([tag if i == 0 else "", f"{x['city']} {x['district']}", p2(x["yield"]),
                         p2(x["net"]), n0(x["buildings"]), n0(x["price_ping"])])
    A(tbl(rows, [18 * mm, 48 * mm, 20 * mm, 20 * mm, 22 * mm, 30 * mm], right=(2, 3, 4, 5)))
    A(Spacer(1, 6))
    A(P(f"<b>Within vs between.</b> Over {n0(disp['buildings'])} buildings with at least "
        f"{disp['min_pairs']} pairs, the typical spread of yields inside one building (IQR "
        f"{disp['within_iqr']:.3f}pp) is {disp['ratio']:.2f}× the spread between district medians "
        f"({disp['between_iqr']:.3f}pp). In the two-city version this ratio was 2.46× the other way, "
        "\"one building varies more than a whole city\". That conclusion inverted when scope went "
        "national and was rewritten to follow the data in either direction. Even so, two flats in one "
        "building differ by more than half as much as two districts do, which is why a single district "
        "average hides a lot."))
    A(P(f"<b>Vacancy break-even.</b> The highest-yielding district with enough data, "
        f"{vb['city']}{vb['district']} ({p2(vb['gross'])}), would need a vacancy rate of "
        f"{vb['breakeven_vacancy_pct']}% to fall to the national district median — against a default "
        f"of {vb['default_vacancy_pct']:.0f}% and a measured county low-use rate far below that. High "
        "yields in cheap districts are not explained away by empty flats."))

    # ------------------------------------------------------------ 9 walk-ups
    A(CondPageBreak(95 * mm))
    A(P("9  Walk-ups vs towers: the founding hypothesis", "h1"))
    A(P("The project started from one idea: older 公寓 walk-ups, cheap per 坪 and without management "
        "fees, should out-yield towers. It went through four verdicts."))
    A(tbl([["Stage", "Verdict", "Why"],
           ["Two cities (Aug)", "dead", "gross gap 0.041pp; ~81% of the net gap was the project's own cost assumption"],
           ["National (Sep 8)", "alive", f"gross gap +0.374pp, CI excluding zero; the \"dead\" label had been a hard-coded string"],
           ["Controls (Sep 11)", "contested", "+0.120pp within price decile, +0.637pp within district: both cannot be the effect"],
           ["v2.2 (Sep 20)", "unanswerable", "tower-side representativeness fails; fee mechanism falsified"]],
          [30 * mm, 24 * mm, FRAME_W - 54 * mm], wrap=(2,)))
    A(Spacer(1, 6))
    prec = wr["precision"]
    A(P(f"<b>The gap is real in the matched data.</b> Walk-ups {p2(dh['by_type'][2]['gross'])} vs towers "
        f"{p2(dh['by_type'][0]['gross'])}: {pp(prec['gross_gap'],3)} gross (CI {prec['lo']:.3f}–"
        f"{prec['hi']:.3f}, {prec['ratio_obs_to_mdd']}× the minimum detectable difference) and "
        f"{pp(prec['net_gap'],3)} net. It holds in the same sign across most control families:"))
    fam = {"price_decile": "price decile", "county_district": "district", "county": "county",
           "age_band": "age band", "size_band": "size band", "has_mgr": "has manager",
           "district_x_price_decile": "district × price decile", "district_x_age_band": "district × age band"}
    A(tbl([["Control family", "cells", "walk-ups covered", "median gap", "same sign", "binding"]] +
          [[fam.get(c["family"], c["family"]), str(c["cells"]), n0(c["walkups_covered"]),
            "—" if c["median_gap"] is None else pp(c["median_gap"], 3),
            "—" if c["same_sign_pct"] is None else f"{c['same_sign_pct']:.0f}%",
            "yes" if c["binding"] else "no"] for c in wr["controls"]],
          [42 * mm, 15 * mm, 30 * mm, 25 * mm, 22 * mm, 18 * mm], right=(1, 2, 3, 4)))
    A(Spacer(1, 6))
    rw, rt = wr["representativeness"]
    A(P(f"<b>Why it cannot be settled.</b> Matched walk-ups look like walk-ups in general (largest "
        f"median difference {rw['max_abs_diff_pct']}%). Matched towers do not: they are "
        f"{rt['medians']['area_ping']['m']:.1f} 坪 against {rt['medians']['area_ping']['u']:.1f} for towers "
        f"that sold and never matched ({rt['medians']['area_ping']['diff_pct']:+.1f}%). Two differently "
        "skewed samples cannot answer a population question, and the pre-stated rule classifies that as "
        f"<i>{wr['verdict'].replace('_', ' ')}</i>. The age distributions barely overlap either: walk-up "
        f"median {wr['common_support']['walkup_age']['median']:.0f} years vs tower "
        f"{wr['common_support']['tower_age']['median']:.0f}, and zero district × age cells reach 25 "
        "buildings of each."))
    mc = {c["has_mgr"]: c for c in wr["mechanism"]["cells"]}
    A(P(f"<b>What is settled: the proposed mechanism is false.</b> A manager is recorded for "
        f"{wr['mechanism']['p_mgr_tower_pct']}% of towers and {wr['mechanism']['p_mgr_walkup_pct']}% of "
        f"walk-ups, so the fee is nearly a type indicator. But in buildings with no manager on either "
        f"side ({mc[0]['n_walkup']} walk-ups vs {mc[0]['n_tower']} towers), where the modelled fee is "
        f"exactly zero, the gap is still {pp(mc[0]['gross_gap'],3)} (CI {mc[0]['lo']:.3f}–{mc[0]['hi']:.3f}). "
        "The gap does not need the fee. The project's founding explanation died on the project's own "
        "data."))
    A(callout("A complete population of residential leases (owner-let walk-ups never enter the "
              "registry, which only receives filings from licensed firms), or building-level house-tax "
              "micro-data by type × age × floor (released to institutions only). Neither is available "
              "to this project.", "What data would answer it"))

    # ------------------------------------------------------------ 10 within
    A(CondPageBreak(70 * mm))
    A(P("10  Inside one building", "h1"))
    A(P("Comparing units <i>within</i> the same building holds location, age, construction and "
        "amenities constant by construction. These are the most strongly identified results in the "
        "project."))
    A(tbl([["Comparison", "effect", "buildings", "basis"],
           ["Furnished vs unfurnished rent", f"+{wb['furnished']['pct']:.1f}%", n0(wb["furnished"]["buildings"]),
            f"NT${wb['furnished']['diff_ppp']:.0f}/坪/month on {wb['furnished']['base_ppp']:.0f}"],
           ["Rent per floor", f"+{wb['floor']['pct_per_floor']:.2f}%", n0(wb["floor"]["buildings"]),
            f"NT${wb['floor']['slope_ppp_per_floor']:.2f}/坪 per floor"],
           ["Price per floor", f"+{wb['floor_sale']['pct_per_floor']:.3f}%", n0(wb["floor_sale"]["buildings"]),
            f"NT${wb['floor_sale']['slope_ppp_per_floor']:,.0f}/坪 per floor"]],
          [52 * mm, 22 * mm, 24 * mm, FRAME_W - 98 * mm], right=(1, 2)))
    A(Spacer(1, 5))
    A(P(f"Buyers pay about five times more per extra floor than tenants do, so higher floors yield "
        f"less: over twenty floors that is roughly {wb['floor_gap_pp']:.2f}pp of yield. The view is "
        f"capitalised into the price, not the rent. The two slopes come from different building sets "
        f"({n0(wb['floor']['buildings'])} with leases on 2+ floors, {n0(wb['floor_sale']['buildings'])} "
        "with sales on 2+ floors), and the site names both counts."))

    # ------------------------------------------------------------ 11 transit
    A(CondPageBreak(95 * mm))
    A(P("11  Transit: a finding withdrawn four times over", "h1"))
    A(P("Distance to the nearest station looked like the project's second finding: yield rising from "
        "about 2.1% near a station to 2.9% beyond 2.5 km, monotone across seven bins. It is now "
        "<b>withdrawn</b>, and the path there is the most instructive story in the project."))
    A(tbl([["Version", "What was published", "What was wrong"],
           ["v1.2", "national gradient, \"price falls faster than rent\"",
            "only Taipei's 131 stations were loaded: 高雄 buildings were measured ~275 km to Taipei"],
           ["v1.3", "retraction on a 臺北市-only panel", "Taipei City has 4 buildings beyond 2.5 km; the \"null\" was an empty group"],
           ["v1.3b", "restored on 北北桃, then 新北 alone (+0.53pp)", "heavy rail only; 淡海輕軌 serves exactly the far group"],
           ["v1.4", "withdrawn", "with light rail the 新北 gap is ~0; 高雄, the first independent city, shows none"]],
          [16 * mm, 62 * mm, FRAME_W - 78 * mm], wrap=(1, 2)))
    A(Spacer(1, 6))
    mrows = []
    for code, city in (("f", "新北市"), ("e", "高雄市")):
        for key, lab in (("mrth", "heavy rail"), ("mrt", "incl. light rail")):
            near = [b["y"] for b in B if b["c"] == code and b.get(key) is not None and b[key] <= 500]
            far = [b["y"] for b in B if b["c"] == code and b.get(key) is not None and b[key] > 2000]
            if len(near) >= 25 and len(far) >= 25:
                mrows.append([city, lab, f"{statistics.median(near):.2f}% (n={len(near)})",
                              f"{statistics.median(far):.2f}% (n={len(far)})",
                              pp(statistics.median(far) - statistics.median(near))])
            else:
                mrows.append([city, lab, f"n={len(near)}", f"n={len(far)}", "too thin"])
    A(P("Recomputed for this report from the per-building distances in the payload (medians of "
        "building gross yields, ≤500 m vs >2 km):"))
    A(tbl([["County", "Stations counted", "≤500 m", ">2 km", "far − near"]] + mrows,
          [24 * mm, 34 * mm, 40 * mm, 40 * mm, 28 * mm], right=(2, 3, 4)))
    A(Spacer(1, 5))
    A(P("<b>The rule this produced.</b> A result that flips on a judgement call (is 輕軌 a station?) "
        "is a finding about the judgement, not the subject. Where such a call exists, compute both "
        "and show both. And a null from a group of four is not evidence of absence: check the size of "
        "the comparison group before believing a null."))

    # ------------------------------------------------------------ 12 presale
    A(CondPageBreak(70 * mm))
    A(P("12  Pre-sale: the 30% premium that was not one", "h1"))
    A(P(f"The registry's pre-sale files hold {n0(pre['dwellings'])} dwellings in {n0(pre['projects'])} "
        f"projects across {pre['districts']} districts in the window (median NT${n0(pre['median_ppp'])} "
        "per 坪). A pre-sale flat has no lease, so no yield can ever be computed for one; that half of "
        "the result never moved. The price comparison was published wrong twice:"))
    A(KeepTogether(bullets([
        "<b>Attempt 1</b> compared pre-sale against \"completed buildings under two years old\", found "
        "+30.2%, and attributed it to the delivery wait.",
        "<b>Attempt 2</b> retracted the mechanism (a placebo between two completed groups fell almost "
        "as fast) but kept the +30.2%.",
        "<b>Attempt 3</b> found the group itself was wrong. 交易年月日 in the sale file is the "
        "<i>contract</i> date, not the handover date, so \"under two years old\" selected 186,550 rows "
        "of which <b>168,426 (90.3%) were contracts signed before the building existed</b>, median age "
        "at contract −2.17 years. The published number was pre-sale against pre-sale.",
    ])))
    crv = [(f"{c['lag_years']:.1f} yr later ({c['clusters']} clusters)", c["gap_pct"], c["ci_lo"],
            c["ci_hi"], ACCENT if c["gap_pct"] >= 0 else ACCENT2) for c in pre["curve"]]
    A(fig(hbars(crv, lo=-13, hi=9, fmt=lambda v: f"{v:+.1f}%", label_w=130, zero_axis=True),
          "Figure 12.1 — Pre-sale price premium over genuinely completed new homes (0–2 years old at "
          "contract), with the comparison pushed later in time. Intervals are bootstrapped over district "
          "× type clusters, not cells, because cells within a cluster are not independent."))
    A(P(f"Only the contract-quarter gap stands: <b>+{pre['curve'][0]['gap_pct']:.1f}%</b> (CI "
        f"{pre['curve'][0]['ci_lo']:.1f}–{pre['curve'][0]['ci_hi']:.1f}), stable at minimum cell sizes "
        f"of 5, 25 and 100. It reaches {n0(pre['reach_dwellings'])} dwellings ({pre['reach_pct']}%) in "
        f"{pre['reach_districts']} of {pre['total_districts']} districts; the rest have too few genuinely "
        "completed new builds to compare against. Whether the later gaps are time or composition cannot "
        "be separated (<i>separable = false</i>)."))

    # ------------------------------------------------------------ 13 parking
    A(CondPageBreak(95 * mm))
    A(P("13  Parking: a cleaning assumption tested and found false", "h1"))
    lets = pa["lets"]
    A(P(f"{p2(lets['unpriced_pct'])} of clean leases ({n0(lets['unpriced'])}) bundle a parking space "
        "whose rent was never itemised. Until v2.0 the pipeline assumed that meant the space came free "
        "and subtracted only its area. The test: in buildings holding both kinds of bundled lease, "
        "compare total rent per m²."))
    v = pa["verdict"]
    A(tbl([["", "value"],
           ["Predicted ratio if the space were free", f"{v['predicted_if_holds']:.3f}"],
           ["Predicted ratio if its rent were inside the dwelling rent", f"{v['predicted_if_fails']:.3f}"],
           [f"Measured (n = {v['n']} buildings)", f"{v['ratio']:.4f}  [{v['lo']:.3f}, {v['hi']:.3f}]"],
           ["Verdict", v["verdict"].replace("_", " ")]],
          [110 * mm, 60 * mm], right=(1,)))
    A(Spacer(1, 6))
    ex = pa["exposure"]
    A(P(f"The assumption fails, so the dwelling rent was overstated on those leases. The typical "
        f"itemised space rents for NT${pa['share']['park_rent_per_space_median_ntd']:,}/month "
        f"({pa['share']['park_rent_share_median']*100:.1f}% of the lease). Three treatments were compared:"))
    trows = [["Treatment", "gross", "net", "buildings"]]
    for t in pa["treatments"]:
        trows.append([{"impute": "Impute space rent (headline since v2.1)",
                       "area_only": "Area-only subtraction (v1.0–v2.0 headline)",
                       "drop": "Drop bundled leases entirely"}.get(t["case"], t["case"]),
                      p2(t["gross"]), p2(t["net"]) if t.get("net") is not None else "—", n0(t["buildings"])])
    A(tbl(trows, [85 * mm, 25 * mm, 25 * mm, 30 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P(f"Dropping them looks attractive but flatters the result: the {ex['buildings_only_unpriced_pct']}% "
        f"of buildings that would vanish are newer (民國{ex['only_unpriced_built_median']:.0f} vs "
        f"{ex['rest_built_median']:.0f}) and {ex['only_unpriced_tower_pct']}% towers. The rule that "
        "decided the verdict was written after an early n=192 look, and the page says so rather than "
        "calling it pre-registered."))
    mk = [r for r in pk["rungs"] if r["key"] == "market"][0]
    A(P("Parking as an asset", "h2"))
    A(P(f"Treated as its own investment, a space bought and let at market prices yields "
        f"<b>{p2(mk['yield'])}</b> gross (CI {mk['lo']:.2f}–{mk['hi']:.2f}, {mk['buildings']} buildings, "
        f"median price NT${n0(mk['price'])}, rent NT${n0(mk['rent'])}/month), below the flats above them. "
        f"Mechanical spaces (坡道機械) yield more than ramp-level spaces ({pp(pk['type_gap']['wide']['gap_pp'])} "
        "on the wider sample); this is labelled a hypothesis, because its mechanism is not measured."))

    # ------------------------------------------------------------ 14 costs
    A(CondPageBreak(70 * mm))
    A(P("14  The cost model, and how much each guess matters", "h1"))
    A(P(f"Net yield rests on four assumptions, and two of them (vacancy, repairs) have no Taiwanese "
        "source at all. The project's answer was to measure how much each guess moves the result, not "
        "to pretend it had a source."))
    A(P("Management fee", "h2"))
    A(P(f"Only Taipei and New Taipei have published fee surveys, and the other 20 counties are charged "
        f"New Taipei's NT$105/坪. {mex['share_charged_pct']}% of buildings are charged a fee at all "
        f"(those whose leases record on-site staff), and {n0(mex['buildings_outside'])} sit in counties "
        "with no fee statistic. Halving the non-Taipei rate moves net to "
        f"{p2(mex['cases'][1]['net'])}; zeroing it moves it to {p2(mex['cases'][2]['net'])}. Separately, "
        f"{mfl['lets']['incl_pct']}% of leases in staffed buildings state in 備註 that the rent already "
        f"includes the fee. Charging only buildings without that flag gives {p2(mfl['bounds'][1]['net'])} "
        f"({pp(mfl['bounds'][1]['delta_pp'])})."))
    A(P("Vacancy", "h2"))
    A(P(f"Taiwan publishes no rental-vacancy statistic, so the level stays an assumption "
        f"({vp['site_default_pct']:.0f}%). The <i>shape</i> can be measured from 內政部's low-use "
        "(electricity-based) housing table crossed by county and age, recovered from the Internet Archive:"))
    vrows = []
    for r in vp["profile"]:
        vrows.append((f"age {r['band']} · low-use rate", r["rate_pct"], None, None, colors.HexColor("#b9b3a3")))
    A(fig(hbars(vrows, lo=0, hi=25, fmt=lambda v: f"{v:.1f}%", label_w=150, bar_h=8, gap=3),
          "Figure 14.1 — Low-use dwelling rate by building age (111H1), a U shape: new buildings and old "
          "buildings are the emptiest."))
    A(tbl([["Age band", "low-use rate", "share of priced", "share of stock"]] +
          [[r["band"], p2(r["rate_pct"]), p2(r["matched_share_pct"]), p2(r["stock_share_pct"])]
           for r in vp["profile"]],
          [35 * mm, 35 * mm, 40 * mm, 40 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P(f"The priced slice sits on the left arm of the U, where a flat vacancy rate flatters the yield "
        f"most: weighted by its own composition, its expected low-use rate is <b>{vp['prior_pct']:.2f}%</b> "
        f"(CI {vp['prior_ci'][0]:.2f}–{vp['prior_ci'][1]:.2f}) against {vp['national_pct']}% nationally. "
        f"The county-only leg points the other way ({vp['county_leg']['prior_pct']:.2f}% vs "
        f"{vp['county_leg']['national_pct']}%), because the sample is metropolitan; both are published. "
        "Low-use is not rental vacancy (its numerator includes second homes and homes for sale), so it "
        "never replaces the headline assumption:"))
    A(tbl([["Case", "net", "vs headline", "walk-up − tower (net)"]] +
          [[c["en"], p2(c["net"]), pp(c["delta_pp"], 3),
            pp([t for t in vp["type_gap"] if t["case"] == c["key"]][0]["gap_pp"], 3)]
           for c in vp["cases"]],
          [70 * mm, 25 * mm, 30 * mm, 40 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P(f"<b>Repairs</b> are charged at 6% of rent × (1 + age/50). A flat rate would bias walk-up vs "
        f"tower in one direction: the walk-up gap is {rep['gross']:.3f}pp gross, {rep['age_scaled']:.3f}pp "
        f"with age-scaled repairs and {rep['flat']:.3f}pp with a flat rate. <b>Holding tax</b> defaults to "
        "0.15% of price, above the published self-use estimates, because 囤房稅2.0 raised the non-self-use "
        "rate."))

    # ------------------------------------------------------------ 15 context
    A(CondPageBreak(95 * mm))
    A(P("15  Market context", "h1"))
    A(P("Transaction volume halved inside the window", "h2"))
    s = vol["series"]["all"]
    A(fig(lines([s["existing"], s["presale"], s["leases"]], vol["quarters"],
                [ACCENT, ACCENT2, ACCENT3],
                events=[("113Q2", "新青安 tightening"), ("113Q3", "囤房稅2.0 · CBC round 7")]),
          f"Figure 15.1 — Clean registry rows per contract quarter, nationally. Blue: existing homes; "
          f"orange: pre-sale; green: leases. {vol['censored'][0]} is incomplete (late filings)."))
    A(legend([("existing homes", ACCENT), ("pre-sale", ACCENT2), ("leases", ACCENT3)]))
    sm = vol["summary"]
    A(P(f"Existing-home sales fell {abs(sm['existing_change_pct']):.1f}% from their {sm['peak_q']} peak "
        f"({n0(sm['peak_existing'])}) to {sm['after_q']} ({n0(sm['after_existing'])}); pre-sale fell "
        f"{abs(sm['presale_change_pct']):.1f}% by {sm['presale_to_q']}. Leases rose from "
        f"{n0(sm['leases_from'])} to {n0(sm['leases_to'])} over the same span. Three policies landed in "
        "the same two quarters, so the page describes the drop and does not attribute it."))
    A(P("The priced slice is dearer than the official average", "h2"))
    pr = [r for r in moi["price"]["rows"] if r["n"] >= 100]
    A(tbl([["County", "official mean 元/坪", "site median 元/坪", "gap", "buildings"]] +
          [[r["city"], n0(r["official"]), n0(r["ours"]), f"{r['gap_pct']:+.1f}%", n0(r["n"])] for r in pr],
          [30 * mm, 38 * mm, 38 * mm, 25 * mm, 25 * mm], right=(1, 2, 3, 4)))
    A(Spacer(1, 5))
    A(P(f"Against 內政部's {moi['price']['period']} contract averages, the site's matched buildings are "
        "dearer in every large city except 花蓮, 宜蘭 and 嘉義市. This is the \"visible slice is dearer\" "
        "finding confirmed from outside the registry."))
    pi = moi["price_index"]
    A(P(f"<b>Uncorrected drift.</b> The official price index rose {pi['total_pct']}% over "
        f"{pi['quarters']} quarters ({pi['per_quarter_pct']:.2f}%/quarter). At the median sale–lease gap "
        f"of {pi['median_pair_gap_q']:.0f} quarters, a typical pair carries about "
        f"{pi['drift_at_median_gap_pct']}% of price drift. The project's own index made things worse — "
        f"the yield-vs-gap slope steepened from {idx[2]['slope']:.3f} to {idx[3]['slope']:.3f} at ±4 "
        "quarters — so it is off, and the drift is disclosed instead."))
    ma = moi["auction"]
    A(P("Forced sales", "h2"))
    A(P(f"Court auctions (法拍) cleared {n0(ma['court_lots'])} lots worth NT${ma['court_value']/1e8:,.0f}億 "
        f"in the window. The bank-collateral channel (金拍, 台灣金服) the project could scrape had "
        f"{n0(ma['fasc_lots'])} lots in the same window ({ma['fasc_vs_court_pct']}% of the court count). "
        f"These are parallel channels, not a subset. Among 金拍 lots, {auc['above_reserve_pct']}% sold "
        f"above reserve (first round {auc['by_round']['1']['above_reserve_pct']}%). No area field exists, "
        "so no auction discount is computed. 法拍 itself is unreachable: 司法院's system refuses "
        "connections."))
    A(P(f"<b>Also published:</b> {n0(moi['unsold_new']['value'])} completed-but-unsold new homes at "
        f"{moi['unsold_new']['period']}; national low-use rate {lu_rate(moi, 'all')['rate_pct']}% "
        f"({moi['low_use']['period']}), from {lu_rate(moi, 'a')['rate_pct']}% in Taipei to "
        f"{lu_rate(moi, 'd')['rate_pct']}% in Tainan."))

    # ================================================================ PART III
    A(PageBreak())
    A(P("Part III · Reliability", "part"))
    A(P("16  Corrections register", "h1"))
    A(P("The project's design principle was to refuse flattering versions of itself: when a result "
        "looked clean, the next step was to try to break it. These are the published claims that "
        "later checks changed. Every one was true, or at least defensible, when it was written."))
    reg = [
        ["Claim", "First published", "Now", "Caught by"],
        ["Headline gross yield", "2.43% (2 cities) → 2.68%", f"{p2(h['yield'])}", "scope; parking audit"],
        ["Hero coverage sentence", "\"only 6.22% have both on file\"", "27.8% have both; 6.25% survive our filters",
         "independent audit"],
        ["Match rates by type", "towers 14.09%, walk-ups 1.69%", f"{p2(tw['match_rate'])} / {p2(wu['match_rate'])}",
         "denominator moved to universe"],
        ["Selection effect (price/坪)", "+30.5% → +2.7%", f"+{age['ppp_diff_pct']:.1f}%", "site audit (wrong frame)"],
        ["Walk-up hypothesis", "dead → alive", "unanswerable; mechanism falsified", "tower-side check"],
        ["Within vs between spread", "within 2.46× between", f"within {disp['ratio']:.2f}× between", "national rescope"],
        ["Transit gradient", "survives", "withdrawn", "light-rail definition; 高雄"],
        ["Pre-sale premium", "+30.2%", f"+{pre['curve'][0]['gap_pct']:.1f}%", "contract-date contamination"],
        ["Pre-sale net-of-time", "0.9%", "not separable", "second audit"],
        ["Priceable share of all buildings", "1 in 1,086", "withdrawn (棟 ÷ 建號)", "own MOI audit"],
        ["Social-housing ladder rung", "−0.165pp", f"Shapley {pp(sh['social'],3)}", "unit/order analysis"],
        ["Un-itemised parking", "space came free", "rent inside dwelling rent", "within-building test"],
        ["Net histogram & sliders", "\"sliders move this chart\"", "they did not; fixed", "4-agent audit"],
        ["Auction registry share", "13.8% of buildings", "14.0% of lots (unit named)", "audit"],
        ["Room-share filter label", "\"room-shares\"", "also blanks and floor lets (5,964)", "data-cleaning audit"],
        ["臺南 gap vs listings (§4)", pp(zc["臺南市"]["headline"] - GPG_CITIES["臺南市"]),
         f"{pp(zc['臺南市']['per_ping'] - GPG_CITIES['臺南市'])} per 坪, "
         f"{pp(zc['臺南市']['size_matched'] - GPG_CITIES['臺南市'])} size-matched",
         "pre-send stress test (v1.3)"],
        ["City footprint (§4)", "\"a great deal of non-urban area\"",
         "measured: 臺南's city proper yields more than its former county", "pre-send stress test (v1.3)"],
        ["Lease-filing rule (§5)", "asserted", "cited to the two statutes", "pre-send stress test (v1.3)"],
    ]
    A(tbl(reg, [40 * mm, 42 * mm, 48 * mm, FRAME_W - 130 * mm], wrap=(0, 1, 2, 3), size=7.6))
    A(Spacer(1, 6))
    A(P("Across the full ten-dimension site audit: 41 findings raised, 35 confirmed and fixed, 6 rejected "
        "on verification. Two of the six rejections were false alarms raised by the project itself (a "
        "rounding floor mistaken for a bug, and an income \"sign flip\" that compared two different "
        "populations)."))

    A(P("Editions of this paper", "h2"))
    A(P("Numbers get a corrections register; the write-up itself needs one too, or a version number "
        "says nothing about what moved."))
    A(tbl([["Edition", "Date", "What changed"]] +
          [[v, d, t] for v, d, t in PAPER_CHANGES],
          [18 * mm, 20 * mm, FRAME_W - 38 * mm], wrap=(2,), size=7.6))

    A(CondPageBreak(70 * mm))
    A(P("17  Bug classes and working rules", "h1"))
    A(P("The same few mistakes recurred in different clothes. These rules are the most transferable "
        "output of the project, and they apply to any future data work, stocks included."))
    A(KeepTogether(bullets([
        "<b>Derive, don't type.</b> Nine published sentences went stale when scope went national, "
        "because numbers update themselves and prose does not. Every figure in the copy is now "
        "computed from the payload.",
        "<b>Branch, don't assert.</b> Where a claim has a direction (survives or not, wider or "
        "narrower), the copy picks its branch from the data.",
        "<b>Assert the derivation, not the answer.</b> A test that checks verdict == \"dead\" protects "
        "a stale conclusion; a test that checks the verdict follows the interval does not.",
        "<b>Check the unit of both numbers before the arithmetic.</b> Pair vs building, lot vs building, "
        "棟 vs 宅 vs 建號, windowed vs unwindowed: this was the most frequent error class.",
        "<b>A rate needs its numerator and denominator from the same frame.</b>",
        "<b>Compute both sides of a comparison before writing its verdict.</b> The walk-up verdict flipped "
        "the moment the tower side existed.",
        "<b>Establish which population a number describes before calling it wrong.</b>",
        "<b>Read the rendered page, in both languages.</b> Placeholder-order bugs (a count printed as a "
        "percentage) pass every arity test and are visible only on screen.",
        "<b>A tolerance calibrated on one dataset is a constant pretending to be a measurement.</b>",
        "<b>A closure over the thing you are resampling is a resampling that does not happen.</b>",
        "<b>A hard-coded colour is only right in one theme.</b>",
        "<b>Size multi-agent audits to finish.</b> 10-agent runs died on session limits; 3–5-agent runs "
        "completed and every completion found real bugs. When verifiers die, verify by hand.",
    ])))

    A(CondPageBreak(95 * mm))
    A(P("18  Open items and how to restart", "h1"))
    A(P("v1.0 wrote this section about a parked project, and its first three items were that no "
        "reader had ever seen the work, that both repositories were private, and that the page "
        "carried noindex. None of those is true now. A register that goes on asserting them is worse "
        "than no register, so this edition splits the list.", "note"))
    A(P("Closed since v1.0", "h2"))
    A(KeepTogether(bullets([
        "<b>It is public.</b> Write-up, payload, pipeline and page are at "
        "<i>github.com/Stanley0210/taiwan-rental-yield</i>, served at "
        "<i>stanley0210.github.io/taiwan-rental-yield</i>.",
        "<b>\"Check my denominator\" is a real invitation now.</b> The payload ships with its SHA-256 "
        "and a provenance block hashing every source archive and reference file the build read.",
        "<b>It is citable</b>, with a Zenodo concept DOI that always resolves to the newest version, a "
        "CITATION.cff, and the citation in the README.",
        "<b>It exists in Traditional Chinese</b> as well as English, built from the same payload by a "
        "second generator, with a test pinning that both editions state the same headline figures.",
        f"<b>The stale ceiling is fixed.</b> v1.0 caught its own typed constant — "
        f"<i>partial_id.ceiling_pct</i> read 24.0% while the waterfall said "
        f"{p2(h['coverage_ceiling_pct'])} — and named the one-line repair. Payload v2.9 reads it from "
        "the waterfall, so the two can no longer disagree.",
        "<b>The net yield and the reweighted median now carry intervals.</b> Both were published as "
        "bare point estimates beside a gross figure that had a CI.",
        "<b>Dependencies are pinned and a clean install is tested.</b> v1.2 pinned "
        "<i>requirements.txt</i> and then printed \"dependencies are unpinned\" in this very list, "
        "which is the staleness this section exists to catch, committed inside the section itself. "
        "<i>requirements-dev.txt</i> now also carries pytest, which lived nowhere despite being the "
        "command the README leads with, and CI installs from those pins on a machine that has never "
        "seen the project, verifies the payload hash, runs the suite and rebuilds all four documents.",
        "<b>The mortgage rate says what it is.</b> It is still transcribed, because the CBC publishes "
        "五大銀行新承做放款金額與利率 as a per-release PDF and offers no open-data CSV: "
        "<i>A13Rate.csv</i> carries the posted 指數房貸 rate, a different series, and 內政部's file is "
        "quarterly and covers all lenders. So it now declares itself typed, and both editions print "
        "that beside the figure rather than letting it pass for derived.",
    ])))
    A(P("Found while preparing this edition", "h2"))
    A(callout(
        "A rebuild from identical inputs and identical code did not reproduce the published payload. "
        "Thirty fields differed, every one of them in the 內政部 low-use table, and all of them the "
        "same seven rows in reverse order. The cause was a sort: sorting on the period column with "
        "<i>sort_values</i> defaults to a non-stable quicksort, and once the frame is filtered to "
        "the latest period "
        "every key is tied — so the surviving row order was a property of the installed pandas, not "
        "of the data.<br/><br/>"
        "On its own that is a reproducibility hole. But both editions of this paper read that array "
        "<i>by position</i> — the last row as the national rate, row 5 as Taipei, row 1 as Tainan — "
        "so a rebuild under a different pandas printed Kaohsiung's rate as the national one and "
        "swapped the two cities. Three confidently labelled wrong numbers, with the PDF building "
        "cleanly and every test passing. Both reports now look rows up by county code and never by "
        "position, the row order is pinned regardless, and a test shuffles the rows and asserts the "
        "rendered figures do not move.",
        "A sort that was not a total order"))
    A(P("Still open", "h2"))
    A(KeepTogether(bullets([
        "<b>quants.tw itself is still unbound on Railway</b>, so the interactive version of this work "
        "— the sliders, the per-district pages — runs nowhere. The static page carries the findings; "
        "it does not carry the tool. The runbook is <i>docs/RAILWAY_GO_LIVE.md</i> on the housing branch.",
        f"<b>The mortgage figure is behind its source.</b> It reads "
        f"{bm['mortgage']['period_en']}, and the CBC has since published through 115.9 "
        "(September 2026). A transcribed number cannot refresh itself, which is the standing cost of "
        "a series with no machine-readable source; it should be re-read whenever this paper is "
        "revised. It is used only as a reference rate beside the net yield, never inside a "
        "calculation.",
        "<b>Per-building URLs</b> (/housing/b/&lt;key&gt;) were never built, because there was no live "
        "site to link to.",
        "<b>The rental-vacancy level</b> remains an assumption; only its shape is measured (§14).",
    ])))
    A(P("Data that could be added next", "h2"))
    A(P("A scouted and critic-checked menu lives in <i>docs/HOUSING_NEXT_DATA.md</i>. Its \"do first\" "
        "items (volume series, lease-stated management fees, parking audit) were all shipped in v1.9–v2.0. "
        "The remaining useful sources are 法拍 at item level (blocked by 司法院), building-level tax "
        "micro-data (institutions only) and a national 門牌 geocoder (TGOS, institutions only). All "
        "three are blocked by eligibility, not effort."))
    A(P("How to bring it back", "h2"))
    A(tbl([["Step", "Command / action"],
           ["Check out the code", "git checkout feat/housing   (or the tag housing-parked-2026-09-29)"],
           ["Run locally", "SECRET_KEY=devtestkey QUANTS_SUBJECT=housing venv/bin/python3 app.py"],
           ["Rebuild the payload", "venv/bin/python3 src/underwrite.py   (needs the 207 MB season zips in data/lvr/)"],
           ["Verify reproduction", "bin/rebuild-housing.sh"],
           ["Tests", "venv/bin/python3 -m pytest tests/ -q   (265 in this repository; 919 was the whole source site)"],
           ["Read first", "docs/HOUSING_HANDOFF.md §0, §2, §11, §8"]],
          [38 * mm, FRAME_W - 38 * mm], wrap=(1,), size=7.8))
    A(Spacer(1, 6))
    A(P("The raw inputs (season zips, address files, 金拍 cache) are gitignored and live only on the "
        "local machine under <i>data/lvr</i>, <i>data/geo</i> and <i>data/fasc</i>. They are hashed in the "
        "payload, so a fresh download can be checked against the published build.", "note"))

    # ------------------------------------------------------------ references
    A(CondPageBreak(80 * mm))
    A(P("19  References", "h1"))
    A(P("Each work is here because a claim in this report leans on it, and the line under each entry "
        "says which. A reading list of what the subject ought to contain, rather than what the paper "
        "actually used, would be decoration."))
    heads = {
        "bounds": "Partial identification — the frame §6 works inside",
        "selection": "Selection in transaction data — why §5 is the finding and not a caveat",
        "pricerent": "Price and rent measured on the same property",
        "taiwan": "Taiwan",
        "method": "Method: attribution, and intervals under clustering",
        "law": "The law the registry's coverage rests on",
        "data": "Compared against — data, not literature",
    }
    for g in GROUP_ORDER:
        rows = entries(g)
        if not rows:
            continue
        A(P(heads[g], "h2"))
        for _k, r in rows:
            block = [P(f"{byline(r)}. <b>{r['title']}</b>. <i>{r['where']}</i>.")]
            if r.get("quote"):
                block.append(P(f"「{r['quote']}」", "note"))
            block.append(P(r["why"], "note"))
            A(KeepTogether(block))
    # Derive, don't type, applied to the bibliography: a work nothing cites is
    # either a citation that got dropped or decoration, and the build refuses
    # to produce a paper with either. cite() raises on the other direction.
    orphans = uncited()
    if orphans:
        raise SystemExit("references: nothing cites " + ", ".join(orphans))

    # ------------------------------------------------------------ appendix
    A(PageBreak())
    A(P("Appendix A — Provenance", "h1"))
    A(P(f"Payload v{prov['version']}, built {prov['built']} from commit {prov['commit']}. Source "
        f"snapshot digest {prov['source']['sha256']}."))
    A(tbl([["Season", "SHA-256", "bytes"]] +
          [[f["season"], f["sha256"], n0(f["bytes"])] for f in prov["source"]["files"]],
          [16 * mm, 128 * mm, 26 * mm], right=(2,), size=6.6))
    A(Spacer(1, 6))
    A(tbl([["Reference file", "SHA-256 (first 24)", "bytes"]] +
          [[f["path"], f["sha256"][:24] + "…", n0(f["bytes"])] for f in prov["refs"]["files"]],
          [68 * mm, 76 * mm, 26 * mm], right=(2,), size=6.6))
    A(PageBreak())
    A(P("Appendix B — Glossary", "h1"))
    gl = [
        ("實價登錄", "Taiwan's actual-price registration system for property transactions and leases."),
        ("坪 (ping)", "3.3058 m², the standard unit for Taiwanese floor area."),
        ("住宅大樓 / 華廈 / 公寓", "Tower (11+ floors, lift) / mid-rise (≤10 floors, lift) / walk-up (≤5 floors, no lift)."),
        ("透天厝", "1–3 storey single-family townhouse; 42.7% of dwellings and outside this analysis."),
        ("社會住宅包租代管", "Government-subsidised sublet and managed social-housing leases."),
        ("預售屋", "Pre-sale: a flat sold off-plan, before the building exists."),
        ("法拍 / 金拍", "Court-ordered auction / bank-collateral auction via 台灣金服. Different channels."),
        ("棟 / 宅 / 建號", "Building / dwelling / registered building number (roughly one per unit). Never divided by each other."),
        ("Gross yield", "12 × monthly rent ÷ price, parking removed from both."),
        ("Net yield", "Gross after holding tax, management fee, vacancy and age-scaled repairs."),
        ("Matched pair", "A sale and a whole-unit market lease in the same building within ±4 quarters."),
        ("Coverage", "Matched buildings ÷ all buildings with a residential sale in the window."),
        ("Partial identification", "Bounding a quantity for an unobserved population under stated assumptions instead of assuming it resembles the observed one."),
        ("Shapley value", "A filter's average contribution over every order in which filters could be applied."),
        ("民國", "ROC calendar; year + 1911 = Gregorian (民國115 = 2026). Seasons such as 115S2 = Apr–Jun 2026."),
    ]
    A(tbl([["Term", "Meaning"]] + [[a, b] for a, b in gl], [42 * mm, FRAME_W - 42 * mm], wrap=(1,)))
    return story


def lu_rate(moi, code):
    """A low-use rate BY COUNTY CODE ('all' is 全國).

    The order of moi.low_use.rows is not a contract and must never be indexed
    by position. It used to be: this read rows[-1] for the national rate,
    rows[5] for Taipei and rows[1] for Tainan, and those positions held only
    for the row order one pandas version happened to produce. Under another the
    same code printed Kaohsiung as the nation and swapped the two cities.
    Missing is an error, not a zero -- a silently absent county would otherwise
    read as a real 0% low-use rate.
    """
    for r in moi["low_use"]["rows"]:
        if r["county"] == code:
            return r
    raise KeyError(f"low_use: no row for county {code!r}")


def corr_price_yield(districts):
    xs = [d["price_ping"] for d in districts]
    ys = [d["yield"] for d in districts]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den


def main():
    global S
    with open(DATA, encoding="utf-8") as f:
        D = json.load(f)
    S = styles()
    doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title="Quants.tw Housing Pivot — Final Report",
                          author="Stanley (Quants.tw)", subject="Taiwan rental yield from 實價登錄")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    doc.build(build(D))
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
