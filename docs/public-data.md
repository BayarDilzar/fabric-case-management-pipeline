# Public data

Three official public datasets put each fictional service next to real figures for its local authority district: deprivation, drug poisoning deaths, and the district's name and region. They are joined on district code.

## Sources and licences

I read each source's page and recorded its licence on 26 November 2026, before downloading any file.

### Deprivation: English Indices of Deprivation 2025

- **Publisher:** Ministry of Housing, Communities and Local Government (MHCLG).
- **Title:** English indices of deprivation 2025, File 10: Local Authority District summaries - lower tier.
- **Edition:** IoD 2025, version 2 of File 10.
- **Release date:** published 30 October 2025. Files 10, 11 and 14 were reissued as v2 on 17 November 2025, after an ONS lookup error placed one small area in the wrong district.
- **Page:** https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025
- **File:** https://assets.publishing.service.gov.uk/media/6917412ebc34c86ce4e6e7fc/File_10_-_IoD2025_Local_Authority_District_Summaries__lower-tier__v2.xlsx
- **Licence:** Open Government Licence v3.0. The page footer says "All content is available under the Open Government Licence v3.0, except where otherwise stated", and the statistical release says "This publication is licensed under the terms of the Open Government Licence v3.0 except where otherwise stated." Neither names an exception for this file.
- **Attribution:** the page gives no wording of its own, so the licence's default applies: "Contains public sector information licensed under the Open Government Licence v3.0."

### Drug poisoning deaths: ONS deaths related to drug poisoning by local authority

- **Publisher:** Office for National Statistics (ONS).
- **Title:** Deaths related to drug poisoning by local authority, England and Wales.
- **Edition:** the current edition, file 2025localauthorities.xlsx, deaths registered up to 2025.
- **Release date:** 4 November 2026. The next release is "To be announced".
- **Page:** https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/deaths/datasets/drugmisusedeathsbylocalauthority
- **File:** https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/deaths/datasets/drugmisusedeathsbylocalauthority/current/2025localauthorities.xlsx
- **Licence:** Open Government Licence v3.0. The page footer says "All content is available under the Open Government Licence v3.0, except where otherwise stated". The ONS terms and conditions say "Most content on this website is subject to Crown copyright protection and is published under the Open Government Licence (OGL)"; the exemptions they list are third-party photographs, illustrations and videos.
- **Attribution:** the page gives no wording of its own, but the workbook's cover sheet does: "Users should include a source accreditation to ONS - Source: Office for National Statistics licensed under the Open Government Licence." The cover sheet also says "You may re-use this information (not including logos) free of charge in any format or medium, under the terms of the Open Government Licence."
- **Note:** the file link points at "current", so it will serve a different file after the next release. The sha256 of the landed file is recorded under Lineage.

### Local authorities: ONS Open Geography Portal lookup

- **Publisher:** Office for National Statistics (ONS), Open Geography Portal.
- **Title:** Local Authority District to Region (December 2024) Lookup in EN.
- **Edition:** December 2024, districts and regions in England as at 31 December 2024. Fields LAD24CD, LAD24NM, RGN24CD and RGN24NM. IoD 2025 codes its districts at 2024 boundaries, so this is the edition that matches it.
- **Release date:** 28 November 2024, the date the portal gives for the item's creation and its last data edit.
- **Page:** https://geoportal.statistics.gov.uk/datasets/3959874c514b470e9dd160acdc00c97a/about
- **File:** https://geoportal.statistics.gov.uk/api/download/v1/items/3959874c514b470e9dd160acdc00c97a/csv?layers=0
- **Licence:** Open Government Licence v3.0. The item's licence field links to https://www.ons.gov.uk/methodology/geography/licences, which says "Lookup products are supplied under the Open Government Licence."
- **Attribution:** the same page says "You must use the following copyright statement when you reproduce or use this material: Source: Office for National Statistics licensed under the Open Government Licence v.3.0".

## Lineage

pl_load_public_data runs two notebooks. Each layer has its own table per source.

| Layer | Where | Written by | What happens |
|---|---|---|---|
| Landing | lh_bronze, `Files/public/<source>/<release>/<file>` | nb_land_public_data | The file as downloaded inside Fabric, unchanged. A file already landed for that release is kept, and a download with a different sha256 stops the run before anything is written. |
| Bronze | lh_bronze.reference.deprivation_lad, drug_poisoning_deaths_lad, local_authority | nb_load_public_data | Every data row of the source sheet, every column as text, plus _source_file, _source_url, _source_release, _sha256 and _loaded_at. Replaced on every run. |
| Silver | lh_silver.reference.local_authority, deprivation_lad, drug_poisoning_deaths_lad | nb_load_public_data | Trimmed and typed. English district codes only (E06, E07, E08, E09). A rate ONS did not calculate is null, with its marker kept. |
| Gold | lh_gold.dbo.dim_local_authority | nb_load_public_data | One row per district in the lookup, with its region, deprivation and drug poisoning figures. Joins to dim_service on local_authority_code. |

### Landed files

