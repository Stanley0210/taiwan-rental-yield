# 實價收益 — the visible range of Taiwan's rental yield

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23902646.svg)](https://doi.org/10.5281/zenodo.23902646)

**Live page:** https://stanley0210.github.io/taiwan-rental-yield/
**Paper (PDF, v1.0):** [English](docs/HOUSING_FINAL_REPORT.pdf) ·
[中文版](docs/HOUSING_FINAL_REPORT_ZH.pdf) ·
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

**Why it cannot be narrowed.** A median's worst-case interval only leaves the
support band once more than half the population is observed. This registry can
never show more than ~24%. The width is a property of the registry, not of the
cleaning.

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
pip install -r requirements.txt          # pandas, numpy, reportlab, fonttools
python src/underwrite.py                 # rebuilds housing_data.json
python src/housing_final_report.py       # rebuilds the paper      -> docs/
python src/housing_final_report_zh.py    # rebuilds the 中文版     -> docs/
pytest tests/ -q                         # 265 tests
```

The two editions of the paper read the same `housing_data.json`, so they cannot
disagree about a number by accident; `tests/test_report_editions.py` asserts
that every headline figure appears in both. They are separate generators rather
than one bilingual template on purpose — a shared positional template is how
the site's own JavaScript printed a count as a percentage four times, with the
placeholder count matching and only the order wrong.


`src/` is the pipeline: `underwrite.py` builds the payload, `fetch_lvr.py`
cleans the registry, `normalize_addr.py` is the join key that decides when two
records are the same building, and `fetch_moi.py` / `fetch_cbc.py` pull the
official reference series pinned under `data/ref/`.

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

Note that the deposit version and the paper version are different things. The
archive is at v1.1 because it gained the Chinese edition of the paper; the
paper itself is still edition v1.0, as both covers say, because none of its
claims changed.

## Source and licence

Source data: 內政部不動產成交案件實際資訊資料供應系統, under
政府資料開放授權條款第 1 版. The derived payload carries the same terms.

This page describes registered transaction prices. It is not a valuation, and
it is not investment advice.
