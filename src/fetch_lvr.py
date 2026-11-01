"""
fetch_lvr.py — 內政部 實價登錄 (actual-price registry) batch data.

Source: 不動產成交案件實際資訊資料供應系統, https://plvr.land.moi.gov.tw
Licence: 政府資料開放授權條款-第1版 (Government Data Open License v1). Free,
no key, no login, unlimited downloads.

House convention (see fetch_systemic.py): this module is a PURE LIBRARY. It has
no database, no Flask, no global state. It fetches, parses, filters and returns
plain objects. Persistence is entirely the caller's job. IO lives at the top,
pure compute below the banner, and nothing here raises — failures print
`[lvr] ...` and return an empty value.

--------------------------------------------------------------------------------
FACTS VERIFIED AGAINST REAL BYTES (season 115S2, 2026-08-28) — do not "fix" these
from documentation, the docs disagree with the files:

* Filenames inside the zip are LOWERCASE: `a_lvr_land_a.csv`.
  County letter: a=臺北市, f=新北市, b=臺中市, e=高雄市 ...
  Type suffix:   _a=買賣 (sale), _b=預售, _c=租賃 (rent).
* Encoding is UTF-8 **with BOM** -> `utf-8-sig`. It is not Big5.
* There are TWO header rows: Chinese, then English -> `skiprows=[1]`.
* The address column is `土地位置建物門牌`. The name `土地區段位置建物區段門牌`
  that appears in some open-data portals is the 實價登錄 1.0 spelling and is NOT
  in these files.
* Sale and rent have DIFFERENT schemas (schema-main.csv vs schema-main-rent.csv).
  Sale carries 總價元/建物移轉總面積; rent carries 總額元/建物總面積.

THE SCHEMA BOUNDARY — the single most important fact in this file:

    Six rent columns (出租型態, 有無管理員, 租賃期間, 有無電梯, 附屬設備,
    租賃住宅服務) were ADDED at season 112S4 (2023 Q4), tracking the 112.9.1
    rule that brought 包租業 sublease cases into the registry.

    Every cleaning filter this project depends on reads one of those columns.
    Seasons before 112S4 therefore CANNOT be cleaned to the same standard, and
    mixing them in would silently blend subsidised social housing and room-share
    leases into the early period — manufacturing a price trend that is not real.
    FIRST_CLEAN_SEASON is the guard. Do not lower it.
"""

import io
import os
import re
import zipfile

import numpy as np
import pandas as pd
import requests

BASE = "https://plvr.land.moi.gov.tw/DownloadSeason"
CACHE = os.environ.get("LVR_CACHE", "data/lvr")

# Season the six rent columns appear in. See the module docstring.
FIRST_CLEAN_SEASON = "112S4"

PING_PER_M2 = 1 / 3.305785  # 1坪 = 3.305785 m²

# All 22 counties the registry publishes. The zips already contain every one of
# them — the two-city scope was a filter on files we were downloading anyway — so
# widening this costs nothing at fetch time.
#
# 連江縣 (z) publishes a sale file but NO rent file in any season, and 金門縣 (w)
# is missing 113S1/113S2. Both are handled by read_csv_from_zip returning None
# for an absent member rather than by being listed here, so this stays a plain
# statement of what the registry covers.
#
# LVR_COUNTIES=a,f narrows the build (tests use it; it reproduces the published
# two-city numbers exactly).
_ALL_COUNTIES = {
    "a": "臺北市", "b": "臺中市", "c": "基隆市", "d": "臺南市", "e": "高雄市",
    "f": "新北市", "g": "宜蘭縣", "h": "桃園市", "i": "嘉義市", "j": "新竹縣",
    "k": "苗栗縣", "m": "南投縣", "n": "彰化縣", "o": "新竹市", "p": "雲林縣",
    "q": "嘉義縣", "t": "屏東縣", "u": "花蓮縣", "v": "臺東縣", "w": "金門縣",
    "x": "澎湖縣", "z": "連江縣",
}
_want = [c.strip() for c in os.environ.get("LVR_COUNTIES", "").split(",") if c.strip()]
COUNTIES = ({k: v for k, v in _ALL_COUNTIES.items() if k in _want}
            if _want else dict(_ALL_COUNTIES))

