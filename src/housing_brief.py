#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The two-page brief: what you send to a reader who has not asked for 27 pages.

    venv/bin/python3 src/housing_brief.py   -> docs/HOUSING_BRIEF.pdf

Why this exists. The full report is the right document for someone who has
decided to check the work, and the wrong one for someone deciding whether to.
A cold email with a 27-page attachment is a cold email that does not get read.

Why it is generated and not written. Every figure here is read from
housing_data.json at build time, through the same helpers the report uses, so
the brief cannot quietly disagree with the paper it summarises --
tests/test_report_editions.py pins that all four documents state the same
headline numbers. A hand-written summary is a fifth place for a number to go
stale, and section 17 of the report is a list of what happens when numbers live
in prose.
"""
import json
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate,
                                Spacer)

import housing_final_report as R
from housing_final_report import (ACCENT, FRAME_W, MUTED, RULE, F, callout, n0, p2, pp,
                                  tbl, tiles, PAPER_VERSION, PAPER_DATE)
from references import GPG_CITIES, GPG_UPDATED, cite_t

OUT = os.environ.get("BRIEF_OUT", os.path.join(R.ROOT, "docs", "HOUSING_BRIEF.pdf"))
DOI = "10.5281/zenodo.23902646"
REPO = "github.com/Stanley0210/taiwan-rental-yield"


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(F, 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, f"實價收益 · brief · paper {PAPER_VERSION} · doi.org/{DOI}")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"{doc.page} / 2")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
    canvas.restoreState()


def build(D):
    P, bullets = R.P, R.bullets
    h, meta = D["headline"], D["meta"]
    boot, wf, pid = D["bootstrap"], D["coverage_waterfall"], D["partial_id"]
    rungs = {r["key"]: r for r in pid["rungs"]}
    cov = {c["type"]: c for c in D["coverage"]}
    age, rz = D["age"], (D.get("resemblance") or {}).get("vars") or {}
    story = []
    A = story.append

    A(P("實價收益 — the visible range of Taiwan's rental yield", "part"))
    A(P("A rental yield needs a sale price and a rent for the same building. "
        "Taiwan's 實價登錄 publishes both. For most buildings it publishes only one.", "title"))
    A(Spacer(1, 3))
    A(P(f"Two-page brief · paper edition {PAPER_VERSION} ({PAPER_DATE}) · payload v{meta['provenance']['version']} · "
        f"window {meta['seasons'][0]}–{meta['seasons'][1]}", "sub"))
    A(Spacer(1, 7))

    A(tiles([(p2(h["yield"]), f"median gross yield<br/>95% CI {boot['overall']['lo']:.2f}–{boot['overall']['hi']:.2f}"),
             (p2(h["net"]), f"median net yield<br/>95% CI {boot['overall_net']['lo']:.2f}–{boot['overall_net']['hi']:.2f}"),
             (p2(h["coverage_pct"]), f"of {n0(h['universe_buildings'])} buildings<br/>that sold, priceable"),
             (n0(h["buildings"]), f"matched buildings<br/>{n0(h['pairs'])} sale–lease pairs")]))
    A(Spacer(1, 7))

    A(P("Method", "h2"))
    A(P(f"Pair a registered sale with a registered lease <i>in the same building</i> within four "
        f"quarters, and a gross yield falls out with no modelling. Done nationally over "
        f"{meta['n_seasons']} quarters: {n0(h['pairs'])} pairs across {n0(h['buildings'])} buildings. "
        "Every headline is a median of per-building medians, never per pair — pairs concentrate in "
        f"mega-towers, and the pair-weighted figure ({p2(h['pair_level_yield'])}) overweights exactly "
        "the least typical buildings. Intervals are a two-stage bootstrap over buildings then pairs; "
        "net deducts four costs, each sourced or bounded."))

    A(P("The finding is the denominator", "h2"))
    A(P(f"Those medians describe <b>{n0(h['buildings'])} of {n0(h['universe_buildings'])}</b> buildings "
        f"that sold — <b>{p2(h['coverage_pct'])}</b>. Remove every quality filter this project "
        f"applies and the registry's structural ceiling is <b>{p2(h['coverage_ceiling_pct'])}</b>, "
        f"because {wf['law_share']}% of the loss is the registry itself: a lease that was never "
        "filed cannot be recovered by better cleaning."))
    A(P(f"<b>And matchability is itself selective.</b> You can price one apartment tower in "
        f"{round(100/cov['住宅大樓']['match_rate'])} and one walk-up in "
        f"{round(100/cov['公寓']['match_rate'])}. Walk-ups are {p2(cov['公寓']['share_all'])} of the "
        f"buildings that sell and {p2(cov['公寓']['share_matched'])} of those you can measure. The "
        f"buildings you can see are <b>{age['ppp_diff_pct']:.1f}% dearer per 坪</b> and "
        f"<b>{age['matched_built'] - age['unmatched_built']:.0f} years newer</b> than the ones you "
        "cannot."))

    A(P("So the number is replaced by a range — and the range is honest about its assumption", "h2"))
    bd, tp = rungs["band"]["gross"], rungs["type_price"]["gross"]
    A(P(f"Assuming nothing about the unseen, the median of all {n0(pid['scope']['n'])} buildings lies "
        f"in <b>[{bd['lo']:.2f}%, {bd['hi']:.2f}%]</b>. Assuming the unseen resemble seen buildings of "
        f"the same type and price decile, <b>[{tp['lo']:.2f}%, {tp['hi']:.2f}%]</b>. Every rung "
        "between is published, including one that makes the interval <i>wider</i> and is kept "
        "because it fails."))
    if rz:
        bz, az = rz["built"], rz["area"]
        A(callout(
            f"<b>That resemblance assumption is tested, and it half fails.</b> Conditioning on type "
            f"and price decile absorbs {bz['absorbed_pct']:.0f}% of the age gap between matched and "
            f"unmatched buildings — but it makes the <i>size</i> gap worse, from "
            f"{az['unconditional_d']:+.2f} to {az['within_cell_signed_d']:+.2f} standard deviations, "
            f"with {az['cells_unbalanced']} of {az['cells']} cells unbalanced. The cells are cut on "
            "price per 坪 and 坪 is that ratio's denominator, so banding on it frees the size gap "
            "instead of closing it. The interval is a stated-assumption interval, not a validated "
            f"one — and it cannot be repaired by conditioning further: at {p2(h['coverage_pct'])} "
            "coverage the cells run out of buildings first.",
            "The one number here that is not good news"))
    A(P(f"<b>Why it cannot be narrowed.</b> A median's worst-case interval only leaves the support "
        f"band once more than {pid['median_bound_requires_coverage_pct']:.0f}% of the population is "
        f"observed, and this registry can never show more than {p2(h['coverage_ceiling_pct'])}. The "
        "width is a property of the registry, not of the cleaning.", "note"))

    A(P("Against the figure in circulation", "h2"))
    A(P(f"{cite_t('chang2018')} report a gross rent multiplier of 64 for Taiwan and a yield of "
        "1.57%; the stated source of that table is Global Property Guide, a commercial listings "
        "aggregator computing median <i>asking</i> rent over median <i>list</i> price. So the "
        "peer-reviewed Taiwan number and the consumer-facing one are the same number, and neither "
        "is built on transaction data. City by city, against the five both cover:"))
    gp = sorted([c for c in D["counties"] if c["city"] in GPG_CITIES], key=lambda c: -c["buildings"])
    rows = [["City", "This work (transacted)", "95% CI", "buildings", f"Listings ({GPG_UPDATED})", "diff"]]
    for c in gp:
        g = GPG_CITIES[c["city"]]
        ci = boot["county"].get(c["county"])
        rows.append([c["city"], p2(c["yield"]), f"{ci['lo']:.2f}–{ci['hi']:.2f}" if ci else "—",
                     n0(c["buildings"]), p2(g), pp(c["yield"] - g)])
    A(tbl(rows, [24 * mm, 30 * mm, 24 * mm, 22 * mm, 30 * mm, FRAME_W - 130 * mm],
          right=(1, 2, 3, 4, 5), size=7.8))
    A(Spacer(1, 4))
    worst = max(gp, key=lambda c: c["yield"] - GPG_CITIES[c["city"]])
    A(P(f"Higher in all five, widening going south — {worst['city']} differs by "
        f"{pp(worst['yield'] - GPG_CITIES[worst['city']])}. Indicative, not like-for-like: different "
        "footprints, units and windows. Taipei has three independent estimates, agreeing to about a "
        "tenth of a point.", "note"))

    A(P("What was withdrawn", "h2"))
    A(KeepTogether(bullets([
        "<b>The founding hypothesis is unanswerable.</b> Walk-ups out-yield towers and the sign "
        "survives every control, but matched towers depart from their own population far more than "
        "matched walk-ups do, and two separately skewed samples cannot settle a population question. "
        "Its proposed mechanism is separately falsified: where the modelled fee is zero, the gap stays.",
        "<b>The transit gradient is retracted.</b> It survived only if 輕軌 did not count as a "
        "station, and vanished entirely in Kaohsiung.",
        "<b>\"One building in 1,086\" is withdrawn.</b> It divided 棟 by 建號 — two different units.",
    ])))

    A(Spacer(1, 4))
    A(P(f"Every figure above is read from <i>housing_data.json</i> at build time, whose SHA-256 is "
        f"pinned beside it, and the payload hashes every source archive the build read. "
        f"<b>{REPO}</b> · <b>doi.org/{DOI}</b> · full report 27pp, English and 中文.", "note"))

    A(callout(
        "<b>1 · Coverage.</b> Does 實價登錄 really receive only leases filed through licensed "
        f"rental-service and brokerage firms? That rule carries {wf['law_pp']:.0f} of the "
        f"{100 - h['coverage_pct']:.0f} percentage points of non-coverage — the load-bearing fact "
        "here.<br/>"
        "<b>2 · Conditioning.</b> Given the balance result, is there a conditioning set this "
        "registry supports that beats type × price decile — or is partial identification the end "
        "of the road?<br/>"
        f"<b>3 · The cost model.</b> Does {p2(h['net'])} net match what practitioners see, and is "
        "charging a management fee only where a lease records on-site staff defensible?",
        "The three questions I would most like answered"))
    return story


def main():
    R.S = R.styles()
    # The report's title style is sized for a cover page. Here it is a lead
    # paragraph on a two-page document, so it is scaled down rather than
    # forked -- the brief shares every other style with the paper.
    R.S["title"].fontSize, R.S["title"].leading = 18, 23
    R._ensure_static_fonts()
    with open(R.DATA, encoding="utf-8") as f:
        D = json.load(f)
    doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title="實價收益 — the visible range of Taiwan's rental yield (brief)",
                          author="Stanley (Quants.tw)",
                          subject="Taiwan rental yield from 實價登錄 — two-page brief")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=footer)])
    doc.build(build(D))
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
