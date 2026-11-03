"""
fetch_fasc.py — 台灣金服 金拍 auction results.

Source: 台灣金融資產服務股份有限公司 (TFASC), https://www.tfasc.com.tw
        公開標售結果 /Product/Bidded/

TFASC is the state-established clearing house for financial-institution
collateral (set up under 金融機構合併法), and its auction results are published
without a login, without an API key, and without a robots.txt. The site is
polled here at one request every 1.2 s with an honest User-Agent, and every
response is cached to disk so a re-run costs nothing.

House convention (see fetch_lvr.py): this module is a PURE LIBRARY. No
database, no Flask, no global state. IO lives at the top, pure compute below the
banner, and nothing here raises — failures print `[fasc] ...` and return an
empty value.

--------------------------------------------------------------------------------
WHAT THIS IS, AND WHAT IT IS NOT — read before drawing a conclusion from it.

    This is 金拍, NOT 法拍.

    法拍 is a court auction run by 司法院 under compulsory execution. 金拍 is
    the bank's own disposal of collateral through TFASC. They overlap in spirit
    and not in population: 金拍 is the smaller channel, it skews toward
    financial-institution collateral, and a property can pass through one and
    never the other. Anything computed here describes 金拍 and must say so.

    司法院's own system (aae.court.gov.tw) refuses connections outright, and the
    實價登錄 registry does not flag auction sales at all — 備註 carries zero
    法拍/金拍/拍賣 mentions across a full season of 臺北市. So there is no route
    to court-auction data from either the open registry or the court site, and
    that is why this file covers the channel it can actually reach.

FACTS VERIFIED AGAINST REAL BYTES (2026-09-06) — do not "fix" these from the
page markup, which disagrees with itself:

* The listing page has NO <form action>. It is a Kendo UI grid posting
  aspnetmvc-ajax params to two endpoints:
      POST /Product/Bidded/ReadData        -> auction SESSIONS
      POST /Product/Bidded/ReadDataDetil   -> the properties in one session
  `ReadDataDetil` is spelled that way on the server. It is not a typo here.
* Session listing takes qDateBeginS / qDateEndS as ISO dates and qAreaNo in
  {'', 1 北區, 2 中區, 3 南區}. 2015-01-01..2026-12-31 returns 1,549 sessions.
* The detail POST keys on `id` (the session Id), not qId and not BuzSaleMainId.
* PropType is 'BuzLand' or 'BuzBuild'. Only BuzBuild carries a real 門牌
  ("臺南市仁德區新田路222號2樓"); BuzLand carries a 地號 parcel reference, which
  cannot be matched to the registry and is dropped.
* Saleamt is the SOLD price and MinPrice the reserve (底價). SalePrice and
  EvaluatePrice exist in the schema and are null/0 in practice — do not read
  them.
* Saleamt == MinPrice on most rows. That is not a bug and not a default: an
  auction that draws one qualifying bid clears AT the reserve. The share of
  rows above reserve is the competition rate and is worth reporting.
* sNewSaleNo carries the round ("第2拍 (共8筆)"). Taiwanese auctions re-list at
  a reduced reserve each round, so the round is a confounder for any price
  comparison and is parsed out rather than ignored.
* There is NO AREA FIELD anywhere in the response. Lat/Lng exist in the schema
  and are null in every row observed. Price-per-ping therefore cannot be
  computed from this source alone — it has to come from matching the address
  into the registry, which is the same same-building join the project already
  uses for sale-to-lease.
"""

import json
import os
import re
import time

import pandas as pd
import requests

BASE = "https://www.tfasc.com.tw"
LIST_URL = BASE + "/Product/Bidded/"
SESSIONS_URL = BASE + "/Product/Bidded/ReadData"
ITEMS_URL = BASE + "/Product/Bidded/ReadDataDetil"

