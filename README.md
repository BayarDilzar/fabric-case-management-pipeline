# Treatment case management pipeline in Microsoft Fabric

This is a Microsoft Fabric pipeline for a fictional drug and alcohol treatment provider. Each week it takes the export from the provider's case management system, checks it row by row and feeds a Power BI report. The data is synthetic with errors planted on purpose, and the project proves every one is caught and no row goes missing.

![Power BI service overview page](docs/images/10-report-service-overview.png)

The Service overview page, all synthetic data.

## At a glance

- 354 errors were planted across four extracts: 312 in the historical one and 14 in each weekly one. In every extract the dq tables count the same fixes, removals and quarantines as the answer key. The [defect results](docs/defect-results.md) set them side by side.
- Every load reconciles, table by table, or the run fails.
- Loading the same week twice inserts and updates nothing.
- An extract with a missing column fails before anything's written. It's retried on the next run, never skipped.
- People in treatment by service on the report match a separate SQL query over Gold.
- Tests cover the generator and the SQL view files.

## How the data flows

```mermaid
flowchart LR
    gen["Python generator<br>synthetic CSV extracts"] --> land["Landing<br>files in lh_bronze"]
    land --> bronze["Bronze<br>raw, all text"]
    bronze --> silver["Silver<br>cleaned and checked"]
    silver --> dq["dq schema<br>quarantined rows and load counts"]
    silver --> gold["Gold<br>star schema"]
    dq --> gold
    gold --> model["Semantic model<br>Direct Lake"]
    model --> report["Power BI report"]
```

### The data

None of it's real. A Python generator in `extract_generator/` stands in for the case management system and writes a historical extract, three weekly ones and one that's broken on purpose. It plants the mistakes real exports have, like duplicates, day-first dates, lower-case codes and orphan rows, and records each one with its expected outcome in a manifest. That manifest is the answer key.

### Bronze

nb_load_bronze loads one extract at a time from the landing folder in lh_bronze. Every column stays text. If Bronze typed dates on the way in, a day-first date would fail or come out null and Silver would never see the error. Reloading an extract only replaces that extract's rows.

### Silver

nb_load_silver removes duplicates and checks every row against the data quality rules. It fixes a value only when there's one right answer. Anything else that breaks a rule goes to dq.quarantine with the original row, and clean rows go in with a MERGE that won't take an older last_modified_at. Each table must then reconcile or the run fails.

### Gold and the model

nb_load_gold rebuilds Gold from Silver in full on every run. It's a small star schema with one fact row per episode of care and six dimensions. The reporting date is the latest extract's cut-off, not today. The semantic model reads Gold in Direct Lake mode, so there's no import to refresh.

### The report

Two pages. Service overview covers people in treatment, waits to triage, planned completions and referrals. Data quality shows what happened to each extract's rows and when the last good load ran. Anyone reading the first page can check it against the second.

### The pipeline

pl_load_extract runs one extract end to end. Its first step picks the oldest landed extract with no successful run in ops.run_log. A failed step is logged, then a Fail activity marks the run Failed. The broken extract fails at the column check every time and is picked again on the next run.

The [full build story](docs/how-it-works.md) has every screenshot and the design decisions.

## Proving it with SQL

Passing runs aren't proof, so I checked the tables directly in nb_sql_checks. These two checks matter most.

![Spark SQL reconciliation check for every pipeline run](docs/images/14-sql-every-load-reconciles.png)

Every run balances, reruns included.

![Spark SQL join over Gold counting people in treatment by service](docs/images/17-sql-gold-join-matches-report.png)

People in treatment by service from Gold, the same six numbers as the report.

## Known gaps and next steps

- Show Planned Completion (%) per service.
- Show the wait to triage per service.
- Split referrals per month by referral source and mark the latest month as partial.
- Give every visual a plain title.
- Label the Last Successful Load time as UTC.
- Send an alert when a run fails.
- Add a source that's read from an API, not just file extracts.
- The public data stage still needs a full check.
- Promote the items to a test workspace with a deployment pipeline.

## How to run it

You'll need Python 3 and a Fabric capacity. I used an F2.

```
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m extract_generator --seed 2026 --out output
.venv\Scripts\python -m pytest
```

Connect a Fabric workspace to this repo with Git integration on `fabric/`, then update it from Git. A tenant admin has to allow GitHub sync first, and each notebook may need its default lakehouse attached again. Upload `output/` to `Files/landing/` in lh_bronze, keeping the folder names, and run pl_load_extract once per extract with `extract_id` empty. The fifth run hits the broken extract and fails, as it should. The [runbook](docs/runbook.md) covers the rest.

## Data and licences

The treatment data is synthetic and the six services are fictional, though their districts are real: Middlesbrough, Blackpool, Brighton and Hove, Cornwall, Leeds and Lewisham. The data model and code lists are my own design, not any provider's or a national dataset's. I used the public NDTMS Core Dataset documents for concepts only.

The public data is three files from the Ministry of Housing, Communities and Local Government and ONS under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Contains public sector information licensed under the Open Government Licence v3.0. Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Links and file fingerprints are in the [public data notes](docs/public-data.md).

The code is under the [MIT licence](LICENSE).

## Repo layout

| Folder | What it holds |
|---|---|
| `extract_generator/` | The synthetic data generator |
| `tests/` | Tests for the generator and the view files |
| `fabric/` | The Fabric items as Git integration saves them |
| `sql/` | The reporting views and the script that deploys them |
| `docs/` | The build story, [decisions log](docs/decisions.md), [source to target mapping](docs/source-to-target.md), runbook, public data notes and screenshots |

Author: Bayar Dilzar
