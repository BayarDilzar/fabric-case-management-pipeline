# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a1056192-5bb5-437c-865c-2de615388ce8",
# META       "default_lakehouse_name": "lh_silver",
# META       "default_lakehouse_workspace_id": "79583ae2-ec4b-440f-a2e1-673ae384a224"
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

# Set by pl_load_extract. run_id is the pipeline's trigger time in UTC, so it also gives the start time.
run_id = ""
pipeline_run_id = ""
extract_id = ""
trigger_type = ""
status = ""
failed_step = ""
error_message = ""

# CELL ********************

import re
from datetime import datetime, timezone

from pyspark.sql.types import IntegerType, LongType, StringType, StructField, StructType, TimestampType

if not re.fullmatch(r"\d{8}T\d{6}Z", run_id):
    raise ValueError(f"run_id must look like 20261122T200000Z, not '{run_id}'.")
if status not in ("Succeeded", "Failed", "Nothing to load"):
    raise ValueError(f"status must be Succeeded, Failed or Nothing to load, not '{status}'.")

started_at = datetime.strptime(run_id, "%Y%m%dT%H%M%SZ")
ended_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
# shortcut: Fabric was reported to give Manual for scheduled runs too, so a scheduled run may be logged
# as manual; check the first scheduled run if the schedule is switched on.
trigger = "manual" if trigger_type == "Manual" else "scheduled"

# Counts are read from the tables, so a failed run shows what it left behind: 0 Bronze rows means
# nothing of this extract was written. Only a checked date goes into the SQL text.
bronze_rows = silver_rows = quarantined_rows = None
if re.fullmatch(r"\d{4}-\d{2}-\d{2}", extract_id):
    SOURCES = ["clients", "episodes", "interventions", "reviews"]
    bronze_rows = sum(spark.sql(f"SELECT count(*) FROM lh_bronze.dbo.{t} WHERE _extract_id = '{extract_id}'").first()[0]
                      for t in SOURCES)
    silver_rows = sum(spark.table(f"dbo.{t}").count() for t in SOURCES if spark.catalog.tableExists(f"dbo.{t}"))
    if spark.catalog.tableExists("dq.quarantine"):
        quarantined_rows = spark.sql(f"SELECT count(*) FROM dq.quarantine WHERE extract_id = '{extract_id}'").first()[0]

# CELL ********************

# PySpark here, because the error text can hold any character and a DataFrame row needs no quoting.
schema = StructType([
    StructField("run_id", StringType()), StructField("pipeline_run_id", StringType()),
    StructField("extract_id", StringType()), StructField("trigger_type", StringType()),
    StructField("started_at", TimestampType()), StructField("ended_at", TimestampType()),
    StructField("duration_seconds", IntegerType()), StructField("status", StringType()),
    StructField("failed_step", StringType()), StructField("error_message", StringType()),
    StructField("bronze_rows", LongType()), StructField("silver_rows", LongType()),
    StructField("quarantined_rows", LongType()),
])
row = (run_id, pipeline_run_id or None, extract_id or None, trigger, started_at, ended_at,
       int((ended_at - started_at).total_seconds()), status, failed_step or None, error_message or None,
       bronze_rows, silver_rows, quarantined_rows)
spark.sql("CREATE SCHEMA IF NOT EXISTS ops")
spark.createDataFrame([row], schema).write.format("delta").mode("append").saveAsTable("ops.run_log")
print(row)