CACHE_DIR = os.path.join("data", "fasc")
PAUSE_S = 1.2
TIMEOUT = 40

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Fields worth keeping. The grid returns ~170 columns, most of them internal
# workflow state (ApproveUser, UpfLag, CanMod ...) that would be noise on disk.
KEEP = [
    "Id", "sBuzSaleAdd", "BuzSaleAdd", "PropType", "HouseType",
    "MinPrice", "Saleamt", "EvaluatePrice", "Margin",
    "sNewSaleNo", "sNewCrmNo", "AreaNo", "AreaName",
    "SaleDate", "DecideDate", "BiddedStatus", "ItemStatus",
    "Lat", "Lng", "Rmk",
]


# ── IO ────────────────────────────────────────────────────────────────────────

def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LIST_URL,
    })
    s.verify = False
    try:
        # The grid endpoints want the listing page's cookies.
        s.get(LIST_URL, timeout=TIMEOUT)
    except Exception as e:
        print("[fasc] warm-up failed: %s" % str(e)[:90])
    return s


def _post(s, url, body, what):
    try:
        r = s.post(url, data=body, timeout=TIMEOUT)
        if r.status_code != 200:
            print("[fasc] %s HTTP %s" % (what, r.status_code))
            return None
        return r.json()
    except Exception as e:
        print("[fasc] %s failed: %s" % (what, str(e)[:90]))
        return None


def fetch_sessions(date_from, date_to, s=None):
    """Every auction session between two ISO dates. One row per 場次."""
    s = s or _session()
    out, page, size = [], 1, 100
    while True:
        j = _post(s, SESSIONS_URL, {
            "page": page, "pageSize": size,
            "skip": (page - 1) * size, "take": size,
            "qAreaNo": "", "qDateBeginS": date_from, "qDateEndS": date_to,
        }, "sessions p%d" % page)
        if not j:
            break
        rows = j.get("Data") or []
        out.extend(rows)
        total = j.get("Total") or 0
        if len(out) >= total or not rows:
            break
        page += 1
        time.sleep(PAUSE_S)
    print("[fasc] %d sessions %s..%s" % (len(out), date_from, date_to))
    return out


