# Decisions log

Each entry records the decision, the alternatives considered and the reason.

## UK West region

- **Decision:** The Fabric capacity runs in UK West.
- **Alternatives:** UK South.
- **Reason:** UK South had no Fabric quota on a new subscription.

## F2 pay-as-you-go capacity

- **Decision:** One F2 capacity, billed pay as you go. It is resumed for work and paused afterwards.
- **Alternatives:** A Fabric trial on a Microsoft 365 trial tenant. A larger F SKU. A reserved capacity.
- **Reason:** F2 is the smallest F SKU, and pay as you go charges for compute only while the capacity runs. A trial-only tenant is limited to 30 days and its data is deleted when the trial ends. A reserved capacity is bought for a fixed term.

## One lakehouse per layer

- **Decision:** Each medallion layer has its own lakehouse: lh_bronze now, lh_silver and lh_gold later. The lh_ prefix matches the nb_ and pl_ prefixes of notebooks and pipelines.
- **Alternatives:** One lakehouse with a schema per layer.
- **Reason:** A Silver or Gold notebook writes to its own attached lakehouse, so a mistake there cannot change Bronze.

## Lakehouse schemas on

- **Decision:** lh_bronze has lakehouse schemas turned on, and Bronze tables go in the dbo schema. lh_silver and lh_gold will also have schemas on.
- **Alternatives:** Recreate lh_bronze with schemas off. Schemas cannot be turned off on an existing lakehouse.
- **Reason:** It was created with schemas on. It is kept because it is the current Fabric default, costs nothing for this project, and recreating it would add work for no gain. The two documented limits, direct sharing of the lakehouse and external tables over ADLS, do not affect this project.

## Bronze stored as text

- **Decision:** Bronze keeps each file exactly as received. Every source column is stored as text, with no cleaning, casting or de-duplication. Each row gets three load columns: _extract_id, _source_file and _loaded_at.
- **Alternatives:** Cast types on load. Drop or fix bad rows on load.
- **Reason:** Bad values survive into Bronze, so the M2 checks can find them and the manifest can prove it. Silver can always be rebuilt from Bronze. An empty field is stored as null, which matches the extract rule that an empty string means no value.

## Replace-by-extract reloads

- **Decision:** Bronze keeps every extract. Loading an extract replaces only the rows with that _extract_id, using a Delta replaceWhere write.
- **Alternatives:** Append on every run. Overwrite the whole table. Merge on the record key.
- **Reason:** A rerun gives the same rows and never touches other extracts. Appending would duplicate rows on a rerun. Overwriting would lose earlier extracts. A merge on the key cannot work, because Bronze holds duplicate keys on purpose.

## Git folder fabric/

- **Decision:** The workspace syncs with the main branch, in the fabric/ folder.
- **Alternatives:** The root of the repo.
- **Reason:** Fabric item definitions stay apart from the generator code, tests and docs.

## Reference files and manifest in Bronze

- **Decision:** Every load also reloads the two reference files and the reference manifest, tagged with the extract identifier reference. The manifest loads into test_manifest_files and test_manifest_defects.
- **Alternatives:** A separate run for the reference files. Tagging the reference rows with each extract date.
- **Reason:** One run then fills every Bronze table. Replace-by-extract keeps one copy of the reference data, which matches the generator writing it once. The test_ prefix marks the manifest as test reference data, not source data.

## Fix, remove or quarantine

- **Decision:** Silver fixes a value only when there is one right answer: spaces are trimmed, codes are upper-cased, and dates written as DD/MM/YYYY or YYYYMMDD are read as dates. It removes extra rows with the same business key, keeping the row with the latest last_modified_at. It quarantines a row that has an empty required field, an unreadable value, an invalid code or a missing parent, breaks a business rule, or belongs to a quarantined parent. Each check is a rule with its own id and the action fixed, removed or quarantined.
- **Alternatives:** Quarantine every row with any defect. Guess a fix for unknown codes, for example HEROIN to OPIATE. Keep every row in Silver with a flag.
- **Reason:** No value in Silver is guessed. Quarantining fixable rows would hold back 95 good values in the first extract. A flag would leave every report to filter out bad rows itself.

## Data quality tables in a dq schema

- **Decision:** dq.rule_results, dq.quarantine and dq.reconciliation sit in a dq schema in lh_silver, apart from the Silver tables in dbo. Rule results and reconciliation gain rows on every run, so runs can be compared.
- **Alternatives:** The dbo schema with a dq_ prefix. A separate lakehouse for data quality.
- **Reason:** The schema keeps the two kinds of table apart, while one notebook writes both and one SQL endpoint reads both. A separate lakehouse would mean a second lakehouse for nb_load_silver to write to.

## One quarantine table with the original row as JSON

- **Decision:** Rejected rows from all four source tables go into dq.quarantine, one row per rejected record. Each row holds the run id, extract id, source table, business key, every rule id the record failed, a reason, and the original Bronze row as JSON, with empty fields kept as null. A rebuild replaces that extract's quarantine rows.
- **Alternatives:** One quarantine table per source table, with the source columns. The key and reason only, with no copy of the row.
- **Reason:** One table gives one place to look and the same columns for every source, so a new source needs no new table. The JSON keeps the row exactly as received, whatever its columns. Without a copy, checking a rejected row would mean finding it again in Bronze. Replacing by extract means a rerun does not list the same record twice.

