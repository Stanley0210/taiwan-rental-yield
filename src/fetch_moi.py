# -*- coding: utf-8 -*-
"""
fetch_moi.py — county-level statistical series from 內政部不動產資訊平台.

https://pip.moi.gov.tw/Publicize/Info/E3030 carries 112 quarterly series as
CSV, county by county, back to 民國98 (2009). This module pulls the handful the
housing page can use to check itself against an official figure, and caches
them under data/ref/moi/.

WHY THESE. Every one either fills a gap the page already admits, or replaces a
number the page types in:

  法院拍定成屋   the auction section says outright that it sees 金拍 only and
                that 法拍 is much larger. This is 法拍, by county, by quarter.
  住宅存量       the page's denominator is "buildings with a sale record". The
  建物總量       housing stock is the denominator a reader actually means, and
                it is much larger — which makes the page's central claim
                stronger, not weaker.
  買賣契約價格   an official average sale price per 坪, by county and building
  平均單價       type, in 萬元. An external check on the page's own price medians.
  購置住宅貸款   the average new-mortgage rate, quarterly. A second official
  平均利率       series beside the Central Bank figure the page already cites.
  建物買賣移轉   the official registration count the volume section sets beside
  登記棟數       the registry's contract-dated rows. 棟, by registration quarter
                 -- a different unit and a different clock, so it is drawn in
                 its own figure and never divided into the registry counts.

HOW THE EXPORT WORKS. The CSV links on the page are `a.cmd-link` elements with
`data-keyk` / `data-keyn` / `data-keyt`; their click handler sets
Command=匯出CSV檔 plus K, N, T on the page's form and posts back to the same
URL. No __VIEWSTATE is needed. Two things stop a naive fetch:

  * Python 3.13 enables VERIFY_X509_STRICT, and the MOI certificate carries no
    Subject Key Identifier, so the handshake fails. `_RelaxedX509` clears that
    one flag. Certificate and hostname verification stay ON — this is not
    verify=False, and must not become it.
  * A WAF rejects requests without browser-like headers. The set below passes.

The server says charset=big5 and ships UTF-8 with a BOM. County names use 台
where the rest of the pipeline uses 臺; `_tw()` normalises.

Licence: 政府資料開放授權條款-第1版, same as the registry data.
"""
import io
import os
import re
import ssl
import time

import pandas as pd

CACHE = os.environ.get("MOI_CACHE", "data/ref/moi")
URL = "https://pip.moi.gov.tw/Publicize/Info/E3030"

# key -> (T, K, N, zh, en, unit)
SERIES = {
    "court_auction_n":   ("4", "2", "1", "法院拍定成屋總件數", "Court-auction sales (lots)", "件"),
    "court_auction_amt": ("4", "2", "2", "房地拍定總金額", "Court-auction sales, total value", "元"),
    "resi_auction_n":    ("4", "4", "1", "住宅拍賣移轉筆數", "Residential auction transfers", "筆"),
    "housing_stock":     ("2", "5", "1", "住宅存量", "Housing stock", "宅"),
    # NOT 棟. 建物總量 exceeds 住宅存量 in every county (臺北市 1.16x at
    # 114Q4), and no count of physical buildings can exceed the count of
    # dwellings in a tower city: these are registered 建號, roughly one per
    # unit. Mislabelling this series is what produced the withdrawn "one
    # building in 1,086", so it is labelled correctly HERE, at the source.
    "building_stock":    ("2", "1", "1", "建物總量（登記建號，約一戶一筆）",
                          "Registered buildings (建號, roughly one per unit)", "建號"),
    "resi_tax_roll":     ("2", "2", "1", "房屋稅籍住宅類數量",
                          "Residential buildings on the house-tax roll", "宅"),
    "mortgage_rate_new": ("5", "3", "2", "本季新增購置住宅貸款平均利率",
                          "New-mortgage average rate (quarter)", "%"),
    "sale_price_ping":   ("3", "1", "1", "買賣契約價格平均單價",
                          "Contract sale price per ping", "元/坪"),
    "sale_transfers":    ("4", "1", "3", "建物買賣移轉登記棟數",
                          "Building sale transfers registered", "棟"),
    # 租金單價-分租雅房、住家、套房、獨套 [3,3,1] looked like the best series in the
    # catalogue -- an official rent per 坪 split by exactly the 出租型態 categories
    # behind the ladder's Simpson reversal. It runs 098Q1..102Q4 and stops.
    # Three counties, nothing after 2013. Fetched, checked, not used.
}

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Origin": "https://pip.moi.gov.tw",
    "Referer": URL,
}


