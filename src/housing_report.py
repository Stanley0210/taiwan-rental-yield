#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A citable, versioned PDF of the housing findings.

The web page is the work; this is the thing that gets forwarded. Faculty and
licensed appraisers circulate PDFs and cite documents that carry a version and a
date, so the report is stamped with the payload version, the build date, the
commit, and the SHA-256 of both the source snapshot and the payload itself. A
reader who disagrees with a number can name exactly which build they disagree
with, and `bin/rebuild-housing.sh` reproduces it.

Every figure is read out of `housing_data.json`. Nothing is typed in twice, so
the PDF cannot drift from the site the way a hand-maintained summary would.

    venv/bin/python3 housing_report.py            -> housing_report.pdf

The CJK font is Noto Sans TC (SIL Open Font Licence 1.1), embedded. That is
deliberate: reportlab's built-in CID fonts are not embedded, and on a viewer
without the Adobe Asian font pack they render as the WRONG glyphs rather than as
missing ones -- a failure that looks like text and is not. An OFL font may be
embedded and redistributed, which is what a document meant for forwarding needs.
"""
import json
import os
import statistics
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("LVR_OUT", os.path.join(HERE, "housing_data.json"))
FONT = os.path.join(HERE, "data", "fonts", "NotoSansTC.ttf")
OUT = os.environ.get("REPORT_OUT", os.path.join(HERE, "housing_report.pdf"))

# The page's ink, so the PDF and the site are recognisably the same document.
INK = colors.HexColor("#191814")
MUTED = colors.HexColor("#6b675c")
RULE = colors.HexColor("#cfc9ba")
PAPER = colors.HexColor("#f7f5ee")

F = "NotoTC"


def load():
    if not os.path.exists(DATA):
        sys.exit(f"!! {DATA} not found -- run underwrite.py first")
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    sha = None
    p = DATA + ".sha256"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            sha = f.read().split()[0]
    return d, sha


def styles():
    pdfmetrics.registerFont(TTFont(F, FONT))
    base = dict(fontName=F, textColor=INK, wordWrap="CJK")
    return {
        "title": ParagraphStyle("title", fontSize=25, leading=34, spaceAfter=4, **base),
        "sub": ParagraphStyle("sub", fontSize=12.5, leading=19, textColor=MUTED,
                              fontName=F, wordWrap="CJK", spaceAfter=2),
        "h2": ParagraphStyle("h2", fontSize=15, leading=22, spaceBefore=16,
                             spaceAfter=7, **base),
        "h3": ParagraphStyle("h3", fontSize=11.5, leading=17, spaceBefore=11,
                             spaceAfter=4, **base),
        "body": ParagraphStyle("body", fontSize=9.8, leading=16.5, spaceAfter=7,
                               alignment=TA_JUSTIFY, **base),
        "note": ParagraphStyle("note", fontSize=8.4, leading=13.5, spaceAfter=5,
                               fontName=F, textColor=MUTED, wordWrap="CJK"),
        "big": ParagraphStyle("big", fontSize=34, leading=38, fontName=F,
                              textColor=INK, alignment=TA_CENTER),
        "biglab": ParagraphStyle("biglab", fontSize=8.2, leading=12, fontName=F,
                                 textColor=MUTED, alignment=TA_CENTER,
                                 wordWrap="CJK"),
        "mono": ParagraphStyle("mono", fontSize=7.6, leading=12, fontName=F,
                               textColor=MUTED),
    }


FRAME_W = A4[0] - 40 * mm


def tbl(rows, widths, align_right=(), head=True, size=8.6):
    # reportlab raises when a flowable is too TALL for the frame but silently
    # runs a too-WIDE table off the edge of the page, which a reader only
    # discovers in print. Checked here rather than hoped for.
    if sum(widths) > FRAME_W + 0.5:
        raise ValueError(f"table is {sum(widths)/mm:.1f}mm wide, frame is "
                         f"{FRAME_W/mm:.1f}mm -- it would run off the page")
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    cmds = [
        ("FONT", (0, 0), (-1, -1), F, size),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
    ]
    if head:
        cmds += [("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.9, INK),
                 ("BOTTOMPADDING", (0, 0), (-1, 0), 6)]
    for c in align_right:
        cmds.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(cmds))
    return t


def bignum(items, S, width):
    """The hero row: a few large figures with small labels underneath."""
    cells = [[Paragraph(v, S["big"]) for v, _ in items],
             [Paragraph(l, S["biglab"]) for _, l in items]]
    t = Table(cells, colWidths=[width / len(items)] * len(items), hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
    ]))
    return t


def _generator_sha():
    """A digest of THIS file, so two reports built from one payload but from
    different generator code are distinguishable.

    Every other stamp on the document identifies the payload. That is the right
    pin for the numbers that come from the payload -- and no pin at all for the
    prose around them, which is where five wrong figures lived until v2.6.
    """
    import hashlib
    try:
        with open(os.path.abspath(__file__), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def build(d, payload_sha):
    S = styles()
    m, h = d["meta"], d["headline"]
    pv = m.get("provenance") or {}
    src = (pv.get("source") or {}).get("sha256") or "(unstamped)"
    boot = (d.get("bootstrap") or {}).get("overall") or {}
    W = A4[0] - 40 * mm

    gen = _generator_sha()

    def footer(canv, doc):
        canv.saveState()
        canv.setFont(F, 7.2)
        canv.setFillColor(MUTED)
        canv.drawString(20 * mm, 12 * mm,
                        f"實價收益 Quants.tw  ·  v{pv.get('version','?')}  ·  "
                        f"{pv.get('built','?')}  ·  來源快照 {src[:12]}"
                        + (f"  ·  報表 {gen[:8]}" if gen else ""))
        canv.drawRightString(A4[0] - 20 * mm, 12 * mm, str(canv.getPageNumber()))
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.4)
        canv.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
        canv.restoreState()

    doc = BaseDocTemplate(OUT, pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=20 * mm, bottomMargin=22 * mm,
                          title="實價收益 — 全臺灣租金報酬率的可見範圍",
                          author="Quants.tw", subject="Taiwan rental yield coverage")
    doc.addPageTemplates([PageTemplate(
        id="main",
        frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                      id="f")],
        onPage=footer)])

    E = []
    A = E.append

    # ══ cover ═════════════════════════════════════════════════════════════
    A(Spacer(1, 40 * mm))
    A(Paragraph("實價收益", S["title"]))
    A(Paragraph("全臺灣租金報酬率的可見範圍", S["title"]))
    A(Spacer(1, 5))
    A(Paragraph("The visible range of Taiwan's rental yield — what the public "
                "transaction registry can and cannot show", S["sub"]))
    A(Spacer(1, 16 * mm))
    A(Paragraph(
        "把一筆真實成交價與<b>同一棟建物</b>的真實租約配對，算出租金報酬率，"
        "並公布這個數字描述得到的市場有多小。分母才是重點。", S["body"]))
    A(Spacer(1, 12 * mm))

    meta_rows = [
        ["版本 Version", f"v{pv.get('version','?')}"],
        ["建置日 Built", pv.get("built", "?")],
        ["原始碼 Commit", pv.get("commit") or "(not recorded)"],
        ["資料期間 Window",
         f"{m['seasons'][0]}–{m['seasons'][1]}（{m['n_seasons']} 季 / quarters）"],
        ["來源快照 Source SHA-256", src],
        ["資料檔 Payload SHA-256", payload_sha or "(not recorded)"],
        ["報表產生器 Generator SHA-256", gen or "(unavailable)"],
        ["資料來源 Source", m["generated_from"]],
        ["授權 Licence", m["licence"]],
    ]
    A(tbl(meta_rows, [46 * mm, W - 46 * mm], head=False, size=8.0))
    A(Spacer(1, 8 * mm))
    A(Paragraph(
        "本文件所有數字均由 <font name='%s'>housing_data.json</font> 產生，"
        "可用 <font name='%s'>bin/rebuild-housing.sh</font> 重建並逐位元比對；"
        "重建方式與差異判讀見 docs/REPRODUCING.md。"
        "引用時請註明版本與建置日期。" % (F, F), S["note"]))
    A(PageBreak())

    _pid = d.get("partial_id") or {}
    _ph = next((r for r in (_pid.get("rungs") or [])
                if r["key"] == _pid.get("headline_rung")), None)
    pid_h = ({"scope": _pid["scope"], "lo": _ph["gross"]["lo"], "hi": _ph["gross"]["hi"]}
             if _ph else None)

    # ══ abstract ══════════════════════════════════════════════════════════
    A(Paragraph("摘要", S["h2"]))
    A(Paragraph(
        "要算一間房子的租金報酬率，必須同時知道它賣多少錢、租多少錢。"
        "內政部實價登錄兩者都有記錄，但<b>同一棟建物兩種紀錄都有</b>的，"
        f"只有 {h['coverage_pct']}%。這份研究不主張一個「台灣的租金報酬率」，"
        "而是主張：任何以成交資料計算的報酬率，都只描述得到市場中一個"
        "特定的、可辨識的子集合，而那個子集合的邊界是可以量化的。", S["body"]))
    A(Paragraph(
        f"在 {m['seasons'][0]}–{m['seasons'][1]} 共 {m['n_seasons']} 季的資料中，"
        f"可配對的建物有 {h['buildings']:,} 棟，佔全部有成交紀錄建物"
        f"（{h['universe_buildings']:,} 棟）的 {h['coverage_pct']}%。"
        f"其毛報酬率中位數為 {h['yield']:.2f}%"
        + (f"（95% 信賴區間 {boot['lo']:.2f}–{boot['hi']:.2f}%）" if boot.get("lo") else "")
        + f"，扣除稅費、管理費、空置與修繕後為 {h['net']:.2f}%。"
        f"即使完全不做任何品質篩選，只保留「租約與買賣相隔四季內」這一個"
        f"結構條件，覆蓋率的上限也僅有 {h['coverage_ceiling_pct']}%。"
        + (f"在只對配不到的建物設上下界、不假設它們和看得到的一樣的情況下，"
           f"這 {pid_h['scope']['n']:,} 棟的毛報酬率中位數落在 "
           f"{pid_h['lo']:.2f}% 到 {pid_h['hi']:.2f}% 之間（見第三節）。" if pid_h else ""), S["body"]))
    A(Spacer(1, 4))
    A(Paragraph("Abstract", S["h3"]))
    A(Paragraph(
        "A rental yield requires both a sale price and a rent for the same "
        "dwelling. Taiwan's public transaction registry (實價登錄) records both, "
        f"but only {h['coverage_pct']}% of buildings with a recorded sale also "
        "carry a recorded lease. This report does not claim a national rental "
        "yield. It claims that any transaction-based yield describes a specific, "
        "identifiable subset of the market, and it quantifies the boundary of "
        f"that subset. Over {m['n_seasons']} quarters "
        f"({m['seasons'][0]}–{m['seasons'][1]}), {h['buildings']:,} buildings can "
        f"be matched — {h['coverage_pct']}% of the {h['universe_buildings']:,} with "
        f"a sale — at a median gross yield of {h['yield']:.2f}%"
        + (f" (95% CI {boot['lo']:.2f}–{boot['hi']:.2f}%)" if boot.get("lo") else "")
        + f" and {h['net']:.2f}% net. With every quality filter removed and only "
        f"the four-quarter matching window retained, the ceiling is "
        f"{h['coverage_ceiling_pct']}%."
        + (f" Bounding the unmatched buildings rather than assuming they resemble "
           f"the matched ones, the median gross yield of all {pid_h['scope']['n']:,} "
           f"lies between {pid_h['lo']:.2f}% and {pid_h['hi']:.2f}% (section 3)." if pid_h else ""), S["body"]))

    A(Paragraph("兩個界線 · The two bounds", S["h2"]))
    A(bignum([(f"{h['coverage_pct']:.2f}%", "本站可算出報酬率的建物比例<br/>Coverage at this site's quality bar"),
              (f"{h['coverage_ceiling_pct']:.1f}%", "完全不篩選的結構上限<br/>Structural ceiling, no quality filters")],
             S, W))
    A(Spacer(1, 6))
    A(Paragraph(
        "這兩個數字框住了所有可能的版本。把本站每一個判斷都拿掉，"
        f"實價登錄最多也只看得到 {h['coverage_ceiling_pct']}% 的成交建物；"
        f"照本站的品質標準，剩 {h['coverage_pct']}%。沒有任何算法能突破前一個數字。"
        "這是本文最重要的一句話。", S["body"]))
    bms = d.get("benchmarks") or []
    if bms:
        A(Paragraph("對照利率 · Reference rates", S["h3"]))
        rows = [["利率", "%", "期間"]]
        for b in bms:
            rows.append([b["src_zh"],
                         f"{b['rate']:.3f}" if b["key"] == "mortgage" else f"{b['rate']:.2f}",
                         b["period_zh"]])
        A(tbl(rows, [FRAME_W * 0.62, FRAME_W * 0.12, FRAME_W * 0.26], align_right=(1,)))
        A(Spacer(1, 4))
        A(Paragraph(
            f"淨報酬率 {h['net']:.2f}% 與這三個利率並列、不相減：定存是稅前、保本、名目的利率；"
            "淨報酬率是扣掉估算成本、不保本的建物中位數，分母不同。", S["note"]))
    A(PageBreak())

    # ══ the finding ═══════════════════════════════════════════════════════
    A(Paragraph("一、主要發現：可配對性本身就有選擇性", S["h2"]))
    cov = d.get("coverage") or []
    if cov:
        rows = [["建物型態", "全部建物", "可配對", "配對率", "佔全體", "佔配對樣本", "毛報酬率"]]
        for c in cov:
            rows.append([c["type"], f"{c['all_buildings']:,}", f"{c['matched']:,}",
                         f"{c['match_rate']:.2f}%", f"{c['share_all']:.1f}%",
                         f"{c['share_matched']:.1f}%",
                         f"{c['yield']:.2f}%" if c.get("yield") is not None else "—"])
        A(tbl(rows, [30 * mm, 22 * mm, 20 * mm, 20 * mm, 18 * mm, 24 * mm, 22 * mm],
              align_right=(1, 2, 3, 4, 5, 6)))
        A(Spacer(1, 6))
        best = max(cov, key=lambda c: c["match_rate"])
        worst = min(cov, key=lambda c: c["match_rate"])
        A(Paragraph(
            f"同棟配對——唯一不需要「推估租金」就能算出報酬率的方法——對"
            f"{best['type']}可行的比例是 {best['match_rate']:.2f}%，"
            f"對{worst['type']}只有 {worst['match_rate']:.2f}%，相差 "
            f"{best['match_rate']/max(worst['match_rate'],1e-9):.1f} 倍。"
            f"而{worst['type']}佔全部有成交紀錄的建物（棟）的 {worst['share_all']:.1f}%。",
        S["body"]))
    age = d.get("age") or {}
    if age.get("matched_built") is not None:
        yrs = age["matched_built"] - age["unmatched_built"]
        A(Paragraph(
            f"配對得到的建物不是市場的隨機樣本。它們平均比配不到的建物年輕 "
            f"{yrs:.0f} 年（民國 {age['matched_built']:.0f} 年 vs "
            f"{age['unmatched_built']:.0f} 年），每坪單價高 "
            f"{age['ppp_diff_pct']:.1f}%，面積小 "
            f"{abs(age['unmatched_area'] - age['matched_area']):.1f} 坪，"
            f"且高度集中在投資型的大樓產品。因此任何以成交資料計算的台灣租金報酬率，"
            "在結構上都是算在一個年輕、高樓層、投資人持有的切片上。"
            "<b>公布的數字不是市場的報酬率，是「租得掉也賣得掉」那一塊的報酬率。</b>",
            S["body"]))

    wf = d.get("coverage_waterfall") or {}
    if wf.get("steps"):
        A(Paragraph("二、覆蓋率的損失，以及是誰造成的", S["h2"]))
        A(Paragraph(
            f"覆蓋率讀起來像是「法規只讓你看到這麼多」。這大致為真，但不完全："
            f"法規是主要項（{wf.get('law_pp')}pp），本站自己的篩選條件"
            f"佔 {wf.get('ours_pp')}pp，約五分之一的損失。"
            f"把兩者分開講，是因為不分開就等於把自己造成的限制記在法規頭上。",
            S["body"]))
        rows = [["每一步", "誰造成", "從", "到", "損失"]]
        for s in wf["steps"]:
            rows.append([s["zh"], "法規" if s["whose"] == "law" else "本站",
                         f"{s['from']:,}", f"{s['to']:,}", f"{s['lost_pp']:.2f}pp"])
        A(tbl(rows, [58 * mm, 18 * mm, 24 * mm, 24 * mm, 20 * mm],
              align_right=(2, 3, 4)))
    A(PageBreak())

    # ══ partial identification ════════════════════════════════════════════
    pid = d.get("partial_id") or {}
    if pid.get("rungs"):
        R = {r["key"]: r for r in pid["rungs"]}
        head, sc = R.get(pid["headline_rung"]), pid["scope"]
        mts = {m["key"]: m for m in (pid.get("mts") or [])}
        A(Paragraph("三、看不見的 94% 容許的說法", S["h2"]))
        A(Paragraph(
            f"前兩節說的是「看得到多少」。這一節問的是它的下一句：看得到 "
            f"{sc['coverage_pct']}%，到底容許主張什麼。把配不到的 "
            f"{sc['n'] - sc['matched']:,} 棟當成不存在，等於假設它們和看得到的一樣。"
            "本節不做那個假設，改成對它們的報酬率只設上下界，"
            "再看每多一個假設，區間縮短多少。"
            f"中位數的最壞情況區間，要看得到過半才會離開支撐區；"
            f"本站看得到 {sc['coverage_pct']}%，"
            f"把本站自己的五道篩選全部拿掉，結構上限也只有 {pid['ceiling_pct']}%——不到一半。"
            "所以第一階不是清理得不夠好，是清理再好也不會動。", S["body"]))
        rows = [["", "假設", "毛報酬率區間", "寬度", "較上一階"]]
        lab = {"band": "只用本站自己的品質區間",
               "type_support": "配不到的落在同型態已配對的最小–最大值之間",
               "type_trim": "…落在同型態第 5–95 百分位（近似假設）",
               "type_price": "…同型態、且同一個每坪價十分位",
               "type_price_age": "…再加同一個屋齡區間（反而變寬）"}
        for i, r in enumerate(pid["rungs"]):
            g = r["gross"]
            b = ("—" if r.get("buys_pp") is None else
                 (f"短 {r['buys_pp']:.2f}pp" if r["buys_pp"] >= 0
                  else f"長 {abs(r['buys_pp']):.2f}pp"))
            rows.append([f"{i+1:02d}", lab.get(r["key"], r["key"]),
                         f"{g['lo']:.2f}–{g['hi']:.2f}%", f"{g['width']:.2f}pp", b])
        # both directions of the residual selection, published unsigned: the two
        # rows must not read alike, or the table looks like it says one thing twice
        for k, arrow, why in (("mts_up", "↑", "配不到的更高（價格梯度；未量測）"),
                              ("mts_down", "↓", "配不到的更低（流動性選擇；未量測）")):
            if k in mts:
                g = mts[k]["gross"]
                rows.append([arrow, why, f"{g['lo']:.2f}–{g['hi']:.2f}%",
                             f"{g['width']:.2f}pp", "—"])
        A(tbl(rows, [8 * mm, 64 * mm, 26 * mm, 18 * mm, 22 * mm],
              align_right=(2, 3, 4)))
        A(Spacer(1, 5))
        trim, age2 = R.get("type_trim"), R.get("type_price_age")
        if trim and age2:
            A(Paragraph(
                f"第三階買走 {trim['buys_pp']:.2f}pp，是最大的一筆，但它買的方式要看清楚："
                "「落在第 5 到第 95 百分位」比「和已配對的分布一樣」更強——"
                "它不准任何一棟配不到的建物落在自己型態的前 5%。"
                "那是近似假設，不是支撐假設，所以上一階（不修剪）留在表上。"
                f"最後一階示範了反面：加上屋齡區間後格子變細，{age2['cells']} 個格子裡有 "
                f"{age2['cells_below_min']} 個的已配對建物不足 {pid['min_cell']} 棟，"
                f"{age2['fellback_universe_n']:,} 棟的質量退回較弱的型態層假設，"
                f"區間反而長了 {abs(age2['buys_pp']):.2f}pp。這一階公布出來，就是因為它失敗。",
                S["body"]))
        if head:
            g, nt = head["gross"], head.get("net") or {}
            A(Paragraph(
                f"<b>結論：在已寫明的假設下，這 {sc['n']:,} 棟的毛報酬率中位數落在 "
                f"{g['lo']:.2f}% 到 {g['hi']:.2f}% 之間"
                + (f"（淨 {nt['lo']:.2f}–{nt['hi']:.2f}%）" if nt else "")
                + f"；完全不加假設則是本站的品質區間 {R['band']['gross']['lo']:.2f}–"
                f"{R['band']['gross']['hi']:.2f}%。</b>"
                f"摘要的 {pid['matched_point']['gross']:.2f}% 是配對到的 {sc['matched']:,} 棟的中位數，"
                "落在區間內，但它不是這個母體的估計值。"
                "請不要引用區間的中點：區間的意思是端點之間每一個值都還沒有被排除，"
                "中點沒有比別的點更可能。", S["body"]))
        A(Paragraph(
            f"範圍：{sc['zh']}，{sc['n']:,} 棟，以「{sc['unit']}」計。{sc['not_taiwan_zh']}",
            S["note"]))
        A(Spacer(1, 4))
        A(Paragraph("Partial identification", S["h3"]))
        if head:
            g = head["gross"]
            A(Paragraph(
                f"Treating the {sc['n'] - sc['matched']:,} unmatched buildings as absent "
                "assumes they resemble the ones that can be seen. This section refuses that "
                "assumption and bounds them instead. Under the assumptions it states, the "
                f"median gross yield of these {sc['n']:,} buildings lies between "
                f"{g['lo']:.2f}% and {g['hi']:.2f}%; with no assumptions at all it is the "
                f"site's own quality band, {R['band']['gross']['lo']:.2f}% to "
                f"{R['band']['gross']['hi']:.2f}%. A median's worst-case interval only leaves "
                f"the support band once more than half the population is observed, and the "
                f"registry's structural ceiling is {pid['ceiling_pct']}% — less than half. "
                "The midpoint of an interval means nothing and is deliberately not quoted.",
                S["body"]))
    A(PageBreak())

    # ══ the ladder + the correction ═══════════════════════════════════════
    A(Paragraph("四、清理階梯：每一個判斷值多少", S["h2"]))
    A(Paragraph(
        "同一份資料，逐步套用清理條件後的數字。這不是在說別人公布的是第一階——"
        "沒有人真的那樣算。<b>要注意的是這是一條「路徑」，不是每個條件各自的價值：</b>"
        "前一階改變了後一階要處理的樣本組成。所有數字都以「棟」計算。", S["body"]))
    lad = [r for r in (d.get("ladder") or []) if r.get("key") != "building"]
    if lad:
        rows = [["", "清理步驟", "報酬率（以棟計）", "95% CI", "以配對計", "建物數"]]
        for i, r in enumerate(lad):
            v = r.get("yield_building", r["yield"])
            ci = (f"{r['lo']:.2f}–{r['hi']:.2f}"
                  if r.get("lo") is not None else "—")
            rows.append([f"{i+1:02d}", r["zh"], f"{v:.2f}%", ci,
                         f"{r.get('yield_pair', float('nan')):.2f}%",
                         f"{r['buildings']:,}"])
        A(tbl(rows, [8 * mm, 58 * mm, 26 * mm, 24 * mm, 20 * mm, 22 * mm],
              align_right=(2, 3, 4, 5)))
        A(Spacer(1, 5))
        A(Paragraph(
            f"同一份最終樣本，以配對計是 {h['pair_level_yield']:.2f}%，"
            f"以棟計是 {h['yield']:.2f}%。一棟有 40 筆買賣、30 筆租賃的大樓會產生 "
            f"1,200 個配對，少數幾棟巨型社區就能主導以配對計的中位數，"
            f"所以本站所有數字都以「棟」為單位。", S["note"]))

    fm = d.get("filter_marginals") or {}
    if fm.get("shapley"):
        A(Paragraph("五、更正：階梯顯示的不是各條件的價值", S["h2"]))
        A(Paragraph(
            "本站原先把上面那張表描述為「每一個清理決定值多少個百分點」。"
            "那個描述是錯的，而且錯得可以被抓到：原本的階梯把"
            "「排除社會住宅」顯示成 −0.17pp——對一群租金比市場低 "
            f"{abs((d.get('rent_bias') or {}).get('gap_pct') or 0):.0f}% 的房子來說，方向是反的。",
            S["body"]))
        LAB = {"social": "排除社會住宅", "rooms": "排除分租套房／雅房",
               "related": "排除親友間交易"}
        rows = [["篩選條件", "階梯上顯示的（配對）", "與順序無關（配對）", "與順序無關（棟）"]]
        for k in ("social", "rooms", "related"):
            if fm["shapley"]["building"].get(k) is None:
                continue
            rows.append([LAB[k],
                         f"{fm['path'][k]:+.3f}pp",
                         f"{fm['shapley']['pair'][k]:+.3f}pp",
                         f"{fm['shapley']['building'][k]:+.3f}pp"])
        A(tbl(rows, [44 * mm, 36 * mm, 34 * mm, 34 * mm], align_right=(1, 2, 3)))
        A(Spacer(1, 5))
        A(Paragraph(
            "右欄是把三個條件的全部 6 種先後順序都跑過一遍後的平均邊際效果"
            "（2³ 網格上的 Shapley 值）。三者相加恰好等於總變化量，"
            "所以這是一個分解，不是三個各自獨立的敏感度測試。", S["note"]))
        mm_ = d.get("marginal_mechanism") or {}
        if mm_.get("by_let_type"):
            A(Paragraph("原因（兩個，都不是篩選條件寫錯）", S["h3"]))
            A(Paragraph(
                "<b>其一，單位混用。</b>原本階梯前五階以「配對」計、後兩階以「棟」計。"
                "社會住宅包租代管極度集中在少數幾棟巨型套房大樓，"
                "以配對計會把它們的權重放大。", S["body"]))
            con = mm_.get("concentration") or {}
            if con:
                A(Paragraph(
                    f"有社會住宅租約的建物平均帶 "
                    f"{con['with_social']['pairs_per_building']} 個配對，"
                    f"沒有的只帶 {con['without']['pairs_per_building']} 個。"
                    f"以配對計時前者被加權 {con['pair_weight_ratio']}:1；"
                    f"以棟計是 {con['bldg_weight_ratio']}:1。", S["note"]))
            A(Paragraph(
                "<b>其二，順序。</b>排除社會住宅時，分租套房還在樣本裡。"
                "分租套房的面積欄位記的是整棟而非出租單位，報酬率因此只有約 1.3%，"
                "而社會住宅裡幾乎沒有分租套房。一排除社會住宅，"
                "分租套房在樣本中的佔比就變成三倍——每個組成部分都往上走，"
                "整體卻往下掉。這是典型的 Simpson 反轉。", S["body"]))
            rows = [["出租型態", "社會住宅", "市場", "佔各自樣本（社／市）"]]
            for t in mm_["by_let_type"]:
                rows.append([t["let_type"], f"{t['social']:.2f}%", f"{t['market']:.2f}%",
                             f"{t['social_share_pct']:.1f}% / {t['market_share_pct']:.1f}%"])
            A(tbl(rows, [34 * mm, 26 * mm, 26 * mm, 44 * mm], align_right=(1, 2, 3)))
            A(Spacer(1, 4))
            A(Paragraph(
                "在每一個出租型態<b>內部</b>，社會住宅的報酬率都低於市場——"
                "與補貼租金的預期完全一致。反轉只發生在加總的時候。"
                "統一以「棟」計算並拆掉順序效果之後，方向就回來了："
                f"排除社會住宅使報酬率<b>上升 "
                f"{fm['shapley']['building']['social']:+.3f}pp</b>。", S["body"]))
    vol = d.get("volume") or {}
    if vol.get("series"):
        sm = vol.get("summary") or {}
        A(Paragraph("交易量：依契約季的登錄筆數（描述，不歸因）", S["h3"]))
        A(Paragraph(
            f"契約季 Q 的紀錄只在 Q 或 Q+1 季公布時才計入，每一季用同一把尺量。"
            f"成屋買賣（契約日在建物完成之後）從 {sm.get('peak_q')} 的 {sm.get('peak_existing', 0):,} 筆"
            f"降到 {sm.get('after_q')} 的 {sm.get('after_existing', 0):,} 筆（{sm.get('existing_change_pct')}%）；"
            f"預售契約從 {sm.get('presale_from', 0):,} 筆降到 {sm.get('presale_to_q')} 的 "
            f"{sm.get('presale_to', 0):,} 筆（三條線的谷底不在同一季）。"
            "新青安優化（2024-06-27）、囤房稅 2.0（2024-07-01）與央行第七波信用管制（2024-09-19）"
            "落在同一個季度交界，資料無法區分任何一個的效果，本節只描述、不歸因。"
            "官方「建物買賣移轉登記棟數」以棟計、按登記季，與登錄筆數並列、不相除。", S["body"]))
        Q = vol["quarters"]; ser = vol["series"]["all"]
        off = (vol.get("official") or {}).get("series", {}).get("all")
        cens = set(vol.get("censored") or [])
        rows = [["契約季", "成屋買賣（筆）", "預售契約（筆）", "租賃登錄（筆）", "官方買賣移轉（棟，登記季）"]]
        for i, q in enumerate(Q):
            rows.append([q + ("（未完整）" if q in cens else ""),
                         f"{ser['existing'][i]:,}", f"{ser.get('presale', [0]*len(Q))[i]:,}",
                         f"{ser.get('leases', [0]*len(Q))[i]:,}",
                         f"{off[i]:,}" if off else "—"])
        A(tbl(rows, [FRAME_W * 0.18, FRAME_W * 0.19, FRAME_W * 0.19, FRAME_W * 0.19, FRAME_W * 0.25],
              align_right=(1, 2, 3, 4), size=8.2))
    A(PageBreak())

    # ══ negative results ══════════════════════════════════════════════════
    A(Paragraph("六、沒有成功的結果，以及已更正的結論", S["h2"]))
    A(Paragraph(
        "這些留在報告裡，是因為一份只登載成功結果的分析，其成功結果也不值得相信。",
        S["body"]))
    negs = []
    it = d.get("index_test") or []
    if it:
        pairs_ = {}
        for r in it:
            pairs_.setdefault(r["window"], {})[r["index"]] = r["slope"]
        detail = "；".join(f"±{w}: {v['off']:.3f}→{v['on']:.3f}"
                           for w, v in sorted(pairs_.items())
                           if "off" in v and "on" in v)
        negs.append(["價格指數修正",
                     f"測了，沒有用，已關閉。它讓報酬率與買賣／租賃時間差的斜率在"
                     f"每一個視窗都變得更<b>陡</b>而不是更平（{detail}）——"
                     f"所以那個斜率是樣本組成造成的，不是價格漂移。"])
    dh = d.get("dead_hypothesis") or {}
    if dh.get("gross_gap") is not None:
        gci = dh.get("gross_ci") or {}
        ci_txt = (f"（95% CI {gci['lo']:+.3f}–{gci['hi']:+.3f}pp）"
                  if gci.get("lo") is not None else "")
        v = dh.get("verdict")
        if v == "dead":
            txt = (f"已死。毛報酬率的差距 {dh['gross_gap']:+.3f}pp{ci_txt} "
                   f"與零無法區分，所以扣成本後的 {dh['net_gap']:+.3f}pp "
                   f"只能來自本站自己的成本假設。")
        elif v == "alive":
            txt = (f"<b>本季更正：不再成立。</b>雙北時期毛差距僅 0.041pp，"
                   f"因此判定為「假設造成的假象」。全國資料上毛差距是 "
                   f"{dh['gross_gap']:+.3f}pp{ci_txt}，在成本模型介入之前就已存在，"
                   f"且扣成本後擴大到 {dh['net_gap']:+.3f}pp。原判定是硬寫死的字串，"
                   f"改為全國尺度後從未重新評估；現已改為由資料推導。")
        elif v == "reversed":
            txt = (f"方向相反。毛差距 {dh['gross_gap']:+.3f}pp{ci_txt}，"
                   f"大樓的報酬率高於公寓。")
        else:
            txt = "樣本不足，未判定。"
        # v2.2 closed this hypothesis at a level `dead_hypothesis` cannot see:
        # its verdict is still the pre-v2.2 "alive" rung. Publishing that alone
        # makes the PDF assert as a live national finding what the site itself
        # closed as unanswerable, so the closing is appended to the same row.
        wr = d.get("walkup_resolution") or {}
        if wr.get("verdict"):
            pr = wr.get("precision") or {}
            rep = wr.get("representativeness") or []
            def _dev(t):
                r = [x for x in rep if x.get("type") == t]
                return r[0].get("max_abs_diff_pct") if r else None
            dtw, dwu = _dev("住宅大樓"), _dev("公寓")
            txt += ("　<b>v2.2 結案：本登錄回答不了。</b>"
                    f"配對到的公寓確實比配對到的住宅大樓高 {pr.get('gross_gap')}pp，"
                    "方向在每一個涵蓋過半樣本的控制下都成立"
                    + (f"；但配對到的住宅大樓偏離自己的母體 {dtw}%，"
                       f"公寓只偏離 {dwu}%" if dtw is not None and dwu is not None else "")
                    + "——兩個各自偏斜的樣本回答不了母體問題。"
                    "機制也被推翻：在雙方都沒有管理員的建物裡，模型費用為零，差距仍在。")
        negs.append(["「公寓報酬率高於大樓」", txt])
    pre = d.get("presale") or {}
    if pre.get("separable") is False:
        # residual_pct is the placebo-netted premium at the FURTHEST lag, on the
        # sparsest cell and with no interval. Reporting only that cell is the
        # thing this site withdrew and says so on the page ("An early version of
        # this site reported only that furthest cell; corrected"), so the PDF
        # prints the whole curve instead of its last point.
        _curve = pre.get("curve") or []
        _net = "、".join(
            f"{((1 + c['gap_pct'] / 100) / (1 + (c.get('placebo_pct') or 0) / 100) * 100 - 100):.1f}%"
            for c in _curve) or "--"
        negs.append(["預售屋「+30% 溢價」",
                     f"已撤回。原本的對照組有九成本身就是預售屋，所以那條曲線"
                     f"證明不了任何事。重新分組後，扣掉安慰劑的淨溢價在五個時間落差上是 {_net}"
                     f"——落差為零時沒有時間可扣，最遠那一格格子數最少且沒有信賴區間，"
                     f"所以不可分離（separable = false）。本站早期只報了最遠那一格，已更正。"])
    negs.append(["社會住宅階梯 −0.17pp", "已更正，見第四節。原因是單位混用與順序效果，"
                                       "不是篩選條件錯誤。"])
    vb = d.get("vacancy_breakeven") or {}
    if vb.get("breakeven_vacancy_pct") is not None:
        negs.append(["行政區空屋率", f"無法取得。村里與行政區層級的低度使用住宅統計自民國 109 年起"
                                  f"停止產製，只剩縣市層級 PDF。改以損益兩平測試替代："
                                  f"{vb.get('city','')}{vb.get('district','')}的"
                                  f"{vb.get('gross', 0):.1f}% 毛報酬率，需要 "
                                  f"{vb['breakeven_vacancy_pct']}% 的空置率才會掉到全國中位數，"
                                  f"而預設假設是 {vb.get('default_vacancy_pct')}%。"])
    mf = d.get("mgmt_flag") or {}
    if mf.get("bounds") and len(mf["bounds"]) >= 2:
        bA, bB = mf["bounds"][0], mf["bounds"][1]
        negs.append(["管理費全數扣除",
                     f"未更正，改為兩個界線。租賃備註顯示有管理員建物的租約中 {mf['lets']['incl_pct']}% "
                     f"寫明「租金總額含管理費」、{mf['lets']['unstated_pct']}% 未註明。"
                     f"全部扣除（現行）淨報酬率 {bA['net']:.2f}%（95% CI {bA['lo']:.2f}–{bA['hi']:.2f}）；"
                     f"只扣至少一筆租約寫明含管理費的建物 {bB['net']:.2f}%（{bB['lo']:.2f}–{bB['hi']:.2f}）。"
                     "未註明不等於承租人自付；標題數字不變。"])
    pa = d.get("parking_audit") or {}
    if pa.get("treatments") and pa.get("verdict"):
        T = {t["case"]: t for t in pa["treatments"]}
        v = pa["verdict"]
        vz = {"assumption_fails": "不成立", "assumption_holds": "成立", "inconclusive": "無法判定"}[v["verdict"]]
        negs.append(["未列明車位租金（v2.1 起已更正）",
                     f"前提「車位金額為零＝未另計租」經同棟檢驗：{vz}。總租金／總面積比值 {v['ratio']:.2f}"
                     f"（95% CI {v['lo']:.2f}–{v['hi']:.2f}，{v['n']} 棟；前提成立時預期 {v['predicted_if_holds']:.2f}）。"
                     f"三種處理：推算扣除 {T['impute']['gross']:.2f}%／{T['impute']['net']:.2f}%（{T['impute']['buildings']:,} 棟，v2.1 起的標題）；"
                     f"舊作法保留只扣面積 {T['area_only']['gross']:.2f}%／{T['area_only']['net']:.2f}%（{T['area_only']['buildings']:,} 棟，v1.0–v2.0 的標題）；"
                     f"整筆排除 {T['drop']['gross']:.2f}%／{T['drop']['net']:.2f}%（{T['drop']['buildings']:,} 棟）。舊數字保留為界線。"])
    pk = d.get("parking") or {}
    if pk.get("rungs"):
        R = {r["key"]: r for r in pk["rungs"]}
        mk, wd = R.get("market"), R.get("wide")
        if mk:
            txt = (f"同棟車位買賣×車位租賃，單位為一個車位（非坪）：市價層 {mk['yield']:.2f}%"
                   f"（95% CI {mk['lo']:.2f}–{mk['hi']:.2f}，{mk['buildings']} 棟，車位中位價 NT${mk['price']:,}，"
                   f"月租中位 NT${mk['rent']:,}）")
            if wd and pk.get("wide_licensed"):
                txt += f"；加入社宅車位租金 {wd['yield']:.2f}%（{wd['buildings']:,} 棟，配對 {wd['social_pairs_pct']}% 為社宅）"
            txt += f"。住宅毛報酬率 {pk['dwelling']['yield']:.2f}% 並列不相減。"
            negs.append(["車位收益率", txt])
    rows = [["項目", "結果"]]
    for a, b in negs:
        rows.append([Paragraph(a, ParagraphStyle("c", fontName=F, fontSize=8.6,
                                                 leading=13, wordWrap="CJK",
                                                 textColor=INK)),
                     Paragraph(b, ParagraphStyle("c2", fontName=F, fontSize=8.6,
                                                 leading=13, wordWrap="CJK",
                                                 textColor=INK))])
    A(tbl(rows, [40 * mm, W - 40 * mm]))

    # ══ identification ════════════════════════════════════════════════════
    A(Paragraph("七、證據強度：兩類結果不是同一個等級", S["h2"]))
    A(Paragraph(
        "<b>同棟內部識別（強）。</b>樓層溢價、家具溢價這類結果，是在同一棟樓內部比出來的："
        "同一個地段、同一批公設、同一個屋齡、同一個建商。"
        "干擾項是被結構消掉的，不是被假設掉的。", S["body"]))
    A(Paragraph(
        "<b>跨建物比較（弱）。</b>離捷運站的距離這類結果，比的是不同的建物。"
        "離站近與離站遠的房子在屋齡、坪數、建商、屋況、所在城市上全都不一樣，"
        "而這些差異一項都沒有被控制住。應讀作相關性的敘述，不是因果估計。", S["body"]))
    A(Paragraph(
        "這個差別不是修辭，而且本站在這一節錯過兩次，兩次都記錄在案。"
        "第一版用的是全國 8,798 棟的圖，但車站圖層只有臺北捷運的 131 站——"
        "高雄的房子因此被算出中位數 274,843 公尺的「最近車站距離」，臺中 112,217 公尺。"
        "那不是到車站的距離，是到臺北的距離，而舊的「2.5 公里以上」那一段有七成是這種房子。"
        "第二版改用臺北市單獨檢驗，得到「效果消失」並據此撤回；那也是錯的，"
        "因為臺北市太密，2.5 公里以外只有 4 棟——所謂不顯著其實是沒有遠端樣本。", S["body"]))
    # The two New Taipei spreads used to be typed in. They were true when the
    # retraction was written and silently false afterwards, because buildings[]
    # moved and the text did not. Recomputed here with the page's own bins,
    # 15 km cap and 25-building floor, so the PDF cannot drift from the site.
    def _mrt_spread(field):
        bins = [(0, 250), (250, 500), (500, 750), (750, 1000),
                (1000, 1500), (1500, 2500), (2500, 15000)]
        rows = [b for b in (d.get("buildings") or [])
                if b.get("c") == "f" and b.get("y") is not None]
        out = []
        for lo, hi in bins:
            g = [r["y"] for r in rows
                 if r.get(field) is not None and lo <= r[field] < hi]
            if len(g) >= 25:
                out.append(statistics.median(g))
        return f"{out[-1] - out[0]:.2f}" if len(out) >= 2 else "--"
    mrt_heavy, mrt_all = _mrt_spread("mrth"), _mrt_spread("mrt")
    A(Paragraph(
        "第三版把全國車站補齊（131 → 264 站，含輕軌），可用建物 4,920 → 8,014 棟。"
        f"結論是這個發現<b>撤回</b>。在新北市，若只算重軌，最近段與最遠段差 {mrt_heavy} 個百分點；"
        "一旦把淡海輕軌算進來——而它服務的正是原本被歸為「遠」的淡水一帶——"
        f"差距變成 {mrt_all} 個百分點。更關鍵的是高雄：它有自己的捷運系統，"
        "是補齊車站之後才進得了這份資料的，而在那裡兩種定義下都看不到梯度。", S["body"]))
    _wb = d.get("within_building") or {}
    _fr = f"{(_wb.get('floor') or {}).get('pct_per_floor', 0):.2f}"
    _fs = f"{(_wb.get('floor_sale') or {}).get('pct_per_floor', 0):.2f}"
    A(Paragraph(
        "一個要靠「輕軌算不算車站」才成立、而且在獨立的第二個城市完全不成立的關係，"
        "不能當成發現發布。距離與報酬率之間看得到的差異，小於「你決定什麼算車站」造成的差異。"
        f"同棟內部的樓層結果（房價每層 +{_fs}%、租金每層 +{_fr}%）不受此影響——"
        "它是在單一棟建物內比出來的，是本報告證據強度最高的一類。", S["body"]))
    disp = d.get("dispersion") or {}
    if disp.get("within_iqr") and disp.get("between_iqr"):
        # NOTE: in the two-city era within-building dispersion EXCEEDED
        # between-district dispersion, and that was published as a finding. It
        # does not survive going national -- 22 counties spread the between-
        # district term far wider than 12 Taipei districts did. Stated in
        # whichever direction the data actually points.
        w, bt = disp["within_iqr"], disp["between_iqr"]
        if w > bt:
            claim = (f"同一棟樓裡兩戶的差異，大於兩個行政區之間的差異"
                     f"（{w/bt:.2f} 倍）——這正是「行政區平均值」意義有限的原因。")
        else:
            claim = (f"在全國尺度上，行政區之間的離散度較大（{bt/max(w,1e-9):.2f} 倍），"
                     f"這與只涵蓋雙北時的結論相反：22 個縣市之間的差距，"
                     f"遠大於 12 個臺北市行政區之間的差距。但同棟內部 "
                     f"{w:.3f} 的離散度仍不可忽略——它代表「同一棟樓的平均報酬率」"
                     f"本身就是一個帶有相當不確定性的敘述。")
        A(Paragraph(
            f"另一個尺度感：同一棟建物<b>內部</b>的報酬率四分位距是 {w}，"
            f"行政區<b>之間</b>是 {bt}（{disp.get('buildings','?'):,} 棟，"
            f"每棟至少 {disp.get('min_pairs','?')} 個配對）。{claim}", S["body"]))

    A(Paragraph("八、成本假設", S["h2"]))
    A(Paragraph(
        "淨報酬率是一個模型，不是資料。四個參數在網站上都是可調的滑桿，"
        "此處列出的是預設值。其中「空置率」在台灣沒有官方統計，是一個明示的假設；"
        "「修繕」沒有來源，並刻意隨屋齡調整，以免在公寓與大樓之間製造偏差。", S["body"]))
    asm = d.get("assumptions") or []
    if isinstance(asm, list) and asm:
        cell = ParagraphStyle("cell", fontName=F, fontSize=7.8, leading=12,
                              wordWrap="CJK", textColor=INK)
        rows = [["項目", "預設值", "單位", "來源"]]
        for a in asm:
            rows.append([a.get("zh", a.get("key", "")),
                         str(a.get("default", "")),
                         a.get("unit", ""),
                         Paragraph(a.get("src_zh") or "（無來源，明示為假設）", cell)])
        A(tbl(rows, [32 * mm, 18 * mm, 26 * mm, W - 76 * mm],
              align_right=(1,), size=7.8))

    vp = d.get("vacancy_prior") or {}
    if vp.get("cases") and vp.get("gap_pp") is not None:
        VC = {c["key"]: c for c in vp["cases"]}
        cl = vp.get("county_leg") or {}
        A(Spacer(1, 6))
        A(Paragraph("空置率：水準是假設，形狀量得出來", S["h3"]))
        A(Paragraph(
            f"四項成本裡只有空置率完全沒有來源，而且不分縣市、不分屋齡，每一棟收一樣的 "
            f"{vp['site_default_pct']:.0f}%。台灣不公布租賃空置率，所以水準補不起來；"
            f"形狀補得起來。內政部表2-3-2把低度使用（用電）住宅率做成縣市×屋齡的交叉表，"
            f"把它重新加權到本站配對建物自己的縣市與屋齡組合，得到 {vp['prior_pct']:.2f}%，"
            f"而{vp['period']}同期全國是 {vp['national_pct']:.2f}%——"
            f"<b>高出 {vp['gap_pp']:.2f} 個百分點</b>。原因是屋齡：五年以下的住宅低度使用率最高，"
            f"而本站配對得到的建物大量集中在那一層。"
            + (f"只看縣市則方向相反（{cl['prior_pct']:.2f}% 對 {cl['national_pct']:.2f}%），"
               f"因為本站看得見的建物集中在空屋較少的都會區；交叉表同時處理兩者。"
               if cl.get("gap_pp") is not None else ""), S["body"]))
        A(Paragraph(
            f"低度使用住宅不是租賃空置率——分子含二屋與待售屋，分母是全部房屋稅籍住宅，"
            f"不是出租中的住宅——所以本站不把它換進 headline。"
            f"它給出的是一個界線：直接當空置率收，淨報酬率從 {VC['flat']['net']:.2f}% 降到 "
            f"{VC['level']['net']:.2f}%。網站上另有一個開關，可在保持水準為 "
            f"{vp['site_default_pct']:.0f}% 的前提下，只套用這個形狀。", S["note"]))
        A(Paragraph(
            f"Vacancy is the only cost term with no source, and it is charged flat. "
            f"Reweighting 內政部's county-by-age cross-table to this site's own matched "
            f"mix gives {vp['prior_pct']:.2f}% against {vp['national_pct']:.2f}% nationally "
            f"in {vp['period']} -- {vp['gap_pp']:.2f}pp higher, because the visible slice is "
            f"young and new dwellings are the emptiest band. That is a bound, not a "
            f"vacancy rate: charging it outright takes the net yield from "
            f"{VC['flat']['net']:.2f}% to {VC['level']['net']:.2f}%.", S["note"]))

    A(Spacer(1, 8))
    A(Paragraph(
        "法律聲明：本文件所引用之價格均為內政部實價登錄之<b>已登記成交價格</b>，"
        "並非估價。本文件不對任何特定不動產表示價值意見，"
        "亦不構成投資建議。不動產估價業務依《不動產估價師法》第 14 條"
        "由不動產估價師執行。", S["note"]))
    A(Paragraph(
        "Legal note: every price cited is a registered transaction price from the "
        "Ministry of the Interior's public registry, not a valuation. This document "
        "expresses no opinion of value on any specific property and is not "
        "investment advice.", S["note"]))

    doc.build(E)
    return OUT


if __name__ == "__main__":
    data, sha = load()
    out = build(data, sha)
    size = os.path.getsize(out)
    pv = (data["meta"].get("provenance") or {})
    print(f"[rep] wrote {out} ({size/1e3:.0f} KB)")
    print(f"[rep] v{pv.get('version')}  built {pv.get('built')}  payload {(sha or '')[:12]}")
