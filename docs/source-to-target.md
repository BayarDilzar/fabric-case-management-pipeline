# Source to target: Bronze to Silver

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
