# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "381f57db-79ac-4c76-8ad3-61256c09907f",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "79583ae2-ec4b-440f-a2e1-673ae384a224"
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

# Empty unless the pipeline is told which extract to load.
extract_id = ""

# CELL ********************

import re

RUN_LOG = "lh_silver.ops.run_log"
DATE = r"\d{4}-\d{2}-\d{2}"

# Folder names are dates written YYYY-MM-DD, so name order is date order and the first is the oldest.
landed = sorted(f.name for f in notebookutils.fs.ls("Files/landing/extracts") if f.isDir and re.fullmatch(DATE, f.name))
# Only a successful run counts as loaded, so a failed or half-finished extract is tried again,
# and a broken one is never skipped. The run log does not exist before the first run.
loaded = set()
if spark.catalog.tableExists(RUN_LOG):
    loaded = {row.extract_id for row in spark.sql(f"SELECT DISTINCT extract_id FROM {RUN_LOG} WHERE status = 'Succeeded'").collect()}

if extract_id:
    if not re.fullmatch(DATE, extract_id):
        raise ValueError(f"extract_id must be an extract date such as 2026-10-25, not '{extract_id}'.")
    # Loading a newer extract first would quarantine its new rows whose parents are in an older one, so every
    # older landed extract must have loaded. A rerun after them is still allowed.
    missing = [name for name in landed if name < extract_id and name not in loaded]
    if missing:
        raise ValueError(f"Cannot load {extract_id}: these older landed extracts have no successful run: "
                         f"{', '.join(missing)}. Run pl_load_extract with no extract_id to load them in order.")
    chosen = extract_id
else:
    pending = [name for name in landed if name not in loaded]
    chosen = pending[0] if pending else ""

print(f"extract to load: '{chosen}'" if chosen else "nothing to load")

# CELL ********************

notebookutils.notebook.exit(chosen)
