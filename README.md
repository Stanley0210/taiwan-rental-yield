# 實價收益 — the visible range of Taiwan's rental yield

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23902646.svg)](https://doi.org/10.5281/zenodo.23902646)
[![CI](https://github.com/Stanley0210/taiwan-rental-yield/actions/workflows/ci.yml/badge.svg)](https://github.com/Stanley0210/taiwan-rental-yield/actions/workflows/ci.yml)

**Live page:** https://stanley0210.github.io/taiwan-rental-yield/
**Paper (PDF, v1.2):** [English](docs/HOUSING_FINAL_REPORT.pdf) ·
[中文版](docs/HOUSING_FINAL_REPORT_ZH.pdf) ·
**Two-page brief:** [English](docs/HOUSING_BRIEF.pdf) ·
[中文版](docs/HOUSING_BRIEF_ZH.pdf) ·
**Technical report:** [`housing_report.pdf`](housing_report.pdf) ·
**Open question:** [`docs/SOCIAL_HOUSING_NOTE.md`](docs/SOCIAL_HOUSING_NOTE.md)

A rental yield needs two facts about the *same* building: what it sold for and
what it rents for. Taiwan's 實價登錄 publishes both. For most buildings it
publishes only one.

This project pairs real sales with real leases in the same building, publishes
the yield — and publishes the denominator that shows how little of the market
that yield describes. **The denominator is the point.**

## What it found

| | |
|---|---|
| Buildings with a sale on record | 157,407 |
| …that also have a matchable lease | **9,843 (6.25%)** |
| Structural ceiling, no quality filters at all | **24.2%** |
| Median gross yield of those 9,843 | 2.55% |
| Median net, after modelled costs | 1.73% |

**Matchability is itself selective.** You can price 1 in 9 apartment towers and
1 in 65 old walk-ups — and walk-ups are 31% of the buildings that sell but 8%
of the ones you can measure. The buildings you *can* see are **8.2% dearer per
坪** and 12 years newer than the ones you cannot.

**So the single number is replaced by a range.** Assuming nothing about the
unseen 94%, the median lies in **[0.30%, 12.00%]**. Assuming they resemble seen
buildings of the same type and price decile, **[1.90%, 4.26%]**. Every
assumption in between is written down, including one rung that makes the
interval *wider* and is published because it fails.

**And that resemblance assumption is now tested, not just stated — it half
fails.** Conditioning on type and price decile absorbs **77%** of the age gap
between matched and unmatched buildings, but it makes the *size* gap **worse**,
from −0.22 to −0.53 standard deviations, with 26 of 30 cells unbalanced and
every one of the worst six in the same direction. The cells are cut on price per
坪, and 坪 is the denominator of that, so banding on the ratio frees the size
gap instead of closing it. `[1.90%, 4.26%]` is therefore a stated-assumption
interval, not a validated one. It cannot be repaired by conditioning on size as
well: at 6.25% coverage the data runs out before the conditioning does.

**Why it cannot be narrowed.** A median's worst-case interval only leaves the
support band once more than half the population is observed. This registry can
never show more than ~24%. The width is a property of the registry, not of the
cleaning.

## How it compares

The Taiwan rental yield in general circulation is **1.57%**, from a gross rent
multiplier of 64. That figure appears in the peer-reviewed literature (Chang and
Chen 2018, *International Real Estate Review*), and its stated source there is
**Global Property Guide** — a commercial listings aggregator, whose method is
median *asking* rent × 12 ÷ median *list* price. So the academic number and the
consumer-facing number are the same number, and neither is built on transaction
data. A ratio of two medians taken over different properties is also not a median
of per-property ratios; only the second is a yield a building could have earned.

Set side by side, city by city, for the five cities both cover:

| City | This paper (transacted, matched) | Global Property Guide (asking) | difference |
|---|---|---|---|
| 臺北市 Taipei | 2.08% [2.03–2.12] | 1.97% | +0.11pp |
| 新北市 New Taipei | 2.26% [2.23–2.29] | 2.19% | +0.07pp |
| 桃園市 Taoyuan | 2.56% [2.48–2.63] | 2.44% | +0.12pp |
| 高雄市 Kaohsiung | 2.91% [2.86–2.93] | 2.57% | +0.34pp |
| 臺南市 Tainan | 3.07% [2.94–3.14] | 2.12% | +0.95pp |

The registry measure is higher in all five, and the gap widens going south. This
is indicative, not like-for-like — the listings figure covers apartments inside
five city boundaries, this one covers 4+ storey residential buildings across the
whole county, and the windows differ — but the direction is the same everywhere.

Taipei has three independent estimates and they agree within about a tenth of a
point: 1.97% (listings, 2026), about 2.0% (a Taipei gross rent multiplier of ~50
from 591 asking rents against 實價登錄 sales, 2013–2016), and 2.08% here.

## Results that were withdrawn

Published on the page, not deleted:

- **The founding hypothesis is unanswerable.** Walk-ups out-yield towers by
  +0.51pp in the matched sample and the sign survives every control — but
  matched towers depart from their own population by 18.0% on median area
  against 3.8% for walk-ups. Two separately skewed samples cannot settle a
  population question. The proposed mechanism (management fees) is separately
  falsified: where no manager exists and the modelled fee is zero, the gap
  remains.
- **The transit gradient is retracted.** It survived only if 輕軌 did not count
  as a station, and vanished entirely in Kaohsiung.
- **"One building in 1,086" is withdrawn.** It divided 棟 by 建號 — two
  different units.

## Checking it

Every figure on the page is read from [`housing_data.json`](housing_data.json),
whose SHA-256 is pinned in
[`housing_data.json.sha256`](housing_data.json.sha256). The payload carries its
own provenance block: the hash of every source archive and reference file the
build read, so two people running the pipeline months apart can tell whether a
difference came from the code or from the data.

[`docs/REPRODUCING.md`](docs/REPRODUCING.md) is the version table — one row per
payload version, each stating what moved and why, including the corrections.

## Rebuilding it

```bash
pip install -r requirements-dev.txt      # the pinned runtime deps, plus pytest
python src/underwrite.py                 # rebuilds housing_data.json
python src/housing_final_report.py       # rebuilds the paper      -> docs/
python src/housing_final_report_zh.py    # rebuilds the 中文版     -> docs/
python src/housing_brief.py              # the two-page brief      -> docs/
python src/housing_brief_zh.py           # the 中文版 brief        -> docs/
pytest tests/ -q                         # 303 tests
```

All four documents read the same `housing_data.json`, so they cannot disagree
about a number by accident; `tests/test_report_editions.py` asserts that every
headline figure appears in each, that the briefs fit on two pages, and that a
brief may not quote the narrowed interval without the caveat the paper attaches
to it — which is the one shortening a summary must not make. They are separate generators rather
than one bilingual template on purpose — a shared positional template is how
the site's own JavaScript printed a count as a percentage four times, with the
placeholder count matching and only the order wrong.


`src/` is the pipeline: `underwrite.py` builds the payload, `fetch_lvr.py`
cleans the registry, `normalize_addr.py` is the join key that decides when two
records are the same building, and `fetch_moi.py` / `fetch_cbc.py` pull the
official reference series pinned under `data/ref/`.

Every version is pinned, and CI installs from those pins on a machine that has
never seen the project, verifies the published payload hash, runs the suite and
rebuilds all four documents — then checks a fresh build says the same as the
committed one. Unpinned dependencies are how a non-stable sort once produced a
payload that would not reproduce; pins nobody tests are not much better.

The season archives themselves are ~200 MB and are not committed;
`docs/REPRODUCING.md` says where to get them and how to tell a data difference
from a code difference. `bin/rebuild-housing.sh` rebuilds and compares against
the committed hash.

## Citing it

```
Jen, S. (2026). 實價收益 — the visible range of Taiwan's rental yield.
Zenodo. https://doi.org/10.5281/zenodo.23902646
```

`10.5281/zenodo.23902646` is the **concept DOI**: it always resolves to the
newest version. To cite one specific release instead, use that release's own
DOI from its Zenodo page — v1.0 is `10.5281/zenodo.23902647`.

Author ORCID: [`0009-0003-3396-106X`](https://orcid.org/0009-0003-3396-106X).
`CITATION.cff` carries it in machine-readable form, so citation tooling can
resolve the author as well as the work.

Note that the deposit version and the paper version are different things, and
they move independently:

| deposit | paper | what changed |
|---|---|---|
| 1.0 | v1.0 | first citable edition, English only |
| 1.1 | v1.0 | the archive gained the Traditional Chinese edition; no claim moved |
| 1.2 | v1.1 | references, the comparison above, a rewritten §18, payload v2.9 |
| 1.3 | v1.2 | the resemblance assumption tested and found to half fail; payload v2.10 |

## Source and licence

Source data: 內政部不動產成交案件實際資訊資料供應系統, under
政府資料開放授權條款第 1 版. The derived payload carries the same terms.

This page describes registered transaction prices. It is not a valuation, and
it is not investment advice.
