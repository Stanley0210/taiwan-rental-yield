# -*- coding: utf-8 -*-
"""
fetch_cbc.py — two reference rates from 中央銀行, pinned under data/ref/cbc/.

The page's net yield needs a "compared to what". These are the two cheapest
honest answers, both from the CBC's own open-data files:

  A13Rate.csv   五大銀行 posted (牌告) deposit and lending rates, monthly, per
                bank, back to 民國90. We read 定存利率-一年期-固定.
  webF1.csv     重貼現率 (rediscount rate) and the two accommodation rates,
                one row per change since 2000. Catalogued at
                https://data.gov.tw/dataset/6022.

TWO TRAPS, both silent if you miss them:

  * A13Rate.csv carries SIX banks. 彰化銀行 stopped filing in 民國97年11月, so
    "the latest month every bank in the file posts" is November 2008 at 2.17%.
    The five-bank filter below is the whole point of load_deposit_1y; the test
    asserts 彰化銀行 never enters the mean.
  * The two files are in different encodings: A13Rate.csv is UTF-8 with a BOM,
    webF1.csv is Big5. Reading either with the other's codec fails at parse
    time (webF1) or corrupts the bank names so the five-bank filter matches
    nothing (A13).

The CBC certificate has the same defect as MOI's -- no Subject Key
Identifier, which Python 3.13's VERIFY_X509_STRICT rejects -- so the session
clears that one flag and nothing else. Verification stays on; this is not
verify=False and must not become it.

PINNING. The bytes are written verbatim -- the sha256 in provenance is the
server's file, not a re-encoding -- and MANIFEST.json beside them records url,
fetch date and digest. underwrite.py reads `fetched` from that file and never
from today(), or every rebuild would change the payload and --verify could
never match. If cbc.gov.tw is unreachable at refresh time the fallback is a
browser download committed by hand with the manifest edited to match.

Like fetch_moi, a warm cache is returned without a network call, so the build
touches the network only when a file is missing or `force` is set.

Licence: 政府資料開放授權條款-第1版 (both files are listed on data.gov.tw
under it), the same licence as the registry data.
"""
import datetime
import hashlib
import json
import os
import ssl

import pandas as pd

CACHE = os.environ.get("CBC_CACHE", "data/ref/cbc")
LICENCE = "政府資料開放授權條款-第1版"

FILES = {
    "A13Rate.csv": ("https://www.cbc.gov.tw/public/data/OpenData/A13Rate.csv",
                    "utf-8-sig", None),
    # Path case is exactly as the CBC serves it; the catalogue is data.gov.tw 6022.
    "webF1.csv":   ("https://www.cbc.gov.tw/Public/Data/opendata/webF1.csv",
                    "big5", "https://data.gov.tw/dataset/6022"),
}

