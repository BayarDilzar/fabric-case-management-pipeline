# Source to target

## Bronze to Silver

Bronze is lh_bronze.dbo, all text. Silver is lh_silver.dbo. A row that fails any quarantined rule goes to dq.quarantine instead of Silver. Clean rows are merged into Silver on the business key: a new key is inserted, and a stored row is updated only by a newer last_modified_at.

| Bronze table and column | Silver table and column | Target type | Transformation | Rule ids |
|---|---|---|---|---|
| clients.client_id | clients.client_id | string | Trimmed. Business key: one row kept per key, merged into Silver on this key | DQ_CLI_TRIM, DQ_CLI_MISSING_REQUIRED, DQ_CLI_DUP_EXACT, DQ_CLI_DUP_VERSION |
| clients.birth_year | clients.birth_year | int | Trimmed, read as a whole number | DQ_CLI_TRIM, DQ_CLI_MISSING_REQUIRED, DQ_CLI_INVALID_TYPE |
| clients.sex | clients.sex | string | Trimmed, upper-cased, checked against code list sex | DQ_CLI_CODE_CASE, DQ_CLI_MISSING_REQUIRED, DQ_CLI_INVALID_CODE |
| clients.local_authority_code | clients.local_authority_code | string | Trimmed. Can be empty | DQ_CLI_TRIM |
| clients.last_modified_at | clients.last_modified_at | timestamp | Trimmed, read as YYYY-MM-DD HH:MM:SS in UTC. The latest one wins among rows with the same key; if one of them cannot be read, every copy is quarantined. A stored row is updated only by a newer value | DQ_CLI_TRIM, DQ_CLI_MISSING_REQUIRED, DQ_CLI_INVALID_TYPE, DQ_CLI_DUP_VERSION, DQ_CLI_DUP_BAD_TIMESTAMP |
| clients._extract_id | clients._extract_id | string | Copied | none |
| none | clients._run_id | string | Run that last inserted or updated the row | none |
| episodes.episode_id | episodes.episode_id | string | Trimmed. Business key: one row kept per key, merged into Silver on this key | DQ_EPI_TRIM, DQ_EPI_MISSING_REQUIRED, DQ_EPI_DUP_EXACT, DQ_EPI_DUP_VERSION |
| episodes.client_id | episodes.client_id | string | Trimmed. Must be in Silver clients or in this extract, and that client must not be quarantined in this extract | DQ_EPI_TRIM, DQ_EPI_MISSING_REQUIRED, DQ_EPI_ORPHAN_CLIENT, DQ_EPI_CLIENT_QUARANTINED |
| episodes.service_code | episodes.service_code | string | Trimmed, upper-cased, checked against services | DQ_EPI_CODE_CASE, DQ_EPI_MISSING_REQUIRED, DQ_EPI_INVALID_CODE |
| episodes.referral_date | episodes.referral_date | date | Trimmed, read from YYYY-MM-DD, DD/MM/YYYY or YYYYMMDD | DQ_EPI_TRIM, DQ_EPI_DATE_FORMAT, DQ_EPI_MISSING_REQUIRED, DQ_EPI_INVALID_TYPE, DQ_EPI_DISCHARGE_BEFORE_REFERRAL, DQ_EPI_FUTURE_DATE |
| episodes.referral_source | episodes.referral_source | string | Trimmed, upper-cased, checked against code list referral_source | DQ_EPI_CODE_CASE, DQ_EPI_MISSING_REQUIRED, DQ_EPI_INVALID_CODE |
| episodes.primary_substance | episodes.primary_substance | string | Trimmed, upper-cased, checked against code list substance | DQ_EPI_CODE_CASE, DQ_EPI_MISSING_REQUIRED, DQ_EPI_INVALID_CODE |
| episodes.triage_date | episodes.triage_date | date | Trimmed, read from the three date formats. Can be empty | DQ_EPI_TRIM, DQ_EPI_DATE_FORMAT, DQ_EPI_INVALID_TYPE, DQ_EPI_FUTURE_DATE |
| episodes.discharge_date | episodes.discharge_date | date | Trimmed, read from the three date formats. Can be empty. Not before referral_date | DQ_EPI_TRIM, DQ_EPI_DATE_FORMAT, DQ_EPI_INVALID_TYPE, DQ_EPI_DISCHARGE_BEFORE_REFERRAL, DQ_EPI_FUTURE_DATE |
| episodes.discharge_reason | episodes.discharge_reason | string | Trimmed, upper-cased, checked against code list discharge_reason. Can be empty | DQ_EPI_CODE_CASE, DQ_EPI_INVALID_CODE |
| episodes.last_modified_at | episodes.last_modified_at | timestamp | Trimmed, read as YYYY-MM-DD HH:MM:SS in UTC. The latest one wins among rows with the same key; if one of them cannot be read, every copy is quarantined. A stored row is updated only by a newer value | DQ_EPI_TRIM, DQ_EPI_MISSING_REQUIRED, DQ_EPI_INVALID_TYPE, DQ_EPI_DUP_VERSION, DQ_EPI_DUP_BAD_TIMESTAMP |
| episodes._extract_id | episodes._extract_id | string | Copied | none |
| none | episodes._run_id | string | Run that last inserted or updated the row | none |
| interventions.intervention_id | interventions.intervention_id | string | Trimmed. Business key: one row kept per key, merged into Silver on this key | DQ_INT_TRIM, DQ_INT_MISSING_REQUIRED, DQ_INT_DUP_EXACT, DQ_INT_DUP_VERSION |
| interventions.episode_id | interventions.episode_id | string | Trimmed. Must be in Silver episodes or in this extract, and that episode must not be quarantined in this extract | DQ_INT_TRIM, DQ_INT_MISSING_REQUIRED, DQ_INT_ORPHAN_EPISODE, DQ_INT_EPISODE_QUARANTINED |
| interventions.intervention_type | interventions.intervention_type | string | Trimmed, upper-cased, checked against code list intervention_type | DQ_INT_CODE_CASE, DQ_INT_MISSING_REQUIRED, DQ_INT_INVALID_CODE |
| interventions.start_date | interventions.start_date | date | Trimmed, read from the three date formats | DQ_INT_TRIM, DQ_INT_DATE_FORMAT, DQ_INT_MISSING_REQUIRED, DQ_INT_INVALID_TYPE, DQ_INT_END_BEFORE_START, DQ_INT_FUTURE_DATE |
| interventions.end_date | interventions.end_date | date | Trimmed, read from the three date formats. Can be empty. Not before start_date | DQ_INT_TRIM, DQ_INT_DATE_FORMAT, DQ_INT_INVALID_TYPE, DQ_INT_END_BEFORE_START, DQ_INT_FUTURE_DATE |
| interventions.last_modified_at | interventions.last_modified_at | timestamp | Trimmed, read as YYYY-MM-DD HH:MM:SS in UTC. The latest one wins among rows with the same key; if one of them cannot be read, every copy is quarantined. A stored row is updated only by a newer value | DQ_INT_TRIM, DQ_INT_MISSING_REQUIRED, DQ_INT_INVALID_TYPE, DQ_INT_DUP_VERSION, DQ_INT_DUP_BAD_TIMESTAMP |
| interventions._extract_id | interventions._extract_id | string | Copied | none |
| none | interventions._run_id | string | Run that last inserted or updated the row | none |
| reviews.review_id | reviews.review_id | string | Trimmed. Business key: one row kept per key, merged into Silver on this key | DQ_REV_TRIM, DQ_REV_MISSING_REQUIRED, DQ_REV_DUP_EXACT, DQ_REV_DUP_VERSION |
| reviews.episode_id | reviews.episode_id | string | Trimmed. Must be in Silver episodes or in this extract, and that episode must not be quarantined in this extract | DQ_REV_TRIM, DQ_REV_MISSING_REQUIRED, DQ_REV_ORPHAN_EPISODE, DQ_REV_EPISODE_QUARANTINED |
| reviews.review_date | reviews.review_date | date | Trimmed, read from the three date formats | DQ_REV_TRIM, DQ_REV_DATE_FORMAT, DQ_REV_MISSING_REQUIRED, DQ_REV_INVALID_TYPE, DQ_REV_FUTURE_DATE |
| reviews.review_type | reviews.review_type | string | Trimmed, upper-cased, checked against code list review_type | DQ_REV_CODE_CASE, DQ_REV_MISSING_REQUIRED, DQ_REV_INVALID_CODE |
| reviews.days_used_last_28 | reviews.days_used_last_28 | int | Trimmed, read as a whole number, 0 to 28. Can be empty | DQ_REV_TRIM, DQ_REV_INVALID_TYPE, DQ_REV_DAYS_RANGE |
| reviews.quality_of_life | reviews.quality_of_life | int | Trimmed, read as a whole number, 0 to 20. Can be empty | DQ_REV_TRIM, DQ_REV_INVALID_TYPE, DQ_REV_QOL_RANGE |
| reviews.last_modified_at | reviews.last_modified_at | timestamp | Trimmed, read as YYYY-MM-DD HH:MM:SS in UTC. The latest one wins among rows with the same key; if one of them cannot be read, every copy is quarantined. A stored row is updated only by a newer value | DQ_REV_TRIM, DQ_REV_MISSING_REQUIRED, DQ_REV_INVALID_TYPE, DQ_REV_DUP_VERSION, DQ_REV_DUP_BAD_TIMESTAMP |
| reviews._extract_id | reviews._extract_id | string | Copied | none |
| none | reviews._run_id | string | Run that last inserted or updated the row | none |
| services.service_code | services.service_code | string | Trimmed. Merged into Silver on this key | none |
| services.service_name | services.service_name | string | Trimmed. A stored row is updated when this or local_authority_code differs | none |
| services.local_authority_code | services.local_authority_code | string | Trimmed | none |
| services._extract_id | services._extract_id | string | Copied | none |
| none | services._run_id | string | Run that last inserted or updated the row | none |
| code_lists.list_name | code_lists.list_name | string | Trimmed | none |
| code_lists.code | code_lists.code | string | Trimmed. Merged into Silver on list_name and code | none |
| code_lists.label | code_lists.label | string | Trimmed. A stored row is updated when this differs | none |
| code_lists._extract_id | code_lists._extract_id | string | Copied | none |
| none | code_lists._run_id | string | Run that last inserted or updated the row | none |

