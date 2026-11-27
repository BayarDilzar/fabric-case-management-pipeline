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
# META       "default_lakehouse_workspace_id": "79583ae2-ec4b-440f-a2e1-673ae384a224",
# META       "known_lakehouses": [
# META         {
# META           "id": "a1056192-5bb5-437c-865c-2de615388ce8"
# META         },
# META         {
# META           "id": "429d9211-4452-441f-9a73-d314301863a4"
# META         },
# META         {
# META           "id": "381f57db-79ac-4c76-8ad3-61256c09907f"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC SELECT client_id, COUNT(*) AS copies
# MAGIC FROM lh_bronze.dbo.clients
# MAGIC WHERE _extract_id = '2026-10-25'
# MAGIC GROUP BY client_id
# MAGIC HAVING COUNT(*) > 1
# MAGIC ORDER BY client_id

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC SELECT run_id,
# MAGIC        extract_id,
# MAGIC        SUM(bronze_rows) AS bronze_rows,
# MAGIC        SUM(inserted + updated + unchanged + duplicates_removed + quarantined) AS accounted_for,
# MAGIC        CASE WHEN SUM(bronze_rows) = SUM(inserted + updated + unchanged + duplicates_removed + quarantined)
# MAGIC             THEN 'balances' ELSE 'MISMATCH' END AS result
# MAGIC FROM lh_silver.dq.reconciliation
# MAGIC GROUP BY run_id, extract_id
# MAGIC ORDER BY run_id

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC SELECT rule_ids, COUNT(*) AS rows_quarantined
# MAGIC FROM lh_silver.dq.quarantine
# MAGIC GROUP BY rule_ids
# MAGIC ORDER BY rows_quarantined DESC

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC SELECT extract_id, status, COUNT(*) AS runs, MAX(started_at) AS last_started
# MAGIC FROM lh_silver.ops.run_log
# MAGIC GROUP BY extract_id, status
# MAGIC ORDER BY extract_id, status

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC SELECT s.service_name, COUNT(DISTINCT f.client_id) AS people_in_treatment
# MAGIC FROM lh_gold.dbo.fact_episode AS f
# MAGIC JOIN lh_gold.dbo.dim_service AS s
# MAGIC   ON f.service_code = s.service_code
# MAGIC WHERE f.is_open = true
# MAGIC GROUP BY s.service_name
# MAGIC ORDER BY people_in_treatment DESC

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }
