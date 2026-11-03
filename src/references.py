#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The bibliography, shared by both editions of the paper.

Why this is a module and not prose in each report: the two editions are
separate generators on purpose (a shared positional template is how the site's
JavaScript printed a count as a percentage four times), but a *citation* has no
language -- an author's surname and a year read the same in both. So the data
lives here once and each edition renders its own headings around it.

The inline label is DERIVED, never typed. `cite("horowitz1995")` reads the
surnames and the year out of the entry, so the prose cannot name a work the
bibliography does not carry, and `uncited()` refuses to let a report build with
an entry nothing cites. That is the same "derive, don't type" rule the paper
applies to its own numbers (section 17), turned on its own references.

Every entry below was checked against the publisher or RePEc record while the
references section was written (2026-11-03), including page ranges -- Heckman
(1979) ends at 162, not 161, which is a common miscitation.
"""

# ── the works ────────────────────────────────────────────────────────────────
# group: which heading the entry prints under, in the order the groups appear.
# authors: surnames only, for the derived inline label.
# full: the byline as the list prints it.
REFERENCES = {
    # Partial identification -- the frame section 6 works inside.
    "manski1989": dict(
        group="bounds", year=1989, authors=["Manski"], full="Manski, C. F.",
        title="Anatomy of the selection problem",
        where="Journal of Human Resources 24(3), 343–360",
        why="States the problem this project has: when the outcome is observed "
            "selectively, the sampling process does not identify the population "
            "quantity, and no amount of data cleaning changes that."),
    "horowitz1995": dict(
        group="bounds", year=1995, authors=["Horowitz", "Manski"],
        full="Horowitz, J. L., and C. F. Manski",
        title="Identification and robustness with contaminated and corrupted data",
        where="Econometrica 63(2), 281–302",
        why="The sharp-bound construction section 6 uses: put the unobserved mass "
            "at the extremes of its support and the parameter is bounded, not "
            "point-identified."),
    "manski2003": dict(
        group="bounds", year=2003, authors=["Manski"], full="Manski, C. F.",
        title="Partial Identification of Probability Distributions",
        where="Springer Series in Statistics. Springer, New York",
        why="Book-length treatment of prediction with missing data; the source for "
            "why a median's worst-case interval is finite only once more than half "
            "the population is observed."),

    # Selection in housing transaction data -- why section 5 is the finding.
    "heckman1979": dict(
        group="selection", year=1979, authors=["Heckman"], full="Heckman, J. J.",
        title="Sample selection bias as a specification error",
        where="Econometrica 47(1), 153–162",
        why="The correction this project deliberately does not run: it needs a "
            "model of why a lease is filed, and section 5 shows the filing rule is "
            "institutional rather than behavioural."),
    "gatzlaff1997": dict(
        group="selection", year=1997, authors=["Gatzlaff", "Haurin"],
        full="Gatzlaff, D. H., and D. R. Haurin",
        title="Sample selection bias and repeat-sales index estimates",
        where="Journal of Real Estate Finance and Economics 14(1–2), 33–50",
        why="The same structure one step removed: an index built only from houses "
            "that sell twice is biased because selling twice is not random. Here it "
            "is leasing and selling, and the surviving share is far smaller."),

    # Price and rent measured on the same property.
    "bracke2015": dict(
        group="pricerent", year=2015, authors=["Bracke"], full="Bracke, P.",
        title="House prices and rents: microevidence from a matched data set in "
              "Central London",
        where="Real Estate Economics 43(2), 403–431",
        why="The closest methodological sibling: rent-price ratios from properties "
            "both sold and let, matched within six months. Agency data, one city, "
            "1,922 properties; this project's analogue is a public registry, a "
            "whole country, and a published denominator."),
    "himmelberg2005": dict(
        group="pricerent", year=2005, authors=["Himmelberg", "Mayer", "Sinai"],
        full="Himmelberg, C., C. Mayer, and T. Sinai",
        title="Assessing high house prices: bubbles, fundamentals and misperceptions",
        where="Journal of Economic Perspectives 19(4), 67–92",
        why="Why a gross yield is not a verdict: the user-cost identity holds that "
            "a low rent-price ratio can be a rational response to low real rates "
            "and expected growth. Section 14's net yield is a cost model, not a "
            "user cost, and does not settle that question."),

    # Taiwan.
    "chang2018": dict(
        group="taiwan", year=2018, authors=["Chang", "Chen"],
        full="Chang, C.-O. (張金鶚), and S.-M. Chen",
        title="Dilemma of housing demand in Taiwan",
        where="International Real Estate Review 21(3), 397–418",
        why="Carries the Taiwan rental-yield figure this paper is measured against. "
            "Its Table 5 gives a rent multiplier of 64 and a yield of 1.57%, "
            "sourced to Global Property Guide (2018) -- a listings aggregator, not "
            "transaction data. That provenance is the gap this project fills."),
    "yang2018": dict(
        group="taiwan", year=2018, authors=["楊博宇"], full="楊博宇 (Yang, P.-Y.)",
        title="臺北市房地產預期增值為何高漲？──以租金乘數探討投資價值與消費價值的差異",
        where="碩士論文, 國立政治大學地政學系 (master's thesis, Department of Land "
              "Economics, National Chengchi University); advisers 張金鶚, 江穎慧",
        why="Taipei gross rent multiplier of about 50 from 591 asking rents against "
            "實價登錄 sales, 2013–2016. The closest published Taipei number built on "
            "the same registry, and it brackets this paper's Taipei median."),

    # Method: attribution, and intervals under clustering.
    "shorrocks2013": dict(
        group="method", year=2013, authors=["Shorrocks"], full="Shorrocks, A. F.",
        title="Decomposition procedures for distributional analysis: a unified "
              "framework based on the Shapley value",
        where="Journal of Economic Inequality 11(1), 99–126",
        why="The reason section 7 reports Shapley values rather than a filter "
            "sequence: the Shapley decomposition is the order-independent one, and "
            "this ladder's order demonstrably matters."),
    "cameron2008": dict(
        group="method", year=2008, authors=["Cameron", "Gelbach", "Miller"],
        full="Cameron, A. C., J. B. Gelbach, and D. L. Miller",
        title="Bootstrap-based improvements for inference with clustered errors",
        where="Review of Economics and Statistics 90(3), 414–427",
        why="Pairs within a building are clustered, and the cluster count is what "
            "limits precision. The two-stage bootstrap resamples buildings first "
            "for that reason; this is also the warning that few clusters make "
            "intervals optimistic, which is why district intervals carry an n floor."),
}

# ── external yield estimates this paper is compared against ──────────────────
# TYPED, NOT DERIVED -- the one table in this paper that is, and it says so in
# the report. These figures live on other people's pages and in other people's
# PDFs; nothing in housing_data.json can produce them and no test can check
# them. Each row therefore carries where it came from and when it was read, so
# a reader can re-check it the way they can re-check everything else here.
EXTERNAL_READ_ON = "2026-11-03"

# Global Property Guide's own per-city gross yields, transcribed from the page.
# Their method, quoted from it: median monthly rent x 12 / median purchase
# price, using "asking rents and list prices" from a listings platform. Note
# that is a ratio OF medians across different properties, not a median of
# per-property ratios -- the two are not the same statistic.
GPG_CITIES = {
    "臺北市": 1.97,
    "新北市": 2.19,
    "桃園市": 2.44,
    "高雄市": 2.57,
    "臺南市": 2.12,
}
GPG_NATIONAL = 2.26          # Q2 2026; was 2.20 in Q4 2025
GPG_UPDATED = "June 2026"
GPG_SOURCE = dict(
    group="data", year=2026, authors=["Global Property Guide"],
    full="Global Property Guide",
    title="Gross rental yields in Taiwan: Taipei and 4 other cities",
    where=f"globalpropertyguide.com, last updated {GPG_UPDATED}; read "
          f"{EXTERNAL_READ_ON}. Asking rents and list prices from a local "
          "listings platform, apartments of 1–5 bedrooms in five cities; gross "
          "yield computed as median monthly rent × 12 ÷ median purchase price",
    why="The figure in general circulation, and the one Chang and Chen (2018) "
        "report. Section 4 sets it beside the registry measurement city by city.")
REFERENCES["gpg2026"] = GPG_SOURCE

# Group headings are rendered by each edition in its own language; this fixes
# only the order they appear in.
GROUP_ORDER = ["bounds", "selection", "pricerent", "taiwan", "method", "data"]

_CITED = set()


def _who(r):
    a = r["authors"]
    return (a[0] if len(a) == 1 else
            f"{a[0]} and {a[1]}" if len(a) == 2 else
            f"{a[0]} et al.")


def cite(*keys):
    """Parenthetical label: '(Horowitz and Manski 1995; Manski 2003)'.

    A key with no entry raises KeyError here rather than printing a dangling
    name into the paper.
    """
    out = []
    for k in keys:
        r = REFERENCES[k]
        _CITED.add(k)
        # Non-breaking inside the label: a citation split as "Himmelberg et al." /
        # "2005" across a line break happened in the Chinese edition, where a CJK
        # line's only breakable spaces are the ones bracketing Latin text. It is
        # wrong in English too, so both editions get it.
        out.append(f"{_who(r)} {r['year']}".replace(" ", "&nbsp;"))
    return "(" + "; ".join(out) + ")"


def cite_t(key):
    """Textual form: 'Chang and Chen (2018)', to use as a sentence subject."""
    r = REFERENCES[key]
    _CITED.add(key)
    return f"{_who(r)} ({r['year']})".replace(" ", "&nbsp;")


def uncited():
    """Entries nothing has cited yet. A report refuses to build if any remain."""
    return sorted(k for k in REFERENCES if k not in _CITED)


def entries(group):
    """The works in one group, author then year."""
    rows = [(k, v) for k, v in REFERENCES.items() if v["group"] == group]
    return sorted(rows, key=lambda kv: (kv[1]["authors"][0], kv[1]["year"]))


# ── the same notes, for the Chinese edition ─────────────────────────────────
# A Chinese-language edition should not hand its reader English annotations, so
# each entry's note exists in both languages. The bibliographic fields above
# (author, year, title, journal, pages) are deliberately NOT translated: a
# citation has to be copyable into a reference manager exactly as published.
WHY_ZH = {'manski1989': '把本專案面對的問題講清楚：當結果變數是被選擇性觀察到的，抽樣過程本身就無法識別母體數量，再怎麼清理資料也改變不了這件事。',
    'horowitz1995': '第 6 節所用的精確界線（sharp bound）構造法：把沒觀察到的那團質量放到支撐集的兩端，參數就只能被設界，而不是被點識別。',
    'manski2003': '以整本書處理「在資料缺失下做預測」；也是「中位數的最壞情況區間，只有在觀察到超過一半母體之後才會變成有限區間」這個結果的來源。',
    'heckman1979': '本專案刻意不做的那個修正：它需要一個「租約為什麼會被申報」的模型，而第 5 節顯示申報規則是制度性的，不是建物的行為。',
    'gatzlaff1997': '同一個結構、退一步看：只用賣過兩次的房子所建立的指數是有偏的，因為「賣兩次」不是隨機發生的。在這裡是「同時出租又出售」，而存活下來的比例小得多。',
    'bracke2015': '方法上最接近的前例：取同時被出售與出租的物件計算租金／價格比，兩筆交易相距六個月以內，共 1,922 件。那是一家仲介自己的客戶名單、一座城市；本專案的對應物是公開的全國登錄資料，而且分母是可以被量出來的。',
    'himmelberg2005': '為什麼毛報酬率不是一個判決：依使用者成本（user cost）恆等式，偏低的租金／價格比可以是對低實質利率與預期增值的合理反應。第 14 節的淨報酬率是一個成本模型，不是使用者成本，也不能回答那個問題。',
    'chang2018': '承載了本文要對照的那個臺灣租金報酬率數字。其表 5 給出租金乘數 64、報酬率 1.57%，來源註明為 Global Property Guide（2018）——一個刊登網站的彙整，不是成交資料。那個來源本身，就是本專案要填的缺口。',
    'yang2018': '以 591 的刊登租金對上實價登錄的成交價，估出臺北市 2013–2016 年的租金乘數約為 50。這是建立在同一套登錄資料上、最接近的已發表臺北數字，而且它夾住了本文的臺北中位數。',
    'shorrocks2013': '第 7 節報告 Shapley 值而不是一條篩選順序的理由：Shapley 分解是與順序無關的那一種，而這道階梯的順序確實會影響結果。',
    'cameron2008': '同一棟樓內的配對不是獨立抽樣，而限制精確度的是棟數、不是配對數——這就是兩階段拔靴法先重抽建物的原因。這篇也是「群聚數太少會讓區間過度樂觀」的警告，因此各行政區在被報告之前要先過棟數下限。',
    'gpg2026': '一般流通、也是 Chang 與 Chen（2018）所引用的那個數字。第 4 節把它與登錄資料的量測逐一城市並列。'}


def why(key, lang="en"):
    """The annotation under an entry, in the edition's own language."""
    if lang == "zh":
        return WHY_ZH[key]
    return REFERENCES[key]["why"]
