# Housing pivot — handoff

Written 2026-08-30, last revised **2026-09-26** (payload v2.8, 919 tests).
Read this **before** touching anything under the housing surface. It exists so a
new session does not have to re-derive facts that cost days of spike work, and
does not reintroduce bugs that have already been found and fixed once.

Sections are appended over time, so **later sections supersede earlier ones**
where they disagree. §2 is always the current truth.

Companion documents:

| | |
|---|---|
| The plan + spike results + build log | `~/.claude/plans/the-pivot-quants-tw-stops-rippling-hummingbird.md` |
| Legal framing (投顧法 and 不動產估價師法) | `docs/LEGAL.md` |

---

## 0 · Start here

**If you read nothing else, read these five, in this order:**

1. **§2 Current state** — the numbers as of HEAD. Anything you find elsewhere in
   this file that contradicts §2 is stale; §2 wins.
2. **§11 House rules** — how to commit, what never to run, and the two rules that
   have cost real damage (`git add -A`, and dev servers through Bash).
3. **§8 Bugs already fixed** — every one of these shipped once. Reintroducing one
   is the most likely way to waste a session.
4. **§7 The map** — it is the hardest surface in the project and it has invariants
   that look like style choices and are not (the SVG user unit is a **metre**).
5. **§12 The ink restyle** — the design language everything is now drawn in.

**The one-line version of the project:** pair a real sale with a real lease *in
the same building*, publish the yield, and publish the denominator that shows how
little of the market that yield describes. The denominator is the point.

**The single most useful habit:** this page is built to refuse flattering
versions of itself. When a result looks clean, the next move is to try to break
it, not to publish it. Three of the findings in here were wrong the first time
and were caught that way — see §14 for the worst of them, where a comparison
group turned out to be 90% the thing it was supposed to be compared against.

**Sessions 2026-09-05 → 09-07 added:** the ink restyle (§12), 金拍 auctions
(§13), 預售屋 (§14), the MRT and floor findings, the related-party filter, and a
design/contrast audit. All pushed. Test count went 783 → 801.

---

## 1 · What this is

Quants.tw stopped being a stock analytics product and restarted as a **Taiwan
rental-yield analysis tool**. Same repo, same infrastructure, different subject.
Defensible because the stock version is frozen — no live users being destroyed.

The engine is **underwriting**: pull a real sale from 實價登錄, pair it with a
real lease *in the same building*, run the NOI math, output a yield. The word
"underwriting" never appears in the UI.

**Standing constraints from the user, still in force:**

1. This is the *second* start. **A third pivot becomes the signal itself.** Ship
   badly and iterate; do not redesign when the next good idea shows up.
2. **Stay strictly in the data-and-analysis lane.** Credibility is in analysing
   housing data, not in opining on housing policy.
3. ~~Scope: Taipei City + New Taipei only.~~ **LIFTED by Stanley 2026-08-31.**
   Scope is now **all 22 counties, national.** Yield still via **matched pairs**,
   never district averages — that part never changed and must not.

`不動產估價師法 §14` reserves 估價 for licensed appraisers (NT$30k–150k penalty).
The line the site walks:

- ✅ "Transactions in this building cleared at X% on these assumptions."
- ❌ "This property is worth NT$Y" / "this is a good buy."

The detail panel ends with an explicit line saying it is a registered
transaction price, not a valuation. **Do not remove it.**

---

## 2 · Current state

**Branch `feat/housing`, clean, everything pushed to the `quants` remote.**
HEAD is the **v2.8** build (§35). **919 tests pass**, zero failures, zero skips
that matter.

```
(v2.8)  fix(housing): v2.8 — the join key, and the bug it woke up
42c2dd7 fix(housing): v2.7 — the last two audit dimensions
58b083b fix(housing): v2.6 — the site audit, and a finding published at a third of its size
6ee0935 fix(housing): v2.5 — hygiene, and a reproducibility floor worth documenting
48faf8e feat(housing): v2.4 — the vacancy guess gets a measured shape
690cb3e feat(housing): v2.3 — the unseen 94% is bounded, not assumed away
7f6cfbb feat(housing): v2.2 — the founding hypothesis is closed as unanswerable, and its mechanism is falsified
86e4f7b fix(housing): four banded MOI series, and the total/mean columns that leaked in as bands
7e93649 feat(housing): v2.1 — the headline imputes the un-itemised space rent (2.68% -> 2.55%)
58601f5 feat(housing): v2.0 — parking spaces as an asset, and the parking assumption tested
3f4cf8d feat(housing): v1.9 — transaction volume, the management-fee gate, and reference rates
```

### The numbers as of HEAD

| | |
|---|---|
| Headline gross / net | **2.55% / 1.7344%** (v2.8 corrected the join key; §35) |
| Identified bound, all 157,594 | **[1.90%, 4.26%]** gross under stated assumptions; [0.30, 12.00] with none (§30) |
| Vacancy prior (matched vs stock) | **11.53% vs 9.52%**, +2.01pp — the visible slice is EMPTIER because it is new (§31) |
| Selection effect (matched vs unmatched) | **+8.5%** per 坪, on 147,789 unmatched — was published as 2.7% until v2.6 (§33) |
| Buildings / pairs | 9,843 / 143,297 |
| Universe (denominator) | 157,594 buildings with any residential sale |
| Coverage | **6.25%**, ceiling 24.0% with no quality filters |
| Window | 112S4–115S2, **11 seasons** |
| Clean sales / rents | 395,435 / 66,747 (raw 970,942 / 432,649) |
| Geocoded | 8,798 / 9,805 = 89.73%, district agreement 100% |
| Payload | 3,641 KB raw, 846 KB gzipped |

> ⚠️ **Never `git add -A` in this repo.** It has swept in another branch's work
> twice. Stage housing files **by name**.

### Deployment

`QUANTS_SUBJECT=housing` makes `/` the housing surface, with the stock SPA at
`/stocks-legacy`. Railway watches `quants main`.

> ⚠️ **quants.tw returns Railway `{"code":404,"message":"Application not found"}`
> on EVERY route.** The app is not bound to the domain. This long predates the
> housing work and cannot be fixed from here — it needs Stanley's Railway
> dashboard. **Nothing in this project is reachable by any reader until it is.**

## 3 · Running it

```bash
SECRET_KEY=devtestkey QUANTS_SUBJECT=housing venv/bin/python3 app.py
```

Or use the `.claude/launch.json` config named **`housing`** with the browser
preview tools. **Never run a dev server through Bash.**

Rebuild the data payload (only needed if the pipeline changes):

```bash
venv/bin/python3 underwrite.py
```

Run tests:

```bash
venv/bin/python3 -m pytest tests/ -q
```

`node` is **not installed** on this machine, so `tests/test_js_syntax.py` skips
and `node --check housing.js` is unavailable. Verify JS in the browser instead —
this repo has a documented history of 130 tests staying green while the inline JS
was completely broken.

---

## 4 · Files

### Pipeline (build-time only; none of it runs at request time)

| File | Lines | Job |
|---|---|---|
| `underwrite.py` | 1803 | The engine: matcher, cost model, ladder, coverage waterfall, bootstrap, every analysis block, and the JSON emit. |
| `fetch_lvr.py` | 585 | Download / extract / parse 實價登錄. **All cleaning filters live here**, each as a parameter so the ladder can walk the same code path. Pure library. |
| `boundaries.py` | 422 | Pure-Python `.shp`/`.dbf` reader + forward transverse Mercator + RDP simplification + county dissolve. |
| `fetch_fasc.py` | 294 | 金拍 auction results from 台灣金服. Cached to `data/fasc/` (gitignored). See §13. |
| `geocode.py` | 286 | Join 門牌 to the government address-point files. A join, not an estimate. |
| `basemap.py` | 208 | OSM roads / MRT / water / stations via Overpass, **cached to disk, queried once**. |
| `normalize_addr.py` | 114 | 門牌 → building key. 100% recall on 130 labelled pairs. |

### Surface

| File | Lines | Job |
|---|---|---|
| `housing.js` | 3543 | One IIFE. Bilingual `STR` table (295 keys), Simple/Advanced modes, ~20 sections, every chart hand-rolled SVG. |
| `housing.css` | 1015 | Self-contained ink tokens, light + dark under both `prefers-color-scheme` and `[data-theme]`. See §12. |
| `housing.html` | 49 | Thin shell. Theme-before-paint script + stock service-worker eviction. |
| `housing_data.json` | 3641 KB | Precomputed payload. `.gz` is 846 KB and is served when accepted. **Both are committed** — a stale `.gz` once nearly shipped 2,549 buildings to every browser, and there is a sync test. |

### Tests — 801 total

`tests/test_housing.py` (1921), `tests/test_underwrite.py` (328),
`tests/test_housing_map_layout.py` (250), `tests/test_addr.py` (124).
`tests/fixtures/addr_pairs.csv` holds 150 labelled address pairs.

`test_housing_map_layout.py` is a **browser-free port of the map layout maths**.
It exists because the browser pane's `requestAnimationFrame` is frozen while the
pane is hidden, so the map cannot be visually verified from a headless session.

`tests/conftest.py` has an **autouse fixture forcing `db._client = False`**.
Without it, pytest loads `.env` and any test touching Supabase writes to **prod**
from a laptop. Do not remove it.

### Routes in `app.py`

All are explicit — **there is no catch-all**, and a missing route is the failure
mode that ships green (commit `239e758` exists because of it).

| Route | Handler | Line |
|---|---|---|
| `/housing` | `housing_page()` | `app.py:4943` |
| `/housing.js` | `housing_js()` | `app.py:4972` |
| `/housing.css` | `housing_css()` | `app.py:4977` |
| `/housing_data.json` | `housing_data()` | `app.py:4991` |
| `_SUBJECT` flag + `/` gate + `/stocks-legacy` | `_housing_subject_gate()` | `app.py:4954` |

---

## 5 · Data facts that were expensive to establish

Everything here is **verified on real bytes**, not from documentation.

### Source

內政部 不動產成交案件實際資訊資料供應系統. Free, no key, no login, Government
Data Open License v1.

```
https://plvr.land.moi.gov.tw/DownloadSeason?season=115S2&type=zip&fileName=lvr_landcsv.zip
```

Use the **combined** `lvr_landcsv.zip` (sales + pre-sale + rentals).
`lvr_landAcsv.zip` is sales-only — wrong file.

| | |
|---|---|
| Filenames | **lowercase**: `a_lvr_land_a.csv` = Taipei sale, `a_lvr_land_c.csv` = Taipei rent, `f_…` = New Taipei |
| Encoding | **UTF-8 with BOM** → `utf-8-sig`. Not Big5 |
| Header | **Two rows** (Chinese, then English) → `skiprows=[1]` |
| Address column | `土地位置建物門牌` (not the 1.0-era `土地區段位置建物區段門牌`) |
| ROC seasons | 2026 = 民國115, so `115S2` = Apr–Jun 2026 |

### The 112S4 boundary — do not lower it

**Six rent columns were added at 112S4 (2023 Q4)**: `出租型態`, `有無管理員`,
`租賃期間`, `有無電梯`, `附屬設備`, `租賃住宅服務`. They do not exist in
110S3–112S3.

All three cleaning filters depend on columns that do not exist before 112S4.
Using older seasons would silently blend subsidised social housing and
room-shares into the early period and **manufacture a fake time trend**.

`FIRST_CLEAN_SEASON = "112S4"` in `fetch_lvr.py` is the guard. Usable window is
**11 quarters, 112S4 → 115S2**.

### The three filters (authoritative)

```python
RESIDENTIAL   = {'住宅大樓(11層含以上有電梯)', '華廈(10層含以下有電梯)', '公寓(5樓含以下無電梯)'}
SOCIAL_HOUSING = {'社會住宅包租轉租', '社會住宅代管'}
WHOLE_UNIT     = {'整棟(戶)出租', '獨立套房'}
```

- **Parking needs no assumption.** Filter `交易標的 == 房地(土地+建物)` on the sale
  side and `交易標的 == 租賃房屋` on the rent side. Both then exclude parking by
  construction, symmetrically, with zero modelling. (`車位總額元` exists but is
  itemised in only 54 of 5,744 rows — use the filter, not the field.)
- **Exclude 社會住宅.** It is subsidised and biases the raw sample *downward*.
  Anyone computing a yield off raw 實價登錄 rents is blending subsidised and
  market rents.
- **Exclude room-shares** (分租套房 / 分租雅房). Their area field is not comparable
  to a whole-unit sale. This filter is what makes the sale/rent area ratios come
  out at ~1.0, which is what killed the 公設 worry.

The `clean_sales()` / `clean_rents()` functions take **flags** for each filter so
the honesty ladder shares the same code path. An earlier version reimplemented
the filters in `build_ladder` and drifted from the headline by one building.

### Coordinates

TWD97 / TM2, EPSG:3826, in **metres**, used as-is. Never converted to lat/lon —
TM2 is already planar, the area is ~50 km across, and a conversion would only add
error to a picture drawn in screen pixels.

`boundaries.validate()` checks that buildings land inside the district their own
實價登錄 record names. **99.88%.** That is the projection's only real test: a
wrong central meridian, a swapped axis or a bad datum all place points somewhere
plausible-looking but in the wrong polygon, and nothing else would notice.

Hard-coded district code→name maps in `geocode.py` are validated the same way:
**100% district agreement.** Nationally the match is **8,798 of 9,805 (89.73%)** — the two-city era's 99.7% was against a much easier address set.

The 100–200 MB address CSVs live in `data/geo/` and are **not needed to serve the
site**. Only the ~2,500 matched coordinates ship.

---

## 6 · The numbers

> ⚠️ **The figures in this section are v2.0's and are kept as written.** The
> headline has moved twice since: v2.1 imputed the bundled space rent (§28) and
> v2.8 corrected the join key (§35). Current values are in §2 —
> **2.55% / 1.7344%** on **9,843** buildings, coverage **6.25%**. The lesson this
> section teaches (pair-level against building-level) is unchanged; only its
> worked numbers are old.

All figures are **building-level**, never pair-level.

> ⚠️ **Pairs are not a sample size.** Pairs concentrate hard in mega-towers, so
> `n_sale × n_rent` massively over-weights them. Building-level is the only
> honest unit, and the last ladder rung exists to show the difference:
> pair-level 2.89% against building-level **2.68%**.

| | |
|---|---|
| Headline gross yield | **2.6769%** (n = 9,805 buildings) |
| Net yield (current assumptions) | **1.8449%** |
| Coverage | **6.22%** of 157,594 buildings with a sale record |
| Structural ceiling (window only, no quality filters) | **24.0%** |
| Matched pairs | 142,518 |
| Quarters | 11 (112S4 → 115S2) |
| Raw → clean | 970,942 sales → 395,435; 432,649 rents → 66,747 |

> These superseded the two-city figures (2.43%, n=2,549, coverage 3.66%) when
> scope went national. If you find 2.43% or 2,549 anywhere, it is stale.

### The finding

**Same-building matching — the only way to compute a yield without imputing rent
— is possible for 14.09% of towers but 1.69% of walk-ups.**

| 建物型態 | share of stock | share of matched | match rate |
|---|---|---|---|
| 住宅大樓 (tower) | 21.8% | 59.9% | **14.09%** |
| 華廈 (mid-rise) | 18.2% | 20.3% | 5.71% |
| 公寓 (walk-up) | 60.0% | 19.8% | **1.69%** |

Matched buildings are **13 years newer** (built 民國85 vs 72) and **+30.5% per
坪**. So every transaction-based Taiwan rental yield is structurally computed on
a young, tower-heavy, investor-owned slice. **The published number is not the
market's yield; it is the yield of the rentable-and-tradeable subset.**

Coverage waterfall: the law costs **77.4pp** (no lease record at all), our own
filters cost **18.9pp** — so roughly **80% of the loss is structural, not ours.**
The page decomposes it rather than quoting one number.

> ⚠️ **Everything above this line in §6 was measured in the TWO-CITY era and
> parts of it are stale.** The rescope to 22 counties in 2026-08-31 changed the
> numbers and, in two places, the *direction* of a published conclusion. Nothing
> in the build catches that, because conclusions live in prose and prose is not
> asserted. Corrected 2026-09-08 — see §16. Current values:
>
> | claim in §6 | two-city | national (HEAD) |
> |---|---|---|
> | matched vs unmatched, price per 坪 | +30.5% | **+2.7%** |
> | matched vs unmatched, age | 民國 85 vs 72 | 民國 **96 vs 83** (still 13 yrs) |
> | law vs our filters | 77.4pp / 18.9pp | **72.2pp / 21.6pp** (law_share 77) |
> | 社會住宅 rent gap / share | −35.7% / 79% | **−28.0% / 82.1%** |
> | post-stratification shift | 2.43→2.59 (+0.157pp) | 2.6769→**2.9333** (+0.2564pp) |
> | price-index slopes | ±2 .034→.064, ±4 .056→.071 | ±2 **.006→.018**, ±4 **.036→.075** |
> | vacancy break-even | 淡水區 3.0%, 15.6% | **臺南市安平區 3.69%, 24.8%** |
> | within- vs between- dispersion | 0.605 vs 0.246 (**2.46×**) | **0.551 vs 0.932 (0.59× — REVERSED)** |
> | 公寓 vs 大樓 gross gap | 0.041pp ("dead") | **+0.374pp, CI [0.246, 0.494] ("alive")** |

### Three negative results — all published on the page, all must stay

1. **The price index failed.** It makes the yield-vs-gap slope *worse* at every
   window (±2: 0.034→0.064; ±4: 0.056→0.071). Drift would have flattened; it
   steepened, so the slope is composition, not drift. `USE_PRICE_INDEX = False`
   (env `LVR_PRICE_INDEX=1` to re-enable for testing).
2. **The 公寓-out-yields-大樓 hypothesis is dead.** 0.041pp at gross, 0.217pp
   after costs — **~81% of the gap was my own cost assumption.** The plan's kill
   criterion fired. Do not resurrect it.
3. **District 空屋率 is unavailable.** Village/district-level low-use-housing
   statistics stopped being produced in 民國109; only county-level PDFs remain.
   Replaced with a **break-even test**: 淡水區's 3.0% gross needs a 15.6% vacancy
   rate to fall to the district median, against a 5% default.

### Other published results

- **社會住宅 rents 35.7% below market**, and are **79%** of whole-unit registry
  leases. (An earlier 36% figure was one Taipei quarter *before* the room-share
  filter; room-shares are almost all private, so excluding them raises it.)
- **Post-stratification** on price decile × building type moves the yield
  2.43% → 2.59% (+0.157pp, two-city era). The bias is *measured and reported*, never silently
  corrected.
- **Within-building yield IQR is 2.46× the between-district IQR** (0.605 vs
  0.246, over 738 buildings with ≥4 pairs). Two units in one building differ more
  than two districts do — which is what makes a district average, the product
  every competitor sells, close to meaningless.
