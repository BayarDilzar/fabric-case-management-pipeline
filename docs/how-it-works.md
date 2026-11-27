# How it works

The [README](../README.md) is the short version. This page has the full build story with every screenshot, the design decisions that shaped the project most, and the limits.

I built it in stages, and the docs call them M1 to M5. M1 is the generator and Bronze, M2 is Silver, M3 is the weekly loads and the pipeline around them, M4 is Gold and the report, and M5 is the public data.

## The data

None of the treatment data is real. I designed a Python generator, in `extract_generator/`, that plays the part of the provider's case management system. From one seed it builds about three and a half years of clients, episodes of care, interventions and reviews for six fictional services in six real English districts. It exports them as CSV files: one large historical extract, three weekly extracts holding only new and changed rows, and one broken extract with a column missing. On the way out it plants the kind of errors real exports have, such as duplicate rows, dates written day first, codes in the wrong case and rows that point at a client who does not exist. Every planted error goes into a manifest with the outcome the pipeline should reach, so the manifest is an answer key that the pipeline in Fabric is marked against.

## Landing and Bronze

Fabric keeps data in lakehouses, which hold plain files next to Delta tables (tables stored as Parquet files with a transaction log, so a write either lands in full or not at all). The generator's files are uploaded to a landing folder in lh_bronze, one folder per extract date, and nb_load_bronze loads one extract at a time into Bronze, the raw layer. Bronze keeps each extract exactly as it arrives, so nothing is lost. Every column is stored as text, with three extra columns for the extract, the source file and the load time. Text is a deliberate choice: if Bronze turned dates into dates on the way in, a date written day first would fail or come out empty, and the error would vanish before Silver could see it. Loading the same extract again replaces only that extract's rows.

![Bronze clients table in Fabric with every source column typed as text and three load columns](images/01-bronze-tables-loaded-as-text.png)

Bronze clients: every source column is text, and the last three columns record the extract, the file and the load time.

## Silver: cleaning and checking

Silver is the cleaned layer, where nb_load_silver checks every row against 48 rules. It removes duplicates, fixes what it safely can, and quarantines bad rows with a reason instead of deleting them. A fix is only allowed when there is one right answer, like a code typed in lower case. HEROIN in a substance column probably means the code OPIATE, but no value in Silver is a guess, so that row goes to quarantine with the rule it broke and a copy of the original row. Clean rows go into Silver with a MERGE, which inserts new records and updates existing ones by their key, but only when the incoming copy is newer, so a rerun or a late, older extract cannot overwrite anything. Then every load is reconciled, so every row is accounted for: for each table, the rows in Bronze must equal the rows inserted, updated, unchanged, removed and quarantined, or the run fails.

![Silver clients table with typed columns, and the dq schema holding quarantine, reconciliation and rule_results](images/05-silver-typed-tables-and-dq-schema.png)

Silver clients: birth_year is now a number, and the data quality tables live in their own dq schema.

![Quarantine table listing rejected rows with rule ids, reasons and the original row](images/06-dq-quarantine-with-reasons.png)

dq.quarantine: 122 rejected rows across four extracts, each with its rule, a plain English reason and the original Bronze row.

![Reconciliation table with inserted, updated and unchanged counts per extract](images/07-dq-reconciliation-by-extract.png)

dq.reconciliation: the lower boxed rows are a rerun of 2026-11-08, which inserts and updates nothing.

## Gold and the semantic model

Gold, the reporting layer, is rebuilt in full from Silver on every run. It is small, 2,683 episodes and 2,090 clients after four extracts, and a rebuild took 28 to 73 seconds in test runs, so it costs little and Gold can never drift out of step with Silver. It is a star schema: one central fact table with a row per episode of care, and small dimension tables around it for client, service, date, referral source, substance and discharge reason. Every question the report asks is a count of episodes filtered by one of those, which is the shape a star handles best. The reporting date is the cut-off of the latest extract, never today, so the same data always gives the same answers. On top sits the semantic model, the set of tables, relationships and measures that Power BI reads, in Direct Lake mode, so Power BI reads the Gold Delta tables where they are and there is no imported copy to refresh.

![Semantic model diagram with the Episodes fact table joined to six dimension tables, plus two standalone tables](images/09-gold-semantic-model.png)

The semantic model: Episodes in the middle with its six dimensions, and two standalone tables for data quality and the reporting date.

## The report

The report has two pages. Service overview covers the provider's everyday questions: how many people are in treatment, how long they wait for triage, how many leave with a planned completion, and which substances bring them in. Data quality covers the question under all of those, whether the figures can be trusted. For each extract it shows how many rows were loaded, fixed, removed and quarantined, and when the last good load ran. I put that page in the report itself so that anyone reading the first page can check the second. Some visuals still need work, and the open flaws are listed under [Limits](#limits).

![Power BI data quality page with a table per extract, a chart of quarantined rows and the last successful load time](images/11-report-data-quality.png)

The Data quality page. Fixed, removed and quarantined match the generator's answer key for every extract.

## Orchestration and failures