## Cascading quarantine of child records

- **Decision:** When a client is quarantined, its episodes are quarantined too, and when an episode is quarantined, so are its interventions and reviews. Each child gets its own rule: DQ_EPI_CLIENT_QUARANTINED, DQ_INT_EPISODE_QUARANTINED or DQ_REV_EPISODE_QUARANTINED.
- **Alternatives:** Leave the children in Silver. Treat them as orphans.
- **Reason:** A child left in Silver would point at a parent that is not there, so joins would drop it without a trace. It is not an orphan, because its parent exists in Bronze, so its own rule says why it was held back. The test data puts row-rejecting defects only on rows without children (generator decision D2), so the first extract has no cascades and these rules find 0 rows.

## Full rebuild in M2, merge in M3

- **Decision:** nb_load_silver rebuilds every Silver table from one extract's Bronze rows and overwrites it. Every write goes through one function, so M3 can replace the Silver overwrite with a merge on the business key.
- **Alternatives:** Build the merge now.
- **Reason:** M2 has one extract, so a rebuild gives the same result as a merge with less code, and a rerun is simple. The weekly extracts that need a merge arrive in M3.

## One orchestration pipeline

- **Decision:** pl_load_extract runs one extract through four notebooks in order: nb_resolve_extract picks the extract, nb_load_bronze loads Bronze, nb_load_silver merges into Silver, and nb_write_run_log logs the run. It calls nb_load_bronze directly, and pl_load_bronze is deleted.
- **Alternatives:** Call pl_load_bronze as a child pipeline. One notebook that runs the others with notebookutils.
- **Reason:** The current Invoke pipeline activity needs a connection object with stored credentials, even inside one workspace, and the legacy activity is being replaced. pl_load_bronze only wrapped one notebook, so a child pipeline would add a credential and a second run in monitoring for no gain. Separate pipeline steps show which step failed, in monitoring and in the run log.

## The resolver loads the oldest extract not yet loaded

- **Decision:** With no extract_id, nb_resolve_extract lists the date folders under Files/landing/extracts and returns the oldest one that has no Succeeded row in ops.run_log. With an extract_id it returns that one. When nothing is left, the pipeline logs Nothing to load and ends as Succeeded.
- **Alternatives:** The newest landed extract. A separate control table of loaded extracts. Get Metadata and Filter activities in the pipeline.
- **Reason:** A schedule passes no extract date, so the pipeline has to work out what comes next. Loading in date order keeps Silver in step with the source. Only a Succeeded run counts, so a failed or half-finished load is tried again and a broken extract is never skipped. The run log already records success, so no second table is needed. Pipeline expressions cannot sort, so the choice is made in Python.

## Run log in ops.run_log

- **Decision:** ops.run_log in lh_silver holds one row per pipeline run: run id, pipeline run id, extract id, trigger type, start and end time, duration, status, failed step, error message, and three counts: the extract's rows in Bronze, the rows in Silver and the extract's quarantined rows. nb_write_run_log writes the row as the last step, on success and on failure. The run id is the pipeline's trigger time in UTC, and nb_load_silver uses the same id in the dq tables.
- **Alternatives:** The pipeline run history in monitoring. A row written at the start and updated at the end.
- **Reason:** Monitoring history is not a table, so the resolver cannot read it, and it holds no row counts. A row written once at the end needs no update. A run that stops before its log step, for example when the capacity pauses, leaves no row, so the resolver tries that extract again. The counts are read from the tables, so a failed run shows what it left behind. Fabric is reported to give Manual as the trigger type of scheduled runs too, so a scheduled run may be logged as manual; this cannot be tested while the schedule is off.

## Schema check before writing Bronze

- **Decision:** nb_load_bronze reads the header of every file it is about to load and compares it with the columns in the generator spec. A missing or extra column fails the run, naming the file and the column, before any table is written.
- **Alternatives:** Let Delta fill a missing column with null. Check only the four extract files. Check in Silver.
- **Reason:** Spark loads a file with a missing column without complaint, so the broken extract 2026-11-22 would reach Silver with every end_date empty. Checking every file the run reads, the reference files and manifest included, keeps one rule: nothing is written unless everything matches. A check in Silver would come too late, because Bronze would already hold the rows.

## Log the failure, then fail the pipeline

- **Decision:** Each notebook step in pl_load_extract has its own failure branch: a run log row with status Failed, the step name and the error message, then a Fail activity with the same message. The Fail activity runs whether or not the log row was written.
- **Alternatives:** No failure branch. A failure branch with the log step only.
- **Reason:** When a failed activity is handled by a branch that succeeds, monitoring shows the whole run as Succeeded. The Fail activity keeps a failed load Failed. A branch per step records which step failed without parsing the message.

## Schedule created but switched off

- **Decision:** pl_load_extract has a daily schedule at 20:00 UK time, ending 30 November 2026. It uses the time zone GMT Standard Time, so it follows British Summer Time. It is switched off.
- **Alternatives:** Switch it on. No schedule.
- **Reason:** The capacity is paused most of the time, so live scheduled runs would only fail and fill the run log with failures. The schedule shows how the load would run unattended, and the resolver makes a run with no extract_id safe. Scheduling works on this F2 capacity: the schedule was created and read back through the API on 25 November 2026.
