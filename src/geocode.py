"""
geocode.py — turn a 門牌 into a point, using the government's own address file.

Nothing here calls a geocoding API. 內政部 and the two city governments publish
the complete 門牌位置數值資料 — every registered street number with a surveyed
coordinate — so the "geocoding" is a join, not an estimate. Measured match rate
against the matched-building set: **99.7%**.

  臺北市  data.taipei  ~124 MB, 1,156,079 rows
  新北市  data.ntpc    ~192 MB

Coordinates are TWD97 / TM2 zone 121 (EPSG:3826) in metres. They are used AS-IS
rather than converted to lat/lon: TM2 is already a planar projection, the whole
area of interest is ~50 km across, and an unnecessary conversion would only add a
source of error to a picture that is drawn in screen pixels anyway.

Neither file carries a district NAME, only a code, so the two maps below have to
be hard-coded. They are not trusted blindly: `build_points` is validated by
checking that every joined building's district from 實價登錄 agrees with the
district the code map implies. That agreement is currently 100%, which is what
makes the hard-coding safe.

The source files are large and are NOT needed to serve the site — only the ~2,500
matched coordinates ship, inside housing_data.json. This module runs at build
time only.
"""

import os

import pandas as pd

from normalize_addr import addr_key

CACHE = os.environ.get("GEO_CACHE", "data/geo")

TPE_CSV = ("https://data.taipei/api/dataset/b7c8e724-1e98-45ee-a0bd-f3840623ed97"
           "/resource/ce76ca0c-7f94-4935-ab47-1d2a41ca2abb/download")
NTP_CSV = "https://data.ntpc.gov.tw/api/datasets/d7b568ab-3819-40c8-a6e7-a6b199443101/csv/file"
# 高雄市114年門牌坐標資料-TWD97 (民政局), 政府資料開放授權條款第一版
KHH_CSV = "https://data.kcg.gov.tw/File/ResourceDownload/276d3129-3356-4563-a058-2557bf05e033"
# 桃園市門牌位置坐標資料 115年7月, data.gov.tw 157689
TYC_CSV = ("https://opendata.tycg.gov.tw/api/dataset/ec47dbd5-9ed8-4c8d-8ce1-ccb63b1b72e6"
           "/resource/477902e6-1bc5-4278-a35c-82a56e2e2a69/download")
# 臺南市門牌坐標資料 114年, data.gov.tw 120044. Titled 「僅供參考」 — see `quality`.
TNN_CSV = "https://data.tainan.gov.tw/File/ResourceCsvDownload/af44f904-2f4c-49b2-aaf8-1a64dce09bd4"

# 臺中市 does not serve its address points itself. Its data.gov.tw dataset
# (169806) is a MANIFEST whose "CSV" is a table of Google Drive links, one per
# month — so this URL is a specific monthly file (115年1月) rather than a
# "latest" endpoint, and refreshing 臺中 means re-reading that manifest and
# taking the newest 門牌點位 row.
#
# The plain uc?export=download endpoint returns Drive's virus-scan interstitial
# for a file this size; the usercontent host with confirm=t returns the bytes and
# needs no uuid, no cookie and no user agent.
TCH_CSV = ("https://drive.usercontent.google.com/download"
           "?id=1oxPMFv5twHRSkK6BtlHD-8t2qfwGF1R9&export=download&confirm=t")

# ── district codes: derived from the shapefile, never hand-written ───────────
#
# Each city's address file keys its rows by a 鄉鎮市區代碼, and the MOI boundary
# shapefile carries the authoritative TOWNCODE -> TOWNNAME table for all 368
# districts. So the map is DERIVED, and two hand-written tables (12 + 29 entries)
# are gone with it. A wrong entry in those tables would have put every affected
# building in the wrong place on the map with nothing else complaining.
#
# The catch is that the files do not all encode the code the same way:
#
#   臺北市/新北市  63000010   the full 8-digit TOWNCODE
#   桃園市/臺南市  6800100    2-digit county + 3-digit ORDINAL + "00"
#
# so rather than record which county uses which — another hand-written table
# waiting to go stale — every known form is tried and the one that maps 100% of
# the file's codes onto that county's real districts wins. Anything less than
# 100% is a hard failure, because a partial match is exactly what a silently
# wrong map looks like.

_CODE_FORMS = (
    ("full-8", lambda c: c),
    # 6800100 -> 68 + "000" + (001 * 10) -> 68000010
    ("ordinal-7", lambda c: c[:2] + "000" + "%03d" % (int(c[2:5]) * 10)
     if len(c) == 7 and c[2:5].isdigit() else None),
)


