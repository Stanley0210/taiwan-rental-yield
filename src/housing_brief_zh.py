#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兩頁摘要（中文版）。

    venv/bin/python3 src/housing_brief_zh.py   -> docs/HOUSING_BRIEF_ZH.pdf

Same reasoning as the English brief: the full report is the right document for
someone who has decided to check the work and the wrong one for someone
deciding whether to. Separate generator, shared helpers -- the standing rule in
this repository is that the two languages never share a positional template.

Text goes through the Chinese edition's pipeline (_bind for the line-break
binding, _safe for the font's real cmap), so the brief inherits every fix the
中文版 report earned.
"""
import json
import os

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate,
                                Spacer)

import housing_final_report as R
import housing_brief as B
from housing_final_report import FRAME_W, n0, p2, pp, tbl, tiles, PAPER_VERSION
from housing_final_report_zh import P, bullets, callout, ZH_EDITION_DATE
from references import GPG_CITIES, GPG_UPDATED, cite_t

OUT = os.environ.get("BRIEF_OUT_ZH", os.path.join(R.ROOT, "docs", "HOUSING_BRIEF_ZH.pdf"))


def build(D):
    h, meta = D["headline"], D["meta"]
    boot, wf, pid = D["bootstrap"], D["coverage_waterfall"], D["partial_id"]
    rungs = {r["key"]: r for r in pid["rungs"]}
    cov = {c["type"]: c for c in D["coverage"]}
    age, rz = D["age"], (D.get("resemblance") or {}).get("vars") or {}
    story = []
    A = story.append

    A(P("實價收益 — 全臺灣租金報酬率的可見範圍", "part"))
    A(P("要算一間房子的租金報酬率，你需要同一棟樓的成交價與租金。"
        "實價登錄兩者都有公布。但對大多數建物，它只公布其中一樣。", "title"))
    A(Spacer(1, 3))
    A(P(f"兩頁摘要 · 論文版本 {PAPER_VERSION}（{ZH_EDITION_DATE}）· "
        f"資料版本 v{meta['provenance']['version']} · "
        f"期間 {meta['seasons'][0]}–{meta['seasons'][1]}", "sub"))
    A(Spacer(1, 7))

    A(tiles([(p2(h["yield"]), f"毛報酬率中位數<br/>95% 信賴區間 {boot['overall']['lo']:.2f}–{boot['overall']['hi']:.2f}"),
             (p2(h["net"]), f"淨報酬率中位數<br/>95% 信賴區間 {boot['overall_net']['lo']:.2f}–{boot['overall_net']['hi']:.2f}"),
             (p2(h["coverage_pct"]), f"{n0(h['universe_buildings'])} 棟成交建物中<br/>算得出報酬率的比例"),
             (n0(h["buildings"]), f"可配對建物<br/>{n0(h['pairs'])} 組買賣—租賃配對")]))
    A(Spacer(1, 7))

    A(P("方法", "h2"))
    A(P(f"把一筆登錄的買賣，與<i>同一棟樓</i>內相隔四季以內的一筆登錄租約配成對，"
        f"毛報酬率就直接算得出來，完全不需要任何模型。以全國資料、涵蓋 {meta['n_seasons']} 季："
        f"{n0(h['buildings'])} 棟建物、{n0(h['pairs'])} 組配對。"
        "每一個主要數字都是「各棟中位數」的中位數，絕不以配對計——配對集中在少數巨型大樓，"
        f"以配對加權的數字（{p2(h['pair_level_yield'])}）剛好會加重那些最不具代表性的建物。"
        "區間來自先重抽建物、再重抽棟內配對的兩階段拔靴法；淨報酬率扣除四項成本，每一項都有來源或界線。"))

    A(P("真正的發現是分母", "h2"))
    A(P(f"上面那些中位數描述的，是 {n0(h['universe_buildings'])} 棟成交建物裡的 "
        f"<b>{n0(h['buildings'])} 棟</b>——也就是 <b>{p2(h['coverage_pct'])}</b>。"
        f"把本專案的每一道品質篩選全部拿掉，實價登錄的結構上限是 "
        f"<b>{p2(h['coverage_ceiling_pct'])}</b>，因為全部流失裡有 {wf['law_share']}% 是登錄制度本身："
        "一份從未被申報的租約，再怎麼清理也救不回來。"))
    A(P(f"<b>而且「可配對」這件事本身就是有選擇性的。</b>住宅大樓每 "
        f"{round(100/cov['住宅大樓']['match_rate'])} 棟算得出一棟，公寓每 "
        f"{round(100/cov['公寓']['match_rate'])} 棟才算得出一棟。公寓佔成交建物的 "
        f"{p2(cov['公寓']['share_all'])}，卻只佔算得出報酬率者的 {p2(cov['公寓']['share_matched'])}。"
        f"看得見的那些建物，每坪比看不見的<b>貴 {age['ppp_diff_pct']:.1f}%</b>、"
        f"<b>新 {age['matched_built'] - age['unmatched_built']:.0f} 年</b>。"))

    A(P("所以單一數字被換成一個區間——而這個區間對自己的假設很誠實", "h2"))
    bd, tp = rungs["band"]["gross"], rungs["type_price"]["gross"]
    A(P(f"對看不見的部分完全不做假設時，全部 {n0(pid['scope']['n'])} 棟建物的報酬率中位數落在 "
        f"<b>[{bd['lo']:.2f}%、{bd['hi']:.2f}%]</b>。"
        f"假設看不見的那些，長得像同型態、同價格十分位中看得見的那些，則是 "
        f"<b>[{tp['lo']:.2f}%、{tp['hi']:.2f}%]</b>。"
        "中間每一階都公布出來，包括一階反而把區間撐寬、而且正因為它失敗才被保留。"))
    if rz:
        bz, az = rz["built"], rz["area"]
        A(callout(
            f"<b>那個相似性假設被檢驗過了，而它只有一半成立。</b>以型態與價格十分位條件化，"
            f"吸收了可配對與配不到建物之間 {bz['absorbed_pct']:.0f}% 的屋齡落差——"
            f"但它把<i>面積</i>落差變得更糟，從 {az['unconditional_d']:+.2f} 變成 "
            f"{az['within_cell_signed_d']:+.2f} 個標準差，{az['cells']} 個格子裡有 "
            f"{az['cells_unbalanced']} 個未達平衡。格子是依每坪單價切的，而「坪」正是它的分母，"
            "用比值分帶等於放開面積落差，而不是收斂它。所以這個區間是「在明列假設下」的區間，"
            f"不是一個已被驗證的區間——而且它修不了：在 {p2(h['coverage_pct'])} 的覆蓋率下，"
            "格子的棟數會先用完。",
            "這裡唯一一個不是好消息的數字"))
    A(P(f"<b>為什麼它無法再收窄。</b>中位數的最壞情況區間，只有在觀察到超過母體 "
        f"{pid['median_bound_requires_coverage_pct']:.0f}% 之後才會離開支撐區，"
        f"而這套登錄資料最多只能看到 {p2(h['coverage_ceiling_pct'])}。"
        "這個寬度是登錄制度的性質，不是清理方式的問題。", "note"))

    A(P("與流通中的那個數字相比", "h2"))
    A(P(f"{cite_t('chang2018')} 給出臺灣的租金乘數 64、報酬率 1.57%；"
        "那張表自己註明的來源是 Global Property Guide——一個商業刊登網站的彙整，"
        "算法是「刊登租金中位數除以刊登價格中位數」。也就是說，經過同儕審查的那個臺灣數字"
        "與面向消費者的那個是同一個數字，而兩者都不是建立在成交資料上。逐一城市對照，"
        "兩邊都涵蓋的那五個："))
    gp = sorted([c for c in D["counties"] if c["city"] in GPG_CITIES], key=lambda c: -c["buildings"])
    rows = [["城市", "本研究（成交）", "95% 信賴區間", "棟數", f"刊登（{GPG_UPDATED}）", "差異"]]
    for c in gp:
        g = GPG_CITIES[c["city"]]
        ci = boot["county"].get(c["county"])
        rows.append([c["city"], p2(c["yield"]), f"{ci['lo']:.2f}–{ci['hi']:.2f}" if ci else "—",
                     n0(c["buildings"]), p2(g), pp(c["yield"] - g)])
    A(tbl(rows, [22 * mm, 28 * mm, 26 * mm, 20 * mm, 30 * mm, FRAME_W - 126 * mm],
          right=(1, 2, 3, 4, 5), size=7.4))
    A(Spacer(1, 4))
    worst = max(gp, key=lambda c: c["yield"] - GPG_CITIES[c["city"]])
    A(P(f"五個城市全部都是登錄資料算出來的比較高，往南落差愈大——{worst['city']}差 "
        f"{pp(worst['yield'] - GPG_CITIES[worst['city']])}。這只是指示性的對照，並非嚴格同類比較："
        "涵蓋範圍、單位與期間都不同。臺北市有三個獨立估計，彼此相差約零點一個百分點。", "note"))

    A(P("被撤回的結果", "h2"))
    A(KeepTogether(bullets([
        "<b>最初的假設無法回答。</b>公寓的報酬率確實高於大樓，而且這個方向通過每一道控制；"
        "但可配對的大樓偏離它自己的母體，遠比可配對的公寓嚴重，"
        "而兩個各自偏斜的樣本無法判定一個母體層次的問題。"
        "它所提出的機制也被另外推翻了：在模型管理費為零的地方，落差依然存在。",
        "<b>捷運的距離梯度已撤回。</b>只有在「輕軌不算車站」的情況下它才存在，而且在高雄完全消失。",
        "<b>「1,086 棟裡有一棟」已撤回。</b>它拿「棟」去除以「建號」——那是兩個不同的單位。",
    ])))
    A(Spacer(1, 4))
    A(P(f"上面每一個數字都是在建置時從 <i>housing_data.json</i> 讀出來的，"
        f"它的 SHA-256 就釘在旁邊，而資料檔也為這次建置讀過的每一份原始壓縮檔留了雜湊值。"
        f"<b>{B.REPO}</b> · <b>doi.org/{B.DOI}</b> · 完整報告 27 頁，有英文版與中文版。", "note"))

    A(callout(
        "<b>1 · 覆蓋率。</b>實價登錄是否真的只收到透過合法登記的租賃住宅服務業與不動產經紀業"
        f"申報的租約？這條規則承擔了 {100 - h['coverage_pct']:.0f} 個百分點未覆蓋當中的 "
        f"{wf['law_pp']:.0f} 個——也是本研究最承重的一項事實。<br/>"
        "<b>2 · 條件化。</b>在上面那個平衡檢驗的結果之下，這套登錄資料是否還支持某一組條件化變數，"
        "能夠勝過「型態×價格十分位」——還是說，部分識別就是這裡的終點？<br/>"
        f"<b>3 · 成本模型。</b>{p2(h['net'])} 的淨報酬率，與實務上看到的相符嗎？"
        "而「只對租約有記載管理員的建物收管理費」這個做法站得住腳嗎？",
        "我最想得到答案的三個問題"))
    return story


def main():
    R._ensure_static_fonts()
    R.S = R.styles()
    R.S["body"].alignment = TA_LEFT      # the ZH edition's rule: no justified CJK rivers
    R.S["title"].fontSize, R.S["title"].leading = 18, 25
    with open(R.DATA, encoding="utf-8") as f:
        D = json.load(f)
    doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title="實價收益 — 全臺灣租金報酬率的可見範圍（兩頁摘要）",
                          author="Stanley (Quants.tw)", subject="以實價登錄計算台灣租金報酬率 — 兩頁摘要")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=B.footer)])
    doc.build(build(D))
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
