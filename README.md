# fabric-case-management-pipeline

I built this Microsoft Fabric pipeline to take weekly extracts from a made-up drug and alcohol treatment case management system through Bronze, Silver and Gold lakehouses into a Power BI report. The data is synthetic, made by a Python generator I designed, and the data model is my own design, not any real provider's.

The treatment strand (M1 to M4) is built, run and checked in my own Fabric workspace. The public data strand (M5) is built but not reviewed by me.

I built it in five stages, and the docs refer to them:

- M1: the extract generator and Bronze
- M2: Silver and the data quality checks
- M3: weekly incremental loads, the run log and failure handling
- M4: Gold, the reporting views, the semantic model and the report
- M5: public data by local authority

## How it fits together

```mermaid
flowchart LR
    gen["Python generator<br>synthetic CSV extracts"] --> land["Landing<br>lh_bronze Files"]
    land --> bronze["Bronze<br>lh_bronze, all text"]
    bronze --> silver["Silver<br>lh_silver, typed and checked"]
    silver --> gold["Gold<br>lh_gold, star schema"]
    gold --> model["Semantic model<br>Direct Lake"]
    model --> report["Power BI report<br>two pages"]
```

### Generator

The generator in `extract_generator/` runs on my laptop. From one seed it builds about three and a half years of clients, episodes, interventions and reviews for six fictional services in six real English districts. It writes one historical extract, three weekly extracts that hold only new and changed rows, and one broken extract whose interventions file has no `end_date` column. It also plants known mistakes in the files and lists every one in a manifest, 312 in the historical extract, so the checks in Fabric can be tested against an answer key. The same seed always gives the same files, byte for byte.

### Landing

The generator's output goes into `Files/landing/` in lh_bronze, one folder per extract date, with its manifest next to it.

### Bronze

nb_load_bronze loads one extract into Delta tables in lh_bronze. Every column stays text, and three load columns record the extract, the source file and the load time. Text means bad values survive for the Silver checks, and Bronze row counts match the files exactly. Before it writes anything, it checks the columns of every file, so the broken extract stops here. A rerun replaces only that extract's rows.

### Silver

nb_load_silver checks each row of an extract against 44 rules, and every row ends up with one of three outcomes:

- Fixed: the value has one right answer, so Silver corrects it. Spaces are trimmed, codes are upper-cased, and dates written as DD/MM/YYYY or YYYYMMDD are read as dates.
- Removed: another row has the same business key. Silver keeps the one with the latest `last_modified_at`.
- Quarantined: anything else, such as an unknown code, a missing parent or a broken business rule. The row goes to `dq.quarantine` with its rule ids, a reason and the original Bronze row as JSON. Its child rows are quarantined with it.

Clean rows are merged into Silver on the business key, and a stored row only changes when the incoming `last_modified_at` is newer. So a rerun, or an older extract that arrives late, changes nothing. Each run also writes `dq.reconciliation`, where Bronze rows must equal inserted + updated + unchanged + removed + quarantined for every table, and the run fails if one does not balance.

### Gold

nb_load_gold rebuilds lh_gold from Silver on every run, in about a minute. It is a small star schema: `fact_episode` has one row per episode, with dimensions for client, service, date, referral source, substance and discharge reason. `fact_extract_load` holds the data quality figures for each extract, and `report_settings` holds the reporting date and the 21 day wait threshold. The reporting date is the cut-off of the latest loaded extract, never today, so the same data always gives the same answers. Six T-SQL views in `sql/reporting/` answer the same questions for analysts on the lh_gold SQL endpoint.

### Semantic model and report

sm_case_management reads the Gold tables in Direct Lake mode, so there is no imported copy to refresh. rpt_case_management has two pages, Service overview and Data quality.

### Orchestration

pl_load_extract runs one extract end to end. nb_resolve_extract picks the oldest landed extract with no successful run, then the pipeline runs Bronze, Silver and Gold and writes one row to `ops.run_log`. When a step fails, the pipeline logs the failure and a Fail activity marks the run Failed, so monitoring never shows a false success. Only one run goes at a time. A daily schedule exists but is switched off, because I pause the capacity when I am not working on it.

### Public data

pl_load_public_data downloads three official files: the English Indices of Deprivation 2025, ONS deaths related to drug poisoning by local authority, and the ONS district to region lookup. It loads them through Bronze and Silver into `reference` schemas and builds `lh_gold.dbo.dim_local_authority`, one row per English district, which joins to `dim_service` on the district code. It is not in the semantic model or the report yet. The public data strand (M5) is built but not reviewed by me.

Every design choice, with the alternatives and the reason, is in [docs/decisions.md](docs/decisions.md). Column by column mappings are in [docs/source-to-target.md](docs/source-to-target.md).

## Results

Everything here comes from the synthetic data, as of 15 November 2026, the cut-off of the latest loaded extract. The figures show the pipeline works. They say nothing about any real service.