# ── Cleaning filters. These are the authoritative set; the numbers in the
#    comments are Taipei 115S2 and are what makes each filter non-optional.
RESIDENTIAL = {
    "住宅大樓(11層含以上有電梯)",
    "華廈(10層含以下有電梯)",
    "公寓(5樓含以下無電梯)",
}
# Pre-sale carries the same three, and the list is written out again rather than
# aliased so that a change to one can never silently move the other. What it
# excludes matters here: 19,221 pre-sale rows are 透天厝 (a whole house, not
# comparable per ping to a flat) and 6,882 are commercial — 辦公商業大樓, 店面,
# 廠辦. 公寓 is in the set for symmetry and is effectively empty in practice: a
# five-storey walk-up with no lift is not something anyone builds off-plan.
RESIDENTIAL_PRESALE = {
    "住宅大樓(11層含以上有電梯)",
    "華廈(10層含以下有電梯)",
    "公寓(5樓含以下無電梯)",
}
# 36% of Taipei rent rows. Social-housing rents are administratively set BELOW
# market, so leaving them in drags the measured yield down and blends two
# different price regimes into one number.
SOCIAL_HOUSING = {"社會住宅包租轉租", "社會住宅代管"}
# 28% of Taipei rent rows. A 分租套房's 建物總面積 describes the whole floor or
# building, not the let room, so its NT$/坪 is not comparable to a whole-unit
# sale. Excluding these is what brings the sale/rent area ratio to ~1.0.
WHOLE_UNIT = {"整棟(戶)出租", "獨立套房"}

# A parking SPACE as an asset of its own. Its unit is a space, never NT$/坪:
# 車位面積平方公尺 is an allocated share of the basement (one 坡道平面 bay records
# 41.73 m2), not the size of the bay, so no function in this file divides a
# space price or rent by that area. The record kinds on each side, and the
# 車位類別 codes, are identical in the sale and rent files.
PARK_SALE_TARGETS = ("車位", "房地(土地+建物)+車位")
PARK_LEASE_TARGETS = ("車位", "租賃房屋+車位")
PARK_TYPES = ("坡道平面", "坡道機械", "升降平面", "升降機械", "塔式車位", "一樓平面", "其他")


# ══════════════════════════════════════════════════════════════════ IO ════

def season_url(season):
    return f"{BASE}?season={season}&type=zip&fileName=lvr_landcsv.zip"


def download_season(season, cache_dir=None, force=False):
    """Fetch one season's zip into the cache. Returns the path, or '' on failure.

    Cached by default: the registry never revises a closed season, so a present
    file is authoritative and re-downloading 15 MB to learn nothing is waste.
    """
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{season}.zip")
    if os.path.exists(path) and not force and os.path.getsize(path) > 1_000_000:
        return path
    try:
        r = requests.get(season_url(season), timeout=120,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.content) < 1_000_000:
            print(f"[lvr] {season}: http {r.status_code}, {len(r.content)} bytes")
            return ""
        if not r.content.startswith(b"PK"):
            print(f"[lvr] {season}: not a zip (got an error page?)")
            return ""
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"[lvr] {season}: {len(r.content)/1e6:.1f} MB")
        return path
    except Exception as e:
        print(f"[lvr] {season}: download error: {e}")
        return ""


def read_csv_from_zip(zpath, member, tolerant=False):
    """Read one CSV out of a season zip. Returns a DataFrame or None.

    Handles the two header rows and the BOM. Everything is read as str: the
    registry uses '' and '--' freely, and letting pandas infer dtypes turns a
    column into float64 the moment one row is blank.

    `tolerant` exists for ONE reason and is off everywhere else. PRE-SALE files
    carry rows with an extra unquoted field and fail a strict read outright —
    "Expected 30 fields, saw 31". Skipping those rows recovers essentially all
    of them, and one of the affected files is 115S1 臺北市 with 1,184 rows, so
    dropping the file whole is not an option.

    Two figures, because they are easy to confuse. Across the WHOLE on-disk
    cache (14 seasons, including the three out-of-window one-offs) it is 12 of
    289 files and 15,741 of ~15,759 rows recovered. Inside the 112S4..115S2
    window a build actually reads, it is 6 files, 7,721 rows kept and 7 skipped
    — which is what the run prints, so the stdout and this docstring reconcile.

    It is NOT enabled for sales or leases, and must not be: those files parse
    cleanly today (308 and 289 of them, zero failures), so a tolerant read there
    would convert a future export bug into silent data loss. The count of
    skipped rows is printed rather than swallowed, because a recovery that does
    not say what it cost is just a quieter kind of loss.
    """
    try:
        with zipfile.ZipFile(zpath) as z:
            names = {n.lower(): n for n in z.namelist()}
            if member.lower() not in names:
                return None
            with z.open(names[member.lower()]) as fh:
                raw = fh.read()
    except Exception as e:
        print(f"[lvr] open {member} from {os.path.basename(zpath)}: {e}")
        return None
    try:
        return pd.read_csv(io.BytesIO(raw), dtype=str, skiprows=[1],
                           encoding="utf-8-sig", low_memory=False)
    except Exception as e:
        if not tolerant:
            print(f"[lvr] read {member} from {os.path.basename(zpath)}: {e}")
            return None
    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, skiprows=[1],
                         encoding="utf-8-sig", low_memory=False,
                         on_bad_lines="skip")
    except Exception as e:
        print(f"[lvr] read {member} from {os.path.basename(zpath)}: {e}")
        return None
    # Two header rows, so the data-row count is lines - 2.
    expect = max(0, raw.decode("utf-8-sig", errors="replace").count("\n") - 2)
    lost = expect - len(df)
    print(f"[lvr] {os.path.basename(zpath)}/{member}: ragged file, "
          f"kept {len(df):,} rows, skipped {max(0, lost):,}")
    return df


def seasons_through(last, first=FIRST_CLEAN_SEASON):
    """Every season id from `first` to `last` inclusive, e.g. 112S4..115S2."""
    def parse(s):
        m = re.fullmatch(r"(\d{3})S([1-4])", s)
        return (int(m.group(1)), int(m.group(2))) if m else None
    a, b = parse(first), parse(last)
    if not a or not b:
        print(f"[lvr] bad season range {first}..{last}")
        return []
    out, cur = [], a
    while cur <= b:
        out.append(f"{cur[0]}S{cur[1]}")
        cur = (cur[0] + 1, 1) if cur[1] == 4 else (cur[0], cur[1] + 1)
    return out


def _park_totals(zpath, member):
    """編號 -> (parking price, parking area m2, space count, first 車位類別).

    Each zip ships a `*_park.csv` beside the main file, keyed on 編號, itemising
    every parking space in a transaction. One sale can carry several, so they sum.
    Measured coverage: 100% of parking-bundled rows have a row here, and 73% of
    sales (48% of leases) carry a non-zero price.
    """
    d = read_csv_from_zip(zpath, member)
    if d is None or d.empty or "編號" not in d.columns:
        return {}
    price = pd.to_numeric(d.get("車位價格"), errors="coerce").fillna(0.0)
    area = pd.to_numeric(d.get("車位面積平方公尺"), errors="coerce").fillna(0.0)
    typ = d.get("車位類別", pd.Series("", index=d.index)).fillna("").astype(str).str.strip()
    # Sums for the subtraction, plus the per-SPACE view the sum throws away:
    # how many spaces the transaction carries and the first one's 車位類別.
    # The parking section needs both, and reading these files twice (they are
    # 44 members per season) is what this avoids.
    g = pd.DataFrame({"編號": d["編號"], "p": price, "a": area, "t": typ}) \
        .groupby("編號").agg(p=("p", "sum"), a=("a", "sum"), n=("p", "size"), t=("t", "first"))
    return {k: (float(r.p), float(r.a), int(r.n), str(r.t)) for k, r in g.iterrows()}


def load_presale_season(season, cache_dir=None):
    """Pre-sale (預售屋) records for one season, raw but tagged.

    A separate entry point rather than a third key on load_season(), because
    the main build loads every season and would otherwise pay the IO for a file
    it does not use. Parking is attached the same way, from the matching
    `*_b_park.csv` sub-file, which does exist.

    Tolerant reading is ON here and only here — see read_csv_from_zip.
    """
    zpath = download_season(season, cache_dir)
    if not zpath:
        return None
    frames = []
    for c in COUNTIES:
        df = read_csv_from_zip(zpath, f"{c}_lvr_land_b.csv", tolerant=True)
        if df is None or df.empty:
            continue
        df["county"] = c
        df["season"] = season
        pk = _park_totals(zpath, f"{c}_lvr_land_b_park.csv")
        if pk and "編號" in df.columns:
            df["park_price"] = df["編號"].map(lambda k: pk.get(k, (0.0, 0.0))[0])
            df["park_area_m2"] = df["編號"].map(lambda k: pk.get(k, (0.0, 0.0))[1])
        else:
            df["park_price"] = 0.0
            df["park_area_m2"] = 0.0
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else None