def _session():
    import certifi
    import requests
    from requests.adapters import HTTPAdapter

    class _RelaxedX509(HTTPAdapter):
        def init_poolmanager(self, *a, **kw):
            ctx = ssl.create_default_context(cafile=certifi.where())
            ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
            kw["ssl_context"] = ctx
            return super().init_poolmanager(*a, **kw)

    s = requests.Session()
    s.mount("https://", _RelaxedX509())
    s.headers.update(_HEADERS)
    return s


def _tw(s):
    return s.replace("台", "臺") if isinstance(s, str) else s


def fetch_series(key, cache_dir=None, force=False):
    """Export one series to the cache. Returns the path, or '' on failure."""
    if key not in SERIES:
        raise KeyError(f"unknown MOI series {key!r}; known: {sorted(SERIES)}")
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{key}.csv")
    if os.path.exists(path) and not force and os.path.getsize(path) > 500:
        return path
    t, k, n, zh, _, _ = SERIES[key]
    try:
        s = _session()
        s.get(URL, timeout=60)                      # cookies first, or the WAF bites
        for attempt in range(3):
            r = s.post(URL, data={"Command": "匯出CSV檔", "T": t, "K": k, "N": n},
                       timeout=120)
            ok = (r.status_code == 200 and "csv" in r.headers.get("Content-Type", "")
                  and len(r.content) > 500)
            if ok:
                with open(path, "wb") as f:
                    f.write(r.content)
                print(f"[moi] {key} ({zh}): {len(r.content)/1e3:.0f} KB")
                return path
            print(f"[moi] {key}: http {r.status_code}, "
                  f"{r.headers.get('Content-Type')}, {len(r.content)} bytes — retry")
            time.sleep(8 * (attempt + 1))
        return ""
    except Exception as e:
        print(f"[moi] {key}: {e}")
        return ""


def load_series(key, cache_dir=None):
    """A tidy frame: period ('112Q4'), county (臺-normalised), value.

    Four layouts exist in the catalogue and all come back as
    period, county, district, kind, value -- with district and kind '' where
    the series has no such dimension:

      period, county, value                          most series
      period, county, 鄉鎮市區, value                 建物總量, 住宅拍賣移轉筆數 -- district
                                                     rows, county total on a blank district
      period, county, 鄉鎮市區, 建物類型, value       買賣契約價格 -- a category column
      period, county, <k1>, <k2>, ...                one value column per category -> melted
    """
    path = fetch_series(key, cache_dir)
    if not path:
        return pd.DataFrame()
    txt = open(path, "rb").read().decode("utf-8-sig", errors="replace")
    df = pd.read_csv(io.StringIO(txt), dtype=str, keep_default_na=False)
    df = df.rename(columns={df.columns[0]: "period", df.columns[1]: "county"})
    df["county"] = df["county"].map(_tw)
    # The export itself is not clean. In 買賣契約價格平均單價, 335 rows arrive with
    # the columns SHUFFLED -- period, 建物類型, county, district, value -- every
    # one carrying 0.00. A building type in the county column is the tell.
    _TYPES = {"公寓", "別墅", "套房", "透天厝", "電梯大廈", "樓中樓", "住宅大樓", "華廈"}
    bad = df["county"].isin(_TYPES)
    if bad.any():
        print(f"[moi] {key}: dropped {int(bad.sum())} rows with shuffled columns "
              f"(a building type where the county should be; all value 0)")
        df = df[~bad]
    # Dimension columns the catalogue uses, by name. Anything else after
    # county is a value column (one, or several to be melted into `kind`).
    DIMS = {"鄉鎮市區": "district", "建物類型": "kind"}
    for zh, en in DIMS.items():
        if zh in df.columns:
            df = df.rename(columns={zh: en})
            df[en] = df[en].map(_tw)
    if "district" not in df.columns:
        df["district"] = ""
    ids = [c for c in ("period", "county", "district", "kind") if c in df.columns]
    value_cols = [c for c in df.columns if c not in ids]
    if len(value_cols) == 1:
        out = df.rename(columns={value_cols[0]: "value"})
        out["value"] = pd.to_numeric(out["value"].str.replace(",", ""), errors="coerce")
        if "kind" not in out.columns:
            out["kind"] = ""
        return out[["period", "county", "district", "kind", "value"]]
    long = df.melt(id_vars=ids, value_vars=value_cols, var_name="kind", value_name="value")
    long["value"] = pd.to_numeric(long["value"].str.replace(",", ""), errors="coerce")
    return long[["period", "county", "district", "kind", "value"]]


