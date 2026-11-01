"""
underwrite.py — match sales to leases in the same building, and compute yields.

The whole point of this project in one sentence: a rental yield is only honest
if the rent and the price describe the *same building*, and almost nobody
computes it that way because the address join is annoying.

Two design decisions here are load-bearing and easy to get wrong:

1. **Aggregate to the building, never to the pair.** A tower with 40 sales and
   30 leases generates 1,200 "pairs" from 70 records. Measured on real data the
   top 10 buildings produced 38% of all pairs, and one building alone produced
   5,354. A pair-level median is therefore a median of a handful of large
   towers wearing a large-n disguise. Every published statistic in this file is
   computed with one observation per building.

2. **Index prices to the lease's quarter.** Pairing tolerates a +/-4 quarter gap,
   and Taipei prices moved over the window, so an unindexed pair silently books
   part of the price trend as yield. `district_price_index()` builds a
   NT$/坪-by-quarter index from our own (dense) sale side and restates every
   sale at the lease's quarter. `gap_sensitivity()` is the check: if the
   correction works, yield is flat across the pairing gap.

Everything below the PURE COMPUTE banner is dependency-free and unit-tested
offline; nothing in this module touches the network or a database.
"""

import datetime
import gzip
import hashlib
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd

import basemap as BM
import boundaries as BD
import fetch_lvr as L
import geocode as G
from normalize_addr import addr_key, street_key

LAST_SEASON = os.environ.get("LVR_LAST_SEASON", "115S2")
WINDOW_FIRST = None   # set by build() once the season list is known
OUT = os.environ.get("LVR_OUT", "housing_data.json")

# Bump on any change that moves a published number. The page prints it beside
# the build date and the source hash, so a reader who comes back in six months
# can tell whether they are looking at different code or different data --
# 實價登錄 grows every quarter, and without this a rebuild that disagrees is
# indistinguishable from a bug.
PAYLOAD_VERSION = "2.8"

MATCH_WINDOW_Q = 4          # +/- quarters a sale and a lease may be apart

# ── THE PRICE INDEX IS OFF, AND THAT IS A RESULT ─────────────────────────────
# The plan called for restating each sale at the lease's quarter via a
# district-quarter price index, on the theory that a +/-4 quarter pairing gap
# would otherwise book price drift as yield. Built it, measured it, and it makes
# the symptom WORSE at every window:
#
#     window   unindexed slope   indexed slope   buildings
#     +/-2        +0.034 pp        +0.064 pp        2,073
#     +/-4        +0.056 pp        +0.071 pp        2,550
#
# (slope = median yield at the widest gap minus median yield at gap 0)
#
# If the slope were drift, indexing would flatten it. It steepens it, at both
# windows — so the district-quarter medians are contributing more noise than the
# drift they remove, and the residual slope is a COMPOSITION effect: buildings
# whose sale and lease sit far apart are systematically different (thinner,
# less liquid) from those transacting in the same quarter. Narrowing the window
# to +/-2 costs 19% of the sample and buys 0.02 pp, which is not a trade worth
# making.
#
# So: index OFF by default. district_price_index() and the comparison are kept
# because the negative result is worth more than the correction was.
USE_PRICE_INDEX = os.environ.get("LVR_PRICE_INDEX", "0") == "1"
MIN_DISTRICT_N = 25         # buildings needed before a district is reported
YIELD_BAND = (0.3, 12.0)    # %; outside this a record is a data error, not a deal

# ── COST MODEL ───────────────────────────────────────────────────────────────
# Every default below is SOURCED, and the source is carried into the payload so
# the page can show it next to the number. None of these are in 實價登錄; they
# are the difference between a gross yield (data) and a net yield (a model).
#
# holding tax: 房屋稅 + 地價稅 as an EFFECTIVE rate on MARKET PRICE. Modelling it
#   that way sidesteps 房屋課稅現值 entirely, which is the right move because the
#   assessed base is exactly what is unknowable from a transaction record.
#   彭建文等 (2007), Taipei 大同/內湖 actual cases:      0.0886% - 0.1304%
#   王宏文・曾彥閔 (2013), Taipei residential:            0.066%
#   李明軒 (中山大學), nominal 0.6% vs effective:         ~0.12%
#   Those measure SELF-USE. 囤房稅2.0 (2024-07) raised the 房屋稅 leg for
#   non-self-use from 1.2% to 2.0-4.8% (全國歸戶); 地價稅 is unchanged. A rented
#   unit therefore sits above the measured range but below 2x it. 0.15% is the
#   midpoint of that reasoning and is deliberately adjustable on the page.
DEFAULT_TAX_PCT = 0.15
# management fee, NT$ per 坪 per month. Taipei general residential runs
# NT$100-180 (TWProbe 2026 survey; ETtoday 2026), New Taipei NT$90-120.
# Applied ONLY where the building is OBSERVED to have staff (有無管理員=有) —
# that flag is in the lease records, so this is data-gated, not type-guessed.
DEFAULT_MGMT_A = 140.0      # 臺北市
DEFAULT_MGMT_F = 105.0      # 新北市
# vacancy. No Taiwan rental-vacancy statistic exists; the widely quoted 8.77%
# is a PERIOD-SPECIFIC reading (111H2) of a different population, not a constant
# 空屋率 is低度用電-derived EMPTY HOMES, a different and larger population.
# 5% ~ 18 days of turnover a year. Pure assumption, labelled as one.
DEFAULT_VACANCY_PCT = 5.0
# repairs as % of gross rent, scaled by building age: a 50-year walk-up costs
# more to keep lettable than a 5-year tower, and a FLAT rate would bias the
# 公寓-vs-大樓 comparison in precisely the direction the dead hypothesis predicted.
DEFAULT_REPAIRS_PCT = 6.0

TYPE_SHORT = {
    "住宅大樓(11層含以上有電梯)": "住宅大樓",
    "華廈(10層含以下有電梯)": "華廈",
    "公寓(5樓含以下無電梯)": "公寓",
}


# ═══════════════════════════════════════════════════════ PURE COMPUTE ════

def district_price_index(sales):
    """Median NT$/坪 per (county, district, quarter), normalised to the district
    mean. Returns {(county, district, q): factor}.

    Built from sales because sales are the dense side (~76k rows vs ~20k leases).
    A district-quarter cell with fewer than 10 sales is left at 1.0 rather than
    given a noisy factor — a thin cell would inject more error than the drift it
    is meant to remove.
    """
    if sales.empty:
        return {}
    s = sales.assign(ppp=sales.price / sales.area_ping)
    g = s.groupby(["county", "district", "q"])["ppp"].agg(["median", "size"])
    idx = {}
    for (c, d), grp in g.groupby(level=[0, 1]):
        solid = grp[grp["size"] >= 10]["median"]
        if len(solid) < 2:
            continue
        base = solid.mean()
        if not np.isfinite(base) or base <= 0:
            continue
        for (_, _, q), row in grp.iterrows():
            idx[(c, d, q)] = (row["median"] / base
                              if row["size"] >= 10 and np.isfinite(row["median"])
                              else 1.0)
    return idx


def match_pairs(sales, rents, window=MATCH_WINDOW_Q, index=None):
    """Tier-1 join: same normalised building key, within `window` quarters.

    When `index` is supplied the sale price is restated at the lease's quarter,
    so the pair measures a yield rather than a yield plus however much the
    district moved in between.
    """
    if sales.empty or rents.empty:
        return pd.DataFrame()
    scols = ["county", "district", "k", "q", "price", "area_ping",
             "bldg_type", "built_roc_y"]
    if "total_floor" in sales.columns:
        scols.append("total_floor")
    s = sales[scols]
    rcols = ["county", "k", "q", "rent", "area_ping"]
    for extra in ("has_mgr", "rent_incl_mgmt", "rent_excl_mgmt", "park_unpriced"):
        if extra in rents.columns:
            rcols.append(extra)
    r = rents[rcols]
    m = s.merge(r, on=["county", "k"], suffixes=("_s", "_r"))
    for extra in ("has_mgr", "rent_incl_mgmt", "rent_excl_mgmt", "park_unpriced"):
        if extra not in m.columns:
            m[extra] = 0
    if "total_floor" not in m.columns:
        m["total_floor"] = None
    if m.empty:
        return m
    m["gap"] = (m.q_s - m.q_r).abs()
    m = m[m.gap <= window].copy()
    if m.empty:
        return m
    price = m.price.to_numpy(dtype=float)
    if index:
        fs = np.array([index.get((c, d, q), 1.0) for c, d, q
                       in zip(m.county, m.district, m.q_s)])
        fr = np.array([index.get((c, d, q), 1.0) for c, d, q
                       in zip(m.county, m.district, m.q_r)])
        price = price * np.where(fs > 0, fr / fs, 1.0)
    m["price_adj"] = price
    m["gross"] = (m.rent * 12.0) / m.price_adj * 100.0
    lo, hi = YIELD_BAND
    return m[(m.gross > lo) & (m.gross < hi)]


