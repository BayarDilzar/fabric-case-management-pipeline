# Runbook: pl_load_extract

## Load the next extract

1. Resume the capacity if it is paused.
2. Check the extract's four files are in lh_bronze under `Files/landing/extracts/<YYYY-MM-DD>/`, and its manifest under `Files/landing/manifests/<YYYY-MM-DD>/`.
3. Open pl_load_extract and select Run. Leave extract_id empty.
4. Wait for the run to finish in Monitor. A run takes 7 to 9 minutes.
5. Read the run log as below. The newest row shows the extract id and status Succeeded.
6. Repeat from step 3 until the newest row shows status Nothing to load, or a run fails.
7. Pause the capacity if you are stopping.

## Rerun one extract

1. Open pl_load_extract and select Run.
2. Set extract_id to the extract date, for example 2026-11-08.
3. Wait for the run to finish in Monitor.
4. Check the newest run log row shows that extract id and status Succeeded.
5. In dq.reconciliation, filter on the new run_id. Expect inserted and updated to be 0 for every table, unless the landed files changed.

## Read the run log

1. Open the lh_silver SQL analytics endpoint.
2. Open ops.run_log and sort by run_id, newest first. run_id is the run's start time in UTC.
3. Read status: Succeeded, Failed or Nothing to load.
4. For a Failed row, read failed_step and error_message.
5. Compare bronze_rows, silver_rows and quarantined_rows with the row before it.
6. To open the run in Monitor, search for its pipeline_run_id.
7. To see the row counts per table, filter dq.reconciliation on the same run_id.

## Recover from a failed run

1. Find the Failed row in ops.run_log. Read failed_step and error_message.
2. If error_message contains "Schema check failed", a file has a missing or extra column. The message names the file and the column. Nothing was written. Get a corrected file from the source, land it in the same folder, and go to step 6.
3. If error_message contains "No landed files", land the missing files named in the message and go to step 6.
4. If failed_step is Load Silver, read the errorValue part of error_message. For more detail, open the run in Monitor, open the Load Silver activity and open its notebook snapshot.
5. Fix the cause.
6. Run pl_load_extract with extract_id empty. The resolver picks the failed extract again, because it has no Succeeded row.
7. Check the newest run log row shows status Succeeded.
8. If Monitor shows a failed run with no run log row, the run stopped before its log step. Go to step 6.