# ── series that live as HTML tables on their own pages, not in the catalogue ─
#
# Same tidy shape out (period, county, district, kind, value), scraped from a
# page rather than exported. `head0` is the text of the table's first header
# cell, which is how the right table is picked out of the several on a page.

HTML_SERIES = {
    # 住宅價格指數, 基期 105年 = 100. 101Q3 onward, 全國 + six municipalities.
    "price_index": ("https://pip.moi.gov.tw/Publicize/Info/E1060", "縣市",
                    "住宅價格指數", "House-price index (105年 = 100)", "index"),
    # 低度使用(用電)住宅 -- dwellings drawing very little electricity. Half-
    # yearly, 098 onward. These are EMPTY HOMES, a different and larger
    # population than rental vacancy; see moi_block for how it is used.
    "low_use":     ("https://pip.moi.gov.tw/Publicize/Info/E1040", "時間",
                    "低度使用(用電)住宅", "Low-electricity-use dwellings", "宅"),
    # 待售新成屋 -- completed new homes still unsold. Quarterly, 109Q1 onward.
    # Same page, second 時間 table.
    "unsold_new":  ("https://pip.moi.gov.tw/Publicize/Info/E1040", "時間",
                    "待售新成屋", "Completed new homes unsold", "宅"),
}

_PERIOD_RES = [
    (r"(\d{3})年第(\d)季", lambda m: f"{m.group(1)}Q{m.group(2)}"),
    (r"(\d{3})上半年",       lambda m: f"{m.group(1)}H1"),
    (r"(\d{3})下半年",       lambda m: f"{m.group(1)}H2"),
    (r"^(\d{3})年?$",        lambda m: f"{m.group(1)}"),
]


def _parse_period(text):
    for pat, fn in _PERIOD_RES:
        m = re.match(pat, text)
        if m:
            return fn(m)
    return None