- **21 of 22 adjacent district CI pairs overlap** (two-stage bootstrap over
  buildings, then pairs within). Most of the ranking is not statistically
  distinguishable; the two extremes genuinely are.

### The cost model

Sourced, and all four are live sliders. `netYield()` in JS is a twin of
`net_yield()` in Python and agrees on every building (asserted in tests).

| Term | Default | Source |
|---|---|---|
| 房屋稅+地價稅 | 0.15%/yr of price | 彭建文等(2007) 0.089–0.130%; 王宏文・曾彥閔(2013) 0.066%; 李明軒 ~0.12% — all self-use, uplifted for 囤房稅2.0 |
| 管理費 | NT$140/坪/月 (北), 105 (新北) | published surveys; applied **only where 有無管理員 = 有** |
| Vacancy | 5% | no TW statistic exists — labelled an assumption |
| Repairs | 6% of rent × (1 + age/50) | no source; **age-scaled so it cannot bias 公寓-vs-大樓** |

Modelling tax as an effective rate on *market price* deliberately sidesteps
房屋課稅現值 — the one term a transaction record can never reveal.

---

## 7 · The map

The most intricate part of the surface, and where most of the bugs have been.
A real map drawn from government geometry with **no tile layer and no library**.

### Invariants

- **One network request.** The published page fetches its own payload and nothing
  else. There is a test that fails if an off-origin URL appears in `housing.js`.
  Tiles would have broken that; baked geometry does not. OSM is a **build-time**
  dependency, cached to `data/geo/`, and the page carries the ODbL attribution.
- Everything is drawn in **TWD97 metres inside a `scale(1,-1)` group**, so the
  coordinates *are* the projection and north is up. Consequences: anything sized
  in screen terms is multiplied by `mpp` (metres per pixel), and world **y grows
  north**, so "below on screen" is a *lower* y.
- Pan and zoom move the **viewBox**, never re-render.
- Colours are **CSS variables only** (`#fff` is the sole literal, in `.hs-clab`).
  That is what lets the theme toggle repaint the whole map with no re-render.
- Straight quotes only. A smart quote once killed a 6,000-line inline block.

### Structure (`housing.js`)

| Line | Function | Job |
|---|---|---|
| 637 | `mapAR()` | Target aspect ratio: 0.86 portrait ≤700px, else 880/640 |
| 641 | `fitBox()` | viewBox matching that aspect; handles the y flip |
| 653 | `mapHome()` | Full extent, 9% padding, cached with an AR guard |
| 682 | `yieldFill()` | Sequential ramp → `var(--y1..--y6)` |
| 699 | `districtGroups()` | Buildings → district groups (count, median, centroid, bbox) |
| 732 | `districtView()` | Zoom-to-fit box for one district |
| 740 | `secMap()` | Renders the whole section, including the choropleth and the boundary layer |
| 904 | `dotsHtml()` | One building = one symbol |
| 924 | `countSize()` / 929 `markScale()` | Mark geometry |
| 934 | `labelBox()` | Half-extent of the two-line block, in world metres |
| 955 | `layoutLabels()` | Rectangle collision displacement. **Never drops a name** |
| 995 | `labelHtml()` | The number, the name, and one transparent hit rect |
| 1018 | `marksHtml()` | Chooses label vs individual per district |
| 1048 | `openPanel()` | Building detail panel |
| 1087 | `wireMap()` | All interaction. `commit()` inside it is the render hot path |

### District grouping (current model)

Redesigned 2026-08-30. The disc is gone; the value moved to the polygon.

- **The polygon is a choropleth** of the district's **median yield**, on the same
  `--y1..--y6` ramp as the buildings inside it. Fill is a *presentation
  attribute* set per district, so **no CSS rule may declare `fill` on `.hs-land`
  unconditionally** — a CSS declaration would beat it and flatten the ramp.
  `fill-opacity` is the lever that is safe to pull.
- **The mark is the number**, with the district's name under it — no disc. Size
  carries the count (sqrt, as a font size), and the count is plain high-contrast
  type at every size because it no longer has to sit legibly on a coloured fill.
- **The name is part of the mark and is never dropped.** The badge layout dropped
  9 of 33 at full extent, always the dense ones in the core, which are the names
  a reader wants most. `layoutLabels()` separates blocks along whichever axis
  needs the least movement — for something wide and short, almost always the
  vertical one — over 160 iterations, on a leash of 2.2 block-radii (3.2 on a
  small canvas). Measured at full extent: **0 overlaps, 33 of 33 named**, desktop
  and 375 px alike.
- The 8 districts with no matched building are named by the standalone
  `.hs-dlabel` layer, so **all 41 are named**.
- **Boundaries are their own layer**, drawn above the roads and the density grid,
  as a wide casing in `var(--surface)` under a `var(--dline)` line. One line
  cannot contrast with both ends of the ramp; the casing is what lets it. All
  casings are emitted before any line, or a casing paints over its neighbour's
  boundary.
- **Clicking a mark — or anywhere in the district polygon — fits that district
  and shows only its buildings.** Every other district dims (`.hs-land.dim`),
  the focused one lightens so its dots read (`.hs-land.foc`), and a focus pill
  inside the map names where you are and returns home. The dimming is
  `classList.toggle` on 41 nodes, not a re-render.
- Because focus means *only* that district, `_focus` suppresses the viewport
  rule: without that, its neighbours opened too and buried what was clicked.
- Absent a focus, a district still opens automatically when `V.w < DETAIL_W`
  (12,000 m) **and** its bbox intersects the viewport + 25%. Expanding all 33
  would put 2,541 marks in the DOM to look at three.
- Focus is abandoned when zoomed back out past `home.w * 0.5`.
- Mark size **scales to the canvas** (`markScale`), because a fixed-px mark
  covers three times the share of a 341px phone map that it does of an 880px one.

`districtGroups()` is cached on `_fKey` — call `filtered()` **first**, then
compare, or the cache goes stale.

### Performance rules, each learned the hard way

- **`filtered()` is memoised.** The hover path was re-filtering every record on
  every `pointermove`.
- **All zoom work is coalesced into one `requestAnimationFrame`.**
- **Marks live in their own `<g id="hs-marks">`** so a zoom redraws only them.
  Re-clustering used to call `rerender()`, which rebuilt all 14 sections
  including a 600-row table and a 2,541-point scatter — 425 ms to move ~100
  circles.
- **The density grid is 5 banded `<path>`, not 2,000 `<rect>`.** SVG nodes
  2,585 → 582.
- **The density grid hides below 20,000 m of viewBox.** Its 400 m cells are the
  coverage argument at city scale and a grey checkerboard the size of city blocks
  at street scale.
### The basemap is staged by zoom

Added 2026-08-30, and it is most of what made the map legible.

At full extent the map answers *which district*, and every street, stream and
metro line drawn across it answers a question nobody has asked yet — 33 numbers
over a web of veins was the complaint. Context now fades in with the scale that
gives it meaning. The `STAGE` table in `commit()`:

| Layer | Appears below |
|---|---|
| water, rivers, major roads, MRT | 30,000 m |
| stations | 16,000 m |
| secondary roads | 13,000 m |
| station names | 7,000 m |

Home is ~65,000 m wide, so **nothing in that table is on at full extent**. The
layer menu carries a line saying so, because a toggle that visibly does nothing
reads as a broken toggle.

**The density grid defaults to OFF.** Two area fills compete for one channel, and
the 400 m grey checkerboard was winning against the value the map is for. It is
one click away, and the coverage argument it makes has its own section.

Districts with no matched building are `--surface3`, not `--surface2`: at
`--surface2` they sat within a shade of the map's own background, so the emptiest
third of New Taipei read as a hole punched through the picture. They are also
`pointer-events: none` — there is nothing to open.

Building dots are outlined in `color-mix(var(--text) 38%)`, not in `--surface`.
The ramp's dark end is `#3a4270` in dark mode and `#cdd3f5` in light, so at both
ends a building was a dot the same value as the ground under it.

---

## 8 · Bugs already fixed — do not reintroduce

Each of these has a test. If a test looks like it is asserting something odd,
read its docstring: several of them record a **reversed** decision.

| Bug | Why it happened |
|---|---|
| **A CSS declaration silently beat every presentation attribute** | Author CSS wins over a presentation attribute, and this map's user unit is a **metre** — so `.hs-rd1 path { stroke-width: 1.9 }`, written as a "placeholder" under a comment saying the real value is set in metres by `commit()`, was a **1.9-metre road: about 0.03 px** at city scale. Every stroke on the map had been rendering as a sub-pixel ghost, the district boundaries could not be seen at all, and `.hs-dlabel { font-size: 11px }` drew the only name 8 districts have at **a seventh of a pixel**. The halo on `.hs-dgname` was the one stroke that ever worked, because it was the one rule that omitted the property. All such declarations are removed; a test now forbids restating in CSS anything `commit()` sets as an attribute. The widths were then retuned, because nobody had ever seen them. |
| **`vector-effect: non-scaling-stroke`** | The textbook answer for geometry in world units, and pathological here: the browser recomputes stroke geometry per segment in device space, and on an 11,000-point road path it hung the renderer for seconds. Widths are set in **metres** via the `STROKES` array in `commit()`. A test now *forbids* it. |
| **Duplicate `wireMap`** | A rewrite **inserted instead of replaced**. JS hoists both and the *last* wins, so a stale implementation with `setTimeout(rerender)` ran — 8,570 ms per zoom, while the correct new code sat directly above it doing nothing. Now 21–43 ms. |
| **`setPointerCapture` on pointerdown** | Retargets `pointerup` *and* `click` to the `<svg>`, so `e.target.closest('.hs-dg'/'.hs-mdot'/'.hs-land')` matched nothing and **every click on the map was silently dead**. Capture is now taken **lazily**, on the first move past a 4 px threshold. Pinch still captures both pointers immediately. |
| **Any pointermove counted as a drag** | The tiniest tremor between down and up set `moved = true` and the click handler bailed. Now a 4 px slack radius. |
| **`.hs-land` carried `data-d`** | The root-level delegated `[data-d]` handler matched it too: the svg handler set `state.district` and rerendered, the event bubbled to `#hs-root` (which survives a rerender) and toggled it straight back. Clicking a district did nothing. Renamed to `data-dkey`. |
| **viewBox aspect ≠ surface aspect** | Data bounds are 1.10 against a 1.375 surface; `preserveAspectRatio="meet"` letterboxed it while `toWorld()` mapped clientX linearly across the whole element — displacing every zoom anchor and click horizontally. `fitBox()` now matches the surface. |
| **Hard-coded `height="640"`** | With `height: auto` an SVG takes its intrinsic ratio from the width/height **attributes**, not the viewBox — so the portrait phone box was computed and then ignored, leaving the map 341×248 on a 375 px screen. `H = Math.round(MAP_W / mapAR())`. |
| **Listener stacking** | `wire()` re-bound the delegated handler to `#hs-root` (which survives re-render) on *every* render, so a click ran the handler N times and any flip-state handler landed back where it started on an even count. `_bound` guard + `wirePerRender()`. |
| **`"y"` key collision** | The map Y coordinate silently overwrote the gross yield on every building. Renamed to `mx` / `my`. |
| **`NaN` in JSON** | Assigning a list containing `None` to a pandas column coerces to float64; `json.dump` writes a bare `NaN`, which fails silently in `fetch().json()` — a blank page with a clean console. Fixed at source **and** `allow_nan=False`. |
| **`to_buildings` grouped on 建物型態** | 8 buildings the registry types inconsistently split into two rows and were double-counted. Now grouped on `(county, addr_key)` with a modal type. |
| **Scatter clamped out-of-range points** | Stacked 13 outliers into a false cluster on the axis. Now dropped and disclosed. |
| **Stale service worker** | `quants-v13` served a 52 KB `housing.js` against a 64 KB file. `housing.html` now unregisters it. |
| **`%%` in 8 STR strings** | `Sf()` collapses `%%` → `%`. |
| **`&middot;` rendered literally** | `row()` escapes its value; use the real character. |
| **Over-broad substring tests (twice)** | `"leaflet"` matched my own comment saying we *don't* use Leaflet; `#[0-9a-fA-F]{3,6}` matched `&#9662;`. Test behaviour, not substrings. |

### The map's aspect ratio is measured, not chosen

ONE canvas serves all three levels, and they want different shapes: Taiwan is a
portrait country (the buildings span 169 × 305 km, aspect **0.55**) while a
single county is not. `mapAR()` derives the aspect from `map.bounds` and clamps
it at **1.15**, and that floor came out of a sweep, not taste:

| AR | canvas | country fills | county overlaps |
|---|---|---|---|
| 1.375 (the old fixed box) | 1070×778 | 37% | 4 |
| **1.15** | **900×783** | **44%** | **3** |
| 1.0 | 860×860 | 51% | 6 |
| 0.78 | 780×1000 | 65% | 10 |

1.15 wins on **both** counts against the old 1.375 — more of the canvas is data
*and* fewer labels collide — so it is not a trade-off. Pushing further towards
the data's true 0.55 fixes the national view and wrecks the county ones: 高雄
goes from 0 overlapping labels to 6. `.hs-mapwrap` caps the width at 900 px on
desktop to match. `tests/test_housing_map_layout.py` holds the line; re-run that
sweep before changing either number.

### Bugs from the national map, 2026-08-31

| Bug | Why it happened |
|---|---|
| **A city showed less than half of itself** | `districtGroups()` is built from BUILDINGS, so a district with no matched pair had no mark: 臺南市 showed 20 of its 37, 高雄市 24 of 38, 屏東縣 6 of 33 — 166 of 365 nationally. `allDistricts()` now takes the POLYGON set as the authority for which districts exist. |
| **…and opening one threw** | An empty district has no median, and `g.med.toFixed(2)` raised `TypeError: Cannot read properties of null` **inside `marksHtml`**, aborting the rebuild. The map kept the previous level's marks, so the click looked dead — while `_focus` and `_level` had both moved. 臺北市 was the only city that opened, because all 12 of its districts have data. **Read the console first.** |
| **Marks piled up when zoomed in** | The canvas clamp dragged every off-screen county and district INTO the viewport and stacked them: 高雄市 open was 57 marks / 85 overlapping pairs, 三民區 open 417 / 56. Off-screen marks are dropped before layout now. |
| **臺 vs 台** | The registry writes 台東市; the boundary shapefile writes 臺東市. One character, 9 orphaned buildings — no polygon, so undrawable, unopenable, and 臺東市 never appeared. **`geocode`'s "district agreement 100%" cannot catch this**: both sides of that comparison come from the registry. `underwrite._tw` normalises at every entry point. |

### Two things about verifying this map

- ⚠️ **`requestAnimationFrame` is frozen while the browser pane is hidden.** Every
  zoom, fly and mark rebuild goes through one rAF, so with the pane hidden
  `_focus` updates and *nothing renders* — and every measurement taken through
  the DOM is stale. It reads exactly like a broken map. `document.hidden` tells
  you. `resize_window` gives an emulated viewport that fixes layout measurement
  but not rAF.