| What I checked | Result |
|---|---|
| Planted defects in the historical extract | 312 of 312 caught, each by the rule meant for it. No clean row rejected and no clean value changed |
| Planted defects in each weekly extract | 14 of 14 caught in each of the three |
| Reconciliation | Balances for every table in every run |
| Rerun of 2026-11-08 after 2026-11-15 | 0 rows inserted, 0 updated, 259 unchanged. Silver got no new Delta version |
| Broken extract 2026-11-22 | Failed at Load Bronze on all four attempts and was never skipped. Nothing was written |
| Silver after four extracts, against an independent Python model | Every row matches: 2,090 clients, 2,683 episodes, 4,171 interventions and 5,296 reviews |
| The six report questions, worked out again in plain Python from the CSV files | 0 differences from the views |
| Each DAX measure against its view | 60 checks, 0 differences |
| Unit tests | 101 pass |

## What Gold answers

All six as of 15 November 2026. How each one is measured is in [docs/decisions.md](docs/decisions.md#how-each-question-is-measured).

1. How many people are in treatment now? 582: Leeds 154, Blackpool 115, Cornwall 90, Middlesbrough 87, Brighton and Hove 73, Lewisham 63. In treatment means an episode with no discharge date.
2. How many new referrals come in each month, and from where? 2,683 over 44 months, April 2023 to November 2026. Self-referral 1,198, criminal justice 533, GP 415, other health or social care 317, and family, friend or carer 220. November 2026 only runs to the 15th and has 85.
3. How long do people wait from referral to triage? The median is 13 days at every service. 76.5% of the 2,600 triaged episodes (1,989) were seen within 21 days, from 72.8% at Cornwall to 80.0% at Blackpool. 83 episodes are not triaged yet, so they have no wait.
4. What share of discharges are planned completions? 48.2%, or 1,012 of 2,101. Leeds 51.0%, Cornwall 50.0%, Lewisham 49.1%, Middlesbrough 47.4%, Blackpool 44.9%, Brighton and Hove 44.1%.
5. What is the primary substance at referral? Alcohol 971 (36.2%), opiates 791 (29.5%), cannabis 297 (11.1%), crack cocaine 252 (9.4%), powder cocaine 246 (9.2%) and other drugs 126 (4.7%).
6. Can the figures be trusted? Each extract's rows, as Silver handled them:

   | Extract | Rows loaded | Values fixed | Rows removed | Rows quarantined |
   |---|---|---|---|---|
   | 2026-10-25 | 13,959 | 95 | 110 | 107 |
   | 2026-11-01 | 274 | 5 | 4 | 5 |
   | 2026-11-08 | 268 | 5 | 4 | 5 |
   | 2026-11-15 | 265 | 5 | 4 | 5 |
   | Total | 14,766 | 110 | 122 | 122 |

   Rows loaded counts the four extract files. The last successful load was on 25 November 2026 at 06:40 UTC.

## Screenshots

![Bronze clients table in Fabric with every source column typed as text and three load columns](docs/images/01-bronze-tables-loaded-as-text.png)

Bronze keeps each extract exactly as it arrived. Every source column is text, so bad values survive for the Silver checks, and three load columns record the extract, the source file and the load time.

![Fabric pipeline canvas for pl_load_extract: set run id, resolve extract, an If Condition that runs the load steps, and a failure branch that logs then fails](docs/images/02-orchestration-pipeline.png)

pl_load_extract picks the oldest extract not yet loaded, then runs Bronze, Silver and Gold in order. When a step fails, the pipeline logs the failure, then a Fail activity marks the run as Failed (boxed).

![Monitor run history for pl_load_extract with six successful runs and two failed runs for the broken extract](docs/images/03-pipeline-run-history.png)

Runs of pl_load_extract on the morning of 25 November 2026. The two failures are the broken extract 2026-11-22, which fails each time it is tried rather than being skipped.

![Error message naming the extract, file and missing column](docs/images/04-broken-extract-fails-schema-check.png)

The broken extract fails the schema check before anything is written: interventions.csv is missing end_date. This run is from before Load Gold was added to the pipeline.

![Silver clients table with typed columns, and the dq schema holding quarantine, reconciliation and rule_results](docs/images/05-silver-typed-tables-and-dq-schema.png)

Silver is typed: birth_year is a number and last_modified_at a timestamp. The data quality tables sit in their own dq schema.

![Quarantine table listing rejected rows with rule ids, reasons and the original row](docs/images/06-dq-quarantine-with-reasons.png)

122 rejected rows across four extracts, each kept with the rule it broke, a plain English reason and the original Bronze row.

![Reconciliation table with inserted, updated and unchanged counts per extract](docs/images/07-dq-reconciliation-by-extract.png)

Every extract reconciles: Bronze rows = inserted + updated + unchanged + duplicates removed + quarantined. The boxed rows are 2026-11-08 loaded once, then rerun. The rerun inserts and updates nothing.

![Run log table listing twelve runs with their status and failed step](docs/images/08-run-log.png)

ops.run_log has one row per pipeline run, with the extract, timings, status and the step that failed (boxed). The broken extract 2026-11-22 fails at Load Bronze every time it is tried. Nothing to load is a run with no new extract waiting.

![Semantic model diagram with the Episodes fact table joined to six dimension tables, plus two standalone tables](docs/images/09-gold-semantic-model.png)

The Gold star schema as the semantic model sees it. Episodes joins to six dimensions: client, service, date, substance, referral source and discharge reason. Extract Loads and Report Settings stand alone and feed the data quality page and the reporting date.

![Power BI service overview page with three headline cards and four charts](docs/images/10-report-service-overview.png)

582 people in treatment, a 13 day median wait to triage and 76.5% seen within 21 days, with caseload by service, planned completions, and referrals by substance and by month.

![Power BI data quality page with a table per extract, a chart of quarantined rows and the last successful load time](docs/images/11-report-data-quality.png)

Rows loaded, quarantined, fixed and removed for each extract, copied into Gold from the dq tables in Silver, with the time of the last successful load. The 122 quarantined rows match the quarantine table above.

## SQL checks

I checked the pipeline from the tables themselves with five Spark SQL queries in the nb_sql_checks notebook. Each one proves something different.

1. [Duplicates in Bronze](docs/images/13-sql-duplicates-in-bronze.png). 20 client ids arrive twice in the historical extract, which matches the 20 duplicates Silver removed from clients. So Bronze keeps what arrived, and the removing happens in Silver.
2. Every load reconciles (below). For each of the seven runs, Bronze rows equal inserted + updated + unchanged + duplicates removed + quarantined, reruns included. So no row was lost or counted twice. These totals include the services and code list files, so each is 31 rows higher than Rows loaded above.
3. [Quarantine by rule](docs/images/15-sql-quarantine-by-rule.png). The 122 quarantined rows fall into 12 groups of rule ids, so every held-back row says which rule it broke. One row can break more than one rule.
4. [Run history by status](docs/images/16-sql-run-history-by-status.png). 2026-11-22 failed on all four attempts, 2026-11-08 succeeded twice and 2026-11-15 three times. So a broken extract is retried, not skipped, and a rerun succeeds.
5. Gold matches the report (below). People in treatment by service from a join of fact_episode and dim_service gives 154, 115, 90, 87, 73 and 63, the same as the report.

![Notebook cell with a Spark SQL query showing balances for every pipeline run](docs/images/14-sql-every-load-reconciles.png)

![Notebook cell with a Spark SQL join returning people in treatment for six services](docs/images/17-sql-gold-join-matches-report.png)

The tests in `tests/` check the generator: the same seed gives the same bytes, and the manifest lists exactly the defects that a separate detector finds in the files, for five seeds. A test also checks that each file in `sql/reporting/` creates the view it is named after.

## How to run it

What is where:

| Folder | What it holds |
|---|---|
| `extract_generator/` | The Python generator that writes the synthetic extracts |
| `tests/` | Tests for the generator and the view files |
| `fabric/` | The Fabric items, as Fabric Git integration writes them: lakehouses, notebooks, pipelines, the semantic model and the report |
| `sql/` | The reporting views and the script that deploys them |
| `docs/` | Decisions, mappings, the runbook and the public data sources |

1. Make the extracts on your own machine. I used Python 3.10.

   ```
   py -3 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements-dev.txt
   .venv\Scripts\python -m extract_generator --seed 2026 --out output
   .venv\Scripts\python -m pytest
   ```

   The generator takes about two seconds and writes to `output/`, which git ignores.

2. Create a Fabric workspace on a capacity. I used an F2 capacity, paid as you go, and paused it whenever I stopped. Connect the workspace to this repo with Fabric Git integration, using the `fabric/` folder, and update the workspace from Git. A tenant admin has to turn on the setting that lets users sync workspace items with GitHub. I have only run this in my own workspace. Each notebook stores its default lakehouse as an ID in `fabric/`, so in a new workspace you may need to attach each notebook to its lakehouse again.

3. Upload the contents of `output/` to `Files/landing/` in lh_bronze, keeping the folder names (`reference/`, `extracts/<date>/` and `manifests/<date>/`). I used the OneLake API from a small script that is not in this repo. Any upload that keeps the paths works.

4. Run pl_load_extract with `extract_id` left empty. Each run loads the next extract, so four runs load the historical extract and the three weekly ones. A fifth run reaches the broken extract 2026-11-22 and fails, which is what it should do. A run takes 9 to 10 minutes on F2.

5. Deploy the reporting views with `python sql/deploy_views.py <workspace name>`, after `az login`.

6. Run pl_load_public_data to load the public data. It has no parameters.

7. Pause the capacity.

The [runbook](docs/runbook.md) has the checks after each run, how to rerun one extract and how to recover from a failed run.
