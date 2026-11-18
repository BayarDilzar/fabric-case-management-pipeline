"""Values fixed by notes/generator-spec.md."""

from datetime import date

START_DATE = date(2023, 4, 1)
# Historical extract, three weeks, then the broken extract.
CUTOFFS = [
    date(2026, 10, 25),
    date(2026, 11, 1),
    date(2026, 11, 8),
    date(2026, 11, 15),
    date(2026, 11, 22),
]

SERVICES = [
    ("S01", "Blackpool community service", "E06000009"),
    ("S02", "Middlesbrough community service", "E06000002"),
    ("S03", "Brighton and Hove community service", "E06000043"),
    ("S04", "Leeds community service", "E08000035"),
    ("S05", "Lewisham community service", "E09000023"),
    ("S06", "Cornwall community service", "E06000052"),
]
SERVICE_DISTRICT = {code: district for code, _, district in SERVICES}

CODE_LISTS = [
    ("sex", "F", "Female"),
    ("sex", "M", "Male"),
    ("sex", "U", "Not stated"),
    ("referral_source", "SELF", "Self-referral"),
    ("referral_source", "GP", "GP"),
    ("referral_source", "HEALTH", "Other health or social care"),
    ("referral_source", "CJS", "Criminal justice"),
    ("referral_source", "FAMILY", "Family, friend or carer"),
    ("substance", "OPIATE", "Opiates, for example heroin"),
    ("substance", "CRACK", "Crack cocaine"),
    ("substance", "COCAINE", "Powder cocaine"),
    ("substance", "ALCOHOL", "Alcohol"),
    ("substance", "CANNABIS", "Cannabis"),
    ("substance", "OTHER", "Other drug"),
    ("intervention_type", "PHARMA", "Pharmacological (prescribing)"),
    ("intervention_type", "PSYCHO", "Psychosocial (talking support)"),
    ("intervention_type", "RECOVERY", "Recovery support"),
    ("discharge_reason", "COMPLETED", "Treatment completed"),
    ("discharge_reason", "TRANSFERRED", "Transferred to another provider"),
    ("discharge_reason", "DROPPED_OUT", "Dropped out"),
    ("discharge_reason", "DECLINED", "Declined treatment"),
    ("discharge_reason", "DIED", "Died"),
    ("review_type", "START", "Start of treatment"),
    ("review_type", "REVIEW", "Six-monthly review"),
    ("review_type", "EXIT", "At discharge"),
]

COLUMNS = {
    "clients": ["client_id", "birth_year", "sex", "local_authority_code", "last_modified_at"],
    "episodes": [
        "episode_id",
        "client_id",
        "service_code",
        "referral_date",
        "referral_source",
        "primary_substance",
        "triage_date",
        "discharge_date",
        "discharge_reason",
        "last_modified_at",
    ],
    "interventions": [
        "intervention_id",
        "episode_id",
        "intervention_type",
        "start_date",
        "end_date",
        "last_modified_at",
    ],
    "reviews": [
        "review_id",
        "episode_id",
        "review_date",
        "review_type",
        "days_used_last_28",
        "quality_of_life",
        "last_modified_at",
    ],
}
KEYS = {"clients": "client_id", "episodes": "episode_id", "interventions": "intervention_id", "reviews": "review_id"}

# Shares from section 4 of the spec, as (code, weight).
SERVICE_SHARES = [("S01", 20), ("S02", 15), ("S03", 10), ("S04", 25), ("S05", 15), ("S06", 15)]
SEX_SHARES = [("M", 64), ("F", 34), ("U", 2)]
SUBSTANCE_SHARES = [("ALCOHOL", 35), ("OPIATE", 30), ("CRACK", 10), ("COCAINE", 10), ("CANNABIS", 10), ("OTHER", 5)]
REFERRAL_SOURCE_SHARES = [("SELF", 45), ("CJS", 20), ("GP", 15), ("HEALTH", 12), ("FAMILY", 8)]
TREATED_DISCHARGE_SHARES = [("COMPLETED", 50), ("DROPPED_OUT", 33), ("TRANSFERRED", 12), ("DIED", 5)]