- Because of that, `tests/test_housing_map_layout.py` is a **browser-free port of
  the layout maths** — `countSize`/`markScale`/`labelBox`/`layoutLabels` plus
  `marksHtml`'s viewport filter. It asserts the district-integrity join, that
  every district of every county is placeable, and the overlap count at each
  level. If you change the layout in `housing.js`, change it there too and let
  the numbers say whether it improved. Current: national 0 overlaps, 高雄 0,
  臺南 1, 臺中 1, 三民區 1 (新北's 29 basin districts are the stubborn ones).

### Palette

Resolved. The skill gates CVD on **min(protan, deutan)** with tritan only
*reported* — an earlier port also gated on tritan and disagreed with the skill's
documented numbers. The corrected port reproduces 9.2 / 9.4 exactly, and then
caught a real failure: dark `--s1` `#8d99ff` has L = 0.717, outside the dark band
[0.48, 0.67]. Replaced with **`#6b79f5`** (L = 0.628, 6° off brand hue), which
passes every check in both modes.

Series slots: `--s1 #2b3ec9` / `--s2 #eb6834` / `--s3 #1baf7a` (light).
Slots 2 and 3 measure 3.04 and 2.67 contrast against the light surface — under
3:1 — so **direct labels are mandatory** on every chart using them, and the table
view is not optional.

---

## 9 · Page structure

`housing.js` renders 5 sections in **Simple** (default) and 14 in **Advanced**.
Advanced sections are *built* only in the advanced branch, not CSS-hidden.

```js
var parts = [secHero(), secCoverage(), secMap(), secDistrict()];
if (adv) parts.push(secPostStrat(), secDispersion(), secLadder(), secBias(),
                    secNet(), secDead(), secScatter(), secMethodChecks());
parts.push(secTable(), secLimits());
if (adv) parts.push(secMethod());
```

The hero leads with **coverage (6.22%)**, not the yield. Leading with a number
that describes a 6.22% slice undercut the page's own argument.

Toggle lives top-right. Simple is the default because "regular people opening
won't understand a lot of the more advanced stuff."

---

## 9b · Going national — what was measured, 2026-08-31

The user lifted standing constraint #3 ("Taipei City + New Taipei only"). This
section records what a national expansion actually costs, so nobody re-derives it.
**Everything here is measured, not estimated**, unless it says otherwise.

### The registry is not the constraint

A run of the real pipeline across all 22 county files in the season zips already
on disk. The a+f slice of that run reproduces every published figure exactly
(2,549 buildings, 69,732 universe, 2.43% median gross, 14.09/5.71/1.69% match
rates), which is what makes the national figure a measurement rather than a prior.

| | today (a+f) | national |
|---|---|---|
| Matched buildings | 2,549 | **6,043** (2.37x) |
| Tier-1 pairs | 31,685 | 91,343 |
| Districts with >= 1 building | 33 | **166** of 368 |
| Districts clearing `MIN_DISTRICT_N` = 25 | 23 | **59** |
| Sale universe | 49,705 | 98,631 |
| Raw sales / rents | 219,198 / 140,344 | 970,942 / 432,649 |
| Clean sales / rents | 75,868 / 19,710 | 175,799 / 44,708 |

**The headline finding strengthens.** Tower match rate 14.09% -> **14.98%**,
mid-rise 5.71% -> 6.02%, walk-up 1.69% -> **1.71%**, on twice the buildings. A
Taipei-basin observation becomes a statement about Taiwan.

**The 112S4 schema floor holds nationally.** All six post-112S4 rent columns are
present in every rent CSV of all 21 rent-publishing counties, in all 11 seasons.
連江縣 (z) publishes no rent file at all; 金門縣 is missing 113S1 and 113S2.

**社會住宅 is a national pattern, not a rural-New-Taipei quirk.** 82.1% of
clean-eligible leases nationally, worse in 桃園 93.8%, 苗栗 93.7%, 基隆 92.5%.
Excluding it costs 13,762 buildings (19,805 -> 6,043) and 31 districts.

Matched buildings by county: 新北 1,392 · 高雄 1,305 · 臺北 1,157 · 桃園 520 ·
臺南 516 · 臺中 475 · 花蓮 155 · 基隆 118 · 宜蘭 114 · 嘉義市 99 · 新竹市 65 ·
雲林 27 · 新竹縣 25 · 彰化 20 · 嘉義縣 15 · 屏東 12 · 臺東 9 · 南投 9 · 苗栗 8 ·
澎湖 2 · **金門 0 · 連江 0**.

### Geocoding — the answer, and it took real work to get

**There is NO national open 門牌 coordinate file.** Multiple standing citizen
requests on data.gov.tw ask for exactly that and it has not been released.

**TGOS 全國門牌地址定位服務 is the national geocoder and we cannot use it.**
批次門牌地址比對服務 requires membership plus an approval review, and eligibility
is 限定政府機關、法人機構、學術單位、業界. 10,000 lookups/day once approved would
be ample for 6,043 buildings — the blocker is eligibility, not throughput.

So it is per-county open data. **The files share one common MOI schema**, verified
byte-for-byte across four counties:

```
省市縣市代碼, 鄉鎮市區代碼, 村里, 鄰, 街路段, 地區, 巷, 弄, 號, 橫座標, 縱座標
```

TWD97 / TM2 metres, UTF-8, 政府資料開放授權條款第一版, free, no key. That means
`geocode._SPECS` extends with **one reader and N URLs**, not N readers.

| County | Dataset | State |
|---|---|---|
| 臺北市 | data.gov.tw 155472 | wired. **現場調查** — surveyed |
| 新北市 | data.gov.tw 168887 | wired |
| 高雄市 | data.kcg.gov.tw `/DataSet/Detail/1e015103-320c-45e7-927b-70a3c0be87c3` | verified, monthly to 114年12月. Also publishes its own 鄉鎮市區代碼 lookup at `7d92ad41-81a0-495e-aa45-3180f2ee72ab` |
| 桃園市 | data.gov.tw 157689 | **download verified** (84 MB, HTTP 200, identical header), 55 monthly resources to 115年7月 |
| 臺南市 | data.gov.tw 120044 | **download verified** (36 MB, HTTP 200, identical header) |
| 臺中市 | data.gov.tw 169806 → Google Drive | **wired 2026-08-31.** Its data.gov.tw "CSV" is a MANIFEST whose rows are Drive links, one 門牌點位 file per month; the URL in `geocode.TCH_CSV` is a specific month (115年1月), so refreshing 臺中 means re-reading the manifest. `uc?export=download` returns Drive's virus-scan page for a file this size; `drive.usercontent.google.com/download?…&confirm=t` returns the bytes with no uuid, cookie or user agent. 157 MB, 750,882 points, **98.7% placed** |

Top six counties = **5,365 of 6,043 buildings (88.8%)**, and all six are now
wired: national placement is **87.24%** (5,272 of 6,043), 98.3% within the
counties that have a file.

> ⚠️ **Coordinate provenance is NOT uniform, and it matters less than it looks.**
> Taipei's file is 現場調查 (surveyed). 臺南's is titled 「僅供參考」 and its own
> description says 各戶政事務所於電腦上系統內參照各相對門牌位置**人工點位，非準確
> 坐標位置**. 桃園's carries the same caveat.
>
> This does **not** touch any published number. `G.attach` runs at
> `underwrite.py:843`, **after** matching and the yield maths; coordinates feed
> only `mx`/`my` (the map dot) and `attach_mrt`. Yields, coverage, the honesty
> ladder and the tower-vs-walk-up finding are all coordinate-free. What degrades
> is dot placement, `boundaries.validate()` containment, and distance-to-MRT.
> **Disclose provenance per county on the page; do not drop the counties.**

### Everything else that was measured

- **離島 are unreachable, and it is a registry fact.** 金門 has 949 clean sales
  but 24 raw rent rows in 11 seasons and **zero** clean leases. 連江 publishes no
  rent file. Publish as a stated limit.
- **嘉義市 and 新竹市 have no district granularity in the registry** — 鄉鎮市區 is
  literally 「嘉義市」/「新竹市」 while the shapefile splits them into 2 and 3
  polygons. 164 buildings affected. Dissolve those polygons to city level.
- **368 labels cannot share one canvas.** Measured label ink at the current mark
  geometry is **67.1% of the canvas** while the country covers 14.2% of a national
  viewport — 4.7x the land area. Needs the COUNTY / DISTRICT / BUILDING hierarchy.
  Worst-case districts inside one county is **38** (高雄), *below* today's 41 — so
  the proven layout survives, re-scoped per level, and the never-drop rule can stay.
- `layoutLabels()` is O(n² × 160): 84,480 pair-iterations at n=33, **10,804,480**
  at n=368. It is on the render hot path.
- **Taiwan is a portrait country in a landscape box.** Main island AR 0.520 against
  a 1.375 surface: `fitBox()` gives a 588 km viewport for a 204 km country and 62%
  of the desktop canvas is ocean. Proposed answer is a portrait map column (AR
  ~0.70) beside a rank list.
- **Three shapefile records blow up the extent**: 高雄市旗津區 carries 東沙 and
  南沙太平島 (down to lat 10.37), 宜蘭縣頭城鎮 carries 釣魚臺, 基隆市中正區 carries
  彭佳嶼. Fitting all 368 gives a 768,833 m home viewBox in which Taiwan is a
  smudge. Clip to the populated extent — and say so, rather than deciding silently.
- **Payload.** National district geometry at the current tol=45 m is **1.02 MB raw
  / 307 KB gz**, larger than today's entire payload, against 94 KB now. Tolerance
  is a clean LOD lever (300 m -> 11,667 pts / 76 KB gz, all 368 kept);
  `min_ring_area` is not — it drops districts.
- ⚠️ **`boundaries.validate()` must always run on the FINE geometry.** Containment
  falls 99.88% (45 m) -> 99.02% (150) -> 98.27% (300) -> 97.05% (400), so shipping
  a coarse LOD and validating against it would break the projection test for a
  reason that has nothing to do with the projection.
- **The basemap is 25% of the payload and 100% dead weight at national zoom.**
  248 KB of 993 KB raw, 101 KB of 260 KB gz, and nothing in the `STAGE` table
  renders above 30,000 m against a national home of ~644,000 m. Stitching OSM ways
  that share an endpoint is a **free 47% cut** (major roads 4,685 ways -> 182
  chains) and is worth doing today, nationally or not. A nationwide Overpass query
  is not runnable (2 slots, ~135-165 MB response) — switch the build source to the
  Geofabrik Taiwan extract.
- `railway=subway` is the wrong national tag: it misses 高雄輕軌, 淡海輕軌, 安坑輕軌,
  TRA and THSR, and 15 of 22 counties have no metro at all. The layer becomes rail.

### Two bugs this surfaced that bite TODAY

1. **`state.district` is a bare district name**, and 8 names are shared across
   counties (19 of 368 records): 東區 ×4, 北區 ×3, and 大安區 in **both 臺北市 and
   臺中市**, plus 中正區/中山區/信義區 in both 基隆市 and 臺北市. Nationally,
   filtering silently merges two cities. Promote it to the `county|district`
   composite key that `_focus`, `districtGroups()` and `map.labels` already use.
2. **The yield ramp is pinned to the Taipei spread.** `yieldFill()` computes
   `(v - 1.6) / 2.0` and the legend axis is the literal strings `1.6%`/`3.6%`.
   Central and southern yields run higher and would clamp to the top of the ramp.
   Move the domain into the payload.

### Verdict

**GO_PARTIAL.** The registry is free, the boundaries are on disk, the finding gets
stronger, and 88.8% of national buildings sit in six counties whose address files
share one schema. Phase it on the geocoder, one county at a time, cheapest first.

## 10 · Open items

**Done since this list was written (2026-09-05/06):**

- **Address search on the map** — shipped (`.hs-msearch`, `mapSearch()`), and on
  a phone it sits *below* the map rather than on top of 高雄.
- **The city selector** — superseded. Drill-down county → district → building
  does the job, so the dropdown was never needed.
- **Yield vs distance-to-MRT** — shipped as `secMRT()`, and it was the second
  finding the list predicted. 2.10% within 250 m of a station, 2.91% beyond
  2.5 km, monotonic across seven bins. The mechanism is in the components: price
  falls 63% across the range while rent falls 51%. Ships with a within-臺北市
  panel because most of the national spread is *which city*, and a guard test
  keeps both panels.
- **Floor premium** — now measured on BOTH sides within a building: rent
  +0.12%/floor, price ~+0.5%/floor. The gap is the finding, and it is the same
  capitalisation the MRT section measures in a different dimension.
- **The whole page redrawn in one ink** — see §12.
- **金拍 auction results** — new `fetch_fasc.py`, see §13.
- **預售屋** — shipped, see §14. It was the top open item and it produced a
  negative result, which is the best kind this page publishes.

**Not done, roughly in value order:**

1. **Per-building URLs** (`/housing/b/<key>`) — routing plus SEO, no analysis.
   Deliberately still not built: the page carries `noindex,nofollow` and the
   site is not bound on Railway, so a shareable building link currently has no
   consumer. The detail panel it would deep-link to is now keyboard-complete
   (§15), which is the half that was actually costing anyone anything.
3. **法拍 proper.** `fetch_fasc.py` covers 金拍 only. 司法院's own system
   (aae.court.gov.tw) refuses connections outright, and the registry does not
   flag auction sales at all (zero 法拍/金拍/拍賣 in 備註 across a full season of
   臺北市), so court auctions remain unreachable from here. Do not conflate the
   two channels; there is a test.
4. `housing.html` still carries `noindex,nofollow`. Now that `/` *is* the housing
   site, this deindexes quants.tw. Flagged to the user; they said ship as is. It
   is a one-line change.
5. **No users.** Of the three things that matter — verifiable, produced a
   finding, anyone used it — there are now two findings, the live URL is still
   blocked on Railway, and usage has not started.

**Known limits that are stated on the page and should stay stated:**

- 11 quarters only. No cycle, no time-series claims.
- The address-recall fixture is machine-mined; hand-labelling would be stronger,
  though the 0.01% no-門牌 rate keeps the caveat small.
- Net yield rests on four assumptions, two of which (vacancy, repairs) have no
  Taiwanese source at all and are labelled as such.

---

## 11 · House rules

- **Commit and push to the `quants` remote after every code change.** Stage
  housing files **by name** — never `git add -A`.
- Git credentials live in the macOS keychain; both remote URLs are clean
  https (verified 2026-08-30). An older note in this repo's history said the
  `quants` URL embedded a plaintext PAT — that is no longer true.
- Verify front-end JS **in a browser**, not only with pytest.
- Do not use `save_cache` / `save_analysis_cache` for housing data — those are
  JSON blobs and the repo already hit that ceiling (a 28 MB blob sharded 10 ways
  to fit one JSONB row).
- Never run a full `chip_archive` scan online (hundreds of MB per run; the
  Supabase free-plan egress has been over budget before).
- End every reply to this user with a **"What's next"** section and then a
  **plain-English summary** of the whole response.

### Added 2026-09-07, both paid for in this session

- **Verify in a browser by LOADING FRESH, not by flipping `data-theme` from the
  console.** Setting the attribute leaves `var()`-dependent properties stale, and
  it produced ten convincing phantom contrast failures — invisible buttons that
  did not exist. A real user flips theme with the button, which calls
  `rerender()`. Set `localStorage.hs-theme` and reload instead.
- **Run the reviewer's fix before believing it.** In §14 two of three independent
  reviewers prescribed the same age fix; it does nothing, because it leaves every
  negative-age row in place. The third reviewer found the load-bearing half. A
  prescription that sounds right and moves the number by a rounding error is a
  signal, not a success.
- **The Workflow tool failed 5 of 6 times this session** (session limits ×4, DNS
  ×1), burning ~2.3M subagent tokens for two usable results. It is worth using
  for genuine fan-out — the one run that completed found the §14 contamination
  nobody else had — but budget for it dying, do the cheap checks yourself first,
  and never block on it.

---

## 12 · The ink restyle (2026-09-06)

The page is drawn in one ink on one paper. Every grey that encodes a VALUE is
countable lines — hatch **pitch**, never opacity and never a flat fill. Token
NAMES in `housing.css` are unchanged throughout, so ~3,000 call sites kept
working; only the values moved. `--accent` no longer means blue, it means "the
interactive role", which one ink carries with an underline and with weight.

**The map is the part that breaks if you touch it carelessly.** Its user unit is
a METRE inside `scale(1,-1)`, so:

- The choropleth fill is `url(#hx1..6)`, six SVG patterns, coverage 10% → 64%
  monotonic. `HATCH[]` in `housing.js` must stay numerically identical to
  `.hs-y1..6` in `housing.css` or the legend is lying about the map. **Test.**
- `sizeHatch(mpp)` re-cuts every tile in metres on each zoom, exactly as
  `commit()` already did for stroke widths. A 9-unit tile is a NINE-METRE tile:
  0.02 px at national zoom, 18 px on one building. **Test.**
- The pattern angle is written `rotate(-28)`, not `+28`. The y-flip mirrors it,
  and `+28` would hatch the map against the legend and the rest of the page.
- Below the sample floor a district is **bare paper** — no tone at all, not the
  palest step. This is the rule the map was rebuilt for after 嘉義縣 was painted
  the darkest county in Taiwan off 18 buildings. **Test.**

**Two things deliberately lost information and it is worth knowing which.** A
luminance ramp is faster to rank than hatch and supports more steps; the number
printed on every mark is what keeps that honest. And individual building marks
are uniform ink — one sale matched to one lease is the noisiest figure in the
payload, and a six-step ramp over 2,000 of them invited exactly the over-reading
the page argues against.

**建物型態 cost nothing.** `symbolPath()` already drew 公寓 / 華廈 / 住宅大樓 as
circle / diamond / square, so the three series colours were redundant with shape
before any of this. Charts now use three categorical TEXTURES (hatch, cross,
stipple) — never three densities, because density is the ordinal channel and
yield is spending it. **Test.**

**No handwriting anywhere**, and that is a limit rather than an omission: Google
Fonts has no usable Traditional Chinese hand and this brand is Chinese. Caveat
was tried and removed after it did nothing but drop the glyphs into whatever
cursive fallback the OS owned.

## 13 · 金拍 auctions — `fetch_fasc.py`

**This is 金拍, NOT 法拍.** A bank disposing of collateral through 台灣金服, not
a court auction under compulsory execution. Smaller channel, different
population. There is a test asserting the distinction is stated, because
conflating them misleads about both the size and the nature of the data.

Two Kendo endpoints, no form, no API key, no robots.txt:

    POST /Product/Bidded/ReadData        -> auction sessions
    POST /Product/Bidded/ReadDataDetil   -> items in one session   (their spelling)

Keyed on `id` (the session Id). 2015-01-01..2026-12-31 returns 1,549 sessions;
the default window starts 2023-10-01 to match the 112S4 schema floor. Every
response is cached to `data/fasc/`, one file per session, and `fasc_block()`
reads **only** that cache — a build must never depend on a third-party site
being up, and there is a test that it does not.

Field traps, verified against real bytes:

- `Saleamt` is the sold price and `MinPrice` the reserve. `SalePrice` and
  `EvaluatePrice` are in the schema and null/0 in practice.
- `Saleamt == MinPrice` on most rows is **not** a default. One qualifying bid
  clears AT the reserve, so the share above it is a competition signal.
- `PropType` is `BuzLand` or `BuzBuild`; only `BuzBuild` has a 門牌.
- `SaleDate` is `/Date(ms)/`, and `str.extract` yields STRINGS —
  `to_datetime(unit='ms')` silently coerces every one to NaT without a
  `to_numeric` first.
- **高雄巿** (U+5DFF) appears for 高雄市 (U+5E02). Different character, survives
  every normaliser that only knows 台→臺, and it silently costs the address match.
- **There is no area field anywhere**, and `Lat`/`Lng` are null in every row
  observed. So no price-per-ping and no comparison against market prices — a
  total auction price against a market median compares a studio to a townhouse,
  and reserves fall by round anyway. There is a test that no such comparison is
  computed.

## 14 · 預售屋 — and why the 30% premium is not one

`*_b.csv` in the same season zips. 306,290 rows over 14 seasons; 231,173 in the
112S4–115S2 window this project is pinned to, cleaning to **180,835 dwellings
across 4,587 建案 in 226 districts**.

**Loading it needs its own path, and here is why.** 12 of the 289 pre-sale files
carry rows with an extra unquoted field and fail a strict `read_csv` outright —
including 115S1 臺北市 with 1,184 rows, so dropping the file whole is not an
option. `read_csv_from_zip(..., tolerant=True)` skips the bad rows, recovers
15,741 of ~15,759, and **prints what it skipped**. It is opt-in and enabled only
by `load_presale_season`; the sale and rent files parse cleanly (308 and 289
files, zero failures) and a tolerant read there would turn a future export bug
into silent data loss. There is a test.

Three things differ from the completed side and each is forced by the data:

- **The address is not a 門牌.** `土地位置建物門牌` holds a project-unit reference
  (`…三重路200巷A-3F`) with no 號. `addr_key` cannot key it, so the same-building
  matching that produces the site's main finding is impossible here. `建案名稱`
  is 100% populated and is the only stable grouping key.
- **`建築完成年月` is 0% populated.** The building does not exist. Age cannot be
  computed on this side, so any comparison has to control for it on the other.
- **82.3% carry parking**, far above the completed market, so dropping bundled
  transactions would throw away five sixths of the market. Parking is subtracted.

### The finding, on the third attempt

A pre-sale flat has no lease, so **no yield can ever be computed for one** — not
a data gap, the nature of the thing. 179,252 dwellings the headline is blind to
in principle. That half was right from the start and never moved.

The price comparison was published **wrong twice**, and both versions are kept
here because the second mistake is the interesting one.

**Attempt 1** measured +30.2% against "completed buildings under two years old"
and concluded the gap was the three-year delivery wait being priced in, because
pushing the comparison forward collapsed it to +4.3%.

**Attempt 2** retracted the mechanism: running the same shift between two
completed groups (no delivery wait) falls almost as fast, so the curve could not
distinguish the two stories. It kept the +30.2% and published `separable: false`.

**Attempt 3 — the group itself was wrong**, and this is the one that mattered:

> `交易年月日` in the 買賣 file is the **CONTRACT date**, not the handover date.

Filtering `age <= 2` on the completion year alone selected 186,550 rows of which
**168,426 — 90.3% — were contracts signed before the building existed**, median
age at contract **−2.17 years**; the largest single cell was 110 contracts on 113
completions (25,571 rows). The "completed" comparison group was overwhelmingly
the previous pre-sale cohort. **The published number was pre-sale against
pre-sale**, and the attempt-2 placebo structurally could not catch it, because
both placebo arms were drawn from that same contaminated group.

The fix is `age = contract_date − completion_date`, kept `between(0, 2)`. The
`>= 0` floor is the load-bearing half: merely re-anchoring the year (the fix two
independent reviewers prescribed) keeps every negative-age row and moves the
headline about a point. Both sides are also now indexed on the **contract
quarter**, not the zip's publication season — median publication-minus-contract
is 1 quarter on the pre-sale side and 10 on the old group, so "same season" was a
median 2.25-year gap in the thing that moves prices.

**Corrected:**

| completed comparison | pre-sale gap | cells | placebo | cells |
|---|---|---|---|---|
| same contract quarter | **+5.4%** | 261 | 0.0% | 337 |
| +0.5 yr | +3.0% | 198 | −4.5% | 144 |
| +1.0 yr | +0.9% | 132 | −5.7% | 100 |
| +1.5 yr | −3.0% | 87 | −5.9% | 76 |
| +2.0 yr | −7.5% | 55 | −8.3% | 48 |

Residual net of the placebo: **0.9%**. Measured against homes that actually
exist, pre-sale is barely dearer at all, and the little that remains is time.

The floor is stable now, which the contaminated version was not: **+5.4% at
n≥5, n≥25 and n≥100** alike, where the old one ran 23.9% → 33.9%.

**Reach is published on the page**: 63,361 dwellings (35.3%), 63 of 226
districts, 261 cells. Many districts have too few genuinely-completed new builds
to compare against.

`newbuild_cagr_pct` was **deleted, not corrected** — its base quarter had n=467
and it was measured on the contaminated group; the ~10%/yr replacement two
reviewers proposed was measured on the same group and would have swapped one
wrong number for another.

`clean_presale` also drops **解約情形** rows (rescinded contracts, 1,583 of them),
as a parameter with the others.

**Uncontrolled:** which projects sell off-plan, specification and finish,
developer pricing strategy. 11 quarters means two years is the reach.

The guard test used to assert the literal string `"C.age <= 2"`, which was true
of the defective filter and false of the correct one — it defended the bug. It is
now a property test over a synthetic frame.


## 15 · Two follow-ups from the pre-sale review

**Per-rung cluster CIs.** The curve reported cell counts, and 261 cells at the
first rung are only **71 district × 建物型態 clusters** (55 cells at the last are
30). Cells inside one district and type are not independent draws — the same
streets and often the same 建案 supply several quarters of them — so the cell
count flattered the evidence. `_cluster_ci` bootstraps over clusters at the same
seed/percentile convention `bootstrap_cis` already uses:

| lag | gap | 95% CI |
|---|---|---|
| same contract quarter | +5.4% | [4.2, 7.0] |
| +0.5 yr | +3.0% | [−0.1, 5.5] |
| +1.0 yr | +0.9% | [−3.5, 3.1] |
| +1.5 yr | −3.0% | [−5.6, −1.1] |
| +2.0 yr | −7.5% | [−9.4, −5.0] |

So the +5.4% at contract excludes zero and everything past a year does not.

**The building panel was a dialog pretending to be a div.** Three defects, all
of which a keyboard user hits on the first try:

- opening it left focus on the map, so a screen reader had nothing to read;
- **Escape reached the map's handler and zoomed the country out** instead of
  closing the thing the reader had just opened. `closePanel()` now returns a
  boolean so one key does both jobs in the right order;
- the map's listener is on the `<svg>` and the panel is a **sibling** of it, so
  from inside the panel Escape reached nothing at all. There is now one
  document-level handler that yields to the map handler while focus is on the map.

Closing returns focus to wherever the reader came from. The `isConnected` guard
is not a corner case: opening a building from the map search closes the result
list, so the button they came from is usually **already gone** by then — verified
in the browser, focus went to `<body>`. There is a fallback to the map svg
(`tabindex="-1"`), and in the common search path focus lands back on the search
input, which is better still.

---

## 16 · Session 2026-09-08 — the ladder was measuring the wrong thing

Five items were raised. All five were done. Two of them turned up findings that
were not part of the ask.

### 16a · The social-housing rung read backwards, and it was not the filter

The ladder showed **排除社會住宅 −0.165pp** — remove subsidised leases and the
yield *falls* — which is the wrong sign for a population renting 28% below
market. The filter is correct (`~isin` over `fillna("")`, so NaN survives; the
2³ grid reproduces all four shared ladder rungs to 1e-9). **Two presentation
faults produced it, stacked:**

1. **Mixed units.** Rungs 1–5 were medians over *pairs*, 6–7 over *buildings*.
   Social leases concentrate in a few enormous 包租代管 studio towers: a building
   holding any social lease carries **32.8 pairs** against **7.8** for one that
   holds none. A pair-level median weights that group **14:1**; a building-level
   median weights it **3.3:1**.
2. **Ordering.** Social housing is removed while room-shares are still in.
   Room-shares yield **~1.27%** (their 面積 field describes the building, not the
   let) and are **14.6%** of market leases but **0.0%** of social ones — so
   dropping social housing *triples* the room-share weight. Textbook Simpson: in
   every 出租型態 individually the social lease yields LESS (獨立套房 −0.05pp,
   整棟戶出租 −0.25pp, 分租套房 −0.37pp), and the aggregate still moves the other
   way.

**Fixed:** every rung is read per building and carries a 95% CI; the per-pair
figure sits on each row instead of in one terminal rung (`building` is now a
duplicate of `related` and is not drawn — it stays in the payload). New
`filter_marginals` publishes each filter's **Shapley value** over the 2³ grid,
which sums exactly to the total move. Social housing is **+0.181pp per
building** — the sign the subsidy story predicts, and the largest of the three
filters.

> The page's own copy said the ladder "measures one thing only: what each
> cleaning decision is worth". **It cannot**, and that sentence is what kept the
> reversal invisible. Retracted on the page and in the docstring.

### 16b · `verdict: "dead"` was a hard-coded string

`dead_hypothesis_block` returned the literal `"verdict": "dead"`. True for two
cities (gross gap 0.041pp — a rounding error, so the net gap could only have come
from the cost model). **Never re-evaluated when the scope went national, where it
is false:** gross gap **+0.374pp, 95% CI [0.246, 0.494]**, present *before* any
cost model, widening to **+0.526pp** after. The cost model contributes 28.9% of
the net gap, not ~81%.

The verdict is now **derived** from `gap_ci`: `alive` if the gross interval
excludes zero, `reversed` if it excludes zero the other way, `dead` only if it
contains zero. The page's heading and copy branch on it. `test_the_dead_
hypothesis_is_on_the_record` used to assert `== "dead"` — asserting the *answer*
is exactly how a stale conclusion survives a change of scope, so it now asserts
the record and the derivation.

The same fault hit **§dispersion**: "one building spreads 2.46× wider than the
whole city" was true for 12 Taipei districts and inverts across 22 counties
(0.551 vs 0.932, ratio 0.59). Copy now follows the ratio in both directions.

> **The pattern to watch for.** Going national in one commit silently invalidated
> several published conclusions. Numbers update themselves; **prose does not, and
> neither do tests that assert a conclusion instead of a derivation.** Before
> trusting any sentence in §6 or on the page, check it against the payload.

### 16c · Reproducibility (item 2)

`meta.provenance` now carries `version` (`PAYLOAD_VERSION`, currently **1.0**),
`built`, `commit`, and a **per-season SHA-256 manifest** plus a combined
`source.sha256`. The build writes `housing_data.json.sha256` beside the payload.
`bin/rebuild-housing.sh` rebuilds and diffs; `docs/REPRODUCING.md` explains the
three cases a mismatch can be. Page footer and method section print version,
date and the short source hash.

> ⚠️ **Both GitHub repos are PRIVATE** (`Stanley-jen/twse-alpha-scout`,
> `Stanley0210/Quants.tw` — both 404 unauthenticated). "Check my denominator" is
> not a real invitation while the code is unreadable. **Making a repo public is
> Stanley's call and was not done here.**

### 16d · Intervals and identification (item 3)

95% CI now on: the headline (in the hero), **every ladder rung**, every MRT
distance bin, and the walk-up/tower gap. Browser-side intervals use a seeded
`mulberry32` + quickselect — deterministic, because an interval that moves on
every page load is not checkable. `two_stage_ci` is extracted so the headline,
the district ranking and the ladder all quote intervals from one implementation.

Identification is now stated out loud: the floor/furniture results are
**within-building** (confounders held constant by construction) and the MRT
result is **between-building** (nothing controlled) — they were being presented
as peers.

### 16e · The ceiling, and the PDF (items 4, 5)

**24.0%** now sits beside 6.22% in the hero, with a `hs-plain` line stating that
the pair bounds every possible version of the analysis.

`housing_report.py` → `housing_report.pdf`, 8 pages, A4, all figures read from
the payload so it cannot drift. Cover carries version, date, commit, source hash
and payload hash.

> **The CJK font is load-bearing.** reportlab's built-in CID fonts
> (`UnicodeCIDFont('MSung-Light')`) are **not embedded** and rendered the *wrong
> glyphs* — 實價登錄 came out as 巋牝岫完. It looks like text, so it does not fail
> loudly. `data/fonts/NotoSansTC.ttf` (SIL OFL 1.1, embeddable and
> redistributable) is embedded instead. **Verify any PDF change by rendering to
> PNG and looking at it** (`qlmanage -t -s 900 -o . file.pdf`), never by checking
> that the file was written.

### 16f · Two tools this session added, both cheap and both earned

- **A JS syntax gate without node.** macOS ships JavaScriptCore:
  `/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc -e
  'var s=read("housing.js"); new Function(s)'`. The repo has no node and 801
  tests stayed green through a fully broken `housing.js` once before.
- **A zh/en placeholder-arity test.** A `%s` count that differs between the two
  languages renders `undefined` in exactly one of them, and the tests are in
  English while the site ships in Chinese. 330 strings, now asserted.

### 16g · What browser verification caught that nothing else would

The MRT interval whiskers were drawn in `var(--bg)`. The lower half sits on the
hatched bar and reads; **the upper half always extends past the bar end onto the
page background, where it was invisible** — every interval's upper bound, on
every bin. `PARSE OK` passed, the DOM contained the elements, and the tests were
green. Now drawn twice: a 4.5px `--bg` halo under a 1.6px `--text` line, which
reads on both grounds.

Also fixed while there: `<html lang>` stayed `zh-Hant` no matter which language
was rendered, so a screen reader announced the English page in a Chinese voice.

### 16h · Still open

- Railway binding and the `noindex,nofollow` on `housing.html` — unchanged, both
  Stanley's.
- Repo visibility (16c).
- The three items from the previous turn: post-stratification treatment, the
  net-yield assumptions, and the social-housing rationale as a *published
  argument* (16a fixes the measurement, not the framing).
- The code-level design review still has not run.

---

## 17 · The prose audit, 2026-09-09 — nine claims, v1.1

§16 found two conclusions that the national rescope had silently invalidated and
warned that there were probably more. Stanley asked for the sweep. **There were
nine.** No figure in the payload moved; nine published *claims* did, so the
version went to **1.1** on that alone.

Method: dump the `STR` table with `jsc`, flag every string carrying a
**hard-coded number** (33 of 333), then check each against the payload, and
separately re-derive every **directional** claim — the ones formatted with `%s`
but whose *direction* is asserted in the surrounding words. The directional ones
are where the damage was.

| claim | was | is | status |
|---|---|---|---|
| `covP` walk-up shares | 49% / 14% | **36.4% / 7.8%** | derived now |
| `wbH` furniture premium | "adds 3%" | **4.2%** | derived now |
| `wbFloorNote` 20 floors | "under 1.2%" | 0.12×20 = **2.4%** | derived (dead branch — `wbFloorGap` renders) |
| `wfP` filter count | "our own **four** filters" | **five** ours-steps | derived now |
| `mapGeo` geocoding | "six municipalities **and Hsinchu** above 98%" | **5** counties ≥98%; **Hsinchu is 0%**; 臺南 is 89.8%; **14** counties at zero | derived now |
| `psNote` bias split | "type barely moves it… **almost all** in price" | type **+0.114pp**, price **+0.200pp** | both stated |
| `ciNote` ranking | "**most** of this ranking is not distinguishable" | **79 of 79** — *none* of it is | `ciNoteAll` branch |
| `f2` parking method | "excluded symmetrically… no assumption needed" | pipeline **subtracts** parking | rewritten |
| `lim3` missing market | "an estimated **70–90%**" | unsourced, **not derivable** | removed; replaced with the 82.1% that IS derivable |

### 17a · The transit conclusion is retracted

The big one. `mrtWhy` ended *"the effect shrinks, and it survives."* With the
intervals §16d added, **it does not.**

- Inside 臺北市 the nearest band (1.99–2.16) and the furthest (2.08–2.42)
  **overlap**, the bins are **not monotone** (2.07, 2.05, 2.20, 2.09, 2.21, 2.28),
  and the whole spread is 0.20pp against 0.81pp nationally.
- The **mechanism reverses**. `mrtP` said *"Rent is not what changes — price
  falls faster than rent."* Nationally price −63.4% vs rent −50.7%, so price does
  fall faster (and rent falling by half is not "not what changes"). **Inside
  Taipei: price −24.4%, rent −25.1%** — rent falls marginally *faster*. The
  price/rent divergence is a **between-city artefact**.

So the national panel describes **where the cheap housing is**, not what transit
does to a yield. The heading now says so (`mrtH2`), and both the heading and the
retraction are conditional on the computed overlap, so they cannot go stale.

> **`wbFloorGap` was citing the transit result as corroboration** — "It is the
> same thing the transit section finds". The floor result is identified
> *within-building* and stands; the transit result does not survive holding city
> constant. Using the weak one to prop up the strong one is backwards, and the
> cross-reference is gone.

### 17b · The rule this produces

Every one of the nine was **true when written**. The failure is not carelessness,
it is that **a number updates itself and a sentence does not**. Three defences
now exist, and they are the thing to preserve:

1. **Derive, don't type.** Any figure in prose comes from the payload via `Sf()`.
2. **Branch, don't assert.** Where a claim has a direction — survives/doesn't,
   wider/narrower, dead/alive — the copy picks its own branch from the data
   (`mrtH2`/`mrtGone`, `ciNoteAll`, `dispHN`, `deadHA`).
3. **Assert the derivation, not the answer.** `test_the_walk_up_prediction_is_on_
   the_record` is the model: it checks the verdict follows the interval, never
   that the verdict is a particular word.

Seven regression tests in `tests/test_housing.py` name each retracted literal, so
a future edit that reintroduces "49%", "Hsinchu", "four filters" or "same thing
the transit section finds" fails.

### 17c · Verified TRUE, left alone

`distH` (corr price↔yield = **−0.814**), `covH`, `aucH` (13.8% in registry),
`heroH` (1 in 16.08), `preH`/`preLim`/`preReach` (floor 5/25/100 all give 5.4%),
`mapP` (400 m grid matches `density_grid(cell=400)`), `repP` (flat 0.633 >
age-scaled 0.527), `gapP` (index steepens), `f1` (`主要用途` contains 住家用 —
the filter is real), `f5`, `f6`, `whyWinV`, `aucRound`, `legal`, and the
"two extremes genuinely differ" half of `ciNote` (大安區 1.775–1.938 vs 南區
3.333–4.432, no overlap).

### 17d · Housekeeping

`<html lang>` follows the rendered language. Gap intervals print in **pp**, not
`%`. `mrtP`/`mrtGone` pass `Math.abs` — they read "falls by 63.4%", not
"falls by −63.4%".

### 17e · A tenth: the management fee is a two-city assumption charged to 22 counties

Found while auditing the assumption panel's own prose. `net_yield` reads:

```python
mgmt = (mgmt_a if county == "a" else mgmt_f) * area_ping * 12.0 if has_mgr else 0.0
```

`mgmt_f` is **新北市's** NT$105/坪/月, and the branch is `county == "a"` — so
臺東縣, 澎湖縣, 雲林縣 and every other county are charged New Taipei's rate. The
panel labelled it "管理費（臺北）/ Management fee (Taipei)" and cited a survey
covering only 北北. Same failure as the prose: a two-city model that survived the
rescope because nothing asserted its scope.

**Not corrected — there is no per-county management-fee statistic to correct it
with.** Measured instead, the way the vacancy term is: `mgmt_exposure()` reports
the median net yield with that rate at full, half and zero, plus how many
buildings and counties are exposed. The panel now says plainly that 20 counties
are charged a rate with no source, and the page prints the range. **The net yield
should be quoted with it.**

### 17f · One bug the arity test cannot catch

The zh and en halves of `mgxP` were written with the same two placeholders in
**opposite order** — `(counties, buildings)` against `(buildings, counties)`.
Placeholder *counts* match, so `test_every_string_has_the_same_placeholder_count_
in_both_languages` passes and one language silently prints "the 20 buildings
across the other 8,139 counties". Caught by reading, not by a test.

> **When adding a bilingual format string, write both halves with the arguments
> in the same order, and read them side by side.** A count test cannot see this.

### 17h · A test that was already guarding this, and what replaced it

`test_the_headline_ratio_matches_the_measured_coverage` already existed. Its
docstring records the hero drifting **three times** — 二十分之一 against a measured
3.66%, then 二十六 against 3.83%, then wrong again at 6.44% — and it pinned the
typed word to the payload.

That is the weaker of the two fixes. The headline is now **derived**
(`Sf('heroH', Math.round(100 / h.coverage_pct))`), which removes the failure mode
rather than policing it, and the test asserts the derivation with the
word-checking branch kept only as a fallback.

**Worth noticing:** the repo had already been bitten by this exact class of bug,
had written a test for that one instance, and still shipped nine more of them.
A test per instance does not generalise. Deriving the value does.

### 17g · Process note

`pkill -f 'underwrite.py'` also kills any `until ! pgrep -f 'underwrite.py'`
waiter shells, because their own command line contains the pattern. Harmless here
but it surfaces as several confusing "task failed, exit 144" notifications at
once. Use a more specific pattern, or accept the noise.

---

## 18 · 2026-09-10 — the net distribution, and two tool notes

### 18a · `histogram_net` was computed and never drawn

Found by a mechanical check worth repeating: **list every top-level payload key
and grep `housing.js` for each.** One key had zero references —
`histogram_net`, the distribution of net yields, computed in every build since
the cost model landed and never rendered, on a page that headlines a net yield.

It was not hiding anything alarming (1 building of 9,805 is negative, 6.18% sit
below 1%), so it was dead weight rather than a suppressed caveat — but the check
found it, and `test_no_payload_block_is_computed_and_never_rendered` now fails on
any future one.

Now drawn **on the same axis as the gross histogram**: gross as hatched bars,
net as a stepped outline, with both medians as differently-dashed verticals.
The distance between them IS the cost model, which is the thing the page asks
the reader to own. Caption states that 6.2% sit below 1% and 1 below zero, and
that the sliders move the chart.

> Two bugs I introduced doing it, both caught by looking rather than by tests:
> - **`ticks(lo, hi, n)` takes the number of INTERVALS, not a step.** I passed 1
>   and the x-axis collapsed from eight labels to its two endpoints. Everything
>   still rendered; the DOM had a `<text>` count of 2 and nothing complained.
> - I wrote `netBelow(t)` returning a **count when `t === 0` and a percentage
>   otherwise**. It rendered correctly the day I wrote it. Split into
>   `netBelowN` / `netBelowPct`.

### 18b · Verifying a chart when the Browser pane is hidden

Screenshots come back **solid black** when the pane is hidden (`tabs_context`
says so explicitly), and `computer{action:'zoom'}` silently returns a full
screenshot instead of the crop. Neither fails loudly.

The way through, which worked and is worth reusing:

1. In the page, grab the chart's `outerHTML`, the shared `<defs>` (the `#hxbar`
   hatch lives in a different SVG), and `getComputedStyle` for every `--token`
   the markup references.