def _scrape_time_tables(url):
    """Every table on `url` whose first header is a period/county label, as a
    list of (heads, rows) with entities unescaped and tags stripped."""
    import html as _html
    s = _session()
    r = s.get(url, timeout=90)
    if r.status_code != 200:
        print(f"[moi] {url}: http {r.status_code}")
        return []
    out = []
    for t in re.findall(r"<table.*?</table>", r.text, re.S):
        heads = [_html.unescape(re.sub(r"<.*?>", "", h)).strip()
                 for h in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
        if not heads:
            continue
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            cells = [_html.unescape(re.sub(r"<.*?>", "", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if len(cells) == len(heads) and _parse_period(cells[0]):
                rows.append(cells)
        if rows:
            out.append((heads, rows))
    return out


def fetch_html_series(key, cache_dir=None, force=False):
    """Scrape one HTML-table series to the cache. Returns the path or ''."""
    if key not in HTML_SERIES:
        raise KeyError(f"unknown HTML series {key!r}; known: {sorted(HTML_SERIES)}")
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{key}.csv")
    if os.path.exists(path) and not force and os.path.getsize(path) > 200:
        return path
    url, head0, zh, _, _ = HTML_SERIES[key]
    try:
        tables = [(h, r) for h, r in _scrape_time_tables(url) if h[0] == head0]
        # E1040 carries two 時間 tables: low-use first, unsold-new second.
        pick = {"price_index": 0, "low_use": 0, "unsold_new": 1}[key]
        if len(tables) <= pick:
            print(f"[moi] {key}: table not found ({len(tables)} candidates)")
            return ""
        heads, rows = tables[pick]
        with open(path, "w", encoding="utf-8") as f:
            f.write("period,county,value\n")
            n = 0
            for cells in rows:
                period = _parse_period(cells[0])
                for county, val in zip(heads[1:], cells[1:]):
                    v = val.replace("%", "").replace("－", "").replace(",", "").strip()
                    if v:
                        f.write(f"{period},{_tw(county)},{v}\n")
                        n += 1
        print(f"[moi] {key} ({zh}): {n} rows, {rows[-1][0]}..{rows[0][0]}")
        return path
    except Exception as e:
        print(f"[moi] {key}: {e}")
        return ""


def load_html_series(key, cache_dir=None):
    path = fetch_html_series(key, cache_dir)
    if not path:
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"period": str, "county": str})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["district"] = ""
    df["kind"] = ""
    return df[["period", "county", "district", "kind", "value"]]


# ── themed series from E4040, exported by a plain GET ───────────────────
#
# A third mechanism. /Publicize/Info/E4041?m=csv&k=<kind>&n=<name> returns the
# CSV directly; no postback. These are the ones that give the coverage findings
# a denominator that is the actual STOCK rather than "buildings with a sale".
#
# Both are in 宅 (dwelling units on the house-tax roll), not 棟. The site counts
# buildings, so these are compared as DISTRIBUTIONS, never divided into.

THEME_URL = "https://pip.moi.gov.tw/Publicize/Info/E4041"
THEME_SERIES = {
    "stock_by_age":   ("K02", "T13", "房屋稅籍住宅類數量依屋齡區分",
                       "Residential stock by age band", "宅"),
    "stock_by_floor": ("K02", "T16", "房屋稅籍住宅類數量依總樓層區分",
                       "Residential stock by floor count", "宅"),
    "stock_by_size":  ("K02", "T14", "房屋稅籍住宅類數量依面積區分",
                       "Residential stock by floor-area band", "宅"),
    # The population that TRANSACTS, by the same bands as the stock. It sits
    # between the whole stock and this site's matched set, so the two selection
    # steps -- does a building sell, and does a sale-carrying building also
    # have a registered lease -- can be told apart. Unit is 筆 (transfers), not
    # 宅 and not 棟: compare as distributions, never divide.
    "xfer_by_age":    ("K03", "T25", "住宅買賣移轉筆數依屋齡區分",
                       "Residential sale transfers by age band", "筆"),
    "xfer_by_size":   ("K03", "T26", "住宅買賣移轉筆數依面積區分",
                       "Residential sale transfers by floor-area band", "筆"),
    "xfer_by_floor":  ("K03", "T28", "住宅買賣移轉筆數依總樓層區分",
                       "Residential sale transfers by floor count", "筆"),
}


def fetch_theme_series(key, cache_dir=None, force=False):
    if key not in THEME_SERIES:
        raise KeyError(f"unknown theme series {key!r}; known: {sorted(THEME_SERIES)}")
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{key}.csv")
    if os.path.exists(path) and not force and os.path.getsize(path) > 500:
        return path
    k, n, zh, _, _ = THEME_SERIES[key]
    try:
        s = _session()
        s.get("https://pip.moi.gov.tw/Publicize/Info/E4040", timeout=60)
        r = s.get(THEME_URL, params={"m": "csv", "k": k, "n": n}, timeout=180)
        if r.status_code != 200 or "csv" not in r.headers.get("Content-Type", "") \
                or len(r.content) < 500:
            print(f"[moi] {key}: http {r.status_code}, {len(r.content)} bytes")
            return ""
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"[moi] {key} ({zh}): {len(r.content)/1e3:.0f} KB")
        return path
    except Exception as e:
        print(f"[moi] {key}: {e}")
        return ""


def load_theme_series(key, cache_dir=None):
    """period, county, district, kind, value -- one row per band.

    The source has ONE location column, 縣市/地區, that holds '新北市' for a
    county total and '新北市板橋區' for a district. It is split here. The
    total column comes back as kind='' ; a mean column as kind='mean'.

    BOTH of those must be recognised or they melt in as bands and anyone
    summing the bands gets double. The stock series head their total
    房屋稅籍住宅類數量 and their mean 住宅平均屋齡; the transfer series head
    theirs 住宅買賣總筆數 and 平均買賣屋齡/平均買賣面積/買賣平均總樓層 --
    different words for the same two roles, and the unit suffix is (宅), (筆)
    or (歲)/(坪)/(樓) depending on the series. Measured on xfer_by_age 115Q2
    全國: the ten real bands sum to 21,512, which is exactly the total column,
    and the mean column is 32.35 -- so a naive melt returns 43,056.35.
    """
    path = fetch_theme_series(key, cache_dir)
    if not path:
        return pd.DataFrame()
    txt = open(path, "rb").read().decode("utf-8-sig", errors="replace")
    df = pd.read_csv(io.StringIO(txt), dtype=str, keep_default_na=False)
    df = df.rename(columns={df.columns[0]: "period", df.columns[1]: "loc"})
    df["loc"] = df["loc"].map(_tw)
    counties = sorted({c for c in df["loc"] if len(c) == 3 and c.endswith(("市", "縣"))}
                      | {"全國"}, key=len, reverse=True)
    def split(loc):
        if loc == "全國":
            return "全國", ""
        for c in counties:
            if c != "全國" and loc.startswith(c):
                return c, loc[len(c):]
        return loc, ""
    parts = df["loc"].map(split)
    df["county"] = [p[0] for p in parts]
    df["district"] = [p[1] for p in parts]
    value_cols = [c for c in df.columns if c not in ("period", "loc", "county", "district")]
    long = df.melt(id_vars=["period", "county", "district"], value_vars=value_cols,
                   var_name="kind", value_name="value")
    long["value"] = pd.to_numeric(long["value"].str.replace(",", ""), errors="coerce")
    # normalise the band names: strip the unit suffix, mark the total and the mean
    def band(k):
        k = re.sub(r"\((宅|筆|歲|坪|樓)\)$", "", k).strip()
        if k.startswith("房屋稅籍住宅類數量") or k.startswith("住宅買賣總筆數"):
            return ""
        # 平圴 is a TYPO in MOI's own header on the by-size series (圴 for 均).
        # Without it the mean area melts in as an eighth band worth 39.
        if "平均" in k or "平圴" in k:
            return "mean"
        return k
    long["kind"] = long["kind"].map(band)
    return long[["period", "county", "district", "kind", "value"]]


# ── the low-use series for ALL 22 counties, via 經濟部能源署 ─────────────
#
# 內政部's own E1040 page publishes 低度使用(用電)住宅 for 全國 and the SIX
# municipalities and nothing else, which leaves the other sixteen counties --
# 9% of this site's matched buildings, and the counties with the HIGHEST rates
# -- with no rate at all.
#
# 經濟部能源署 republishes the same 內政部 counts for all 22 counties, because
# it needs them to derive bottled-gas households (房屋稅籍住宅類數量 − 天然氣
# 用戶數 − 低度使用戶數). Verified before use, county by county:
#
#   * its 低度使用 column equals 內政部's 上半年 (H1) figure EXACTLY for every
#     year and every one of the six counties both sources publish (112, 113,
#     114 checked; 114 臺北市 65,717 both ways);
#   * its 房屋稅籍住宅數 column equals this repo's resi_tax_roll to the unit;
#   * summed over all 22 counties against the Q2 roll it reproduces 內政部's
#     published 114H1 national rate of 10.43% exactly.
#
# So it is the same numerator, one half-year per year, at full county coverage.
# It is NOT a second opinion and must never be averaged with E1040: where both
# publish, they are the same number. E1040 stays the source for the 內政部
# section (it has both halves); this is the source for the vacancy prior (it
# has every county).
#
# The file's own derived column pairs an H1 numerator with a Q4 denominator;
# this module does not read that column.
DIRECT = {
    "low_use_22": ("https://www.moeaea.gov.tw/ECW/populace/opendata/"
                   "wHandOpenData_File.ashx?set_id=153",
                   "低度使用(用電)住宅數，全22縣市，年度=該年上半年",
                   "Low-use dwellings, all 22 counties, 年度 N = N年上半年"),
}


def fetch_direct(key, cache_dir=None, force=False):
    """Download one plain-URL CSV to the cache. Returns the path or ''."""
    if key not in DIRECT:
        raise KeyError(f"unknown direct series {key!r}; known: {sorted(DIRECT)}")
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{key}.csv")
    if os.path.exists(path) and not force and os.path.getsize(path) > 200:
        return path
    url = DIRECT[key][0]
    try:
        r = _session().get(url, timeout=90)
    except Exception as e:                      # noqa: BLE001 - reported, not raised
        print(f"[moi] {key}: {type(e).__name__} {e}")
        return ""
    if r.status_code != 200 or len(r.content) < 200:
        print(f"[moi] {key}: http {r.status_code}, {len(r.content)} bytes")
        return ""
    with open(path, "wb") as f:
        f.write(r.content)
    print(f"[moi] {key}: {len(r.content):,} bytes")
    return path


def load_low_use_22(cache_dir=None):
    """period ('114H1'), county (臺-normalised), low_use, stock.

    `stock` is the file's own 房屋稅籍住宅數 column and is returned only so a
    caller can assert it against resi_tax_roll -- the rate must be computed on
    the roll at the matching quarter, not on this column, because the file
    pairs an H1 numerator with a Q4 denominator.
    """
    path = fetch_direct("low_use_22", cache_dir)
    if not path:
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    cols = list(df.columns)
    yr = cols[0]
    cty = cols[1]
    lu = next((c for c in cols if c.startswith("低度使用")), None)
    st = next((c for c in cols if c.startswith("房屋稅籍住宅數")), None)
    if lu is None or st is None:
        print(f"[moi] low_use_22: expected columns not found in {cols}")
        return pd.DataFrame()
    out = pd.DataFrame({
        "period": df[yr].str.strip() + "H1",
        "county": df[cty].map(_tw),
        "low_use": pd.to_numeric(df[lu].str.replace(",", ""), errors="coerce"),
        "stock_file": pd.to_numeric(df[st].str.replace(",", ""), errors="coerce"),
    })
    return out.dropna(subset=["low_use"])


# ── low-use by county x AGE BAND, from the archived half-yearly report ───
#
# 內政部 publishes 表2-3-2 低度使用(用電)住宅半年報表-按屋齡分 as an .ods: the
# low-use RATE for every county crossed with seven age bands. It is a JOINT
# table, not two marginals, so a prior built on it needs no independence
# assumption between county and age.
#
# It lives on pip.moi.gov.tw, which is not reachable from every network, and the
# only editions the Internet Archive holds are 111年上半年 and 111年下半年 --
# captured 2024-06-02. Later editions are not archived and the live host may be
# unavailable, so the ARCHIVE SNAPSHOT is the pin: the `id_` form returns the
# original bytes with no Wayback banner, and MANIFEST.json records the snapshot
# URL and its timestamp so a rebuild reads exactly the same file.
#
# Validated before use: weighting the 111H1 national band rates by the national
# house-tax roll's own age composition at 111Q2 reproduces the published 111H1
# national low-use rate to 9.68% against 9.52% -- the residual is the roll's ten
# bands folding into the table's seven, and it is far inside the gap this table
# is used to measure.
WAYBACK = "https://web.archive.org/web/%sid_/%s"
LOW_USE_AGE = {
    # period -> (wayback timestamp, original url)
    "111H1": ("20240602033751",
              "https://pip.moi.gov.tw/Upload/Statistics/year/111Y/111Y_"
              "%E8%A1%A82-3-2%E4%BD%8E%E5%BA%A6%E4%BD%BF%E7%94%A8(%E7%94%A8%E9%9B%BB)"
              "%E4%BD%8F%E5%AE%85%E5%8D%8A%E5%B9%B4%E5%A0%B1%E8%A1%A8-"
              "%E6%8C%89%E5%B1%8B%E9%BD%A1%E5%88%86(%E4%B8%8A%E5%8D%8A%E5%B9%B4).ods"),
    "111H2": ("20240602033801",
              "https://pip.moi.gov.tw/Upload/Statistics/year/111Y/111Y_"
              "%E8%A1%A82-3-2%E4%BD%8E%E5%BA%A6%E4%BD%BF%E7%94%A8(%E7%94%A8%E9%9B%BB)"
              "%E4%BD%8F%E5%AE%85%E5%8D%8A%E5%B9%B4%E5%A0%B1%E8%A1%A8-"
              "%E6%8C%89%E5%B1%8B%E9%BD%A1%E5%88%86(%E4%B8%8B%E5%8D%8A%E5%B9%B4).ods"),
}
# the table's own seven bands, in its own order
AGE_BANDS = ["<=5", "5-10", "10-20", "20-30", "30-40", "40-50", "50+"]
AGE_EDGES = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 10 ** 9)]