def fetch_items(session_id, s=None, cache_dir=CACHE_DIR):
    """The properties sold in one session. Cached to disk by session id."""
    path = os.path.join(cache_dir, "s%s.json" % session_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass                      # a truncated cache file just re-fetches
    s = s or _session()
    j = _post(s, ITEMS_URL, {
        "page": 1, "pageSize": 300, "skip": 0, "take": 300, "id": session_id,
    }, "items %s" % session_id)
    rows = (j or {}).get("Data") or []
    rows = [{k: r.get(k) for k in KEEP} for r in rows]
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    except Exception as e:
        print("[fasc] cache write failed: %s" % str(e)[:90])
    return rows


def load_auctions(date_from="2023-10-01", date_to="2026-12-31",
                  cache_dir=CACHE_DIR, limit=None):
    """Every auctioned item in the window, as a DataFrame.

    The default window starts at 2023-10-01 because that is 112S4, the schema
    floor the rest of this project is pinned to — a comparison against registry
    prices outside that window would be comparing to data the pipeline refuses
    to clean.
    """
    s = _session()
    sess = fetch_sessions(date_from, date_to, s=s)
    if not sess:
        return pd.DataFrame()
    ids = [x.get("Id") for x in sess if x.get("Id") is not None]
    if limit:
        ids = ids[:limit]
    rows, fetched = [], 0
    for i, sid in enumerate(ids):
        path = os.path.join(cache_dir, "s%s.json" % sid)
        cached = os.path.exists(path)
        rows.extend(fetch_items(sid, s=s, cache_dir=cache_dir))
        if not cached:
            fetched += 1
            time.sleep(PAUSE_S)
        if (i + 1) % 100 == 0:
            print("[fasc] %d/%d sessions (%d fetched)" % (i + 1, len(ids), fetched))
    df = pd.DataFrame(rows)
    print("[fasc] %d items from %d sessions (%d newly fetched)"
          % (len(df), len(ids), fetched))
    return df


# ── pure compute ──────────────────────────────────────────────────────────────

_ROUND = re.compile(r"第\s*(\d+)\s*拍")


def parse_round(s):
    """'第2拍 (共8筆)' -> 2. Blank or unparseable -> 1.

    The round matters more than it looks. Taiwanese auctions re-list unsold lots
    at a reduced reserve, so a 3rd-round sale is cheap partly BECAUSE it is a
    3rd-round sale. Comparing a mixed bag of rounds against market prices would
    attribute the reserve schedule to "auctions are cheap".
    """
    if not isinstance(s, str) or not s:
        return 1
    m = _ROUND.search(s)
    return int(m.group(1)) if m else 1


def clean_auctions(df):
    """Residential-looking buildings with a real address and a real price.

    BuzLand is dropped outright: a 地號 parcel reference has no 門牌, so it can
    neither be matched to the registry nor placed on the map, and a land price
    is not comparable to a dwelling price under any treatment.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    d = df[df["PropType"].astype(str) == "BuzBuild"].copy()
    if d.empty:
        return pd.DataFrame()
    d["addr"] = d["sBuzSaleAdd"].fillna("").astype(str).str.strip()
    # sBuzSaleAdd is suffixed '地號' on parcels; a stray one that slipped past
    # the PropType filter is still not an address.
    d = d[d.addr.str.contains("號") & ~d.addr.str.contains("地號")]
    d["price"] = pd.to_numeric(d["Saleamt"], errors="coerce")
    d["reserve"] = pd.to_numeric(d["MinPrice"], errors="coerce")
    d["round"] = d["sNewSaleNo"].map(parse_round)
    # '/Date(1783468800000)/'. extract() yields STRINGS, and to_datetime with
    # unit='ms' silently coerces every string to NaT — so the numeric cast is
    # load-bearing, not defensive.
    d["date"] = pd.to_datetime(
        pd.to_numeric(d["SaleDate"].astype(str).str.extract(r"\((\d+)")[0],
                      errors="coerce"),
        unit="ms", errors="coerce")
    # 高雄巿 (U+5DFF) for 高雄市 (U+5E02) appears in this feed. It is a
    # different character, it survives every normaliser that only knows 台->臺,
    # and it silently costs the address match.
    d["addr"] = d["addr"].str.replace("巿", "市", regex=False)
    d = d[(d.price > 1e5) & (d.reserve > 0)]
    # An auction with one qualifying bid clears AT the reserve; above it means
    # two or more bidders. The distinction is the only competition signal the
    # feed carries, so it is computed once here rather than re-derived.
    d["above_reserve"] = d.price > d.reserve
    d["over_pct"] = (d.price / d.reserve - 1.0) * 100.0
    return d.reset_index(drop=True)


def summarise(d):
    """Headline facts about the auction channel. Descriptive only."""
    if d is None or d.empty:
        return {}
    by_round = {}
    for r in sorted(d["round"].unique()):
        g = d[d["round"] == r]
        if len(g) < 10:
            continue
        by_round[int(r)] = {
            "n": int(len(g)),
            "above_reserve_pct": round(float(g.above_reserve.mean()) * 100, 1),
            "median_over_pct": round(float(g.over_pct.median()), 2),
        }
    return {
        "items": int(len(d)),
        "above_reserve_pct": round(float(d.above_reserve.mean()) * 100, 1),
        "median_over_pct": round(float(d.over_pct.median()), 2),
        "median_price": int(d.price.median()),
        "by_round": by_round,
        "date_min": str(d.date.min().date()) if d.date.notna().any() else None,
        "date_max": str(d.date.max().date()) if d.date.notna().any() else None,
    }


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    raw = load_auctions(limit=lim)
    cl = clean_auctions(raw)
    print("[fasc] %d raw -> %d residential buildings" % (len(raw), len(cl)))
    print(json.dumps(summarise(cl), ensure_ascii=False, indent=1))
