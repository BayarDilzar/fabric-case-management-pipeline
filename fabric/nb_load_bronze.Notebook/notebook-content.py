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

# The pipeline passes extract_id. It is empty by default, so a run without it fails instead of guessing.
extract_id = ""

# CELL ********************

import json
import re
from datetime import datetime, timezone

from pyspark.sql import functions as F

LANDING = "Files/landing"
REFERENCE = "reference"

if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", extract_id):
    raise ValueError(f"extract_id must be an extract date such as 2026-10-25, not '{extract_id}'.")

# (table, folder, file, tag). The reference files and their manifest load with every extract under
# one tag, so Bronze holds one copy of them, as the generator writes them once.
loads = [(name, f"extracts/{extract_id}", f"{name}.csv", extract_id) for name in ["clients", "episodes", "interventions", "reviews"]]
loads += [
    ("test_manifest_files", f"manifests/{extract_id}", "files.csv", extract_id),
    ("test_manifest_defects", f"manifests/{extract_id}", "defects.csv", extract_id),
    ("services", REFERENCE, "services.csv", REFERENCE),
    ("code_lists", REFERENCE, "code_lists.csv", REFERENCE),
    ("test_manifest_files", f"manifests/{REFERENCE}", "files.csv", REFERENCE),
]

# Check every file before writing, so a wrong extract_id fails with no table changed.
missing = [f"{LANDING}/{folder}/{file}" for _, folder, file, _ in loads if not notebookutils.fs.exists(f"{LANDING}/{folder}/{file}")]
if missing:
    raise FileNotFoundError(f"No landed files for extract_id '{extract_id}'. Missing: {', '.join(missing)}")

# CELL ********************

# One timestamp for the whole run, so every row from this load carries the same value.
loaded_at = F.lit(datetime.now(timezone.utc))

for table, folder, file, tag in loads:
    rows = (
        spark.read.option("header", True)
        # No schema inference: every column stays text, so bad values reach Bronze unchanged.
        # The generator escapes a quote by doubling it, which Spark only reads correctly with this option.
        .option("escape", '"')
        .csv(f"{LANDING}/{folder}/{file}")
        .withColumn("_extract_id", F.lit(tag))
        .withColumn("_source_file", F.lit(f"{folder}/{file}"))
        .withColumn("_loaded_at", loaded_at)
    )
    # Replace only this tag's rows: a rerun never duplicates, and other extracts stay as they are.
    rows.write.format("delta").mode("overwrite").option("replaceWhere", f"_extract_id = '{tag}'").saveAsTable(table)

# CELL ********************

loaded = {f"{table}/{tag}": spark.read.table(table).where(F.col("_extract_id") == tag).count() for table, _, _, tag in loads}
totals = {table: spark.read.table(table).count() for table in dict.fromkeys(table for table, *_ in loads)}
result = json.dumps({"extract_id": extract_id, "loaded": loaded, "totals": totals})
print(result)

# CELL ********************

notebookutils.notebook.exit(result)