def age_band(years):
    """The table's band for an age in years. Ages at or below 0 read as new."""
    if years is None or years != years:
        return None
    for (lo, hi), lab in zip(AGE_EDGES, AGE_BANDS):
        if lo < years <= hi:
            return lab
    return AGE_BANDS[0] if years <= 0 else AGE_BANDS[-1]


def _ods_rows(raw):
    """Every row of an .ods as a list of cell strings.

    Written here rather than pulled in as a dependency: the file is one small
    sheet, and odfpy/pandas-ods would be a new install for 30 lines of regex.
    `number-columns-repeated` is honoured because the sheet uses it for blanks.
    """
    import html as _html
    import zipfile
    x = zipfile.ZipFile(io.BytesIO(raw)).read("content.xml").decode("utf-8")
    out = []
    for r in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", x, re.S):
        cells = []
        for m in re.finditer(r"<table:table-cell([^>]*)(?:/>|>(.*?)</table:table-cell>)",
                             r, re.S):
            attrs, inner = m.group(1), m.group(2) or ""
            rep = re.search(r'number-columns-repeated="(\d+)"', attrs)
            val = re.search(r'office:value="([^"]*)"', attrs)
            txt = " ".join(_html.unescape(re.sub(r"<[^>]+>", "", t))
                           for t in re.findall(r"<text:p[^>]*>(.*?)</text:p>", inner, re.S))
            cells += [(val.group(1) if val else txt).strip()] * min(
                int(rep.group(1)) if rep else 1, 12)
        while cells and cells[-1] == "":
            cells.pop()
        if cells:
            out.append(cells)
    return out


