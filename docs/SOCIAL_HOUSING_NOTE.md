# A filter whose sign depends on the unit of analysis

*A short note on an unresolved result, offered as a question rather than a
finding. Figures from payload v2.8 (`housing_data.json`, SHA-256 pinned in
`housing_data.json.sha256`).*

## What was tested

Taiwan's 實價登錄 lease file marks 社會住宅包租轉租 and 社會住宅代管 — dwellings
let through the government's subsidised-tenancy scheme. These are ordinary
private buildings; only the rent leg is depressed by the subsidy.

They dominate the registered rental data:

| | records | rent, NT$/坪/yr | median area |
|---|---|---|---|
| social housing | **205,731 (82.1%)** | 627.4 | 24.9坪 |
| market lets | 44,708 | **871.1** | 23.4坪 |

The rent gap is **−28.0%**, on areas that are if anything slightly *larger*. So
removing social housing from a yield calculation should raise the measured
yield: you are deleting the cheapest rents in the file.

## What happened

It does — if you count buildings. It does the opposite if you count pairs.

Each sale can be matched to each lease in the same building, so a building with
*s* sales and *l* leases produces *s × l* pairs. Measuring the order-independent
contribution of the social-housing filter (a Shapley value over all filter
orderings, so this is not an artefact of where the step sits in a sequence):

| unit of analysis | effect of removing social housing |
|---|---|
| per **building** | **+0.179pp** — the yield rises, as expected |
| per **pair** | **−0.088pp** — the yield *falls* |

The order-dependent path shows the same inversion more strongly (−0.164pp per
pair). The two units disagree about the **sign**, not the size.

## What has been ruled out

1. **Not a misidentified filter.** Social leases are selected on the registry's
   own 出租型態 field, not inferred.
2. **Not a rent-level error.** The −28% gap is measured directly and the areas
   are comparable, so these genuinely are the cheap rents.
3. **Not order-dependence.** The Shapley value averages over every ordering of
   the filters and the sign still differs between units.
4. **Not small-n.** 205,731 social records against 44,708 market records.
5. **Not the parking or room-share filters.** Their contributions are computed
   in the same decomposition and are small and same-signed in both units
   (rooms +0.125 pair / +0.029 building; related-party −0.026 / −0.038).

## The mechanism this site assumes, and the question

Pairs are extremely unevenly distributed. Across 9,843 buildings and 143,297
pairs:

- the **median building contributes 2 pairs**
- the **largest contributes 6,988**
- the **top ten buildings hold 17.1% of all pairs**

So a pair-level median is substantially a statement about a handful of
mega-developments. The working explanation is that social-housing tenancies
concentrate in particular buildings, and removing those leases removes a large
*mass* of pairs from specific towers — changing which buildings dominate the
pair-level median by more than the rent level changes it.

This site therefore computes **every** figure per building, and treats the
pair-level number as a diagnostic only (pair-level yield 2.79% against
building-level 2.55%).

**The question I cannot answer from this data:**

> Is "use buildings, not pairs" a complete account of the inversion, or is the
> concentration of subsidised tenancies in particular buildings itself telling
> us something — about which landlords enter 包租代管, and therefore about
> whether the 82.1% of registered leases that are subsidised can be treated as
> a usable control group at all?

The second possibility matters well beyond this filter. If subsidised tenancies
are not spread evenly across the building stock, then every rental statistic
computed from this registry — not only mine — is measuring a population whose
composition is set by programme take-up rather than by the market.

## How to check any of this

`housing_data.json` → `filter_marginals.shapley` (both units),
`rent_bias` (the −28% and the 82.1%), `concentration` (the pair distribution),
and `ladder` (the order-dependent path). `docs/REPRODUCING.md` rebuilds the
payload and compares it byte for byte.
