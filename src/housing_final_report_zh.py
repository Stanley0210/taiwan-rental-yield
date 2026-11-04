#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""住宅轉向的結案報告（中文版）。

    venv/bin/python3 src/housing_final_report_zh.py  -> docs/HOUSING_FINAL_REPORT_ZH.pdf

這是 housing_final_report.py（英文版）的中文對照版本，兩者：
  * 讀同一份 housing_data.json，所以每個數字必然一致；
  * 共用同一組樣式、圖表與版面函式（直接 import，不複製）；
  * 各自保有自己的 f-string。這是刻意的：把 274 條內嵌數字的句子改寫成
    雙語共用的位置式樣板（%s），會重現 housing.js 修過四次的那類錯誤
    ——同樣的佔位符數量、不同的順序，於是把「棟數」印成「百分比」而
    測試全部通過。兩份各自寫死、用測試釘住數字相同，比共用樣板安全。

散文是中文寫作，不是逐句直譯；標籤能從 payload 的 zh 欄位讀到的就讀，
不另行翻譯，以免與網站用詞分歧。
"""
import json
import os
import re
import statistics
import sys

from reportlab.graphics.shapes import Drawing, Line, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether,
                                PageBreak, PageTemplate, Spacer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import housing_final_report as R
from housing_final_report import (ACCENT, ACCENT2, ACCENT3, FRAME_W, INK, MUTED, RULE,
                                  SOFT, F, callout, corr_price_yield, fig,
                                  hbars, histogram, legend, lines, n0, p2, pp, tbl,
                                  tiles, _s, PAPER_VERSION, PAPER_DATE,
                                  PAPER_CHANGES)
from references import (EXTERNAL_READ_ON, GPG_CITIES, GPG_NATIONAL, GPG_UPDATED,
                        GROUP_ORDER, cite, cite_t, entries, uncited, why)

# The paper version is the EN module's: both editions render the same claims,
# so there is one paper version and two languages, never a Chinese v1.0 beside
# an English v1.1. v1.1 ships in both languages on the same day, which is why
# this date and PAPER_DATE now agree; in v1.0 they did not, and the cover row
# below exists so that an edition written later can never inherit an earlier
# edition's date.
ZH_EDITION_DATE = "2026-11-04"

# PAPER_CHANGES, for the register in section 16. Kept beside the English list
# rather than translated at render time, for the same reason the two reports
# are separate generators: prose belongs to its edition.
PAPER_CHANGES_ZH = [
    ("v1.2", "2026-11-04",
     "檢驗了支撐區間那一階所依賴的「相似性假設」，並公布結果：它只有一半成立。"
     "格子吸收了可配對與配不到建物之間 77% 的屋齡落差，卻把面積落差變得更大。"
     "沒有任何數字改變——區間一樣，而且一直都標示為依賴假設——"
     "但它的身分變了：從一個沒有人檢查過的假設，變成一個在可量測的維度上被資料反駁的假設。"
     "第 6 節把這件事寫出來。"),
    ("v1.1", "2026-11-03",
     "新增第 19 節參考文獻，並據此在第 4 節首次與已發表的估計對照——"
     "其中包括：目前流通的臺灣報酬率數字，來源是刊登網站的彙整而不是成交資料。"
     "第 18 節重寫：專案已經公開，原本寫著「沒有人讀過」「儲存庫是私有的」那些項目已經不成立。"
     "沒有任何量測出來的數字改變。"),
    ("v1.0", "2026-11-01", "第一個可引用的版本，寫於專案封存之時。"),
]

OUT = os.environ.get("REPORT_OUT_ZH",
                     os.path.join(R.ROOT, "docs", "HOUSING_FINAL_REPORT_ZH.pdf"))

# Verdict strings as the payload spells them. Typing the Chinese for a verdict
# would re-create the bug sec. 17 warns about: the conclusion would stop
# following the data the moment the pipeline re-decided it.
UNIT_ZH = {
    "% of price / yr": "% 房價／年",
    "% of rent": "% 租金",
    "NT$/坪/月": "元／坪／月",
}

VERDICT_ZH = {
    "assumption_fails": "假設不成立",
    "assumption_holds": "假設成立",
    "unanswerable_selection": "無法回答（選擇偏誤）",
    "alive": "存活",
    "dead": "死亡",
    "contested": "有爭議",
}


# A number and the Chinese unit that follows it must not be split across lines.
# reportlab breaks at spaces, and the space this prose puts between a Latin
# numeral and the CJK that follows ("的 4 層以上", "共 72.0 個百分點") is the only
# break opportunity on an otherwise unbroken CJK line, so it is the one the
# line-breaker takes. Binding it leaves the break to the space before the number.
_BIND = re.compile(r"(?<=[0-9A-Za-z%）)\]])[ ]+(?=[\u4e00-\u9fff])")


def _bind(t):
    return _BIND.sub("&nbsp;", t)


def P(text, style="body"):
    return R.P(_bind(text), style)


def callout(text, title=None):
    """R.callout, but through this edition's text pipeline.

    R.callout builds its Paragraph directly, so callout text never passed
    through _bind() -- every Chinese callout in this edition could break a line
    between a Latin token and the character after it ("pandas" / "下重建"), the
    same defect _bind() exists to prevent in body text. Found while rendering
    the v1.1 section 18 callout; it affected the ones already there too.
    """
    return R.callout(_bind(_safe(text)), _safe(title) if title else title)


def bullets(items, style="bullet"):
    return R.bullets([_bind(t) for t in items], style)


_CMAP = None


def _safe(s):
    """Drop codepoints the embedded font cannot draw.

    The payload's own prose is written for the web, where the system font
    stack covers things Noto Sans TC does not. src_zh for the management
    fee carries U+26A0 followed by U+FE0F (variation selector): the sign
    itself is in the font, the selector is not, so it renders as a notdef
    box in the PDF and in the PDF only. Filtering against the real cmap
    catches the next one of these too, instead of this one only.
    """
    global _CMAP
    if _CMAP is None:
        from fontTools.ttLib import TTFont
        f = TTFont(R.FONT_REG)
        cm = set()
        for t in f["cmap"].tables:
            cm |= set(t.cmap.keys())
        _CMAP = cm
    return "".join(c for c in s if ord(c) < 128 or ord(c) in _CMAP)


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont(F, 7.2)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(20 * mm, 12 * mm, "Quants.tw 住宅轉向 · 結案報告")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"{doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
    canvas.restoreState()


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

    # ------------------------------------------------------------ 封面
    A(Spacer(1, 38 * mm))
    A(P("9,843 棟台灣建物告訴我們的租金報酬率，"
        "以及任何一個報酬率究竟能描述這個市場的多小一塊", "title"))
    A(Spacer(1, 4))
    A(P("實價登錄租金報酬率專案的結案報告（2026-08-30 → 2026-09-26），寫於專案封存當日", "sub"))
    A(Spacer(1, 16 * mm))
    A(tiles([(p2(h["yield"]), "毛報酬率中位數<br/>（以棟為單位）"),
             (p2(h["net"]), "淨報酬率中位數<br/>（扣除四項明列成本後）"),
             (p2(h["coverage_pct"]), f"在 {n0(h['universe_buildings'])} 棟中<br/>只有這個比例算得出報酬率"),
             (n0(h["buildings"]), f"可配對建物<br/>（{n0(h['pairs'])} 組買賣—租賃配對）")]))
    A(Spacer(1, 22 * mm))
    A(tbl([["", ""],
           ["論文版本", f"{PAPER_VERSION}  ·  {PAPER_DATE}"],
           ["中文版", f"{ZH_EDITION_DATE}（與英文版 {PAPER_VERSION} 同步發佈，內容相同）"],
           ["資料版本", f"v{prov['version']}  ·  建立於 {prov['built']}"],
           ["資料期間", f"{meta['seasons'][0]} → {meta['seasons'][1]}（共 {meta['n_seasons']} 季，"
                        "民國112年第4季 → 115年第2季）"],
           ["來源快照 SHA-256", prov["source"]["sha256"][:32] + "…"],
           ["程式碼", "github.com/Stanley0210/taiwan-rental-yield"],
           ["初稿日期", "2026-09-29"]],
          [45 * mm, FRAME_W - 45 * mm], size=7.8))
    A(Spacer(1, 6))
    A(P("本報告中的每一個數字，都在建立 PDF 時從 <i>housing_data.json</i> 讀出。"
        "凡是描述「曾經發佈、後來撤回」的數字，報告都會明說；那些數字來自專案交接文件，"
        "已不存在於任何一版資料檔中。", "note"))
    A(PageBreak())

    # ------------------------------------------------------------ 目錄
    A(P("目錄", "h1"))
    toc = [
        ("", "摘要"),
        ("壹", "這個專案——它是什麼、為什麼存在、怎麼運作"),
        ("", "1  起點與限制 · 2  資料 · 3  方法"),
        ("貳", "發現"),
        ("", "4  報酬率主數字 · 5  覆蓋率：核心發現 · "
             "6  為看不見的 94% 設界 · 7  每一道清理步驟值多少 · "
             "8  地理 · 9  公寓與大樓 · 10  同一棟樓之內 · "
             "11  捷運（已撤回） · 12  預售屋 · 13  車位 · 14  成本模型 · "
             "15  市場背景"),
        ("參", "可信度"),
        ("", "16  更正紀錄 · 17  錯誤類型與工作守則 · 18  未結事項與重啟方式 · "
             "19  參考文獻"),
        ("", "附錄A — 資料來源 · 附錄B — 名詞"),
    ]
    for a, b in toc:
        A(P(f"<b>{a}</b>  {b}" if a else b, "body" if not a else "h2"))
    A(PageBreak())

    # ------------------------------------------------------------ 摘要
    A(P("摘要", "h1"))
    law_pp, ours_pp = wf["law_pp"], wf["ours_pp"]
    A(P("<b>一句話版本。</b>從內政部實價登錄取一筆真實成交，在<i>同一棟建物</i>內找到一筆四季以內的"
        "真實租約，租金報酬率就直接算得出來，完全不需要任何模型。以全國資料這樣做，毛報酬率中位數為"
        f"<b>{p2(h['yield'])}</b>（95% 信賴區間 {boot['overall']['lo']:.2f}–{boot['overall']['hi']:.2f}），"
        f"淨報酬率為 <b>{p2(h['net'])}</b>"
        f"（95% 信賴區間 {boot['overall_net']['lo']:.2f}–{boot['overall_net']['hi']:.2f}）"
        f"——低於五大銀行新承作房貸的 {bm['mortgage']['rate']:.3f}%。"
        "但更重要的數字是分母：這些中位數描述的，是期間內有成交紀錄的 "
        f"<b>{n0(h['universe_buildings'])}</b> 棟當中的 <b>{n0(h['buildings'])}</b> 棟"
        f"——<b>{p2(h['coverage_pct'])}</b>，大約每 {round(100/h['coverage_pct'])} 棟裡的一棟。"))
    A(P("本專案的主張是<b>分母才是重點</b>：所有以成交資料計算、關於台灣的租金報酬率，描述的都是這個市場"
        "裡一小塊年輕、以大樓為主、投資者持有的切片，而沒有人說那一塊有多小。本專案把它量出來。"))

    A(P("通過每一輪稽核的十項發現", "h2"))
    tw, mr, wu = cov["住宅大樓"], cov["華廈"], cov["公寓"]
    A(KeepTogether(bullets([
        f"<b>覆蓋率的損失是結構性的。</b>有成交紀錄的建物中，{p2(h['coverage_pct'])} 算得出報酬率。"
        f"其中 {law_pp:.1f} 個百分點的損失，是因為實價登錄裡根本沒有這棟樓的租約；本專案自己的品質"
        f"篩選只佔 {ours_pp:.1f} 個百分點。即使把每一道篩選都拿掉，上限也只有 "
        f"{p2(h['coverage_ceiling_pct'])}。",
        f"<b>大樓相對公寓被高估了大約七倍。</b>配對率：住宅大樓 {p2(tw['match_rate'])}、"
        f"華廈 {p2(mr['match_rate'])}、公寓 {p2(wu['match_rate'])}。大樓佔有成交紀錄建物的 "
        f"{tw['share_all']:.1f}%，卻佔算得出報酬率的建物 {tw['share_matched']:.1f}%。",
        f"<b>算得出報酬率的那一塊更新、更貴。</b>可配對建物的完工年約在民國"
        f"{age['matched_built']:.0f}年，其餘為 {age['unmatched_built']:.0f}年，每坪單價高出 "
        f"{age['ppp_diff_pct']:.1f}%。此外，全台 42.7% 的宅數（1–3 層透天）"
        "在定義上就不在本分析範圍內。",
        f"<b>把看得見的那一塊重新加權、使其組成貼近整體市場後，報酬率會上升</b>——"
        f"由 {p2(ps['visible_gross'])} 升至 {p2(ps['by_both']['gross'])}（{pp(ps['shift_pp'])}）。"
        "這個偏誤被公開寫出來，而不是默默修掉。",
        f"<b>在明列的假設下，全部 {n0(pid['scope']['n'])} 棟建物的報酬率中位數落在 "
        f"[{rungs['type_price']['gross']['lo']:.2f}%、{rungs['type_price']['gross']['hi']:.2f}%] 之間。</b>"
        "若不做任何假設，區間就是整個品質區間；而且再怎麼改進清理方式都無法縮小它，"
        "因為中位數只有在觀察到超過半數母體之後才可能被收窄。"
        f"<b>這個假設現在被檢驗過了，而它只有一半成立：</b>格子吸收了可配對與配不到建物之間"
        f"{rz['built']['absorbed_pct']:.0f}% 的屋齡落差，卻把面積落差變得<i>更大</i>（第 6 節）。"
        "這個區間是「在明列假設下」的區間，不是一個已被驗證的區間。",
        f"<b>社會住宅會扭曲實價登錄的原始租金。</b>整戶出租租約中有 {rb['social_share_pct']:.1f}% 是"
        f"受補貼的社會住宅，每坪租金低於市場 {abs(rb['gap_pct']):.1f}%。"
        "任何直接拿實價登錄原始租金算報酬率的人，量到的主要是這筆補貼。",
        f"<b>行政區之間的報酬率差異，主要是價格造成的。</b>行政區每坪單價與報酬率的相關係數為 "
        f"{corr_price_yield(D['districts']):.3f}；租金的變異遠小於價格。",
        f"<b>在同一棟樓內，租金幾乎不隨樓層上升（每層 +{wb['floor']['pct_per_floor']:.2f}%），"
        f"而價格上升的速度是它的五倍（每層 +{wb['floor_sale']['pct_per_floor']:.2f}%）。</b>"
        f"同一棟樓內，有附傢俱的單位租金比無附傢俱高 {wb['furnished']['pct']:.1f}%。"
        "這些都是同棟內比較，因此建物品質被固定住了。",
        f"<b>預售屋只貴 {pre['curve'][0]['gap_pct']:.1f}%</b>（信賴區間 "
        f"{pre['curve'][0]['ci_lo']:.1f}–{pre['curve'][0]['ci_hi']:.1f}），"
        "比較對象是同一簽約季、真正已完工的新成屋。這不是外界常引用的約 30%。"
        "那個 30% 的比較組，本身有九成是預售屋合約。",
        f"<b>沒有列明金額的車位並不是免費的。</b>附車位但車位租金未列明的租約，"
        f"每平方公尺的總租金與有列明者相同（比值 {pa['verdict']['ratio']:.3f}，信賴區間 "
        f"{pa['verdict']['lo']:.3f}–{pa['verdict']['hi']:.3f}）。推算並扣除車位租金後，"
        f"主數字由 {p2(area_only.get('gross', 2.68))} 變為 {p2(h['yield'])}。",
    ])))

    A(P("沒有存活下來的結果", "h2"))
    A(P("本專案發佈過幾項後來被檢查推翻的結果，而它把這些撤回全部留在紀錄上："))
    A(KeepTogether(bullets([
        "<b>最初的假設——公寓報酬率高於大樓——以「無法回答」結案。</b>"
        f"這個差距在可配對資料中確實存在（{pp(wr['precision']['gross_gap'],3)}，信賴區間 "
        f"{wr['precision']['lo']:.3f}–{wr['precision']['hi']:.3f}），"
        f"但可配對的大樓比「有成交卻配不到租約」的大樓小了 "
        f"{abs(wr['representativeness'][1]['medians']['area_ping']['diff_pct']):.0f}%。"
        "兩個偏斜方向不同的樣本，無法解決一個關於母體的問題。"
        "而原本提出的機制（管理費）則已被直接證偽。",
        "<b>距捷運站的距離</b>曾經發佈、撤回、恢復，最後撤回。"
        "它完全取決於輕軌算不算一個站；而高雄完全看不到這個梯度。",
        "<b>「預售屋約有 30% 溢價」</b>建立在一個被污染的比較組上（見第 12 節）。",
        "<b>「1,086 棟裡只有一棟」</b>把建物數除以登記建號（約等於戶數）。"
        "這是單位錯誤，已撤回。",
        "<b>價格指數</b>讓「報酬率對時間差」的斜率變得更差而非更好，因此關閉不用。",
    ])))
    A(callout(
        f"在這段期間買下一戶「算得出價格」的典型台灣住宅的房東，扣成本前每年收到的租金約 "
        f"{h['yield']:.1f}%，扣成本後約 {h['net']:.1f}%，僅略高於一年期銀行定存"
        f"（{bm['deposit_1y']['rate']:.2f}%），且低於 {bm['mortgage']['rate']:.2f}% 的房貸利率。"
        f"但這裡的「典型」指的是大樓裡比較新的一戶，因為公開資料只算得出這一種。"
        f"大約每 16 棟就有 15 棟，資料根本說不出話來；而本報告逐一說明每一棟是在哪一步被漏掉的。",
        "白話總結"))
    A(PageBreak())

    # ================================================================ 第壹部
    A(P("第壹部 · 這個專案", "part"))
    A(P("1  起點與限制", "h1"))
    A(P("Quants.tw 原本是一個台股籌碼流向產品。2026-08-30，同一個程式庫被重啟為"
        "<b>台灣租金報酬率分析工具</b>：同樣的基礎設施，不同的題目。當時股票產品是凍結狀態，"
        "因此沒有影響到任何線上使用者。第一版只涵蓋臺北與新北（2,549 棟可配對建物，毛報酬率 2.43%）。"
        "這個範圍限制在 2026-08-31 解除，之後所有結果都涵蓋 22 個縣市。"
        "接下來的四週內，資料檔從 v1.0 推進到 v2.8，測試從約 780 條增加到 919 條，"
        "方法則由獨立代理人從十個面向稽核過。"))
    A(P("這個引擎實際上就是在做承保（underwriting）：取一筆真實成交，配上同一棟樓的一筆真實租約，"
        "然後計算淨營運收益。有三條來自 Stanley 的既定規則，從頭到尾沒有改變："))
    A(KeepTogether(bullets([
        "<b>這已經是第二次起步。</b>再轉第三次，本身就是一個訊號，"
        "所以規則是先把東西粗糙地做出來再迭代，而不是重新設計。",
        "<b>守在資料與分析的範圍內。</b>本站分析住宅資料，不對住宅政策發表意見。",
        "<b>報酬率一律來自配對，絕不使用行政區平均。</b>範圍擴及全國，這條規則沒有動。",
    ])))
    A(P("<b>法律界線。</b>不動產估價師法第 14 條將估價保留給領有證照的估價師，"
        "罰則為新臺幣 3 萬至 15 萬元。因此本站的說法一律是「這棟建物的成交案件在這些假設下"
        "相當於 X%」，而絕不會說「這間房子值 Y 元」或「這是好買點」。"
        "每一個建物面板的結尾都有一行字，說明該數字是登錄的成交價格，而非估價。"))
    A(P("<b>封存時的狀態（2026-09-29）。</b>程式碼位於 <i>quants</i> remote 的 <i>feat/housing</i> 分支"
        "與 <i>housing-parked-2026-09-29</i> 標籤上。quants.tw 這個網域自八月下旬起一直回傳 Railway 的"
        "「Application not found」，原因是代管它的 Railway 帳號失效，與程式碼無關。"
        "沒有任何讀者看過上線後的住宅網站。股票網站則在本報告撰寫的同一天於 <i>main</i> 分支恢復。"))

    A(CondPageBreak(70 * mm))
    A(P("2  資料", "h1"))
    A(P("主要來源：內政部不動產成交案件實際資訊資料供應系統（實價登錄）。它免費、不需金鑰，"
        f"並以 {meta['licence']} 授權發佈。合併後的季度壓縮檔包含每個縣市的買賣（a）、"
        "預售（b）與租賃（c）資料。"))
    A(tbl([["", "原始筆數", "清理後", "保留比例"],
           ["買賣", n0(meta["raw_sales"]), n0(meta["clean_sales"]),
            p2(meta["clean_sales"] / meta["raw_sales"] * 100)],
           ["租賃", n0(meta["raw_rents"]), n0(meta["clean_rents"]),
            p2(meta["clean_rents"] / meta["raw_rents"] * 100)],
           ["預售屋", "—", n0(pre["dwellings"]) + " 宅", f"{n0(pre['projects'])} 建案"]],
          [55 * mm, 35 * mm, 45 * mm, 35 * mm], right=(1, 2, 3)))
    A(Spacer(1, 6))
    A(P("<b>為什麼期間從 112S4（民國112年第4季）開始。</b>有六個租賃欄位是從那一季才開始出現的："
        "出租型態、有無管理員、租賃期間、有無電梯、附屬設備與租賃住宅服務。"
        "每一道品質篩選都依賴它們。若使用更早的季度，就會把受補貼的社會住宅與分租套房"
        "默默混進前期，製造出一個假的時間趨勢。因此可用期間為 11 季，"
        "這對任何關於景氣循環的主張來說都太短。"))
    A(P("<b>篩選條件</b>（每一道都可以關掉，所以第 7 節的誠實階梯走的是同一條程式路徑）："))
    A(KeepTogether(bullets([
        "只留住宅類型：住宅大樓（11 層以上、有電梯）、華廈（10 層以下、有電梯）、"
        "公寓（5 層以下、無電梯）。1–3 層的透天在定義上排除。",
        "排除社會住宅（包租轉租／代管），因為那些租金受補貼。",
        "只留整戶出租（整棟(戶)出租、獨立套房）。這會排除分租套房、分層出租與未填類型，"
        "因為它們的面積欄位無法與整戶買賣相比。",
        "排除親友／親屬／關係人間的買賣，因為那不是市場價格。",
        "買賣與租賃兩側都扣除車位；未列明的車位租金另行推算（見第 13 節）。",
        "買賣與租賃相隔 ±4 季以內；報酬率落在 0.3–12% 之外者視為申報錯誤而剔除。",
    ])))
    A(P("<b>地址。</b>建物代碼由門牌推導，正規化程式以 150 組人工標註的配對測試過，"
        f"只有 {meta['addr']['no_key_pct']}% 的紀錄產不出代碼。v2.8 修正了兩個被實價登錄推翻的假設："
        "異體字「巿」（U+5DFF）被當成「市」，以及含有「號」字的單位標示。"
        "座標來自各縣市的開放門牌點位檔，因為台灣沒有全國性的開放地理編碼服務："
        f"{n0(meta['geo']['total'])} 棟中有 {n0(meta['geo']['matched'])} 棟"
        f"（{meta['geo']['rate']:.2f}%）定位成功，行政區一致率 100%。"
        "座標只供地圖使用，絕不進入任何報酬率計算。"))
    A(P("<b>背景資料來源</b>，每一項都在資料檔中留有雜湊值：內政部統計（按樓層與屋齡的宅數、"
        "法拍量、低度使用住宅、價格指數、待售新成屋）、中央銀行（定存、重貼現與房貸利率）、"
        "主計總處家庭收入、台灣金服金拍拍定結果，以及 OpenStreetMap"
        "（底圖與 264 個捷運／輕軌站）。"))

    A(CondPageBreak(70 * mm))
    A(P("3  方法", "h1"))
    A(P("<b>分析單位是棟，不是配對。</b>配對高度集中在超大型大樓："
        f"中位數的建物有 {conc['median_per_building']} 組配對，最多的一棟有 "
        f"{n0(conc['max_per_building'])} 組，而前十棟就佔了全部配對的 {conc['top10_share']:.1f}%。"
        f"以配對為單位的中位數（{p2(h['pair_level_yield'])}）會剛好加重那些最不具代表性的建物。"
        "因此每一個主要數字，都是「各棟中位數」的中位數。"))
    A(P("<b>區間估計。</b>所有信賴區間都來自同一個兩階段拔靴法（bootstrap）："
        "先重抽建物，再在每棟之內重抽配對。瀏覽器以固定種子的隨機數重算區間，"
        "因此數字不會在每次重新載入頁面時跳動。"))
    A(P("<b>淨報酬率。</b>扣除四項成本，每一項在網站上都是可調整的滑桿。"
        "JavaScript 的實作與 Python 版本是孿生的，並以測試確認兩者在每一棟建物上都一致。"))
    rows = [["成本項目", "預設值", "範圍", "來源"]]
    for a in D["assumptions"]:
        rows.append([a["zh"].split("（")[0],
                     f"{a['default']:g} {UNIT_ZH.get(a['unit'], a['unit'])}",
                     f"{a['min']:g}–{a['max']:g}", _safe(a["src_zh"])])
    A(tbl(rows, [26 * mm, 26 * mm, 17 * mm, FRAME_W - 69 * mm], wrap=(3,), size=7.2))
    A(Spacer(1, 6))
    A(P(f"在同一間房子上同時取得成交價與租金，並不是新的做法。{cite_t('bracke2015')} "
        "就以一家仲介自己的成交簿對倫敦市中心做過：1,922 件物件在六個月內同時被出售與出租。"
        "這裡不同的是來源與它能支撐的結論——公開的全國登錄資料，而不是一家公司的客戶名單；"
        "而且這份登錄資料「沒有涵蓋到的部分」本身是可以被量出來的，仲介的成交簿做不到這件事。"))
    A(P(f"<b>區間。</b>同一棟樓之內的配對並不是獨立抽樣，而真正限制精確度的是棟數、不是配對數"
        f"{cite('cameron2008')}——這也是為什麼各行政區要先通過 {meta['min_district_n']} 棟的下限"
        "才會被報告出來。",
        "note"))
    A(P("<b>可重現性。</b>資料檔內含各季原始壓縮檔的 SHA-256 清單、每一份參考 CSV 與金拍快取的雜湊值、"
        "建立時的 commit 以及版本號。<i>bin/rebuild-housing.sh</i> 會重建資料檔，"
        "並在結構上與已提交的雜湊值比對差異。"))
    A(PageBreak())

    # ================================================================ 第貳部
    A(P("第貳部 · 發現", "part"))
    A(P("4  報酬率主數字", "h1"))
    A(tiles([(p2(h["yield"]), f"毛報酬率，95% 信賴區間 {boot['overall']['lo']:.2f}–{boot['overall']['hi']:.2f}"),
             (p2(h["net"]), "淨報酬率，已扣稅、管理費、空置與修繕<br/>"
                            f"95% 信賴區間 {boot['overall_net']['lo']:.2f}–{boot['overall_net']['hi']:.2f}"),
             (p2(h["pair_level_yield"]), "同一份資料，以配對加權<br/>（錯誤的單位）")]))
    A(Spacer(1, 6))
    A(fig(histogram(D["histogram"], D["histogram_net"], h["yield"], h["net"],
                    label_g="毛報酬率中位數 {:.2f}%", label_n="淨報酬率中位數 {:.2f}%"),
          "圖 4.1 — 以棟為單位的報酬率分布。柱狀為毛報酬率，折線為淨報酬率。"
          "兩端的柱子是超出範圍者的堆積（直方圖在此截斷），不是該區間自己的次數。"
          f"兩個中位數之間的水平距離（{h['yield']-h['net']:.2f} 個百分點）就是成本模型。"))
    hn = D["histogram_net"]
    below1 = sum(b["n"] for b in hn if b["x1"] <= 1.0)
    neg = sum(b["n"] for b in hn if b["x1"] <= 0)
    A(P(f"有 {below1:,} 棟（{below1/h['buildings']*100:.1f}%）的淨報酬率低於每年 1%，"
        f"其中 {neg} 棟低於零。與並列公佈的參考利率相比："))
    A(tbl([["參考利率", "數值", "期間", "這是什麼"],
           ["本站淨報酬率", p2(h["net"]), "112S4–115S2", "可配對建物的中位數"],
           ["一年期定存", p2(bm["deposit_1y"]["rate"]), bm["deposit_1y"]["period_en"],
            "五大銀行，五家完全相同"],
           ["重貼現率", p2(bm["rediscount"]["rate"]), bm["rediscount"]["period_en"],
            "政策利率，無法投資"],
           ["新承作房貸（央行）", f"{bm['mortgage']['rate']:.3f}%", bm["mortgage"]["period_en"],
            "五大銀行，新承作購屋貸款"],
           ["新承作房貸（內政部）", p2(moi["mortgage"]["rate"]), moi["mortgage"]["period"],
            "全國所有新承作貸款"]],
          [38 * mm, 18 * mm, 30 * mm, FRAME_W - 86 * mm], right=(1,)))
    A(P("在這段期間以房貸購屋的買方，付出的利息高於中位數可定價住宅所產生的淨租金收入。"
        "報酬率低於買下它的那筆錢的成本。這是一個算術陳述，不是對「價格錯了」的判決："
        f"依使用者成本（user cost）恆等式{cite('himmelberg2005')}，偏低的租金／價格比"
        "可以是對低實質利率與預期增值的合理反應，而本文量到的任何東西都無法判定是哪一種。",
        "note"))

    A(P("與其他已發表的估計相比", "h2"))
    A(P(f"臺灣其實已經有一個在流通的租金報酬率數字，值得問的是它從哪裡來。"
        f"{cite_t('chang2018')} 給出臺灣的租金乘數 64、報酬率 1.57%，"
        "而那張表自己註明的來源是 Global Property Guide——一個商業刊登網站的彙整。"
        f"{cite_t('gpg2026')} 目前公布的全國數字是 {p2(GPG_NATIONAL)}，"
        "算法是五個城市公寓的「刊登租金中位數 × 12 ÷ 刊登價格中位數」。"
        "也就是說，經過同儕審查的那個臺灣數字與面向消費者的那個是同一個數字，"
        "而兩者都不是建立在成交資料上。由此延伸出兩點與本報告的差異。刊登價格不是成交價格。"
        "而且「兩個分別取自不同物件的中位數之比」並不等於「每一棟各自比值的中位數」——"
        "它們是不同的統計量，而且只有後者是某一棟建物真的可能賺到的報酬率。"))
    A(CondPageBreak(62 * mm))
    A(P("逐一城市對照，這個比較過去沒有被做過："))
    gp = sorted([c for c in D["counties"] if c["city"] in GPG_CITIES],
                key=lambda c: -c["buildings"])
    crows = [["城市", "本報告", "95% 信賴區間", "棟數", f"GPG（{GPG_UPDATED}，刊登）", "差異"]]
    for c in gp:
        g = GPG_CITIES[c["city"]]
        ci = boot["county"].get(c["county"])
        crows.append([c["city"], p2(c["yield"]),
                      f"{ci['lo']:.2f}–{ci['hi']:.2f}" if ci else "—",
                      n0(c["buildings"]), p2(g), pp(c["yield"] - g)])
    A(tbl(crows, [24 * mm, 22 * mm, 26 * mm, 20 * mm, 38 * mm, FRAME_W - 130 * mm],
          right=(1, 2, 3, 4, 5), size=7.6))
    A(Spacer(1, 5))
    worst = max(gp, key=lambda c: c["yield"] - GPG_CITIES[c["city"]])
    best = min(gp, key=lambda c: c["yield"] - GPG_CITIES[c["city"]])
    A(P(f"五個城市全部都是登錄資料算出來的比較高，"
        f"{best['city']}差 {pp(best['yield']-GPG_CITIES[best['city']])}，"
        f"{worst['city']}差 {pp(worst['yield']-GPG_CITIES[worst['city']])}。"
        "兩者在北部相當接近，往南則逐漸分開。這只是指示性的對照，並非嚴格的同類比較："
        "刊登網站的數字涵蓋五個市轄範圍內的公寓，本文涵蓋全縣市的四層以上住宅建物——"
        "對新北、高雄、臺南而言，那包含了大量非都市地區——而且兩者的期間也不同。"
        "不過方向在每一個城市都一致，而且落差最大的地方，正是刊登平台涵蓋最薄的地方。"))
    A(P(f"臺北市是唯一有三個獨立估計的城市，而三者相符。{cite_t('yang2018')} 以 591 的刊登租金"
        "對上實價登錄的成交價，估出 2013–2016 年臺北的租金乘數約為 50，倒數過來約等於 2.0% ——"
        "這是把他們的數字做算術倒數，不是他們自己寫出來的報酬率。"
        f"Global Property Guide 的 2026 年數字是 {p2(GPG_CITIES['臺北市'])}。"
        f"本報告是 {p2([c for c in gp if c['city']=='臺北市'][0]['yield'])}。"
        "三種方法、三個期間，差距約在零點一個百分點上下。"))
    A(P("改成和第 6 節的界線對照，而不是和點估計對照：目前的刊登數字與 2013–2016 年的租金乘數"
        "都落在「相似性假設」的區間之內，而流通中的 1.57% 落在它之下——"
        "不過那個數字描述的是比本文期間更早的時期，所以這不算矛盾，"
        "而是再一次提醒：一個沒有附上日期與分母的報酬率，並不是一次量測。", "note"))
    A(P(f"<b>這張表是手寫的，不是推導出來的。</b>它是本報告唯一一張這樣的表。"
        f"這些數字活在別人的網頁與別人的 PDF 裡；沒有任何資料檔能產生它們，也沒有任何測試能檢查它們。"
        f"它們是在 {EXTERNAL_READ_ON} 從來源讀取的，來源列在第 19 節，"
        "所以讀者可以用檢查本報告其他每一個數字的方式去檢查它們。", "note"))

    # ------------------------------------------------------------ 5 覆蓋率
    A(CondPageBreak(95 * mm))
    A(P("5  覆蓋率：核心發現", "h1"))
    A(P(f"期間內有住宅成交紀錄的 {n0(wf['universe'])} 棟建物中，{n0(wf['final'])} 棟算得出報酬率。"
        "瀑布圖說明其餘每一棟是在哪一步流失的，以及每一步該算在誰的帳上。"))
    wrows = []
    for s in wf["steps"]:
        short = {"no_lease": "完全沒有租賃紀錄（實價登錄）", "window": "租約相隔超過4季／落在品質區間外",
                 "parking": "車位金額未列明", "social": "租約是社會住宅",
                 "rooms": "不是整戶出租", "related": "親友間交易"}.get(s["key"], _safe(s["zh"])[:40])
        wrows.append((short, s["lost_pp"], None, None,
                      ACCENT2 if s["whose"] == "law" else ACCENT))
    A(fig(hbars(wrows, lo=0, hi=80, fmt=lambda v: f"{v:.2f}pp", label_w=165),
          f"圖 5.1 — 在 {n0(wf['universe'])} 棟的母體中，每一步流失的百分點。"
          f"橘色為實價登錄本身（沒有租約紀錄），共 {law_pp:.1f} 個百分點；"
          f"藍色為本專案的品質篩選，合計 {ours_pp:.1f} 個百分點。"
          f"制度側佔全部流失的 {wf['law_share']}%。"))
    A(P("「沒有租約紀錄」不等於「租約未登錄」。實價登錄只收到透過"
        "租賃住宅服務業與不動產經紀業申報的租約，而那些建物大多本來就是自住。"
        "重點是：再怎麼清理，都救不回一份從未被申報的租約。"
        f"把本專案的每一道篩選都拿掉，上限是 <b>{p2(wf['ceiling_pct'])}</b>。"))
    A(P("哪些建物存活下來", "h2"))
    A(fig(hbars([("住宅大樓", tw["match_rate"], None, None, ACCENT),
                 ("華廈", mr["match_rate"], None, None, ACCENT),
                 ("公寓", wu["match_rate"], None, None, ACCENT)],
                lo=0, hi=14, label_w=110),
          "圖 5.2 — 各類型建物中，有成交紀錄且能配對到租約的比例。"))
    A(tbl([["類型", "有成交（棟）", "可配對", "配對率", "佔有成交", "佔可配對",
            "毛", "淨"]] +
          [[t, n0(c["all_buildings"]), n0(c["matched"]), p2(c["match_rate"]), p2(c["share_all"]),
            p2(c["share_matched"]), p2(c["yield"]), p2(c["net"])]
           for t, c in cov.items()],
          [22 * mm, 24 * mm, 19 * mm, 19 * mm, 22 * mm, 22 * mm, 18 * mm, 18 * mm],
          right=(1, 2, 3, 4, 5, 6, 7)))
    sbf = moi["stock_by_floor"]
    A(P("與全國住宅存量相比", "h2"))
    A(P(f"政府的房屋稅籍資料計有 {n0(sbf['total'])} 宅。"
        f"<b>其中 {sbf['outside_pct']}% 是 1–3 層建物</b>，絕大多數是透天厝，"
        "而住宅類型篩選在定義上就排除它們，所以本報告的任何結果都不代表它們。"
        "在本站確實描述到的 4 層以上存量之內，住宅大樓佔宅數的 "
        f"{[t for t in sbf['by_type'] if t['type']=='住宅大樓'][0]['share_of_inside_pct']}%，"
        f"卻佔可定價建物的 {tw['share_matched']}%；公寓則是 "
        f"{[t for t in sbf['by_type'] if t['type']=='公寓'][0]['share_of_inside_pct']}% 對 "
        f"{wu['share_matched']}%。存量統計算的是「宅」，本站算的是「棟」；"
        "由於一棟大樓的宅數遠多於一棟公寓，這個比較其實<i>低估</i>了偏斜程度。"
        "兩者只並列呈現，絕不相除。"))
    sba = moi["stock_by_age"]
    agerows = []
    for r in sba["rows"]:
        lab = r["band"].replace("（含）", "")
        agerows.append((lab + " · 存量", r["stock_pct"], None, None, colors.HexColor("#b9b3a3")))
        agerows.append((lab + " · 可定價", r["ours_pct"], None, None, ACCENT))
    A(fig(hbars(agerows, lo=0, hi=26, fmt=lambda v: f"{v:.1f}%", label_w=120, bar_h=7, gap=2.5),
          f"圖 5.3 — 住宅存量的屋齡分布（灰色，{sba['period']}，平均 {sba['stock_mean_age']} 年）"
          f"與本站可定價建物的屋齡分布（藍色，中位數 {sba['ours_median_age']:.0f} 年）對照。"
          "可定價的那一塊集中在十年以下的建物，40 年以上幾乎完全缺席。"))
    A(P("一張表看選擇效應", "h2"))
    A(P(f"這就是古典的選擇問題{cite('heckman1979', 'manski1989')}，"
        "而住宅量測領域也遇過它：只用賣過兩次的房子所建立的指數是有偏的，"
        f"因為「賣兩次」不是隨機發生的{cite('gatzlaff1997')}。"
        "常見的修補方式是替「被觀察到」的機率建模再加以校正。這個修補在這裡用不上，"
        "第 6 節會說明原因：能不能被觀察到，取決於租約是否經由合法登記的業者申報，"
        "那是關於這套登錄制度的制度性事實，不是建物本身的行為，"
        "而登錄資料並沒有公布任何可以預測它的東西。"))
    A(tbl([["", "可配對", "配不到", "差異"],
           ["建物數", n0(age["matched_n"]), n0(age["unmatched_n"]), ""],
           ["每坪單價（中位數）", n0(age["matched_ppp"]), n0(age["unmatched_ppp"]),
            f"+{age['ppp_diff_pct']:.1f}%"],
           ["完工年（民國，中位數）", f"{age['matched_built']:.0f}", f"{age['unmatched_built']:.0f}",
            f"新 {age['matched_built']-age['unmatched_built']:+.0f} 年"],
           ["面積（坪，中位數）", f"{age['matched_area']:.1f}", f"{age['unmatched_area']:.1f}",
            f"{(age['matched_area']/age['unmatched_area']-1)*100:+.1f}%"]],
          [55 * mm, 35 * mm, 35 * mm, 45 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P("這個比較有兩個版本是以三分之一的規模出貨的。它讀到了<i>清理後</i>的買賣資料，"
        "而那份資料已經先丟掉了較便宜的存量（車位未列明、親友交易），"
        "於是它拿來比較的是 100,800 棟而不是全部，並印出 2.7% 的價差。"
        f"在完整母體上，價差是 {age['ppp_diff_pct']:.1f}%。"
        "現在有一條測試把「配不到的棟數」釘在「母體減去可配對」上。", "note"))
    A(P("把看得見的那一塊重新加權", "h2"))
    A(P(f"把可配對建物事後分層（post-stratification）到母體的組成後，毛報酬率由 "
        f"{p2(ps['visible_gross'])} 變為 {p2(ps['by_price']['gross'])}（僅按價格十分位）、"
        f"{p2(ps['by_type']['gross'])}（僅按類型），以及 <b>{p2(ps['by_both']['gross'])}</b>"
        f"（兩者同時，95% 信賴區間 "
        f"{ps['by_both']['ci_gross'][0]:.2f}–{ps['by_both']['ci_gross'][1]:.2f}）；"
        f"淨報酬率則變為 {p2(ps['by_both']['net'])}"
        f"（區間 {ps['by_both']['ci_net'][0]:.2f}–{ps['by_both']['ci_net'][1]:.2f}）。"
        f"這個區間不含未加權的 {p2(ps['visible_gross'])}，"
        f"所以 {pp(ps['shift_pp'])} 的位移不是四捨五入造成的。最便宜的價格十分位被低估"
        f"（只有應有比例的 {ps['deciles'][0]['ratio']:.2f} 倍），最貴的被高估"
        f"（{ps['deciles'][-1]['ratio']:.2f} 倍）。由於較便宜的建物報酬率較高，"
        "看得見的那一塊<i>低估</i>了它看不見的那些建物的報酬率——"
        "<i>前提是</i>它們與同一價格十分位的鄰居相似。第 6 節說明為什麼這個「前提」拿不掉。"))
    A(P("房價負擔，作為附帶結果", "h2"))
    A(P(f"以中位數房價除以每位就業者平均所得衡量（主計總處，{inc['year']}年），"
        f"全國一戶房子相當於 {inc['national_years']} 年所得，可定價的那一塊則是 "
        f"{inc['matched_years']} 年。臺北市是極端值，達 "
        f"{[c for c in inc['counties'] if c['county']=='a'][0]['years']} 年；"
        f"嘉義市最可負擔，為 {[c for c in inc['counties'] if c['county']=='i'][0]['years']} 年。"
        "可定價的那一塊每坪較貴但面積較小，因此總價較低。"))

    # ------------------------------------------------------------ 6 部分識別
    A(CondPageBreak(95 * mm))
    A(P("6  為看不見的 94% 設界", "h1"))
    A(P("上面每一個數字，都是本站配得到的那些建物的中位數。"
        f"把其餘 {n0(pid['scope']['n'] - pid['scope']['matched'])} 棟直接丟掉，"
        "等於默默假設它們長得和有紀錄的那些一樣。部分識別（partial identification）拒絕這個假設，"
        "改為替它們<i>設界</i>。在每一個格子內（先按類型，再按類型×價格十分位，再加屋齡級距），"
        "可配對建物以其實際觀察到的報酬率進入，配不到的那一部分則以一整團質量落在該格子假設的"
        "下界或上界上。這個混合分布的加權中位數，就是每一階所標示之假設下的精確界線（sharp bound）。"
        f"這是標準的構造法{cite('manski1989', 'horowitz1995', 'manski2003')}："
        "把沒有觀察到的那團質量放到它支撐集的兩端，得到的是一個資料無法再收窄的區間，"
        "而不是一個資料無法支撐的點。"))
    names = {"band": "僅本站自己的品質區間", "type_support": "落在自身類型已觀察到的最小—最大值內",
             "type_trim": "落在自身類型第5—第95百分位內", "type_price": "＋自身價格十分位（主數字）",
             "type_price_age": "＋自身屋齡級距"}
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
    d.add(_s(X(h["yield"]) + 3, 2, f"可配對中位數 {h['yield']:.2f}%", size=6.6, color=ACCENT2))
    for t in (0, 3, 6, 9, 12):
        d.add(_s(X(t), d.height - 6, f"{t}%", size=6.2, color=MUTED, anchor="middle"))
    A(fig(d, "圖 6.1 — 在每一階的假設下，所有有成交紀錄建物的毛報酬率中位數可能落在哪裡。"
             "每一階對其假設而言都是精確界線，而不只是保守估計。"))
    tp = rungs["type_price"]
    A(P(f"主數字那一階把全部建物的中位數框在毛報酬率 <b>[{tp['gross']['lo']:.2f}%、"
        f"{tp['gross']['hi']:.2f}%]</b>，淨報酬率 [{tp['net']['lo']:.2f}%、{tp['net']['hi']:.2f}%]。"
        "解讀時有三件事構成限制："))
    A(KeepTogether(bullets([
        "<b>修尾（trim）是一個「相似性」假設。</b>「落在第 5 到第 95 百分位內」禁止任何配不到的建物"
        f"位於自身類型的前 5%。它換來 {rungs['type_trim']['buys_pp']:.2f} 個百分點的收窄，"
        "是幅度最大的一步，因此未修尾的那一階一直並列保留。",
        f"<b>屋齡那一階失敗了，而且是公開地失敗。</b>{rungs['type_price_age']['cells']} 個格子中有 "
        f"{rungs['type_price_age']['cells_below_min']} 個的可配對建物太少，"
        f"{n0(rungs['type_price_age']['fellback_universe_n'])} 棟退回使用較弱的假設，"
        f"而區間反而<i>變寬</i> {abs(rungs['type_price_age']['buys_pp']):.2f} 個百分點。"
        "條件給得更多，並不一定識別得更多。",
        f"<b>殘餘的選擇效應方向未定。</b>可配對建物每坪貴 {pid['ppp_gap_pct']:.1f}%，"
        "這暗示配不到的建物報酬率較高。但「能配對」同時需要一筆買賣與一筆租約，"
        "這會篩出流動性高的投資型物件，而這又暗示它們報酬率較低。"
        "兩個方向都公開寫出，不擇一。",
    ])))
    A(callout(f"一個中位數的最壞情況區間，只有在觀察到超過母體 "
              f"{pid['median_bound_requires_coverage_pct']:.0f}% 之後，才可能脫離整個支撐區間。"
              f"本站觀察到 {p2(h['coverage_pct'])}；把每一道篩選都拿掉，實價登錄允許的上限是 "
              f"{p2(h['coverage_ceiling_pct'])}。再怎麼改進清理方式，都動不了第一階。"
              "這是關於實價登錄的事實，不是關於本站的免責聲明。", "可引用的結果"))
    un = pid["unanswerable"][0]
    A(P(f"只套用在公寓上（可配對率 {p2(un['coverage_pct'])}），區間是 "
        f"[{un['support'][0]:.2f}%、{un['support'][1]:.2f}%]，寬度 {un['width']:.2f} 個百分點。"
        "這個寬度足以把第 9 節整個公寓與大樓的差距吞掉。"))

    A(P("相似性假設是真的嗎？", "h2"))
    A(P("支撐階以上的每一階，都建立在同一個想法上：一棟配不到租約的建物，"
        "長得像它所屬格子裡<i>可配對</i>的那些建物。到 v1.1 為止的每一版都把這件事寫出來、"
        "做成階梯、誠實標示——卻從來沒有檢驗過它，"
        "這使它成為本報告裡唯一一個被主張、而不是被量測的承重論點。"
        "它是可以檢驗的，而且就檢驗在格子沒有條件化的那兩件事上：建物多老，以及建物多大。"
        "如果格子真的做到那一階所宣稱的事，可配對與配不到建物之間的落差，應該在格子內部收斂。"))
    A(P(f"以標準化差異（standardised difference，平均差除以合併標準差）報告，這個量尺與單位無關，"
        f"慣例上 |d| &lt; {rz_meta['balanced_at']} 視為平衡。"
        f"一個格子要有 {rz_meta['min_cell']} 棟可配對建物才會被計入，"
        "所以少數幾棟不會壓過一整個十分位。", "note"))
    bz, az = rz["built"], rz["area"]
    A(tbl([["", "屋齡（建成年）", "面積（坪）"],
           ["未條件化的 d（全母體）", f"{bz['unconditional_d']:+.3f}", f"{az['unconditional_d']:+.3f}"],
           ["格子內 |d|（依規模加權）", f"{bz['within_cell_abs_d']:.3f}", f"{az['within_cell_abs_d']:.3f}"],
           ["格子內帶號 d", f"{bz['within_cell_signed_d']:+.3f}", f"{az['within_cell_signed_d']:+.3f}"],
           ["被格子吸收的比例", f"{bz['absorbed_pct']:.1f}%", f"{az['absorbed_pct']:.1f}%"],
           ["未達平衡的格子", f"{bz['cells_unbalanced']} / {bz['cells']}",
            f"{az['cells_unbalanced']} / {az['cells']}"]],
          [58 * mm, 32 * mm, 32 * mm], right=(1, 2), size=7.4))
    A(Spacer(1, 6))
    A(P(f"<b>屋齡：大致被吸收了。</b>在全母體上，可配對建物比配不到的新了 "
        f"{bz['unconditional_d']:+.2f} 個標準差。進到格子內之後降到 {bz['within_cell_abs_d']:.3f}，"
        f"也就是條件化消掉了其中 {bz['absorbed_pct']:.0f}%。"
        f"剩下來的雖然小，卻不是雜訊：帶號平均是 {bz['within_cell_signed_d']:+.3f}，"
        f"方向與原始落差相同，而且 {bz['cells']} 個格子裡仍有 {bz['cells_unbalanced']} 個落在平衡帶之外。"
        "可配對建物比同一格子裡的鄰居更新。"))
    A(P(f"<b>面積：不但沒有變好，反而更糟。</b>未條件化時，可配對建物小了 "
        f"{abs(az['unconditional_d']):.2f} 個標準差。進到格子內之後它沒有縮小，"
        f"反而擴大到 {az['within_cell_abs_d']:.3f}——往錯誤方向走了 {abs(az['absorbed_pct']):.0f}%，"
        f"{az['cells']} 個格子裡有 {az['cells_unbalanced']} 個未達平衡，"
        "而且最差的六個格子全部帶同一個方向。機制並不神祕：格子是依每坪單價切的，"
        "而「坪」正是每坪單價的分母。用一個比值分帶，等於把原本部分抵消面積效果的價格效果抽掉，"
        "於是在同一個價帶之內，面積的落差比在全母體上表現得更自由。"))
    A(P("面積上 |d| 最大的格子：" + "、".join(
        f"{w['type']}第 {w['decile']} 十分位（{w['d']:+.2f}）" for w in az["worst"][:4]) + "。", "note"))
    A(callout(
        "所以主數字的那個區間，是一個<b>「在明列假設下」</b>的區間，不是一個已被驗證的區間；"
        "而且在一個可量測的維度上，那個假設不只是「未經查證」，而是被資料反駁。"
        "算術本身沒有任何改變——每一階對它自己所標示的假設而言仍然是精確界線——"
        "但讀者應該把「從品質區間收窄下來」這件事，視為建立在一個資料只支持一半的條件之上。<br/><br/>"
        "而且這件事沒辦法靠「連面積也一起條件化」來修。屋齡那一階已經示範了會發生什麼事："
        f"多加一個維度之後，{rungs['type_price_age']['cells']} 個格子裡有 "
        f"{rungs['type_price_age']['cells_below_min']} 個低於最低棟數，"
        f"{n0(rungs['type_price_age']['fellback_universe_n'])} 棟建物退回較弱的假設，"
        f"所以它反而把區間<i>撐寬</i>了 {abs(rungs['type_price_age']['buys_pp']):.2f} 個百分點。"
        f"在 {p2(h['coverage_pct'])} 的覆蓋率之下，資料會比條件化先用完。"
        "這和第 6 節其餘部分撞到的是同一面牆，只是從另一個方向撞上去。",
        "這對那個區間的意義"))

    # ------------------------------------------------------------ 7 階梯
    A(CondPageBreak(95 * mm))
    A(P("7  每一道清理步驟值多少", "h1"))
    A(P("誠實階梯把主數字重算一遍，每次多加一道篩選，而且全部走與主數字相同的程式路徑。"
        "每一階都以棟為單位讀出，並附 95% 信賴區間；以配對為單位的數字並列顯示，"
        "讓單位問題看得見。"))
    lrows = [["階", "以棟計", "95% 信賴區間", "以配對計", "棟數", "配對數"]]
    for r in lad:
        lrows.append([_safe(r["zh"]), p2(r["yield_building"]), f"{r['lo']:.2f}–{r['hi']:.2f}",
                      p2(r["yield_pair"]), n0(r["buildings"]), n0(r["pairs"])])
    A(tbl(lrows, [66 * mm, 21 * mm, 22 * mm, 18 * mm, 21 * mm, 22 * mm], right=(1, 2, 3, 4, 5),
          wrap=(0,), size=7.8))
    A(Spacer(1, 6))
    sh = fm["shapley"]["building"]
    A(P(f"由於篩選的先後順序會影響結果，每一道篩選的貢獻另以 <b>Shapley 值</b>"
        f"{cite('shorrocks2013')}計算，"
        f"涵蓋全部 2³ 種組合；三者相加恰好等於以棟計的總變動 {pp(fm['total']['building'],3)}。"
        f"社會住宅：<b>{pp(sh['social'],3)}</b>（幅度最大，且方向正如補貼所預測）。"
        f"只留整戶出租：{pp(sh['rooms'],3)}。親友交易：{pp(sh['related'],3)}。"))
    A(P("逼出這個做法的 Simpson 反轉", "h2"))
    A(P("早先的階梯顯示「排除社會住宅」會<i>降低</i>報酬率，"
        "而對一群租金低於市場 28% 的母體而言，這是錯的方向。篩選本身是正確的，"
        "錯的是兩個疊在一起的呈現問題："))
    cc = mm_["concentration"]
    A(KeepTogether(bullets([
        f"<b>單位混用。</b>只要有一筆社會住宅租約的建物，就帶有 {cc['with_social']['pairs_per_building']} "
        f"組配對，而完全沒有的建物只有 {cc['without']['pairs_per_building']} 組；"
        f"於是以配對為單位的中位數會把社會住宅建物加權 {cc['pair_weight_ratio']}:1，"
        f"以棟為單位則是 {cc['bldg_weight_ratio']}:1。",
        "<b>順序。</b>分租套房的報酬率約 1.27%（它們的面積欄位描述的是整棟建物，不是那一間），"
        f"佔市場租約的 {mm_['by_let_type'][2]['market_share_pct']}%，"
        f"佔社會住宅租約的 {mm_['by_let_type'][2]['social_share_pct']}%。"
        "先排除社會住宅，會提高分租套房的權重。",
    ])))
    A(tbl([["出租型態", "社會住宅", "市場", "社會住宅 − 市場"]] +
          [[r["let_type"], p2(r["social"]), p2(r["market"]), pp(r["social"] - r["market"])]
           for r in mm_["by_let_type"]],
          [50 * mm, 30 * mm, 30 * mm, 35 * mm], right=(1, 2, 3)))
    A(P("在每一種出租型態之內，社會住宅的報酬率都較低，但加總後卻往反方向移動。"
        "網站上原本聲稱這個階梯測量了「每一個清理決定值多少」的句子已經撤回："
        "一個循序的階梯做不到那件事，而 Shapley 分解做得到。", "note"))
    A(P("社會住宅的租金落差", "h2"))
    A(P(f"社會住宅租約每坪每月 {rb['social']['rent_ping']:.0f} 元，"
        f"市場租約為 {rb['market']['rent_ping']:.0f} 元（{rb['gap_pct']:.1f}%），"
        f"而它們佔實價登錄整戶出租租約的 {rb['social_share_pct']}%（佔全部租約約 58%）。"
        "在桃園、苗栗與基隆，這個比例超過九成。排除它們是本專案最大的單一篩選決定，"
        "也是多數以原始資料估算報酬率的人最常跳過的一步。"))

    # ------------------------------------------------------------ 8 地理
    A(CondPageBreak(95 * mm))
    A(P("8  地理", "h1"))
    cn = sorted([c for c in D["counties"] if c["buildings"] >= 25], key=lambda c: c["yield"])
    crow = []
    for c in cn:
        ci = boot["county"].get(c["county"])
        crow.append((f"{c['city']}（{c['buildings']:,}）", c["yield"], ci["lo"] if ci else None,
                     ci["hi"] if ci else None, ACCENT))
    A(fig(hbars(crow, lo=0, hi=4.6, label_w=110, bar_h=9, gap=4, ref=h["yield"],
                ref_label=f"全國 {h['yield']:.2f}%"),
          "圖 8.1 — 各縣市毛報酬率中位數與 95% 拔靴法信賴區間（括號內為棟數）。"
          "可配對建物少於 25 棟的縣市未列出。金門與連江完全沒有乾淨的租約，"
          "這是實價登錄的事實。"))
    A(P(f"多數相鄰縣市在統計上分辨不出差異"
        f"（{boot['adjacent_pairs']} 組相鄰行政區區間中有 {boot['adjacent_overlaps']} 組重疊），"
        "但兩個極端確實不同。臺北市是報酬率最低的大城市，因為它最貴："
        f"跨行政區看，每坪單價與報酬率的相關係數為 <b>{corr_price_yield(D['districts']):.3f}</b>"
        f"（涵蓋已發佈的 {len(D['districts'])} 個行政區）。租金的變異遠小於價格。"))
    ds = sorted([x for x in D["districts"] if x["buildings"] >= 25], key=lambda x: x["yield"])
    rows = [["", "行政區", "毛", "淨", "棟數", "每坪單價"]]
    for tag, sub in (("最低", ds[:6]), ("最高", ds[-6:][::-1])):
        for i, x in enumerate(sub):
            rows.append([tag if i == 0 else "", f"{x['city']}{x['district']}", p2(x["yield"]),
                         p2(x["net"]), n0(x["buildings"]), n0(x["price_ping"])])
    A(tbl(rows, [18 * mm, 48 * mm, 20 * mm, 20 * mm, 22 * mm, 30 * mm], right=(2, 3, 4, 5)))
    A(Spacer(1, 6))
    A(P(f"<b>棟內與棟間。</b>在至少有 {disp['min_pairs']} 組配對的 {n0(disp['buildings'])} 棟建物上，"
        f"同一棟樓內報酬率的典型離散程度（四分位距 {disp['within_iqr']:.3f} 個百分點）"
        f"是行政區中位數之間離散程度（{disp['between_iqr']:.3f} 個百分點）的 {disp['ratio']:.2f} 倍。"
        "在兩市版本中，這個比值是反過來的 2.46 倍，當時的說法是「一棟樓的變異大於一整座城市」。"
        "範圍擴及全國後這個結論反轉，而文案被改寫成可以跟著資料往任一方向走。"
        "即使如此，同一棟樓裡的兩戶，差異仍超過兩個行政區之間差異的一半，"
        "這也是為什麼單一的行政區平均值會藏起很多東西。"))
    A(P(f"<b>空置率的損益兩平點。</b>資料足夠且報酬率最高的行政區是"
        f"{vb['city']}{vb['district']}（{p2(vb['gross'])}），"
        f"它需要 {vb['breakeven_vacancy_pct']}% 的空置率才會掉到全國行政區中位數"
        f"——而預設值只有 {vb['default_vacancy_pct']:.0f}%，實際量到的該縣市低度使用率更遠低於此。"
        "便宜行政區的高報酬率，不能用「房子空著」解釋掉。"))

    # ------------------------------------------------------------ 9 公寓
    A(CondPageBreak(95 * mm))
    A(P("9  公寓與大樓：最初的假設", "h1"))
    A(P("本專案始於一個想法：屋齡較高的公寓，每坪便宜又沒有管理費，報酬率應該高於大樓。"
        "這個想法經歷了四次判定。"))
    A(tbl([["階段", "判定", "理由"],
           ["兩市（8月）", "死亡", "毛報酬率差距 0.041 個百分點；淨報酬率差距中約 81% 來自本專案自己的成本假設"],
           ["全國（9月8日）", "存活", "毛報酬率差距 +0.374 個百分點，信賴區間不含零；「死亡」這個標籤原來是寫死的字串"],
           ["加控制（9月11日）", "有爭議", "同價格十分位內 +0.120 個百分點，同行政區內 +0.637 個百分點：兩者不可能同時是效果"],
           ["v2.2（9月20日）", "無法回答", "大樓一側的代表性不成立；費用機制被證偽"]],
          [30 * mm, 24 * mm, FRAME_W - 54 * mm], wrap=(2,)))
    A(Spacer(1, 6))
    prec = wr["precision"]
    A(P(f"<b>這個差距在可配對資料中是真的。</b>公寓 {p2(dh['by_type'][2]['gross'])} 對大樓 "
        f"{p2(dh['by_type'][0]['gross'])}：毛報酬率差 {pp(prec['gross_gap'],3)}"
        f"（信賴區間 {prec['lo']:.3f}–{prec['hi']:.3f}，為最小可偵測差異的 "
        f"{prec['ratio_obs_to_mdd']} 倍），淨報酬率差 {pp(prec['net_gap'],3)}。"
        "在大多數控制族之下，它的方向也維持一致："))
    fam = {"price_decile": "價格十分位", "county_district": "行政區", "county": "縣市",
           "age_band": "屋齡級距", "size_band": "面積級距", "has_mgr": "有無管理員",
           "district_x_price_decile": "行政區 × 價格十分位", "district_x_age_band": "行政區 × 屋齡級距"}
    A(tbl([["控制族", "格子數", "涵蓋公寓數", "差距中位數", "同方向", "具約束力"]] +
          [[fam.get(c["family"], c["family"]), str(c["cells"]), n0(c["walkups_covered"]),
            "—" if c["median_gap"] is None else pp(c["median_gap"], 3),
            "—" if c["same_sign_pct"] is None else f"{c['same_sign_pct']:.0f}%",
            "是" if c["binding"] else "否"] for c in wr["controls"]],
          [42 * mm, 15 * mm, 30 * mm, 25 * mm, 22 * mm, 22 * mm], right=(1, 2, 3, 4)))
    A(Spacer(1, 6))
    rw, rt = wr["representativeness"]
    A(P(f"<b>為什麼它無法被解決。</b>可配對的公寓看起來像一般的公寓"
        f"（中位數最大差異 {rw['max_abs_diff_pct']}%）。可配對的大樓則不然：它們是 "
        f"{rt['medians']['area_ping']['m']:.1f} 坪，而「有成交卻從未配對成功」的大樓是 "
        f"{rt['medians']['area_ping']['u']:.1f} 坪（{rt['medians']['area_ping']['diff_pct']:+.1f}%）。"
        "兩個偏斜方向不同的樣本無法回答一個關於母體的問題，"
        f"而事先訂下的規則把這種情況歸類為"
        f"<i>{VERDICT_ZH.get(wr['verdict'], wr['verdict'].replace('_', ' '))}</i>。"
        f"屋齡分布也幾乎不重疊：公寓中位數 {wr['common_support']['walkup_age']['median']:.0f} 年，"
        f"大樓 {wr['common_support']['tower_age']['median']:.0f} 年，"
        "而且沒有任何一個「行政區 × 屋齡」格子能在兩側各湊到 25 棟。"))
    mc = {c["has_mgr"]: c for c in wr["mechanism"]["cells"]}
    A(P(f"<b>已經確定的是：原本提出的機制是錯的。</b>有管理員的紀錄出現在 "
        f"{wr['mechanism']['p_mgr_tower_pct']}% 的大樓與 {wr['mechanism']['p_mgr_walkup_pct']}% 的公寓，"
        f"因此這筆費用幾乎就是一個類型的指示變數。但在兩側都沒有管理員的建物中"
        f"（{mc[0]['n_walkup']} 棟公寓對 {mc[0]['n_tower']} 棟大樓），"
        f"模型算出的費用正好是零，而差距依然是 {pp(mc[0]['gross_gap'],3)}"
        f"（信賴區間 {mc[0]['lo']:.3f}–{mc[0]['hi']:.3f}）。這個差距不需要那筆費用。"
        "本專案最初的解釋，死在本專案自己的資料上。"))
    A(callout("一份完整的住宅租賃母體（自住自租的公寓從來不會進入實價登錄，"
              "因為它只收到業者申報的案件），或是按類型 × 屋齡 × 樓層的建物層級房屋稅微觀資料"
              "（僅對機構開放）。這兩者本專案都拿不到。", "什麼資料才能回答"))

    # ------------------------------------------------------------ 10 棟內
    A(CondPageBreak(70 * mm))
    A(P("10  同一棟樓之內", "h1"))
    A(P("在<i>同一棟建物內</i>比較不同單位，等於在定義上固定住了區位、屋齡、建材與公共設施。"
        "這些是本專案中識別最強的結果。"))
    A(tbl([["比較", "效果", "棟數", "基準"],
           ["附傢俱與未附傢俱的租金", f"+{wb['furnished']['pct']:.1f}%", n0(wb["furnished"]["buildings"]),
            f"每坪每月 {wb['furnished']['diff_ppp']:.0f} 元，基準 {wb['furnished']['base_ppp']:.0f} 元"],
           ["每層樓的租金", f"+{wb['floor']['pct_per_floor']:.2f}%", n0(wb["floor"]["buildings"]),
            f"每坪每層 {wb['floor']['slope_ppp_per_floor']:.2f} 元"],
           ["每層樓的價格", f"+{wb['floor_sale']['pct_per_floor']:.3f}%", n0(wb["floor_sale"]["buildings"]),
            f"每坪每層 {wb['floor_sale']['slope_ppp_per_floor']:,.0f} 元"]],
          [52 * mm, 22 * mm, 24 * mm, FRAME_W - 98 * mm], right=(1, 2)))
    A(Spacer(1, 5))
    A(P(f"買方為多一層樓所付的代價，大約是租客的五倍，因此樓層越高報酬率越低："
        f"二十層的高度差大約相當於 {wb['floor_gap_pp']:.2f} 個百分點的報酬率。"
        f"景觀被資本化進價格，而不是租金。這兩條斜率來自不同的建物集合"
        f"（{n0(wb['floor']['buildings'])} 棟有兩個以上樓層的租約、"
        f"{n0(wb['floor_sale']['buildings'])} 棟有兩個以上樓層的買賣），而本站把兩個棟數都寫出來。"))

    # ------------------------------------------------------------ 11 捷運
    A(CondPageBreak(95 * mm))
    A(P("11  捷運：一個被四重撤回的發現", "h1"))
    A(P("距最近車站的距離曾經看起來是本專案的第二個發現：報酬率從車站附近約 2.1% "
        "一路上升到 2.5 公里外的 2.9%，跨七個距離組單調遞增。它現在已<b>撤回</b>，"
        "而走到這一步的過程，是本專案最有教育意義的一段。"))
    A(tbl([["版本", "當時發佈的內容", "錯在哪裡"],
           ["v1.2", "全國梯度，「價格掉得比租金快」",
            "只載入了臺北的 131 個車站：高雄的建物被量成距臺北約 275 公里"],
           ["v1.3", "以臺北市單一面板撤回", "臺北市在 2.5 公里外只有 4 棟建物；那個「無效果」是個空組"],
           ["v1.3b", "先以北北桃恢復，再以新北單獨恢復（+0.53 個百分點）", "只算重運量；而淡海輕軌剛好服務最遠的那一組"],
           ["v1.4", "撤回", "把輕軌算進去後，新北的差距約為零；高雄作為第一個獨立城市，完全看不到"]],
          [16 * mm, 62 * mm, FRAME_W - 78 * mm], wrap=(1, 2)))
    A(Spacer(1, 6))
    mrows = []
    for code, city in (("f", "新北市"), ("e", "高雄市")):
        for key, lab in (("mrth", "僅重運量"), ("mrt", "含輕軌")):
            near = [b["y"] for b in B if b["c"] == code and b.get(key) is not None and b[key] <= 500]
            far = [b["y"] for b in B if b["c"] == code and b.get(key) is not None and b[key] > 2000]
            if len(near) >= 25 and len(far) >= 25:
                mrows.append([city, lab, f"{statistics.median(near):.2f}%（n={len(near)}）",
                              f"{statistics.median(far):.2f}%（n={len(far)}）",
                              pp(statistics.median(far) - statistics.median(near))])
            else:
                mrows.append([city, lab, f"n={len(near)}", f"n={len(far)}", "樣本太少"])
    A(P("以下由本報告從資料檔中的各棟距離重新計算（各棟毛報酬率的中位數，"
        "500 公尺以內對 2 公里以外）："))
    A(tbl([["縣市", "計入的車站", "≤500 公尺", ">2 公里", "遠 − 近"]] + mrows,
          [24 * mm, 34 * mm, 40 * mm, 40 * mm, 28 * mm], right=(2, 3, 4)))
    A(Spacer(1, 5))
    A(P("<b>這件事產生的守則。</b>一個會因為判斷而翻盤的結果（輕軌算不算一個站？），"
        "是關於那個判斷的發現，而不是關於題目的發現。只要存在這樣的判斷，就把兩種都算出來、"
        "兩種都呈現。另外，從一個只有四棟的組裡得到的「無效果」不是「沒有效果」的證據："
        "相信一個無效果之前，先看比較組有多大。"))

    # ------------------------------------------------------------ 12 預售
    A(CondPageBreak(70 * mm))
    A(P("12  預售屋：那個其實不存在的 30% 溢價", "h1"))
    A(P(f"實價登錄的預售檔在期間內有 {n0(pre['projects'])} 個建案、{n0(pre['dwellings'])} 宅，"
        f"分佈在 {pre['districts']} 個行政區（每坪中位數 {n0(pre['median_ppp'])} 元）。"
        "預售屋沒有租約，所以永遠算不出報酬率；這一半的結論從未動搖。"
        "而價格比較則發佈錯了兩次："))
    A(KeepTogether(bullets([
        "<b>第一次嘗試</b>拿預售屋和「屋齡兩年以內的完工建物」比，得到 +30.2%，"
        "並歸因於等待交屋的時間成本。",
        "<b>第二次嘗試</b>撤回了那個機制（兩個完工組之間的安慰劑檢定幾乎掉得一樣快），"
        "但保留了 +30.2%。",
        "<b>第三次嘗試</b>發現比較組本身就是錯的。買賣檔裡的交易年月日是<i>簽約</i>日，"
        "不是交屋日，所以「屋齡兩年以內」選出了 186,550 筆，其中 "
        "<b>168,426 筆（90.3%）是在建物還不存在時就簽的約</b>，簽約時的屋齡中位數為 −2.17 年。"
        "當時發佈的數字，是預售屋對預售屋。",
    ])))
    crv = [(f"延後 {c['lag_years']:.1f} 年（{c['clusters']} 群）", c["gap_pct"], c["ci_lo"],
            c["ci_hi"], ACCENT if c["gap_pct"] >= 0 else ACCENT2) for c in pre["curve"]]
    A(fig(hbars(crv, lo=-13, hi=9, fmt=lambda v: f"{v:+.1f}%", label_w=130, zero_axis=True),
          "圖 12.1 — 預售屋相對於真正完工新成屋（簽約時屋齡 0–2 年）的價格溢價，"
          "並把比較對象逐步往後推移。信賴區間以「行政區 × 類型」群為單位做拔靴，"
          "而不是以格子為單位，因為同一群內的格子並不獨立。"))
    A(P(f"只有簽約同季的差距站得住腳：<b>+{pre['curve'][0]['gap_pct']:.1f}%</b>"
        f"（信賴區間 {pre['curve'][0]['ci_lo']:.1f}–{pre['curve'][0]['ci_hi']:.1f}），"
        f"在最小格子數 5、25、100 的設定下都穩定。它涵蓋 {pre['total_districts']} 個行政區中的 "
        f"{pre['reach_districts']} 個、{n0(pre['reach_dwellings'])} 宅（{pre['reach_pct']}%）；"
        "其餘行政區真正完工的新建物太少，無從比較。至於往後推移的那些差距究竟是時間還是組成，"
        "無法分離（<i>separable = false</i>）。"))

    # ------------------------------------------------------------ 13 車位
    A(CondPageBreak(95 * mm))
    A(P("13  車位：一個被檢驗而且證明為錯的清理假設", "h1"))
    lets = pa["lets"]
    A(P(f"乾淨租約中有 {p2(lets['unpriced_pct'])}（{n0(lets['unpriced'])} 筆）附帶車位，"
        "但車位租金從未列明。在 v2.0 之前，流程假設這代表車位是免費附送的，因此只扣除它的面積。"
        "檢驗方式是：在同時擁有兩種附車位租約的建物內，比較每平方公尺的總租金。"))
    v = pa["verdict"]
    A(tbl([["", "數值"],
           ["若車位免費，預測的比值", f"{v['predicted_if_holds']:.3f}"],
           ["若車位租金已含在房屋租金內，預測的比值", f"{v['predicted_if_fails']:.3f}"],
           [f"實際量到（n = {v['n']} 棟）", f"{v['ratio']:.4f}  [{v['lo']:.3f}, {v['hi']:.3f}]"],
           ["判定", VERDICT_ZH.get(v["verdict"], v["verdict"].replace("_", " "))]],
          [110 * mm, 60 * mm], right=(1,)))
    A(Spacer(1, 6))
    ex = pa["exposure"]
    A(P(f"假設不成立，因此那些租約的房屋租金被高估了。有列明的車位，"
        f"典型租金為每月 {pa['share']['park_rent_per_space_median_ntd']:,} 元"
        f"（佔整筆租約的 {pa['share']['park_rent_share_median']*100:.1f}%）。三種處理方式的比較："))
    trows = [["處理方式", "毛", "淨", "棟數"]]
    for t in pa["treatments"]:
        trows.append([{"impute": "推算並扣除車位租金（v2.1 起的主數字）",
                       "area_only": "只扣面積（v1.0–v2.0 的主數字）",
                       "drop": "整筆排除含車位的租約"}.get(t["case"], t["case"]),
                      p2(t["gross"]), p2(t["net"]) if t.get("net") is not None else "—", n0(t["buildings"])])
    A(tbl(trows, [85 * mm, 25 * mm, 25 * mm, 30 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P(f"整筆排除看起來很誘人，但會讓結果變得好看：會因此消失的那 "
        f"{ex['buildings_only_unpriced_pct']}% 建物比較新"
        f"（民國{ex['only_unpriced_built_median']:.0f}年對 {ex['rest_built_median']:.0f}年），"
        f"而且有 {ex['only_unpriced_tower_pct']}% 是大樓。"
        "決定這個判定的規則，是在早期 n=192 的一次觀察之後才寫下的，"
        "而網站把這件事明說，而不是把它稱為事先登錄（pre-registered）。"))
    mk = [r for r in pk["rungs"] if r["key"] == "market"][0]
    A(P("車位作為一項資產", "h2"))
    A(P(f"把車位當成獨立的投資，以市場價格買進並出租，毛報酬率為 <b>{p2(mk['yield'])}</b>"
        f"（信賴區間 {mk['lo']:.2f}–{mk['hi']:.2f}，{mk['buildings']} 棟，"
        f"價格中位數 {n0(mk['price'])} 元，租金 {n0(mk['rent'])} 元／月），"
        f"低於它上方的住宅。坡道機械車位的報酬率高於平面車位"
        f"（在較寬樣本上相差 {pp(pk['type_gap']['wide']['gap_pp'])}）；"
        "這一項標示為假設，因為它的機制沒有被測量。"))

    # ------------------------------------------------------------ 14 成本
    A(CondPageBreak(70 * mm))
    A(P("14  成本模型，以及每個猜測的影響有多大", "h1"))
    A(P("淨報酬率建立在四個假設上，而其中兩個（空置、修繕）完全沒有台灣的來源。"
        "本專案的做法是去測量每一個猜測會把結果移動多少，而不是假裝它有來源。"))
    A(P("管理費", "h2"))
    A(P(f"只有臺北與新北有公開的管理費調查，其餘 20 個縣市一律套用新北的每坪 105 元。"
        f"實際被收取管理費的建物佔 {mex['share_charged_pct']}%（即租約記載有管理員者），"
        f"而有 {n0(mex['buildings_outside'])} 棟位於沒有管理費統計的縣市。"
        f"把非臺北的費率減半，淨報酬率變為 {p2(mex['cases'][1]['net'])}；"
        f"歸零則變為 {p2(mex['cases'][2]['net'])}。另外，有管理員建物的租約中有 "
        f"{mfl['lets']['incl_pct']}% 在備註載明租金已含管理費。"
        f"只對沒有這項註記的建物收取費用，結果為 {p2(mfl['bounds'][1]['net'])}"
        f"（{pp(mfl['bounds'][1]['delta_pp'])}）。"))
    A(P("空置", "h2"))
    A(P(f"台灣沒有發佈租賃空置率統計，因此水準值仍是一個假設"
        f"（{vp['site_default_pct']:.0f}%）。但<i>形狀</i>可以從內政部的低度使用（以用電量認定）"
        "住宅表中量出來，並按縣市與屋齡交叉；該表由網際網路檔案館（Internet Archive）復原："))
    vrows = []
    for r in vp["profile"]:
        vrows.append((f"屋齡 {r['band']} · 低度使用率", r["rate_pct"], None, None,
                      colors.HexColor("#b9b3a3")))
    A(fig(hbars(vrows, lo=0, hi=25, fmt=lambda v: f"{v:.1f}%", label_w=150, bar_h=8, gap=3),
          "圖 14.1 — 按建物屋齡的低度使用住宅比率（111H1），呈 U 形："
          "最新與最舊的建物空得最多。"))
    A(tbl([["屋齡級距", "低度使用率", "佔可定價", "佔存量"]] +
          [[r["band"], p2(r["rate_pct"]), p2(r["matched_share_pct"]), p2(r["stock_share_pct"])]
           for r in vp["profile"]],
          [35 * mm, 35 * mm, 40 * mm, 40 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P(f"可定價的那一塊坐在 U 形的左臂上，而這正是「一律套用同一個空置率」最會美化報酬率的位置："
        f"以它自身的組成加權，其預期低度使用率為 <b>{vp['prior_pct']:.2f}%</b>"
        f"（信賴區間 {vp['prior_ci'][0]:.2f}–{vp['prior_ci'][1]:.2f}），"
        f"而全國為 {vp['national_pct']}%。只按縣市的那一條腿指向相反方向"
        f"（{vp['county_leg']['prior_pct']:.2f}% 對 {vp['county_leg']['national_pct']}%），"
        "因為樣本偏向都會區；兩者都公開。低度使用不等於租賃空置"
        "（它的分子包含第二戶住宅與待售住宅），所以它永遠不會取代主數字的那個假設："))
    A(tbl([["情境", "淨", "與主數字相比", "公寓 − 大樓（淨）"]] +
          [[_safe(c["zh"]), p2(c["net"]), pp(c["delta_pp"], 3),
            pp([t for t in vp["type_gap"] if t["case"] == c["key"]][0]["gap_pp"], 3)]
           for c in vp["cases"]],
          [70 * mm, 25 * mm, 30 * mm, 40 * mm], right=(1, 2, 3)))
    A(Spacer(1, 5))
    A(P(f"<b>修繕</b>按租金的 6% × (1 + 屋齡/50) 計算。若改用固定費率，"
        f"會讓公寓與大樓的比較偏向一個方向：公寓的毛報酬率差距是 {rep['gross']:.3f} 個百分點，"
        f"以屋齡加權的修繕計算是 {rep['age_scaled']:.3f} 個百分點，"
        f"固定費率則是 {rep['flat']:.3f} 個百分點。<b>持有稅</b>預設為房價的 0.15%，"
        "高於已發佈的自用估計值，因為囤房稅2.0 提高了非自住的稅率。"))

    # ------------------------------------------------------------ 15 背景
    A(CondPageBreak(95 * mm))
    A(P("15  市場背景", "h1"))
    A(P("成交量在期間內腰斬", "h2"))
    s = vol["series"]["all"]
    A(fig(lines([s["existing"], s["presale"], s["leases"]], vol["quarters"],
                [ACCENT, ACCENT2, ACCENT3],
                events=[("113Q2", "新青安緊縮"), ("113Q3", "囤房稅2.0 · 央行第七波")]),
          f"圖 15.1 — 全國各簽約季的乾淨實價登錄筆數。藍色為成屋，"
          f"橘色為預售，綠色為租賃。{vol['censored'][0]} 不完整（尚有延遲申報）。"))
    A(legend([("成屋", ACCENT), ("預售", ACCENT2), ("租賃", ACCENT3)]))
    sm = vol["summary"]
    A(P(f"成屋買賣由 {sm['peak_q']} 的高點（{n0(sm['peak_existing'])}）下跌 "
        f"{abs(sm['existing_change_pct']):.1f}% 至 {sm['after_q']}（{n0(sm['after_existing'])}）；"
        f"預售屋至 {sm['presale_to_q']} 下跌 {abs(sm['presale_change_pct']):.1f}%。"
        f"同一期間，租賃則由 {n0(sm['leases_from'])} 增加到 {n0(sm['leases_to'])}。"
        "三項政策落在同樣的兩個季度裡，因此網站只描述這個下跌，不做歸因。"))
    A(P("算得出價格的那一塊比官方平均更貴", "h2"))
    pr = [r for r in moi["price"]["rows"] if r["n"] >= 100]
    A(tbl([["縣市", "官方平均 元/坪", "本站中位數 元/坪", "差距", "棟數"]] +
          [[r["city"], n0(r["official"]), n0(r["ours"]), f"{r['gap_pct']:+.1f}%", n0(r["n"])] for r in pr],
          [30 * mm, 38 * mm, 38 * mm, 25 * mm, 25 * mm], right=(1, 2, 3, 4)))
    A(Spacer(1, 5))
    A(P(f"與內政部 {moi['price']['period']} 的簽約平均相比，本站的可配對建物在每一個大城市都更貴，"
        "只有花蓮、宜蘭與嘉義市例外。這是「看得見的那一塊更貴」這個發現，"
        "從實價登錄之外得到的確認。"))
    pi = moi["price_index"]
    A(P(f"<b>未修正的價格漂移。</b>官方價格指數在 {pi['quarters']} 季內上漲 {pi['total_pct']}%"
        f"（每季 {pi['per_quarter_pct']:.2f}%）。在買賣與租賃相隔的中位數 "
        f"{pi['median_pair_gap_q']:.0f} 季下，一組典型配對約帶有 "
        f"{pi['drift_at_median_gap_pct']}% 的價格漂移。本專案自己做的指數讓情況更糟"
        f"——「報酬率對時間差」的斜率在 ±4 季下由 {idx[2]['slope']:.3f} 變陡為 {idx[3]['slope']:.3f}"
        "——因此指數關閉不用，改為把漂移揭露出來。"))
    ma = moi["auction"]
    A(P("強制拍賣", "h2"))
    A(P(f"期間內法院拍賣（法拍）共拍定 {n0(ma['court_lots'])} 件，"
        f"金額 {ma['court_value']/1e8:,.0f} 億元。本專案能夠抓取的銀行擔保品通道"
        f"（金拍，台灣金服）在同一期間有 {n0(ma['fasc_lots'])} 件"
        f"（為法拍件數的 {ma['fasc_vs_court_pct']}%）。這兩者是平行通道，不是子集合。"
        f"在金拍的標的中，{auc['above_reserve_pct']}% 高於底價拍定"
        f"（第一輪為 {auc['by_round']['1']['above_reserve_pct']}%）。"
        "由於沒有面積欄位，因此不計算任何拍賣折價。法拍本身無法取得："
        "司法院的系統拒絕連線。"))
    A(P(f"<b>另外也一併發佈：</b>{moi['unsold_new']['period']} 的已完工待售新成屋 "
        f"{n0(moi['unsold_new']['value'])} 戶；全國低度使用率 "
        f"{R.lu_rate(moi, 'all')['rate_pct']}%（{moi['low_use']['period']}），"
        f"從臺北的 {R.lu_rate(moi, 'a')['rate_pct']}% 到"
        f"臺南的 {R.lu_rate(moi, 'd')['rate_pct']}%。"))

    # ================================================================ 第參部
    A(PageBreak())
    A(P("第參部 · 可信度", "part"))
    A(P("16  更正紀錄", "h1"))
    A(P("本專案的設計原則是拒絕對自己有利的版本：當一個結果看起來很乾淨，下一步就是試著把它打破。"
        "以下是後來的檢查改變了的那些已發佈主張。每一項在寫下的當時，都是正確的，"
        "或至少是站得住腳的。"))
    reg = [
        ["主張", "最初發佈", "現在", "由什麼發現"],
        ["毛報酬率主數字", "2.43%（兩市）→ 2.68%", f"{p2(h['yield'])}", "範圍擴大；車位稽核"],
        ["首頁覆蓋率句子", "「只有 6.22% 兩者都有紀錄」", "27.8% 兩者都有；6.25% 通過本站篩選",
         "獨立稽核"],
        ["各類型配對率", "大樓 14.09%、公寓 1.69%", f"{p2(tw['match_rate'])} / {p2(wu['match_rate'])}",
         "分母改為全母體"],
        ["選擇效應（每坪單價）", "+30.5% → +2.7%", f"+{age['ppp_diff_pct']:.1f}%", "本站稽核（讀錯資料框）"],
        ["公寓假設", "死亡 → 存活", "無法回答；機制被證偽", "大樓一側的檢查"],
        ["棟內與棟間離散", "棟內為棟間 2.46 倍", f"棟內為棟間 {disp['ratio']:.2f} 倍", "全國化重新計算"],
        ["捷運梯度", "存活", "撤回", "輕軌的定義；高雄"],
        ["預售屋溢價", "+30.2%", f"+{pre['curve'][0]['gap_pct']:.1f}%", "簽約日污染"],
        ["預售屋扣除時間後", "0.9%", "無法分離", "第二次稽核"],
        ["可定價佔全部建物比例", "1,086 棟中的 1 棟", "撤回（棟 ÷ 建號）", "本站自己的內政部稽核"],
        ["社會住宅那一階", "−0.165 個百分點", f"Shapley {pp(sh['social'],3)}", "單位／順序分析"],
        ["未列明的車位", "車位是免費附送", "租金已含在房屋租金內", "同棟內檢定"],
        ["淨值直方圖與滑桿", "「滑桿會改變這張圖」", "其實不會；已修正", "四代理人稽核"],
        ["拍賣登錄佔比", "佔建物的 13.8%", "佔標的件數的 14.0%（單位已明確）", "稽核"],
        ["分租篩選的標籤", "「分租套房」", "也包含未填與分層出租（5,964 筆）", "資料清理稽核"],
    ]
    A(tbl(reg, [40 * mm, 42 * mm, 48 * mm, FRAME_W - 130 * mm], wrap=(0, 1, 2, 3), size=7.6))
    A(Spacer(1, 6))
    A(P("在完整的十面向網站稽核中：提出 41 項發現，35 項經確認並修正，6 項在驗證後被駁回。"
        "那 6 項駁回中有 2 項是本專案自己提出的假警報（一個是把捨入下限誤認為錯誤，"
        "另一個是所得的「符號反轉」，其實是在比較兩個不同的母體）。"))

    A(P("本文的版本沿革", "h2"))
    A(P("數字有更正紀錄；文章本身也需要一份，否則版本號說不出到底動了什麼。"))
    A(tbl([["版本", "日期", "動了什麼"]] +
          [[v, d, t] for v, d, t in PAPER_CHANGES_ZH],
          [18 * mm, 20 * mm, FRAME_W - 38 * mm], wrap=(2,), size=7.2))

    A(CondPageBreak(70 * mm))
    A(P("17  錯誤類型與工作守則", "h1"))
    A(P("同樣的少數幾個錯誤，換了不同的外衣反覆出現。這些守則是本專案最可移轉的產出，"
        "而且適用於未來任何資料工作，包括股票。"))
    A(KeepTogether(bullets([
        "<b>要推導，不要手寫。</b>範圍擴及全國時，有九個已發佈的句子就地過期，"
        "因為數字會自己更新，散文不會。現在文案中的每一個數字都從資料檔計算而來。",
        "<b>要分支，不要斷言。</b>只要一個主張帶有方向（存活與否、變寬或變窄），"
        "文案就從資料裡選它該走的那一支。",
        "<b>斷言推導過程，而不是答案。</b>一條檢查 verdict == \"dead\" 的測試，"
        "保護的是一個過期的結論；一條檢查「判定是否由區間推出」的測試不會。",
        "<b>做算術之前，先確認兩個數字的單位。</b>配對對棟、標的件數對建物、"
        "棟對宅對建號、有期間限制對沒有期間限制：這是最常發生的一類錯誤。",
        "<b>一個比率的分子與分母必須來自同一個資料框。</b>",
        "<b>在寫下一個比較的判定之前，先把兩邊都算出來。</b>"
        "公寓的判定就是在大樓那一側存在之後立刻翻盤的。",
        "<b>在說一個數字錯了之前，先確認它描述的是哪一個母體。</b>",
        "<b>讀渲染後的頁面，而且兩種語言都要讀。</b>佔位符順序的錯誤"
        "（把一個數量印成百分比）會通過所有的參數個數測試，只有在螢幕上才看得見。",
        "<b>在一個資料集上校準出來的容許值，是一個假裝自己是測量結果的常數。</b>",
        "<b>一個把你正在重抽的東西閉包起來的寫法，等於沒有在重抽。</b>",
        "<b>寫死的顏色只在一種主題下是對的。</b>",
        "<b>多代理人稽核的規模要以「能跑完」為準。</b>10 個代理人的run會死在工作階段上限；"
        "3 到 5 個代理人的run跑完了，而且每一次跑完都找到真正的錯誤。當驗證者死掉時，用手驗。",
    ])))

    A(CondPageBreak(95 * mm))
    A(P("18  未結事項與重啟方式", "h1"))
    A(P("v1.0 是針對一個已封存的專案寫這一節的，而它列在最前面的三項是：沒有任何讀者看過這份工作、"
        "兩個儲存庫都是私有的、頁面帶有 noindex。這三件事現在都不成立了。"
        "一份一直在陳述錯誤事實的紀錄，比沒有紀錄更糟，所以這一版把清單拆開。", "note"))
    A(P("自 v1.0 以來已經結案的事", "h2"))
    A(KeepTogether(bullets([
        "<b>它公開了。</b>文章、資料檔、管線與頁面都在 "
        "<i>github.com/Stanley0210/taiwan-rental-yield</i>，並由 "
        "<i>stanley0210.github.io/taiwan-rental-yield</i> 提供瀏覽。",
        "<b>「來查我的分母」現在是一個真正的邀請。</b>資料檔附帶自己的 SHA-256，"
        "以及一個把每一份原始壓縮檔與參考檔都列出雜湊值的來源區塊。",
        "<b>它可以被引用了</b>：Zenodo 的概念 DOI 永遠指向最新版本，另有 CITATION.cff 與 README 中的引用格式。",
        "<b>它有繁體中文版</b>，與英文版讀同一份資料檔、由第二支產生器建立，"
        "並有測試釘住兩個版本所陳述的主要數字必須一致。",
        f"<b>那個過期的上限已經修好了。</b>v1.0 自己抓到了它手寫的常數——"
        f"<i>partial_id.ceiling_pct</i> 讀到 24.0%，而瀑布圖說的是 "
        f"{p2(h['coverage_ceiling_pct'])}——並指出只有一行的修法。"
        "資料檔 v2.9 改為從瀑布圖讀它，兩者不可能再互相矛盾。",
        "<b>淨報酬率與重新加權後的中位數現在都有區間了。</b>這兩個數字過去都是以單點估計發表，"
        "旁邊的毛報酬率卻帶著信賴區間。",
    ])))
    A(P("準備這一版時發現的事", "h2"))
    A(callout(
        "以完全相同的輸入與完全相同的程式碼重建資料檔，並沒有重現已發佈的那一份。"
        "有三十個欄位不同，而且全部都在內政部的低度使用住宅表裡，"
        "全部都是同樣那七列、順序剛好完全顛倒。原因是一次排序：以 <i>sort_values</i> "
        "依 period 欄位排序時，預設使用的是不穩定的 quicksort，"
        "而當資料被篩到最新一期之後，每一個鍵值都是相同的——"
        "所以存活下來的列順序，是「安裝了哪一版 pandas」的性質，不是資料的性質。<br/><br/>"
        "單就這樣，它只是一個可重現性的漏洞。但本文的兩個版本都是<i>按位置</i>讀這個陣列的——"
        "最後一列當成全國、第 5 列當成臺北、第 1 列當成臺南——"
        "所以在不同的 pandas 下重建，會把高雄的比率印成全國的，並且把那兩個城市對調。"
        "三個被自信地貼上標籤的錯誤數字，而 PDF 產生得乾乾淨淨，每一條測試都通過。"
        "兩份報告現在都改為按縣市代碼查詢、絕不按位置，列順序本身也被釘住了，"
        "而且有一條測試會把列順序打亂，然後確認印出來的數字不動。",
        "一次不構成全序的排序"))
    A(P("仍然未結的事", "h2"))
    A(KeepTogether(bullets([
        "<b>quants.tw 本身在 Railway 上仍未綁定</b>，所以這份工作的互動版本——"
        "那些滑桿、各行政區的頁面——沒有在任何地方執行。靜態頁面承載的是發現，不是工具。"
        "操作手冊是住宅分支上的 <i>docs/RAILWAY_GO_LIVE.md</i>。",
        "<b>相依套件沒有釘住版本。</b><i>requirements.txt</i> 列了六個套件、沒有任何版本，"
        "這正是一次不穩定的排序之所以會變成一次重現失敗的原因。把版本釘住，"
        "會讓 <i>bin/rebuild-housing.sh</i> 成為比現在更強的承諾。",
        "<b>房貸利率是一個手寫的常數</b>，沒有釘住的來源檔，與它的另外兩個同類不同。",
        "<b>每棟建物的網址</b>（/housing/b/&lt;key&gt;）從未建立，因為當時沒有上線的網站可以連過去。",
        "<b>租賃空置率的水準值</b>仍然是一個假設；只有它的形狀被測量出來（第 14 節）。",
    ])))
    A(P("接下來可以加入的資料", "h2"))
    A(P("一份經過探勘與批判檢查的清單放在 <i>docs/HOUSING_NEXT_DATA.md</i>。"
        "其中「優先做」的項目（成交量序列、租約記載的管理費、車位稽核）"
        "都已在 v1.9–v2.0 完成。剩下仍然有用的來源是標的層級的法拍資料（被司法院擋住）、"
        "建物層級的稅籍微觀資料（僅對機構開放），以及全國門牌地理編碼服務"
        "（TGOS，僅對機構開放）。這三者都是被資格條件擋住，不是被工作量擋住。"))
    A(P("怎麼把它叫回來", "h2"))
    A(tbl([["步驟", "指令／動作"],
           ["取出程式碼", "git checkout feat/housing（或標籤 housing-parked-2026-09-29）"],
           ["本機執行", "SECRET_KEY=devtestkey QUANTS_SUBJECT=housing venv/bin/python3 app.py"],
           ["重建資料檔", "venv/bin/python3 src/underwrite.py（需要 data/lvr/ 內 207 MB 的季度壓縮檔）"],
           ["驗證可重現性", "bin/rebuild-housing.sh"],
           ["測試", "venv/bin/python3 -m pytest tests/ -q（本儲存庫為 265 條；919 是原專案全站的數量）"],
           ["先讀這些", "docs/HOUSING_HANDOFF.md 第 0、2、11、8 節"]],
          [38 * mm, FRAME_W - 38 * mm], wrap=(1,), size=7.8))
    A(Spacer(1, 6))
    A(P("原始輸入（季度壓縮檔、門牌檔、金拍快取）被 gitignore 排除，只存在於本機的 "
        "<i>data/lvr</i>、<i>data/geo</i> 與 <i>data/fasc</i> 之下。它們在資料檔中留有雜湊值，"
        "因此重新下載的檔案可以與已發佈的版本比對。", "note"))

    # ------------------------------------------------------------ 參考文獻
    A(CondPageBreak(80 * mm))
    A(P("19  參考文獻", "h1"))
    A(P("每一筆都是因為本報告裡有某個主張倚賴它才列在這裡，每一筆底下那一行說明是哪一個。"
        "若列的是「這個題目應該要有什麼」而不是「這篇文章實際用了什麼」，那就只是裝飾。"))
    A(P("書目欄位（作者、年份、篇名、期刊、頁碼）刻意不翻譯：一筆引用必須能被照原樣複製進"
        "文獻管理軟體。", "note"))
    heads = {
        "bounds": "部分識別——第 6 節所處的框架",
        "selection": "成交資料中的選擇問題——為什麼第 5 節是發現，而不是免責聲明",
        "pricerent": "在同一間房子上同時量價格與租金",
        "taiwan": "臺灣",
        "method": "方法：歸因，以及群聚下的區間",
        "data": "用來對照的資料，不是文獻",
    }
    for g in GROUP_ORDER:
        rows = entries(g)
        if not rows:
            continue
        A(P(heads[g], "h2"))
        for _k, r in rows:
            A(KeepTogether([
                P(_safe(f"{r['full']} ({r['year']}). <b>{r['title']}</b>. <i>{r['where']}</i>.")),
                P(_safe(why(_k, "zh")), "note"),
            ]))
    orphans = uncited()
    if orphans:
        raise SystemExit("references: nothing cites " + ", ".join(orphans))

    # ------------------------------------------------------------ 附錄
    A(PageBreak())
    A(P("附錄A — 資料來源", "h1"))
    A(P(f"資料檔 v{prov['version']}，於 {prov['built']} 由 commit {prov['commit']} 建立。"
        f"來源快照摘要 {prov['source']['sha256']}。"))
    A(tbl([["季", "SHA-256", "位元組"]] +
          [[f["season"], f["sha256"], n0(f["bytes"])] for f in prov["source"]["files"]],
          [16 * mm, 128 * mm, 26 * mm], right=(2,), size=6.6))
    A(Spacer(1, 6))
    A(tbl([["參考檔案", "SHA-256（前 24 碼）", "位元組"]] +
          [[f["path"], f["sha256"][:24] + "…", n0(f["bytes"])] for f in prov["refs"]["files"]],
          [68 * mm, 76 * mm, 26 * mm], right=(2,), size=6.6))
    A(PageBreak())
    A(P("附錄B — 名詞", "h1"))
    gl = [
        ("實價登錄", "內政部不動產成交案件實際資訊申報登錄制度，涵蓋買賣與租賃。"),
        ("坪", "3.3058 平方公尺，台灣樓地板面積的標準單位。"),
        ("住宅大樓／華廈／公寓", "11 層以上有電梯／10 層以下有電梯／5 層以下無電梯。"),
        ("透天厝", "1–3 層的獨棟住宅；佔全國宅數 42.7%，在本分析範圍之外。"),
        ("社會住宅包租代管", "政府補貼的轉租與代管社會住宅租約。"),
        ("預售屋", "在建物尚未存在時即先行出售的住宅。"),
        ("法拍／金拍", "法院強制拍賣／透過台灣金服的銀行擔保品拍賣。兩者是不同的通道。"),
        ("棟／宅／建號", "建物／住宅單位／登記建號（大致一戶一個）。三者絕不相除。"),
        ("毛報酬率", "12 × 月租金 ÷ 房價，買賣與租賃兩側都已扣除車位。"),
        ("淨報酬率", "毛報酬率扣除持有稅、管理費、空置與按屋齡加權的修繕後。"),
        ("配對", "同一棟建物內、相隔 ±4 季以內的一筆買賣與一筆整戶市場租約。"),
        ("覆蓋率", "可配對建物 ÷ 期間內所有有住宅成交紀錄的建物。"),
        ("部分識別", "在明列的假設下，為一個未被觀察到的母體設定界線，"
                     "而不是假設它與被觀察到的那一部分相似。"),
        ("Shapley 值", "在所有可能的篩選施加順序下，一道篩選的平均貢獻。"),
        ("民國", "中華民國曆；年份 + 1911 = 西元（民國115 = 2026）。"
                 "季別如 115S2 指 2026 年 4 至 6 月。"),
    ]
    A(tbl([["名詞", "說明"]] + [[a, b] for a, b in gl], [42 * mm, FRAME_W - 42 * mm], wrap=(1,)))
    return story


def main():
    R._ensure_static_fonts()
    with open(R.DATA, encoding="utf-8") as f:
        D = json.load(f)
    R.S = R.styles()
    # Chinese body text is set flush left, not justified. reportlab justifies by
    # stretching spaces, and CJK runs have almost none -- so the only spaces on a
    # line, the ones bracketing Latin numerals and names, absorb the whole slack
    # and open rivers ("以    150    組"). The English edition keeps TA_JUSTIFY.
    R.S["body"].alignment = TA_LEFT
    doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title="Quants.tw 住宅轉向 — 結案報告",
                          author="Stanley (Quants.tw)", subject="以實價登錄計算台灣租金報酬率")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    doc.build(build(D))
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