# 五大銀行 as the CBC's own series defines them. Never derive this list from
# the file -- see the 彰化銀行 trap above.
FIVE = ("臺灣銀行", "合作金庫", "土地銀行", "華南銀行", "第一銀行")
COL_1Y_FIXED = "定存利率-一年期-固定"

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/csv,*/*;q=0.8",
}


def _sha(b):
    return hashlib.sha256(b).hexdigest()


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


def manifest(cache_dir=None):
    """The sidecar: {name: {url, fetched, sha256, bytes, licence, catalogue?}}."""
    p = os.path.join(cache_dir or CACHE, "MANIFEST.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def fetch(name, cache_dir=None, force=False):
    """Fetch one file into the cache, verbatim. Returns the path, or '' on failure.

    On a warm cache this is a stat call. On a failed fetch with a stale copy
    present it returns the stale copy and says so."""
    if name not in FILES:
        raise KeyError(f"unknown CBC file {name!r}; known: {sorted(FILES)}")
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, name)
    if os.path.exists(path) and not force and os.path.getsize(path) > 200:
        return path
    url, _, catalogue = FILES[name]
    try:
        r = _session().get(url, timeout=60)
        if r.status_code != 200 or len(r.content) < 200:
            raise RuntimeError(f"http {r.status_code}, {len(r.content)} bytes")
        with open(path, "wb") as f:
            f.write(r.content)
        man = manifest(cache_dir)
        entry = {"url": url, "fetched": datetime.date.today().isoformat(),
                 "sha256": _sha(r.content), "bytes": len(r.content),
                 "licence": LICENCE}
        if catalogue:
            entry["catalogue"] = catalogue
        man[name] = entry
        with open(os.path.join(cache_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        print(f"[cbc] {name}: {len(r.content)/1e3:.1f} KB  sha256 {entry['sha256'][:12]}")
        return path
    except Exception as e:
        if os.path.exists(path):
            print(f"[cbc] WARN {name}: {e} -- using the cached copy")
            return path
        print(f"[cbc] {name}: {e}")
        return ""


# ── 五大銀行新承做放款金額與利率 ─────────────────────────────────────────────
# The new-mortgage rate the page sets beside the net yield. Unlike the two
# files above this one has NO stable URL: the CBC publishes each month as a new
# release page with freshly named ODS / XLS / PDF attachments, so fetch() cannot
# refresh it. That is why it was a hand-typed constant until payload 2.13, and
# why 2.11 wrongly concluded the series "exists only as a PDF" -- the release
# page was never opened, only the listing.
#
# So it is pinned by hand and read by code: download the newest release's ODS
# from NEW_LOANS_LISTING, hand it to pin_new_loans(), and the manifest records
# where it came from. Every month back to 83/07 is in the one file, which is
# what lets a test check that the pinned file still reproduces the figure that
# used to be typed.
NEW_LOANS = "five_bank_new_loans.ods"
NEW_LOANS_LISTING = "https://www.cbc.gov.tw/tw/lp-528-1.html"
_ODS_T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_ODS_P = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"


def _ods_rows(path):
    """First sheet of an ODS as lists of cell strings. Standard library only:
    an .ods is a zip with a content.xml, and nothing in it is executed."""
    import xml.etree.ElementTree as ET
    import zipfile
    root = ET.fromstring(zipfile.ZipFile(path).read("content.xml"))
    sheet = next(root.iter(_ODS_T + "table"))
    out = []
    for r in sheet.iter(_ODS_T + "table-row"):
        cells = []
        for c in r:
            if not c.tag.endswith("table-cell"):
                continue
            rep = int(c.get(_ODS_T + "number-columns-repeated", "1"))
            txt = "".join("".join(p.itertext()) for p in c.iter(_ODS_P)).strip()
            cells += [txt] * min(rep, 40)
        while cells and cells[-1] == "":
            cells.pop()
        if cells:
            out.append(cells)
    return out


def load_new_loans(path=None):
    """Monthly 購屋貸款 amount and rate: [{year, month, rate, amount_m}], oldest first.

    The columns are found by their headers, never by position -- a table that
    gains a column must fail here rather than quietly return a different loan
    type's rate.
    """
    import re
    path = path or os.path.join(CACHE, NEW_LOANS)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} is not pinned; see NEW_LOANS_LISTING")
    rows = _ods_rows(path)
    head = next(i for i, r in enumerate(rows) if "購屋貸款" in r)
    col = rows[head].index("購屋貸款")
    sub = rows[head + 1]
    if sub[col] != "金額" or sub[col + 1] != "利率":
        raise ValueError(f"unexpected sub-header under 購屋貸款: {sub[col:col + 2]}")
    out = []
    for r in rows[head + 2:]:
        m = re.match(r"^(\d{2,3})/(\d{1,2})$", r[0]) if r else None
        if not m or len(r) <= col + 1:
            continue
        try:
            out.append({"year": int(m.group(1)), "month": int(m.group(2)),
                        "rate": float(r[col + 1]),
                        "amount_m": int(r[col].replace(",", ""))})
        except ValueError:
            continue
    if not out:
        raise ValueError("no monthly rows parsed from the new-loans table")
    return out


def load_mortgage_new(path=None):
    """The latest month's new house-purchase loan rate at the five big banks."""
    series = load_new_loans(path)
    last = series[-1]
    return dict(last, period=f"{last['year']:03d}{last['month']:02d}", n_months=len(series))


def pin_new_loans(src, url, cache_dir=None):
    """Copy a downloaded release into the cache and record where it came from.

    `url` is the attachment's own download link on the release page; it changes
    every month, which is the whole reason this is not in FILES.
    """
    cache_dir = cache_dir or CACHE
    with open(src, "rb") as f:
        blob = f.read()
    load_new_loans(src)                      # refuse to pin a file that does not parse
    with open(os.path.join(cache_dir, NEW_LOANS), "wb") as f:
        f.write(blob)
    man = manifest(cache_dir)
    man[NEW_LOANS] = {"url": url, "listing": NEW_LOANS_LISTING,
                      "fetched": datetime.date.today().isoformat(),
                      "sha256": _sha(blob), "bytes": len(blob), "licence": LICENCE}
    with open(os.path.join(cache_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return os.path.join(cache_dir, NEW_LOANS)


def roc_month(p):
    """'11411' -> ('114年11月', 'Nov 2025')."""
    y, m = int(p[:3]), int(p[3:5])
    en = datetime.date(y + 1911, m, 1).strftime("%b %Y")
    return f"{y}年{m}月", en


def load_deposit_1y(path=None):
    """Five-bank one-year fixed time-deposit rate at the latest month ALL FIVE post.

    Returns {'period': '11411', 'rate': mean, 'banks': {bank: rate}, 'spread',
    'latest_single': {bank, period, rate}} -- the last because one bank (土銀)
    keeps filing after the other four stop, and quoting its month as the
    five-bank figure would be wrong."""
    path = path or fetch("A13Rate.csv")
    d = pd.read_csv(path, encoding=FILES["A13Rate.csv"][1], dtype=str)
    d.columns = [c.strip() for c in d.columns]
    d["銀行"] = d["銀行"].str.strip()
    d["年月"] = d["年月"].str.strip()
    d = d[d["銀行"].isin(FIVE)].copy()
    missing = set(FIVE) - set(d["銀行"])
    if missing:
        raise ValueError(f"A13Rate.csv lacks {sorted(missing)}; the five-bank "
                         f"filter would silently shrink the common month")
    d["r"] = pd.to_numeric(d[COL_1Y_FIXED], errors="coerce")
    d = d[d.r.notna()]
    months = d.groupby("年月")["銀行"].nunique()
    common = months[months == len(FIVE)].index.max()
    rows = d[d["年月"] == common].set_index("銀行")["r"]
    last = d.sort_values("年月").groupby("銀行").tail(1).sort_values("年月").iloc[-1]
    return {
        "period": common,
        "rate": round(float(rows.mean()), 3),
        "banks": {b: round(float(rows[b]), 3) for b in FIVE},
        "spread": round(float(rows.max() - rows.min()), 3),
        "latest_single": {"bank": last["銀行"], "period": last["年月"],
                          "rate": round(float(last.r), 3)},
    }


def load_rediscount(path=None):
    """The CBC rediscount rate as of the latest change, with the two
    accommodation rates from the same row."""
    path = path or fetch("webF1.csv")
    d = pd.read_csv(path, encoding=FILES["webF1.csv"][1], dtype=str)
    d.columns = [c.strip() for c in d.columns]
    d["dt"] = pd.to_datetime(d["調整日期"].str.strip(), format="%Y/%m/%d", errors="coerce")
    d = d[d.dt.notna()].sort_values("dt")
    last = d.iloc[-1]
    return {
        "rate": round(float(last["重貼現率"]), 3),
        "effective": last["dt"].strftime("%Y-%m-%d"),
        "secured": round(float(last["擔保放款融通利率"]), 3),
        "short": round(float(last["短期融通利率"]), 3),
        "n_changes": int(len(d)),
    }


def effective_labels(iso):
    """'2024-03-22' -> ('2024年3月22日起', 'since 22 Mar 2024')."""
    dt = datetime.date.fromisoformat(iso)
    return f"{dt.year}年{dt.month}月{dt.day}日起", "since " + dt.strftime("%-d %b %Y")


if __name__ == "__main__":
    for name in FILES:
        fetch(name, force=True)
    dep = load_deposit_1y()
    red = load_rediscount()
    print(f"deposit 1y fixed  {dep['rate']}%  at {dep['period']}  "
          f"spread {dep['spread']}  latest single {dep['latest_single']}")
    print(f"rediscount        {red['rate']}%  since {red['effective']}  "
          f"(secured {red['secured']}, short {red['short']}, {red['n_changes']} changes)")
