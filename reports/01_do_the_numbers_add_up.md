# Do the numbers add up? Official waste collection figures for Lagos, 2021 to 2026

Phase 1 note. Data: `data/processed/official_stats.csv`. Analysis: `notebooks/01_official_numbers.ipynb`. Source IDs refer to `docs/sources.md`; conflict IDs to `docs/data_conflicts.md`; assumption IDs to `docs/assumptions.md`.

## Summary

Official statements put household waste generation in Lagos at 13,000 to 15,000 tonnes per day [S03, S06, S09]. In May 2026, LAWMA reported that 418,500 tonnes reached its disposal facilities [S01, S05]. Taken at face value, that figure means 90% to 104% of all waste generated in the state was collected and disposed of. The same agency stated five months earlier that PSP operators can collect 4,000 to 5,000 tonnes per day [S06]. The official figures are not consistent with each other, and the way they are produced appears to be an estimate based on truck trips rather than weighed tonnage.

## Findings

1. The May 2026 daily average does not match the monthly total. LAWMA stated 418,500 tonnes for the month and "an average daily 13,200 tonnes" [S01]. Over 31 days, 418,500 tonnes is 13,500 tonnes per day; 13,200 tonnes per day over 31 days is 409,200 tonnes (C02).

2. Reported tonnage appears to be estimated, not weighed. For the week of 28 July to 3 August 2026, LAWMA reported 18,660 tonnes from 1,866 truck trips, and for 1 August 3,490 tonnes from 349 trips [S02]. Both ratios are exactly 10.00 tonnes per trip. Weighed loads do not produce identical round ratios on separate figures, which indicates that tonnage is computed as trips multiplied by 10 [A02].

3. The May 2026 figure is 2.7 to 3.4 times stated PSP capacity. 13,500 tonnes per day compares with 4,000 to 5,000 tonnes per day that PSP operators can collect, according to LAWMA's Managing Director in December 2025 [S06], and with 4,263 to 7,020 tonnes per day collected through approved channels in 2020 to 2021 according to the World Bank (33% to 54% of 13,000 tonnes per day) [S10] (C04).

4. Reported disposal volumes fell by 80% within two months. The week of 28 July to 3 August 2026 averaged 2,666 tonnes per day at disposal facilities [S02], against 13,500 tonnes per day in May. The Commissioner for the Environment described the weekly truck count as covering movements "across disposal facilities" [S09], which indicates the same scope as the May figure (C03).

5. The May figure implies a truck volume not reported elsewhere. At 10 tonnes per trip, 13,500 tonnes per day requires about 1,350 trips per day. Reported daily trips were 850 in 2021 [S07] and 267 in the week of 28 July 2026 [S02].

6. LAWMA's approved budget nearly doubled while the reported fleet shrank. Approved expenditure was N27.2 billion in 2024 [S13], N52.2 billion in 2025 [S14] and N51.0 billion in 2026 [S15], in nominal terms [A05]. Reported compactor trucks fell from 102 in April 2025 [S04] to 77 in June 2026 [S01] (C06). Capital expenditure was 22.7% of the 2025 budget and 18.4% of the 2026 budget.

## Figures

- `reports/figures/01_daily_tonnage_vs_capacity.png`
- `reports/figures/01_truck_trips_per_day.png`
- `reports/figures/01_lawma_budget_2021_2026.png`

## Limitations

All operational figures come from official statements reported in the press; no LAWMA monthly operational series for 2021 to 2025 was located. Budget values are approved appropriations, not actual spending, and are not adjusted for inflation [A05]. No LAWMA budget line was located for 2023. Generation estimates are not based on a published measurement method [A04]. The scope of the July to August 2026 weekly figure is inferred from a ministerial statement and has not been confirmed by LAWMA.

## Implication for the study

Official tonnage figures cannot be used to measure where or how often collection fails. The resident survey (Phase 2) provides an independent measure of collection frequency, missed pickups and fees paid by LGA.