def roc_ym(v):
    """ROC yyyymmdd -> decimal ROC year. 1130415 -> 113.25.

    Module-level because two blocks need the same predicate: the presale
    comparison group (age >= 0 at contract) and the volume count, which drops
    presale-origin rows with the identical test. One definition, or the two
    sections silently disagree about what an "existing" home is.
    """
    v = pd.to_numeric(v, errors="coerce")
    return (v // 10000) + (((v // 100) % 100).clip(1, 12) - 1) / 12.0


def _tw(series):
    """臺 vs 台.

    The registry writes 台東市; 內政部's boundary shapefile writes 臺東市, and
    every other district name in both files already agrees. One character, and
    it orphaned 9 buildings: their district key had no polygon, so they could
    not be drawn, could not be opened, and 臺東市 never appeared as a mark at
    all. geocode's "district agreement 100%" check cannot catch this, because
    both sides of that comparison come from the registry.
    """
    return series.str.replace("台", "臺", regex=False)


def _mode(s):
    """Most common value, for fields the registry sometimes disagrees with itself
    about across records for one building."""
    m = s.mode()
    return m.iat[0] if len(m) else None


def to_buildings(pairs):
    """Collapse pairs to ONE row per building. This is the unit of analysis.

    Grouped on (county, addr_key) ALONE. Grouping on 建物型態 as well looked
    natural and was wrong: the registry types the same building inconsistently
    (華廈 on one record, 住宅大樓 on another), which split 8 buildings into two
    rows each and double-counted them in every median and coverage denominator.
    A building has one type; where the records disagree, the modal one wins.
    """
    if pairs.empty:
        return pd.DataFrame()
    g = pairs.groupby(["county", "k"], as_index=False).agg(
        district=("district", _mode),
        bldg_type=("bldg_type", _mode),
        gross=("gross", "median"),
        price_ping=("price_adj", lambda x: np.median(x)),
        area=("area_ping_s", "median"),
        rent=("rent", "median"),
        rent_area=("area_ping_r", "median"),
        built=("built_roc_y", "median"),
        pairs=("gross", "size"),
        gap=("gap", "median"),
        has_mgr=("has_mgr", lambda x: int(round(float(pd.Series(x).mean() or 0)))),
        # ANY-let rule, unlike has_mgr's majority rule: one lease saying the
        # rent includes the fee is a statement about the building's practice;
        # the majority count is published beside it so the choice is visible.
        mgmt_incl_any=("rent_incl_mgmt", "max"),
        mgmt_incl_share=("rent_incl_mgmt", "mean"),
        mgmt_excl_any=("rent_excl_mgmt", "max"),
        # share of the building's pairs whose lease is an un-itemised bundled
        # one -- the rows the parking audit is about
        park_unp_share=("park_unpriced", "mean"),
        floors=("total_floor", _mode),
    )
    g["price_ping"] = g.price_ping / g.area
    g["rent_ping_yr"] = g.rent * 12.0 / g.rent_area
    return g


def median(series):
    s = pd.Series(series).dropna()
    return round(float(s.median()), 4) if len(s) else None


def net_yield(price, annual_rent, area_ping, has_mgr, age_yrs, county,
              tax_pct=DEFAULT_TAX_PCT, mgmt_a=DEFAULT_MGMT_A, mgmt_f=DEFAULT_MGMT_F,
              vacancy_pct=DEFAULT_VACANCY_PCT, repairs_pct=DEFAULT_REPAIRS_PCT):
    """Gross rent minus the four cost terms, over price. Percent.

    Kept as a pure function of explicit arguments (rather than reading module
    defaults inline) so the page can recompute it live from the assumptions
    panel and get exactly the number this file would have produced. The JS twin
    in housing.js MUST stay in lockstep with this arithmetic.
    """
    if not price or price <= 0 or not annual_rent:
        return None
    effective = annual_rent * (1.0 - vacancy_pct / 100.0)
    mgmt = (mgmt_a if county == "a" else mgmt_f) * area_ping * 12.0 if has_mgr else 0.0
    tax = price * tax_pct / 100.0
    age = 0.0 if age_yrs is None or age_yrs != age_yrs else max(0.0, age_yrs)
    repairs = annual_rent * (repairs_pct / 100.0) * (1.0 + age / 50.0)
    return (effective - mgmt - tax - repairs) / price * 100.0


def mgmt_exposure(b):
    """How much of the net yield rests on a fee sourced for two cities.

    `net_yield` charges 臺北市 NT$140/坪/月 and EVERYWHERE ELSE NT$105 — the
    New Taipei rate — because those are the two cities the published surveys
    cover and the site used to stop there. It now covers 22 counties, so 20 of
    them are being charged a metropolitan fee for want of a source.

    There is no per-county management-fee statistic to wire in, so this does what
    the vacancy term does: instead of guessing a better number, it measures what
    the assumption is worth. If halving or zeroing the fee outside 北北 barely
    moves the headline, the exposure is small and stated; if it does move it, the
    reader needs to know before quoting the net yield.
    """
    if b is None or b.empty:
        return {}
    out_of_area = b[~b.county.isin(["a", "f"])]
    affected = out_of_area[out_of_area.has_mgr == 1]
    rows = []
    for label, rate in (("default", DEFAULT_MGMT_F), ("half", DEFAULT_MGMT_F / 2),
                        ("zero", 0.0)):
        nets = [net_yield(p, ar, ap, hm, ag, c, mgmt_f=rate)
                for p, ar, ap, hm, ag, c in zip(b.price_abs, b.annual_rent, b.area,
                                                b.has_mgr, b.age, b.county)]
        rows.append({"case": label, "mgmt_f": round(rate, 1), "net": median(pd.Series(nets))})
    base = rows[0]["net"]
    for r in rows:
        r["delta_pp"] = round((r["net"] or 0) - (base or 0), 4)
    return {
        "buildings_outside": int(len(out_of_area)),
        "buildings_charged": int(len(affected)),
        "share_charged_pct": round(len(affected) / max(1, len(b)) * 100, 1),
        "counties_outside": int(out_of_area.county.nunique()),
        "cases": rows,
    }


def mgmt_flag_block(rents, pairs, b, n_boot=120, seed=13):
    """What the lease itself says about the management fee, as two bounds.

    `net_yield` charges a fee for every building with on-site staff (有無管理員),
    whether or not the tenant's rent already includes it. The registry has a
    second field that speaks to exactly that: the free-text 備註, where ~40% of
    lets in staffed buildings say 租金總額含管理費 and ~8% say the tenant pays
    separately. The other half say nothing -- and nothing is not evidence of
    either, so this block publishes two bounds rather than a corrected number:

        all_charged   the fee charged to every staffed building (the headline)
        flag_only     the fee charged only where a lease says the rent includes it

    The truth is between them. The headline stays on the first, unchanged --
    corrections accrete. Building rule = ANY flagged let (see to_buildings);
    the majority-rule count is published beside it. CIs reuse two_stage_ci on
    pair-level nets with the building's charge decision applied to every pair
    of that building, the ladder's pattern; the point estimate is the building
    median of net_yield() on the same inputs as add_net_yield, so all_charged
    reproduces the headline exactly. Own rng seed so no existing interval moves.
    """
    if rents is None or rents.empty or b is None or b.empty:
        return {}
    R = rents
    hm = R[R.has_mgr == 1]
    nm = R[R.has_mgr == 0]
    n_hm = int(len(hm))
    incl, excl = int(hm.rent_incl_mgmt.sum()), int(hm.rent_excl_mgmt.sum())
    pct = lambda x, n: round(x / n * 100, 1) if n else None
    note = R["備註"].fillna("").astype(str) if "備註" in R.columns else pd.Series("", index=R.index)
    lets = {
        "has_mgr": n_hm, "incl": incl, "excl": excl, "unstated": n_hm - incl - excl,
        "incl_pct": pct(incl, n_hm), "excl_pct": pct(excl, n_hm),
        "unstated_pct": pct(n_hm - incl - excl, n_hm),
        "no_mgr": int(len(nm)),
        "no_mgr_incl_pct": pct(int(nm.rent_incl_mgmt.sum()), len(nm)),
        "no_mgr_excl_pct": pct(int(nm.rent_excl_mgmt.sum()), len(nm)),
        "strict_incl_all": int(note.str.contains("租金總額含管理費", regex=False).sum()),
        "loose_incl_all": int(R.rent_incl_mgmt.sum()),
    }

    # by LEASE quarter -- 'Q' labels, the same clock the volume section teaches.
    # Rows before the window's first season are late-filed; the last is still
    # filling.
    by_q = []
    if len(hm):
        win0 = season_index(WINDOW_FIRST) if WINDOW_FIRST else None
        last_q = int(hm.q.max())
        for q, g in hm.groupby("q"):
            if len(g) < 500:
                continue
            i, e = int(g.rent_incl_mgmt.sum()), int(g.rent_excl_mgmt.sum())
            by_q.append({"q": L.quarter_label(int(q)), "lets": int(len(g)),
                         "incl": i, "incl_pct": pct(i, len(g)),
                         "excl": e, "excl_pct": pct(e, len(g)),
                         "partial": bool(win0 is not None and q < win0),
                         "censored": bool(q == last_q)})

    # by county: lets (筆) and buildings (棟) in separate columns, never divided
    hb = b[b.has_mgr == 1]
    rows = []
    for c, g in hm.groupby("county"):
        bb = hb[hb.county == c]
        rows.append({"county": c, "lets": int(len(g)),
                     "incl": int(g.rent_incl_mgmt.sum()),
                     "incl_pct": pct(int(g.rent_incl_mgmt.sum()), len(g)),
                     "excl": int(g.rent_excl_mgmt.sum()),
                     "excl_pct": pct(int(g.rent_excl_mgmt.sum()), len(g)),
                     "bldgs": int(len(bb)), "bldgs_flag_any": int(bb.mgmt_incl_any.sum()),
                     "bldgs_flag_any_pct": pct(int(bb.mgmt_incl_any.sum()), len(bb))})
    rows.sort(key=lambda r: -r["lets"])
    top, rest = rows[:6], rows[6:]
    other = {k: int(sum(r[k] for r in rest)) for k in ("lets", "incl", "excl", "bldgs", "bldgs_flag_any")}

    # within building: flagged vs unflagged rent per 坪, building-level median of
    # per-building ratios; and the same in NT$/坪/月 beside the assumed rate
    def _within(frame, a_mask, b_mask):
        f = frame.assign(rpp=frame.rent / frame.area_ping)
        ga = f[a_mask(f)].groupby(["county", "k"]).rpp.median()
        gb = f[b_mask(f)].groupby(["county", "k"]).rpp.median()
        both = ga.index.intersection(gb.index)
        if not len(both):
            return {"n": 0}
        ratio = (ga[both] / gb[both] - 1) * 100
        gap = ga[both] - gb[both]
        return {"n": int(len(both)), "median_pct": round(float(ratio.median()), 2),
                "q1_pct": round(float(ratio.quantile(.25)), 2),
                "q3_pct": round(float(ratio.quantile(.75)), 2),
                "share_pos_pct": round(float((ratio > 0).mean() * 100), 1),
                "gap_ntd_ping_mo": int(round(float(gap.median()))),
                "rent_ping_mo": int(round(float(gb[both].median())))}
    within = _within(hm, lambda f: f.rent_incl_mgmt == 1, lambda f: f.rent_incl_mgmt == 0)
    within["vs_excl"] = _within(hm, lambda f: f.rent_incl_mgmt == 1, lambda f: f.rent_excl_mgmt == 1)
    within["vs_unstated"] = _within(hm, lambda f: f.rent_incl_mgmt == 1,
                                    lambda f: (f.rent_incl_mgmt == 0) & (f.rent_excl_mgmt == 0))
    within["assumed_ntd_ping_mo"] = {"a": DEFAULT_MGMT_A, "f": DEFAULT_MGMT_F}

    buildings = {
        "has_mgr": int(len(hb)), "has_mgr_pct": pct(len(hb), len(b)),
        "flag_any": int(hb.mgmt_incl_any.sum()),
        "flag_any_pct": pct(int(hb.mgmt_incl_any.sum()), len(hb)),
        "flag_majority": int((hb.mgmt_incl_share >= 0.5).sum()),
        "mixed": int(((hb.mgmt_incl_share > 0) & (hb.mgmt_incl_share < 1)).sum()),
        "excl_any": int(hb.mgmt_excl_any.sum()),
    }

    # the two bounds
    rng = np.random.default_rng(seed)
    charge_flag = ((b.has_mgr == 1) & (b.mgmt_incl_any == 1)).astype(int)
    flag_of = dict(zip(zip(b.county, b.k), charge_flag))
    pp = pairs.assign(age=115.0 - pairs.built_roc_y)
    bounds = []
    for case, charged in (("all_charged", b.has_mgr), ("flag_only", charge_flag)):
        nets = [net_yield(p_, ar, ap, hm_, ag, c)
                for p_, ar, ap, hm_, ag, c in zip(b.price_abs, b.annual_rent, b.area,
                                                  charged, b.age, b.county)]
        if case == "all_charged":
            pair_hm = pp.has_mgr
        else:
            pair_hm = pd.Series([flag_of.get(k, 0) for k in zip(pp.county, pp.k)], index=pp.index)
        pn = pp.assign(hm=pair_hm)
        pn["net"] = [net_yield(p_, r * 12.0, ap, hm_, ag, c)
                     for p_, r, ap, hm_, ag, c in zip(pn.price_adj, pn.rent, pn.area_ping_s,
                                                      pn.hm, pn.age, pn.county)]
        gp = {kk: g.net.dropna().values for kk, g in pn.groupby(["county", "k"])}
        lo, hi = two_stage_ci(gp, list(gp.keys()), n_boot, rng)
        bounds.append({"case": case, "charged": int(charged.sum()),
                       "net": median(pd.Series(nets)), "lo": lo, "hi": hi})
    for r_ in bounds:
        r_["delta_pp"] = round((r_["net"] or 0) - (bounds[0]["net"] or 0), 4)
    # The rule's sensitivity, as a point: what the flag-only bound would be
    # under a majority-of-leases rule instead of any-lease. No CI; it is a
    # disclosure of the choice, not a third bound.
    charge_maj = ((b.has_mgr == 1) & (b.mgmt_incl_share >= 0.5)).astype(int)
    maj_net = median(pd.Series([net_yield(p_, ar, ap, hm_, ag, c)
                                for p_, ar, ap, hm_, ag, c in zip(b.price_abs, b.annual_rent, b.area,
                                                                  charge_maj, b.age, b.county)]))
    buildings["flag_majority_net"] = maj_net
    buildings["flag_majority_delta_pp"] = round((maj_net or 0) - (bounds[1]["net"] or 0), 4)

    return {
        "predicate": {"field": "備註", "side": "rent", "incl": L.MGMT_INCL,
                      "not_incl": L.MGMT_NOT_INCL, "excl_regex": L.MGMT_EXCL.pattern,
                      "rule": "any"},
        "lets": lets,
        "by_quarter": by_q,
        "by_county": top,
        "by_county_other": other,
        "within_building": within,
        "buildings": buildings,
        "bounds": bounds,
    }


# ── a parking space as its own asset ─────────────────────────────────────────

PARK_MIN_TYPE_N = 10        # buildings before a 車位類別 cell is reported
PARK_WIDE_TOL = 0.10        # |within-building social/market rent ratio - 1| that licenses the wide rung
PARK_WIDE_MIN_N = 100       # ...on at least this many buildings


def _park_key(d):
    """The building key, as key_frames applies it, without key_frames: that
    function writes bldg_type from 建物型態 and a standalone space is '其他'."""
    d = d.copy()
    d["k"] = d["土地位置建物門牌"].map(addr_key)
    d["district"] = _tw(d["鄉鎮市區"])
    return d[d.k != ""], int((d.k == "").sum())


def _park_pairs(sd, ld, window=MATCH_WINDOW_Q):
    """Space sale x space lease in the same building, within `window` quarters.
    Not match_pairs: that one restates price over an area and a space has none."""
    if sd.empty or ld.empty:
        return pd.DataFrame(), 0
    s = sd[["county", "k", "q", "price", "cls", "sp_type", "season", "編號"]].rename(
        columns={"q": "q_s", "cls": "cls_s", "sp_type": "type_s", "season": "season_s", "編號": "id_s"})
    r = ld[["county", "k", "q", "rent", "cls", "sp_type", "social", "season", "編號"]].rename(
        columns={"q": "q_r", "cls": "cls_r", "sp_type": "type_r", "season": "season_r", "編號": "id_r"})
    m = s.merge(r, on=["county", "k"])
    m = m[(m.q_s - m.q_r).abs() <= window].copy()
    if m.empty:
        return m, 0
    m["gap"] = (m.q_s - m.q_r).abs()
    m["gross"] = m.rent * 12.0 / m.price * 100.0
    lo, hi = YIELD_BAND
    keep = (m.gross > lo) & (m.gross < hi)
    return m[keep], int((~keep).sum())


def _park_buildings(pairs):
    g = pairs.groupby(["county", "k"], as_index=False).agg(
        gross=("gross", "median"), price=("price", "median"), rent=("rent", "median"),
        pairs=("gross", "size"),
        n_sales=("id_s", lambda x: pd.Series(list(zip(pairs.loc[x.index, "season_s"], x))).nunique()),
        n_leases=("id_r", lambda x: pd.Series(list(zip(pairs.loc[x.index, "season_r"], x))).nunique()),
        district=("k", "size"))
    return g


def _park_rung(key, zh, en, sd, ld, rng, n_boot):
    pairs, band_dropped = _park_pairs(sd, ld)
    if pairs.empty:
        return None, pairs, pd.DataFrame()
    b = _park_buildings(pairs)
    gp = {kk: g.gross.values for kk, g in pairs.groupby(["county", "k"])}
    lo, hi = two_stage_ci(gp, list(gp.keys()), n_boot, rng)
    same = pairs[pairs.type_s == pairs.type_r]
    row = {
        "key": key, "zh": zh, "en": en,
        "buildings": int(len(b)), "pairs": int(len(pairs)),
        "yield": median(b.gross), "lo": lo, "hi": hi,
        "q1": round(float(b.gross.quantile(.25)), 4), "q3": round(float(b.gross.quantile(.75)), 4),
        "yield_pair": median(pairs.gross),
        "price": int(b.price.median()), "rent": int(b.rent.median()),
        "band_dropped": band_dropped,
        "social_pairs_pct": round(float(pairs.social.mean() * 100), 1),
        "same_type_pairs_pct": round(float(len(same) / len(pairs) * 100), 1),
        "same_type_buildings": int(same.groupby(["county", "k"]).ngroups),
        "bldg_ge2_ge2": int(((b.n_sales >= 2) & (b.n_leases >= 2)).sum()),
        "classes": {"sale": {k: int(v) for k, v in pairs.cls_s.value_counts().items()},
                    "lease": {k: int(v) for k, v in pairs.cls_r.value_counts().items()}},
    }
    return row, pairs, b


def _park_within(frame, col, a_mask, b_mask):
    """Ratio of two record kinds' per-building medians, on buildings carrying both."""
    ga = frame[a_mask].groupby(["county", "k"])[col].median()
    gb = frame[b_mask].groupby(["county", "k"])[col].median()
    both = ga.index.intersection(gb.index)
    if not len(both):
        return {"n": 0, "median": None, "q1": None, "q3": None, "share_within_10pct": None, "thin": True}
    ratio = ga[both] / gb[both]
    return {"n": int(len(both)), "median": round(float(ratio.median()), 3),
            "q1": round(float(ratio.quantile(.25)), 3), "q3": round(float(ratio.quantile(.75)), 3),
            "share_within_10pct": round(float(((ratio - 1).abs() <= 0.10).mean() * 100), 1),
            "thin": bool(len(both) < MIN_DISTRICT_N)}


def parking_block(raw_sales, raw_rents, headline, n_boot=200, seed=31):
    """A parking space as its own asset: same-building space sale x space lease.

    The unit is a SPACE -- price per space, rent per space per month, yield
    per space. Never NT$/坪: the registry's space area is an allocated share of
    the basement. Three rungs in the ladder's grammar, each with a two-stage
    CI on its own seed so no existing interval moves:

        strict   spaces sold alone x spaces let alone
        market   + the itemised space in a flat+space sale / lease; social-
                 housing space rents and related-party sales out   (headline)
        wide     + social-housing space rents

    Two record kinds are pooled on each side, and the wide rung admits a
    third population, so the block carries the within-building checks that
    license each pooling (n, median ratio, IQR) and a `wide_licensed` flag
    decided by a stated rule -- the rung is shown on that flag, not on taste.
    The 機械 > 平面 type gap has a stated mechanism (the owner bears
    maintenance and replacement on a mechanical space and it is harder to
    resell, so the price discount exceeds the rent discount); it is labelled
    the hypothesis it is and the numbers are published whichever way they
    point. The dwelling headline is copied in for the side-by-side and is
    never differenced against a space -- two assets.
    """
    if raw_sales is None or raw_rents is None or raw_sales.empty or raw_rents.empty:
        return {}
    sale_all = L.clean_parking_sales(raw_sales, exclude_related=False)
    rent_all = L.clean_parking_rents(raw_rents, exclude_social=False)
    if sale_all.empty or rent_all.empty:
        return {}
    sale_all, s_nokey = _park_key(sale_all)
    rent_all, r_nokey = _park_key(rent_all)
    sale_m = sale_all[~sale_all.related]
    rent_m = rent_all[~rent_all.social]

    # the records waterfall, so the reader sees what a single-space rule costs
    rs = raw_sales[raw_sales["交易標的"].isin(L.PARK_SALE_TARGETS)]
    rr = raw_rents[raw_rents["交易標的"].isin(L.PARK_LEASE_TARGETS)]
    rs_single = rs[rs.park_n == 1]; rr_single = rr[rr.park_n == 1]
    records = {
        "sale": {
            "rows_with_parking": int(len(rs)),
            "standalone": int(rs["交易標的"].eq("車位").sum()),
            "bundled": int((~rs["交易標的"].eq("車位")).sum()),
            "no_park_row": int((rs.park_n == 0).sum()),
            "multi_space": int((rs.park_n >= 2).sum()),
            "single_standalone": int(rs_single["交易標的"].eq("車位").sum()),
            "single_bundled": int((~rs_single["交易標的"].eq("車位")).sum()),
            "single_bundled_itemised": int(((~rs_single["交易標的"].eq("車位")) & (rs_single.park_price > 0)).sum()),
            "related": int(sale_all.related.sum()),
            "no_key": s_nokey,
            "usable": int(len(sale_all)), "usable_market": int(len(sale_m)),
        },
        "lease": {
            "rows_with_parking": int(len(rr)),
            "standalone": int(rr["交易標的"].eq("車位").sum()),
            "bundled": int((~rr["交易標的"].eq("車位")).sum()),
            "no_park_row": int((rr.park_n == 0).sum()),
            "multi_space": int((rr.park_n >= 2).sum()),
            "single_standalone": int(rr_single["交易標的"].eq("車位").sum()),
            "single_bundled": int((~rr_single["交易標的"].eq("車位")).sum()),
            "single_bundled_priced": int(((~rr_single["交易標的"].eq("車位")) & (rr_single["車位總額元"].map(L.num) > 0)).sum()),
            "social": int(rent_all.social.sum()),
            "token_rent_lt_500": int((rent_all.rent < 500).sum()),
            "no_key": r_nokey,
            "usable": int(len(rent_all)), "usable_market": int(len(rent_m)),
        },
    }

    rng = np.random.default_rng(seed)
    rungs, frames = [], {}
    for key, zh, en, sd, ld in (
        ("strict", "只用單獨賣、單獨租的車位", "Spaces sold alone and let alone only",
         sale_m[sale_m.cls == "standalone"], rent_m[rent_m.cls == "standalone"]),
        ("market", "市價紀錄（排除社宅車位租金、排除親友間交易）",
         "Market records only (social-housing space rents and related-party sales out)",
         sale_m, rent_m),
        ("wide", "加入社宅代管的車位租金", "Social-housing space rents admitted", sale_m, rent_all),
    ):
        row, pairs, b = _park_rung(key, zh, en, sd, ld, rng, n_boot)
        if row is None:
            continue
        rungs.append(row)
        frames[key] = (pairs, b)
    if "market" not in frames:
        return {}

    # the checks that license pooling
    validations = [
        {"key": "bundled_sale_vs_standalone", "side": "sale",
         **_park_within(sale_m, "price", sale_m.cls == "bundled_itemised", sale_m.cls == "standalone")},
        {"key": "social_vs_market_rent", "side": "lease",
         **_park_within(rent_all, "rent", rent_all.social, ~rent_all.social),
         "cross_sample": {"social": int(rent_all[rent_all.social].rent.median()) if rent_all.social.any() else None,
                          "market": int(rent_m.rent.median())}},
        {"key": "bundled_lease_vs_standalone", "side": "lease",
         **_park_within(rent_m, "rent", rent_m.cls == "bundled_priced", rent_m.cls == "standalone")},
    ]
    v2 = validations[1]
    wide_licensed = bool(v2["n"] >= PARK_WIDE_MIN_N and v2["median"] is not None
                         and abs(v2["median"] - 1.0) <= PARK_WIDE_TOL)

    # sensitivity: the market rung with one record kind removed
    sensitivity = []
    for key, sd, ld in (
        ("market_lease_standalone_only", sale_m, rent_m[rent_m.cls == "standalone"]),
        ("market_sale_standalone_only", sale_m[sale_m.cls == "standalone"], rent_m),
        ("market_sale_bundled_only", sale_m[sale_m.cls == "bundled_itemised"], rent_m),
    ):
        row, _, _ = _park_rung(key, "", "", sd, ld, rng, n_boot)
        if row:
            sensitivity.append({k: row[k] for k in ("key", "buildings", "pairs", "yield", "lo", "hi", "price", "rent")})

    # by 車位類別, same type on both sides
    by_type, type_gap = {}, {"a": "坡道平面", "b": "坡道機械", "hypothesis": True, "mechanism_measured": False}
    for key in ("market", "wide"):
        pairs, _ = frames[key]
        same = pairs[(pairs.type_s == pairs.type_r) & (pairs.type_s != "")]
        cells = same.groupby(["county", "k", "type_s"], as_index=False).agg(
            gross=("gross", "median"), price=("price", "median"), rent=("rent", "median"))
        rows = []
        for t, g in cells.groupby("type_s"):
            if len(g) >= PARK_MIN_TYPE_N:
                rows.append({"type": t, "buildings": int(len(g)), "yield": median(g.gross),
                             "q1": round(float(g.gross.quantile(.25)), 4),
                             "q3": round(float(g.gross.quantile(.75)), 4),
                             "price": int(g.price.median()), "rent": int(g.rent.median())})
        rows.sort(key=lambda r: -r["buildings"])
        by_type[key] = rows
        cells_named = cells.rename(columns={"type_s": "bldg_type"})
        ga = cells[cells.type_s == "坡道平面"]; gb = cells[cells.type_s == "坡道機械"]
        lo, hi = gap_ci(cells_named, "坡道機械", "坡道平面", "gross")
        type_gap[key] = {
            "gap_pp": (round(float(gb.gross.median() - ga.gross.median()), 3) if len(ga) and len(gb) else None),
            "lo": lo, "hi": hi, "n_a": int(len(ga)), "n_b": int(len(gb)),
            "price_ratio": (round(float(gb.price.median() / ga.price.median()), 3) if len(ga) and len(gb) else None),
            "rent_ratio": (round(float(gb.rent.median() / ga.rent.median()), 3) if len(ga) and len(gb) else None),
        }
        # buildings that carry same-type pairs of two different types (a within-building version would need these)
        type_gap[key + "_within_building_n"] = int((same.groupby(["county", "k"]).type_s.nunique() >= 2).sum())

    # by county, each rung
    by_county = {}
    for key in ("market", "wide"):
        pairs, b = frames[key]
        rows = []
        for c, g in b.groupby("county"):
            gp = {kk: gg.gross.values for kk, gg in pairs[pairs.county == c].groupby(["county", "k"])}
            lo, hi = two_stage_ci(gp, list(gp.keys()), n_boot, rng) if len(g) >= MIN_DISTRICT_N else (None, None)
            rows.append({"county": c, "buildings": int(len(g)), "yield": median(g.gross), "lo": lo, "hi": hi,
                         "price": int(g.price.median()), "rent": int(g.rent.median())})
        rows.sort(key=lambda r: -r["buildings"])
        by_county[key] = rows[:6]
        by_county[key + "_other"] = {"buildings": int(sum(r["buildings"] for r in rows[6:]))}

    # window sensitivity, no CI
    window_test = []
    for w in (2, 4, 8, None):
        entry = {"window": w}
        for key, sd, ld in (("market", sale_m, rent_m), ("wide", sale_m, rent_all)):
            pairs, _ = _park_pairs(sd, ld, window=10**6 if w is None else w)
            if pairs.empty:
                entry[key] = {"buildings": 0, "yield": None}
                continue
            b = pairs.groupby(["county", "k"]).gross.median()
            entry[key] = {"buildings": int(len(b)), "yield": median(b)}
        window_test.append(entry)
    mp, _ = frames["market"]
    gap_buckets = [{"gap": int(g), "pairs": int(len(x)), "yield": median(x.gross)} for g, x in mp.groupby("gap")]

    print(f"[uw] parking: " + " / ".join(f"{r['key']} {r['buildings']:,}" for r in rungs) +
          f" buildings; market {rungs[[r['key'] for r in rungs].index('market')]['yield']:.2f}%"
          f"; wide_licensed={wide_licensed}")
    return {
        "unit": "space",
        "predicate": {
            "sale_targets": list(L.PARK_SALE_TARGETS), "lease_targets": list(L.PARK_LEASE_TARGETS),
            "n_spaces": 1, "related_party": L.RELATED_PARTY, "social_housing": sorted(L.SOCIAL_HOUSING),
            "match_window_q": MATCH_WINDOW_Q, "yield_band": list(YIELD_BAND),
            "min_type_buildings": PARK_MIN_TYPE_N, "min_county_buildings": MIN_DISTRICT_N,
            "price_field": {"standalone": "總價元", "bundled": "車位價格 (park.csv)"},
            "rent_field": {"standalone": "總額元", "bundled": "車位總額元"},
            "priced_means": "park.csv 車位價格 > 0 on the sale side; 車位總額元 > 0 on the lease side "
                            "(the audit block's 'priced' is park.csv price > 0 on all space counts)",
            "wide_rule": {"validation": "social_vs_market_rent", "min_n": PARK_WIDE_MIN_N,
                          "max_abs_dev": PARK_WIDE_TOL,
                          "mechanism_zh": "假說：包租代管的租金補貼落在住宅租金，不落在車位租金，所以社宅車位租金貼近市價",
                          "mechanism_en": "Hypothesis: the 包租代管 subsidy applies to the dwelling rent, not the space, so social-housing space rents track the market"},
        },
        "records": records,
        "headline_rung": "market",
        "rungs": rungs,
        "wide_licensed": wide_licensed,
        "dwelling": {"yield": headline["yield"], "buildings": headline["buildings"]},
        "validations": validations,
        "sensitivity": sensitivity,
        "by_type": by_type,
        "type_gap": type_gap,
        "by_county": by_county,
        "window_test": window_test,
        "gap_buckets_market": gap_buckets,
    }


# ── un-itemised parking rent: a stated assumption, tested ────────────────────

AUDIT_MIN_N = 100           # buildings the primary within-building test needs
AUDIT_EQUAL_MARGIN = 0.02   # half-width of the "holds" band, and the gap below 1.0 it must keep
AUDIT_MIN_COUNTY_N = 30     # priced rows a county needs to donate an imputed space rent


def _ratio_ci(ratio, n=400, seed=41):
    """95% CI on the median of per-building ratios: a building bootstrap, run
    through two_stage_ci with singleton vectors so it is the one CI routine."""
    gp = {i: np.array([v]) for i, v in enumerate(ratio.values)}
    return two_stage_ci(gp, list(gp.keys()), n, np.random.default_rng(seed))


def _audit_within(frame, col, a_mask, b_mask, seed):
    ga = frame[a_mask].groupby(["county", "k"])[col].median()
    gb = frame[b_mask].groupby(["county", "k"])[col].median()
    both = ga.index.intersection(gb.index)
    if not len(both):
        return {"n": 0}
    ratio = (ga[both] / gb[both]).dropna()
    lo, hi = _ratio_ci(ratio, seed=seed)
    by_county = {}
    for c, g in ratio.groupby(level="county"):
        if len(g) >= 20:
            by_county[c] = {"n": int(len(g)), "median": round(float(g.median()), 4)}
    return {"n": int(len(ratio)), "median": round(float(ratio.median()), 4),
            "q1": round(float(ratio.quantile(.25)), 4), "q3": round(float(ratio.quantile(.75)), 4),
            "share_gt1_pct": round(float((ratio > 1).mean() * 100), 1),
            "lo": lo, "hi": hi,
            "a_median": round(float(ga[both].median()), 2), "b_median": round(float(gb[both].median()), 2),
            "by_county": by_county}


def _pair_nets(pp, charged):
    """Pair-level net yields with the building's charge decision, as mgmt_flag does."""
    return [net_yield(p_, r * 12.0, ap, hm_, ag, c)
            for p_, r, ap, hm_, ag, c in zip(pp.price_adj, pp.rent, pp.area_ping_s, charged,
                                             115.0 - pp.built_roc_y, pp.county)]


def _treatment(case, pairs, b, rng, n_boot):
    gp_g = {kk: g.gross.values for kk, g in pairs.groupby(["county", "k"])}
    glo, ghi = two_stage_ci(gp_g, list(gp_g.keys()), n_boot, rng)
    pn = pairs.assign(net=_pair_nets(pairs, pairs.has_mgr))
    gp_n = {kk: g.net.dropna().values for kk, g in pn.groupby(["county", "k"])}
    nlo, nhi = two_stage_ci(gp_n, list(gp_n.keys()), n_boot, rng)
    return {"case": case, "buildings": int(len(b)), "pairs": int(len(pairs)),
            "gross": median(b.gross), "gross_lo": glo, "gross_hi": ghi,
            "net": median(b.net), "net_lo": nlo, "net_hi": nhi}


def impute_parking_rent(rents, min_county_n=AUDIT_MIN_COUNTY_N):
    """Subtract an imputed per-space rent from every un-itemised bundled lease.

    The headline's treatment since v2.1. The within-building test in
    parking_audit_block showed the parking rent sits inside the dwelling rent
    on these rows, so leaving it in overstated the yield. Donor, per space:
    the same building's itemised leases (median), else the county's where it
    has at least `min_county_n` itemised rows, else the country's; times the
    row's space count. Rows left at or under the NT$3,000 floor are dropped.
    Deterministic from the frame alone, so the rebuild stays reproducible.
    Returns (frame, stats); stats is published inside `parking_audit`.
    """
    if rents is None or rents.empty or "park_unpriced" not in rents.columns:
        return rents, {}
    priced = rents["交易標的"].astype(str).eq("租賃房屋+車位") & (rents.park_price > 0)
    per_space = rents.loc[priced, "park_price"] / rents.loc[priced, "park_n"].clip(lower=1)
    donors = rents[priced].assign(ps=per_space)
    bld_med = donors.groupby(["county", "k"]).ps.median()
    cty_n = donors.groupby("county").ps.size()
    cty_med = donors.groupby("county").ps.median()
    nat_med = float(per_space.median()) if len(per_space) else 0.0
    out = rents.copy()
    src = {"building": 0, "county": 0, "national": 0}
    imputed = {}
    for idx, row in out[out.park_unpriced == 1].iterrows():
        key = (row.county, row.k)
        if key in bld_med.index:
            v, s_ = float(bld_med[key]), "building"
        elif row.county in cty_n.index and cty_n[row.county] >= min_county_n:
            v, s_ = float(cty_med[row.county]), "county"
        else:
            v, s_ = nat_med, "national"
        src[s_] += 1
        imputed[idx] = v * max(1, int(row.park_n))
    imp = pd.Series(imputed)
    out.loc[imp.index, "rent"] = out.loc[imp.index, "rent"] - imp
    under = int((out.loc[imp.index, "rent"] <= 3000).sum())
    out = out[out.rent > 3000]
    stats = {
        "imputed_rows": int(len(imp)), "dropped_under_floor": under, "source_split": src,
        "min_county_n": min_county_n,
        "imputed_median_ntd": int(imp.median()) if len(imp) else None,
        "national_median_ntd": int(nat_med),
        "county_medians": [{"county": c, "ntd": int(cty_med[c]), "n": int(cty_n[c])}
                           for c in cty_n.index if cty_n[c] >= min_county_n],
    }
    return out, stats


def parking_audit_block(rents_old, rents, sales, pairs, b, raw_rents, ladder, imp_stats,
                        index=None, n_boot=120, seed=41):
    """Was a zero 車位總額元 really 'no extra rent'? Tested within building.

    fetch_lvr._subtract_parking keeps a bundled lease whose space was never
    itemised and takes out only the AREA, on the assumption that the space came
    free. This block tests that on the page's own clean frame: buildings that
    carry both an itemised and an un-itemised bundled lease, comparing TOTAL
    rent per m2 of total area (dwelling plus space, before any subtraction).
    If the space were free the un-itemised lease should sit lower by about the
    itemised parking share s; if the parking rent is inside the dwelling rent,
    the two should be equal. The verdict is one predicate over fields the
    block publishes (n, lo, hi, hold_band, equal_margin), and a test re-derives
    it; it is NOT called pre-registered, because the rule was settled while
    the scout's n=192 result was already known.

    Three treatments of the un-itemised leases (the ladder's grammar, own
    seed): area_only -- keep them and take out only the area, the headline
    from v1.0 to v2.0; drop them; impute a per-space rent and subtract it --
    the headline from v2.1 (impute_parking_rent, applied in build() and as
    the ladder's last rung). Corrections accrete: the old treatment stays a
    published bound. `rents_old` is the pre-imputation frame the tests run on;
    `rents`/`pairs`/`b` are the headline's. Returns (block, ro_map) where
    ro_map carries each building's median rent under the OLD treatment, for
    the page's live waterfall row.
    """
    if rents_old is None or rents_old.empty or pairs is None or pairs.empty:
        return {}, {}
    R = rents_old.copy()
    bund = R["交易標的"].astype(str).eq("租賃房屋+車位")
    priced = bund & (R.park_price > 0)
    unpriced = R.park_unpriced == 1
    nopark = R["交易標的"].astype(str).eq("租賃房屋")
    R["tot_rent"] = R["總額元"].map(L.num)
    R["tot_area_m2"] = R["建物總面積平方公尺"].map(L.num)
    R["tot_rpm2"] = R.tot_rent / R.tot_area_m2
    R["dw_rpp"] = R.rent / R.area_ping
    has_area = R.park_area_m2 > 0

    share = R[priced].park_price / R[priced].tot_rent
    s_med = round(float(share.median()), 4)
    per_space = (R[priced].park_price / R[priced].park_n.clip(lower=1))
    lets = {
        "clean": int(len(R)), "bundled": int(bund.sum()), "priced": int(priced.sum()),
        "unpriced": int(unpriced.sum()), "unpriced_pct": round(float(unpriced.mean() * 100), 1),
        "unpriced_of_bundled_pct": round(float(unpriced.sum() / max(1, bund.sum()) * 100), 1),
        "nopark": int(nopark.sum()),
        "unpriced_area_itemised": int((unpriced & has_area).sum()),
        "unpriced_nothing_itemised": int((unpriced & ~has_area).sum()),
        "priced_by_service": {str(k): int(v) for k, v in
                              R[priced]["租賃住宅服務"].fillna("").replace("", "（未填）").value_counts().items()},
    }
    share_blk = {
        "n_priced": int(priced.sum()), "park_rent_share_median": s_med,
        "q1": round(float(share.quantile(.25)), 4), "q3": round(float(share.quantile(.75)), 4),
        "park_rent_per_space_median_ntd": int(per_space.median()),
        "park_rent_per_space_q1_ntd": int(per_space.quantile(.25)),
        "park_rent_per_space_q3_ntd": int(per_space.quantile(.75)),
    }

    W = {
        "total_unpriced_vs_priced": {**_audit_within(R, "tot_rpm2", unpriced, priced, seed),
                                     "unit": "NT$/m2/month of total area, dwelling+space, before subtraction",
                                     "role": "primary"},
        "dwell_unpriced_vs_priced": {**_audit_within(R, "dw_rpp", unpriced, priced, seed + 1),
                                     "unit": "NT$/坪/month of dwelling after the current subtraction",
                                     "predicted_if_fails": round(1.0 / (1.0 - s_med), 4)},
        "dwell_unpriced_vs_nopark": {**_audit_within(R, "dw_rpp", unpriced, nopark, seed + 2),
                                     "unit": "NT$/坪/month of dwelling after the current subtraction"},
        "dwell_priced_vs_nopark": {**_audit_within(R, "dw_rpp", priced, nopark, seed + 3),
                                   "unit": "NT$/坪/month of dwelling after the current subtraction",
                                   "role": "control"},
        # robustness: the primary test on the two halves of the un-itemised rows
        "total_unpriced_area_itemised_vs_priced": {**_audit_within(R, "tot_rpm2", unpriced & has_area, priced, seed + 4),
                                                   "role": "robustness"},
        "total_unpriced_nothing_itemised_vs_priced": {**_audit_within(R, "tot_rpm2", unpriced & ~has_area, priced, seed + 5),
                                                      "role": "robustness"},
    }

    # social-housing leases, excluded from the page: corroboration only
    social_only = None
    if raw_rents is not None and not raw_rents.empty:
        S_ = L.clean_rents(raw_rents, exclude_social=False, subtract_parking=True)
        S_ = S_[S_["租賃住宅服務"].fillna("").isin(L.SOCIAL_HOUSING)].copy()
        if not S_.empty:
            S_["k"] = S_["土地位置建物門牌"].map(addr_key)
            S_ = S_[S_.k != ""]
            sb = S_["交易標的"].astype(str).eq("租賃房屋+車位")
            sp = sb & (S_.park_price > 0)
            su = S_.park_unpriced == 1
            S_["tot_rpm2"] = S_["總額元"].map(L.num) / S_["建物總面積平方公尺"].map(L.num)
            social_only = {"rows": int(len(S_)), "priced": int(sp.sum()), "unpriced": int(su.sum()),
                           "total_unpriced_vs_priced": _audit_within(S_, "tot_rpm2", su, sp, seed + 6),
                           "note": "excluded from the page; corroboration only, never in the verdict"}

    # the verdict: one predicate over published fields
    P = W["total_unpriced_vs_priced"]
    m = AUDIT_EQUAL_MARGIN
    hold_band = [round(1.0 - s_med - m, 4), round(1.0 - s_med + m, 4)]
    n, lo, hi = P.get("n", 0), P.get("lo"), P.get("hi")
    if n < AUDIT_MIN_N or lo is None:
        verdict = "inconclusive"
    elif lo > hold_band[1]:
        verdict = "assumption_fails"
    elif lo <= hold_band[1] and hi >= hold_band[0] and hi < 1.0 - m:
        verdict = "assumption_holds"
    else:
        verdict = "inconclusive"
    verdict_blk = {
        "verdict": verdict, "test": "within_building.total_unpriced_vs_priced",
        "min_n": AUDIT_MIN_N, "n": n, "ratio": P.get("median"), "lo": lo, "hi": hi,
        "share_s": s_med, "equal_margin": m,
        "predicted_if_holds": round(1.0 - s_med, 4), "predicted_if_fails": 1.0,
        "hold_band": hold_band,
        "rule": "inconclusive if n < min_n; fails iff lo > hold_band[1]; holds iff the CI overlaps "
                "hold_band and hi < 1 - equal_margin; else inconclusive",
        "pre_registered": False,
    }

    # exposure
    pu = pairs.park_unpriced == 1
    only = b.park_unp_share == 1
    by_c = []
    for c, g in pairs.groupby("county"):
        if len(g) >= 1000:
            by_c.append({"county": c, "pairs": int(len(g)), "unpriced": int(g.park_unpriced.sum()),
                         "pct": round(float(g.park_unpriced.mean() * 100), 1)})
    by_c.sort(key=lambda r: -r["pairs"])
    exposure = {
        "pairs_total": int(len(pairs)), "pairs_on_unpriced": int(pu.sum()),
        "pairs_on_unpriced_pct": round(float(pu.mean() * 100), 2),
        "buildings_total": int(len(b)),
        "buildings_any_unpriced": int((b.park_unp_share > 0).sum()),
        "buildings_any_unpriced_pct": round(float((b.park_unp_share > 0).mean() * 100), 1),
        "buildings_only_unpriced": int(only.sum()),
        "buildings_only_unpriced_pct": round(float(only.mean() * 100), 1),
        "only_unpriced_gross_as_now": median(b[only].gross),
        "rest_gross_as_now": median(b[~only].gross),
        # who those buildings are, measured rather than asserted
        "only_unpriced_built_median": (None if not only.any() else round(float(b[only].built.median()), 1)),
        "rest_built_median": round(float(b[~only].built.median()), 1),
        "only_unpriced_tower_pct": round(float((b[only].bldg_type == "住宅大樓").mean() * 100), 1) if only.any() else None,
        "rest_tower_pct": round(float((b[~only].bldg_type == "住宅大樓").mean() * 100), 1),
        "by_county": by_c,
    }

    # the three treatments; the headline is `impute` (pairs/b as given)
    rng = np.random.default_rng(seed)
    p_old = match_pairs(sales, rents_old, index=index)
    b_old = add_net_yield(to_buildings(p_old))
    t_old = _treatment("area_only", p_old, b_old, rng, n_boot)

    r_drop = rents_old[rents_old.park_unpriced == 0]
    p_drop = match_pairs(sales, r_drop, index=index)
    b_drop = add_net_yield(to_buildings(p_drop))
    t_drop = _treatment("drop", p_drop, b_drop, rng, n_boot)

    t_imp = _treatment("impute", pairs, b, rng, n_boot)
    t_imp.update(imp_stats or {})
    treatments = [t_imp, t_old, t_drop]
    base = t_imp
    for t in treatments:
        t["gross_delta_pp"] = round((t["gross"] or 0) - (base["gross"] or 0), 4)
        t["net_delta_pp"] = round((t["net"] or 0) - (base["net"] or 0), 4)
        t["buildings_delta"] = t["buildings"] - base["buildings"]
    rm_now = dict(zip(zip(b.county, b.k), b.rent))
    ro_map = {k: v for k, v in zip(zip(b_old.county, b_old.k), b_old.rent)}
    t_old["buildings_rent_moved"] = int(sum(1 for k, v in ro_map.items()
                                            if k in rm_now and round(v) != round(rm_now[k])))

    pd_rung = next((r for r in (ladder or []) if r.get("key") == "parking_drop"), None)
    coverage = {
        "parking_drop_rung": pd_rung["buildings"] if pd_rung else None,
        "parking_drop_yield": pd_rung.get("yield_building") if pd_rung else None,
        "drop": t_drop["buildings"], "area_only": t_old["buildings"], "impute": t_imp["buildings"],
    }
    print(f"[uw] parking audit: verdict {verdict}; ratio {P.get('median')} [{lo}, {hi}] n={n}; "
          f"gross impute(headline) {t_imp['gross']} / area_only {t_old['gross']} / drop {t_drop['gross']}")
    return {
        "predicate": {"field": "交易標的", "bundled": "租賃房屋+車位", "priced": "park_price > 0",
                      "price_source": "*_c_park.csv 車位價格 summed per 編號 (fetch_lvr._park_totals); equals "
                                      "車位總額元 on every row where both > 0; rows with 車位總額元 > 0 and no "
                                      "park.csv price count as unpriced here (the parking-yield block reads "
                                      "車位總額元 directly)",
                      "side": "rent", "frame": "clean_rents(subtract_parking=True) after key_frames, "
                               "BEFORE impute_parking_rent (the tests run on the old frame)",
                      "impute": "per space: same-building itemised median, else county median with >= "
                                f"{AUDIT_MIN_COUNTY_N} itemised rows, else national median; x park_n; rows "
                                "left at or under the NT$3,000 floor are dropped"},
        "lets": lets, "share": share_blk, "within_building": W, "social_only": social_only,
        "verdict": verdict_blk, "exposure": exposure,
        "headline_case": "impute", "previous_headline_case": "area_only",
        "treatments": treatments, "coverage": coverage,
    }, ro_map


def cost_assumptions():
    """Shipped with the payload so every default is auditable next to the number."""
    return [
        {"key": "tax", "zh": "房屋稅＋地價稅", "en": "Holding tax",
         "unit": "% of price / yr", "default": DEFAULT_TAX_PCT, "min": 0.05, "max": 0.40,
         "step": 0.01,
         "src_zh": "彭建文等(2007) 0.089–0.130%、王宏文・曾彥閔(2013) 0.066%、李明軒 約0.12%（皆為自用）；囤房稅2.0 非自住房屋稅由1.2%升至2.0–4.8%，故取其上緣。",
         "src_en": "Peng et al. (2007) 0.089-0.130%, Wang & Tseng (2013) 0.066%, Li ~0.12% -- all self-use. 囤房稅2.0 raised the non-self-use house-tax leg from 1.2% to 2.0-4.8%, so the default sits above the measured range."},
        {"key": "mgmt", "zh": "管理費（臺北；其餘縣市套用新北費率）",
         "en": "Management fee (Taipei; every other county is charged New Taipei's rate)",
         "unit": "NT$/坪/月", "default": DEFAULT_MGMT_A, "min": 0, "max": 300, "step": 5,
         "src_zh": "臺北市一般住宅每坪約100–180元（新北90–120元）。僅套用於租賃紀錄顯示「有管理員」的建物。⚠️ 這兩個費率只有雙北的調查來源；本站已擴及22縣市，其餘20縣市一律套用新北費率，因為找不到分縣市的管理費統計。這個假設值多少，見下方敏感度。此外，有管理員建物的租約中約四成在備註寫明「租金總額含管理費」，五成沒有說；本費用是否該扣，見進階模式「租約自己怎麼說」的兩個界線。",
         "src_en": "Taipei general residential runs NT$100-180 per ping (New Taipei 90-120). Applied only to buildings whose lease records report on-site staff. WARNING: those two rates are the only ones with a published source, and the site now covers 22 counties -- the other 20 are all charged New Taipei's rate for want of a per-county statistic. What that assumption is worth is measured below. Separately, about four in ten leases in staffed buildings state in 備註 that the rent includes the fee and five in ten say nothing; whether the fee should be charged at all is bounded under \"what the lease itself says\" (advanced mode)."},
        {"key": "vacancy", "zh": "空置率", "en": "Vacancy",
         "unit": "%", "default": DEFAULT_VACANCY_PCT, "min": 0, "max": 20, "step": 0.5,
         "src_zh": "台灣沒有租賃空置率的官方統計；常被引用的 8.77% 是低度使用（用電）住宅率的 111年下半年 數字，量測的是完全不同的母體，而且它每半年都在動（本頁另外公布 111H1 9.52%、114H1 10.43%、114H2 9.44%）。5% 純屬假設；它的形狀見「空置率」那一節。",
         "src_en": "No Taiwan rental-vacancy statistic exists. The often-quoted 8.77% is the 111H2 reading of the electricity-derived LOW-USE rate -- a different population, and one that moves every half-year (this page also publishes 111H1 9.52%, 114H1 10.43% and 114H2 9.44%). 5% is an assumption, not a measurement; what can be measured about its SHAPE is in the vacancy section."},
        {"key": "repairs", "zh": "修繕（依屋齡加權）", "en": "Repairs (age-weighted)",
         "unit": "% of rent", "default": DEFAULT_REPAIRS_PCT, "min": 0, "max": 25, "step": 0.5,
         "src_zh": "無公開資料來源。以租金百分比計並隨屋齡放大（×(1+屋齡/50)），因為固定比例會朝「公寓劣於大樓」的方向系統性偏誤。",
         "src_en": "No public source. Charged as a share of rent and scaled by age (x(1+age/50)), because a flat rate biases the walk-up-vs-tower comparison in one direction."},
    ]


def gap_sensitivity(pairs):
    """Median yield by pairing gap. Flat => the price index did its job."""
    if pairs.empty:
        return []
    out = []
    for gap, grp in pairs.groupby("gap"):
        b = to_buildings(grp)
        if len(b) >= 20:
            out.append({"gap": int(gap), "yield": median(b.gross),
                        "buildings": int(len(b))})
    return out


def two_stage_ci(gp, keys, n, rng):
    """95% CI on a median of building-level medians, resampling BOTH levels.

    `gp` maps a building key to its vector of pair-level yields. Buildings are
    resampled with replacement, then pairs within each drawn building, so a
    building resting on one pair is correctly treated as measured less precisely
    than one resting on forty.

    Extracted so the headline, the district ranking and the honesty ladder all
    quote intervals produced by the same code. Two implementations of this drifted
    once already and the ladder was the thing that drifted.
    """
    keys = list(keys)
    if not keys:
        return (None, None)
    out = []
    for _ in range(n):
        meds = []
        for j in rng.integers(0, len(keys), len(keys)):
            v = gp.get(keys[j])
            if v is None or not len(v):
                continue
            meds.append(np.median(v[rng.integers(0, len(v), len(v))])
                        if len(v) > 1 else v[0])
        if meds:
            out.append(np.median(meds))
    if not out:
        return (None, None)
    lo, hi = np.percentile(out, [2.5, 97.5])
    return (round(float(lo), 3), round(float(hi), 3))

# ═══════════════════════════════════════════════════ THE HONESTY LADDER ══

def build_ladder(raw_sales, raw_rents, index=None, capture=None, n_boot=120,
                 seed=11):
    """Recompute the headline with one more correction applied at each rung.

    Each rung applies one more correction — NOT a claim that any competitor
    publishes rung 1. Nobody computes a yield that way; rung 1 exists to show the
    size of the corrections.

    This ladder is a PATH, and it used to be described as a measurement of what
    each cleaning decision is worth. That was wrong, because the sample is not
    nested the way the presentation implies: every filter changes the composition
    the next one acts on. `filter_marginals` measures the filters
    order-independently; this function measures the route taken through them.

    Every rung calls the SAME `clean_sales`/`clean_rents` the headline uses, with
    flags flipped. The ladder used to reimplement the filters and drifted from
    the real pipeline by a building — so the last rung is now identical to the
    headline by construction, not by coincidence.

    Every rung now carries BOTH units and a CI. It used to report rungs 1–5 per
    pair and 6–7 per building, and that switch — not any cleaning decision — is
    what made the social-housing rung read backwards: social leases concentrate
    in a few enormous 包租代管 studio towers, so a pair-level median weights those
    buildings 14:1 where a building-level median weights them 3.3:1.
    """
    rungs = [
        ("raw",      "實價登錄原始資料（全部租賃紀錄）", "Every lease record, unfiltered",
         dict(exclude_parking=False, exclude_social=False, exclude_rooms=False), "pair"),
        ("parking",  "扣掉車位金額（買賣與租賃同步）", "Parking subtracted, both sides",
         dict(exclude_parking=True, exclude_social=False, exclude_rooms=False,
              subtract_parking=True), "pair"),
        ("social",   "排除社會住宅包租代管", "Social housing removed",
         dict(exclude_parking=True, exclude_social=True, exclude_rooms=False,
              subtract_parking=True), "pair"),
        ("rooms",    "只留整棟(戶)出租與獨立套房（排除分租套房／雅房、分層出租、未填）",
                     "Whole-unit lets only (room-shares, floor lets and blanks removed)",
         dict(exclude_parking=True, exclude_social=True, exclude_rooms=True,
              subtract_parking=True), "pair"),
        # The one correction on the SALE side. 9.29% of clean residential sales
        # are 親友間交易, and they close 24.9% under comparable arm's-length
        # sales — which does not nudge a yield, it inflates it by a third. Every
        # rung above this one still has them in, which is what makes the drop
        # here a measurement of the bias rather than an assertion about it.
        ("related",  "排除親友間交易", "Related-party sales removed",
         dict(exclude_parking=True, exclude_social=True, exclude_rooms=True,
              subtract_parking=True, exclude_related=True), "pair"),
        ("building", "以「棟」為單位，而非配對數", "Per building, not per pair",
         dict(exclude_parking=True, exclude_social=True, exclude_rooms=True,
              subtract_parking=True, exclude_related=True), "building"),
        # v2.1: the last step. A flat+space lease with no itemised space rent
        # used to be kept with only its area taken out, on the assumption the
        # space came free; parking_audit_block tested that within building and
        # it failed, so an imputed per-space rent is now subtracted too. This
        # rung IS the headline's code path.
        ("park_impute", "推算並扣除未列明的車位租金", "Un-itemised space rent imputed and subtracted",
         dict(exclude_parking=True, exclude_social=True, exclude_rooms=True,
              subtract_parking=True, exclude_related=True, impute_parking=True), "building"),
        # Not another step down the same staircase — an ALTERNATIVE to rung 2.
        # Instead of dropping every transaction that carries a parking space, take
        # the space out using the price and area the registry itemises in its
        # *_park.csv sub-file, and drop only what it failed to itemise.
        # What the site used to do: drop the whole transaction rather than take
        # the space out of it. Kept as a rung because it is what every other
        # published Taiwanese yield still does, and the difference is the point.
        ("parking_drop", "改為整筆排除含車位的交易（本站舊作法）",
         "Parking-bundled transactions dropped whole (the old treatment)",
         dict(exclude_parking=True, exclude_social=True, exclude_rooms=True,
              subtract_parking=False, exclude_related=True), "building"),
    ]
    out = []
    rng = np.random.default_rng(seed)
    for key, zh, en, flags, unit in rungs:
        sub = flags.get("subtract_parking", False)
        rel = flags.get("exclude_related", False)
        imp = flags.get("impute_parking", False)
        s = L.clean_sales(raw_sales, exclude_parking=flags["exclude_parking"],
                          subtract_parking=sub, exclude_related=rel)
        # exclude_related is a SALE-side flag and impute_parking is applied
        # after keying, so neither reaches **flags.
        r = L.clean_rents(raw_rents, **{k: v for k, v in flags.items()
                                        if k not in ("exclude_related", "impute_parking")})
        if s.empty or r.empty:
            continue
        s, r, _ = key_frames(s, r)
        if imp:
            r, _ = impute_parking_rent(r)
        p = match_pairs(s, r, index=index)
        if p.empty:
            continue
        b = to_buildings(p)
        if capture is not None:
            capture[key] = b
        gp = {kk: g.gross.values for kk, g in p.groupby(["county", "k"])}
        lo, hi = two_stage_ci(gp, list(gp.keys()), n_boot, rng)
        out.append({
            "key": key, "zh": zh, "en": en, "unit": unit,
            "yield": median(p.gross) if unit == "pair" else median(b.gross),
            # Both units on every rung. `yield` stays the rung's own unit so
            # nothing downstream changes meaning; the page reads the two below.
            "yield_pair": median(p.gross),
            "yield_building": median(b.gross),
            # The interval is on the BUILDING median — the only unit this site
            # treats as honest, and now the only one the ladder is read in.
            "lo": lo, "hi": hi,
            "pairs": int(len(p)),
            "buildings": int(len(b)),
            "rent_records": int(len(r)),
        })
    return out



# ═══════════════════════════ WHAT EACH FILTER IS ACTUALLY WORTH ══════════

FILTER_KEYS = ("social", "rooms", "related")


def filter_marginals(raw_sales, raw_rents, index=None):
    """The ladder shows a PATH. This shows what each filter is worth on its own.

    The ladder applies its corrections in a fixed order and reports the move at
    each step. That is honest about the path and dishonest about the filters,
    because the sample is not nested in the way the presentation implies: every
    filter changes the composition the next one acts on, so the move at a rung is
    "this filter, given everything already applied", not "this filter".

    It matters, and the social-housing rung is the proof. On the page it reads
    -0.165pp -- social housing removed, yield DOWN -- which is backwards for a
    population that rents 28% below market. Measured order-independently it is
    -0.087pp at pair level and **+0.181pp at building level**, the sign the
    subsidy story predicts, and the largest of the three filters.

    Two things produce the reversal, and `mechanism` below measures both:

    1. Simpson. Within every 出租型態 a social lease yields LESS than a market
       one. But social leases are 70.3% 獨立套房 and 0.0% 分租套房, while market
       leases are 24.5% and 14.6%. Room-shares yield ~1.27% because their area
       field describes the building rather than the let space -- which is the
       whole reason the NEXT rung removes them. So dropping social housing
       triples the room-share weight and the aggregate falls while every
       component rises.
    2. Concentration. A building holding any social lease carries 32.8 pairs
       against 7.8 for one that holds none. Pair-level medians therefore weight
       social-containing buildings 14:1; building-level weights them 3.3:1. The
       ladder shows rungs 1-5 per pair, so it shows the concentrated version.

    Contributions are Shapley values over the 2^3 grid: the average marginal
    effect of switching a filter on, over all 6 orderings. They sum exactly to
    the total move, which is what makes them a decomposition rather than three
    unrelated sensitivities.
    """
    if raw_sales is None or raw_rents is None or raw_sales.empty or raw_rents.empty:
        return {}

    # Clean once per distinct flag combination, not once per cell: the cleaners
    # are the expensive half and only 2 sale frames and 4 rent frames exist.
    def _keyed(df):
        d = df.copy()
        d["k"] = d["土地位置建物門牌"].map(addr_key)
        d["district"] = _tw(d["鄉鎮市區"])
        if "建物型態" in d.columns:
            d["bldg_type"] = d["建物型態"].map(TYPE_SHORT)
        return d[d.k != ""]

    S_ = {rel: _keyed(L.clean_sales(raw_sales, exclude_parking=True,
                                    subtract_parking=True, exclude_related=rel))
          for rel in (False, True)}
    R_ = {(soc, rm): _keyed(L.clean_rents(raw_rents, exclude_parking=True,
                                          exclude_social=soc, exclude_rooms=rm,
                                          subtract_parking=True))
          for soc in (False, True) for rm in (False, True)}

    grid = {}
    for soc in (False, True):
        for rm in (False, True):
            for rel in (False, True):
                p = match_pairs(S_[rel], R_[(soc, rm)], index=index)
                if p.empty:
                    return {}
                b = to_buildings(p)
                grid[(soc, rm, rel)] = {
                    "pair": median(p.gross), "building": median(b.gross),
                    "pairs": int(len(p)), "buildings": int(len(b)),
                }

    # Shapley: average marginal effect over all 3! orderings. The weight
    # k!(n-k-1)!/n! is the share of orderings in which exactly the coalition
    # `sub` precedes filter `idx`.
    import itertools
    from math import factorial
    n = len(FILTER_KEYS)

    def shapley(idx, level):
        others = [i for i in range(n) if i != idx]
        total = 0.0
        for k in range(n):
            for sub in itertools.combinations(others, k):
                off = [False] * n
                for i in sub:
                    off[i] = True
                on = list(off)
                on[idx] = True
                w = factorial(k) * factorial(n - k - 1) / factorial(n)
                total += w * (grid[tuple(on)][level] - grid[tuple(off)][level])
        return round(total, 4)

    none_, all_ = grid[(False, False, False)], grid[(True, True, True)]
    out = {
        "grid": [{"social": s, "rooms": r, "related": e, **v}
                 for (s, r, e), v in grid.items()],
        "shapley": {lvl: {k: shapley(i, lvl) for i, k in enumerate(FILTER_KEYS)}
                    for lvl in ("pair", "building")},
        # What the ladder shows: each filter measured in ITS position in the
        # chain, which is what makes the social rung read backwards.
        "path": {
            "social": round(grid[(True, False, False)]["pair"] - none_["pair"], 4),
            "rooms": round(grid[(True, True, False)]["pair"]
                           - grid[(True, False, False)]["pair"], 4),
            "related": round(all_["pair"] - grid[(True, True, False)]["pair"], 4),
        },
        "total": {lvl: round(all_[lvl] - none_[lvl], 4) for lvl in ("pair", "building")},
        "base": {lvl: none_[lvl] for lvl in ("pair", "building")},
    }
    return out


def marginal_mechanism(raw_sales, raw_rents, index=None):
    """The two numbers that explain the social rung's reversal, measured.

    Published so the explanation on the page is a reading of the data rather
    than a story about it.
    """
    if raw_sales is None or raw_rents is None or raw_sales.empty or raw_rents.empty:
        return {}
    s = L.clean_sales(raw_sales, exclude_parking=True, subtract_parking=True,
                      exclude_related=False)
    r = L.clean_rents(raw_rents, exclude_parking=True, exclude_social=False,
                      exclude_rooms=False, subtract_parking=True).copy()
    r["is_social"] = r["租賃住宅服務"].fillna("").isin(L.SOCIAL_HOUSING)
    r["let_type"] = r["出租型態"].fillna("")
    s, r, _ = key_frames(s, r)
    scols = ["county", "district", "k", "q", "price", "area_ping", "bldg_type",
             "built_roc_y"]
    rcols = ["county", "k", "q", "rent", "area_ping", "is_social", "let_type"]
    m = s[scols].merge(r[rcols], on=["county", "k"], suffixes=("_s", "_r"))
    m["gap"] = (m.q_s - m.q_r).abs()
    m = m[m.gap <= MATCH_WINDOW_Q].copy()
    if m.empty:
        return {}
    m["price_adj"] = m.price.astype(float)
    m["gross"] = (m.rent * 12.0) / m.price_adj * 100.0
    lo, hi = YIELD_BAND
    m = m[(m.gross > lo) & (m.gross < hi)]
    if m.empty:
        return {}

    info = m.groupby(["county", "k"]).agg(pairs=("gross", "size"),
                                          soc=("is_social", "mean"))
    has, non = info[info.soc > 0], info[info.soc == 0]
    by_type = []
    for lt in ("獨立套房", "整棟(戶)出租", "分租套房"):
        a, b = m[(m.let_type == lt) & m.is_social], m[(m.let_type == lt) & ~m.is_social]
        if not len(a) or not len(b):
            continue
        by_type.append({
            "let_type": lt,
            "social": median(a.gross), "market": median(b.gross),
            "n_social": int(len(a)), "n_market": int(len(b)),
            "social_share_pct": round(len(a) / max(1, int(m.is_social.sum())) * 100, 1),
            "market_share_pct": round(len(b) / max(1, int((~m.is_social).sum())) * 100, 1),
        })
    return {
        "by_let_type": by_type,
        "concentration": {
            "with_social": {"buildings": int(len(has)), "pairs": int(has.pairs.sum()),
                            "pairs_per_building": round(float(has.pairs.mean()), 1)},
            "without": {"buildings": int(len(non)), "pairs": int(non.pairs.sum()),
                        "pairs_per_building": round(float(non.pairs.mean()), 1)},
            "pair_weight_ratio": round(float(has.pairs.sum()) / max(1.0, float(non.pairs.sum())), 1),
            "bldg_weight_ratio": round(len(has) / max(1, len(non)), 1),
        },
        "social_pair_median": median(m[m.is_social].gross),
        "market_pair_median": median(m[~m.is_social].gross),
    }

# ══════════════════════════════ BIAS, UNCERTAINTY AND SENSITIVITY ════════
# Everything below answers the same question from a different angle: how much
# should you distrust the headline? Each block is measured, not asserted.

def wmedian(values, weights):
    v = np.asarray(values, dtype=float); w = np.asarray(weights, dtype=float)
    ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
    v, w = v[ok], w[ok]
    if not len(v):
        return None
    o = np.argsort(v); v, w = v[o], w[o]
    return float(v[np.searchsorted(np.cumsum(w) / w.sum(), 0.5)])


def coverage_waterfall(raw_sales, raw_rents, universe_sales, b_final):
    """Where do the buildings go, and WHOSE fault is each loss?

    The headline coverage figure reads as "this is what the registry law lets you
    see". That is only mostly true: the law is the dominant term, but our own
    filters are a fifth of the loss and the page has to say which is which,
    or it is taking credit for a limitation it partly imposed.
    """
    def prep_s(df):
        d = df.copy()
        d["k"] = d["土地位置建物門牌"].map(addr_key)
        d["district"] = _tw(d["鄉鎮市區"])
        d["bldg_type"] = d["建物型態"].map(TYPE_SHORT)
        return d[d.k != ""]

    def prep_r(df):
        d = df.copy()
        d["k"] = d["土地位置建物門牌"].map(addr_key)
        return d[d.k != ""]

    # exclude_related=False on both: these are the stages BEFORE the sale-side
    # correction, and the correction gets its own labelled step below. Letting
    # them inherit the new default would drop ~9% of buildings with no row in
    # the waterfall to account for them — silent attrition, on the one page that
    # exists to account for attrition.
    S_all = prep_s(L.clean_sales(raw_sales, exclude_parking=False,
                                 exclude_related=False))
    S_np = prep_s(L.clean_sales(raw_sales, subtract_parking=True,
                                exclude_related=False))
    S_fin = prep_s(L.clean_sales(raw_sales, subtract_parking=True,
                                 exclude_related=True))
    R_all = prep_r(L.clean_rents(raw_rents, exclude_parking=False,
                                 exclude_social=False, exclude_rooms=False))
    R_np = prep_r(L.clean_rents(raw_rents, exclude_social=False, exclude_rooms=False,
                                subtract_parking=True))
    R_ns = prep_r(L.clean_rents(raw_rents, exclude_rooms=False, subtract_parking=True))
    R_fin = prep_r(L.clean_rents(raw_rents, subtract_parking=True))
    n0 = S_all.groupby(["county", "k"]).ngroups

    def matched(S, R):
        p = match_pairs(S, R)
        return 0 if p.empty else len(to_buildings(p))

    n1 = len(set(zip(S_all.county, S_all.k)) & set(zip(R_all.county, R_all.k)))
    stages = [
        ("no_lease", "law", "完全沒有租賃紀錄", "No lease record at all", n0, n1),
        # `matched()` runs match_pairs, which applies the +/-4-quarter window AND
        # the 0.3-12% yield band, so this step's loss is both. Named for both
        # rather than for the window alone.
        ("window", "ours", "租賃與買賣相隔超過 4 季，或報酬率落在品質區間外",
         "Lease more than 4 quarters from the sale, or yield outside the quality band",
         n1, matched(S_all, R_all)),
        # The step is no longer "carries a parking space" — those are subtracted
        # now. What is left is the rows the registry did not itemise, which
        # cannot be corrected and so still have to go.
        ("parking", "ours", "車位金額未列明，無法扣除",
         "Parking not itemised, so it cannot be subtracted",
         matched(S_all, R_all), matched(S_np, R_np)),
        ("social", "ours", "租約是社會住宅", "Lease is social housing",
         matched(S_np, R_np), matched(S_np, R_ns)),
        # NOT only 分租套房／雅房: exclude_rooms is a whitelist of 整棟(戶)出租
        # and 獨立套房, so it also drops 分層出租 and rows with no 出租型態 at
        # all. Naming just the room-shares put 5,964 lease records in a
        # category they are not in.
        ("rooms", "ours", "租約不是整戶出租（分租套房／雅房、分層出租、未填）",
         "Lease is not a whole unit (room-share, floor let, or type blank)",
         matched(S_np, R_ns), matched(S_np, R_fin)),
        # Ours, and the only one on the sale side. These buildings have a real
        # lease and a real sale; the sale just is not a market price.
        ("related", "ours", "買賣是親友間交易，不是市場價",
         "Sale is between relatives, so it is not a market price",
         matched(S_np, R_fin), matched(S_fin, R_fin)),
    ]
    steps, law, ours = [], 0.0, 0.0
    for key, who, zh, en, a, c in stages:
        pp = (a - c) / n0 * 100
        if who == "law":
            law += pp
        else:
            ours += pp
        steps.append({"key": key, "whose": who, "zh": zh, "en": en,
                      "from": int(a), "to": int(c), "lost_pp": round(pp, 2)})
    final = stages[-1][5]
    return {
        "universe": int(n0), "final": int(final),
        "coverage_pct": round(final / n0 * 100, 2),
        "ceiling_pct": round(stages[1][5] / n0 * 100, 1),   # no filters, window only
        "law_pp": round(law, 1), "ours_pp": round(ours, 1),
        "law_share": round(law / (law + ours) * 100),
        "steps": steps,
    }


def universe_buildings(raw_sales, with_rows=False):
    """One row per building that has ANY residential sale on record. This is the
    honest denominator and the post-stratification frame.

    `with_rows` additionally returns the keyed ROW frame this builds and would
    otherwise throw away -- the only way to count sale records in 筆 without a
    second pass over half a million rows. The default return is unchanged and a
    test asserts the frame is identical either way."""
    # exclude_related=False on purpose. A building that only ever sold to a
    # relative is still a building that exists and still has a residential sale
    # on record, so it belongs in the denominator. Filtering it here would
    # shrink the denominator and make coverage look better than it is, which is
    # the one direction this number must never move by accident.
    d = L.clean_sales(raw_sales, exclude_parking=False, exclude_related=False).copy()
    d["k"] = d["土地位置建物門牌"].map(addr_key)
    d["bldg_type"] = d["建物型態"].map(TYPE_SHORT)
    d["district"] = _tw(d["鄉鎮市區"])
    d = d[d.k != ""]
    ub = d.groupby(["county", "k"], as_index=False).agg(
        bldg_type=("bldg_type", _mode), district=("district", _mode),
        price=("price", "median"), area=("area_ping", "median"),
        built=("built_roc_y", "median"))
    ub["ppp"] = ub.price / ub.area
    return (ub, d) if with_rows else ub


def post_stratify(b, ub, deciles=10):
    """Reweight the matched buildings to the price-and-type composition of every
    building that sold.

    Measuring the selection bias and then not correcting it leaves the reader to
    guess its size. This turns it into a number. Price bands do the work: the
    matched sample is ~2.9x over-weighted in the most expensive decile, and price
    is the yield's denominator, so type-only reweighting (which shifts the answer
    by 0.01pp) badly understates the problem.
    """
    if b.empty or ub.empty:
        return {}
    edges = np.quantile(ub.ppp.dropna(), np.linspace(0, 1, deciles + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    ub = ub.assign(pb=pd.cut(ub.ppp, edges, labels=False, duplicates="drop"))
    bb = b.assign(pb=pd.cut(b.price_ping, edges, labels=False, duplicates="drop"))

    def run(cols):
        us = ub.groupby(cols).size(); us = us / us.sum()
        ms = bb.groupby(cols).size(); ms = ms / ms.sum()
        w = (us / ms).replace([np.inf, -np.inf], np.nan).dropna()
        key = bb[cols[0]] if len(cols) == 1 else list(zip(*[bb[c] for c in cols]))
        ww = np.array([w.get(k, np.nan) for k in key])
        return (wmedian(bb.gross.values, ww), wmedian(bb.net.values, ww),
                int(np.isfinite(ww).sum()))

    g_pb, n_pb, _ = run(["pb"])
    g_bt, n_bt, _ = run(["bldg_type"])
    g_both, n_both, used = run(["pb", "bldg_type"])
    vis = median(b.gross)
    us = ub.groupby("pb").size() / len(ub)
    ms = bb.groupby("pb").size() / len(bb)
    return {
        "visible_gross": vis, "visible_net": median(b.net),
        "by_price": {"gross": round(g_pb, 4), "net": round(n_pb, 4)},
        "by_type": {"gross": round(g_bt, 4), "net": round(n_bt, 4)},
        "by_both": {"gross": round(g_both, 4), "net": round(n_both, 4), "n": used},
        "shift_pp": round(g_both - vis, 4),
        "deciles": [{"d": int(d) + 1,
                     "universe": round(float(us.get(d, 0)) * 100, 1),
                     "matched": round(float(ms.get(d, 0)) * 100, 1),
                     "ratio": round(float(ms.get(d, 0)) / float(us.get(d, 1e-9)), 2)}
                    for d in sorted(us.index)],
    }


# ── what 6% identifies ───────────────────────────────────────────────────────

PID_TRIM = 0.05         # the percentile a resemblance assumption trims to
PID_DECILES = 10        # price bands, on the universe's own edges
PID_MIN_CELL = 25       # below this a cell falls back to type level, and is counted
PID_SEED = 37
PID_BOOT = 200


def _pid_bound(cells, col, lo_key, hi_key):
    """The sharp bound on a weighted median when part of every cell is unseen.

    Each cell contributes its observed values at weight share x p_observed, and
    the unseen remainder as a single atom at the cell's assumed floor (for the
    lower bound) or ceiling (for the upper). The median of that mixture is the
    extreme the data allow; nothing between the two ends is ruled out.
    """
    out = {}
    for end, key in (("lo", lo_key), ("hi", hi_key)):
        vals, wts = [], []
        for c in cells:
            # A cell with too few matched buildings still carries its mass: it
            # contributes nothing observed and its whole share sits on the
            # weaker type-level assumption. Skipping it instead would drop that
            # mass from the weighting and bound a different population.
            n = len(c["vals"][col])
            if n:
                vals.extend(c["vals"][col]); wts.extend([c["share"] * c["p"] / n] * n)
            if c["share"] * (1.0 - c["p"]) > 0:
                vals.append(c[key][col]); wts.append(c["share"] * (1.0 - c["p"]))
        m = wmedian(vals, wts)
        out[end] = None if m is None else round(float(m), 3)
    if out["lo"] is not None and out["hi"] is not None:
        out["width"] = round(out["hi"] - out["lo"], 3)
    return out


def partial_id_block(b, ub, n_boot=PID_BOOT, seed=PID_SEED, ppp_gap_pct=None):
    """What the registry identifies about the buildings it cannot see.

    The site prices 6.22% of the buildings that have a sale on record. The
    question this block answers is not "what is the yield" but "what does
    seeing 6% of them permit anyone to say", and the answer is a ladder of
    intervals, each one rung narrower because one more assumption was added,
    each assumption written as a sentence a reader can reject.

    The formal fact underneath: a median's worst-case bound only leaves the
    support band once more than HALF the population is observed. This site
    observes 6.22%, and with every one of its own filters removed the
    registry's structural ceiling is 24.0% -- less than half. So no amount of
    better cleaning moves the first rung. That is the result, not a caveat.

    RUNG 1 IS NOT ASSUMPTION-FREE and does not claim to be. It returns
    YIELD_BAND, the band this site itself uses to throw out filing errors. It
    assumes only that, and it is published as "the site's own cleaning band,
    and nothing else".

    THE TRIM IS A RESEMBLANCE ASSUMPTION, not a support one. "An unmatched
    building lies inside the 5th-95th percentile of matched buildings of its
    type" forbids an unmatched building from being in its own type's top 5%,
    which is strictly stronger than "unmatched are distributed like matched".
    The untrimmed rung ships beside it so the reader can see what the trim
    buys.

    SCOPE is the buildings that have a sale in the window -- 棟, this site's
    own unit, its own frame. The block does NOT reweight onto the house-tax
    dwelling stock: that would convert 宅 shares into 棟 weights, which is
    only valid if dwellings-per-building is constant across types, and a tower
    holds an order of magnitude more than a walk-up. It is the same unit
    confusion that got "one building in 1,086" withdrawn, and it was measured
    to be worth 0.007pp. The 1~3層 透天 stock -- 42.7% of all dwellings -- is
    outside the site's filters by construction and no reweighting reaches a
    cell with no data, so no rung here speaks about "Taiwan".
    """
    if b is None or b.empty or ub is None or ub.empty:
        return {}
    lo_band, hi_band = YIELD_BAND
    edges = np.quantile(ub.ppp.dropna(), np.linspace(0, 1, PID_DECILES + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    U = ub.assign(pb=pd.cut(ub.ppp, edges, labels=False, duplicates="drop"))
    B = b.assign(pb=pd.cut(b.price_ping, edges, labels=False, duplicates="drop"))
    B = B.assign(ab=(115.0 - B.built).map(_walk_bands))
    U = U.assign(ab=(115.0 - U.built).map(_walk_bands))
    N = int(len(U))
    _B = B

    def build_cells(keys, trim, B=None):
        """One cell per key combination: its share of the universe, the share of
        it this site observes, its observed yields, and the floor/ceiling the
        rung's assumption puts on the rest."""
        B = _B if B is None else B
        cells, below, fell = [], 0, 0
        gtype = B.groupby("bldg_type")
        tsup = {t: {c: (float(np.quantile(g[c].dropna(), trim)),
                        float(np.quantile(g[c].dropna(), 1 - trim)))
                    for c in ("gross", "net")} for t, g in gtype if len(g)}
        for key, ug in U.groupby(keys):
            mg = B
            for c, v in zip(keys, key if isinstance(key, tuple) else (key,)):
                mg = mg[mg[c] == v]
            share = len(ug) / N
            t = (key[0] if isinstance(key, tuple) else key)
            if len(mg) < PID_MIN_CELL:
                below += 1; fell += int(len(ug))
                sup = tsup.get(t) or tsup[next(iter(tsup))]
                vals = {c: [] for c in ("gross", "net")}
                p = 0.0
            else:
                vals = {c: mg[c].dropna().values for c in ("gross", "net")}
                sup = {c: (float(np.quantile(vals[c], trim)),
                           float(np.quantile(vals[c], 1 - trim))) if len(vals[c])
                       else tsup[t][c] for c in ("gross", "net")}
                p = min(1.0, len(mg) / max(1, len(ug)))
            cells.append({"share": share, "p": p, "vals": vals,
                          "lo": {c: sup[c][0] for c in sup},
                          "hi": {c: sup[c][1] for c in sup}})
        return cells, below, fell

    # the ladder. each entry: key, one rejectable sentence, the cell keys, the trim
    ladder = [
        ("band", ["bldg_type"], None),
        ("type_support", ["bldg_type"], 0.0),
        ("type_trim", ["bldg_type"], PID_TRIM),
        ("type_price", ["bldg_type", "pb"], PID_TRIM),
        ("type_price_age", ["bldg_type", "pb", "ab"], PID_TRIM),
    ]
    rungs, prev_w = [], None
    matched_g, matched_n = median(b.gross), median(b.net)
    for key, keys, trim in ladder:
        if key == "band":
            # no cell structure: every unseen building may sit anywhere in the
            # band this site uses to reject filing errors, and nothing narrower
            # is licensed while coverage is under a half
            bd = {"gross": {"lo": round(lo_band, 3), "hi": round(hi_band, 3),
                            "width": round(hi_band - lo_band, 3)}}
            cells_n, below, fell = 1, 0, 0
        else:
            cells, below, fell = build_cells(keys, trim)
            bd = {c: _pid_bound(cells, c, "lo", "hi") for c in ("gross", "net")}
            cells_n = len(cells)
        w = bd["gross"].get("width")
        rungs.append({
            "key": key, "is_bound": True, "trim": trim,
            "cells": cells_n, "cells_below_min": below, "fellback_universe_n": fell,
            "gross": bd.get("gross"), "net": bd.get("net"),
            "buys_pp": (None if prev_w is None or w is None else round(prev_w - w, 3)),
        })
        prev_w = w

    # rung 4: the direction of the residual selection, published BOTH ways
    tp = next(r for r in rungs if r["key"] == "type_price")
    mts = []
    for key, lo_, hi_ in (("mts_up", matched_g, tp["gross"]["hi"]),
                          ("mts_down", tp["gross"]["lo"], matched_g)):
        mts.append({"key": key, "is_bound": True, "gross": {
            "lo": round(lo_, 3), "hi": round(hi_, 3), "width": round(hi_ - lo_, 3)}})

    # what each rung's endpoints are worth as sampling, not as identification.
    # A cluster bootstrap over buildings: a support quantile is a building-level
    # statistic, so resampling pairs inside a building would not move it.
    rng = np.random.default_rng(seed)
    keys_tp = ["bldg_type", "pb"]
    los, his = [], []
    for _ in range(n_boot):
        Bs = B.iloc[rng.integers(0, len(B), len(B))]
        cs, _, _ = build_cells(keys_tp, PID_TRIM, B=Bs)
        bb = _pid_bound(cs, "gross", "lo", "hi")
        if bb.get("lo") is not None:
            los.append(bb["lo"]); his.append(bb["hi"])
    endpoint_ci = ({"lo_ci": [round(float(np.percentile(los, 2.5)), 3),
                              round(float(np.percentile(los, 97.5)), 3)],
                    "hi_ci": [round(float(np.percentile(his, 2.5)), 3),
                              round(float(np.percentile(his, 97.5)), 3)],
                    "n_boot": n_boot, "seed": seed,
                    "note_zh": "這是端點的抽樣誤差，不是報酬率的不確定性。",
                    "note_en": "sampling error on the endpoints, not uncertainty about the yield"}
                   if los else None)

    # composition, three units side by side and never divided across
    comp = []
    for t in TYPE_SHORT.values():
        un, mn = int((U.bldg_type == t).sum()), int((B.bldg_type == t).sum())
        if not un:
            continue
        comp.append({"type": t, "universe_n": un, "matched_n": mn,
                     "universe_share_pct": round(un / N * 100, 1),
                     "matched_share_pct": round(mn / max(1, len(B)) * 100, 1),
                     "match_rate_pct": round(mn / un * 100, 2), "unit": "棟"})

    # the type whose own coverage makes it hopeless on its own
    worst = min(comp, key=lambda c: c["match_rate_pct"])
    wv = B[B.bldg_type == worst["type"]].gross.dropna()
    unanswerable = [{
        "key": "type_alone", "type": worst["type"],
        "coverage_pct": worst["match_rate_pct"],
        "support": [round(float(np.quantile(wv, PID_TRIM)), 3),
                    round(float(np.quantile(wv, 1 - PID_TRIM)), 3)] if len(wv) else None,
    }]
    if len(wv):
        unanswerable[0]["width"] = round(unanswerable[0]["support"][1]
                                         - unanswerable[0]["support"][0], 3)

    head = next(r for r in rungs if r["key"] == "type_price")
    print(f"[uw] partial id: band {rungs[0]['gross']['lo']}-{rungs[0]['gross']['hi']} -> "
          f"type_price {head['gross']['lo']}-{head['gross']['hi']} gross, "
          f"{head['net']['lo']}-{head['net']['hi']} net ({head['cells']} cells)")
    # the measured matched-minus-unmatched price gap, formatted once
    _gap = "--" if ppp_gap_pct is None else f"{ppp_gap_pct:g}"
    return {
        "ppp_gap_pct": ppp_gap_pct,
        "scope": {"zh": "窗口內有成交紀錄的建物", "en": "buildings with a recorded sale in the window",
                  "unit": "棟", "n": N, "matched": int(len(B)),
                  "coverage_pct": round(len(B) / N * 100, 2),
                  "not_taiwan_zh": "1~3 層透天佔全國住宅 42.7%，本站篩選在定義上排除，沒有任何一階說得到「全臺灣」。",
                  "not_taiwan_en": "1-3 storey 透天 are 42.7% of the country's dwellings and are outside "
                                   "this site's filters by construction; no rung here speaks about Taiwan."},
        "median_bound_requires_coverage_pct": 50.0,
        "ceiling_pct": 24.0,
        "trim": PID_TRIM, "deciles": PID_DECILES, "min_cell": PID_MIN_CELL,
        "composition": comp,
        "rungs": rungs, "mts": mts, "mts_signed": False,
        "headline_rung": "type_price",
        "endpoint_ci": endpoint_ci,
        "matched_point": {"gross": matched_g, "net": matched_n},
        "unanswerable": unanswerable,
        "assumptions": {
            "band": {"zh": "只假設本站自己用來剔除登錄錯誤的區間；沒有別的假設。",
                     "en": "assumes only the band this site itself uses to reject filing errors, and nothing else"},
            "type_support": {"zh": "配不到的建物，報酬率落在同型態已配對建物的最小值與最大值之間。",
                             "en": "an unmatched building's yield lies between the lowest and highest seen for its own type"},
            "type_trim": {"zh": "配不到的建物，落在同型態已配對建物的第 5 到第 95 百分位之間——這比「和已配對的分布一樣」更強，因為它不准任何一棟落在自己型態的前 5%。",
                          "en": "it lies inside the 5th-95th percentile of matched buildings of its type -- strictly "
                                "stronger than assuming the unmatched resemble the matched, because it forbids any "
                                "unmatched building from being in its own type's top 5%"},
            "type_price": {"zh": "同型態、且同一個每坪價十分位——價格在每一棟配不到的建物上都看得到，因為它們都有成交紀錄。",
                           "en": "the same, within its own type AND its own decile of price per ping -- a variable "
                                 "observed on every unmatched building, because every one of them has a sale"},
            "type_price_age": {"zh": "再加上同一個屋齡區間。這一階公布是因為它「變寬」：格子細到很多格沒有足夠的已配對建物。",
                               "en": "the same, plus its own age band. Published because it is WIDER: the cells get "
                                     "thin enough that many have too few matched buildings to bound at all"},
            # the gap is MEASURED by age_block on the universe frame and passed
            # in; it used to be the literal 8.5, which drifted out of agreement
            # with the `age` block the moment that block moved frames.
            "mts": {"zh": f"殘餘選擇的方向。兩個方向都說得通、都沒有量測：已配對的建物每坪貴 {_gap}%（指向配不到的更高），但「同時賣掉又出租」挑的是流動性好的投資型物件（指向配不到的更低）。本頁兩邊都登，不選邊。",
                    "en": "a direction for the residual selection. Two arguments point opposite ways and neither is "
                          f"measured: matched buildings are {_gap}% dearer per ping (unmatched would yield more), but "
                          "matching requires both selling and letting, which selects liquid investor stock "
                          "(unmatched would yield less). Both are published; neither is signed."},
        },
    }


def bootstrap_cis(pairs, b, n_overall=200, n_district=120, seed=7):
    """Two-stage bootstrap: resample BUILDINGS, then pairs within each building.

    One stage would miss that a building resting on a single pair is measured far
    less precisely than one resting on forty. Note the effective sample size is
    NOT deflated by pair concentration -- aggregating to buildings already fixed
    that; each building is one observation regardless of how many pairs it has.
    The uncertainty that remains is per-district n, which is small by design
    (the floor is 25), and that is exactly what these intervals expose.
    """
    if pairs.empty or b.empty:
        return {}
    rng = np.random.default_rng(seed)
    gp = {k: g.gross.values for k, g in pairs.groupby(["county", "k"])}

    def boot(keys, n):
        return two_stage_ci(gp, keys, n, rng)

    lo, hi = boot([(c, k) for c, k in zip(b.county, b.k)], n_overall)
    per = {}
    for (c, d), grp in b.groupby(["county", "district"]):
        if len(grp) < MIN_DISTRICT_N:
            continue
        per[f"{c}|{d}"] = boot([(c, k) for k in grp.k], n_district)
    # The same interval one level up, so the county ranking can carry a CI
    # instead of a bare dot. Without it the top level of the chart would be the
    # only place on the page that shows a median with no uncertainty attached.
    per_county = {}
    for c, grp in b.groupby("county"):
        if len(grp) < MIN_DISTRICT_N:
            continue
        per_county[c] = boot([(c, k) for k in grp.k], n_district)
    ordered = sorted(
        [(k, median(b[(b.county == k.split("|")[0]) & (b.district == k.split("|")[1])].gross), v)
         for k, v in per.items()], key=lambda x: x[1])
    overlaps = sum(1 for i in range(len(ordered) - 1)
                   if ordered[i][2][1] is not None and ordered[i + 1][2][0] is not None
                   and ordered[i][2][1] > ordered[i + 1][2][0])
    return {
        "overall": {"median": median(b.gross), "lo": lo, "hi": hi},
        "district": {k: {"lo": v[0], "hi": v[1]} for k, v in per.items()},
        "county": {k: {"lo": v[0], "hi": v[1]} for k, v in per_county.items()},
        "adjacent_overlaps": overlaps,
        "adjacent_pairs": max(0, len(ordered) - 1),
        "extremes_separate": bool(ordered and ordered[-1][2][0] is not None
                                  and ordered[0][2][1] is not None
                                  and ordered[-1][2][0] > ordered[0][2][1]),
    }


def dispersion(pairs, b, min_pairs=4):
    """Spread of yields INSIDE one building vs BETWEEN district medians.

    If a single building spreads wider than the whole city does, then a district
    average -- the product every competitor sells -- is close to meaningless.
    """
    if pairs.empty:
        return {}
    per = pairs.groupby(["county", "k"]).gross
    counts = per.size()
    keep = counts[counts >= min_pairs].index
    if not len(keep):
        return {}
    iqr = per.agg(lambda x: x.quantile(0.75) - x.quantile(0.25))[keep]
    d = b.groupby(["county", "district"]).gross.median()
    n = b.groupby(["county", "district"]).size()
    d = d[n >= MIN_DISTRICT_N]
    b_iqr = float(d.quantile(0.75) - d.quantile(0.25))
    return {
        "buildings": int(len(keep)), "min_pairs": min_pairs,
        "within_iqr": round(float(iqr.median()), 3),
        "between_iqr": round(b_iqr, 3),
        "between_range": round(float(d.max() - d.min()), 3),
        "ratio": round(float(iqr.median()) / b_iqr, 2) if b_iqr else None,
    }


def repairs_specification(b):
    """The same comparison under both repair specs, so the reader sees the result
    under the one that flatters it too.

    Age-scaling was adopted because a flat rate looked like it would bias
    walk-up-vs-tower. Measured, it goes the OTHER way: age-scaling charges old
    walk-ups more and SHRINKS their advantage, so it is the conservative choice.
    """
    def gap(age_scaled):
        vals = [net_yield(p, r * 12, a, m,
                          (None if pd.isna(bb) else 115 - bb) if age_scaled else 0.0,
                          c)
                for p, r, a, m, bb, c in zip(b.price_abs, b.rent, b.area,
                                             b.has_mgr, b.built, b.county)]
        t = pd.Series(vals, index=b.index)
        w = t[b.bldg_type == "公寓"].median()
        tw = t[b.bldg_type == "住宅大樓"].median()
        return round(float(w - tw), 3)
    gross = round(float(b[b.bldg_type == "公寓"].gross.median()
                        - b[b.bldg_type == "住宅大樓"].gross.median()), 3)
    return {"gross": gross, "age_scaled": gap(True), "flat": gap(False)}


def vacancy_breakeven(b, top_n=1):
    """District-level 空屋率 has not been produced since 民國109, five years before
    this window opens, and the current series is county-level PDF only. So the
    per-district vacancy the ranking really wants does not exist.

    What CAN be computed is the break-even: how much higher would the top
    district's vacancy have to be, holding every other district at the default,
    before its rank collapses to the median? If the answer is implausibly large,
    the ranking survives the objection without needing the data.
    """
    d = b.groupby(["county", "district"])
    med = d.gross.median()[d.size() >= MIN_DISTRICT_N].sort_values()
    if len(med) < 3:
        return {}
    (tc, td), top = med.index[-1], med.iloc[-1]
    mid = float(med.median())
    sub = b[(b.county == tc) & (b.district == td)]
    lo, hi = 0.0, 95.0
    for _ in range(60):
        v = (lo + hi) / 2
        got = median(pd.Series([net_yield(p, r * 12, a, m,
                                          None if pd.isna(bb) else 115 - bb, c,
                                          vacancy_pct=v)
                                for p, r, a, m, bb, c in
                                zip(sub.price_abs, sub.rent, sub.area, sub.has_mgr,
                                    sub.built, sub.county)]))
        base = median(pd.Series([net_yield(p, r * 12, a, m,
                                           None if pd.isna(bb) else 115 - bb, c)
                                 for p, r, a, m, bb, c in
                                 zip(b.price_abs, b.rent, b.area, b.has_mgr,
                                     b.built, b.county)]))
        if got is None:
            break
        if got > base:
            lo = v
        else:
            hi = v
    return {"district": td, "city": L.COUNTIES[tc], "gross": round(float(top), 3),
            "median_district": round(mid, 3),
            "breakeven_vacancy_pct": round((lo + hi) / 2, 1),
            "default_vacancy_pct": DEFAULT_VACANCY_PCT,
            "note_zh": "村里／鄉鎮市區層級的低度使用住宅統計自民國109年起停止產製，"
                       "現行僅有縣市層級且為PDF，故無法逐區帶入真實空置率。",
            "note_en": "District-level low-use-housing statistics have not been produced "
                       "since ROC 109; the current series is county-level PDF only, so a "
                       "real per-district vacancy rate cannot be wired in."}


# ── the vacancy prior ─────────────────────────────────────────────────────
#
# DEFAULT_VACANCY_PCT is the softest number on the page: 5%, an assumption with
# no source, charged identically to a two-year-old tower in 臺北市 and a
# forty-year-old walk-up in 臺東縣. Taiwan publishes no rental-vacancy
# statistic, so the LEVEL cannot be sourced — but the SHAPE can, and the shape
# is where a flat rate does its damage: every cross-section on this page is
# computed with the same vacancy charged to buildings whose void risk is not
# the same.
#
# The published quantity that varies across the same cells is 低度使用(用電)
# 住宅 — dwellings drawing almost no electricity. It is NOT rental vacancy:
# its numerator counts second homes, homes for sale and homes between owners,
# and its denominator is every dwelling on the house-tax roll, not the rented
# ones. So this block does not swap it in. It does three separable things:
#
#   MEASURE the composition gap. 內政部's 表2-3-2 gives the rate for every
#           county CROSSED WITH seven age bands — a joint table, so no
#           independence assumption is needed. Reweighted to the matched set's
#           own county-and-age mix it answers the question the flat 5% cannot:
#           are the buildings this site can see emptier than the stock, or not?
#   SHAPE   each building's vacancy scaled by its cell's rate over the matched
#           set's mean, so the level is still the site's assumption and only
#           the relative structure is measured.
#   BOUND   charging the cell rate outright, published because a reader is
#           entitled to ask what happens if the empty-home rate is taken
#           literally. It is the pessimistic end and it is labelled as the
#           wrong construct, not as a better estimate.
VAC_PRIOR_BOOT = 400
VAC_PRIOR_SEED = 41
VAC_PRIMARY_PERIOD = "111H1"    # the archived edition the prior is computed on


def national_low_use_pct(period):
    """內政部's own published national rate for one half-year, on its own base.

    H1 pairs with the Q2 roll and H2 with Q4, the same rule low_use_rates uses.
    """
    import fetch_moi as M
    lu = M.load_html_series("low_use")
    hs = M.load_series("resi_tax_roll")
    if lu.empty or hs.empty:
        return None
    q = period[:3] + ("Q2" if period.endswith("H1") else "Q4")
    n = lu[(lu.period == period) & (lu.county == "全國")]
    d = hs[(hs.period == q) & (hs.county == "全國") & (hs.district == "")]
    if n.empty or d.empty or not float(d.value.iloc[0]):
        return None
    return round(float(n.value.iloc[0]) / float(d.value.iloc[0]) * 100, 2)


def _age_joint(period):
    """{county_code or 'all': {band: rate_pct}} for one archived edition."""
    import fetch_moi as M
    df = M.load_low_use_age()
    if df.empty:
        return {}, M
    df = df[df.period == period]
    if df.empty:
        return {}, M
    name_to_code = {v: k for k, v in L.COUNTIES.items()}
    out = {}
    for _, r in df.iterrows():
        k = "all" if r.county == "全國" else name_to_code.get(r.county)
        if k is None:
            continue
        out.setdefault(k, {})[r.band] = float(r.rate_pct)
    return out, M


def _vac_rates(b, joint, M, overall=None):
    """The cell rate for every building, and how many needed a fallback.

    A building's age is taken at the window's end (115 - built), the same clock
    every other age on this page runs on, and the band profile is read as a
    profile OF AGE rather than of a cohort — which is an assumption, and is why
    the block publishes the other archived edition beside it.

    Two fallbacks, both counted rather than hidden: a county the archived table
    does not carry falls back to that band's national rate, and a building with
    no 建築完成年月 (30 of 9,805) has no band at all and falls back to the
    period's national OVERALL rate — which is a shape multiplier of roughly 1,
    i.e. that building is charged the site's flat assumption and contributes
    nothing to the finding either way.
    """
    nat = joint.get("all", {})
    rates, fell = [], 0
    for county, built in zip(b.county, b.built):
        band = M.age_band(None if pd.isna(built) else 115.0 - float(built))
        if band is None:
            rates.append(overall)
            fell += 1
            continue
        cell = joint.get(county, {})
        v = cell.get(band)
        if v is None:
            v = nat.get(band)
            fell += 1
        rates.append(v)
    return rates, fell


def vacancy_prior_block(b, primary=VAC_PRIMARY_PERIOD):
    """What the empty-home statistic says about the page's 5% guess."""
    if b is None or b.empty:
        return {}, {}
    joint, M = _age_joint(primary)
    if not joint or "all" not in joint:
        return {}, {}
    nat_primary = national_low_use_pct(primary)
    rates, fell = _vac_rates(b, joint, M, overall=nat_primary)
    if any(r is None for r in rates):
        return {}, {}

    mean_rate = float(np.mean(rates))
    # Rounded HERE, not at emission. The payload ships `vs` at 4dp, so anything
    # computed from the unrounded multipliers is a number no reader can
    # reproduce from the published file -- the shaped case was 1.7277 in the
    # payload and 1.7275 when recomputed from it, which is small and is exactly
    # the kind of gap this site exists to not have.
    shape = [round(r / mean_rate, 4) for r in rates]
    keys = list(zip(b.county, b.k))

    def nets(vec):
        return median(pd.Series([
            net_yield(p, ar, ap, hm, ag, c, vacancy_pct=v)
            for p, ar, ap, hm, ag, c, v in zip(
                b.price_abs, b.annual_rent, b.area, b.has_mgr, b.age, b.county, vec)]))

    flat_v = [DEFAULT_VACANCY_PCT] * len(b)
    shape_v = [DEFAULT_VACANCY_PCT * s for s in shape]
    level_v = list(rates)
    cases = []
    for key, zh, en, vec in (
            ("flat",  "每棟都是 5%（本站 headline）", "a flat 5% for every building (the headline)", flat_v),
            ("shape", "5% 的水準，低度使用的形狀", "the 5% level, shaped by the low-use rate", shape_v),
            ("level", "直接把低度使用率當空置率", "charging the low-use rate outright", level_v)):
        cases.append({"key": key, "zh": zh, "en": en, "net": nets(vec),
                      "vacancy_mean_pct": round(float(np.mean(vec)), 3),
                      "vacancy_min_pct": round(float(np.min(vec)), 3),
                      "vacancy_max_pct": round(float(np.max(vec)), 3)})
    base = cases[0]["net"]
    for c in cases:
        c["delta_pp"] = round((c["net"] or 0) - (base or 0), 4)

    # what each case does to the comparison the page actually rests on
    tg = []
    for key, vec in (("flat", flat_v), ("shape", shape_v), ("level", level_v)):
        by = {}
        for t, p, ar, ap, hm, ag, c, v in zip(
                b.bldg_type, b.price_abs, b.annual_rent, b.area, b.has_mgr,
                b.age, b.county, vec):
            by.setdefault(t, []).append(net_yield(p, ar, ap, hm, ag, c, vacancy_pct=v))
        tw, wu = median(pd.Series(by.get("住宅大樓", []))), median(pd.Series(by.get("公寓", [])))
        tg.append({"case": key, "tower": tw, "walkup": wu,
                   "gap_pp": None if (tw is None or wu is None) else round(wu - tw, 4)})

    rng = np.random.default_rng(VAC_PRIOR_SEED)
    arr = np.asarray(rates, dtype=float)
    draws = sorted(float(arr[rng.integers(0, len(arr), len(arr))].mean())
                   for _ in range(VAC_PRIOR_BOOT))
    ci = [round(draws[int(0.025 * len(draws))], 3),
          round(draws[int(0.975 * len(draws)) - 1], 3)]

    # the age profile itself, and the matched set's mix against the stock's
    st = _stock_age_mix(M)
    cnt = {}
    for county, built in zip(b.county, b.built):
        band = M.age_band(None if pd.isna(built) else 115.0 - float(built))
        cnt[band] = cnt.get(band, 0) + 1
    profile = [{"band": bd, "rate_pct": round(joint["all"][bd], 2),
                "matched_share_pct": round(100.0 * cnt.get(bd, 0) / len(b), 2),
                "stock_share_pct": st.get(bd)}
               for bd in M.AGE_BANDS if bd in joint["all"]]

    # the second leg, published because it points the OTHER way
    county_leg = _county_only_leg(b, M)
    # the other archived edition, as a stability check on the profile
    alt = _alt_edition(b, M, primary)

    return {
        "period": primary,
        "national_pct": nat_primary,
        "prior_pct": round(mean_rate, 3),
        "prior_ci": ci, "n_boot": VAC_PRIOR_BOOT,
        "gap_pp": None if nat_primary is None else round(mean_rate - nat_primary, 3),
        "fellback_to_national": int(fell),
        "site_default_pct": DEFAULT_VACANCY_PCT,
        "bands": M.AGE_BANDS,
        "profile": profile,
        "county_leg": county_leg,
        "stability": alt,
        "cases": cases,
        "type_gap": tg,
        "headline_case": "flat",
        "source_zh": "內政部 表2-3-2 低度使用(用電)住宅半年報表-按屋齡分（縣市×屋齡交叉表）",
        "source_en": "內政部 Table 2-3-2, low-use dwellings by county CROSSED WITH age band",
        "construct_zh": "低度使用(用電)住宅的分子含二屋、待售屋、換手空檔，分母是全部房屋稅籍住宅，"
                        "不是出租中的住宅。它不是租賃空置率，本站不把它換進 headline。",
        "construct_en": "The low-use numerator counts second homes, homes for sale and homes "
                        "between owners, and its denominator is every dwelling on the house-tax "
                        "roll, not the rented ones. It is not rental vacancy and this site does "
                        "not swap it into the headline.",
        "period_zh": "屋齡交叉表只有民國111年上、下半年存於網頁典藏；本節所用的全 22 縣市序列"
                     "（經濟部能源署轉載內政部上半年數字）最新為114年上半年。內政部自己那份只含"
                     "全國與六都、但有下半年的序列（最新 114H2）印在下面的官方數字那一節，兩者"
                     "不是同一個檔，也不相乘。",
        "period_en": "Only the 111H1 and 111H2 editions of the age cross-table are archived. The "
                     "all-22-county series this section uses (經濟部能源署's mirror of 內政部's "
                     "first-half figures) runs to 114H1; 內政部's own series, which covers 全國 "
                     "and the six municipalities but does carry second halves, runs to 114H2 and "
                     "is the one printed in the official-figures section below. They are different "
                     "files, and the legs are never multiplied together.",
    }, {k: float(x) for k, x in zip(keys, shape)}


def _stock_age_mix(M):
    """The house-tax roll's own age mix, folded onto the table's seven bands."""
    try:
        st = M.load_theme_series("stock_by_age")
    except Exception:                           # noqa: BLE001 - optional series
        return {}
    if st.empty:
        return {}
    st = st[(st.county == "全國") & (st.district == "") & (st.kind != "") & (st.kind != "mean")]
    if st.empty:
        return {}
    per = sorted(st.period.unique())[-1]
    st = st[st.period == per]
    fold = {"1（含）年以下": "<=5", "1~5（含）年": "<=5", "5~10（含）年": "5-10",
            "10~15（含）年": "10-20", "15~20（含）年": "10-20", "20~25（含）年": "20-30",
            "25~30（含）年": "20-30", "30~40（含）年": "30-40", "40~50（含）年": "40-50",
            "50年以上": "50+"}
    acc, tot = {}, 0.0
    for _, r in st.iterrows():
        band = fold.get(str(r.kind).strip())
        if band is None or pd.isna(r.value):
            continue
        acc[band] = acc.get(band, 0.0) + float(r.value)
        tot += float(r.value)
    return {k: round(100.0 * v / tot, 2) for k, v in acc.items()} if tot else {}


def _county_only_leg(b, M):
    """The county series at its own latest period, all 22 counties.

    Published beside the joint because it points the OTHER way, and the reader
    should see which leg does the work.
    """
    df = M.load_low_use_22()
    if df.empty:
        return {}
    per = sorted(df.period.unique())[-1]
    df = df[df.period == per]
    hs = M.load_series("resi_tax_roll")
    # the same half-year rule the rest of the file uses (H1 -> Q2, H2 -> Q4).
    # The mirror only ever carries H1 today, but hard-coding Q2 would pair a
    # future H2 numerator with the wrong roll and produce a rate silently.
    q = per[:3] + ("Q2" if per.endswith("H1") else "Q4")
    hq = hs[(hs.period == q) & (hs.district == "")]
    name_to_code = {v: k for k, v in L.COUNTIES.items()}
    rates = {}
    for _, r in df.iterrows():
        stock = hq[hq.county == r.county]
        code = name_to_code.get(r.county)
        if code is None or stock.empty or not float(stock.value.iloc[0]):
            continue
        rates[code] = round(float(r.low_use) / float(stock.value.iloc[0]) * 100, 2)
    if not rates:
        return {}
    nat = national_low_use_pct(per)
    vals = [rates.get(c) for c in b.county]
    covered = sum(1 for v in vals if v is not None)
    vals = [v if v is not None else nat for v in vals]
    cnt = {}
    for c in b.county:
        cnt[c] = cnt.get(c, 0) + 1
    return {
        "period": per, "national_pct": nat,
        "prior_pct": round(float(np.mean(vals)), 3),
        "gap_pp": None if nat is None else round(float(np.mean(vals)) - nat, 3),
        "covered_pct": round(100.0 * covered / len(b), 2),
        "counties": len(rates),
        "rows": sorted(({"county": c, "rate_pct": v,
                         "matched": int(cnt.get(c, 0)),
                         "matched_share_pct": round(100.0 * cnt.get(c, 0) / len(b), 2)}
                        for c, v in rates.items() if cnt.get(c)),
                       key=lambda r: -r["rate_pct"]),
    }


def _alt_edition(b, M, primary):
    """The other archived half-year, as a stability check on the age profile."""
    other = [p for p in M.LOW_USE_AGE if p != primary]
    if not other:
        return {}
    per = other[0]
    joint, _ = _age_joint(per)
    if not joint or "all" not in joint:
        return {}
    nat = national_low_use_pct(per)
    rates, _fell = _vac_rates(b, joint, M, overall=nat)
    if any(r is None for r in rates):
        return {}
    mean_rate = float(np.mean(rates))
    return {"period": per, "prior_pct": round(mean_rate, 3), "national_pct": nat,
            "gap_pp": None if nat is None else round(mean_rate - nat, 3)}


# ═══════════════════════════════════════════════════════════ ASSEMBLY ════
# build() used to be one 120-line procedure. It is split here so each block is
# independently testable and so the payload's shape is readable at a glance.

def source_manifest(seasons, cache_dir=None):
    """A hash of the exact bytes this build read.

    The site's whole argument is "check my denominator", and that is not
    checkable unless the inputs are pinned: 實價登錄 gains a season every
    quarter and silently revises nothing, so two people running this pipeline
    three months apart get different numbers for reasons that have nothing to do
    with the code. This is the fixed point they can compare against.

    Hashed per season zip and then over the ordered list of those digests, so a
    single missing or newer season changes the combined hash and is identifiable
    from the per-file list rather than only visible as a mismatch.
    """
    import hashlib
    cache_dir = cache_dir or L.CACHE
    files, h = [], hashlib.sha256()
    for s in seasons:
        path = os.path.join(cache_dir, f"{s}.zip")
        if not os.path.exists(path):
            files.append({"season": s, "sha256": None, "bytes": 0})
            continue
        d = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                d.update(chunk)
        dig = d.hexdigest()
        files.append({"season": s, "sha256": dig,
                      "bytes": int(os.path.getsize(path))})
        h.update(dig.encode())
    return {"files": files, "sha256": h.hexdigest()}


REF_DIRS = ("data/ref/moi", "data/ref/cbc")
REF_EXTRA = ("data/ref/dgbas_income.csv",)
# The 金拍 session cache: 436 JSON files under data/fasc/ that the auction block
# publishes wholesale (items, above-reserve share, median price, per-round
# schedule) and that moi_block divides against 法拍. It was pinned by neither
# hash -- source_manifest covers the season zips and ref_manifest globs *.csv --
# so the one input on this page that is fetched from a LIVE feed was also the
# one input nobody could check. Hashed as a set: the digest of the ordered
# per-file digests, which is stable under re-reading and changes the moment a
# session is added, removed or revised.
FASC_DIR = "data/fasc"


def _fasc_digest(d=FASC_DIR):
    """One digest over the whole 金拍 session cache, or {} when it is absent.

    Per-file digests in sorted filename order, then a digest over those, so the
    result is independent of filesystem order and moves if any session's bytes
    move. Counted as one manifest entry rather than 436.
    """
    import glob
    import hashlib
    paths = sorted(glob.glob(os.path.join(d, "*.json")))
    if not paths:
        return {}
    h, total = hashlib.sha256(), 0
    for p in paths:
        with open(p, "rb") as f:
            raw = f.read()
        total += len(raw)
        h.update(hashlib.sha256(raw).hexdigest().encode())
    return {"path": d + "/*.json", "sha256": h.hexdigest(),
            "bytes": int(total), "files": len(paths),
            "note": "金拍 session cache, hashed as a set"}


def ref_manifest(ref_dirs=REF_DIRS, extra=REF_EXTRA):
    """A hash of every reference CSV this build read, beside the season hash.

    Until v1.9 only the season zips were pinned; the 內政部 and 主計總處 series
    under data/ref/ went into the payload unhashed, so a re-exported official
    series (the platform revises history) would have changed the numbers with
    nothing in provenance to say why. This is the second fixed point.

    Kept as a SIBLING of `source`, not folded into it, so a refs-only mismatch
    (an official series re-exported) reads differently from a source mismatch
    (a new season), and 1.8 and 1.9 source snapshots stay comparable. Keyed by
    repo-relative path, since basenames can collide across directories. Where a
    directory carries a MANIFEST.json (fetch_cbc writes one), its url and fetch
    date ride along -- read from that file, never regenerated, or the payload
    would change on every rebuild.
    """
    import glob
    import hashlib
    import json
    paths = []
    for d in ref_dirs:
        paths += sorted(glob.glob(os.path.join(d, "*.csv")))
    paths += [p for p in extra if os.path.exists(p)]
    files, h = [], hashlib.sha256()
    fasc = _fasc_digest()
    if fasc:
        files.append(fasc)
        h.update(fasc["sha256"].encode())
    for path in paths:
        man = {}
        mp = os.path.join(os.path.dirname(path), "MANIFEST.json")
        if os.path.exists(mp):
            with open(mp, encoding="utf-8") as f:
                man = json.load(f).get(os.path.basename(path), {})
        with open(path, "rb") as f:
            dig = hashlib.sha256(f.read()).hexdigest()
        entry = {"path": path, "sha256": dig, "bytes": int(os.path.getsize(path))}
        if man.get("url"):
            entry["url"] = man["url"]
        if man.get("fetched"):
            entry["fetched"] = man["fetched"]
        files.append(entry)
        h.update(dig.encode())
    return {"files": files, "sha256": h.hexdigest()}


def git_commit():
    """The source tree this build ran from. None where git is unavailable.

    Marked `+dirty` when the tree has uncommitted changes, which matters more
    than it looks: this stamp is by construction the commit BEFORE the one that
    carries the resulting payload, since the payload cannot contain the hash of
    the commit that adds it. So it is informational, not the pin. The pins are
    `version` and `source.sha256`; to reproduce a specific payload, check out the
    commit whose `housing_data.json.sha256` matches it. See docs/REPRODUCING.md.
    """
    try:
        import subprocess
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=5)
        sha = out.stdout.strip()[:12]
        if not sha:
            return None
        st = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                            text=True, timeout=5)
        return sha + ("+dirty" if st.stdout.strip() else "")
    except Exception:
        return None


def load_window(last_season=LAST_SEASON):
    """Every season in the clean window, raw and cleaned. Returns 4 frames."""
    seasons = L.seasons_through(last_season)
    print(f"[uw] seasons {seasons[0]}..{seasons[-1]} ({len(seasons)})")
    raw_s, raw_r, cs, cr = [], [], [], []
    for season in seasons:
        d = L.load_season(season)
        # Parking is SUBTRACTED, not excluded.
        #
        # The old treatment dropped every transaction carrying a space — 17,222
        # buildings, the largest self-imposed loss on the site. The registry
        # itemises each space's price and area in a *_park.csv sub-file, so the
        # correction uses numbers the PARTIES stated rather than a model of what
        # a space is worth, and only rows the registry failed to itemise are
        # still dropped.
        #
        # The LEASE-side keep rested on an assumption (zero = no extra rent)
        # that v2.0 tested within building and found false. From v2.1 build()
        # subtracts an imputed space rent after keying (impute_parking_rent);
        # `parking_audit` keeps the old treatment as a published bound.
        #
        # Validated the way everything else here is validated — within a
        # building. Across the sample a parking-subtracted sale prices 13.7%
        # higher per 坪 than one that never had a space; inside a single
        # building, across 8,316 that sold both ways, the gap is -0.7%
        # (quartiles -7.2% to +3.4%). So the cross-sample gap is composition —
        # flats with a space sit in dearer buildings — and not arithmetic left
        # in the price. 6,043 buildings -> 10,148, headline 2.91% -> 2.71%.
        if d["sale"] is not None:
            raw_s.append(d["sale"])
            cs.append(L.clean_sales(d["sale"], subtract_parking=True))
        if d["rent"] is not None:
            raw_r.append(d["rent"])
            cr.append(L.clean_rents(d["rent"], subtract_parking=True))
    return (seasons,
            pd.concat(raw_s, ignore_index=True), pd.concat(raw_r, ignore_index=True),
            pd.concat(cs, ignore_index=True), pd.concat(cr, ignore_index=True))


def key_frames(sales, rents):
    """Attach the building key. Reports how many records have no 門牌 at all —
    a number that must be published, because the normaliser's measured recall is
    only ever measured on addresses that HAVE a 號."""
    for d in (sales, rents):
        d["k"] = d["土地位置建物門牌"].map(addr_key)
        d["district"] = _tw(d["鄉鎮市區"])
    sales["bldg_type"] = sales["建物型態"].map(TYPE_SHORT)
    stats = {
        "sale_no_key": int((sales.k == "").sum()),
        "rent_no_key": int((rents.k == "").sum()),
        "sale_total": int(len(sales)),
        "rent_total": int(len(rents)),
    }
    stats["no_key_pct"] = round(
        (stats["sale_no_key"] + stats["rent_no_key"]) /
        max(1, stats["sale_total"] + stats["rent_total"]) * 100, 2)
    return sales[sales.k != ""], rents[rents.k != ""], stats


def coverage_block(sales, b):
    """The finding: which buildings can be measured at all.

    `sales` must be the UNIVERSE frame (universe_buildings), not the cleaned
    sales. It used to be the cleaned frame, which had already dropped buildings
    whose only sales carried unitemised parking or were related-party -- so the
    per-type match rates sat on 110,942 buildings while the hero's 6.22% sat on
    157,594, and 46,652 buildings in the headline denominator were never named
    anywhere. A cold reader summed the pie and caught it.
    """
    all_bldg = sales.groupby("bldg_type")["k"].nunique()
    matched = b.groupby("bldg_type").size()
    out = []
    for t in TYPE_SHORT.values():
        tot, mat = int(all_bldg.get(t, 0)), int(matched.get(t, 0))
        out.append({
            "type": t, "all_buildings": tot, "matched": mat,
            "match_rate": round(mat / tot * 100, 2) if tot else 0.0,
            "share_all": round(tot / max(1, int(all_bldg.sum())) * 100, 1),
            "share_matched": round(mat / max(1, int(matched.sum())) * 100, 1),
            "yield": median(b[b.bldg_type == t].gross),
            "net": median(b[b.bldg_type == t].net),
        })
    # The rate published before v2.2, when the numerator was typed on the
    # matched pairs and the denominator on every sale. Six buildings moved;
    # corrections accrete, so the superseded figure stays visible.
    for r in out:
        r["match_rate_pre_v22"] = {"公寓": 1.55, "華廈": 4.68, "住宅大樓": 10.93}.get(r["type"])
    return out


def age_block(sales, b):
    """Matched vs unmatched, on the three variables a critic asks about.

    Price per 坪 matters most: it is the yield's denominator, so a difference
    there biases the headline mechanically, in a direction we can state.

    `sales` must be the UNIVERSE row frame (universe_buildings(..., with_rows=
    True)), not the cleaned one: "unmatched" has to mean every building with a
    sale that this site cannot price, which is what the rest of the page counts.
    There used to be an unused `ub=None` parameter here that made the wrong call
    look considered; it is gone so the frame is the caller's only choice.
    """
    sale_b = sales.groupby("k").agg(built=("built_roc_y", "median"),
                                    area=("area_ping", "median"),
                                    price=("price", "median"))
    sale_b["ppp"] = sale_b.price / sale_b.area
    sale_b["matched"] = sale_b.index.isin(set(b.k))
    m, u = sale_b[sale_b.matched], sale_b[~sale_b.matched]
    extra = {
        "matched_ppp": median(m.ppp), "unmatched_ppp": median(u.ppp),
        "ppp_diff_pct": (round((median(m.ppp) / median(u.ppp) - 1) * 100, 1)
                         if median(u.ppp) else None),
    }
    return dict(extra, **{
        "matched_built": median(sale_b[sale_b.matched].built),
        "unmatched_built": median(sale_b[~sale_b.matched].built),
        "matched_area": median(sale_b[sale_b.matched].area),
        "unmatched_area": median(sale_b[~sale_b.matched].area),
        "matched_n": int(sale_b.matched.sum()),
        "unmatched_n": int((~sale_b.matched).sum()),
    })


def gap_ci(b, type_a, type_b, col, n=400, seed=23):
    """95% CI on the difference of two building-level medians.

    Buildings are the unit and they are already one row each, so this is a plain
    cluster bootstrap: resample each type's buildings independently and take the
    difference of the resampled medians.
    """
    a = b[b.bldg_type == type_a][col].dropna().values
    c = b[b.bldg_type == type_b][col].dropna().values
    if len(a) < 25 or len(c) < 25:
        return (None, None)
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for i in range(n):
        out[i] = (np.median(a[rng.integers(0, len(a), len(a))])
                  - np.median(c[rng.integers(0, len(c), len(c))]))
    lo, hi = np.percentile(out, [2.5, 97.5])
    return (round(float(lo), 3), round(float(hi), 3))


def dead_hypothesis_block(b):
    """The prediction this project set out to test, and its result.

    It is on the page because a finding that arrives AFTER the planned one dies
    is worth less if the death is hidden. Walk-ups were predicted to out-yield
    towers once management fees were netted off.

    The verdict used to be the hard-coded string "dead". It was true when the
    site covered two cities -- the gross gap was 0.041pp, a rounding error, so
    the apparent net gap was an artefact of the cost model rather than a fact
    about buildings. It was never re-evaluated when the scope went national, and
    on national data it is FALSE: the gross gap is an order of magnitude larger
    and it WIDENS after costs instead of collapsing.

    So the verdict is now derived, with an interval, and it says whatever the
    data says. A conclusion that cannot change when the data changes is not a
    conclusion.
    """
    rows = []
    for t in TYPE_SHORT.values():
        sub = b[b.bldg_type == t]
        rows.append({"type": t, "n": int(len(sub)),
                     "gross": median(sub.gross), "net": median(sub.net)})
    mgr = []
    for flag, label in ((1, "有管理員"), (0, "無管理員")):
        sub = b[b.has_mgr == flag]
        mgr.append({"flag": label, "n": int(len(sub)),
                    "gross": median(sub.gross), "net": median(sub.net)})
    walk = [r for r in rows if r["type"] == "公寓"][0]
    tower = [r for r in rows if r["type"] == "住宅大樓"][0]
    g_lo, g_hi = gap_ci(b, "公寓", "住宅大樓", "gross")
    n_lo, n_hi = gap_ci(b, "公寓", "住宅大樓", "net")
    gross_gap = round((walk["gross"] or 0) - (tower["gross"] or 0), 3)
    net_gap = round((walk["net"] or 0) - (tower["net"] or 0), 3)
    # The original kill criterion, applied to whatever data is in front of it:
    # the hypothesis dies if the gap is absent BEFORE costs, because then the
    # net gap can only have come from the cost model.
    if g_lo is None:
        verdict = "untested"
    elif g_lo > 0:
        verdict = "alive"           # gap present at gross, before any modelling
    elif g_hi < 0:
        verdict = "reversed"        # towers out-yield walk-ups at gross
    else:
        verdict = "dead"            # gross gap indistinguishable from zero
    return {
        "by_type": rows, "by_manager": mgr,
        "gross_gap": gross_gap, "net_gap": net_gap,
        "gross_ci": {"lo": g_lo, "hi": g_hi},
        "net_ci": {"lo": n_lo, "hi": n_hi},
        # How much of the net gap the cost model contributes. Only meaningful
        # when the gross gap is real; it was the whole story when it was not.
        "cost_share_pct": (round((1 - gross_gap / net_gap) * 100, 1)
                           if net_gap else None),
        "verdict": verdict,
    }


# 中央銀行「五大銀行（台銀、合庫銀、土銀、華銀及一銀）新承做購屋貸款」加權平均
# 利率. This is a REFERENCE number, published by someone else, carried here so
# the net yield can be read against something. It is not modelled and not a
# slider: it is quoted, with its source and its month, and it goes stale — check
# https://www.cbc.gov.tw/tw/lp-528-1.html before trusting the date below.
MORTGAGE_RATE = {
    "rate": 2.322,
    "period_zh": "115年5月",
    "period_en": "May 2026",
    "src_zh": "中央銀行「五大銀行新承做購屋貸款」加權平均利率",
    "src_en": "Central Bank of the ROC, weighted average rate on new house-purchase "
              "lending by the five major banks",
    "url": "https://www.cbc.gov.tw/tw/lp-528-1.html",
}


# ── the walk-up hypothesis, settled ──────────────────────────────────────────

WALK_MIN_N = 200            # matched walk-up buildings below which nothing is decided
WALK_BOOT_N = 2000
WALK_SEED = 23
WALK_MDD_Z = 1.96
WALK_SIGN_SHARE = 0.80      # a binding control family must agree in sign this often
WALK_CTRL_MIN_COVER = 0.50  # ...and cover this share of matched walk-ups to bind
WALK_SEL_TOL_PCT = 10.0     # matched vs unmatched median tolerance, per variable
WALK_JOINT_MIN_N = 25       # buildings per district x age-band cell
WALK_JOINT_MIN_CELLS = 3    # cells needed to attribute the gap to type over age
WALK_MECH_MIN_CELL = 25     # buildings per type x has_mgr cell

WALK_A, WALK_B = "公寓", "住宅大樓"


def _walk_gap_ci(pairs, a, b_, col, n, rng):
    """Two-stage CI on the DIFFERENCE of two building-level medians: buildings
    resampled, then pairs within building, exactly as two_stage_ci does, but
    carried through to a gap so the interval belongs to the thing published."""
    ga = {k: g[col].values for k, g in pairs[pairs.bldg_type == a].groupby(["county", "k"])}
    gb = {k: g[col].values for k, g in pairs[pairs.bldg_type == b_].groupby(["county", "k"])}
    ka, kb = list(ga), list(gb)
    if len(ka) < 5 or len(kb) < 5:
        return (None, None, None)
    out = np.empty(n)
    for i in range(n):
        ma = [np.median(ga[ka[j]][rng.integers(0, len(ga[ka[j]]), len(ga[ka[j]]))]) if len(ga[ka[j]]) > 1
              else ga[ka[j]][0] for j in rng.integers(0, len(ka), len(ka))]
        mb = [np.median(gb[kb[j]][rng.integers(0, len(gb[kb[j]]), len(gb[kb[j]]))]) if len(gb[kb[j]]) > 1
              else gb[kb[j]][0] for j in rng.integers(0, len(kb), len(kb))]
        out[i] = np.median(ma) - np.median(mb)
    lo, hi = np.percentile(out, [2.5, 97.5])
    return (round(float(lo), 3), round(float(hi), 3), round(float(out.std(ddof=1)), 4))


def _walk_cells(frame, keys, col="gross", min_n=25):
    """Median gap per cell, and how many matched walk-ups the qualifying cells
    hold. A control that covers a tenth of the sample is not a control."""
    rows, covered = [], 0
    for _, g in frame.groupby(keys):
        ga, gb = g[g.bldg_type == WALK_A], g[g.bldg_type == WALK_B]
        if len(ga) >= min_n and len(gb) >= min_n:
            rows.append(float(ga[col].median() - gb[col].median()))
            covered += int(len(ga))
    if not rows:
        return {"cells": 0, "walkups_covered": 0, "median_gap": None,
                "same_sign": 0, "same_sign_pct": None}
    pos = sum(1 for r in rows if r > 0)
    return {"cells": len(rows), "walkups_covered": covered,
            "median_gap": round(float(np.median(rows)), 3),
            "same_sign": int(max(pos, len(rows) - pos)),
            "same_sign_pct": round(max(pos, len(rows) - pos) / len(rows) * 100, 1)}


def _walk_bands(age):
    if age is None or age != age:
        return None
    for hi, lab in ((20, "<20"), (30, "20-30"), (40, "30-40"), (50, "40-50")):
        if age <= hi:
            return lab
    return "50+"


def walkup_resolution_block(b, ub, uni_rows, pairs, rents=None,
                            n_boot=WALK_BOOT_N, seed=WALK_SEED):
    """The project's founding hypothesis, settled -- one half of it.

    The prediction was that walk-ups out-yield towers once management fees are
    netted off. That is two questions. WHICH yields more, this data answers:
    walk-ups do, and the sign survives every control that covers a majority of
    the sample. WHY, it cannot: the mechanism the hypothesis named is
    falsified (the gap is undiminished in buildings with no manager at all, so
    it does not need the fee), and what remains -- being a walk-up versus being
    forty-five years old -- cannot be separated, because at 1.5% matchability
    there is no district x age cell with enough of both types in it.

    So this block publishes two verdicts, not one, each by a stated rule over
    fields it prints. The rule is NOT pre-registered: the raw gap was already
    known when it was written, and saying otherwise would repeat the mistake
    v2.0 caught in the parking audit.

    Units are kept apart: 棟 for buildings, 筆 for records, 宅 for the
    house-tax stock. They sit side by side and are never divided across.
    """
    if b is None or b.empty or pairs is None or pairs.empty:
        return {}
    rng = np.random.default_rng(seed)
    W = b[b.bldg_type == WALK_A]
    T = b[b.bldg_type == WALK_B]
    if len(W) == 0 or len(T) == 0:
        return {}

    # ── 1. coverage, three units side by side ──
    ub_w = ub[ub.bldg_type == WALK_A]
    rows_w = uni_rows[uni_rows["建物型態"].map(TYPE_SHORT) == WALK_A] if uni_rows is not None else None
    matched_keys = set(zip(b.county, b.k))
    stock_4_5, stock_tot = None, None
    try:
        import fetch_moi as M
        sf = M.load_theme_series("stock_by_floor")
        sf = sf[(sf.county == "全國") & (sf.district == "") & (sf.period == "115Q2")]
        stock_4_5 = int(sf[sf.kind.str.startswith("4~5")].value.iloc[0])
        stock_tot = int(sf[sf.kind == ""].value.iloc[0])
    except Exception:
        pass
    pw = pairs[pairs.bldg_type == WALK_A]
    pt = pairs[pairs.bldg_type == WALK_B]
    coverage = {
        "matched_bldg": int(len(W)), "site_bldg": int(len(b)),
        "matched_share_of_site_pct": round(len(W) / len(b) * 100, 2),
        "universe_bldg": int(len(ub_w)),
        "match_rate_pct": round(len(W) / max(1, len(ub_w)) * 100, 2),
        "sale_rows": int(len(rows_w)) if rows_w is not None else None,
        "sale_rows_in_matched_bldg": (int(sum(1 for k in zip(rows_w.county, rows_w.k) if k in matched_keys))
                                      if rows_w is not None else None),
        "sale_rows_all_types": int(len(uni_rows)) if uni_rows is not None else None,
        "pairs": int(len(pw)), "pairs_all_types": int(len(pairs)),
        "pairs_per_bldg_median": float(pw.groupby(["county", "k"]).size().median()),
        "tower_pairs_per_bldg_median": float(pt.groupby(["county", "k"]).size().median()),
        "stock_4_5f_dwellings": stock_4_5, "stock_total_dwellings": stock_tot,
        "stock_4_5f_share_pct": (round(stock_4_5 / stock_tot * 100, 1)
                                 if stock_4_5 and stock_tot else None),
        "stock_period": "115Q2", "stock_unit": "宅",
    }

    # ── 2. representativeness, BOTH types: matched vs sold-but-unmatched ──
    def _rep(t):
        u = ub[ub.bldg_type == t].copy()
        u["matched"] = [k in matched_keys for k in zip(u.county, u.k)]
        m_, x_ = u[u.matched], u[~u.matched]
        if not len(m_) or not len(x_):
            return None
        med = {}
        for col, key in (("built", "built"), ("area", "area_ping"), ("ppp", "ppp")):
            a, c = float(m_[col].median()), float(x_[col].median())
            med[key] = {"m": round(a, 2), "u": round(c, 2),
                        "diff_pct": round((a - c) / c * 100, 1) if c else None}
        by_county = []
        for c_, g in u.groupby("county"):
            if len(g) >= 200:
                by_county.append({"county": c_, "m_pct": round(g.matched.mean() * 100, 2),
                                  "n": int(len(g))})
        by_county.sort(key=lambda r: -r["m_pct"])
        return {"type": t, "matched_n": int(len(m_)), "unmatched_n": int(len(x_)),
                "medians": med, "max_abs_diff_pct": max(abs(v["diff_pct"] or 0) for v in med.values()),
                "by_county": by_county[:3] + by_county[-3:] if len(by_county) > 6 else by_county}
    rep = [r for r in (_rep(WALK_A), _rep(WALK_B)) if r]

    # ── 3. precision: can this sample see the gap it reports? ──
    gross_gap = round(float(W.gross.median() - T.gross.median()), 3)
    net_gap = round(float(W.net.median() - T.net.median()), 3)
    glo, ghi, gse = _walk_gap_ci(pairs, WALK_A, WALK_B, "gross", n_boot, rng)
    precision = {
        "gross_gap": gross_gap, "lo": glo, "hi": ghi, "se": gse,
        "mdd_95": round(WALK_MDD_Z * gse, 3) if gse else None,
        "ratio_obs_to_mdd": round(abs(gross_gap) / (WALK_MDD_Z * gse), 1) if gse else None,
        "net_gap": net_gap, "n_boot": n_boot, "seed": seed,
        "method": "two-stage: buildings, then pairs within building",
    }

    # ── 4. controls ──
    bb = b.copy()
    bb["age_band"] = (115.0 - bb.built).map(_walk_bands)
    bb["size_band"] = pd.cut(bb.area, [0, 20, 30, 40, 1e9], labels=["<20", "20-30", "30-40", "40+"])
    bb["ppp_dec"] = pd.qcut(bb.price_ping, 10, labels=False, duplicates="drop")
    pair_bb = bb[bb.bldg_type.isin([WALK_A, WALK_B])]
    n_w = max(1, len(W))
    families = [
        ("price_decile", ["ppp_dec"], 25), ("county_district", ["county", "district"], 10),
        ("county", ["county"], 25), ("age_band", ["age_band"], 25),
        ("size_band", ["size_band"], 25), ("has_mgr", ["has_mgr"], 25),
        ("district_x_price_decile", ["county", "district", "ppp_dec"], 5),
        ("district_x_age_band", ["county", "district", "age_band"], WALK_JOINT_MIN_N),
    ]
    controls = []
    for name, keys, mn in families:
        r = _walk_cells(pair_bb, keys, "gross", mn)
        r["family"] = name; r["min_n"] = mn
        r["cover_pct"] = round(r["walkups_covered"] / n_w * 100, 1)
        r["binding"] = bool(r["cells"] >= 2 and r["walkups_covered"] / n_w >= WALK_CTRL_MIN_COVER)
        controls.append(r)

    # ── 5. common support: the reason the cause cannot be pinned ──
    wa, ta = (115.0 - W.built).dropna(), (115.0 - T.built).dropna()
    joint = next(c for c in controls if c["family"] == "district_x_age_band")
    joint10 = _walk_cells(pair_bb, ["county", "district", "age_band"], "gross", 10)
    lo_w, hi_w = 35, 60
    ov = pair_bb[(115.0 - pair_bb.built).between(lo_w, hi_w)]
    ov_w, ov_t = ov[ov.bldg_type == WALK_A], ov[ov.bldg_type == WALK_B]
    ov_gap = (round(float(ov_w.gross.median() - ov_t.gross.median()), 3)
              if len(ov_w) >= 25 and len(ov_t) >= 25 else None)
    ov_ci = _walk_gap_ci(pairs[(115.0 - pairs.built_roc_y).between(lo_w, hi_w)],
                         WALK_A, WALK_B, "gross", 400, rng) if ov_gap is not None else (None, None, None)
    common_support = {
        "walkup_age": {"p5": float(wa.quantile(.05)), "median": float(wa.median()), "p95": float(wa.quantile(.95))},
        "tower_age": {"p5": float(ta.quantile(.05)), "median": float(ta.median()), "p95": float(ta.quantile(.95))},
        "towers_over_40y_pct": round(float((ta > 40).mean() * 100), 1),
        "walkups_under_20y_pct": round(float((wa < 20).mean() * 100), 1),
        "joint_cells_at_min_n": joint["cells"], "joint_min_n": WALK_JOINT_MIN_N,
        "joint_cells_at_10": joint10["cells"], "joint_walkups_at_10": joint10["walkups_covered"],
        "overlap_window": {"lo": lo_w, "hi": hi_w, "n_walkup": int(len(ov_w)), "n_tower": int(len(ov_t)),
                           "gap": ov_gap, "lo_ci": ov_ci[0], "hi_ci": ov_ci[1]},
    }

    # ── 6. the mechanism the hypothesis named ──
    cells = []
    for hm in (0, 1):
        g = pair_bb[pair_bb.has_mgr == hm]
        gw, gt = g[g.bldg_type == WALK_A], g[g.bldg_type == WALK_B]
        if not len(gw) or not len(gt):
            continue
        sub = pairs[pairs.has_mgr == hm] if "has_mgr" in pairs.columns else pairs
        lo_, hi_, _ = _walk_gap_ci(sub, WALK_A, WALK_B, "gross", 400, rng)
        cells.append({"has_mgr": hm, "n_walkup": int(len(gw)), "n_tower": int(len(gt)),
                      "gross_gap": round(float(gw.gross.median() - gt.gross.median()), 3),
                      "lo": lo_, "hi": hi_,
                      "net_gap": round(float(gw.net.median() - gt.net.median()), 3)})
    c0 = next((c for c in cells if c["has_mgr"] == 0), None)
    fee_falsified = bool(
        len(cells) == 2
        and all(min(c["n_walkup"], c["n_tower"]) >= WALK_MECH_MIN_CELL for c in cells)
        and c0 and c0["lo"] is not None and c0["lo"] * c0["hi"] > 0)
    mechanism = {
        "p_mgr_walkup_pct": round(float(W.has_mgr.mean() * 100), 1),
        "p_mgr_tower_pct": round(float(T.has_mgr.mean() * 100), 1),
        "cells": cells, "min_cell": WALK_MECH_MIN_CELL,
        "fee_verdict": "falsified" if fee_falsified else "not_falsified",
        "fee_rule": ("falsified iff both type x has_mgr strata hold at least min_cell buildings of "
                     "each type AND the gap's interval in the no-manager stratum excludes zero"),
    }

    # ── 7. reweight each type to its own sold population ──
    ubb = ub.copy()
    ubb["ppp_ter"] = pd.qcut(ubb.ppp, 3, labels=False, duplicates="drop")
    bb2 = bb.copy()
    tgt = ubb.groupby(["bldg_type", "county", "ppp_ter"]).size()
    bb2["ppp_ter"] = [None] * len(bb2)
    edges = ubb.ppp.quantile([1/3, 2/3]).values
    bb2["ppp_ter"] = np.digitize(bb2.price_ping, edges)
    rw = {}
    for t in (WALK_A, WALK_B):
        g = bb2[bb2.bldg_type == t]
        cur = g.groupby(["county", "ppp_ter"]).gross.median()
        wts = tgt.loc[t] if t in tgt.index.get_level_values(0) else None
        if wts is None or cur.empty:
            continue
        common = cur.index.intersection(wts.index)
        if not len(common):
            continue
        w = wts.loc[common].astype(float)
        rw[t] = round(float((cur.loc[common] * w).sum() / w.sum()), 3)
        rw[t + "_cover_pct"] = round(float(w.sum() / wts.sum() * 100), 1)
    reweighted = {"target": "county x price tercile of the same type's sold population",
                  "walkup": rw.get(WALK_A), "tower": rw.get(WALK_B),
                  "gap": (round(rw[WALK_A] - rw[WALK_B], 3)
                          if rw.get(WALK_A) is not None and rw.get(WALK_B) is not None else None),
                  "raw_gap": gross_gap,
                  "walkup_cover_pct": rw.get(WALK_A + "_cover_pct"),
                  "tower_cover_pct": rw.get(WALK_B + "_cover_pct")}

    # ── 8. the two verdicts, each by a rule over fields printed above ──
    binding = [c for c in controls if c["binding"]]
    sel_bad = any((r["max_abs_diff_pct"] or 0) > WALK_SEL_TOL_PCT for r in rep)
    flipped = (reweighted["gap"] is not None and gross_gap != 0
               and reweighted["gap"] * gross_gap < 0)
    if len(W) < WALK_MIN_N:
        verdict = "inconclusive"
    elif precision["mdd_95"] is not None and abs(gross_gap) < precision["mdd_95"]:
        verdict = "unanswerable_precision"
    elif sel_bad or flipped:
        verdict = "unanswerable_selection"
    elif any((c["same_sign_pct"] or 0) < WALK_SIGN_SHARE * 100 for c in binding):
        verdict = "inconclusive"
    else:
        verdict = "resolved_walkups_higher" if gross_gap > 0 else "resolved_towers_higher"
    mech_verdict = ("unanswerable_selection"
                    if joint["cells"] < WALK_JOINT_MIN_CELLS else "attributable")

    print(f"[uw] walk-up: {verdict}; gap {gross_gap}pp [{glo}, {ghi}] on {len(W)} vs {len(T)} buildings; "
          f"fee {mechanism['fee_verdict']}; cause {mech_verdict} ({joint['cells']} joint cells)")
    return {
        "unit_note": "棟 buildings, 筆 records, 宅 dwellings -- side by side, never divided",
        "types": {"a": WALK_A, "b": WALK_B},
        "coverage": coverage, "representativeness": rep, "precision": precision,
        "controls": controls, "common_support": common_support, "mechanism": mechanism,
        "reweighted": reweighted,
        "verdict": verdict, "mechanism_verdict": mech_verdict,
        "rule": ("inconclusive if matched walk-ups < min_n; unanswerable_precision if |gap| < "
                 "mdd_95; unanswerable_selection if any matched-vs-unmatched median differs by "
                 "more than sel_tol_pct or the reweighted gap flips sign; inconclusive if any "
                 "binding control family agrees in sign less than sign_share of the time; else "
                 "resolved by the sign of the gap. The cause is attributable only if district x "
                 "age band yields at least joint_min_cells cells at joint_min_n."),
        "constants": {"min_n": WALK_MIN_N, "mdd_z": WALK_MDD_Z, "sign_share": WALK_SIGN_SHARE,
                      "ctrl_min_cover": WALK_CTRL_MIN_COVER, "sel_tol_pct": WALK_SEL_TOL_PCT,
                      "joint_min_n": WALK_JOINT_MIN_N, "joint_min_cells": WALK_JOINT_MIN_CELLS,
                      "mech_min_cell": WALK_MECH_MIN_CELL},
        "pre_registered": False,
        "would_answer": [
            {"dataset_zh": "完整的租約母體", "dataset_en": "a complete population of residential leases",
             "available": False,
             "why_zh": "本登錄的租賃案件只來自租賃住宅服務業與不動產經紀業；屋主自租的公寓從不進檔。",
             "why_en": "the registry only receives leases filed by licensed rental-service and "
                       "brokerage firms; a walk-up let directly by its owner never enters."},
            {"dataset_zh": "房屋稅籍建號級微資料（型態×屋齡×樓層）",
             "dataset_en": "building-level house-tax micro-data (type x age x floor)",
             "available": False,
             "why_zh": "僅供機關調用；已公布的都是縣市別「宅」數彙總。",
             "why_en": "released to institutions only; every published series is a county "
                       "aggregate in 宅."},
        ],
    }


def benchmarks_block(mortgage=MORTGAGE_RATE):
    """Three reference rates to set beside the net yield. Rates in percent.

    "Compared to what" is the question the page never answered. These are the
    two cheapest honest answers -- what the same money earns in a one-year
    state-bank deposit, and the policy rate -- plus the mortgage rate the page
    already shows, repeated here so the three sit in one strip.

    They are DIFFERENT DENOMINATORS from the yield: a deposit rate is pre-tax,
    principal-guaranteed and nominal; the net yield is a building median after
    modelled costs with no guarantee. So the page draws them side by side and
    never subtracts one from the other. The `mortgage` key is not touched --
    corrections accrete, and this list re-lists it rather than replacing it.

    Both new rates are read from files pinned under data/ref/cbc/ (fetch_cbc):
    the period labels are derived from the data, not typed in.
    """
    try:
        import fetch_cbc as C
        dep = C.load_deposit_1y()
        red = C.load_rediscount()
    except Exception as e:
        print(f"[uw] benchmarks skipped: {e}")
        return []
    dep_zh, dep_en = C.roc_month(dep["period"])
    ls = dep["latest_single"]
    ls_zh, ls_en = C.roc_month(ls["period"])
    red_zh, red_en = C.effective_labels(red["effective"])
    same = dep["spread"] == 0
    return [
        {
            "key": "deposit_1y",
            "rate": dep["rate"],
            "period_zh": dep_zh, "period_en": dep_en,
            "period_iso": f"{int(dep['period'][:3]) + 1911}-{dep['period'][3:5]}",
            "src_zh": "五大銀行一年期定期存款牌告利率（固定）— 中央銀行 A13 利率表",
            "src_en": "One-year fixed time-deposit rate posted by the five major banks "
                      "— CBC table A13",
            "url": C.FILES["A13Rate.csv"][0],
            "note_zh": ("取五家共同最新月份；" +
                        ("五家牌告相同。" if same else f"五家差距 {dep['spread']:.3f} 個百分點。") +
                        f"{ls['bank']}單獨延續至 {ls_zh}，為 {ls['rate']:.2f}%。稅前、保本、名目。"),
            "note_en": ("The latest month posted by all five banks; " +
                        ("identical at all five. " if same else
                         f"spread across the five {dep['spread']:.3f} pp. ") +
                        f"{ls['bank']} alone continues to {ls_en}, at {ls['rate']:.2f}%. "
                        "Pre-tax, principal-guaranteed, nominal."),
            "banks": dep["banks"],
            "same_at_all": same,
            "latest_single": ls,
        },
        {
            "key": "rediscount",
            "rate": red["rate"],
            "period_zh": red_zh, "period_en": red_en,
            "period_iso": red["effective"],
            "src_zh": "中央銀行重貼現率",
            "src_en": "Central Bank of the ROC rediscount rate",
            "url": C.FILES["webF1.csv"][0],
            "catalogue": C.FILES["webF1.csv"][2],
            "note_zh": (f"政策利率，不是可投資的報酬。同表：擔保放款融通利率 {red['secured']:.3f}%、"
                        f"短期融通利率 {red['short']:.2f}%。"),
            "note_en": (f"A policy rate, not an investable return. Same table: secured-loan "
                        f"accommodation {red['secured']:.3f}%, short-term accommodation "
                        f"{red['short']:.2f}%."),
        },
        {
            "key": "mortgage",
            **mortgage,
            "period_iso": "2026-05",
            "note_zh": "借款人付的利率，不是存款人收的；與上方「借錢的成本」是同一個數字，這裡只是並列。",
            "note_en": ("What a borrower pays, not what a saver earns; the same number as the "
                        "section above, repeated here only to sit beside the other two."),
        },
    ]


def excluded_block(rungs, pts, final_keys=frozenset()):
    """Buildings that have BOTH a sale and a lease and are still not on the map.

    The map draws 6,043 of 157,594 buildings, and the honest reason splits in
    two. 113,761 have no lease record at all — that is the law, nothing recovers
    them, and they cannot be drawn because there is no rent to draw. The other
    31,812 DO have both records and are removed by one of our own filters. Those
    can be drawn, and showing them is the whole argument of the site made
    visible: the map fills up, and every added building carries the reason it
    cannot be priced.

    They never enter a yield. The rungs are nested (raw ⊇ parking ⊇ social ⊇
    rooms), so the first rung a building falls out of names the filter that
    removed it.
    """
    if not rungs or "raw" not in rungs:
        return []
    order = [("parking", 1), ("social", 2), ("rooms", 3)]
    rungs = {k: v for k, v in rungs.items() if k != "parking_drop"}
    keys = {k: set(zip(v.county, v.k)) for k, v in rungs.items() if not v.empty}
    if "raw" not in keys:
        return []
    reason = {}
    for ident in keys["raw"]:
        # A building the headline now prices is not excluded, whatever the
        # rungs say. Parking is subtracted rather than dropped, so the rung
        # that used to define the final set no longer does.
        if ident in final_keys:
            continue
        r = 0
        for name, code in order:
            if name in keys and ident not in keys[name]:
                r = code
                break
        if r:
            reason[ident] = r
    if not reason:
        return []

    raw = rungs["raw"]
    keep = raw[[(c, k) in reason for c, k in zip(raw.county, raw.k)]].copy()
    keep["why"] = [reason[(c, k)] for c, k in zip(keep.county, keep.k)]
    keep, _ = G.attach(keep, pts)
    keep = keep[keep.x.notna() & keep.y.notna()]
    # Compact rows, not objects: 31,812 of these ride in the same payload as
    # 6,043 full records, and a dict per building would cost more than the
    # measurable set does. [x, y, type, why].
    tmap = {"住宅大樓": 0, "華廈": 1, "公寓": 2}
    out = []
    for row in keep.itertuples():
        out.append([int(row.x), int(row.y),
                    tmap.get(row.bldg_type, 0), int(row.why)])
    return out


#: How far forward the completed comparison is pushed, in quarters. A pre-sale
#: contract in Taiwan typically delivers in about three years; the window only
#: holds 11 seasons, so 8 quarters is as far as the data reaches.
PRESALE_LAGS = (0, 2, 4, 6, 8)


def load_presale_window(last_season=LAST_SEASON):
    """Every pre-sale (_b) row in the clean window, cleaned. None if absent.

    Factored out of presale_block because the volume section counts the same
    contracts; ~8 s of zip IO, paid once per build."""
    try:
        import fetch_lvr as _L
    except Exception:
        return None
    frames = []
    for s in _L.seasons_through(last_season):
        d = _L.load_presale_season(s)
        if d is not None and not d.empty:
            frames.append(d)
    if not frames:
        return None
    return _L.clean_presale(pd.concat(frames, ignore_index=True))


def presale_block(sales, last_season, P=None):
    """預售屋 — 180,835 dwellings that can never have a yield, and the premium
    that turns out not to be one.

    TWO THINGS, and the first is why this belongs on this page at all.

    A pre-sale flat has no lease because it does not exist yet, so no yield can
    ever be computed for one. Not "we lack the data" — there is nothing to
    measure. That is a whole segment of the market the headline is structurally
    blind to, and it is far larger than the sliver the headline is computed from.

    The second is a gap this data CANNOT explain, and the first version of this
    function got that wrong. The correction is kept in the docstring because the
    mistake is instructive and easy to make again.

    Pre-sale runs about +30% dearer per ping than completed buildings under two
    years old in the same district x 建物型態 x season. Push the completed side
    FORWARD in time and the gap collapses:

        +0.0 yr   +30.2%   (585 cells)
        +0.5 yr   +22.1%
        +1.0 yr   +15.7%
        +1.5 yr   +10.1%
        +2.0 yr    +4.3%   (307 cells)

    That looks like proof of the delivery lag: a contract signed today delivers
    in about three years, so its price describes a market three years out, and
    comparing it to that later market should close the gap. This function
    originally published exactly that conclusion.

    IT DOES NOT FOLLOW. Run the same shift between two COMPLETED groups, where
    there is no delivery lag at all, and the gap falls almost as fast:

        lag      presale vs completed     completed(T) vs completed(T+k)
        +0.0 yr        +30.2%                        0.0%   (by construction)
        +0.5 yr        +22.1%                       -4.7%
        +1.0 yr        +15.7%                       -9.0%
        +1.5 yr        +10.1%                      -13.0%
        +2.0 yr         +4.3%                      -20.6%

    The curve closes because completed prices RISE, which is what any
    time-separated comparison does. Divide it out and the residual premium is
    flat at +27% to +31% across every lag. Algebraically it has to be: dividing
    P(T)/C(T+k) by C(T)/C(T+k) just returns P(T)/C(T).

    So both stories predict the same curve. "Pre-sale prices the delivery date"
    predicts it, and "a persistent ~30% premium on top of ordinary price growth"
    predicts it just as well. THE CURVE CANNOT TELL THEM APART, and presenting it
    as if it could was the error.

    What would tell them apart is observing the SAME units both ways — a project
    that sells off-plan at T and whose flats resell completed at T+3yr. The
    registry makes that impossible: pre-sale addresses are project-unit
    references with no 號, 建案名稱 does not appear on the completed side, and
    完成年月 is empty on every pre-sale row. So the honest output is the gap, the
    placebo beside it, and the statement that this data cannot separate the two.

    Beyond that ambiguity the design removes nothing else: no control for which
    projects sell off-plan, for specification, or for developers pricing to a
    target. Those are stated on the page as limits, not modelled away.
    """
    seasons = L.seasons_through(last_season)
    if P is None:
        P = load_presale_window(last_season)
    if P is None or P.empty or sales is None or sales.empty:
        return {}

    _ym = roc_ym

    def _cq(v):
        """ROC yyyymmdd -> a contract-quarter index, comparable across sides.

        NOT fetch_lvr.roc_to_quarter's encoding: this is y*4 + (m-1)//3 + 1,
        one more than roc_to_quarter's y*4 + (m-1)//3. Only ever compared with
        itself inside this block, so the offset is harmless here -- but do not
        hoist it next to a roc_to_quarter-compatible index."""
        v = pd.to_numeric(v, errors="coerce")
        return (v // 10000) * 4 + (((v // 100) % 100).clip(1, 12) - 1) // 3 + 1

    P = P.copy()
    P["district"] = _tw(P["鄉鎮市區"])
    P["ppp"] = P.price / P.area_ping
    P["cq"] = _cq(P["交易年月日"])
    # These bounds are a malformed-row guard and nothing more: measured, they
    # exclude 0 of 180,835 pre-sale rows (observed range 100,707 to 2,529,996)
    # and 20 of 395,443 completed ones. All the actual trimming happens upstream
    # in clean_presale/clean_sales, on area and price. Left in so a corrupt row
    # cannot reach a median, but they are not outlier control and the comment is
    # here so nobody reads them as if they were.
    P = P[(P.ppp > 3e4) & (P.ppp < 3e6) & P.cq.notna()]

    C = sales.copy()
    C["district"] = _tw(C["鄉鎮市區"])
    C["ppp"] = C.price / C.area_ping
    C = C[(C.ppp > 3e4) & (C.ppp < 3e6)]

    # ── THE COMPARISON GROUP. This is where two published versions went wrong. ──
    #
    # It used to be `age = 115 - built_roc_y`, kept at <= 2. Anchoring to the
    # literal year 115 rather than to the transaction is bad enough on its own —
    # it silently means `built_roc_y >= 113` in every season and breaks outright
    # on the next rebuild. But the real damage is worse than an off-by-a-year:
    #
    #   交易年月日 in the 買賣 file is the CONTRACT date, not the transfer date.
    #
    # So a flat sold off-plan in 110 and completed in 113 registers as a 110
    # contract on a 113 building. Filtering on completion year alone kept every
    # one of those. Measured: 168,426 of the 186,550 rows that filter selected
    # — 90.3% — were contracts signed BEFORE the building existed, median age at
    # contract MINUS 2.17 years, the single largest cell being 110 contracts on
    # 113 completions (25,571 rows).
    #
    # The "completed" comparison group was therefore overwhelmingly the previous
    # pre-sale cohort. The published +30.2% was pre-sale against pre-sale, and no
    # placebo could catch it because both placebo arms were drawn from the same
    # contaminated group.
    #
    # `age >= 0` is the load-bearing half of the fix. Re-anchoring the year alone
    # keeps all 168,426 negative-age rows and moves the headline by 1.1pp.
    C["age"] = _ym(C["交易年月日"]) - _ym(C["建築完成年月"])
    C["cq"] = _cq(C["交易年月日"])
    C = C[C.age.between(0, 2) & C.cq.notna()]
    if C.empty:
        return {}

    # Both sides indexed on the CONTRACT quarter, never on the zip's publication
    # season. Median (publication season - contract quarter) is 1 quarter on the
    # pre-sale side and 10 on the old comparison group, so "same season" was a
    # median 2.25-year gap in the thing that actually moves prices.
    key = ["county", "district", "建物型態", "cq"]
    pa = P.groupby(key)["ppp"].agg(["median", "size"]).reset_index()
    pa.columns = key + ["pre", "pn"]
    cb = C.groupby(key)["ppp"].agg(["median", "size"]).reset_index()
    cb.columns = key + ["cmp", "cn"]

    def _cluster_ci(j, n=600, seed=11):
        """Percentile CI over district x 建物型態 clusters.

        Cells inside one district and building type are not independent draws:
        the same streets and often the same 建案 supply several quarters of
        them, so resampling CELLS would understate the interval. The cluster is
        the unit, the same way bootstrap_cis treats a building rather than a
        pair. 261 cells at lag 0 are 145 clusters; at lag 8, 55 cells are fewer
        still, and the interval is what says so.
        """
        if len(j) < 20:
            return (None, None, 0)
        rng = np.random.default_rng(seed)
        j = j.copy()
        j["_r"] = j.pre / j.cmp
        groups = [g["_r"].values for _, g in
                  j.groupby([j.county, j.district, j["建物型態"]])]
        if len(groups) < 8:
            return (None, None, len(groups))
        out = []
        for _ in range(n):
            pick = rng.integers(0, len(groups), len(groups))
            out.append(np.median(np.concatenate([groups[i] for i in pick])))
        lo, hi = np.percentile(out, [2.5, 97.5])
        return (round(float((lo - 1) * 100), 1),
                round(float((hi - 1) * 100), 1), len(groups))

    # The PLACEBO is not optional decoration. Running the identical shift
    # between two completed groups — where no delivery lag exists — shows how
    # much of the curve is just prices rising over time. Without it the falling
    # gap reads as proof of the lag story, and it is not.
    ca = cb.rename(columns={"cmp": "c0", "cn": "n0"})

    curve = []
    for k in PRESALE_LAGS:
        b = cb.copy()
        b["cq"] = b["cq"] - k              # pre-sale at T against completed at T+k
        j = pa.merge(b, on=key)
        j = j[(j.pn >= MIN_DISTRICT_N) & (j.cn >= MIN_DISTRICT_N)]
        if len(j) < 20:
            continue
        r = (j.pre / j.cmp)
        p2 = ca.merge(b, on=key)
        p2 = p2[(p2.n0 >= MIN_DISTRICT_N) & (p2.cn >= MIN_DISTRICT_N)]
        plac = (float((p2.c0 / p2.cmp).median()) - 1) * 100 if len(p2) >= 20 else None
        lo, hi, ncl = _cluster_ci(j)
        curve.append({
            "lag_q": int(k),
            "lag_years": round(k / 4.0, 2),
            "cells": int(len(j)),
            "clusters": int(ncl),
            "gap_pct": round(float((r.median() - 1) * 100), 1),
            "ci_lo": lo,
            "ci_hi": hi,
            "placebo_pct": round(plac, 1) if plac is not None else None,
            "placebo_cells": int(len(p2)),
        })
    if not curve:
        return {}

    # Coverage of the lag-0 comparison, and how the headline moves with the floor.
    b0 = cb.copy()
    j0 = pa.merge(b0, on=key)
    j0 = j0[(j0.pn >= MIN_DISTRICT_N) & (j0.cn >= MIN_DISTRICT_N)]
    reach = P.merge(j0[key], on=key).shape[0] if len(j0) else 0
    sens = []
    for f in (5, MIN_DISTRICT_N, 100):
        jf = pa.merge(b0, on=key)
        jf = jf[(jf.pn >= f) & (jf.cn >= f)]
        if len(jf) >= 20:
            sens.append({"floor": int(f), "cells": int(len(jf)),
                         "gap_pct": round(float((jf.pre / jf.cmp).median() - 1) * 100, 1)})

    # The premium net of the time effect. Flat across lags by construction,
    # which is exactly the point: the curve carries no information about which
    # explanation is right.
    far = curve[-1]
    resid = None
    if far.get("placebo_pct") is not None:
        resid = ((1 + far["gap_pct"] / 100.0) / (1 + far["placebo_pct"] / 100.0) - 1) * 100

    return {
        "separable": False,          # the two explanations cannot be told apart here
        "residual_pct": round(resid, 1) if resid is not None else None,
        "dwellings": int(len(P)),
        "projects": int(P.project.nunique()),
        "districts": int(P.groupby(["county", "district"]).ngroups),
        "median_ppp": int(P.ppp.median()),
        "seasons": [seasons[0], seasons[-1]],
        "curve": curve,
        "naive_gap_pct": curve[0]["gap_pct"],
        "far_gap_pct": curve[-1]["gap_pct"],
        "far_lag_years": curve[-1]["lag_years"],
        # How much of the pre-sale stock the comparison actually reaches. The
        # lead prints 180,835 dwellings and the gap is computed on a fraction of
        # them; on a page that ships a labelled row for every dropped building,
        # that fraction cannot stay undisclosed.
        "reach_cells": int(len(j0)),
        "reach_dwellings": int(reach),
        "reach_pct": round(reach / len(P) * 100, 1) if len(P) else None,
        "reach_districts": int(j0.groupby(["county", "district"]).ngroups) if len(j0) else 0,
        "total_districts": int(P.groupby(["county", "district"]).ngroups),
        # The n floor is not neutral and the page publishes sensitivities for
        # its other choices, so it publishes this one too.
        "floor_sensitivity": sens,
    }


def _season_end(season):
    """'115S2' -> Timestamp('2026-06-30'). ROC year + 1911, quarter end."""
    y, q = int(season[:3]) + 1911, int(season[-1])
    m = q * 3
    return pd.Timestamp(year=y, month=m, day=1) + pd.offsets.MonthEnd(0)


def fasc_block(sales, cache_dir=os.path.join("data", "fasc"), last_season=None):
    """金拍 auction results, and how much of that channel the registry can see.

    Reads ONLY the on-disk cache written by fetch_fasc.py. A build must never
    depend on a third-party site being up, and this one does not: no cache, no
    block, and the page simply does not render the section.

    Two things are reported and the second is the one that belongs on this page.

    The first is descriptive and needs no join: how often an auction clears at
    its reserve rather than above it. A lot that draws a single qualifying bid
    sells AT the reserve, so the share above it is the only competition signal
    the feed carries.

    The second is the address-match rate into the CLEANED sale frame — not into
    the raw registry. The join is against what this page actually computes from
    (residential, whole dwellings, arm's-length, above the area and price
    floors), so a miss means "outside the slice this site can measure", not
    "the registry holds nothing for that building". The page says so too. Every auctioned dwelling
    is a real home that really changed hands, and the question this page keeps
    asking is how much of the market its own source can see. The answer for the
    auction channel turns out to be a separate number worth publishing, because
    a home sold at auction is exactly the kind of transaction a reader would
    assume the registry contains.

    NOT a price comparison. The feed carries no floor area at all, so a
    price-per-ping for an auctioned unit cannot be computed, and comparing a
    total auction price against a market median would be comparing a studio to
    a townhouse. Reserve schedules also fall by round, so even a like-for-like
    price gap would be measuring the auction calendar as much as the market.
    """
    try:
        import fetch_fasc as FA
    except Exception as e:
        print("[fasc] module unavailable: %s" % str(e)[:80])
        return {}
    if not os.path.isdir(cache_dir):
        return {}
    rows = []
    for fn in sorted(os.listdir(cache_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(cache_dir, fn), "r", encoding="utf-8") as f:
                rows.extend(json.load(f))
        except Exception:
            continue
    if not rows:
        return {}
    d = FA.clean_auctions(pd.DataFrame(rows))
    if d.empty:
        return {}
    out = FA.summarise(d)
    out["sessions_cached"] = len([1 for fn in os.listdir(cache_dir)
                                  if fn.endswith(".json")])
    # The 金拍 feed runs past the registry window (it is fetched live). Any
    # comparison against a windowed series has to use this count, not
    # `items` -- the MOI section said "in the same window" while windowing
    # only its own side, and overstated the ratio by 3 points.
    if last_season and "date" in d.columns:
        end = _season_end(last_season)
        out["items_in_window"] = int((pd.to_datetime(d["date"], errors="coerce") <= end).sum())
        out["window_end"] = end.date().isoformat()

    # ── how much of this channel does the registry hold? ──
    # Same normaliser as everything else on this page, so the comparison is
    # against the same notion of "a building" the rest of the pipeline uses.
    d = d.copy()
    d["k"] = d.addr.map(addr_key)
    d = d[d.k != ""]
    if len(d) and sales is not None and not sales.empty and "k" in sales.columns:
        known = set(sales.k)
        hit = d.k.isin(known)
        out["addr_keyed"] = int(len(d))
        out["in_registry"] = int(hit.sum())
        out["in_registry_pct"] = round(float(hit.mean()) * 100, 1)
        out["buildings"] = int(d.k.nunique())
    return out


def within_building_block(rents, sales=None):
    """Furnishing and floor, measured the way this project measures everything
    else: WITHIN a building.

    A furnished let is dearer and a high floor is dearer, but both are also
    concentrated in newer, better-located buildings — so a raw comparison across
    the whole sample measures the buildings, not the furniture or the floor. The
    same-building design that produced the site's main finding controls for
    location, age, type, management and lift in one step: compare lets in the
    SAME building that differ only in the attribute.

    Reported as the median of per-building differences, so one large building
    cannot carry the result.
    """
    # Each side guards itself. The sale-side floor slope used to sit behind this
    # rent guard, so a run with no usable rents returned {} and silently dropped
    # a block that has nothing to do with rents.
    out = {}
    have_rents = (rents is not None and not rents.empty
                  and "furnished" in rents.columns)
    d = rents.copy() if have_rents else pd.DataFrame()
    if have_rents:
        d["ppp"] = d.rent / d.area_ping
        d = d[(d.ppp > 50) & (d.ppp < 5000)]

    # ── furnished vs not, same building ──
    diffs, n_b = [], 0
    for _, g in (d.groupby(["county", "k"]) if have_rents else []):
        f, u = g[g.furnished == 1], g[g.furnished == 0]
        if len(f) and len(u):
            diffs.append(float(median(f.ppp) - median(u.ppp)))
            n_b += 1
    if diffs:
        arr = sorted(diffs)
        base = float(median(d[d.furnished == 0].ppp))
        out["furnished"] = {
            "buildings": n_b,
            "diff_ppp": round(float(median(pd.Series(arr))), 1),
            "base_ppp": round(base, 1),
            "pct": round(float(median(pd.Series(arr))) / base * 100, 1) if base else None,
            "share_furnished": round(float(d.furnished.mean()) * 100, 1),
            "raw_pct": round((float(median(d[d.furnished == 1].ppp)) / base - 1) * 100, 1)
            if base else None,
        }

    # ── floor, same building (rent side) ──
    per, fd = [], pd.DataFrame()
    if have_rents:
        d["fl"] = d.floor_raw.map(floors_to_int)
        fd = d[d.fl.notna() & (d.fl >= 1) & (d.fl <= 60)].copy()
    for _, g in (fd.groupby(["county", "k"]) if len(fd) else []):
        if g.fl.nunique() < 2 or len(g) < 3:
            continue
        # slope of rent-per-ping on floor, within this building
        x = g.fl.astype(float).values
        y = g.ppp.astype(float).values
        vx = x - x.mean()
        den = float((vx * vx).sum())
        if den <= 0:
            continue
        per.append(float((vx * (y - y.mean())).sum() / den))
    if per:
        base = float(median(fd.ppp))
        out["floor"] = {
            "buildings": len(per),
            "slope_ppp_per_floor": round(float(median(pd.Series(sorted(per)))), 2),
            "base_ppp": round(base, 1),
            "pct_per_floor": round(float(median(pd.Series(sorted(per)))) / base * 100, 2)
            if base else None,
        }

    # ── floor, same building, on the SALE side ──
    #
    # The rent slope above has been on the page for a while and answers half a
    # question. A higher floor is dearer to rent AND dearer to buy, so which
    # one rises faster decides whether the yield goes up or down as you climb —
    # and that is the same mechanism the MRT section measures across space.
    # Measured the same way: within one building, so the comparison controls
    # for location, age, type, lift and management in a single step.
    if sales is not None and not sales.empty and "floor_raw" in sales.columns:
        sd = sales.copy()
        sd["fl"] = sd.floor_raw.map(floors_to_int)
        sd["ppp"] = sd.price / sd.area_ping
        sd = sd[sd.fl.notna() & (sd.fl >= 1) & (sd.fl <= 60)
                & (sd.ppp > 1e4) & (sd.ppp < 5e6)]
        sper = []
        for _, g in sd.groupby(["county", "k"]):
            if g.fl.nunique() < 2 or len(g) < 3:
                continue
            x = g.fl.astype(float).values
            y = g.ppp.astype(float).values
            vx = x - x.mean()
            den = float((vx * vx).sum())
            if den <= 0:
                continue
            sper.append(float((vx * (y - y.mean())).sum() / den))
        if sper:
            sbase = float(median(sd.ppp))
            spct = (float(median(pd.Series(sorted(sper)))) / sbase * 100
                    if sbase else None)
            out["floor_sale"] = {
                "buildings": len(sper),
                "slope_ppp_per_floor": round(float(median(pd.Series(sorted(sper)))), 1),
                "base_ppp": round(sbase, 1),
                "pct_per_floor": round(spct, 3) if spct is not None else None,
            }
            # The whole point of computing both. Positive means price climbs
            # faster than rent, so the yield FALLS as you go up — the same
            # capitalisation the transit section finds across distance.
            rp = out.get("floor", {}).get("pct_per_floor")
            if rp is not None and spct is not None:
                out["floor_gap_pp"] = round(spct - rp, 3)
    return out


# 行政院主計總處 家庭收支調查:「所得收入者平均每人所得收入總計按區域別分」,
# published annually since 1998 under 政府資料開放授權條款. Dataset 117930.
DGBAS_INCOME_CSV = ("https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/232214/"
                    "081-%E6%89%80%E5%BE%97%E6%94%B6%E5%85%A5%E8%80%85%E5%B9%B3"
                    "%E5%9D%87%E6%AF%8F%E4%BA%BA%E6%89%80%E5%BE%97%E6%94%B6%E5%85"
                    "%A5%E7%B8%BD%E8%A8%88%E6%8C%89%E5%8D%80%E5%9F%8E%E5%88%A5"
                    "%E5%88%86.csv")


def income_block(ub, b=None, cache_dir="data/ref"):
    """How many years of income a home costs, per county.

    A yield is a number for someone who already owns capital. "How many years of
    everything you earn" is the same data pointed at the reader who does not, and
    it is the question people actually ask about Taiwanese housing.

    Deliberately computed on the UNIVERSE — every building with a recorded sale —
    not on the 6% this site can price. The measurable set is dearer and newer, so
    using it here would overstate the ratio for exactly the reason the rest of the
    page is about.

    The denominator is per INCOME EARNER, not per household: 主計總處 publishes it
    that way in this series, and a household ratio would be a different and
    smaller number. The page says which.
    """
    import csv as _csv
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "dgbas_income.csv")
    if not os.path.exists(path):
        # requests, not urllib: urllib uses the system trust store, which on this
        # machine has no CA for ws.dgbas.gov.tw and fails the handshake. requests
        # ships certifi, and it is what every other fetch in this repo uses.
        try:
            import requests
            r = requests.get(DGBAS_INCOME_CSV, timeout=120)
            if r.status_code != 200 or len(r.content) < 500:
                print(f"[inc] http {r.status_code}, {len(r.content)} bytes")
                return {}
            with open(path, "wb") as fh:
                fh.write(r.content)
        except Exception as e:
            print(f"[inc] download failed: {e}")
            return {}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            rows = list(_csv.DictReader(fh))
    except Exception as e:
        print(f"[inc] read failed: {e}")
        return {}
    if not rows:
        return {}
    last = rows[-1]
    year = last.get("年", "")
    by_name = {}
    for col, v in last.items():
        if not col or not col.endswith("-元"):
            continue
        try:
            by_name[col[:-2]] = float(str(v).replace(",", ""))
        except ValueError:
            continue
    national_income = by_name.pop("臺灣地區", None)
    name_to_key = {v: k for k, v in L.COUNTIES.items()}
    out = []
    for name, inc in by_name.items():
        c = name_to_key.get(name)
        if not c or inc <= 0:
            continue
        g = ub[ub.county == c]
        if len(g) < MIN_DISTRICT_N:
            continue
        price = float(median(g.price))
        out.append({
            "county": c, "city": name,
            "income": int(round(inc)),
            "price": int(round(price)),
            "years": round(price / inc, 1),
            "n": int(len(g)),
        })
    out.sort(key=lambda r: -r["years"])
    if not out:
        return {}
    nat = median(ub.price)
    nat_inc = national_income
    # The same ratio on the 6% this site CAN price, published so the page can
    # say what using the sliver would do instead of asserting it. The docstring
    # above has always said "overstate"; the page's copy said "understate" and
    # typed the figures in, and after `age` moved to the universe frame the
    # typed ones were wrong as well as contradictory.
    m_price = median(b.price_abs) if b is not None and not b.empty else None
    return {
        "year": year,
        "source_zh": "主計總處 家庭收支調查・所得收入者平均每人所得收入總計",
        "source_en": ("DGBAS Survey of Family Income and Expenditure, "
                      "average total income per income earner"),
        "url": "https://data.gov.tw/dataset/117930",
        "national_years": round(float(nat) / nat_inc, 1) if nat_inc else None,
        "matched_years": (round(float(m_price) / nat_inc, 1)
                          if nat_inc and m_price else None),
        "universe_price": int(nat) if nat else None,
        "matched_price": int(m_price) if m_price else None,
        "counties": out,
    }


def _median_ramp(b, keys, floor_n=MIN_DISTRICT_N):
    """Domain for a choropleth of GROUP MEDIANS, not of individual buildings.

    Padded 8% each way so the darkest and lightest areas are not pinned to the
    very ends of the ramp, which reads as clipping rather than as extremes.
    """
    if b.empty:
        return None
    g = b.groupby(keys).gross
    med = g.median()[g.size() >= floor_n]
    if len(med) < 3:
        return None
    lo, hi = float(med.min()), float(med.max())
    if hi <= lo:
        return None
    pad = (hi - lo) * 0.08
    return [round(lo - pad, 2), round(hi + pad, 2)]


# ── transaction volume ───────────────────────────────────────────────────────

# Three policy dates that fall on one quarter boundary. Constants, not data;
# the section marks them and says in so many words that it cannot tell them
# apart. `frac` = position inside the contract quarter, for the x-coordinate.
VOLUME_EVENTS = [
    {"id": "nqa",  "date": "2024-06-27", "zh": "新青安優化措施（行政院會通過：自住切結、一生一次）",
     "en": "新青安 tightening (Executive Yuan: owner-occupancy affidavit, once per lifetime)"},
    {"id": "tax2", "date": "2024-07-01", "zh": "囤房稅 2.0 生效",
     "en": "囤房稅 2.0 in force"},
    {"id": "cbc7", "date": "2024-09-19", "zh": "央行第七波信用管制",
     "en": "Central Bank credit controls, round seven"},
]
VOLUME_COUNTIES = ("a", "f", "h", "b", "e", "d")   # 臺北 新北 桃園 臺中 高雄 臺南


def season_index(s):
    """'112S4' -> the same integer clock as fetch_lvr.roc_to_quarter, so a
    publication season and a contract quarter subtract cleanly."""
    return int(s[:3]) * 4 + int(s[4]) - 1


def volume_block(sales_all, rents_all, P, seasons):
    """Registered transactions per CONTRACT quarter, counted at a fixed horizon.

    The page has no volume series, and the window contains a halving. But a
    naive count per quarter is not comparable across quarters: a row files in
    the season of its contract or later, so the newest quarter is always short.
    Every quarter here is measured with the same ruler -- a row counts only if
    it was published in season Q or Q+1 -- which captures ~90% of existing-home
    rows and 100% of presale and lease rows, and undercounts every quarter by a
    similar share. The last quarter has no Q+1 yet and is flagged censored.

    Existing-home sales exclude rows whose contract predates the completion
    date -- presale units registering on handover, 54% of cleaned sales, still
    arriving eight seasons later. Same predicate as presale_block (roc_ym).

    COUNTS, not yields, and rows, not buildings -- this is the one section not
    aggregated at building level, because a transaction count is not a yield.
    The official 建物買賣移轉登記棟數 is set BESIDE the registry series in its own
    figure: a different unit (棟) on a different clock (registration quarter),
    so it is never divided into these counts. No attribution: three policies
    land in one quarter and 113Q2 is itself a peak.
    """
    if sales_all is None or sales_all.empty:
        return {}
    import datetime as _dt
    idx0 = season_index(seasons[0])
    Q = [L.quarter_label(idx0 + i) for i in range(len(seasons))]
    qset = {idx0 + i for i in range(len(seasons))}
    sidx = {s: season_index(s) for s in seasons}

    def _lag(frame):
        return frame["season"].map(sidx) - frame["q"]

    S = sales_all.copy()
    S["age"] = roc_ym(S["交易年月日"]) - roc_ym(S["建築完成年月"])
    kinds = {
        "existing": int((S.age >= 0).sum()),
        "presale_origin": int((S.age < 0).sum()),
        "no_completion": int(S.age.isna().sum()),
        "total": int(len(S)),
    }
    E = S[(S.age >= 0) & S.q.isin(qset)].copy()
    E["lag"] = _lag(E)
    anomalies = int((E.lag < 0).sum())

    frames = {"existing": E}
    if P is not None and not P.empty and "season" in P.columns:
        Pq = P[P.q.isin(qset)].copy()
        Pq["lag"] = _lag(Pq)
        anomalies += int((Pq.lag < 0).sum())
        frames["presale"] = Pq
    if rents_all is not None and not rents_all.empty:
        R = rents_all[rents_all.q.isin(qset)].copy()
        R["lag"] = _lag(R)
        anomalies += int((R.lag < 0).sum())
        frames["leases"] = R

    def _arrival(fr):
        ok = fr[fr.lag >= 0]
        n = max(len(ok), 1)
        return {"0": round(float((ok.lag == 0).sum() / n), 3),
                "1": round(float((ok.lag == 1).sum() / n), 3),
                "2": round(float((ok.lag == 2).sum() / n), 3),
                "3+": round(float((ok.lag >= 3).sum() / n), 3)}
    arrival = {k: _arrival(fr) for k, fr in frames.items()}

    counties = ["all"] + [c for c in VOLUME_COUNTIES if c in L.COUNTIES]
    series = {}
    for c in counties:
        series[c] = {}
        for name, fr in frames.items():
            sub = fr if c == "all" else fr[fr.county == c]
            sub = sub[(sub.lag >= 0) & (sub.lag <= 1)]
            counts = sub.groupby("q").size()
            series[c][name] = [int(counts.get(idx0 + i, 0)) for i in range(len(Q))]

    # censored: the quarter whose Q+1 season is not in the window
    censored = [Q[i] for i in range(len(Q)) if (idx0 + i + 1) not in sidx.values()]
    # captured: of all existing rows for quarter q that ever arrived (lag >= 0),
    # the share inside the horizon -- only where Q+2 is in the window
    captured = {}
    for i, q in enumerate(Q):
        if (idx0 + i + 2) in sidx.values():
            allq = E[(E.q == idx0 + i) & (E.lag >= 0)]
            inq = allq[allq.lag <= 1]
            captured[q] = round(len(inq) / len(allq) * 100, 1) if len(allq) else None
        else:
            captured[q] = None

    complete = [q for q in Q if q not in censored]
    ex = series["all"]["existing"]
    pe = series["all"].get("presale")
    le = series["all"].get("leases")
    ci = {q: i for i, q in enumerate(Q)}
    peak_q = max(complete, key=lambda q: ex[ci[q]])
    after_i = min(ci[peak_q] + 2, len(complete) - 1)
    after_q = Q[after_i]
    since = [ex[ci[q]] for q in complete if ci[q] >= after_i]
    summary = {
        "peak_q": peak_q, "peak_existing": ex[ci[peak_q]],
        "after_q": after_q, "after_existing": ex[after_i],
        "existing_change_pct": round((ex[after_i] - ex[ci[peak_q]]) / ex[ci[peak_q]] * 100, 1),
        "since_mean": int(round(sum(since) / len(since))) if since else None,
        "since_to_q": complete[-1],
    }
    if pe:
        later = [q for q in complete if ci[q] > ci[peak_q]]
        to_q = min(later, key=lambda q: pe[ci[q]]) if later else peak_q
        summary.update({"presale_from": pe[ci[peak_q]], "presale_to_q": to_q,
                        "presale_to": pe[ci[to_q]],
                        "presale_change_pct": round((pe[ci[to_q]] - pe[ci[peak_q]])
                                                    / pe[ci[peak_q]] * 100, 1)})
    if le:
        summary.update({"leases_from": le[ci[peak_q]], "leases_to_q": complete[-1],
                        "leases_to": le[ci[complete[-1]]]})

    events = []
    for e in VOLUME_EVENTS:
        d = _dt.date.fromisoformat(e["date"])
        roc = (d.year - 1911) * 10000 + d.month * 100 + d.day
        qi = L.roc_to_quarter(roc)
        q0 = _dt.date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)
        q1m = q0.month + 3
        q1 = _dt.date(q0.year + (q1m > 12), (q1m - 1) % 12 + 1, 1)
        frac = (d - q0).days / (q1 - q0).days
        events.append({**e, "q": L.quarter_label(qi), "frac": round(frac, 3)})

    official = None
    try:
        import fetch_moi as M
        ref = ref_manifest()
        sha = next((f["sha256"] for f in ref["files"]
                    if f["path"].endswith("sale_transfers.csv")), None)
        df = M.load_series("sale_transfers")
        if df is not None and not df.empty and sha:
            df = df[(df.district == "") & df.period.isin(Q)]
            code_of = {v: k for k, v in L.COUNTIES.items()}
            oseries = {}
            for c in counties:
                name = "全國" if c == "all" else L.COUNTIES[c]
                sub = df[df.county == name].set_index("period")["value"]
                if len(sub):
                    oseries[c] = [int(sub.get(q, 0)) for q in Q]
            zh, en, unit = M.SERIES["sale_transfers"][3:6]
            official = {
                "key": "sale_transfers", "zh": zh, "en": en, "unit": unit,
                "basis": "registration quarter, all building uses, 內政部 E3030 T4/K1/N3",
                "url": M.URL,
                "period_first": str(df.period.min()) if len(df) else None,
                "period_last": str(df.period.max()) if len(df) else None,
                "sha256": sha,
                "quarters": Q,
                "series": oseries,
            }
    except Exception as e:
        print(f"[uw] volume: official series skipped: {e}")

    return {
        "quarters": Q,
        "horizon_seasons": 1,
        "censored": censored,
        "basis": {
            "existing": "contract quarter (交易年月日); 建築完成年月 <= contract month; clean_sales",
            "presale": "contract quarter (交易年月日); clean_presale",
            "leases": "lease quarter (租賃年月日); clean_rents",
        },
        "unit": "rows",
        "kinds": kinds,
        "presale_origin_pct": round(kinds["presale_origin"] / kinds["total"] * 100, 1),
        "anomalies": anomalies,
        "arrival": arrival,
        "captured_pct": captured,
        "counties": counties,
        "series": series,
        "summary": summary,
        "events": events,
        "attribution": False,
        "official": official,
    }


def low_use_rates():
    """低度使用(用電)住宅 as a share of the house-tax roll, by county.

    Single-sourced, because two callers need it — the 內政部 section prints it
    and `vacancy_prior_block` reweights it — and v2.2's lesson was that a rate
    whose numerator and denominator come from different frames is not a rate.

    The MOI's own published rate divides by 房屋稅籍住宅類數量, not 住宅存量
    (its page says so: 係以「房屋稅籍住宅類數量」為計算基礎). On that base
    114H2 全國 reproduces the published 9.44% exactly; on 住宅存量 it was
    9.31% and matched nothing the MOI prints.

    Returns {} when either series is missing, so a build without the reference
    CSVs still succeeds.
    """
    import fetch_moi as M
    name_to_code = {v: k for k, v in L.COUNTIES.items()}
    lu = M.load_html_series("low_use")
    hs = M.load_series("resi_tax_roll")
    if lu.empty or hs.empty:
        return {}
    lu_last = lu[lu.value.notna()].sort_values("period")
    if lu_last.empty:
        return {}
    lp = lu_last.period.max()
    lu_last = lu_last[lu_last.period == lp]
    # match the stock to the same half-year: H1 -> Q2, H2 -> Q4
    hq = lp[:3] + ("Q2" if lp.endswith("H1") else "Q4")
    hsq = hs[(hs.period == hq) & (hs.district == "")]
    rows = []
    for _, r in lu_last.iterrows():
        stock = hsq[hsq.county == r.county]
        if stock.empty or not stock.value.iloc[0]:
            continue
        code = name_to_code.get(r.county, "all" if r.county == "全國" else None)
        rows.append({"county": code, "city": r.county,
                     "low_use": int(r.value), "stock": int(stock.value.iloc[0]),
                     "rate_pct": round(float(r.value) / float(stock.value.iloc[0]) * 100, 2)})
    if not rows:
        return {}
    return {"period": lp, "stock_period": hq, "rows": rows,
            "base_zh": "房屋稅籍住宅類數量",
            "base_en": "residential units on the house-tax roll"}


def moi_block(seasons, b, ub, fasc):
    """The government's own figures, printed beside this site's.

    Every number here is an official 內政部 series that either fills a gap the
    page already admits or checks a number the page computes. None replaces
    anything: the point is the pair -- theirs, ours, and the gap between them.

      auction   法院拍定 (court auctions) by county for the site's window. The
                auction section says it sees 金拍 only and that 法拍 is much
                larger. This is how much larger.
      stock     the denominator behind the denominator. The page's universe is
                "buildings with a sale record in the window"; the housing stock
                is what a reader means by "Taiwan's housing", and it is ~60x
                bigger. Units differ (棟 vs 宅) and are labelled, not divided.
      price     official average sale price per 坪 by county and building type,
                against the site's own median across matched buildings. The
                site's slice is the young, tower-heavy, investor-owned part of
                the market, and this is where that shows as a number.
      mortgage  a second official rate beside the Central Bank figure.

    All series are fetched by fetch_moi and cached under data/ref/moi/. A build
    without them still succeeds -- the block is simply empty.
    """
    try:
        import fetch_moi as M
    except Exception:
        return {}
    periods = {s.replace("S", "Q") for s in seasons}
    name_to_code = {v: k for k, v in L.COUNTIES.items()}
    out = {"source_zh": "內政部不動產資訊平台 統計資訊整合項目",
           "source_en": "MOI Real Estate Information Platform, integrated statistics",
           "url": M.URL, "window": [seasons[0], seasons[-1]]}

    # ── auctions ────────────────────────────────────────────────────────
    n = M.load_series("court_auction_n")
    amt = M.load_series("court_auction_amt")
    resi = M.load_series("resi_auction_n")
    if not n.empty:
        w = n[n.period.isin(periods) & (n.district == "")]
        nat = w[w.county == "全國"]
        byc = (w[w.county != "全國"].groupby("county").value.sum()
               .sort_values(ascending=False))
        wa = amt[amt.period.isin(periods) & (amt.district == "") & (amt.county == "全國")]
        wr = resi[resi.period.isin(periods) & (resi.district == "") & (resi.county == "全國")]
        out["auction"] = {
            # 法院拍定成屋總件數: completed court-auction sales, in 件 (lots)
            "court_lots": int(nat.value.sum()),
            "court_value": int(wa.value.sum()) if not wa.empty else None,
            # 住宅拍賣移轉筆數: residential auction TRANSFERS, in 筆 (registrations).
            # A lot can register as several 筆, so this is NOT a subset of the
            # count above and must not be presented as one.
            "court_resi_transfers": int(wr.value.sum()) if not wr.empty else None,
            # 金拍 (TFASC) lots the site's own feed sees. A parallel channel,
            # not a share of 法拍.
            "fasc_lots": int(fasc.get("items_in_window") or fasc.get("items") or 0),
            "fasc_windowed": bool(fasc.get("items_in_window")),
            "quarters": int(nat.period.nunique()),
            "by_county": [{"county": name_to_code.get(c, c), "city": c, "lots": int(v)}
                          for c, v in byc.items() if v > 0][:12],
        }
        if out["auction"]["fasc_lots"] and out["auction"]["court_lots"]:
            # "金拍 lots number X% AS MANY AS 法拍 lots" -- a size ratio between
            # two channels, not a coverage figure.
            out["auction"]["fasc_vs_court_pct"] = round(
                out["auction"]["fasc_lots"] / out["auction"]["court_lots"] * 100, 1)

    # ── stock ───────────────────────────────────────────────────────────
    stock = {}
    for key, label_zh, label_en in (
        ("housing_stock", "住宅存量", "Housing stock (dwellings)"),
        ("resi_tax_roll", "房屋稅籍住宅類數量", "Residential units on the house-tax roll"),
        ("building_stock", None, None),   # labels come from SERIES; see the guard below
    ):
        s = M.load_series(key)
        if s.empty:
            continue
        nat = s[(s.county == "全國") & (s.district == "")]
        if nat.empty:
            continue
        last = nat[nat.period == nat.period.max()].iloc[0]
        stock[key] = {"zh": label_zh or M.SERIES[key][3],
                      "en": label_en or M.SERIES[key][4], "unit": M.SERIES[key][5],
                      "value": int(last.value), "period": last.period}
    if stock:
        # 建物總量 EXCEEDS 住宅存量 in every county (臺北市 1.16x at 114Q4). No
        # count of physical buildings can exceed the count of dwellings in a
        # tower city, so this series is registered 建物 -- 建號, roughly one per
        # unit -- not buildings. The site's 157,594 and 9,805 are 門牌-keyed
        # physical buildings. The two cannot be divided, and this block used to
        # divide them ("one building in 1,086"). Labelled and left undivided.
        # fetch_moi.SERIES now declares this correctly at the source, so this is
        # a GUARD rather than a patch: if the declaration ever drifts back to 棟
        # the build stops here instead of shipping the withdrawn claim's unit.
        if "building_stock" in stock:
            assert stock["building_stock"]["unit"] == "建號", (
                "建物總量 is registered 建號, not 棟 -- see fetch_moi.SERIES")
        out["stock"] = stock
        out["ours"] = {"universe_buildings": int(len(ub)) if ub is not None else None,
                       "matched_buildings": int(len(b)),
                       "unit": "棟",
                       "no_ratio_zh": "官方三個數字都以「宅」或「建號」計，本站以「棟」計。一棟大樓是幾十個建號，所以沒有任何一個可以拿來當本站的分母；這裡只並列，不相除。",
                       "no_ratio_en": "All three official figures count dwellings or registered 建號; this site counts buildings. A tower is dozens of 建號, so none of them can serve as this site's denominator. Set side by side, not divided."}

    # ── price check ─────────────────────────────────────────────────────
    sp = M.load_series("sale_price_ping")
    if not sp.empty and not b.empty:
        # latest quarter in the window with data, county totals, all types
        w = sp[sp.period.isin(periods) & (sp.district == "") & (sp.kind == "")
               & sp.value.notna() & (sp.value > 0)]
        if not w.empty:
            latest = w.period.max()
            w = w[w.period == latest]
            ours = b.groupby("county").price_ping.median()
            rows = []
            for _, r in w.iterrows():
                code = name_to_code.get(r.county)
                if not code or code not in ours.index:
                    continue
                official = float(r.value) * 10000.0          # 萬元 -> 元
                mine = float(ours[code])
                rows.append({"county": code, "city": r.county,
                             "official": round(official), "ours": round(mine),
                             "gap_pct": round((mine / official - 1) * 100, 1),
                             "n": int((b.county == code).sum())})
            rows.sort(key=lambda x: -x["n"])
            out["price"] = {"period": latest, "unit": "元/坪",
                            "note_zh": "官方為該季買賣契約平均單價（所有建物類型）；本站為配對建物的中位數。",
                            "note_en": "Official is the quarter's mean contract price per ping, all "
                                       "building types; ours is the median across matched buildings.",
                            "rows": rows}

    # ── the official price index, against the drift this site leaves in ──
    #
    # The pipeline's own district index was measured, made the yield-vs-gap
    # slope worse, and is OFF. That leaves an admitted, unquantified limitation:
    # a sale and a lease may sit up to 4 quarters apart and nothing corrects
    # for prices moving in between. The official index over the same window
    # puts a number on it -- and at the site's median pair gap, that number is
    # what a typical pair carries.
    pi = M.load_html_series("price_index")
    if not pi.empty:
        nat = pi[(pi.county == "全國") & pi.value.notna()].sort_values("period")
        inwin = nat[nat.period.isin(periods)]
        if len(inwin) >= 2:
            p0, p1 = inwin.iloc[0], inwin.iloc[-1]
            def _qidx(pp):
                return int(pp[:3]) * 4 + int(pp[-1])
            nq = _qidx(p1.period) - _qidx(p0.period)
            total_pct = (float(p1.value) / float(p0.value) - 1) * 100
            per_q = ((float(p1.value) / float(p0.value)) ** (1.0 / nq) - 1) * 100 if nq else 0.0
            med_gap = float(b.gap.median()) if "gap" in b.columns and not b.empty else None
            out["price_index"] = {
                "start": {"period": p0.period, "value": float(p0.value)},
                "end": {"period": p1.period, "value": float(p1.value)},
                "quarters": nq, "total_pct": round(total_pct, 2),
                "per_quarter_pct": round(per_q, 3),
                "median_pair_gap_q": round(med_gap, 2) if med_gap is not None else None,
                "drift_at_median_gap_pct": (round(per_q * med_gap, 2)
                                            if med_gap is not None else None),
                "base_zh": "基期 105 年＝100", "base_en": "105年 = 100",
            }

    # ── low-use (empty) homes: context for the vacancy assumption ────────
    #
    # NOT a vacancy input. 低度使用(用電) counts every dwelling drawing almost no
    # electricity -- second homes, homes for sale, homes between owners -- and
    # its denominator is all dwellings, not rental stock. The page's 5% is a
    # rental-vacancy assumption and this cannot replace it. What it can do is
    # make the break-even test legible: "this district needs 24.8% vacancy to
    # fall to the median" now sits beside the share of homes in that county
    # that are empty by any measure.
    lu_blk = low_use_rates()
    if lu_blk:
        out["low_use"] = dict(lu_blk, site_vacancy_pct=DEFAULT_VACANCY_PCT)

    un = M.load_html_series("unsold_new")
    if not un.empty:
        nat = un[(un.county == "全國") & un.value.notna()].sort_values("period")
        if not nat.empty:
            out["unsold_new"] = {"period": nat.period.iloc[-1], "value": int(nat.value.iloc[-1])}

    # ── the actual stock, by floor count and by age ──────────────────────
    #
    # The coverage section's denominator is "buildings with a sale in the
    # window". That is what the registry allows, and it is not what a reader
    # means by "Taiwan's housing". These two series are the house-tax roll --
    # every residential unit, by how tall its building is and how old.
    #
    # In 宅, not 棟. A 16-storey tower is one building and a hundred units, so
    # a unit-weighted stock is already tower-heavier than a building-weighted
    # one would be. The site's matched set is compared as a DISTRIBUTION of
    # buildings against a distribution of units, and that direction of
    # mismatch UNDERSTATES the skew -- which is the conservative one.
    sf = M.load_theme_series("stock_by_floor")
    if not sf.empty:
        nat = sf[(sf.county == "全國") & (sf.district == "")]
        lp = nat.period.max()
        nat = nat[nat.period == lp]
        tot = float(nat[nat.kind == ""].value.iloc[0])
        bands = {r.kind: float(r.value) for _, r in nat.iterrows() if r.kind}
        # 11+ maps to 住宅大樓 (11層含以上有電梯); 6-10 to 華廈 (10層含以下有電梯);
        # 4-5 to 公寓 (5樓含以下無電梯). 1-3 is mostly 透天厝, which the
        # RESIDENTIAL filter excludes by construction -- shown, not mapped.
        by_type = {
            "住宅大樓": bands.get("11~15層", 0) + bands.get("16層以上", 0),
            "華廈": bands.get("6~10層", 0),
            "公寓": bands.get("4~5層", 0),
        }
        outside = bands.get("1~3層", 0)
        inside = sum(by_type.values())
        out["stock_by_floor"] = {
            "period": lp, "unit": "宅", "total": int(tot),
            "bands": [{"band": k, "units": int(v), "share_pct": round(v / tot * 100, 1)}
                      for k, v in bands.items()],
            # shares of the part of the stock the site's universe can contain
            "by_type": [{"type": t, "units": int(v),
                         "share_of_stock_pct": round(v / tot * 100, 1),
                         "share_of_inside_pct": round(v / inside * 100, 1)}
                        for t, v in by_type.items()],
            "outside_units": int(outside),
            "outside_pct": round(outside / tot * 100, 1),
            "outside_zh": "1~3層，多為透天厝，本站的住宅篩選在定義上就排除",
            "outside_en": "1-3 storeys, mostly 透天厝, excluded by this site's residential filter by construction",
        }

    sa = M.load_theme_series("stock_by_age")
    if not sa.empty and not b.empty and "built" in b.columns:
        nat = sa[(sa.county == "全國") & (sa.district == "")]
        lp = nat.period.max()
        nat = nat[nat.period == lp]
        tot = float(nat[nat.kind == ""].value.iloc[0])
        # 'mean', not 'mean_age': load_theme_series normalises every series'
        # mean column to one label, because the six series word theirs
        # differently (住宅平均屋齡, 平均買賣屋齡, 平均買賣面積, 買賣平均總樓層).
        mean_age = nat[nat.kind == "mean"].value
        # the same bands for the site's matched buildings. Age in ROC years at
        # the end of the window (115), which is how the cost model ages them.
        edges = [(0, 1, "1（含）年以下"), (1, 5, "1~5（含）年"), (5, 10, "5~10（含）年"),
                 (10, 15, "10~15（含）年"), (15, 20, "15~20（含）年"), (20, 25, "20~25（含）年"),
                 (25, 30, "25~30（含）年"), (30, 40, "30~40（含）年"), (40, 50, "40~50（含）年"),
                 (50, 999, "50年以上")]
        ages = (115.0 - b.built.astype(float)).clip(lower=0)
        nb = int(ages.notna().sum())
        rows = []
        for lo, hi, label in edges:
            stock_units = float(nat[nat.kind == label].value.iloc[0]) if (nat.kind == label).any() else 0.0
            mine = int(((ages > lo) & (ages <= hi)).sum()) if lo else int((ages <= hi).sum())
            rows.append({"band": label, "stock_units": int(stock_units),
                         "stock_pct": round(stock_units / tot * 100, 1),
                         "ours_n": mine, "ours_pct": round(mine / max(1, nb) * 100, 1)})
        out["stock_by_age"] = {
            "period": lp, "unit": "宅", "total": int(tot),
            "stock_mean_age": round(float(mean_age.iloc[0]), 2) if len(mean_age) else None,
            "ours_median_age": round(float(ages.median()), 1) if nb else None,
            "ours_n": nb, "rows": rows,
        }

    # ── mortgage ────────────────────────────────────────────────────────
    mr = M.load_series("mortgage_rate_new")
    if not mr.empty:
        nat = mr[(mr.county == "全國") & (mr.district == "") & mr.value.notna()]
        if not nat.empty:
            last = nat[nat.period == nat.period.max()].iloc[0]
            out["mortgage"] = {"rate": float(last.value), "period": last.period,
                               "zh": "本季新增購置住宅貸款平均利率（全國）",
                               "en": "Average rate on new house-purchase loans, national"}
    return out


def county_block(b):
    """The same table one level up.

    59 district rows in one fixed-height chart was the whole of the ranking, and
    at national scope it is a 1,594 px column a reader has to scroll to compare
    anything. Counties first, districts inside one — the same shape the map
    took. The n >= MIN_DISTRICT_N floor applies here too, for the same reason:
    ranking 澎湖縣 on 2 buildings would be inviting a comparison the data cannot
    support.
    """
    out = []
    for c, grp in b.groupby("county"):
        if len(grp) < MIN_DISTRICT_N:
            continue
        out.append({
            "county": c, "city": L.COUNTIES[c], "district": L.COUNTIES[c],
            "yield": median(grp.gross), "net": median(grp.net),
            "buildings": int(len(grp)),
            "districts": int(grp.district.nunique()),
            "price_ping": median(grp.price_ping),
            "rent_ping_yr": median(grp.rent_ping_yr),
            "q1": round(float(grp.gross.quantile(0.25)), 4),
            "q3": round(float(grp.gross.quantile(0.75)), 4),
        })
    out.sort(key=lambda x: x["yield"])
    return out


def district_block(b):
    out = []
    for (c, d), grp in b.groupby(["county", "district"]):
        if len(grp) < MIN_DISTRICT_N:
            continue
        out.append({
            "county": c, "city": L.COUNTIES[c], "district": d,
            "yield": median(grp.gross), "net": median(grp.net),
            "buildings": int(len(grp)),
            "price_ping": median(grp.price_ping),
            "rent_ping_yr": median(grp.rent_ping_yr),
            "q1": round(float(grp.gross.quantile(0.25)), 4),
            "q3": round(float(grp.gross.quantile(0.75)), 4),
        })
    out.sort(key=lambda x: x["yield"])
    return out


_CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}


def floors_to_int(v):
    """總樓層數 arrives as a Chinese numeral: 七層, 十四層, 二十五層."""
    if not isinstance(v, str) or not v:
        return None
    t = v.replace("層", "").strip()
    if not t:
        return None
    if t.isdigit():
        return int(t)
    if "十" not in t:
        return _CN_DIGIT.get(t)
    head, _, tail = t.partition("十")
    tens = _CN_DIGIT.get(head, 1) if head else 1
    ones = _CN_DIGIT.get(tail, 0) if tail else 0
    n = tens * 10 + ones
    return n if 0 < n < 200 else None


def attach_mrt(b, base):
    """Straight-line distance to the nearest MRT station, and its name.

    Proximity to a station is the covariate most people actually price property
    against, and the stations are already in the basemap -- so this costs one
    pass rather than another data source. Straight-line, not walking distance:
    the honest label is "distance to", not "walk to".
    """
    b = b.copy()
    stations = (base or {}).get("stations") or []
    if not stations or b.empty:
        b["mrt_m"] = None
        b["mrt_name"] = None
        b["mrt_heavy_m"] = None
        return b
    q = (base or {}).get("quant", 1)
    sx = np.array([s[0] * q for s in stations], dtype=float)
    sy = np.array([s[1] * q for s in stations], dtype=float)
    names = [s[2] for s in stations]
    # Heavy rail only (station=subway), excluding 輕軌. Shipped as a SECOND
    # distance rather than chosen between, because the choice decides the
    # result: on heavy rail alone 新北市 shows a 0.52pp gradient with separated
    # intervals; counting 淡海輕軌 -- which serves the outer 淡水 area that was
    # the far group -- collapses it to 0.01pp. The page shows both.
    heavy = [i for i, s in enumerate(stations) if len(s) < 4 or s[3] == 0]
    hx, hy = sx[heavy], sy[heavy]
    dm, nm, dh = [], [], []
    for x, y in zip(b.x, b.y):
        if x is None or (isinstance(x, float) and x != x):
            dm.append(None); nm.append(None); dh.append(None); continue
        fx, fy = float(x), float(y)
        d2 = (sx - fx) ** 2 + (sy - fy) ** 2
        i = int(np.argmin(d2))
        dm.append(int(round(float(np.sqrt(d2[i])))))
        nm.append(names[i])
        if len(hx):
            h2 = (hx - fx) ** 2 + (hy - fy) ** 2
            dh.append(int(round(float(np.sqrt(h2.min())))))
        else:
            dh.append(None)
    b["mrt_m"] = dm
    b["mrt_name"] = nm
    b["mrt_heavy_m"] = dh
    return b


def add_net_yield(b):
    """Per-building net yield at the default assumptions."""
    b = b.copy()
    b["age"] = 115.0 - b.built            # ROC years; window ends 115
    b["annual_rent"] = b.rent * 12.0
    b["price_abs"] = b.price_ping * b.area
    b["net"] = [
        net_yield(p, ar, ap, hm, ag, c)
        for p, ar, ap, hm, ag, c in zip(b.price_abs, b.annual_rent, b.area,
                                        b.has_mgr, b.age, b.county)
    ]
    return b


def build(last_season=LAST_SEASON):
    global WINDOW_FIRST
    seasons, raw_sales, raw_rents, sales, rents = load_window(last_season)
    WINDOW_FIRST = seasons[0]
    # The volume count sees every clean row, including the ones key_frames
    # drops for lacking a 門牌: it counts transactions, not buildings.
    sales_all, rents_all = sales, rents
    sales, rents, keystats = key_frames(sales, rents)
    # v2.1: the headline subtracts an imputed rent for un-itemised spaces (see
    # parking_audit_block for the test that made this the default). The
    # pre-imputation frame is kept for that block's tests and its old bound.
    rents_old = rents
    rents, imp_stats = impute_parking_rent(rents)
    print(f"[uw] parking rent imputed on {imp_stats.get('imputed_rows', 0):,} leases "
          f"({imp_stats.get('dropped_under_floor', 0)} fell under the floor)")
    P = load_presale_window(last_season)
    print(f"[uw] raw {len(raw_sales):,} sales / {len(raw_rents):,} rents"
          f"  -> clean {len(sales):,} / {len(rents):,}"
          f"  (no 門牌: {keystats['no_key_pct']}%)")

    index = district_price_index(sales)
    pairs = match_pairs(sales, rents, index=index if USE_PRICE_INDEX else None)
    b = add_net_yield(to_buildings(pairs))
    ub, uni_rows = universe_buildings(raw_sales, with_rows=True)
    # ONE type map. to_buildings takes the modal 建物型態 over a building's
    # MATCHED pairs; universe_buildings takes it over every sale that building
    # ever had, which is strictly more evidence. They disagreed on 6 of 9,805,
    # and because coverage_block reads its denominator from ub and its
    # numerator from b, those 6 were counted under one type in the numerator
    # and another in the denominator. Every matched building is in ub by
    # construction (it has a sale), so this join is total.
    _ubtype = dict(zip(zip(ub.county, ub.k), ub.bldg_type))
    _was = b.bldg_type.value_counts().to_dict()
    b["bldg_type"] = [_ubtype.get(k, t) for k, t in zip(zip(b.county, b.k), b.bldg_type)]
    _now = b.bldg_type.value_counts().to_dict()
    if _was != _now:
        print(f"[uw] type map single-sourced from the universe frame: {_was} -> {_now}")
    wf = coverage_waterfall(raw_sales, raw_rents, sales, b)

    # Geocode: a join against the government's own 門牌 file, not an API call.
    # If the source files are absent the build still succeeds and the page simply
    # has no map -- a missing basemap must never cost us the numbers.
    pts = G.build_points()
    b, geo_stats = G.attach(b, pts)
    grid = G.density_grid(set(ub.k), pts)

    # The ladder runs the same four matches anyway; capture its building sets so
    # the excluded layer costs no extra passes.
    _rungs = {}
    ladder = build_ladder(raw_sales, raw_rents,
                          index if USE_PRICE_INDEX else None, capture=_rungs)
    # The lease-side parking assumption, tested; same index as the headline or
    # the bounds sit on a different code path -- the ladder's exact lesson.
    pa_block, _ro = parking_audit_block(rents_old, rents, sales, pairs, b, raw_rents, ladder,
                                        imp_stats, index if USE_PRICE_INDEX else None)
    excluded = excluded_block(_rungs, pts, frozenset(zip(b.county, b.k)))
    print(f"[uw] excluded-but-drawable buildings: {len(excluded):,}")

    # The vacancy assumption, measured where it can be. Returns the block and a
    # per-building SHAPE multiplier (mean 1 on the matched set) that the page's
    # JS twin applies only in the shaped mode -- the headline path stays flat.
    # Computed here rather than inline in the payload dict because partial_id's
    # own copy quotes this same gap, and a number typed into two places is a
    # number that will disagree with itself -- it already had: the prose said
    # 8.5% while `age` published 2.7%.
    age_blk = age_block(uni_rows, b)
    print(f"[uw] matched vs unmatched (universe frame): ppp +{age_blk['ppp_diff_pct']}%, "
          f"unmatched n={age_blk['unmatched_n']:,}")

    vac_prior, vac_shape = vacancy_prior_block(b)
    if vac_prior:
        print(f"[uw] vacancy prior: matched-weighted low-use "
              f"{vac_prior['prior_pct']:.2f}% vs national {vac_prior['national_pct']:.2f}%; "
              f"net flat {vac_prior['cases'][0]['net']:.4f} -> "
              f"shaped {vac_prior['cases'][1]['net']:.4f} -> "
              f"level {vac_prior['cases'][2]['net']:.4f}")

    # What each filter is worth independent of the order the ladder applies it
    # in. Four of the eight cells are rungs the ladder already computed, so they
    # are asserted equal -- the ladder drifted from the real pipeline once
    # before, and this is the check that would have caught it.
    marg = filter_marginals(raw_sales, raw_rents, index if USE_PRICE_INDEX else None)
    if marg:
        _cells = {(g["social"], g["rooms"], g["related"]): g for g in marg["grid"]}
        _rung_cell = {"parking": (False, False, False), "social": (True, False, False),
                      "rooms": (True, True, False), "related": (True, True, True)}
        for _r in ladder:
            _c = _rung_cell.get(_r["key"])
            if _c and abs(_cells[_c]["pair"] - _r["yield"]) > 1e-9:
                raise AssertionError(
                    f"filter grid disagrees with ladder rung {_r['key']}: "
                    f"{_cells[_c]['pair']} vs {_r['yield']}")
        sh = marg["shapley"]
        print(f"[uw] filter marginals: social {sh['building']['social']:+.3f}pp, "
              f"rooms {sh['building']['rooms']:+.3f}pp, "
              f"related {sh['building']['related']:+.3f}pp (per building)")
    mech = marginal_mechanism(raw_sales, raw_rents, index if USE_PRICE_INDEX else None)

    # District outlines, parsed and projected in-process. Validated by checking
    # buildings land inside the district their own record names -- the only test
    # that catches a wrong datum or central meridian.
    shp_dir = os.path.join(os.path.dirname(G.CACHE) or "data", "geo", "twn")
    # Only the counties actually in this build: drawing all 368 districts when
    # the run is scoped to two cities would paint 327 grey polygons round them.
    # A county the registry reports as ONE district (嘉義市, 新竹市) must have its
    # polygons fused, or the table ranks a key no outline has. Derived from the
    # data, so it stays true if the registry ever changes its granularity.
    _names = b.groupby("county").district.unique()
    dissolve = {c for c, names in _names.items()
                if len(names) == 1 and names[0] == L.COUNTIES.get(c)}
    # SHIPPED tolerance is 150 m, not the 45 m the two-city map used.
    #
    # 365 districts at 45 m is 52,700 vertices, and the map draws the boundary
    # geometry TWICE (the filled polygon and the line over it), so the browser
    # was asked to rasterise ~110,000 vertices before a single building. It gave
    # up: the map rendered in the DOM with correct on-screen rects and painted
    # nothing. 150 m is still well under a screen pixel at every zoom this map
    # opens at nationally, and keeps all 365 records.
    #
    # boundaries.validate() must NEVER be pointed at this geometry -- containment
    # falls 99.88% -> ~99% purely from simplification, which would look like a
    # broken projection. The test builds its own 45 m set for that.
    districts_geo = (BD.build(shp_dir, tolerance=150.0, counties=set(L.COUNTIES),
                              dissolve=dissolve)
                     if os.path.isdir(shp_dir) else [])
    # One outline per county, so the national view can draw 臺南市 as a single
    # block instead of the 37 shapes it is made of. 3,836 points for all 22.
    counties_geo = (BD.dissolve_counties(shp_dir, counties=set(L.COUNTIES))
                    if os.path.isdir(shp_dir) else [])
    if dissolve:
        print(f"[bnd] fused to city level: {sorted(dissolve)}")
    base_layers = BM.build()
    b = attach_mrt(b, base_layers)
    # the building's median rent under the OLD treatment, area only (NaN where
    # absent, never a list with None -- see the mrt comment)
    b["rent_old"] = [_ro.get(k, np.nan) for k in zip(b.county, b.k)]
    print(f"[uw] {len(pairs):,} pairs -> {len(b):,} buildings"
          f"  (price index {'ON' if USE_PRICE_INDEX else 'OFF'})")

    # Measure the correction we chose NOT to apply, so the page can show why.
    index_test = []
    for w in (2, 4):
        for label, ix in (("off", None), ("on", index)):
            gs = gap_sensitivity(match_pairs(sales, rents, window=w, index=ix))
            if len(gs) >= 2:
                index_test.append({
                    "window": w, "index": label,
                    "slope": round(gs[-1]["yield"] - gs[0]["yield"], 3),
                    "buildings": gs[-1]["buildings"] + gs[0]["buildings"],
                })

    _fasc = fasc_block(sales, last_season=last_season)
    payload = {
        "meta": {
            "seasons": [seasons[0], seasons[-1]],
            "n_seasons": len(seasons),
            "generated_from": "內政部不動產成交案件實際資訊資料供應系統",
            "licence": "政府資料開放授權條款-第1版",
            "match_window_q": MATCH_WINDOW_Q,
            "min_district_n": MIN_DISTRICT_N,
            "price_index_on": USE_PRICE_INDEX,
            "clean_sales": int(len(sales)), "clean_rents": int(len(rents)),
            "raw_sales": int(len(raw_sales)), "raw_rents": int(len(raw_rents)),
            "addr": keystats,
            "geo": geo_stats,
            # Everything needed to tell a rebuild that disagrees apart from a
            # bug. See docs/REPRODUCING.md.
            "provenance": {
                "version": PAYLOAD_VERSION,
                "built": datetime.date.today().isoformat(),
                "commit": git_commit(),
                "source": source_manifest(seasons),
                "refs": ref_manifest(),
            },
        },
        "headline": {
            "yield": median(b.gross),
            "net": median(b.net),
            "buildings": int(len(b)),
            "pairs": int(len(pairs)),
            "pair_level_yield": median(pairs.gross),
            # The denominator that keeps the headline honest: matched buildings
            # as a share of every building with a recorded sale.
            "universe_buildings": wf["universe"],
            "coverage_pct": wf["coverage_pct"],
            "coverage_ceiling_pct": wf["ceiling_pct"],
        },
        # Same index setting as the headline, or the last rung is not the
        # headline's code path and the ladder quietly lies about itself.
        "ladder": ladder,
        # The ladder is a path; these are the filters. Kept next to each
        # other on purpose -- the page has to show both or it repeats the
        # claim that the path IS the measurement, which is what went wrong.
        "filter_marginals": marg,
        "marginal_mechanism": mech,
        "districts": district_block(b),
        "counties": county_block(b),
        "mortgage": MORTGAGE_RATE,
        # Three reference rates beside the net yield. Different denominators:
        # set side by side, never differenced (the page rule).
        "benchmarks": benchmarks_block(),
        "within_building": within_building_block(rents, sales=sales),
        "auction": _fasc,
        # 內政部's own series beside this site's numbers: 法拍 the auction
        # section admits it cannot see, the housing stock behind the page's
        # denominator, and an official price per 坪 against ours.
        "moi": moi_block(seasons, b, ub, _fasc),
        "presale": presale_block(sales, last_season, P=P),
        # Counts, not yields. Fixed same+1-season horizon so quarters compare;
        # the official 棟 series sits beside it in its own figure, never divided.
        "volume": volume_block(sales_all, rents_all, P, seasons),
        "income": income_block(ub, b),
        "coverage": coverage_block(ub, b),
        # What seeing 6% of them permits anyone to say: a ladder of bounds,
        # each rung one more rejectable assumption. Scope is this site's own
        # frame and unit; no rung speaks about Taiwan.
        "partial_id": partial_id_block(b, ub, ppp_gap_pct=age_blk.get("ppp_diff_pct")),
        # The UNIVERSE row frame, not the cleaned one. coverage_block moved to
        # the universe in v2.2 and this did not, so the page stated 147,789
        # unmatched buildings in one section and compared 100,800 of them in
        # another -- and the cleaned frame drops exactly the cheaper stock
        # (un-itemised parking, related-party), so the selection effect it
        # published was understated more than threefold: 2.7% against 8.5%.
        "age": age_blk,
        "dead_hypothesis": dead_hypothesis_block(b),
        # The other half of that hypothesis. dead_hypothesis keeps every key and
        # its 'alive' verdict -- the rung this one builds on; corrections accrete.
        "walkup_resolution": walkup_resolution_block(b, ub, uni_rows, pairs),
        "rent_bias": L.social_vs_market_rents(raw_rents),
        "coverage_waterfall": wf,
        "post_strat": post_stratify(b, ub),
        "bootstrap": bootstrap_cis(pairs, b),
        "dispersion": dispersion(pairs, b),
        "repairs_spec": repairs_specification(b),
        # The management fee is sourced for two cities and charged to 22. Not
        # corrected -- there is nothing to correct it with -- but measured, the
        # same way the vacancy assumption is.
        "mgmt_exposure": mgmt_exposure(b),
        # The fee is charged on one registry field (有無管理員); this reports what
        # a second field (備註) says about who pays it. Two bounds, headline untouched.
        "mgmt_flag": mgmt_flag_block(rents, pairs, b),
        # Un-itemised parking rent: a stated assumption in fetch_lvr._subtract_parking,
        # tested within building. Verdict + three treatments as bounds; headline untouched.
        "parking_audit": pa_block,
        # A SPACE is the unit, not a 坪; the dwelling headline is copied in for
        # the side-by-side and never subtracted.
        "parking": parking_block(raw_sales, raw_rents,
                                 {"yield": median(b.gross), "buildings": int(len(b))}),
        "vacancy_breakeven": vacancy_breakeven(b),
        # The 5% vacancy guess, measured where it CAN be measured. The level
        # stays an assumption; the shape comes from 低度使用(用電)住宅, and
        # the literal-level case is published as a bound, not adopted.
        "vacancy_prior": vac_prior,
        "map": {
            "grid": grid,
            # The colour ramp's DOMAIN travels with the data. Hard-coded at the
            # Taipei spread it clamped every building above 3.6% to the top step,
            # which paints higher-yield cities one flat colour and calls it a
            # ramp. 5th/95th percentile, so a handful of outliers cannot flatten
            # the middle where nearly every building actually sits.
            "ramp": ([round(float(b.gross.quantile(0.05)), 2),
                      round(float(b.gross.quantile(0.95)), 2)]
                     if len(b) >= 20 else [1.6, 3.6]),
            # A ramp per LEVEL, because each level colours a different quantity.
            #
            # Individual buildings spread 1.55-5.00%; county MEDIANS spread
            # 2.06-3.68%. Colouring counties on the building ramp put 7 of 14 of
            # them on one step and used 4 of the 6 colours, so the national map
            # was very nearly monochrome — the choropleth carried no information
            # at the only zoom most readers will ever see.
            "ramp_county": _median_ramp(b, ["county"]),
            "ramp_district": _median_ramp(b, ["county", "district"]),
            "bounds": ([int(b.x.min()), int(b.y.min()), int(b.x.max()), int(b.y.max())]
                       if b.x.notna().any() else None),
            "districts": districts_geo,
            "counties": counties_geo,
            # [x, y, type, why] — why: 1 parking, 2 social housing, 3 room-share.
            "excluded": excluded,
            "labels": BD.centroids(districts_geo) if districts_geo else {},
            "base": base_layers,
        },
        "gap_sensitivity": gap_sensitivity(pairs),
        "index_test": index_test,
        "concentration": concentration(pairs),
        "histogram": histogram(b.gross),
        "histogram_net": histogram(b.net, lo=-1.0, hi=5.0),
        "assumptions": cost_assumptions(),
        "buildings": [{
            "a": row.k, "c": row.county, "d": row.district,
            "t": row.bldg_type, "y": round(float(row.gross), 3),
            "nt": None if row.net is None else round(float(row.net), 3),
            "p": int(round(row.price_ping)), "r": int(round(row.rent_ping_yr)),
            "n": int(row.pairs), "b": None if pd.isna(row.built) else int(row.built),
            "m": int(row.has_mgr), "mf": int(row.mgmt_incl_any),
            "ro": None if pd.isna(row.rent_old) else int(round(row.rent_old)),
            # 2dp, not 1. The page recomputes the net yield live from these
            # fields, and area is the dominant rounding error in that twin:
            # 0.05坪 on a ~30坪 median is 0.17% relative, against 0.002% for
            # rent and 0.000005% for price. At 1dp the twin's median landed
            # 6.8e-4 from the payload's -- normally invisible, but it straddled
            # a 2dp boundary and the hero displayed 1.74% beside a payload,
            # a PDF and a prose paragraph all saying 1.73%.
            "ar": round(float(row.area), 2),
            "pa": int(round(row.price_abs)), "rm": int(round(row.rent)),
            # vacancy SHAPE multiplier, mean 1 across the matched set. The page
            # applies it only in the shaped mode; the headline stays flat. It is
            # a function of the county alone while the county leg is the only
            # one sourced, and per-building so an age or size leg needs no
            # payload change.
            "vs": vac_shape.get((row.county, row.k)),
            # mx/my, NOT x/y: "y" is already the gross yield on this record and a
            # dict literal silently lets the later key win, which blanked the
            # yield on every building.
            "mx": None if pd.isna(row.x) else int(row.x),
            "my": None if pd.isna(row.y) else int(row.y),
            "fl": floors_to_int(row.floors) if isinstance(row.floors, str) else None,
            # int(), not the raw cell: assigning a list containing None to a
            # pandas column coerces the whole column to float64 and turns the
            # Nones into NaN -- which json.dump then writes as a bare `NaN`,
            # producing a payload no browser will parse.
            "mrt": None if pd.isna(row.mrt_m) else int(row.mrt_m),
            # Heavy rail only. Ships beside `mrt` so the page can show what the
            # 輕軌 judgement is worth instead of silently making it.
            "mrth": None if pd.isna(getattr(row, "mrt_heavy_m", None))
                    else int(row.mrt_heavy_m),
            "mrts": None if not isinstance(row.mrt_name, str) else row.mrt_name,
        } for row in b.itertuples()],
    }
    return payload
def concentration(pairs):
    """How lopsided the pair counts are — the case for building-level stats."""
    if pairs.empty:
        return {}
    per = pairs.groupby("k").size().sort_values(ascending=False)
    return {
        "total_pairs": int(per.sum()),
        "buildings": int(len(per)),
        "median_per_building": int(per.median()),
        "max_per_building": int(per.max()),
        "top10_share": round(float(per.head(10).sum() / per.sum() * 100), 1),
    }


def histogram(vals, lo=0.0, hi=6.0, bins=24):
    v = pd.Series(vals).dropna()
    counts, edges = np.histogram(v.clip(lo, hi), bins=bins, range=(lo, hi))
    return [{"x0": round(float(edges[i]), 2), "x1": round(float(edges[i + 1]), 2),
             "n": int(counts[i])} for i in range(len(counts))]


if __name__ == "__main__":
    p = build()
    # allow_nan=False turns a stray NaN/Infinity into a build-time exception
    # instead of a bare `NaN` token in the payload -- which is not valid JSON,
    # fails silently in fetch().json(), and renders as a blank page.
    blob = json.dumps(p, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")
    with open(OUT, "wb") as f:
        f.write(blob)
    # Ship a pre-built .gz alongside it. The map pushed the payload to ~900 KB,
    # and flask-compress is an optional import that is simply absent in some
    # environments -- so compressing at build time is both guaranteed and free
    # at request time, instead of being a runtime dependency that silently
    # does nothing.
    with gzip.open(OUT + ".gz", "wb", compresslevel=9) as f:
        f.write(blob)
    # The payload cannot carry its own digest, so it ships beside it. This is
    # the file a reader checks with `shasum -a 256 -c housing_data.json.sha256`.
    digest = hashlib.sha256(blob).hexdigest()
    with open(OUT + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{digest}  {os.path.basename(OUT)}\n")
    raw, gz = os.path.getsize(OUT), os.path.getsize(OUT + ".gz")
    print(f"[uw] wrote {OUT} ({raw/1e3:.0f} KB, gzipped {gz/1e3:.0f} KB "
          f"= {gz/raw*100:.0f}%)")
    _pv = p["meta"]["provenance"]
    print(f"[uw] v{_pv['version']}  built {_pv['built']}  commit {_pv['commit']}")
    print(f"[uw] source sha256  {_pv['source']['sha256']}")
    print(f"[uw] payload sha256 {digest}")
    print(f"[uw] headline {p['headline']['yield']}% "
          f"across {p['headline']['buildings']:,} buildings")
    for r in p["ladder"]:
        print(f"     {r['key']:9s} {r['yield']:.2f}%  "
              f"pairs {r['pairs']:6,}  bldgs {r['buildings']:5,}")