## Silver to Gold

Silver is lh_silver.dbo, with dq and ops in lh_silver. Gold is lh_gold.dbo. nb_load_gold rebuilds every Gold table in full on each run.

| Silver table and column | Gold table and column | Target type | Transformation |
|---|---|---|---|
| ops.run_log.extract_id of Succeeded runs and of the current run | report_settings.reporting_date | date | Latest loaded extract id, read as a date |
| nb_load_gold parameter wait_threshold_days | report_settings.wait_threshold_days | int | 21 unless the notebook is run with another value |
| none | report_settings.built_at | timestamp | Time of the rebuild, UTC |
| nb_load_gold parameter run_id | report_settings.built_by_run_id | string | The pipeline run that rebuilt Gold. Empty for a direct run |
| episodes.referral_date, report_settings.reporting_date | dim_date.calendar_date | date | One row per day from the first referral to the reporting date |
| dim_date.calendar_date | dim_date.year, dim_date.month, dim_date.month_start, dim_date.year_month | int, int, date, string | Year, month number, first day of the month, and the month written yyyy-MM |
| services.service_code, services.service_name, services.local_authority_code | dim_service.service_code, dim_service.service_name, dim_service.local_authority_code | string | Copied |
| code_lists.code, code_lists.label where list_name is referral_source | dim_referral_source.referral_source, dim_referral_source.referral_source_label | string | Copied |
| code_lists.code, code_lists.label where list_name is substance | dim_substance.primary_substance, dim_substance.substance_label | string | Copied |
| code_lists.code, code_lists.label where list_name is discharge_reason | dim_discharge_reason.discharge_reason, dim_discharge_reason.discharge_reason_label | string | Copied |
| code_lists.code where list_name is discharge_reason | dim_discharge_reason.is_planned_completion | boolean | True for COMPLETED |
| clients.client_id, clients.sex, clients.birth_year | dim_client.client_id, dim_client.sex, dim_client.birth_year | string, string, int | Copied |
| code_lists.label where list_name is sex | dim_client.sex_label | string | Label of the client's sex code |
| clients.birth_year, episodes.referral_date | dim_client.age_band_at_first_referral | string | Year of the client's first referral minus birth_year, as 18 to 24, 25 to 34, 35 to 44, 45 to 54, 55 to 64 or 65 and over. Not known when the client has no episode |
| episodes.episode_id, client_id, service_code, referral_source, primary_substance, discharge_reason | fact_episode, the same column names | string | Copied. One row per Silver episode |
| episodes.referral_date, triage_date, discharge_date | fact_episode, the same column names | date | Copied |
| episodes.triage_date, episodes.referral_date | fact_episode.wait_days | int | Days from referral to triage. Empty when not yet triaged |
| episodes.discharge_date, episodes.referral_date, report_settings.reporting_date | fact_episode.length_of_stay_days | int | Days from referral to discharge, or to the reporting date while open |
| episodes.discharge_date | fact_episode.is_open | boolean | True when discharge_date is empty |
| episodes.discharge_reason | fact_episode.is_planned_completion | boolean | True for COMPLETED, false otherwise and while open |
| fact_episode.wait_days, report_settings.wait_threshold_days | fact_episode.is_seen_within_threshold | boolean | True when wait_days is at most the threshold. Empty when not yet triaged |
| ops.run_log.run_id of each extract's latest loaded run | fact_extract_load.extract_id, fact_extract_load.run_id | string | One row per loaded extract |
| fact_extract_load.run_id | fact_extract_load.run_started_at | timestamp | Read from the run id, UTC |
| dq.reconciliation.bronze_rows | fact_extract_load.rows_loaded | bigint | Sum over clients, episodes, interventions and reviews for that run |
| dq.rule_results.rows_failed where action is fixed | fact_extract_load.values_fixed | bigint | Sum for that run |
| dq.reconciliation.duplicates_removed | fact_extract_load.rows_removed | bigint | Sum over the four source tables for that run |
| dq.reconciliation.quarantined | fact_extract_load.rows_quarantined | bigint | Sum over the four source tables for that run |