2. String-replace `var(--x)` with the resolved values, wrap in a standalone
   `<svg xmlns=…>` with an explicit background rect.
3. `btoa` it out, `base64 -d` to a `.svg`, then **`qlmanage -t -s 1320 -o . f.svg`**
   → PNG → Read it.

macOS Quick Look rasterises SVG directly, so this needs no library. It fits the
output to a square, so a wide chart comes back cropped — scale the viewBox if the
right-hand side matters.

### 18d · The 4-agent retry DID work, and caught three things — one of them mine

The lean retry (4 auditors, session limits permitting) returned **25 findings**.
Its verification stage never ran, so all 25 are **unverified**; three were
checked by hand and all three were real.

**1. "the sliders in the cost section move this chart" was false — and I wrote
it an hour earlier.** Two separate reasons, and fixing the first was not enough:

- The figure read `D.histogram_net`, `D.headline.net` and the precomputed
  `b.nt` — every one frozen in the payload. Fixed by recomputing through the
  same `netYield()` twin the table uses.
- It *still* never repainted, because the slider handler only called
  `renderWaterfall()` and `renderTable()`. The figure is now `histFigure()`
  behind `#hs-hist`, with `renderHistogram()` wired in beside them.

  The chart sat directly above a table whose net column *did* respond, so the
  reader had positive evidence the sliders worked. Verified by driving the tax
  slider to max: net median 1.84% → 1.59%, below-1% 6.2% → 15.9%, negatives
  1 → 13, and restoring returns the exact prior values.