| Source | Release folder | File | Bytes | sha256 |
|---|---|---|---|---|
| deprivation_lad | 2025-11-17 | File_10_-_IoD2025_Local_Authority_District_Summaries__lower-tier__v2.xlsx | 226,470 | 6c38a2fd3998e0caf76a3ef8da331613d52d6d0320065ccef346103fd9770a7e |
| drug_poisoning_deaths_lad | 2026-11-04 | 2025localauthorities.xlsx | 1,017,597 | 82646e646f4ec702515c2aa9cdb7eb491efbddccbbdf6dfe2015940460f4890a |
| local_authority | 2024-11-28 | Local_Authority_District_to_Region_(December_2024)_Lookup_in_EN.csv | 14,372 | 73672e80f312c128de148d593c0bc07b50e74ec016e840814fa166664d47ef4a |

All three were landed on 26 November 2026. The same sha256 came from a download on my machine.

### Columns used

The headers below are exact, including the trailing spaces and the line breaks (`\n`) inside the ONS header cells. Bronze keeps every column; these are the ones Silver uses.

- **Deprivation**, sheet IMD, headers on row 1, 296 data rows: `Local Authority District code (2024)`, `Local Authority District name (2024)`, `IMD - Rank of average score `, `IMD - Proportion of LSOAs in most deprived 10% nationally `.
- **Drug poisoning deaths**, sheet Table 3 (all drug poisoning, persons), headers on row 6, 358 data rows: `Area Codes`, `County or Unitary Authority \n[note 7]`, `Local Authority District \n[note 7]`, `2023 to 2025 \nNumber of deaths`, `2023 to 2025 \nRate per 100,000 \n[note 4]`, `2023 to 2025 \nMarker \n[note 6]`, `2023 to 2025 \nLCL \n[note 5]`, `2023 to 2025 \nUCL \n[note 5]`.
- **Local authorities**, CSV with a byte order mark, headers on row 1, 296 data rows: `LAD24CD`, `LAD24NM`, `RGN24CD`, `RGN24NM`.

A Bronze column name is the header with any `[note n]` removed, in lower case, with each run of other characters turned into one underscore. For example `2023 to 2025 \nRate per 100,000 \n[note 4]` becomes `2023_to_2025_rate_per_100_000`.

### Row counts

| Table | Rows |
|---|---|
| lh_bronze.reference.deprivation_lad | 296 |
| lh_bronze.reference.drug_poisoning_deaths_lad | 358, which includes England, Wales, regions and counties |
| lh_bronze.reference.local_authority | 296 |
| lh_silver.reference.local_authority | 296 |
| lh_silver.reference.deprivation_lad | 296 |
| lh_silver.reference.drug_poisoning_deaths_lad | 296 |
| lh_gold.dbo.dim_local_authority | 296 |

## How to rerun

Run pl_load_public_data by hand. It has no parameters and no schedule. The steps and checks are in docs/runbook.md.

- A rerun downloads each file again and compares it with the file landed for that release. If they are the same, Landing is left alone, and Bronze, Silver and Gold are rebuilt with the same row counts. Two runs on 26 November 2026 gave the same counts in all seven tables.
- If a publisher now serves a different file, the run stops at Land public data with both sha256 values, and nothing is written. This is expected for the ONS file after its next release, because its link points at "current".
- To load a new edition, check its licence and record it above first. Then change that source's entry in SOURCES in nb_land_public_data to the new release folder, URL and file name, and run the pipeline. The old file stays in Landing under its own release folder. If the new file has a different layout, the load stops at the header check and READ in nb_load_public_data needs the new sheet or header row.

## Limits

- **The treatment data is synthetic.** The six services and their clients are fictional, so any join between them and these figures is a demonstration of the pipeline only. It says nothing about real services or real people.
- **IoD ranks are relative.** Rank 1 is the most deprived of the 296 districts and 296 the least. A rank shows order, not how much more deprived one district is than another. The proportion of small areas (LSOAs) in the most deprived 10% nationally is also relative to the rest of England. MHCLG says the indices are not a time series, so IoD 2025 ranks cannot be compared with IoD 2019 ranks.
- **Death figures are three year totals, and some are small numbers.** The figures are deaths registered in 2023 to 2025, by year of registration, not year of death. A registration can come months or years after the death. ONS does not calculate the rate below 10 deaths, which is marked `[x]`; that applies to 7 of the 296 districts, and their rate and limits are null, not 0. Rates from 10 to 19 deaths are marked `[u]` for low reliability; that applies to 48 districts.
- **The deaths are all drug poisoning.** Table 3 counts every drug poisoning death, including those from medicines that are not controlled drugs. ONS's headline drug misuse measure is a subset of it and is not loaded. The two cannot be added together.
- **Boundary years can differ.** IoD 2025 and the lookup use 2024 district codes. The ONS file uses "the latest available postcode boundaries (August 2026)". Barnsley and Sheffield have new codes in the ONS file (E08000038 and E08000039, against E08000016 and E08000019), so dim_local_authority has no drug poisoning figures for them. The codes are not remapped. I found no ONS statement of why the codes changed, so I do not know whether their boundaries moved.
- **Cornwall and the Isles of Scilly are separate.** All three files list them as two districts, E06000052 and E06000053. No source combines them, so nothing was remapped. The Isles of Scilly have 0 deaths in 2023 to 2025 and no rate.
- **England only.** IoD covers England only. The Welsh rows in the ONS file stay in Bronze and are not carried into Silver.
- **Area figures say nothing about individuals.** A district's deprivation rank or death rate describes the district as a whole. It cannot be applied to any client, real or fictional, who lives there.