def fetch_low_use_age(cache_dir=None, force=False):
    """Both archived editions as one tidy CSV: period, county, band, rate_pct."""
    import datetime
    import hashlib
    import json as _json
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "low_use_by_age.csv")
    if os.path.exists(path) and not force and os.path.getsize(path) > 200:
        return path
    rows = []
    srcs = {}
    for period, (ts, url) in sorted(LOW_USE_AGE.items()):
        snap = WAYBACK % (ts, url)
        try:
            r = _session().get(snap, timeout=120)
        except Exception as e:                  # noqa: BLE001 - reported, not raised
            print(f"[moi] low_use_by_age {period}: {type(e).__name__} {e}")
            return ""
        if r.status_code != 200 or len(r.content) < 500:
            print(f"[moi] low_use_by_age {period}: http {r.status_code}, "
                  f"{len(r.content)} bytes")
            return ""
        srcs[period] = {"url": snap, "original": url, "wayback": ts,
                        "sha256": hashlib.sha256(r.content).hexdigest()}
        for cells in _ods_rows(r.content):
            name = cells[0].split(" ")[0]
            # county/國 rows only: the sheet also carries 臺灣省/福建省 spacers
            # whose cells are all '-', and bilingual header rows.
            if not re.match(r"^[\u4e00-\u9fff]{2,3}[縣市]$|^全國$", name):
                continue
            vals = []
            for v in cells[1:1 + len(AGE_BANDS)]:
                try:
                    vals.append(float(v))
                except ValueError:
                    vals.append(None)
            if not any(v is not None for v in vals):
                continue
            for band, v in zip(AGE_BANDS, vals):
                if v is not None:
                    rows.append((period, _tw(name), band, round(v, 4)))
    if not rows:
        print("[moi] low_use_by_age: no rows parsed")
        return ""
    with open(path, "w", encoding="utf-8") as f:
        f.write("period,county,band,rate_pct\n")
        for p, c, b, v in rows:
            f.write(f"{p},{c},{b},{v}\n")
    mp = os.path.join(cache_dir, "MANIFEST.json")
    man = {}
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            man = _json.load(f)
    man["low_use_by_age.csv"] = {
        "url": "; ".join(s["url"] for s in srcs.values()),
        "fetched": datetime.date.today().isoformat(),
        "snapshots": srcs,
        "note": ("內政部 表2-3-2 低度使用(用電)住宅半年報表-按屋齡分, read from the "
                 "Internet Archive because pip.moi.gov.tw is not reachable from "
                 "every network and no later edition is archived"),
    }
    with open(mp, "w", encoding="utf-8") as f:
        _json.dump(man, f, ensure_ascii=False, indent=1)
    print(f"[moi] low_use_by_age: {len(rows)} rows, {len(srcs)} editions")
    return path