One pipeline, pl_load_extract, runs a whole extract. A schedule passes no parameters, so its first step, nb_resolve_extract, works out what to load: the oldest landed extract with no successful run in the run log. Bronze, Silver and Gold then load in order, and the last step writes a row to ops.run_log with the status and row counts. When a step fails, the pipeline logs the failure and then a Fail activity marks the whole run as Failed. Without it, Fabric marks a run Succeeded when a failure branch has handled the error, and I wanted a failed load to look failed. The broken extract shows it working: it fails the column check before anything is written, and because only a successful run counts as loaded, it is tried again on the next run instead of being skipped.

![Fabric pipeline canvas for pl_load_extract: set run id, resolve extract, an If Condition that runs the load steps, and a failure branch that logs then fails](images/02-orchestration-pipeline.png)

pl_load_extract. The boxed branch logs a failure, then fails the run.

![Monitor run history for pl_load_extract with six successful runs and two failed runs for the broken extract](images/03-pipeline-run-history.png)

Runs on the morning of 25 November 2026. Both failures are the broken extract 2026-11-22.

![Error message naming the extract, file and missing column](images/04-broken-extract-fails-schema-check.png)

The broken extract stops at the column check: interventions.csv has no end_date, so nothing was written. This run predates the Load Gold step.

![Run log table listing twelve runs with their status and failed step](images/08-run-log.png)

ops.run_log, one row per run. Nothing to load is a run with no new extract waiting.

## SQL checks

Passing runs are not proof on their own, so I also checked the results straight from the tables. The nb_sql_checks notebook holds five Spark SQL queries over Bronze, Silver and Gold. The README shows the two that matter most: every run's reconciliation balances, reruns included, and people in treatment rebuilt from Gold match the report service by service. The reconciliation totals include the two reference files, so each is 31 rows above Rows Loaded on the report. The other three checks:

![Notebook cell with a Spark SQL GROUP BY and HAVING query returning 20 duplicated client IDs](images/13-sql-duplicates-in-bronze.png)

20 client ids arrive twice in the historical extract, matching the 20 duplicates Silver removed from clients.

![Notebook cell with a Spark SQL query counting quarantined rows per rule](images/15-sql-quarantine-by-rule.png)

The 122 quarantined rows grouped by the rules they broke. One row can break more than one rule.

![Notebook cell with a Spark SQL query counting pipeline runs by extract and status](images/16-sql-run-history-by-status.png)

Runs by extract and status: the broken extract failed all four times, and the reruns of 2026-11-08 and 2026-11-15 succeeded.

## Public data

The last stage, pl_load_public_data, adds real context from three official datasets: the English Indices of Deprivation 2025, ONS figures for deaths related to drug poisoning by local authority, and the ONS lookup of districts and regions. They go through the same layers and end up in one Gold table, dim_local_authority, with a row for every English district. It joins to the services on the district code, so each fictional service can sit next to real figures for the area it serves. I recorded each source's licence before downloading anything, and each landed file keeps its sha256 fingerprint, so if a publisher swaps the file the next load stops instead of quietly taking it. The table is not in the semantic model or the report yet. The public data stage still needs a full check. [public-data.md](public-data.md) has the sources, licences, file fingerprints, columns and row counts.

## Design decisions

The [decisions log](decisions.md) has all 39 decisions, each with the alternatives I turned down. These six shaped the project most.

- One lakehouse per layer, so a Silver or Gold notebook cannot change Bronze by mistake.
- Bronze stores every column as text, so bad values survive long enough for Silver to catch them.
- Silver fixes a value only when there is one right answer and quarantines the rest with a reason, so nothing in Silver is a guess.
- The Silver MERGE only takes a newer last_modified_at, so a rerun or a late, older extract cannot replace newer data.
- Each failed step is logged and then fails the pipeline, because a handled failure otherwise shows as Succeeded.
- The reporting date is the latest extract's cut-off, not today, so the same data always gives the same answers.

## Limits

The data is synthetic, so nothing here is a finding about a real provider. I ran it with Python 3.10 on my machine and an F2 Fabric capacity, and only in my own workspace. I upload the extracts manually, and a run takes 9 to 10 minutes on F2. The daily schedule is switched off because I pause the capacity between sessions, so every run so far was started manually. If a run stops halfway, some tables are updated and others not until the next run repeats the extract, which is safe. In the public data, Barnsley and Sheffield have no drug poisoning figures, because the ONS file uses their newer district codes and they are not remapped. The [public data notes](public-data.md#limits) list the rest.

The report has five open flaws, all visible in its definition in `fabric/` and in the screenshots:

- Planned Completion (%) has no service on its axis, so it shows one bar for all services (48.2%), not one per service.
- The wait to triage appears only as two cards for all services together. The figures for each service are in Gold and in the views, but not on the page.
- Referrals per month is one line with no split by referral source, and its last point, November 2026, only runs to the 15th without saying so.
- The visual titles are the default field names, such as "# People in Treatment by Service", not plain titles.
- The Last Successful Load card shows 25 Nov 2026 06:40 with no time zone. The time is UTC.

Beyond those, dim_local_authority still has to be added to the semantic model, and public data runs should be logged in ops.run_log; for now their row counts only live in the pipeline run history.