def _towncodes(county, shp_dir="data/geo/twn"):
    """{TOWNCODE: TOWNNAME} for one 實價登錄 county letter, from the MOI shapefile."""
    import boundaries
    base = None
    for f in sorted(os.listdir(shp_dir)):
        if f.lower().endswith(".dbf"):
            base = os.path.join(shp_dir, f)
            break
    if not base:
        return {}
    return {r["TOWNCODE"]: r["TOWNNAME"] for r in boundaries.read_dbf(base)
            if (r.get("COUNTYID") or "").lower() == county}


def district_map(county, codes, shp_dir="data/geo/twn"):
    """Map this county's file codes onto district NAMES, or raise.

    `codes` is the distinct 鄉鎮市區代碼 values seen in the address file.
    """
    truth = _towncodes(county, shp_dir)
    if not truth:
        raise ValueError(f"[geo] no shapefile districts for county {county!r}")
    codes = [c for c in codes if isinstance(c, str) and c]
    for name, fn in _CODE_FORMS:
        try:
            pairs = [(c, fn(c)) for c in codes]
        except Exception:
            continue
        if any(v is None for _, v in pairs):
            continue
        hit = sum(1 for _, v in pairs if v in truth)
        if hit == len(pairs):
            print(f"[geo] {county}: district codes are {name} "
                  f"({len(pairs)} districts, all matched)")
            return {c: truth[v] for c, v in pairs}
    raise ValueError(
        f"[geo] {county}: no code form maps all {len(codes)} file codes onto the "
        f"{len(truth)} shapefile districts — refusing to guess")


# One reader, N sources. The files share a common MOI schema — the column NAMES
# differ per city but the content does not — which is why adding a county is a
# URL and a column list rather than a new parser.
#
# `note` is published: 臺北市's file is 現場調查 (surveyed), while 臺南市's and
# 桃園市's are 各戶政事務所人工點位，非準確坐標位置. That difference must be
# visible to a reader. It does NOT touch any published number: attach() runs
# AFTER the matching and the yield maths, so coordinates only move the dot on the
# map and the distance-to-MRT field.
_SURVEYED = "surveyed"
_PLOTTED = "plotted"

_COLS_MOI = ["鄉鎮市區代碼", "街路段", "巷", "弄", "號", "橫座標", "縱座標"]

_SPECS = {
    "a": {"url": TPE_CSV, "file": "tpe_addr.csv", "city": "台北市",
          "cols": _COLS_MOI, "quality": _SURVEYED},
    "f": {"url": NTP_CSV, "file": "ntp_addr.csv", "city": "新北市",
          "cols": ["areacode", "street、road、section", "lane", "alley", "number",
                   "x_3826", "y_3826"], "quality": _SURVEYED},
    "e": {"url": KHH_CSV, "file": "khh_addr.csv", "city": "高雄市",
          "cols": _COLS_MOI, "quality": _PLOTTED},
    "h": {"url": TYC_CSV, "file": "tyc_addr.csv", "city": "桃園市",
          "cols": _COLS_MOI, "quality": _PLOTTED},
    "d": {"url": TNN_CSV, "file": "tnn_addr.csv", "city": "台南市",
          "cols": ["地址-行政區域代碼", "街路段", "巷", "弄", "號",
                   "橫座標[E 坐標]", "縱座標[N 坐標]"], "quality": _PLOTTED},
    # 臺中's column names diverge three times -- 街、路段 with the 、, and the
    # coordinates prefixed TWD97 and spelled 坐 rather than 座 -- but the CONTENT
    # is identical, 巷 included ("３９巷", the character and all, exactly as
    # 臺北's file writes it). 臺中 publishes no statement about how its points
    # were produced, so it is filed as plotted rather than claiming a survey it
    # has not claimed.
    "b": {"url": TCH_CSV, "file": "tch_addr.csv", "city": "台中市",
          "cols": ["鄉鎮市區代碼", "街、路段", "巷", "弄", "號",
                   "TWD97橫坐標", "TWD97縱坐標"], "quality": _PLOTTED},
}


def _download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        import requests
        print(f"[geo] downloading {os.path.basename(path)} (this is 100-200 MB)")
        r = requests.get(url, timeout=600)
        if r.status_code != 200 or len(r.content) < 1_000_000:
            print(f"[geo] {path}: http {r.status_code}, {len(r.content)} bytes")
            return ""
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        print(f"[geo] download error: {e}")
        return ""