def load_low_use_age(cache_dir=None):
    path = fetch_low_use_age(cache_dir)
    if not path:
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"period": str, "county": str, "band": str})
    df["rate_pct"] = pd.to_numeric(df.rate_pct, errors="coerce")
    return df.dropna(subset=["rate_pct"])


# kept for the name the block already uses
def load_price_index(cache_dir=None):
    return load_html_series("price_index", cache_dir)


def period_to_season(p):
    """'112Q4' -> '112S4', the registry's season id."""
    return p.replace("Q", "S") if isinstance(p, str) else p


def fetch_all(cache_dir=None, force=False):
    out = {}
    for key in SERIES:
        out[key] = fetch_series(key, cache_dir, force)
        if not out[key]:
            continue
        time.sleep(2)   # be a polite client of a government server
    for key in DIRECT:
        out[key] = fetch_direct(key, cache_dir, force)
    out["low_use_by_age"] = fetch_low_use_age(cache_dir, force)
    return out


if __name__ == "__main__":
    paths = fetch_all()
    for k, p in paths.items():
        df = load_series(k) if p else pd.DataFrame()
        print(f"  {k:<20} {'OK' if p else 'FAIL':<5} rows={len(df):<6}"
              f" periods={df.period.nunique() if len(df) else 0}"
              f" counties={df.county.nunique() if len(df) else 0}")
