# Defect results

The generator plants errors in each extract and lists every one in a manifest with the outcome Silver should give it. This page puts the manifest's counts for seed 2026 next to what the dq tables in lh_silver recorded for each extract's latest run.

| Extract | Planted | Expected fixed | Fixed | Expected removed | Removed | Expected quarantined | Quarantined |
|---|---|---|---|---|---|---|---|
| 2026-10-25 | 312 | 95 | 95 | 110 | 110 | 107 | 107 |
| 2026-11-01 | 14 | 5 | 5 | 4 | 4 | 5 | 5 |
| 2026-11-08 | 14 | 5 | 5 | 4 | 4 | 5 | 5 |
| 2026-11-15 | 14 | 5 | 5 | 4 | 4 | 5 | 5 |
| Total | 354 | 110 | 110 | 122 | 122 | 122 | 122 |

## Where the numbers come from

- **Planted and expected:** `manifests/<extract date>/defects.csv`, written by `python -m extract_generator --seed 2026`. Planted counts the lines with expected_outcome CORRECTED, REMOVED or QUARANTINED, and expected fixed is the CORRECTED lines. `test_seed_2026_plants_354_row_defects_across_the_four_good_extracts` in [tests/test_defects.py](../tests/test_defects.py) asserts these counts.
- **Fixed:** the sum of rows_failed in dq.rule_results where action is fixed.
- **Removed:** the sum of duplicates_removed in dq.reconciliation over clients, episodes, interventions and reviews.
- **Quarantined:** the sum of quarantined in dq.reconciliation over the same four tables. It equals the 122 rows in dq.quarantine.
- **Runs:** each extract's latest run: 20261125T034214Z, 20261125T035139Z, 20261125T043701Z and 20261125T064046Z. Read on 27 November 2026 through the lh_silver SQL analytics endpoint. Gold's fact_extract_load and the report's Data quality page use the same runs.

## Notes

- 2026-11-08 also re-sends five reviews unchanged. The manifest lists them as UNCHANGED, not as defects.
- 2026-11-22 is the broken extract. Its one manifest line is the missing end_date column, expected LOAD_FAILED. It fails in Bronze, so it has no rows in the dq tables.
- The earlier runs of 2026-11-08 and 2026-11-15 recorded the same fixed, removed and quarantined counts. Each rerun inserted and updated no rows.
- The table compares counts per extract and outcome. It does not match each planted error to its own row.
