# Runbook: pl_load_extract and pl_load_public_data

## Load the next extract

1. Resume the capacity if it is paused.
2. Check the extract's four files are in lh_bronze under `Files/landing/extracts/<YYYY-MM-DD>/`, and its manifest under `Files/landing/manifests/<YYYY-MM-DD>/`.
3. Open pl_load_extract and select Run. Leave extract_id empty.
4. Wait for the run to finish in Monitor. A run takes 9 to 10 minutes. A second run started meanwhile waits in the queue until this one ends.
5. Read the run log as below. The newest row shows the extract id and status Succeeded. Gold and the semantic model now include that extract.
6. Repeat from step 3 until the newest row shows status Nothing to load, or a run fails.
7. Pause the capacity if you are stopping.

## Rerun one extract

1. Open pl_load_extract and select Run.
2. Set extract_id to the extract date, for example 2026-11-08.
3. Wait for the run to finish in Monitor.
4. If the run failed at Resolve extract with "Cannot load", an older landed extract has no Succeeded run. The message names it. Run pl_load_extract with extract_id empty to load it first, then go back to step 1.
5. Check the newest run log row shows that extract id and status Succeeded.
6. In dq.reconciliation, filter on the new run_id. Expect inserted and updated to be 0 for every table, unless the landed files changed.

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
4. If failed_step is Load Silver or Load Gold, read the errorValue part of error_message. For more detail, open the run in Monitor, open that activity and open its notebook snapshot.
5. Fix the cause.
6. Run pl_load_extract with extract_id empty. The resolver picks the failed extract again, because it has no Succeeded row.
7. Check the newest run log row shows status Succeeded.
8. If Monitor shows a failed run with no run log row, the run stopped before its log step. Go to step 6.

## Deploy the reporting views

1. Install the development requirements into the project's virtual environment: `pip install -r requirements-dev.txt`.
2. Sign in with `az login`, using an account with Contributor access to the workspace.
3. Run `python sql/deploy_views.py <workspace name>`. It deploys every file in `sql/reporting/` to the lh_gold SQL analytics endpoint.
4. Check the last line lists the six views in the reporting schema.
5. After changing a .sql file, run step 3 again. Each file replaces its view.

## Load the public data

pl_load_public_data lands the three public files and loads them to Bronze, Silver and Gold. The files change once a year, so it runs by hand only. [public-data.md](public-data.md) describes the sources.

1. Resume the capacity if it is paused.
2. Open pl_load_public_data and select Run. It has no parameters.
3. Wait for the run to finish in Monitor. A run takes 2 to 5 minutes.
4. Check that Land public data and Load public data both show Succeeded.
5. Open the output of Load public data. Its exit value gives the row counts: 296, 358 and 296 in the three Bronze tables, 296 in each Silver table, and 296 in dim_local_authority. It also lists the districts without drug poisoning figures, which should be Barnsley and Sheffield only.
6. Open the lh_gold SQL analytics endpoint and open dbo.dim_local_authority. Check it has 296 rows, and that each local_authority_code in dbo.dim_service has a row with a deprivation rank and a death count.
7. Pause the capacity if you are stopping.

## Recover from a failed public data run

1. Open the failed run in Monitor and read the error of the failed activity.
2. If Land public data failed with "is landed with sha256", the publisher now serves a different file for that release. Nothing was written. Follow [How to rerun](public-data.md#how-to-rerun) in public-data.md before loading the new file.
3. If Land public data failed with "did not return an Excel file" or a network error, the site was down or sent an error page. Run the pipeline again later.
4. If Load public data failed, the message names the file or table and the check. "should hold the headers" means the publisher changed the layout. "has no row for service district codes" means a source no longer covers a service district; do not remap the code, look at the source first.
5. Bronze is replaced before the Silver checks run. Silver and Gold are written only after their own checks pass, so after a failed Silver check both keep the tables from the last good run.
6. Fix the cause and run pl_load_public_data again.
