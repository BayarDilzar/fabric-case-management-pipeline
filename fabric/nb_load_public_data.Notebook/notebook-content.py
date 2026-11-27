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

# pl_load_public_data passes the exit value of nb_land_public_data: a JSON list with one entry per landed
# file, giving its source, release, path, URL and sha256.
landed = ""

# CELL ********************

import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone

import notebookutils
import openpyxl
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

# How each file is read: the sheet (None for a CSV), the row the column headers are on, and the text the first
# header cell must have. A different first header means the publisher changed the layout, so the run stops.
READ = {
    "deprivation_lad": {"sheet": "IMD", "header_row": 1, "first_header": "Local Authority District code (2024)"},
    "drug_poisoning_deaths_lad": {"sheet": "Table 3", "header_row": 6, "first_header": "Area Codes"},
    "local_authority": {"sheet": None, "header_row": 1, "first_header": "LAD24CD"},
}
ENGLISH_DISTRICT = r"^E0[6-9][0-9]{6}$"

entries = json.loads(landed) if landed else []
if sorted(e["source"] for e in entries) != sorted(READ):
    raise ValueError(f"landed must list each of {sorted(READ)} once, as nb_land_public_data returns it. Got: {landed!r}")


def column_name(header):
    """A Bronze column name from a header: note markers dropped, lower case, other characters as one underscore."""
    return re.sub(r"[^0-9a-z]+", "_", re.sub(r"\[note \d+\]", "", header.lower())).strip("_")


def text(value):
    # openpyxl gives numbers as int or float and str() keeps the stored value. An empty cell is stored as null.
    return None if value is None or value == "" else str(value)


