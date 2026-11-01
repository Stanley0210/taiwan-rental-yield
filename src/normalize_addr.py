"""
normalize_addr.py — Taiwanese 門牌 normalisation for same-building matching.

This is the load-bearing module of the housing pipeline. Two 實價登錄 records
refer to the same building iff their normalised keys are equal, so a weak
normaliser looks *exactly* like a thin market: few matches, no error, no clue.
That failure mode is why this lives in its own file with its own regression
fixture (tests/fixtures/addr_pairs.csv) rather than as a lambda inside the
matcher.

What the source data actually looks like (verified against season 115S2):

    臺北市中山區復興北路３８０巷１１號４樓
    臺北市中山區南京東路三段８９巷２０號二樓等共有部分
    新北市板橋區文化路一段１８８巷１弄５號３樓

So the grammar is:

    縣市 區 路/街/大道 [N段] [N巷] [N弄] N號[之N] [樓層/單位/描述]
             └──────────────── the BUILDING ──────────────┘ └── the UNIT ──┘

`addr_key()` keeps the building and discards the unit: a 4th-floor lease and a
12th-floor sale in the same tower must collapse to one key. Everything from the
building's 號 onward is unit-level and goes -- see the third grammar fact below
for which 號 that is.

Three grammar facts drive the implementation:

* Digits arrive full-width (３８０) — NFKC folds them, and also folds 巷/號 look-alikes.
* 段 is written in Chinese numerals (三段) while 巷/弄/號 are Arabic. Only 段
  needs the numeral map; converting more would corrupt road names that legitimately
  contain numerals (e.g. 九如路, 三民路).
* 樓 is sometimes Chinese (二樓), sometimes Arabic (4樓), so the cut is made at
  a 號 FOLLOWED BY a unit designator rather than at a parsed floor. This module
  said for a long time that "a unit designator never contains 號" and cut at the
  last one; the registry falsifies that in two ways -- 146號五樓1號 (the flat's
  own 號) and 296號十二樓、298號 (a second 門牌 on one record) -- which keyed 343
  distinct keys to a flat or to two buildings at once.
"""

import re
import unicodedata

# 段 only ever runs 一..十 in practice; anything larger is already Arabic.
_CN_NUM = {
    "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
    "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
}

# Descriptive tails the registry appends to a 門牌. These follow the 號 in the
# raw string but must be stripped BEFORE the cut, because some of them ("等5筆")
# contain digits that would otherwise confuse the range rules.
_TAIL = re.compile(r"(等共有部分|共有部分|等\d*筆|全部|等房屋|等地號).*$")

# 5~7號 / 5、7號 / 5-7號 -> 5號. The registry uses a range when one owner holds
# consecutive 門牌; the first is the canonical one and is what the other side of
# the join will carry.
_RANGE = re.compile(r"(\d+)\s*[~～、,，\-－—–]\s*\d+\s*號")

# What follows the BUILDING's 號: a floor, a room, or a 之N unit. Used to pick
# which 號 ends the building when a record carries more than one.
_UNIT_AFTER = re.compile(r"^(?:[0-9０-９一二三四五六七八九十百]+)?(?:樓|F|f|室|之)")
# A record that lists a second 門牌 after one of these separators.
_SPLIT = re.compile(r"[、,，;；]")

_SEC = re.compile(r"([一二三四五六七八九十])段")
_NUM_AT_END = re.compile(r"^(?P<head>.*?)(?P<no>\d+)(?:之(?P<sub>\d+))?號$")


def _fold(s):
    """NFKC, the 臺/台 split, and the 巿/市 mis-encoding.

    NFKC does NOT merge 巿 (U+5DFF, 'city' with a vertical stroke) and 市
    (U+5E02) -- they are separate CJK ideographs, so the normaliser saw
    屏東巿公裕街242號 and 屏東市公裕街242號 as different buildings. Measured in
    the pinned window: 3,456 SALE rows carry it (3,452 of them county t) and
    ZERO lease rows do, so the damage is one-sided -- a sale spelled 巿 could
    never find its own lease.
    """
    s = unicodedata.normalize("NFKC", s)
    return s.replace("臺", "台").replace("巿", "市")


def addr_key(addr):
    """Normalise a 門牌 to a BUILDING key. Returns '' when unparseable.

    Unparseable is a real category, not a failure: land-only records and
    buildings registered under 段小段 rather than a 門牌 have no 號 at all and
    genuinely cannot be matched by address. Returning '' lets the caller drop
    them explicitly instead of silently matching them to each other.
    """
    if not isinstance(addr, str) or not addr.strip():
        return ""
    s = _fold(addr.strip())
    s = re.sub(r"\s+", "", s)
    s = _TAIL.sub("", s)
    s = _SEC.sub(lambda m: _CN_NUM[m.group(1)] + "段", s)
    s = _RANGE.sub(r"\1號", s)
    # 「A號…、B號…」 is two 門牌 on one record. The first is this building; the
    # whole string keyed something that matched nothing on the other side of the
    # join. AFTER _RANGE, because 「5、7號」 is a range and must collapse first --
    # splitting on 、 before that left "…和平東路2段5" with no 號 at all.
    s = _SPLIT.split(s, 1)[0]

    # A unit designator CAN contain 號 -- 146號五樓1號, 11號四樓之15號 -- and a
    # record can carry a second 門牌 after a separator -- 296號十二樓、298號.
    # Cutting at the last one keyed a FLAT, or two buildings at once, for 343
    # distinct keys. Cut instead at the first 號 that is followed by a unit
    # designator; fall back to the last when none is. The range collapse has
    # already run, so "5~7號" is "5號" by here.
    hits = list(re.finditer("號", s))
    if not hits:
        return ""
    for h in hits:
        if _UNIT_AFTER.match(s[h.end():]):
            return s[: h.end()]
    return s[: hits[-1].end()]


def addr_parts(addr):
    """Split a key into its matching components. Used for the tier ladder.

    Returns {'key','street','number','sub'} or None. `street` is everything
    above the house number — road + 段 + 巷 + 弄 — which is the tier-2 unit
    (same street segment). `number` is the 號; `sub` the 之N when present.
    """
    key = addr_key(addr)
    if not key:
        return None
    m = _NUM_AT_END.match(key)
    if not m:
        return {"key": key, "street": key, "number": None, "sub": None}
    return {
        "key": key,
        "street": m.group("head"),
        "number": int(m.group("no")),
        "sub": int(m.group("sub")) if m.group("sub") else None,
    }


def street_key(addr):
    """Tier-2 key: the street segment (road + 段 + 巷 + 弄), no house number."""
    p = addr_parts(addr)
    return p["street"] if p else ""