def clean_presale(df, subtract_parking=True, exclude_related=True,
                  residential_only=True, exclude_rescinded=True):
    """Pre-sale dwellings, on the same terms the completed side is cleaned on.

    Every filter is a parameter for the same reason they are on clean_sales: an
    honesty ladder has to walk this code path with flags flipped, or it is
    measuring a reimplementation rather than the pipeline.

    Three things differ from clean_sales and each is forced by the data:

    * There is no `交易標的 == 房地(土地+建物)` shortcut worth taking. 82.3% of
      RAW pre-sale rows carry a parking space, so dropping the bundled ones
      would throw away five sixths of the market and keep a strange remainder.
      Parking is subtracted instead, with require_price=True, exactly as on the
      completed side. Note the 82.3% is the raw pre-sale rate: it is not a
      contrast against the comparison group, which carries a similar rate, and
      the subtraction is defensible on its own without one.
    * 建築完成年月 is empty on every row, because the building does not exist.
      No age filter is possible here, and any comparison against completed sales
      has to control for age on the OTHER side.
    * The address is a project-unit reference ("...三重路200巷A-3F"), not a 門牌.
      addr_key cannot key it, so nothing here can be matched to a building.
      建案名稱 is the only stable grouping key, and it is 100% populated.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    if residential_only:
        d = d[d["建物型態"].isin(RESIDENTIAL_PRESALE)
              & d["主要用途"].fillna("").str.contains("住家用")]
    if exclude_related and "備註" in d.columns:
        d = d[~d["備註"].fillna("").str.contains(RELATED_PARTY, na=False)]
    # 解約情形 is a pre-sale-only column: a contract signed and later rescinded,
    # stamped "1150329全部解約". The price was agreed and then unwound, so it is
    # not a transaction. Only ~0.9% of rows carry it and removing them moves
    # nothing measurable — it is a parameter anyway, because the ladder exists
    # so that no cleaning decision is silent, and a filter nobody can see is
    # exactly the thing this project refuses.
    if exclude_rescinded and "解約情形" in d.columns:
        d = d[d["解約情形"].fillna("").str.strip() == ""]
    if d.empty:
        return pd.DataFrame()
    d["area_ping"] = d["建物移轉總面積平方公尺"].map(num) * PING_PER_M2
    d["price"] = d["總價元"].map(num)
    d["q"] = d["交易年月日"].map(roc_to_quarter)
    d["date"] = d["交易年月日"].map(roc_to_iso)
    d["project"] = d["建案名稱"].fillna("").astype(str).str.strip()
    d["rooms"] = pd.to_numeric(
        d.get("建物現況格局-房", pd.Series("", index=d.index)), errors="coerce")
    if subtract_parking:
        if "park_price" not in d.columns:
            d["park_price"] = 0.0
            d["park_area_m2"] = 0.0
        d = _subtract_parking(d, "price", "area_ping", require_price=True)
    return d[(d.area_ping > 5) & (d.price > 1e6) & d.q.notna()]


def load_season(season, cache_dir=None):
    """Return {'sale': df, 'rent': df}, raw but tagged, with parking attached.

    `park_price` / `park_area_m2` come from the `*_park.csv` sub-file and are 0
    where the transaction has no parking or the registry did not itemise it.
    They let clean_sales/clean_rents SUBTRACT parking instead of only excluding
    the transactions that carry it.
    """
    zpath = download_season(season, cache_dir)
    if not zpath:
        return {"sale": None, "rent": None}
    out = {}
    for kind, suffix in (("sale", "a"), ("rent", "c")):
        frames = []
        for c in COUNTIES:
            df = read_csv_from_zip(zpath, f"{c}_lvr_land_{suffix}.csv")
            if df is None or df.empty:
                continue
            df["county"] = c
            df["season"] = season
            pk = _park_totals(zpath, f"{c}_lvr_land_{suffix}_park.csv")
            if pk and "編號" in df.columns:
                _z = (0.0, 0.0, 0, "")
                df["park_price"] = df["編號"].map(lambda k: pk.get(k, _z)[0])
                df["park_area_m2"] = df["編號"].map(lambda k: pk.get(k, _z)[1])
                df["park_n"] = df["編號"].map(lambda k: pk.get(k, _z)[2])
                df["park_type"] = df["編號"].map(lambda k: pk.get(k, _z)[3])
            else:
                df["park_price"] = 0.0
                df["park_area_m2"] = 0.0
                df["park_n"] = 0
                df["park_type"] = ""
            frames.append(df)
        out[kind] = pd.concat(frames, ignore_index=True) if frames else None
    return out


# ═══════════════════════════════════════════════════════ PURE COMPUTE ════

def roc_to_iso(v):
    """1150601 -> '2026-06-01'. Returns '' for anything malformed."""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return ""
    y, m, d = n // 10000, (n // 100) % 100, n % 100
    if not (1 <= m <= 12 and 1 <= d <= 31 and y > 0):
        return ""
    return f"{y + 1911:04d}-{m:02d}-{d:02d}"


def roc_to_quarter(v):
    """1150601 -> 4602, a sortable integer quarter index (rocYear*4 + q)."""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    y, m = n // 10000, (n // 100) % 100
    if not (1 <= m <= 12 and y > 0):
        return None
    return y * 4 + (m - 1) // 3


def quarter_label(q):
    """461 -> '115Q2' (ROC year, matching how the registry is published).

    The index is base-4 (rocYear*4 + (month-1)//3), so 4602 is not a value this
    ever receives -- quarter_label(4602) would read '1150Q3'. The arithmetic was
    always right; the worked example never was, in both this function and
    roc_to_quarter above, which is every season number on the page.
    """
    if q is None:
        return ""
    return f"{q // 4}Q{q % 4 + 1}"


def num(v, default=0.0):
    """Registry numerics carry commas, ='' wrappers and '--' for null."""
    if v is None:
        return default
    s = str(v).strip().strip('="').replace(",", "")
    if not s or s in ("--", "X", "N/A", "nan"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _subtract_parking(d, price_col, area_col, require_price):
    """Take the parking out of a bundled transaction instead of dropping it.

    The registry itemises every space in a `*_park.csv` sub-file, so this is
    arithmetic on numbers the PARTIES stated, not a model of what a space is
    worth. Where nothing was itemised there is nothing to subtract.

    `require_price` differs by side, and the difference is not cosmetic. On a
    SALE a bundled space always has a value, so a zero means the registry did not
    record it and the row cannot be corrected (dropped). On a LEASE a zero was
    ASSUMED to mean the space came with the flat at no extra rent, so only the
    AREA is taken out or the rent-per-ping is computed over a car park.

    That assumption was tested within building at full N (v2.0) and FAILS:
    total rent per m2 of total area is the same whether or not the space is
    itemised (the un-itemised lease should sit ~11.5% lower if the space were
    free), i.e. the parking rent is inside the dwelling rent on the ~21,300
    un-itemised market leases. This function is unchanged; from v2.1
    underwrite.impute_parking_rent subtracts an imputed per-space rent from
    those rows after keying, and that is the headline. The old treatment stays
    a published bound in payload key `parking_audit`
    (underwrite.parking_audit_block); see docs/REPRODUCING.md rows 2.0-2.1.
    """
    has = d["交易標的"].astype(str).str.contains("車位", na=False)
    if require_price:
        d = d[~has | (d.park_price > 0)].copy()
        has = d["交易標的"].astype(str).str.contains("車位", na=False)
    d.loc[has, price_col] = d.loc[has, price_col] - d.loc[has, "park_price"]
    d.loc[has, area_col] = (d.loc[has, area_col]
                            - d.loc[has, "park_area_m2"] * PING_PER_M2)
    return d


# 備註 strings that mark a sale as NOT arm's-length. The registry writes these
# free-form, so this is a substring test rather than a code lookup; the three
# spellings below are what actually appears in the files.
RELATED_PARTY = "親友|親屬|關係人"

# Rent-side 備註: who pays the management fee. The registry's canonical phrase
# is 租金總額含管理費 (23,110 of the 23,347 keyed clean lets the looser test
# matches); the looser test also catches 租金含管理費-style variants.
# 不含管理費 is checked FIRST because it contains the substring 含管理費.
MGMT_INCL = "含管理費"
MGMT_NOT_INCL = "不含管理費"
# Explicit tenant-pays statements. 管理費另計 is 6 rows in 115S2; the real
# opposite phrasings are 租金不含管理費 / 此租約訂定金額不含管理費 / 另有管理費N元 /
# 承租人每月負擔管理費N元 / 租金已扣除管理費. A bare `管理費N元` with no 含 is
# read as a separate charge -- the amount is stated apart from the rent.
MGMT_EXCL = re.compile(r"不含管理費|管理費另計|另有管理費|租金已扣除管理費|"
                       r"承租人.{0,12}管理費|管理費.{0,12}承租人|管理費[:：]?\s*\d+元")


def clean_sales(df, exclude_parking=True, subtract_parking=False,
                exclude_related=True):
    """Whole residential dwellings, parking excluded by construction.

    `exclude_parking` is a parameter rather than a constant so the honesty
    ladder can walk the SAME code path with one filter switched off. The ladder
    used to reimplement this, and the two drifted by a building — a small error
    that made the ladder quietly untrue about its own last rung.

    `交易標的 == 房地(土地+建物)` drops the '+車位' variants, so the price is a
    dwelling price with no parking component to model away. The rent side gets
    the mirror-image filter, which makes the two sides symmetric with zero
    assumptions — the registry's own 車位總價元 field can't do this job because
    on the rent side it is itemised in barely 1% of rows.

    `exclude_related` drops 親友間交易 — sales between relatives. Measured over
    all 11 seasons and all 22 counties: 21,028 of 226,467 clean residential
    sales carry the flag (9.29%), and within the same district × building type ×
    season they transact at a median 0.757 of the arm's-length price. That is
    24.9% below market.

    A yield is rent over PRICE, so a price 24.9% low does not shift a yield a
    little — it inflates that building's gross yield by 33%. Leaving these in
    biases the headline in exactly the flattering direction, which is the one
    direction this page cannot afford to be wrong in.

    Unlike parking, this filter is deliberately NOT symmetric. The same flag on
    the rent side appears on 8 of 5,744 leases (0.14%) in the same season, so
    mirroring it would drop a rounding error and cost real matches. Family
    property transfers are common because they are a tax instrument; family
    leases are rarely registered at all.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    ok_targets = (["房地(土地+建物)"] if (exclude_parking and not subtract_parking)
                  else ["房地(土地+建物)", "房地(土地+建物)+車位"])
    d = df[
        (df["交易標的"].isin(ok_targets))
        & (df["建物型態"].isin(RESIDENTIAL))
        & (df["主要用途"].fillna("").str.contains("住家用"))
    ].copy()
    if exclude_related and "備註" in d.columns:
        d = d[~d["備註"].fillna("").str.contains(RELATED_PARTY, na=False)]
    d["area_ping"] = d["建物移轉總面積平方公尺"].map(num) * PING_PER_M2
    d["price"] = d["總價元"].map(num)
    d["q"] = d["交易年月日"].map(roc_to_quarter)
    d["date"] = d["交易年月日"].map(roc_to_iso)
    if subtract_parking:
        if "park_price" not in d.columns:
            d["park_price"] = 0.0
            d["park_area_m2"] = 0.0
        d = _subtract_parking(d, "price", "area_ping", require_price=True)
    d["built_roc_y"] = pd.to_numeric(d["建築完成年月"].str[:3], errors="coerce")
    d["total_floor"] = d.get("總樓層數", pd.Series("", index=d.index)).fillna("")
    d["floor_raw"] = d.get("移轉層次", pd.Series("", index=d.index)).fillna("")
    d["rooms"] = pd.to_numeric(
        d.get("建物現況格局-房", pd.Series("", index=d.index)), errors="coerce")
    return d[(d.area_ping > 5) & (d.price > 1e6) & d.q.notna()]


def clean_rents(df, exclude_parking=True, exclude_social=True, exclude_rooms=True,
                subtract_parking=False):
    """Whole residential lettings at market rent.

    Three exclusions, each removing a population that is not comparable to a
    sale: parking-bundled leases (交易標的), subsidised social housing
    (租賃住宅服務), and sub-let rooms whose floor area describes the building
    rather than the let space (出租型態).
    """
    if df is None or df.empty:
        return pd.DataFrame()
    missing = [c for c in ("租賃住宅服務", "出租型態") if c not in df.columns]
    if missing:
        print(f"[lvr] rent frame missing {missing} — pre-{FIRST_CLEAN_SEASON} season?")
        return pd.DataFrame()
    ok_targets = (["租賃房屋"] if (exclude_parking and not subtract_parking)
                  else ["租賃房屋", "租賃房屋+車位"])
    d = df[(df["交易標的"].isin(ok_targets)) & (df["建物型態"].isin(RESIDENTIAL))].copy()
    if exclude_social:
        d = d[~d["租賃住宅服務"].fillna("").isin(SOCIAL_HOUSING)]
    if exclude_rooms:
        d = d[d["出租型態"].fillna("").isin(WHOLE_UNIT)]
    d["area_ping"] = d["建物總面積平方公尺"].map(num) * PING_PER_M2
    d["rent"] = d["總額元"].map(num)
    d["q"] = d["租賃年月日"].map(roc_to_quarter)
    d["date"] = d["租賃年月日"].map(roc_to_iso)
    # OBSERVED on-site management. The registry never gives an amount, but this
    # flag means the management-fee term can be data-gated per building instead
    # of guessed from 建物型態 ("towers have fees, walk-ups don't"), which is the
    # assumption that manufactured the project's original, and false, hypothesis.
    if subtract_parking:
        if "park_price" not in d.columns:
            d["park_price"] = 0.0
            d["park_area_m2"] = 0.0
        d = _subtract_parking(d, "rent", "area_ping", require_price=False)
    # A bundled lease whose space was never itemised: the rows the assumption
    # above rests on. Flagged on every path so the audit can find them; all 0
    # when bundled leases were excluded upstream (the ladder's early rungs).
    _bund = d["交易標的"].astype(str).str.contains("車位", na=False)
    d["park_unpriced"] = ((_bund & (d["park_price"] == 0)).astype(int)
                          if "park_price" in d.columns else 0)
    d["has_mgr"] = (d.get("有無管理員", pd.Series("", index=d.index))
                    .fillna("").eq("有").astype(int))
    # What the lease itself says about the fee. 1 = the rent INCLUDES it (the
    # landlord bears it); rent_excl_mgmt 1 = the tenant pays it separately.
    # 0 on both is UNSTATED -- not evidence of either, and 52% of lets in
    # staffed buildings. 備註 is free text; filing habits differ by county.
    _note = d.get("備註", pd.Series("", index=d.index)).fillna("").astype(str)
    d["rent_incl_mgmt"] = (_note.str.contains(MGMT_INCL, regex=False)
                           & ~_note.str.contains(MGMT_NOT_INCL, regex=False)).astype(int)
    d["rent_excl_mgmt"] = (_note.str.contains(MGMT_EXCL)
                           & (d.rent_incl_mgmt == 0)).astype(int)
    # Three fields the registry has carried all along and this pipeline ignored.
    #
    # 有無附傢俱 is a straight confound on rent: a furnished let commands a
    # premium, and a rent series that mixes the two is measuring furniture as
    # well as housing. 租賃層次 is the floor, which is the one building attribute
    # every renter in Taipei has an opinion about and nobody has published a
    # number for. 房 is the bedroom count, which makes two lets on the same floor
    # area comparable in a way square metres alone do not.
    d["furnished"] = (d.get("有無附傢俱", pd.Series("", index=d.index))
                      .fillna("").eq("有").astype(int))
    d["floor_raw"] = d.get("租賃層次", pd.Series("", index=d.index)).fillna("")
    d["rooms"] = pd.to_numeric(
        d.get("建物現況格局-房", pd.Series("", index=d.index)), errors="coerce")
    # 3k floor / 500k ceiling: below is a mis-keyed 押金 or a token family lease,
    # above is a whole-building let mis-filed as a dwelling.
    return d[(d.area_ping > 5) & (d.rent > 3000) & (d.rent < 500000) & d.q.notna()]


def clean_parking_sales(df, exclude_related=True):
    """Single-space parking SALES: a space sold alone, or the itemised space in
    a flat+space sale. Price is per space; there is no area column on purpose.

    standalone: 交易標的 == 車位, price = 總價元 (verified equal to the park
    file's 車位價格 on 100% of single-space rows that carry one).
    bundled_itemised: 房地(土地+建物)+車位 with an itemised park price > 0.
    Rows carrying two or more spaces, or none in the park file, are dropped:
    a multi-space total is not a per-space price.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    need = [c for c in ("交易標的", "總價元", "備註", "交易年月日", "park_n", "park_price")
            if c not in df.columns]
    if need:
        print(f"[lvr] parking sale frame missing {need}")
        return pd.DataFrame()
    d = df[df["交易標的"].isin(PARK_SALE_TARGETS)].copy()
    d["standalone"] = d["交易標的"].eq("車位")
    d["related"] = d["備註"].fillna("").astype(str).str.contains(RELATED_PARTY, na=False)
    d["total"] = d["總價元"].map(num)
    d["price"] = np.where(d.standalone, d.total, d.park_price)
    d["cls"] = np.where(d.standalone, "standalone", "bundled_itemised")
    d["sp_type"] = d["park_type"].fillna("").astype(str) if "park_type" in d.columns else ""
    d["q"] = d["交易年月日"].map(roc_to_quarter)
    d["date"] = d["交易年月日"].map(roc_to_iso)
    d = d[(d.park_n == 1)]
    d = d[d.standalone | (d.park_price > 0)]
    d = d[(d.price > 0) & d.q.notna()]
    if exclude_related:
        d = d[~d.related]
    return d


def clean_parking_rents(df, exclude_social=True):
    """Single-space parking LEASES: a space let alone, or the itemised space
    rent in a flat+space lease. Rent is per space per month; no area column.

    standalone: 交易標的 == 車位, rent = 總額元.
    bundled_priced: 租賃房屋+車位 with 車位總額元 > 0 (verified equal to the
    park file's 車位價格 on 100% of single-space priced rows, so the main-file
    field is authoritative and the park row supplies only n and 車位類別).
    No rent floor: a few hundred leases carry a token 車位總額元 of NT$100-400;
    the yield band removes those that pair, and the count is published.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    need = [c for c in ("交易標的", "總額元", "車位總額元", "租賃住宅服務", "租賃年月日",
                        "park_n") if c not in df.columns]
    if need:
        print(f"[lvr] parking rent frame missing {need}")
        return pd.DataFrame()
    d = df[df["交易標的"].isin(PARK_LEASE_TARGETS)].copy()
    d["standalone"] = d["交易標的"].eq("車位")
    d["social"] = d["租賃住宅服務"].fillna("").isin(SOCIAL_HOUSING)
    d["park_total"] = d["車位總額元"].map(num)
    d["rent"] = np.where(d.standalone, d["總額元"].map(num), d.park_total)
    d["cls"] = np.where(d.standalone, "standalone", "bundled_priced")
    d["sp_type"] = d["park_type"].fillna("").astype(str) if "park_type" in d.columns else ""
    d["q"] = d["租賃年月日"].map(roc_to_quarter)
    d["date"] = d["租賃年月日"].map(roc_to_iso)
    d = d[(d.park_n == 1)]
    d = d[d.standalone | (d.park_total > 0)]
    d = d[(d.rent > 0) & d.q.notna()]
    if exclude_social:
        d = d[~d.social]
    return d


def social_vs_market_rents(df):
    """Rent per 坪 for SUBSIDISED vs MARKET leases, on otherwise identical filters.

    The excluded 36% is not waste — it is the only direct measurement available
    of how far the registry's raw rent sample sits from a market rent. Everything
    except the 租賃住宅服務 test is held constant, so the gap is attributable.
    """
    if df is None or df.empty or "租賃住宅服務" not in df.columns:
        return {}
    base = df[
        (df["交易標的"] == "租賃房屋")
        & (df["建物型態"].isin(RESIDENTIAL))
        & (df["出租型態"].fillna("").isin(WHOLE_UNIT))
    ].copy()
    if base.empty:
        return {}
    base["area_ping"] = base["建物總面積平方公尺"].map(num) * PING_PER_M2
    base["rent"] = base["總額元"].map(num)
    base = base[(base.area_ping > 5) & (base.rent > 3000) & (base.rent < 500000)]
    base["ppp"] = base.rent / base.area_ping
    out = {}
    for label, mask in (
        ("social", base["租賃住宅服務"].fillna("").isin(SOCIAL_HOUSING)),
        ("market", ~base["租賃住宅服務"].fillna("").isin(SOCIAL_HOUSING)),
    ):
        sub = base[mask]
        out[label] = {
            "n": int(len(sub)),
            "rent_ping": round(float(sub.ppp.median()), 1) if len(sub) else None,
            "area_ping": round(float(sub.area_ping.median()), 1) if len(sub) else None,
        }
    s, m = out["social"]["rent_ping"], out["market"]["rent_ping"]
    out["gap_pct"] = round((s - m) / m * 100, 1) if s and m else None
    out["social_share_pct"] = round(out["social"]["n"] / max(1, len(base)) * 100, 1)
    return out


if __name__ == "__main__":  # smoke test
    s = load_season("115S2")
    print("raw   ", {k: (0 if v is None else len(v)) for k, v in s.items()})
    print("clean ", {"sale": len(clean_sales(s["sale"])),
                     "rent": len(clean_rents(s["rent"]))})