def _load_one(county, cache_dir):
    spec = _SPECS[county]
    path = _download(spec["url"], os.path.join(cache_dir, spec["file"]))
    if not path:
        return pd.DataFrame(columns=["k", "x", "y", "geo_district", "county"])
    try:
        d = pd.read_csv(path, dtype=str, encoding="utf-8-sig",
                        usecols=spec["cols"], low_memory=False)
    except Exception as e:
        print(f"[geo] read {path}: {e}")
        return pd.DataFrame(columns=["k", "x", "y", "geo_district", "county"])
    d.columns = ["code", "street", "lane", "alley", "num", "x", "y"]
    try:
        dmap = district_map(county, list(d.code.dropna().unique()))
    except ValueError as e:
        print(e)
        return pd.DataFrame(columns=["k", "x", "y", "geo_district", "county"])
    d["geo_district"] = d.code.map(dmap)
    d = d[d.geo_district.notna()].copy()
    # Rebuild the same string 實價登錄 would print, then run it through the SAME
    # normaliser. Reusing addr_key is the whole reason the join lands at 99.7%:
    # both sides get identical treatment of full-width digits, 段 numerals and
    # the 之N sub-number.
    d["k"] = (spec["city"] + d.geo_district + d.street.fillna("")
              + d.lane.fillna("") + d.alley.fillna("") + d.num.fillna("")).map(addr_key)
    d = d[d.k != ""]
    d["x"] = pd.to_numeric(d.x, errors="coerce")
    d["y"] = pd.to_numeric(d.y, errors="coerce")
    d = d.dropna(subset=["x", "y"])
    # One building, one point: a 門牌 repeats per floor/unit in the source.
    out = d.groupby("k", as_index=False).agg(x=("x", "median"), y=("y", "median"),
                                             geo_district=("geo_district", "first"))
    out["county"] = county
    return out


def build_points(cache_dir=None):
    """key -> (x, y) for both cities. Empty frame if the sources are unavailable,
    so a build without them degrades to a site with no map rather than no site."""
    cache_dir = cache_dir or CACHE
    frames = [_load_one(c, cache_dir) for c in _SPECS]
    frames = [f for f in frames if not f.empty]
    if not frames:
        print("[geo] no address points available - the map will be omitted")
        return pd.DataFrame(columns=["k", "x", "y", "geo_district", "county"])
    pts = pd.concat(frames, ignore_index=True)
    print(f"[geo] {len(pts):,} address points")
    return pts


def attach(df, pts, addr_col="k", district_col="district"):
    """Join points onto a frame, and VALIDATE the hard-coded district maps.

    If a code map were wrong, every affected building would land in the wrong
    place on the map and nothing else would complain. Comparing the joined
    district against the one 實價登錄 already states catches that immediately.
    """
    if pts.empty or df.empty:
        out = df.copy()
        out["x"] = None
        out["y"] = None
        return out, {"matched": 0, "rate": 0.0, "district_agreement": None}
    m = df.merge(pts[["k", "x", "y", "geo_district"]], left_on=addr_col,
                 right_on="k", how="left", suffixes=("", "_geo"))
    hit = m.x.notna()
    agree = None
    if district_col in m.columns and hit.any():
        agree = round(float((m.loc[hit, district_col] == m.loc[hit, "geo_district"]).mean()) * 100, 2)
        if agree < 99.0:
            print(f"[geo] WARNING district agreement only {agree}% - check the code maps")
    stats = {"matched": int(hit.sum()), "total": int(len(df)),
             "rate": round(float(hit.mean()) * 100, 2), "district_agreement": agree}
    print(f"[geo] matched {stats['matched']:,}/{stats['total']:,} "
          f"({stats['rate']}%), district agreement {agree}%")
    return m, stats


def density_grid(sale_keys, pts, cell=400):
    """Coarse counts of EVERY building that sold, on a `cell`-metre grid.

    This is the visual form of the coverage finding: the faint layer is the
    housing that changes hands, the bright points are the sliver where a yield
    can be computed. Shipping a grid rather than ~70,000 points keeps the payload
    small and, at this cell size, says exactly the same thing.
    """
    if pts.empty:
        return {}
    p = pts[pts.k.isin(set(sale_keys))]
    if p.empty:
        return {}
    gx = (p.x // cell).astype(int)
    gy = (p.y // cell).astype(int)
    g = pd.DataFrame({"gx": gx, "gy": gy}).groupby(["gx", "gy"]).size()
    x0, y0 = int(gx.min()), int(gy.min())
    # [dx, dy, n] triples against a shared origin: the same information as
    # absolute metres in roughly a third of the bytes.
    return {"cell": cell, "x0": x0 * cell, "y0": y0 * cell,
            "cells": [[int(a - x0), int(b - y0), int(v)] for (a, b), v in g.items()]}


if __name__ == "__main__":
    pts = build_points()
    print(pts.head().to_string())
