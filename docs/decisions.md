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