**2. `histogram()` clips.** `np.histogram(v.clip(lo, hi), …)` means both end
bars are pile-ups, not counts of their own interval — the right-hand spike (207
buildings against 46 in the neighbouring bin) is everything ≥5.75 stacked up.
Real, and an artefact. Now disclosed in the caption (`histClip`).

**3. The auction 13.8% is a share of LOTS, printed against a count of
BUILDINGS.** `in_registry_pct = hit.mean()` over the row-level frame — 266 of
1,922 lots — while `buildings = d.k.nunique()` is 1,448. The sentence read "Of
the 1,448 buildings … 13.8% appear", multiplying a lot-level rate by a
building-level count. **Exactly the pair-vs-building error from §16**, in a
section nobody had re-read. Both units are now named.

> Extracting `histFigure()` also broke the page at runtime: `padT` was declared
> in `secMethodChecks` and shared with the gap chart, and it left with the block.
> **`jsc` reported PARSE OK and the whole page threw `ReferenceError`.** A
> syntax gate is not a smoke test — load the page.

**The remaining 22 findings are unverified** and listed in the run journal:
`.../subagents/workflows/wf_40f0f0f0-392/journal.jsonl`. Several look plausible
on their face (a `preH` claim against `presale.separable = false`, `incP`,
`mrtN`'s coverage sentence, the `f1`/`f2`/`f4` cleaning-rule list, the `tax`
assumption source). **Do not act on any of them without checking first** — the
verify stage is exactly what did not run.

### 18c · Workflow, again

A 10-agent audit fan-out **died completely**: all ten agents hit the session
limit, ~1.04M subagent tokens, zero findings. The 4-agent retry **worked** and is
the most useful thing in this section (§18d) — 3 auditors returned, the verify
stage did not. Running total on this project: **6 failures and 2 partial
successes in 9 attempts**, almost all session limits.

> **Size it to finish.** Ten agents died; four returned real findings. And
> **never block a deliverable on one** — but do run it after, because the one
> thing it caught was a false claim I had shipped an hour earlier and re-read
> twice without seeing.

---

## 19 · 2026-09-11 — the audit's second pass, and the headline was wrong

The 4-agent re-audit returned **36 findings, 19 surviving adversarial check**.
Nine were acted on. Two of them are the most serious things found in this whole
sequence, and one of those is the site's opening sentence.

### 19a · The hero attributed our own filtering to the law

The lede read: *"the registry records both — but only **6.22%** of buildings have
both on file."*

