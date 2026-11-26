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