## Public data: Landing to Bronze

nb_load_public_data reads each landed file in lh_bronze Files/public and replaces its table in lh_bronze.reference. Every column of the source sheet is kept as text, named from its header as described in [decisions.md](decisions.md#bronze-column-names-made-from-the-headers). The exact headers are listed in [public-data.md](public-data.md#columns-used). An empty cell is stored as null. Each table also gets these columns.

| Source | Bronze column | Target type | Transformation |
|---|---|---|---|
| Landed file path | _source_file | string | For example Files/public/deprivation_lad/2025-11-17/File_10_-_IoD2025_Local_Authority_District_Summaries__lower-tier__v2.xlsx |
| Publisher's file URL | _source_url | string | Copied from nb_land_public_data |
| Release folder | _source_release | string | For example 2025-11-17 |
| Landed file | _sha256 | string | sha256 of the file, checked against the one nb_land_public_data landed |
| none | _loaded_at | timestamp | Time of the load, UTC |

## Public data: Bronze to Silver

Bronze is lh_bronze.reference and Silver is lh_silver.reference. Silver is replaced on every run, after its checks pass.

| Bronze table and column | Silver table and column | Target type | Transformation |
|---|---|---|---|
| local_authority.lad24cd | local_authority.local_authority_code | string | Trimmed. Must be an English district code (E06, E07, E08 or E09) and appear once |
| local_authority.lad24nm | local_authority.local_authority_name | string | Trimmed |
| local_authority.rgn24cd | local_authority.region_code | string | Trimmed |
| local_authority.rgn24nm | local_authority.region_name | string | Trimmed |
| deprivation_lad.local_authority_district_code_2024 | deprivation_lad.local_authority_code | string | Trimmed. Must be an English district code and appear once. The set of codes must equal the lookup's |
| deprivation_lad.local_authority_district_name_2024 | deprivation_lad.local_authority_name | string | Trimmed |
| deprivation_lad.imd_rank_of_average_score | deprivation_lad.imd_rank_of_average_score | int | Read as a whole number. 1 is the most deprived district |
| deprivation_lad.imd_proportion_of_lsoas_in_most_deprived_10_nationally | deprivation_lad.imd_proportion_lsoas_most_deprived_10pct | double | Read as a number. A fraction, so 0.5 means half the district's LSOAs |
| drug_poisoning_deaths_lad.area_codes | drug_poisoning_deaths_lad.local_authority_code | string | Trimmed. Only rows with an English district code are kept, each once |
| drug_poisoning_deaths_lad.local_authority_district, county_or_unitary_authority | drug_poisoning_deaths_lad.local_authority_name | string | The district column, or the unitary authority column when that is empty. Trimmed |
| Bronze column names | drug_poisoning_deaths_lad.period | string | The latest three year period in the headers, written 2023 to 2025 |
| drug_poisoning_deaths_lad.2023_to_2025_number_of_deaths | drug_poisoning_deaths_lad.deaths | int | Read as a whole number. Must be readable |
| drug_poisoning_deaths_lad.2023_to_2025_rate_per_100_000 | drug_poisoning_deaths_lad.age_standardised_rate_per_100000 | double | Read as a number. Null when ONS gives [x] |
| drug_poisoning_deaths_lad.2023_to_2025_lcl | drug_poisoning_deaths_lad.rate_lower_95_ci | double | Read as a number. Null when ONS gives [x] |
| drug_poisoning_deaths_lad.2023_to_2025_ucl | drug_poisoning_deaths_lad.rate_upper_95_ci | double | Read as a number. Null when ONS gives [x] |
| drug_poisoning_deaths_lad.2023_to_2025_rate_per_100_000, 2023_to_2025_marker | drug_poisoning_deaths_lad.rate_marker | string | [x] when the rate is [x], otherwise the marker, [u] or empty. Any other value stops the run |

## Public data: Silver to Gold

Silver is lh_silver.reference and Gold is lh_gold.dbo. nb_load_public_data replaces dim_local_authority on every run. nb_load_gold does not touch it.

| Silver table and column | Gold table and column | Target type | Transformation |
|---|---|---|---|
| local_authority.local_authority_code, local_authority_name, region_code, region_name | dim_local_authority, the same column names | string | Copied. One row per district in the lookup |
| deprivation_lad.imd_rank_of_average_score | dim_local_authority.imd_rank_of_average_score | int | Joined on local_authority_code |
| deprivation_lad.imd_proportion_lsoas_most_deprived_10pct | dim_local_authority.imd_proportion_lsoas_most_deprived_10pct | double | Joined on local_authority_code |
| drug_poisoning_deaths_lad.period | dim_local_authority.drug_poisoning_period | string | Joined on local_authority_code. Empty when the deaths file has no row under the lookup's code, as for Barnsley and Sheffield |
| drug_poisoning_deaths_lad.deaths | dim_local_authority.drug_poisoning_deaths | int | Joined on local_authority_code |
| drug_poisoning_deaths_lad.age_standardised_rate_per_100000 | dim_local_authority.drug_poisoning_rate_per_100000 | double | Joined on local_authority_code |
| drug_poisoning_deaths_lad.rate_lower_95_ci | dim_local_authority.drug_poisoning_rate_lower_95_ci | double | Joined on local_authority_code |
| drug_poisoning_deaths_lad.rate_upper_95_ci | dim_local_authority.drug_poisoning_rate_upper_95_ci | double | Joined on local_authority_code |
| drug_poisoning_deaths_lad.rate_marker | dim_local_authority.drug_poisoning_rate_marker | string | Joined on local_authority_code |