def read_landed(entry):
    """Header texts, Bronze column names and data rows of one landed file, after checking its sha256."""
    local = os.path.join(tempfile.mkdtemp(), os.path.basename(entry["file"]))
    notebookutils.fs.cp(entry["file"], "file:" + local)
    with open(local, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    if sha256 != entry["sha256"]:
        raise ValueError(f"{entry['file']} has sha256 {sha256}, but nb_land_public_data landed {entry['sha256']}.")
    rule = READ[entry["source"]]
    if rule["sheet"] is None:
        # utf-8-sig drops the byte order mark, which would otherwise hide inside the first column name.
        with open(local, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    else:
        workbook = openpyxl.load_workbook(local, read_only=True, data_only=True)
        rows = [list(row) for row in workbook[rule["sheet"]].iter_rows(values_only=True)]
    header = rows[rule["header_row"] - 1]
    while header and header[-1] in (None, ""):
        header = header[:-1]
    if not header or header[0] != rule["first_header"] or None in header:
        raise ValueError(f"{entry['file']}: row {rule['header_row']} should hold the headers, starting with "
                         f"'{rule['first_header']}'. It holds {header[:3]}.")
    headers = [str(h) for h in header]
    names = [column_name(h) for h in headers]
    if len(set(names)) != len(names):
        raise ValueError(f"{entry['file']}: two headers give the same column name: {sorted(n for n in names if names.count(n) > 1)}")
    # Rows with no value at all are layout, not data. A value past the last header would be lost, so it stops the run.
    data = [row for row in rows[rule["header_row"]:] if any(text(v) is not None for v in row)]
    for row in data:
        if any(text(v) is not None for v in row[len(headers):]):
            raise ValueError(f"{entry['file']}: a row has values beyond the last header: {row[:3]}")
    return headers, names, [[text(v) for v in (list(row) + [None] * len(headers))[:len(headers)]] for row in data]

# CELL ********************

# Bronze: each file as received, every column as text, replaced on every run.
loaded_at = datetime.now(timezone.utc)
spark.sql("CREATE SCHEMA IF NOT EXISTS lh_bronze.reference")
bronze_counts = {}
for entry in entries:
    headers, names, data = read_landed(entry)
    print(f"{entry['source']}: {len(data)} data rows, headers {headers}")
    schema = StructType([StructField(n, StringType()) for n in names]
                        + [StructField(n, StringType()) for n in ("_source_file", "_source_url", "_source_release", "_sha256")]
                        + [StructField("_loaded_at", TimestampType())])
    rows = [row + [entry["file"], entry["url"], entry["release"], entry["sha256"], loaded_at] for row in data]
    spark.createDataFrame(rows, schema).createOrReplaceTempView("incoming")
    spark.sql(f"CREATE OR REPLACE TABLE lh_bronze.reference.{entry['source']} USING DELTA AS SELECT * FROM incoming")
    bronze_counts[entry["source"]] = spark.table(f"lh_bronze.reference.{entry['source']}").count()
    if bronze_counts[entry["source"]] != len(data):
        raise ValueError(f"Bronze {entry['source']} has {bronze_counts[entry['source']]} rows; its source sheet has {len(data)}.")

# CELL ********************

# Silver: trimmed and typed. try_cast gives null for an unreadable value; the checks below stop the run on
# any null that the source did not mark as suppressed, so nothing unreadable is passed on as missing.
silver = {}
silver["local_authority"] = spark.sql("""
    SELECT trim(lad24cd) AS local_authority_code, trim(lad24nm) AS local_authority_name,
           trim(rgn24cd) AS region_code, trim(rgn24nm) AS region_name
    FROM lh_bronze.reference.local_authority
""")
silver["deprivation_lad"] = spark.sql("""
    SELECT trim(local_authority_district_code_2024) AS local_authority_code,
           trim(local_authority_district_name_2024) AS local_authority_name,
           try_cast(trim(imd_rank_of_average_score) AS INT) AS imd_rank_of_average_score,
           try_cast(trim(imd_proportion_of_lsoas_in_most_deprived_10_nationally) AS DOUBLE) AS imd_proportion_lsoas_most_deprived_10pct
    FROM lh_bronze.reference.deprivation_lad
""")

# Table 3 has five columns per three year period, newest first. The latest period is found from the headers,
# so the next edition needs no code change here.
periods = sorted({m.groups() for c in spark.table("lh_bronze.reference.drug_poisoning_deaths_lad").columns
                  if (m := re.fullmatch(r"(\d{4})_to_(\d{4})_number_of_deaths", c))}, key=lambda period: period[1])
first, last = periods[-1]
p = f"{first}_to_{last}"
# The file also holds England, Wales, regions and counties; only English districts are kept, as IoD covers
# England only. A district's name is in the unitary authority column or the district column, by its level.
# [x] means ONS did not calculate the rate (fewer than 10 deaths), so the rate and its limits are null and
# the marker says why. [u] means low reliability (10 to 19 deaths); the rate is kept with its marker.
silver["drug_poisoning_deaths_lad"] = spark.sql(f"""
    SELECT trim(area_codes) AS local_authority_code,
           trim(coalesce(local_authority_district, county_or_unitary_authority)) AS local_authority_name,
           '{first} to {last}' AS period,
           try_cast(trim(`{p}_number_of_deaths`) AS INT) AS deaths,
           try_cast(trim(`{p}_rate_per_100_000`) AS DOUBLE) AS age_standardised_rate_per_100000,
           try_cast(trim(`{p}_lcl`) AS DOUBLE) AS rate_lower_95_ci,
           try_cast(trim(`{p}_ucl`) AS DOUBLE) AS rate_upper_95_ci,
           CASE WHEN trim(`{p}_rate_per_100_000`) = '[x]' THEN '[x]' ELSE trim(`{p}_marker`) END AS rate_marker
    FROM lh_bronze.reference.drug_poisoning_deaths_lad
    WHERE trim(area_codes) RLIKE '{ENGLISH_DISTRICT}'
""")


def fail_if_any(df, what):
    rows = df.limit(5).collect()
    if rows:
        raise ValueError(f"{what}: {[r.asDict() for r in rows]}")


for name, df in silver.items():
    fail_if_any(df.where(f"NOT local_authority_code RLIKE '{ENGLISH_DISTRICT}' OR local_authority_name IS NULL"),
                f"Silver {name} has a code that is not an English district code (E06, E07, E08 or E09), or no name")
    fail_if_any(df.groupBy("local_authority_code").count().where("count > 1"), f"Silver {name} has a code more than once")
fail_if_any(silver["deprivation_lad"].where("imd_rank_of_average_score IS NULL OR imd_proportion_lsoas_most_deprived_10pct IS NULL"),
            "Silver deprivation_lad has a rank or proportion that is not a number")
fail_if_any(silver["drug_poisoning_deaths_lad"].where("""
        deaths IS NULL
        OR (rate_marker IS NOT NULL AND rate_marker NOT IN ('[x]', '[u]'))
        OR ((age_standardised_rate_per_100000 IS NULL) <> (rate_marker <=> '[x]'))
        OR ((rate_lower_95_ci IS NULL) <> (rate_marker <=> '[x]'))
        OR ((rate_upper_95_ci IS NULL) <> (rate_marker <=> '[x]'))"""),
            "Silver drug_poisoning_deaths_lad has an unreadable value or a marker other than [x] or [u]")
# IoD 2025 uses 2024 district codes, and so does the December 2024 lookup. If they stop matching, the lookup
# is the wrong edition for IoD.
deprivation_codes = silver["deprivation_lad"].select("local_authority_code")
lookup_codes = silver["local_authority"].select("local_authority_code")
fail_if_any(deprivation_codes.exceptAll(lookup_codes).union(lookup_codes.exceptAll(deprivation_codes)),
            "deprivation_lad and local_authority do not hold the same district codes")

# The six fictional services must find their district in every table, or the join to Gold would lose them.
service_codes = sorted(r[0] for r in spark.sql("SELECT DISTINCT local_authority_code FROM lh_gold.dbo.dim_service").collect())
if not service_codes:
    raise ValueError("lh_gold.dbo.dim_service has no local authority codes to check against.")


def check_services(df, name):
    found = {r[0] for r in df.where(df.local_authority_code.isin(service_codes)).select("local_authority_code").collect()}
    if sorted(found) != service_codes:
        raise ValueError(f"{name} has no row for service district codes {sorted(set(service_codes) - found)}")


for name, df in silver.items():
    check_services(df, f"Silver {name}")

spark.sql("CREATE SCHEMA IF NOT EXISTS lh_silver.reference")
silver_counts = {}
for name, df in silver.items():
    df.createOrReplaceTempView("incoming")
    spark.sql(f"CREATE OR REPLACE TABLE lh_silver.reference.{name} USING DELTA AS SELECT * FROM incoming")
    silver_counts[name] = spark.table(f"lh_silver.reference.{name}").count()

# CELL ********************

# Gold: one row per district in the lookup. A district a source does not cover gets nulls for that source.
gold = spark.sql("""
    SELECT la.local_authority_code, la.local_authority_name, la.region_code, la.region_name,
           d.imd_rank_of_average_score, d.imd_proportion_lsoas_most_deprived_10pct,
           p.period AS drug_poisoning_period, p.deaths AS drug_poisoning_deaths,
           p.age_standardised_rate_per_100000 AS drug_poisoning_rate_per_100000,
           p.rate_lower_95_ci AS drug_poisoning_rate_lower_95_ci, p.rate_upper_95_ci AS drug_poisoning_rate_upper_95_ci,
           p.rate_marker AS drug_poisoning_rate_marker
    FROM lh_silver.reference.local_authority la
    LEFT JOIN lh_silver.reference.deprivation_lad d ON d.local_authority_code = la.local_authority_code
    LEFT JOIN lh_silver.reference.drug_poisoning_deaths_lad p ON p.local_authority_code = la.local_authority_code
""")
if gold.count() != silver_counts["local_authority"] or gold.select("local_authority_code").distinct().count() != gold.count():
    raise ValueError("dim_local_authority must have exactly one row per district in Silver local_authority.")
check_services(gold, "dim_local_authority")
gold.createOrReplaceTempView("incoming")
spark.sql("CREATE OR REPLACE TABLE lh_gold.dbo.dim_local_authority USING DELTA AS SELECT * FROM incoming")
gold_count = spark.table("lh_gold.dbo.dim_local_authority").count()

# Districts the deaths file does not cover under the lookup's code are reported, not hidden.
no_deaths = [r.asDict() for r in spark.sql("""
    SELECT local_authority_code, local_authority_name FROM lh_gold.dbo.dim_local_authority
    WHERE drug_poisoning_deaths IS NULL ORDER BY local_authority_code""").collect()]
summary = {"bronze": bronze_counts, "silver": silver_counts, "gold_dim_local_authority": gold_count,
           "service_codes_checked": service_codes, "drug_poisoning_period": f"{first} to {last}",
           "districts_without_drug_poisoning_figures": no_deaths}
print(json.dumps(summary, indent=2))
notebookutils.notebook.exit(json.dumps(summary))