**27.81% have both on file** (the waterfall's own step 0, 157,594 → 43,833).
6.22% is what survives *our* window, parking, social-housing, room-share and
related-party filters. The `wfP` section three screens down splits the loss
correctly — **law 72.2pp, ours 21.6pp** — and the headline contradicted it.

This is the exact error the site exists to expose, committed by the site, in its
own first sentence, in the flattering direction. Now states both numbers, which
is the **stronger** version of the argument: separating the law's limit from our
own is the thing no competitor does.

### 19b · The MRT distances were not distances, and my retraction was also wrong

`map.base.stations` holds **131 stations — the Taipei network only.** Every
building still got a "distance to the nearest station":

| county | n | median "distance" |
|---|---|---|
| 高雄市 | 1,959 | **274,843 m** |
| 臺南市 | 710 | **245,048 m** |
| 臺中市 | 997 | **112,217 m** |

Those are distances to Taipei. **73% of the old ">2.5 km" bin was buildings like
that**, so the national panel was a map of which city you are in wearing a
distance label.

Then §17a made it worse. I retracted the finding on a 臺北市 comparison —
but **Taipei City has 4 buildings beyond 2.5 km** (17 beyond 2 km). The "null"
was an empty far group, and I published it as a correction.

Restricted to the 4,920 buildings the layer can speak about (北北桃), the
gradient is **2.095% → 2.715%, monotone across all seven bins, intervals
separate.** Holding city constant in **新北市** — the one county with both a real
near group (630) and a real far group (808) — it is **+0.529pp, intervals (2.104,
2.182) vs (2.622, 2.738), price −47.4% against rent −28.9%.**

> **The finding stands.** Direction and mechanism both survive holding city
> constant. 臺中/臺南/高雄 are now excluded outright rather than given a distance
> to Taipei, and the control panel is 新北市, not 臺北市.
>
> **The lesson is about the control, not the claim.** A null from a group with
> n=4 is not evidence of absence, and I read one as if it were. Check the far
> group's size before believing a null.

### 19c · Seven more, all confirmed before acting

| | was | is |
|---|---|---|
| `preH`/`prePlac` | "net of time, almost nothing" (0.9%) | `separable: false` is **in the payload and was never rendered**. The same ratio runs 5.4/7.9/7.0/3.1/**0.9**% across the five lags — the smallest was published, on the sparsest cell, with no interval. At lag 0 it is 5.4%, where there is no time to net out. Only the 5.4% gap (CI 4.2–7.0) stands. |
| `incP` | the sliver "would overstate" | **understates** by ~0.7 yr (13.7 vs 14.4): dearer per ping (+2.7%) but smaller (−7.2%), so lower total price |
| `deadPA` walk-up | +0.374pp, clean | **+0.120pp** within price decile (reversing at the dear end), **+0.637pp** within district, 23/28 districts. Both cannot be the effect. Published with both controls. |
| `ciNoteText` | "79 of 79" under the **county** chart | 79/79 is over districts; at county level **11 of 13**, 臺北/新北 and 新北/桃園 separate. Branches on level now. |
| `covRateS` | "share with both a sale and a lease" | that is step 0 (27.8%); the chart shows the **final match rate** (8.8%) |
| `ladH` | "five ways to count" | six rungs render; derived from `shown.length` |
| `aucRound` | "a lot of any auction discount is this schedule" | no reserve level is stored and the page declines to measure a discount. States only the measured shares. |
| `f1` / `f2` | symmetric filters | `住家用` is **sale-side only**; parking handling **differs** by side |
| `biasH` | "%s% of registered leases" | 82.1% is of **whole-unit** leases (~58% across all) |
| `mcH` | "two corrections that did not work" | one, plus the distribution |
| `wbFloorN` | sale card reused the rent card's count | 22,274 sale-side buildings had been described as letting on 2+ floors |

### 19d · The rule that keeps earning its keep

Two strings I wrote *this session* were already stale by the time I tested them:
`deadCtl` said "reverses in the two most expensive deciles" (typed), and `ladH`
said five over six rows. **Derive it or it will be wrong.** `deadCtl` now counts
its own reversals.

And two pre-existing tests failed because they asserted the *old structure*
(`mrtTpe`, `mrtGone`). Both were rewritten to assert the principle — that a
within-city control panel exists, that the correction note is present and
derived — rather than a string name.

---

## 20 · 2026-09-11 — the metros went in, and they killed the transit finding

Stanley asked for more data sources, minus hotels. This is the first: the other
metro systems. It was meant to strengthen a finding and it withdrew one, which
is why it was worth doing first.

### 20a · What changed

`basemap.py` pulled stations from Overpass bounded to `BBOX_CORE` — the Taipei
basin. New `BBOX_TW` covers the island, and the metro layers (`railway=subway|
light_rail`, `station=subway|light_rail`) are queried separately from roads and
water, which stay bounded to the basin where their geometry is worth the bytes.

**131 → 264 stations. Buildings with a real station distance: 4,920 → 8,014.**

Each station now ships its **kind** (`[x, y, name, 0|1]`, 0 = heavy rail), and
`attach_mrt` computes **two** distances per building: `mrt` (all stations) and
`mrth` (heavy rail only).

### 20b · The finding does not survive

| | 新北市 | 高雄市 |
|---|---|---|
| heavy rail only | **+0.58pp, intervals separate** | no gradient |
| + 輕軌 | **+0.02pp, intervals overlap** | no gradient |

Adding 淡海輕軌 — which serves exactly the outer 淡水 area that **was** the far
group — reclassifies those buildings as near and the gradient collapses. And
高雄, the first genuinely independent replication (its own metro, only reachable
after this change), shows nothing under either definition.

> **Withdrawn.** The section now says so, shows four panels (national, heavy-rail
> only, 新北市, 高雄市), and states that the visible relationship is smaller than
> the difference made by deciding what a station is.

**This section has now been wrong four times** — the original national panel on
garbage distances, my retraction on a 臺北市 far group of 4, my un-retraction on
heavy rail only, and now the withdrawal. Each was defensible on the evidence
available; each was defeated by better coverage. **Do not restate this finding
without checking the station definition and at least one independent city.**

### 20c · The rule

A result that flips on a judgement call — is 輕軌 a station? — is a finding about
the judgement, not the subject. **Where such a call exists, compute both and show
both**, which is why `mrth` ships beside `mrt` rather than one being chosen.

### 20d · MOI's 112 CSV series — mechanism solved, fetcher not built

`https://pip.moi.gov.tw/Publicize/Info/E3030` carries **112 county-level time
series** as CSV. Several are directly on point and not yet integrated:

- **法院拍定成屋總件數 / 房地拍定總金額** `[2,1,4] [2,2,4]` — this is **法拍**,
  the channel §13 says is much larger than the 金拍 the page can see
- **住宅存量 / 建物總量** `[5,1,2] [1,1,2]` — the real denominator. The page's is
  "buildings with a sale record" (157,594); the housing stock is far larger
- **租金單價-分租雅房、住家、套房、獨套** `[3,1,3]` — an official rent series split
  by exactly the 出租型態 categories behind the Simpson reversal in §16a
- **購置住宅貸款平均利率** `[3,1,5]` — replaces the hard-coded `MORTGAGE_RATE`

**How the export works** (worked out, verified):

1. The CSV links are `a.cmd-link` with `data-keyk` / `data-keyn` / `data-keyt`.
2. Their jQuery handler sets `Command=匯出CSV檔`, `K`, `N`, `T` on `form1` and
   posts to `/Publicize/Info/E3030`. No `__VIEWSTATE` is required.
3. **Two gotchas.** Python 3.13 enables `VERIFY_X509_STRICT` and the MOI
   certificate has no Subject Key Identifier, so `requests` fails the handshake —
   mount an adapter whose `SSLContext` clears `VERIFY_X509_STRICT` (keep
   verification on; do **not** use `verify=False`). And a WAF rejects requests
   without browser-like headers — `User-Agent`, `Accept`, `Accept-Language` and
   the `Sec-Fetch-*` set get through.

---

## 21 · 2026-09-11 — 內政部's series beside ours (`fetch_moi.py`, v1.4)

The second of Stanley's data sources. §20d had the mechanism; this built it.

### 21a · What shipped

`fetch_moi.py` — eight series from `pip.moi.gov.tw/Publicize/Info/E3030`,
cached under `data/ref/moi/`. `moi_block()` in `underwrite.py`; `secMoi()` on
the page, simple mode, placed just before the table. Four things, each an
official figure set beside the site's own:

| | official | ours | what it says |
|---|---|---|---|
| **法拍** | 5,202 court lots, NT$625億, 11 quarters | 1,922 金拍 lots | the channel §13 admits it can't see is ~2.7× the one it can. **Parallel channels, not a subset** — `fasc_vs_court_pct`, not "share" |
| **stock** | 10,645,602 buildings (棟) | 157,594 with a sale; 9,805 priced | the priceable slice is **0.092% of all buildings — one in 1,086.** The strongest form of the central claim, on the government's denominator |
| **price** | mean contract 元/坪 by county, 115Q1 | median across matched buildings | ours sits **+9.8% above** across the six large counties (臺北 +16.7%). The "visible slice is dearer" finding from outside the registry |
| **mortgage** | 2.69% (114Q4, all new loans) | 2.322% (CBC five banks, May 2026) | different populations; both shown, neither replaces |

### 21b · Three things the data itself taught

- **The export is not clean.** 買賣契約價格平均單價 ships **335 rows with shuffled
  columns** — `period, 建物類型, county, district, 0.00` instead of
  `period, county, district, 建物類型, value`. A building type in the county
  column is the tell. Dropped and logged.
- **Four layouts, one loader.** Plain; with 鄉鎮市區 (district rows, county total
  on a blank district); with 建物類型 (a category column); and one-column-per-
  category (melted). `load_series` returns `period, county, district, kind, value`
  for all of them.
- **The best-looking series is dead.** 租金單價-分租雅房、住家、套房、獨套 — an
  official rent per 坪 by exactly the 出租型態 categories behind §16a's Simpson
  reversal — **runs 098Q1–102Q4 and stops.** Three counties, nothing after 2013.
  Fetched, checked, left out. It stays in the registry as a comment so nobody
  re-discovers it.

### 21c · Units, kept apart on purpose

`住宅存量` and `房屋稅籍住宅類數量` are in **宅** (dwellings); `建物總量` is in
**棟** (buildings, all uses). The site counts 棟. Only 建物總量 is divided
against; the others are printed with their unit and a sentence saying they
cannot be. `住宅拍賣移轉筆數` counts **transfers (筆)**, not lots — a lot can
register as several — so it is `court_resi_transfers`, not a residential
subset of `court_lots`.

### 21d · Two bugs of my own, same session

- `moiStockP` had **"9,805" typed in.** Derived before the first render.
- `moiPriceWhy` took `(count, gap)` and I passed `(gap, count)` — rendered
  **"+9.8 counties … 6%"**. §17f again: same placeholder count, one language
  reads wrong, and the arity test cannot see it. Caught by reading the page.

### 21e · Connection notes for the next fetch

`_RelaxedX509` clears only `VERIFY_X509_STRICT`; the MOI cert has no Subject
Key Identifier. Do **not** let this become `verify=False`. GET the page first
for cookies, then POST — the WAF rejects a bare POST. ~60 s per export; the
server is slow, not broken. `fetch_all` sleeps 2 s between series.

### 21f · The three that live as HTML tables (v1.5)

Not in the E3030 catalogue. Each is a table on its own page; `fetch_moi.
_scrape_time_tables` pulls any table whose first header cell matches and whose
first column parses as a period (季 / 上下半年 / 年). `HTML_SERIES` registers
them; `load_html_series` returns the same tidy shape as the CSVs.

| series | page | what it is set against |
|---|---|---|
| **住宅價格指數** | E1060, table headed 縣市 | the drift the site leaves in. `USE_PRICE_INDEX` is off because the site's own index made the yield-vs-gap slope worse; the official index says prices moved **+5.62% / 9 quarters = 0.61%/q**, so at the median pair gap of **2.0 q** a typical pair carries **+1.22%** uncorrected. First time that limitation has a number. |
| **低度使用(用電)住宅** | E1040, first 時間 table, half-yearly | the 5% vacancy assumption — as **context, not input.** 9.31% nationally, 臺南 10.79%, 臺北 6.07%. The page states plainly that this is empty homes over all dwellings, rental vacancy is unlet rentals over rental stock, and Taiwan publishes no such statistic. `test_low_use_is_context_not_the_vacancy_input` guards `DEFAULT_VACANCY_PCT`. It also gives the break-even test something to stand against: 安平區 needs 24.8%; 臺南's empty-home rate by any measure is 10.8%. |
| **待售新成屋** | E1040, second 時間 table, quarterly | the pre-sale section's unseen market: 112,501 completed, unsold, unoccupied at 114Q4. |

**Also found and not used:** E4040 (主題項目下載區) has a simpler GET export —
`E4041?m=csv&k=K02&n=T13` — and carries `房屋稅籍住宅類數量依屋齡區分` (stock
**by age**) and `…依總樓層區分` (stock **by floor count**). Those are the real
denominators for §6's age and building-type coverage findings, which currently
use "buildings with a sale" as the base. **Worth doing next**; same cache, same
session helper.

**E1040 also carries the older county series** (q1–q4 groups) but they stop at
109; only q5/q6 are current. The county-level 低度使用 rate the handoff §6
said had "stopped being produced in 民國109" is the *village/district* level —
the county series continues and is what is used here.

### 21g · The real denominator for the coverage finding (v1.6)

E4040's themed exports: `房屋稅籍住宅類數量依總樓層區分` and `…依屋齡區分`, both
at district level, both current to 115Q2. `fetch_moi.load_theme_series` splits
the source's single `縣市/地區` column ('新北市板橋區') into county and district.

**Against the stock, not just what sold:**

| | stock (宅, site-eligible part) | sold (棟) | priced (棟) |
|---|---|---|---|
| 住宅大樓 (11+) | 42% | 37% | **71%** |
| 華廈 (6–10) | 20% | 27% | 21% |
| 公寓 (4–5) | 38% | 36% | **8%** |

Plus **42.7% of all dwellings are 1–3 storey** (mostly 透天), outside the
`RESIDENTIAL` filter by construction — never stated before.

**Age:** stock mean **34.46**, matched median **19.0**. Over-40: 39% of stock,
10% of matched. Under-10: 12% of stock, 36% of matched. Drawn as two
distributions in the MOI's own ten bands.

> **The 棟/宅 point, stated the way the page states it.** A tower is one
> building and dozens of units; a walk-up is one building and a handful. So a
> unit-weighted stock is already tower-heavier than a building-weighted one
> would be, and comparing the site's building distribution against it
> **understates** the skew. That is the conservative direction and the page
> says so. Never divide the two.

Rendering: the `covMix` chart became three columns when `D.moi.stock_by_floor`
is present (`stack()` takes `'stock'` as a field name and reads
`share_of_inside_pct`); `ageVsStock()` is a new figure after it. Both fall back
cleanly when the MOI block is absent.

### 21h · The audit of my own MOI work (v1.7) — seven findings, one serious

A 3-auditor + 1-verifier workflow (4/4 completed, 11 raw, **7 confirmed**) on
v1.4–1.6. Every one was real. The serious one:

> **建物總量 is not buildings.** It *exceeds* 住宅存量 in every county — 臺北市
> 1,118,574 against 966,878 dwellings at 114Q4 — which no physical-building
> count could in a tower city. It counts registered 建物 (建號), roughly one per
> unit. I divided the site's 9,805 門牌-keyed **buildings** by it and published
> "one building in 1,086" as *"the strongest form of the central claim"*. Wrong
> by an unknown multiple, in the direction that flatters the thesis, in the
> section whose whole point is being careful with denominators.

Withdrawn. The three stock figures are labelled (宅 / 宅 / 建號), set beside
the site's 棟 count with a sentence saying why none can be its denominator, and
a test asserts the division does not return.

The other six: 金拍 was counted over its full live feed (1,922) against a
windowed 法拍 while the sentence said "same window" — now 1,765 / 33.9%; the
low-use rate divided by 住宅存量 and matched nothing the MOI prints — now over
房屋稅籍住宅類數量 and reproduces the published **9.44%** exactly; the coverage
chart's stock column said "all housing stock" while showing the 4+ storey subset
renormalised (住宅大樓 read 42% where its share of all stock is 24%) — relabelled;
`moiLuWhy` carried `%%` and was rendered through `S()` not `Sf()` so the page
printed **"5%%"**; "by any definition" was a quantifier the data cannot support;
the English age headline said "averages" of a median.

**The pattern, again.** Three of the seven are *unit* errors (棟/建號, windowed/
unwindowed, one denominator vs another) — the same class as the pair-vs-building
ladder in §16 and the lot-vs-building auction in §18d. **When two numbers from
different sources are set side by side, check the unit of each before the
arithmetic, and say what the unit is on the page.** The `S()`-vs-`Sf()` bug now
has a test that greps every string carrying `%%` for a bare `S()` call.

Workflow tally on this project: **8 runs, 4 completed** — and all four
completions found real bugs I had shipped. The two that died were 10 agents;
the four that worked were 3–5.

---

## 22 · 2026-09-11/12 — reading it top to bottom as a stranger

Stanley's ask after six versions in three days. Pulled the **rendered** page —
simple mode, Chinese, the mode a first visitor lands on — and read it in order.
Not the source; the source was where every previous pass had looked.

### 22a · What a stranger hits

**The MRT section was broken as a piece of writing.** Six paragraphs followed
the chart and **three contradicted the heading**: the heading said "does not
hold", `mrtWhy` said "the direction survives", the verdict said withdrawn, the
old 【兩次更正】 paragraph (v1.2) still said 方向與機制都成立 over a number that
now rendered +0.015pp, and `identBetween` cited "the Taipei column" that no
longer existed. Three rounds of correction had been layered on and the
superseded layers never removed. **A stranger could not tell what the site
concluded.** Now one narrative: lede → four panels → verdict → definitional test
→ replication → number-free history → identification.

The other six, none of which a source-level audit had caught:

| where | what a stranger sees |
|---|---|
| hero | 27.8% and 24.0% two paragraphs apart, nothing saying how they differ. Now three named thresholds: both records at all / both within the window / both plus the quality bar |
| coverage | two age figures back to back, no lead saying what the second adds |
| income | **"分母是主計總處的主計總處 家庭收支調查…"** — the template prefixed the source's own name |
| within-building | cross-referenced an MRT finding since withdrawn |
| 行政區 | "the statistic stopped in 109" — the *district* series did; the county one continues and sits three screens down |
| pre-sale | "0.9%" and "1%" for the same figure in one sentence |

### 22b · The rule this adds

**Every audit so far read the source. None read the page.** A `%s` that renders
correctly, a string that is derived and true, a section that passes every test
— can still sit next to a paragraph that says the opposite, or repeat a name,
or cite a chart that was removed. **Corrections accrete.** When a section is
corrected, remove what it superseded, then read the whole section as prose.

And once more: while fixing the 行政區 note I **typed 10.9%** into it. Caught
before render, derived via `countyLowUsePct()`. The reflex does not go away;
only the check does.

### 22c · Cold readers — what four strangers actually said (v1.8)

Appraiser, first-time buyer, journalist, academic; each read the rendered
Chinese page once, in order, and reported. First launch died on the session
limit in 15 s; relaunched after reset, 5/5 completed.

**They agreed on the conclusion.** All four: 1-in-16 coverage; the covered slice
is new, dear, tower-heavy; net 1.84% < mortgage; everything else retracted.
The argument works. Everything below is about the page, not the argument.

**They agreed on what is wrong** (4/4 unless noted):

| | what they said | done |
|---|---|---|
| **length** | "too long by roughly half"; "twice too long on a phone" | MRT 4 charts → 1 + summary; pre-sale post-mortem, income list, MOI 法拍/待售/2nd rate → advanced |
| **changelog prose** | "performing honesty at the reader's expense"; buyer counted six retractions of things "I have no earlier version to compare against" | every 已撤回 / 本站原本 / 第一版 sentence → advanced only |
| **82.1% on the last screen** | "the single most important fact on the page"; 3/4 said it changed how they read every rent number above it | now directly under the hero tiles, with the by-lease vs by-building reconciliation they asked for |
| **stale 131-站 footnote** | "the moment I stopped trusting the page" | rewritten — 264 stations, OSM, 臺南 excluded for having no metro |
| **two 上限 in ten lines** | all four did the subtraction themselves | hero tells the funnel once; three thresholds named |
| **配對 undefined** | "14.5 per building — of what?" | defined in the tile |
| **1.84% on unstated costs** (3/4) | "a 31% haircut from a black box" | schedule under the hero, from the sliders' defaults |
| **coverage pie ≠ hero denominator** (academic) | 40,561+29,954+40,427 = 110,942, not 157,594 | **a figure moved — see below** |
| "the law" for 72.2pp (academic) | no lease ≠ unregistered lease; most are owner-occupied | relabelled; hero's "law's limit" removed |
| 新北 panel unlabelled (2/4) | "had to subtract to infer which definition" | labelled 含輕軌 |
| line = IQR vs CI (2/4) | same line defined both ways | chart draws the CI; `distP` said IQR |
| floor gap from two building sets (2/4) | 22,274 vs 3,775 subtracted as if one | both counts named in the sentence |
| "most people think" (4/4) | who? | dropped |
| `separable = false` (appraiser) | code in prose | prose |
| 5 + 14 ≠ 20 counties (3/4) | 臺南 at 90% unnamed | derived, adds up |

**The figure that moved.** `coverage_block` took the *cleaned* sales frame,
which had already dropped 46,652 buildings whose only sales were parking-
unitemised or related-party. So the per-type match rates sat on 110,942 while
the hero's 6.22% sat on 157,594, and 30% of the headline denominator was never
named. Now on the universe: **towers 10.9% (was 17.1%), mid-rise 4.7% (7.0%),
walk-ups 1.55% (1.9%).** The 6.22% is unchanged and its parts now sum to it.

> **What no source audit could see.** Every earlier pass read `housing.js`.
> Strings that were derived and true, sections that passed every test, sat
> next to a contradicting footnote, or a name printed twice, or a chart that
> was gone. Only reading the *rendered page* — and only strangers reading it
> — found these. The `镭位數` they all flagged was a byte I corrupted in the
> file I gave them, not the page; everything else was real.

**Tally:** 9 workflow runs on this project; 5 completed, all five found real
things. The four that died were session limits, three of them 10-agent runs.


## 23 · 2026-09-12 — the phone, and the screen reader

Every verification up to here was a 1024-px browser. The page had never
been rendered at 375 px, and no chart had a name a screen reader could say.
No payload change — `housing_data.json` stays at **v1.8**, same SHA-256,
no PDF resend.

**Rule chosen: charts scroll, they don't shrink.** A 560-px chart squeezed
to 295 px has 6-px tick labels; a 560-px chart inside `.hs-scroll
{overflow-x:auto}` reads at full size and the thumb pans it. `chartW(natural)`
in `housing.js` returns the natural width above 900 px and
`max(280, vw − 80)` below it (80 = 2×16 gutter + 2×24 card padding — the
first draft used 40 and every card falsely reported horizontal scroll).
Fourteen charts take it. Three that could not survive a plain rescale got
a `narrow` branch: the **waterfall** (250-px left pad left 7 px for the
longest bar → proportional `wfPadL`), the **district** chart (value labels
printed through their own dots → label at `W−4`, building-count column
dropped), and **covMix** (three columns at hard-coded x → `slot = W2/3`).

**Result at 375 px, both modes: `overflowPx = 0`.** The one non-chart
overflow was a 64-character SHA-256 in the provenance block (166 px in
advanced mode) — `overflow-wrap: anywhere` on `.hs-kv dd`.

**Touch.** `.hs-btn`, `.hs-seg button`, sliders ≥ 44 px; `.hs-rung` ≥ 48 px.
`targetsUnder44: 0`.

**Screen reader.** `svg(w,h,body,cls,label)` gained a 5th arg: with a label
→ `role="img" aria-label`, without → `aria-hidden="true"`. `fig()` now emits
`<figure>/<figcaption>` and injects its own title as the chart's label, so
every figure chart is named for free; the eight bare charts (mrtPanel,
presale, district, bias, dispersion, hist, gap, scatter) are named at the
call site. Nine tables got `aria-label` from their existing heading strings;
four sliders and the map back button got labels; the top bar is a
`<nav aria-label>` and the sections sit in `<main>`. Final audit:
`svgUnlabelled 0 · tablesUnlabelled 0/9 · slidersUnlabelled 0 ·
buttonsUnnamed 0 · landmarks main/nav/header/footer`.

**Three things that didn't work, kept here so nobody re-tries them.**
The `.hs-vs` two-column override placed inside the first `@media` block
did nothing — it sat *before* the base `.hs-vs` rule in the file and lost
the cascade; it lives in its own `@media` block after the base rule now.
A `.hs-scroll::after` fade gradient as a scroll hint added 28 px to
`scrollWidth`, so charts that fit reported as scrolling — removed. And
helper scripts that named a variable `top` hit `top.push is not a
function` — `window.top` — renamed `uniq`.

**Desktop after all of it:** chart widths 640/560/860 unchanged, four hero
tiles, `overflowPx 0`, 843 tests, 400 STR entries with matching `%s` arity.

## 24 · 2026-09-13/14 — the Railway scan, and why the domain routes nowhere

Full runbook: **`docs/RAILWAY_GO_LIVE.md`**. The short version:

- The 404 is Railway's edge fallback: DNS reaches Railway (`69.46.46.69` is
  theirs), the `_railway-verify` TXT is still there, the edge still holds a
  cert issued **2026-07-31** — so the binding existed then and was gone by
  08-29. No deploy happened in that window. **The account lapsed, not the code.**
- The Railway account in Stanley's Chrome (`Stanley.jen@icloud.com`) has zero
  projects, an expired trial, no card, no billing history. It is not the
  account that ran `perfect-optimism`. That one is a different login —
  GitHub as Stanley0210, most likely.
- Repo side, done in `119d29a`: `/health` goes green in housing mode (it sat
  at 503 forever, which would have failed any dashboard healthcheck), the PDF
  and the payload digest got routes and footer links, Procfile aligned with
  `railway.toml`. 845 tests.
- **Boot needs three non-empty variables even in housing mode:** `SECRET_KEY`,
  `OPENAI_API_KEY`, `FUGLE_API_KEY` — the latter two because clients are
  constructed at import. The audit's first pass said Fugle tolerated `None`;
  the synthesizer read the client factory and found it raises. Keep that.
- `quants main` is 26 commits behind `feat/housing` and a strict ancestor.
  The fast-forward push was blocked by the session's permission classifier;
  it is Stanley's one command: `git push quants feat/housing:main`.

**Tally:** 10 workflow runs; the ninth died on a session limit with 8/8 agents
failed, and its resume replayed nothing because nothing had finished — the
journal is the only way to tell a dead run from an empty one.

## 25 · 2026-09-16 — what could be added next: a verified menu

Stanley asked what more data the page could analyse. Rather than list ideas,
seven scouts checked ~40 candidates — three by counting real records in the
registry files already on disk, four by fetching official portals — and a
critic re-ran five of their claims and ranked the survivors. The menu, with
URLs, counts and traps, is **`docs/HOUSING_NEXT_DATA.md`**.

Three things worth recording here because they touch numbers already on the page:

- **The net yield's management-fee term is a guess the registry can gate.**
  `net_yield` charges a fee for every 管理員 building; the unused 備註 field
  says the rent already includes it on ~35% of lets in those buildings, and a
  含管理費 rent is only +4.8% within building (1,743 buildings) — below the
  assumed NT$100–180/坪. Ladder rung, two bounds. (#2)
- **Un-itemised bundled parking may not be free.** `fetch_lvr._subtract_parking`
  assumes a zero 車位總額元 means the space came at no extra rent; within
  buildings that have both, total rent/m² is identical (1.031, n=192), which
  says the parking rent is inside the dwelling rent on those rows — a possible
  upward bias on dwelling yields. n=192 is a hypothesis; re-run at full N and
  publish either way. (#5)
- **The page has no volume series and the window contains a halving.** Clean
  existing-home sales 113Q2→113Q4 −52% in every big county, presale −75% by
  114Q1, replicated by the critic. Three policies land in the same quarter, so
  descriptive only. (#1)

Also caught: the benchmarks scout anchored on the 2026-08-30 headline
(2.43/1.76); the live payload is **2.68% gross / 1.84% net**. The critic
flagged it before anything was wired.

**Tally:** 11 workflow runs. The ninth's resume worked as designed this time
— seven scouts replayed from cache, only the critic re-ran.

## 26 · 2026-09-17 — v1.9: three additions from the menu, and the pin that was missing

The three "do first" items from §25 shipped together as **v1.9**. Full
changelog in `docs/REPRODUCING.md`; the numbers are there. What belongs here
is what the build taught.

**The rebuild script could not fail.** `bin/rebuild-housing.sh` built the
payload, then compared it with the sidecar — which the build had just
rewritten. Every run said MATCH. It now holds the committed hash before
building and, on mismatch, diffs the two JSONs structurally and says whether
only `built`/`commit` moved (a reproduction) or which top-level keys did
(collapsing `buildings[i]` to `buildings[*]`). The volume refactor was proven
this way: only the two stamps differed. The v1.9 build's own diff was exactly
`benchmarks, volume, mgmt_flag, buildings[*].mf, assumptions[1].src_*, meta`.

**Nothing under `data/ref/` was hashed.** The 內政部 and 主計總處 CSVs had gone
into the payload unpinned since v1.4 — a re-exported series would have moved
numbers with nothing in provenance to say so. `provenance.refs` (18 files,
keyed by path, `source` untouched) closes that. `fetch_cbc.py` writes a
`MANIFEST.json` so `fetched` is read from disk, never `today()`.

**Two traps in the CBC file, both silent.** A13Rate.csv carries six banks;
彰化銀行 stopped filing in 2008, so "the latest month every bank posts" is
Nov 2008 at 2.17%. Filter to `FIVE`, and the test asserts 彰化 never enters
the mean. And webF1.csv is Big5 while A13Rate.csv is UTF-8-BOM. Also: the CBC
certificate has MOI's defect (no Subject Key Identifier); `_RelaxedX509`
reused, verification still on.

**`chartW()` is for horizontal bars.** Eleven labelled columns at 295 px
were unreadable on a phone. Column charts keep their natural width and pan
inside `.hs-scroll` — the district chart's rule, which the spec had cited and
I applied wrongly anyway. Caught in the browser at 375 px, not by any test.

**Design-pass corrections worth keeping.** The critic caught: two specs
inventing incompatible provenance shapes (unified), `volLead` passed
`meta.seasons` (a 2-pair, would print `112S4` beside `113Q2`), unescaped
apostrophes in two en strings (a blank page), `volLag` asserting an
unmeasured registration-lag mechanism (now labelled 本頁未量測), lease
quarters labelled with `S` while volume teaches `Q` (unified on `Q`), and a
spec that "verified" Fugle tolerates a null key when the client factory
raises. All fixed before code.

**One more build than planned.** `flag_majority_delta_pp` was referenced in
a string before the backend emitted it — the rule is no typed-in facts, so
the backend grew the field and the payload was built twice. The second
build's diff was those two keys and nothing else, which is what the new
diagnostic is for.

**Gates:** 866 tests (23 new), 412 STR entries with matching `%s` arity, PARSE
OK, 0 overflow at 375 px in both modes, both languages free of `undefined`,
the JS flag-only waterfall row (2.00%) equals the Python bound (2.0008),
`all_charged` equals the headline to four decimals, PDF v1.9 carries all
three sections.

**Tally:** 12 workflow runs. The design run (3 specs + critic) is the one to
copy: the critic's must-fix list was seven items, every one real.

## 27 · 2026-09-18 — v2.0: the parking audit found a cleaning assumption false

Menu items #4 and #5 shipped together. Changelog in `docs/REPRODUCING.md`
row 2.0. What belongs here:

**A stated assumption in the cleaning was wrong, and it bounds the headline.**
Since v1.0 `fetch_lvr._subtract_parking` has kept a flat+space lease whose
space rent was never itemised and subtracted only its AREA — the docstring
said a zero "usually means the space came with the flat at no extra rent".
Tested within building at full N: buildings carrying both an itemised and an
un-itemised bundled lease show the same TOTAL rent per m² either way (ratio
**1.032 [1.004, 1.079], n=191**), where a free space would put the
un-itemised lease ~11.5% lower. Three corroborating comparisons and the
excluded social-housing leases agree. So the parking rent is inside the
dwelling rent on **32% of the clean leases**, and the headline gross is
biased up: **2.68% as now → 2.55% with a per-space rent imputed and
subtracted** (net 1.84 → 1.73). Dropping those leases instead gives 2.73% on
30% fewer buildings — and the removed buildings are newer (median completion
ROC 107 vs 88) and 85% towers, so dropping pushes the headline the flattering
way. **Headline untouched; both bounds published; the default treatment is
Stanley's call** (the docstring, the method text and a limits bullet all
point at the block).

**Not "pre-registered".** The spec's copy called the verdict rule
pre-registered; its own notes said the rule was settled after the scout's
n=192 result was seen — and full N is the same 191 buildings. The critic
caught it. The page now says the rule is stated in full with its constants
in the payload and a test re-derives the verdict; it explicitly does not
claim pre-registration. Keep that honesty when the next rule is written.

**A space is a space.** 車位面積 is an allocated basement share (one bay
records 41.73 m²), so the parking block has no area column and a test greps
every key and string for 坪/ping/area. Market rung **2.00% [1.95, 2.11] on
280 buildings** at ±4 quarters; the scout's 452 was an unbounded match and
the median does not move with the window. The social-admitted rung (2,313)
is shown only on a published rule (`wide_licensed`: within-building
social/market space-rent ratio within 0.10 of 1 on ≥100 buildings — 1.000,
n=141) with the mechanism named as a hypothesis. The 機械 > 平面 gap is
labelled a hypothesis too, and printed whichever way it points.

**Design-pass corrections worth keeping.** Eight must-fixes: the two specs
double-loaded the park sub-files (one `_park_totals` now returns count and
type — that step was proven to move nothing by an accidental build that
diffed from v1.9 by the stamp alone); a type-cell test asserted a sum bound
the spec's own numbers violated (a building can sit in two type cells); the
unit test grepped every `pk*` key and would have failed on the sibling's
`pka*` strings that legitimately say 每坪 for dwellings; "1.10" chosen by
both specs where the plan said 2.0; the wide-rung licence had no test; the
"holds" arm mixed a share-relative band with a typed 0.98.

**Caught in the browser, not by tests.** English "rents more 14.7%" — the
direction word and the number were separate placeholders in Chinese order;
now one language-aware token. And both new horizontal charts had labels on
both sides, so `chartW()` left a 49-px plot at 375 px — natural width,
panning, like the column charts. That rule now reads: chartW for bars
labelled at ONE end only.

**Gates:** 878 tests (12 new), 546 STR entries with matching arity, PARSE OK,
0 overflow at 375 px both modes both languages, rebuild diff exactly
`parking, parking_audit, buildings[*].ri, meta`, the JS impute waterfall row
(1.73%) equals the Python bound (1.734), `as_now` equals the headline to four
decimals, PDF v2.0 carries both rows.

**Tally:** 13 workflow runs.

## 28 · 2026-09-18 — v2.1: the headline moves, 2.68% → 2.55%

Stanley's call after §27: the imputed treatment becomes the default. First
time the headline number has moved for a *method* reason since v1.0 (every
earlier move was scope or a withdrawn claim). How it was done, so the next
one is done the same way:

- **In the pipeline, not beside it.** `impute_parking_rent` runs in `build()`
  right after `key_frames`, and the honesty ladder gained a last rung,
  `park_impute`, with the same flag — so the rung IS the headline's code
  path and the ladder draws the step (`building` 2.68 → `park_impute` 2.55).
  The test that pins the ladder's end to the headline now names that rung.
- **The old number is a bound, not a memory.** `parking_audit` names
  `headline_case: impute` and `previous_headline_case: area_only`; the old
  treatment keeps its CI, `buildings[].ro` carries each building's rent under
  it, and the net waterfall's live row reproduces the old 1.84% from the JS
  twin. Every string that said "headline untouched" now says which version
  used which treatment. The audit's within-building tests still run on the
  pre-imputation frame, or they would be testing their own correction.
- **Everything downstream recomputed** — districts, map, histograms,
  post-stratification, the dead hypothesis, the management-fee bounds (its
  flag-only bound is 1.88 now). No prose anywhere hard-coded the old number;
  the v1.1/1.2 audits that made every figure payload-derived are what made
  this a one-build change.
- **The imputation is an estimate.** The page says so in the limits bullet
  and the method text. The registry never states these rents; the number is
  the same building's itemised median, else the county's, else the country's.

**Gates:** 878 tests, PDF v2.1, hero/ladder/audit/waterfall/limits all read
2.55 / 1.73 with 2.68 / 1.84 visible as the old bound, 0 `undefined`.

## 29 · 2026-09-20 — a reviewer's three points, and the one that flipped a verdict

A reviewer sent three: the vacancy assumption is the softest number on the
page; bounding the 94% the site cannot see is the natural ending of its own
argument; and the walk-up hypothesis should be killed or resolved, because at
1.55% matchability the honest answer may be that the data cannot answer it.
Three specs and a critic. Verdict: **ship the walk-up work now (this section,
v2.2), ship the bounds next, defer the vacancy prior.** Why, and what it cost:

**The walk-up hypothesis is closed as UNANSWERABLE, and the reason is a
must-fix.** The spec computed representativeness for walk-ups only (3.9% max
deviation from walk-ups that sold and did not match) and concluded
`resolved_walkups_higher`. The critic demanded the tower side too. It is
**18.0%** — matched towers are 34.8坪 against 42.5坪 for towers that sold and
did not match. Two separately-skewed samples cannot settle a population
question, and the rule said so the moment the second number existed. The
verdict flipped on a number the spec had not computed. **Compute both sides
of any comparison before writing its verdict.**

**What IS settled, and it is the better result.** The mechanism the project
named is falsified. A manager is recorded for 97.3% of towers and 6.1% of
walk-ups, so the fee variable is very nearly the type indicator — and yet in
buildings with no manager on either side (711 vs 186), where the modelled fee
is exactly zero, the gap is still +0.45pp [0.23, 0.55]. The gap does not need
the fee. The project's founding explanation dies on the project's own data.

**The type map was read two ways.** `coverage_block` took its denominator
from the universe frame and its numerator from the matched frame — two modal
建物型態 maps, disagreeing on 6 of 9,805 buildings, so those six sat under one
type in the numerator and another in the denominator. Single-sourced from the
universe frame (which sees every sale a building ever had). 公寓 1.55 → 1.54,
華廈 4.68 → 4.69, 住宅大樓 unchanged, every type yield identical to 4dp. The
old rates ship as `match_rate_pre_v22`. **A rate whose numerator and
denominator come from different frames is not a rate.**

**Two header bugs in the government's own files.** The transfer series word
their total and mean columns differently from the stock series, so both
melted in as bands: `xfer_by_age` 115Q2 全國 summed to 43,056 against a true
21,512. And the by-size series carries a typo in MOI's own header —
住宅平圴面積, 圴 for 均 — which leaked the mean area in as an eighth band.
Both fixed, all six series assert-sum to their own total. Normalising the
mean label to `mean` then broke `moi_block`, which read `mean_age`: caught by
an existing test, one line, one rebuild.

**Still open, with the reasons:**
- *Bounds on the unseen 94%* — the sharp bound reproduces exactly (gross
  [1.75, 4.18], net [1.06, 3.21] on 30 cells) and the rung-1 result is
  quotable: with coverage 6.22% against a structural ceiling of 24.0%, a
  median's worst-case bound sits at the support endpoints and no better
  cleaning can change that. Two fixes first: rung 1 is NOT assumption-free
  (it rests on YIELD_BAND, the site's own choice), and the 5–95 trim that
  does 7.05pp of the narrowing is a *resemblance* assumption, not a support
  one. Drop the 宅→棟 scope entirely — it is 'one building in 1,086' wearing
  a different hat, for a measured payoff of 0.007pp.
- *Vacancy prior* — the banded low-use rates exist only inside a half-yearly
  PDF booklet; no machine-readable table exists anywhere (settled by fetch).
  Worse, the pinned edition puts the under-5 band at 22.91% while the press
  release for the next one says 12.39%. Publishing a composition-weighted
  11.60% now risks shipping a number the next edition halves. The reviewer is
  right that 5% is too generous for a matched set that is new and small — the
  matched composition is 25.2% under-5 against 7.1% of the stock, and 40.7%
  under-25坪 against 30.5% — but the number has to wait for the booklet.

**Gates:** 203 housing tests (6 new), 589 STR entries with matching arity,
rebuild diff exactly the type map's footprint plus `walkup_resolution` and
meta, headline unchanged at 2.5472 / 1.734.

**Tally:** 14 workflow runs. This one earned its keep twice: the tower-side
must-fix flipped a verdict, and the critic caught that a spec's three
self-declared blockers included one that did not exist.

---

## 30 · 2026-09-20 — v2.3: the coverage caveat becomes a result

The reviewer's second point, shipped. Every number on the page before this was
a median of the 9,805 buildings the site can match; dropping the other 147,789
silently assumes they resemble the ones on file. `partial_id` refuses that and
bounds them instead, so **"we can only see 6.22%" becomes "under these named
assumptions the median lies in [1.90, 4.26], and here is why it cannot be
narrower."** That sentence is the point of the whole section.

**The method, in one paragraph.** Partition the 157,594 buildings with a
recorded sale into cells (type; then type × price-per-ping decile; then ×
age band). Inside a cell, the matched buildings enter the weighting at
`share × p_observed` and a single atom at the cell's assumed floor or ceiling
enters at `share × (1 − p)`. The bound is the weighted median of that mixture,
which is **sharp** for the assumption named on its rung — not conservative,
not approximate. Everything is in 棟 on the site's own population.

**The ladder as published** (gross, 棟, 157,594 buildings):

| rung | interval | buys |
|---|---|---|
| the site's own quality band | [0.30, 12.00] | — |
| unmatched inside their type's observed min–max | [0.59, 11.63] | 0.66pp |
| inside their type's 5th–95th percentile | [1.55, 5.54] | **7.05pp** |
| **+ their own price decile (headline, 30 cells)** | **[1.90, 4.26]** gross, [1.11, 3.22] net | 1.62pp |
| + their own age band (144 cells) | [1.79, 4.26] | **−0.10pp, wider** |

**Three things are published because they constrain the reading, not because
they flatter it.**

1. *The trim is a resemblance assumption, not a support one.* "Inside the
   5th–95th percentile" forbids any unmatched building from sitting in its own
   type's top 5% — strictly stronger than "distributed like the matched ones".
   It does 7.05pp of the narrowing, the largest step on the ladder, so the
   untrimmed rung stays drawn beside it and the bill is visible.
2. *The age rung fails, and is published failing.* Thinner cells leave 75 of
   144 holding fewer than 25 matched buildings, so 21,453 buildings fall back
   to the weaker type-level assumption and the interval **lengthens**.
   Conditioning on more does not always identify more.
3. *The residual selection is published unsigned.* Matched buildings are 8.5%
   dearer per ping and yield falls monotonically across all ten price deciles
   (unmatched higher, [2.55, 4.26]); but matching needs a sale *and* a lease
   within four quarters, which selects liquid investor stock (unmatched lower,
   [1.90, 2.55]). And the first argument **cannot be used as an assumption at
   all**, because price decile is already conditioned on in the rung above.
   Both ladders ship; neither is signed.

**The rung-1 result is the quotable one.** A median's worst-case interval only
leaves the support band once more than half the population is observed. This
site sees 6.22%; with all five of its own filters removed the registry's
structural ceiling is 24.0% — less than half. **No amount of better cleaning
moves rung 1.** That is a fact about the registry, not a disclaimer about the
site.

Turned on 公寓 alone (1.54% matchable) the interval is [1.55, 5.78], width
4.23pp — wide enough to swallow whole the +0.50pp type gap of §29. Partial
identification does not rescue the dead hypothesis; it prices how far from
rescue it is.

**Scope discipline, which is where this section could most easily have gone
wrong.** No rung says "Taiwan": 1–3 storey 透天 are 42.7% of the dwelling stock
and the filters exclude them by construction, so there is not one observation
there to bound. And the house-tax **宅** shares are *not* converted into **棟**
weights — a tower holds dozens of dwellings and a walk-up a handful, which is
"one building in 1,086" (§17) wearing a different hat. It was computed before
being dropped: worth **0.007pp**.

### Bugs found while building it

- **`build_cells` closed over `B`**, so every bootstrap draw rebuilt the cells
  from the full frame and the endpoint CI was measuring nothing. Fixed with an
  explicit `B=None` parameter. *A closure over the thing you are resampling is
  a resampling that does not happen.*
- **`_pid_bound` skipped cells with no matched buildings entirely.** Their mass
  vanished from the weighting, so the bound described a different population
  than the one named. Now a thin cell contributes nothing observed and puts its
  **whole** share on the weaker assumption. The fix made `type_price_age`
  *wider* by 0.10pp — which is exactly what the spec predicted, and is why that
  rung is worth publishing.
- **Two Chinese strings had the right `%s` count in the wrong order.**
  `pidAgeWarn` rendered "75 個格子裡有 144 個"; `pidFigS` consumed (matched,
  median) where the call passes (median, matched). The arity checker compares
  placeholder *counts* between languages and passes both. **Only reading the
  rendered page in both languages finds this class.** Add it to the pre-commit
  read, alongside the overflow check.
- **The chart falls back to the payload key when a label is missing**, so the
  two MTS rows shipped to the rendered page as literal `↑ mts_up` and
  `↓ mts_down` — in both languages — and every automated gate passed. Caught by
  reading the page at 375px. A missing translation should fail loudly; since
  this one cannot, a test now asserts every rung and MTS key has a
  `pidR_<key>` entry in both languages and that neither equals the key.
- **The ladder's rung labels collided with its low-end value labels.** A left
  gutter wide enough for the longest sentence in either language leaves the
  bars no room. Structural fix: the label sits **above** its bar, not beside
  it, and the chart keeps its natural width inside `.hs-scroll`.

**Gates:** 893 tests (8 new), rebuild diff exactly `partial_id, meta` —
additive, nothing moved — headline unchanged at 2.5472 / 1.7340, both languages
read at 375px with `overflowPx: 0` and no undefined strings. The PDF gains
section 三 and one sentence in each abstract; its old 三–七 renumber to 四–八.

**Still open:** the vacancy prior, for the reason in §29 — the banded low-use
rates exist only inside a half-yearly PDF booklet, and the pinned edition puts
the under-5 band at 22.91% where the press release for the next says 12.39%.
The reviewer's point stands (the matched set is 25.2% under-5 against 7.1% of
the stock, and 40.7% under-25坪 against 30.5%), but the number waits for the
booklet.

---

## 31 · 2026-09-20 — v2.4: the vacancy guess gets a measured shape

The reviewer's first point, shipped — and §29 deferred it for a reason that
turned out to be **wrong about where the data lives**, not wrong about the
data. §29 said the banded rates exist only inside a half-yearly PDF booklet.
They also exist as an **.ods spreadsheet**, and the Internet Archive has it.

**What vacancy was.** Of the four cost terms in the net yield, tax has a
literature, the management fee has a two-city survey, repairs are age-weighted
— and vacancy was a flat **5%** with no source, charged identically to a
two-year-old tower in 臺北市 and a forty-year-old walk-up in 臺東縣. Taiwan
publishes no rental-vacancy statistic, so the **level** still cannot be
sourced. The **shape** can, and the shape is where a flat rate does its damage:
every cross-section on this page was computed with the same number charged to
buildings whose void risk is not the same.

### The two sources, and how each was reconciled before use

**表2-3-2 低度使用(用電)住宅半年報表-按屋齡分** — the low-use rate for every
county **crossed with** seven age bands. A JOINT table, so nothing assumes
county and age are independent. It lives on `pip.moi.gov.tw`, which times out
from this machine (as do `segis`, `stat-moibd`, `data.moi`, `ws.moi`, and
github), and `r.jina.ai` gets an F5 "Request Rejected" from MOI's WAF. Only the
**111H1 and 111H2** editions are archived, so the **Wayback snapshot is the
pin**: fetched in `id_` form (original bytes, no banner), hashed, with its
timestamp in `data/ref/moi/MANIFEST.json`.
*Check:* weighting its national band rates by the house-tax roll's own age mix
at 111Q2 reproduces the published 111H1 national rate to **9.68% against
9.52%** — the residual is the roll's ten bands folding into the table's seven.

**All 22 counties instead of six.** 經濟部能源署 republishes 內政部's low-use
counts for every county, because it needs them to derive bottled-gas households
(房屋稅籍 − 天然氣用戶 − 低度使用). One plain CSV, no key, on a reachable host.
*Checks, all three passed before a line of it was used:* its 低度使用 column
equals 內政部's **上半年** figure exactly for every overlapping county and year
(112, 113, 114 — 114 臺北市 is 65,717 both ways); its 房屋稅籍住宅數 column
equals this repo's `resi_tax_roll` to the unit; and summed over all 22 counties
against the Q2 roll it reproduces the published **114H1 national 10.43%**
exactly. Its own derived column pairs an H1 numerator with a Q4 denominator, so
that column is never read. Coverage of the matched set: 91% → **100%**.

### The finding, and why the second leg is published

| leg | matched set | national | gap |
|---|---|---|---|
| county only (114H1, 22 counties) | 9.61% | 10.43% | **−0.82pp** |
| **county × age joint (111H1)** | **11.53%** [11.40, 11.68] | **9.52%** | **+2.01pp** |
| same, other archived half (111H2) | 10.40% | 8.77% | +1.63pp |

**The two legs point opposite ways.** County alone says the visible slice looks
*fuller*, because it is metropolitan. Age says it is markedly *emptier*. The
joint table holds both at once and the answer is emptier — so the county leg
ships beside it, because publishing only the leg that agrees with the
conclusion would be advertising.

The mechanism is the profile, and it is a U: dwellings under five are **21.91%**
low-use, the highest cell in the country, and **25.04%** of matched buildings
sit there against **7.11%** of the national stock. At the other tail, 50-plus is
14.92% and the matched set holds 1.42% of it against 16.05%. The sample is
stacked on the left arm of the U — the end where a flat vacancy rate flatters
the yield most. **The reviewer was right, and now it is measured.**

### What was NOT adopted, and why

低度使用 is an empty-home rate: its numerator counts second homes, homes for
sale and homes between owners, and its denominator is every dwelling on the
house-tax roll, not the rented ones. Charging it as a landlord's void would
answer one population's question with another population's number. So the
headline is untouched and three cases ship:

- **flat 5%** — the headline, still **1.7340%**
- **shaped** — the 5% level, the measured relative structure: 1.7277%,
  **−0.0063pp**. Near-zero *by construction*, because the shape is normalised
  on the matched set. What moves is the cross-section, not the headline.
- **level** — charging the rate outright: **1.5514%, −0.1826pp**. A bound.

A per-building `vs` multiplier ships in `buildings[]`, and an opt-in toggle
recomputes the whole page with it. The JS twin applies `vs` **only** in that
mode, so the default still reproduces `underwrite.py` term for term — the
existing twin test was updated rather than relaxed, and it caught the change.

The walk-up-minus-tower net gap survives all three cases (0.64 / 0.70 / 0.74pp).
That is a robustness check on §29's type gap, not a new finding.

### The negative result, published because it was checked

No 114 banded table is reachable on any open channel. Across all **52,422**
data.gov.tw datasets the string 低度使用 appears **exactly once**, with no
breakdown; the 內政統計通報 series carries county and township totals only (the
114H2 release was read in full through a text proxy — 面積 0 hits, 屋齡 1 hit
and it is the 待售新成屋 footnote); and the **20坪** size bands the reviewer
quoted exist solely inside a 108年 commissioned report which states in its own
notes that the per-band denominators are **grossed up from a match rate**, not
counted. A 108-vintage size leg was therefore NOT spliced in. The reviewer's
exact figures (16.77 / 12.39 / 12.59) were never located in any reachable
source, and no number resembling them was published as if it had been.

### Bugs and lessons

- **A guard that returns `{}` on any `None` turns a data gap into a vanished
  section.** 30 of 9,805 buildings carry no 建築完成年月, so `age_band` returned
  None, so the whole block returned empty — the section would simply not have
  rendered, with no error anywhere. They now fall back to the period's national
  overall rate and are counted in `fellback_to_national`. The existing test
  would have caught it at the gate; the *build* would not.
- **A left gutter sized in Chinese clips in English.** The age-profile chart's
  right-hand "matched X% · stock Y%" label is far wider in English, and at
  padR=150 the longest bar's own value label collided with it. Found by the
  geometry check, not by looking.
- `low_use_rates()` is now single-sourced for both readers (the 內政部 section
  and this prior), per §29's rule about numerators and denominators.
- The site's own note in `vacancy_breakeven` — "the current series is
  county-level PDF only" — was **stale**, and believing it is what deferred
  this feature in §29. Re-check a "no data exists" note before trusting it.

**Gates:** 903 tests (10 new), headline unchanged at 2.5472 / 1.7340, both
languages at 375px with zero overflow, zero clipped or overlapping SVG labels
and no undefined strings, PDF re-rendered at v2.4 with a new subsection under
成本假設.


---

## 32 · 2026-09-21 — v2.5: chasing a bug that was not there, and what it taught

Worth writing down because the mistake is more instructive than the release.

**The false alarm.** Auditing v2.4, I extracted `netYield()` from housing.js and
ran it under `jsc` against the real payload — a check worth having, because the
existing twin test compares the two implementations as TEXT and is blind to any
divergence that lives in the data. It printed:

```
js_flat   1.7340631   py_flat   1.7340    diff 6.3e-5
js_shaped 1.7275310   py_shaped 1.7277    diff 1.7e-4
```

I read the shaped gap as a defect — the shape multipliers were rounded to 4dp
on the way into `buildings[].vs` while the published case was computed from the
unrounded ones — wrote the fix, wrote a test with a 1e-4 tolerance that failed
on the shipped payload, bumped the version, and rebuilt.

**The rebuild proved it wrong.** Diffing the v2.5 payload against v2.4 gives
FOUR changed paths: three meta stamps and `cases[shape].vacancy_min_pct`
(1.7090 → 1.7080). Every published net is byte-identical. The fix was real
hygiene and fixed nothing, because the gap has a different cause.

**The actual cause, which is not fixable and not a bug.** `underwrite.py` takes
its medians over full-precision frame values; `buildings[]` ships rent and price
rounded to the NT$ and area to 0.1坪. No recomputation from the payload can land
on a median taken over the unrounded frame. That floor is ~6.3e-5pp on the flat
case. It is ~1.7e-4pp on the shaped case because charging a different vacancy
per building changes WHICH buildings sit at the median, so the same rounding
noise lands differently — a ratio, not a discrepancy. Both sit two orders of
magnitude below the 2dp anything is published at.

**What survives, and is worth keeping.**
- The `jsc`-against-the-payload check itself. It is the only way to test the JS
  twin numerically without a browser, and it belongs in the toolkit even though
  its first finding was a false positive.
- The test, retargeted: every published net case must recompute from the
  payload's own fields to the **displayed 2dp**, and stay inside 5e-4pp. That
  documents the floor instead of pretending it is zero, and would still catch a
  divergence that mattered.
- `_county_only_leg` now pairs its half-year with the roll by the shared
  H1→Q2 / H2→Q4 rule instead of hard-coding Q2.

**The lesson, stated plainly because it cost a rebuild and a wrong claim:**
*a gap between two numbers is not a bug until you have shown what produces it.*
I had two candidate explanations — shape rounding and per-building field
rounding — and tested neither before acting on the first. The five-minute check
that would have settled it: recompute the flat case's gap, notice it is the
same phenomenon at a smaller size, and conclude the floor is structural. The
version bump stands rather than being unwound, because v2.4 is already pushed
and a reader who cites it must not find it saying something else.

**Gates:** 904 tests (1 new), headline unchanged at 2.5472 / 1.7340, payload
diff against v2.4 is exactly three meta stamps plus one `vacancy_min_pct`.

---

## 33 · 2026-09-24/26 — the site audit, and the finding it was published at a third of its size

Ten dimensions (prose-vs-payload, arithmetic, units, strings, twins, claims,
provenance, tests, render, data-cleaning), each read by an independent agent.
Seven ran; render and data-cleaning never survived a rate limit. Their verifier
agents died too, so **every finding below was re-derived by hand before
anything changed** — and two were thrown out that way.

### The one that mattered

`age_block` compares matched buildings against unmatched ones. It was still
reading the CLEANED sale frame: `coverage_block` moved to the universe in v2.2
and this did not, and its `ub=None` parameter was never read, which made the
wrong call look considered.

| | published | measured |
|---|---|---|
| unmatched buildings | 100,800 | **147,789** |
| price per ping, matched vs not | **2.7%** | **8.5%** |
| matched area | 27.27坪 | 31.57坪 |

The page therefore stated 147,789 unmatched buildings in one section and
compared 100,800 of them in another. The cleaned frame drops exactly the
cheaper stock — un-itemised parking, related-party — so **the selection effect
the entire page rests on shipped at a third of its real size**, for two
versions, with no test pinning it. There is one now: `age.unmatched_n` must
equal universe − matched.

**And the number that was right.** `pidMts` had 8.5% typed into it since v2.3,
which was correct while the computed block next to it said 2.7%. Both now come
from one computation. *A number typed in twice is a number that will disagree
with itself* — and the typed one won.

### Placeholder slots: the class is now five deep

`Sf` substitutes positionally. Four sentences printed a count as a percentage:

- `wuCov` EN — "757 walk-up buildings, **9,805%** of its **7.72**"
- `pidMid` EN — "this site has one -- **9,805%**, the median of its **2.55**"
- `mgfTrend` EN — "From **112Q4%** in **34.5** to **115Q1%** in **41.5**"
- `pkaExpo` **ZH**, the default language — "of **21,333** cleaned leases,
  **66,747** of them (32.0%)", a part three times its own whole

The new token-stream test catches the first three. **It cannot catch the
fourth**: `pkaExpo`'s two languages have an identical `%s`/`%%` stream and
differ only in which slot means the part and which the whole. That sub-class is
findable only by reading the rendered sentence in both languages, which is now
the last line of the pre-commit read.

### Twin drift

- The county CI note sorted by interval midpoint; its chart is drawn in median
  order. It printed "10 of 13" and named 高雄市／臺南市 as separating with 基隆市
  between them. The code's own comment said 11 of 13.
- `walkupControls()` cut price deciles over the 7,700 two-type buildings where
  `underwrite.py` cuts over all 9,805 then restricts — **25.8%** of buildings
  landed in a different decile, so the page and the payload gave two answers
  for one named control.
- Cost sliders refreshed three surfaces; the mortgage and benchmark tiles kept
  the published net. Now a debounced full re-render.
- The waterfall's rows are independent medians and do not sum to its total
  (1.76 against 1.73) while its comment claimed they did.

### The PDF was the worst surface, and nothing tested it

`tests/test_housing.py` asserted only that it returns 200 and starts with
`%PDF-`. Every prose figure in a 786-line generator was unasserted, and five
were wrong:

- New Taipei MRT spreads typed at v1.3: 0.58/0.02 against a measured 0.38/0.08
- the pre-sale furthest-lag residual the site had **explicitly withdrawn**
- `dead_hypothesis` ("alive") rendered without `walkup_resolution`, asserting
  as a live national finding the hypothesis v2.2 closed as unanswerable
- a rent-per-floor slope of 0.12% against the payload's 0.11%
- 113Q4 named for a presale figure that belongs to 114Q3

All now derived from the payload. **Open:** two PDFs with different numbers can
still carry an identical version stamp, because the stamp identifies the
payload, not the PDF.

### Provenance

The **金拍 session cache is pinned**. 436 JSONs from a live feed drove the whole
`auction` block and two MOI ratios; `source_manifest` covers the season zips
and `ref_manifest` globs `*.csv`, so the one input that cannot be re-fetched to
the same state was also the one nobody could check. One set digest — per-file
digests in sorted order, then a digest over those — verified against disk by a
test that tolerates the directory's absence, since it is gitignored.

Also: the 8.77% vacancy citation is dated (111H2, and the page publishes three
other periods); `countyLowUsePct` knew six municipalities and rendered
「花蓮縣 is ?%」; the volume horizon claimed out-of-window rows arrive "three or
more seasons later" when 89% are one season late.

### Two findings thrown out, and one of my own calls reversed

The income sentence looked like it had flipped sign. It had not. Its per-ping
gap is **matched-vs-unmatched** (+8.5%) and its ratio is
**matched-vs-universe** (−4.7%, NT$9,990,000 against NT$10,480,000, 13.7 years
against 14.4). Both were always right. What was real is narrower and still
worth fixing: quoting +8.5% and −7.0% and then stating −4.7% invites the reader
to multiply and get +0.9%, so the sentence was switching comparators mid-way.
It now states one and names the other's different group.

**The lesson, again:** *establish which population a number describes before
calling it wrong.* This is the second time in three days — v2.5 was a false
alarm on a rounding floor — and both times the check that would have settled it
was one line.

**Gates:** 906 tests (4 new), payload diff against v2.5 is the `age` block,
`partial_id.ppp_gap_pct`, `income.matched_*`/`universe_price`, the refs
manifest's set digest and meta.

**Still open:** the Central Bank mortgage rate is a typed constant with no
pinned source and no staleness check, while its two siblings in the same strip
are read from hashed files; and the render and data-cleaning dimensions have
never run.

---

## 34 · 2026-09-26 — the last two audit dimensions, and the audit's tally

`render` and `data-cleaning`, the two that died on a rate limit three times.
Twelve findings, eleven confirmed by hand, one rejected (a "clipped" scatter
axis label — a rotated element's `getBBox()` reports pre-transform coordinates,
so it was never off-canvas).

### The filter that was described as something else

`exclude_rooms` is a **whitelist**. It keeps 整棟(戶)出租 and 獨立套房, which
means it drops four populations, not two:

| dropped | lease records |
|---|---|
| 分租套房 | 25,974 |
| **blank 出租型態** | **5,061** |
| 分租雅房 | 1,611 |
| **分層出租** | **903** |

The coverage-waterfall step and the ladder rung both called the whole drop
「租約是分租套房／雅房」 / "Lease is a room-share". **5,964 records were attributed
to a category they are not in.** The filter is defensible — a blank type cannot
be verified as a whole-unit let, and a 分層出租's area is not comparable — but
the label was not. *A filter's NAME is a published claim.*

Same class, same commit: the waterfall's `window` step takes its `to` from
`match_pairs`, which applies the ±4-quarter window **and** the 0.3–12% yield
band, so the band's losses shipped under the window's name.

### Four charts, and what made each one wrong

- **Eight labels invisible in light mode.** The coverage columns are HATCHES —
  the pattern's only ink is a stroke on transparent, so 69–79% of each segment
  is bare page — and the share labels were hard-coded `#fff`. On `#f7f5ee`
  that is **1.09:1**. Dark mode is 17.4:1, which is why it survived: *a
  hard-coded colour is only ever right in one theme.*
- **The pre-sale chart contradicted its own caption.** The series changes sign
  (+5.4 → −7.5); `Math.abs()` from a single origin with no zero axis made
  −7.5% the **longest bar on the canvas**, pointing the same way as +5.4%,
  under a sentence saying the gap "shrinks all the way to negative". The
  sibling chart `secWalkup` already drew signs correctly, so this broke the
  page's own grammar.
- **The default view promised sliders it does not render.** The hero says
  "adjustable below"; `secNet()` renders only in advanced mode. Measured in
  simple mode: 0 range inputs, no reset button, no waterfall.
- **Left-gutter labels clipped in both languages.** Worst on the dispersion
  chart, where the series names are the only thing identifying each bar and
  started at x=−68 in a 295-wide canvas. English clips where Chinese does not —
  Latin text is roughly twice as wide per character — and the volume panels
  clipped at EVERY width including desktop, because their `padL` is a fixed 118.

One shared `rowLabel()` now puts a label above its bar when the gutter cannot
hold it, the pattern the partial-identification ladder already used. Chinese is
clean; English has one 3-unit hairline left.

### The audit, end to end

| | |
|---|---|
| dimensions | 10 planned, 10 run |
| findings raised | 41 |
| confirmed and fixed | 35 |
| rejected on verification | 6 |
| payload versions | 2.6, 2.7 |

**Every verifier agent died on a rate limit**, in all four batches, so every
finding was re-derived by hand. That is what caught the six rejections — and
two of those were my own calls, reported to the user before I checked them
(§32's rounding floor, §33's income "sign flip"). *The verification pass is not
optional even when the finder is careful; when the verifiers cannot run, the
parent does it, and it will find things.*

**Gates:** 909 tests, payload diff against v2.6 is
`coverage_waterfall.steps[*].zh/en`, `ladder[*].zh/en` and meta — labels only.

### Left open, deliberately

- **Two data-cleaning findings are unverified**, because neither is visible in
  the payload: `normalize_addr._fold` does not fold **巿 (U+5DFF)** to 市, which
  is claimed to strand 688 sale keys (5,700 of them 屏東巿) from their own
  leases; and `addr_key` cuts at the LAST 號 on the assumption that a unit
  designator never contains one, which is claimed false for 320 keys. Both
  affect buildings that never become matched, so checking them needs a full
  window load, not a payload read. If real, both make coverage look WORSE than
  it is, not better.
- The scatter's rotated axis label is a false positive; leave it.

---

## 35 · 2026-09-26 — the join key, and the bug it woke up

The two address findings §34 left open. Both real, both far smaller than
claimed, and fixing them exposed something that had been latent for a while.

### What was wrong

`addr_key` is the load-bearing function here — two records are the same
building **iff** their keys are equal — and its own module docstring stated two
assumptions the registry falsifies.

**NFKC does not merge 巿 (U+5DFF) with 市 (U+5E02).** They are separate CJK
ideographs, so 屏東**巿**公裕街242號 and 屏東**市**公裕街242號 were different
buildings. Measured: **3,456 sale rows** carry the variant, 3,452 of them in
county t, and **ZERO lease rows** do. The damage is one-sided — a sale spelled
巿 could never find its own lease.

**"A unit designator never contains 號" is false**, in two ways:

| pattern | example | old key |
|---|---|---|
| the flat's own number | 146號**五樓1號** | the flat |
| a second 門牌 on one record | 296號十二樓**、298號十二樓** | both buildings at once |

343 distinct keys. The cut is now made at the first 號 **followed by** a unit
designator, and a second 門牌 after a separator is dropped.

**The two fixes broke each other.** The separator split ran before the range
collapse, so 「和平東路2段5、7號」 — where 、 marks a RANGE of house numbers, not
a second address — lost its 號 entirely and returned an empty key. The existing
fixture test caught it within a minute. Ordering matters: ranges collapse
first.

### The dry run, which is why this was safe to ship

`addr_key` runs on every record, so a rule that fires wider than intended
reshapes the whole site silently. Before committing:

- **3,844 of 574,803 rows change key (0.67%)**
- 192 sale keys and 57 lease keys merge
- every sampled example keys a *building* where it used to key a flat or a pair

**Coverage moves UP** — matched 9,805 → 9,843, universe 157,594 → 157,407,
6.22% → 6.25%. `universe_buildings` says in its own comment that coverage must
never move up by accident. It moves here deliberately, and this row says so.

### The latent bug it woke up

The hero recomputes the net yield live from `buildings[]`, which ships rounded
fields. That normally leaves the page's twin ~1e-4 from the payload's median —
invisible. The new building set moved the median onto a 2dp boundary, and the
page displayed **1.74%** beside a payload, a PDF and a prose paragraph all
saying **1.73%**.

Diagnosed rather than tolerated:

| field | rounding | relative error |
|---|---|---|
| **area** | 0.1坪 on ~30坪 | **0.17%** |
| rent | NT$1 on ~21,000 | 0.002% |
| price | NT$1 on ~9,960,000 | 0.000005% |

Area dominates by ~70× because it drives the management-fee term.
`buildings[].ar` now ships at **2dp**: the twin gap falls 6.8e-4 → **4.1e-5**
and both display 1.73. Payload 4.23 MB raw, 976 KB gzipped.

**The test was corrected too.** Its bound was a hard-coded `5e-4`, but the floor
is a property of the data: the two values straddling the median are 5.3e-4
apart, so one rank swap from rounding moves the median by half that. A constant
that held at 9,805 buildings failed at 9,843. It now derives the bound from the
measured median spacing.

### Lessons

- *A payload must carry enough precision for its own twin to reproduce it.*
  The alternative — widening a tolerance — hides a divergence that a reader can
  see on screen.
- *A tolerance calibrated on one dataset is a constant pretending to be a
  measurement.* Derive it.
- **The audit's finder was right in kind and wrong in size for the fourth
  time**: it claimed 688 buildings recovered (measured: 41), 5,711 sale rows
  (3,456), 12 rent rows (0), and predicted coverage would get WORSE (it got
  better). Mechanisms from a cold reader are worth having; its quantities are
  not worth quoting.

**Gates:** 919 tests (10 new in tests/test_addr.py, pinning both corrected
assumptions and the range that must still collapse), hero and payload agree at
2dp, no 1.74% anywhere on the page.
