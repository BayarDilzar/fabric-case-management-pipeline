"""Test helpers. Expected values come from the spec, not from the generator."""

import csv
import re
from collections import defaultdict
from datetime import date, datetime, time

SPEC_SERVICES = {
    "S01": "E06000009",
    "S02": "E06000002",
    "S03": "E06000043",
    "S04": "E08000035",
    "S05": "E09000023",
    "S06": "E06000052",
}


SPEC_CODES = {
    "sex": {"F", "M", "U"},
    "referral_source": {"SELF", "GP", "HEALTH", "CJS", "FAMILY"},
    "substance": {"OPIATE", "CRACK", "COCAINE", "ALCOHOL", "CANNABIS", "OTHER"},
    "intervention_type": {"PHARMA", "PSYCHO", "RECOVERY"},
    "discharge_reason": {"COMPLETED", "TRANSFERRED", "DROPPED_OUT", "DECLINED", "DIED"},
    "review_type": {"START", "REVIEW", "EXIT"},
}
CODE_FIELDS = {
    ("clients", "sex"): "sex",
    ("episodes", "referral_source"): "referral_source",
    ("episodes", "primary_substance"): "substance",
    ("episodes", "discharge_reason"): "discharge_reason",
    ("interventions", "intervention_type"): "intervention_type",
    ("reviews", "review_type"): "review_type",
}
REQUIRED = {
    "clients": ["client_id", "birth_year", "sex", "last_modified_at"],
    "episodes": [
        "episode_id",
        "client_id",
        "service_code",
        "referral_date",
        "referral_source",
        "primary_substance",
        "last_modified_at",
    ],
    "interventions": ["intervention_id", "episode_id", "intervention_type", "start_date", "last_modified_at"],
    "reviews": ["review_id", "episode_id", "review_date", "review_type", "last_modified_at"],
}
DATE_FIELDS = {
    "clients": [],
    "episodes": ["referral_date", "triage_date", "discharge_date"],
    "interventions": ["start_date", "end_date"],
    "reviews": ["review_date"],
}
TABLES = ("clients", "episodes", "interventions", "reviews")
KEYS = {"clients": "client_id", "episodes": "episode_id", "interventions": "intervention_id", "reviews": "review_id"}
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = [dict(zip(header, values)) for values in reader]
    return header, rows


def as_date(value):
    return date.fromisoformat(value) if value else None


def episodes_by_client(view):
    grouped = defaultdict(list)
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        grouped[row["client_id"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: (row["referral_date"], row["episode_id"]))
    return grouped


def rule_r02_episode_parents(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["client_id"] not in view["clients"]:
            yield f"R02 {key}: client {row['client_id']} missing"
        if row["service_code"] not in SPEC_SERVICES:
            yield f"R02 {key}: service {row['service_code']} unknown"


def rule_r07_discharge_after_referral(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["discharge_date"] and as_date(row["discharge_date"]) < as_date(row["referral_date"]):
            yield f"R07 {key}: discharged before referral"


def rule_r11_triage_after_referral(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["triage_date"] and as_date(row["triage_date"]) < as_date(row["referral_date"]):
            yield f"R11 {key}: triaged before referral"


def rule_r13_discharge_date_and_reason_together(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if bool(row["discharge_date"]) != bool(row["discharge_reason"]):
            yield f"R13 {key}: discharge date and reason do not match"


def rule_r14_episodes_do_not_overlap(view, cutoff):
    for client_id, rows in sorted(episodes_by_client(view).items()):
        for earlier, later in zip(rows, rows[1:]):
            if not earlier["discharge_date"]:
                yield f"R14 {client_id}: {earlier['episode_id']} open when {later['episode_id']} starts"
            elif as_date(earlier["discharge_date"]) >= as_date(later["referral_date"]):
                yield f"R14 {client_id}: {earlier['episode_id']} overlaps {later['episode_id']}"


def rule_r15_age_at_referral(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        client = view["clients"].get(row["client_id"])
        if client is None:
            continue
        age = as_date(row["referral_date"]).year - int(client["birth_year"])
        if not 18 <= age <= 80:
            yield f"R15 {key}: age {age} at referral"


def rule_died_is_final(view, cutoff):
    # Not in the spec's table, but a client who died cannot come back.
    for client_id, rows in sorted(episodes_by_client(view).items()):
        for row in rows[:-1]:
            if row["discharge_reason"] == "DIED":
                yield f"DIED {client_id}: episode after {row['episode_id']}"


def children(view, table):
    grouped = defaultdict(list)
    for key in sorted(view[table]):
        grouped[view[table][key]["episode_id"]].append(view[table][key])
    return grouped


def rule_r03_intervention_and_review_parents(view, cutoff):
    for table in ("interventions", "reviews"):
        for key in sorted(view[table]):
            if view[table][key]["episode_id"] not in view["episodes"]:
                yield f"R03 {key}: episode missing"


def rule_r08_end_after_start(view, cutoff):
    for key in sorted(view["interventions"]):
        row = view["interventions"][key]
        if row["end_date"] and as_date(row["end_date"]) < as_date(row["start_date"]):
            yield f"R08 {key}: ends before it starts"


def rule_r12_interventions_inside_episode(view, cutoff):
    for key in sorted(view["interventions"]):
        row = view["interventions"][key]
        episode = view["episodes"].get(row["episode_id"])
        if episode is None:
            continue
        last_day = as_date(episode["discharge_date"]) or cutoff
        if not as_date(episode["referral_date"]) <= as_date(row["start_date"]) <= last_day:
            yield f"R12 {key}: starts outside its episode"
        if episode["discharge_date"] and not row["end_date"]:
            yield f"R12 {key}: still open in a closed episode"
        if row["end_date"] and as_date(row["end_date"]) > last_day:
            yield f"R12 {key}: ends after its episode"


def rule_r09_score_ranges(view, cutoff):
    for key in sorted(view["reviews"]):
        row = view["reviews"][key]
        if row["days_used_last_28"] and not 0 <= int(row["days_used_last_28"]) <= 28:
            yield f"R09 {key}: days_used_last_28 out of range"
        if row["quality_of_life"] and not 0 <= int(row["quality_of_life"]) <= 20:
            yield f"R09 {key}: quality_of_life out of range"


def rule_r12_reviews_inside_episode(view, cutoff):
    for key in sorted(view["reviews"]):
        row = view["reviews"][key]
        episode = view["episodes"].get(row["episode_id"])
        if episode is None:
            continue
        last_day = as_date(episode["discharge_date"]) or cutoff
        if not as_date(episode["referral_date"]) <= as_date(row["review_date"]) <= last_day:
            yield f"R12 {key}: review outside its episode"


def rule_review_pattern(view, cutoff):
    # START opens the reviews, EXIT closes a completed or transferred episode on its discharge day.
    treated = children(view, "interventions")
    for episode_id, rows in sorted(children(view, "reviews").items()):
        episode = view["episodes"].get(episode_id)
        if episode is None:
            continue
        rows = sorted(rows, key=lambda row: (row["review_date"], row["review_id"]))
        kinds = [row["review_type"] for row in rows]
        if not treated[episode_id]:
            yield f"REVIEWS {episode_id}: reviews without treatment"
        if kinds[0] != "START" or kinds.count("START") != 1:
            yield f"REVIEWS {episode_id}: START is not the single first review"
        if "EXIT" in kinds:
            if kinds[-1] != "EXIT" or kinds.count("EXIT") != 1:
                yield f"REVIEWS {episode_id}: EXIT is not the single last review"
            if episode["discharge_reason"] not in ("COMPLETED", "TRANSFERRED"):
                yield f"REVIEWS {episode_id}: EXIT after {episode['discharge_reason'] or 'no discharge'}"
            elif rows[-1]["review_date"] != episode["discharge_date"]:
                yield f"REVIEWS {episode_id}: EXIT not on the discharge date"


def rule_treatment_matches_discharge_reason(view, cutoff):
    # DECLINED means the client never started treatment; any other closure means they did.
    treated = children(view, "interventions")
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["discharge_reason"] == "DECLINED" and treated[key]:
            yield f"TREATMENT {key}: declined but has interventions"
        if row["discharge_reason"] not in ("", "DECLINED") and not treated[key]:
            yield f"TREATMENT {key}: closed as {row['discharge_reason']} with no intervention"
        if not row["triage_date"] and treated[key]:
            yield f"TREATMENT {key}: treated before triage"
        if len(treated[key]) > 3:
            yield f"TREATMENT {key}: more than three interventions"


def rule_r04_codes_in_lists(view, cutoff):
    for (table, column), list_name in sorted(CODE_FIELDS.items()):
        for key in sorted(view[table]):
            value = view[table][key][column]
            if value and value not in SPEC_CODES[list_name]:
                yield f"R04 {key}: {column} {value!r} not in {list_name}"
    for key in sorted(view["clients"]):
        district = view["clients"][key]["local_authority_code"]
        if district and district not in SPEC_SERVICES.values():
            yield f"R04 {key}: district {district!r} not served"


def rule_r05_required_fields(view, cutoff):
    for table in TABLES:
        for key in sorted(view[table]):
            for column in REQUIRED[table]:
                if not view[table][key][column].strip():
                    yield f"R05 {key}: {column} empty"


def rule_r06_r10_dates(view, cutoff):
    for table in TABLES:
        for key in sorted(view[table]):
            for column in DATE_FIELDS[table]:
                value = view[table][key][column]
                if not value:
                    continue
                if not ISO_DATE.fullmatch(value):
                    yield f"R06 {key}: {column} {value!r} not YYYY-MM-DD"
                elif as_date(value) > cutoff:
                    yield f"R10 {key}: {column} after the cut-off"


def rule_r16_last_modified(view, cutoff):
    latest = datetime.combine(cutoff, time(23, 59, 59))
    for table in TABLES:
        for key in sorted(view[table]):
            row = view[table][key]
            if not TIMESTAMP.fullmatch(row["last_modified_at"]):
                yield f"R16 {key}: last_modified_at {row['last_modified_at']!r} not a timestamp"
                continue
            modified = datetime.fromisoformat(row["last_modified_at"])
            if modified > latest:
                yield f"R16 {key}: modified after the cut-off"
            for column in DATE_FIELDS[table]:
                if row[column] and ISO_DATE.fullmatch(row[column]) and modified.date() < as_date(row[column]):
                    yield f"R16 {key}: modified before its {column}"


RULES = [
    rule_r04_codes_in_lists,
    rule_r05_required_fields,
    rule_r06_r10_dates,
    rule_r16_last_modified,
    rule_r02_episode_parents,
    rule_r03_intervention_and_review_parents,
    rule_r08_end_after_start,
    rule_r09_score_ranges,
    rule_r12_interventions_inside_episode,
    rule_r12_reviews_inside_episode,
    rule_r07_discharge_after_referral,
    rule_r11_triage_after_referral,
    rule_r13_discharge_date_and_reason_together,
    rule_r14_episodes_do_not_overlap,
    rule_r15_age_at_referral,
    rule_died_is_final,
]
# How clean source data is shaped. Silver can break these legitimately: a quarantined
# intervention leaves its episode looking untreated.
SHAPE_RULES = [rule_review_pattern, rule_treatment_matches_discharge_reason]


def check_rules(view, cutoff):
    return [problem for rule in RULES for problem in rule(view, cutoff)]


def check_shape(view, cutoff):
    return [problem for rule in SHAPE_RULES for problem in rule(view, cutoff)]


DEFECT_COLUMNS = [
    "defect_id",
    "extract_date",
    "file_name",
    "record_key",
    "field",
    "defect_type",
    "injected_value",
    "expected_outcome",
    "expected_value",
    "expected_reason",
]


def extract_dates(out):
    return sorted(path.name for path in (out / "extracts").iterdir())


def defect_lines(out, extract_date):
    header, rows = read_csv(out / "manifests" / extract_date / "defects.csv")
    assert header == DEFECT_COLUMNS
    return rows


def listed_defects(out, extract_date):
    return {
        (line["file_name"], line["record_key"], line["field"], line["defect_type"], line["injected_value"])
        for line in defect_lines(out, extract_date)
    }


def detect_duplicates(file_name, key_column, rows):
    found = set()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[key_column]].append(row)
    for key, group in grouped.items():
        if len(group) == 1:
            continue
        if len(group) == 2 and group[0] == group[1]:
            found.add((file_name, key, "", "DUP_EXACT", ""))
        elif len(group) == 2:
            older = min(row["last_modified_at"] for row in group)
            found.add((file_name, key, "", "DUP_VERSION", older))
        else:
            found.add((file_name, key, "", "UNEXPECTED_DUPLICATES", str(len(group))))
    return found


def detect_row_defects(table, row):
    file_name, key = f"{table}.csv", row[KEYS[table]]
    for column in REQUIRED[table]:
        if not row[column].strip():
            yield (file_name, key, column, "MISSING_REQUIRED", row[column])
    for column in DATE_FIELDS[table]:
        if row[column] and not ISO_DATE.fullmatch(row[column]):
            yield (file_name, key, column, "DATE_FORMAT", row[column])
    lists = {column: SPEC_CODES[name] for (owner, column), name in CODE_FIELDS.items() if owner == table}
    if table == "episodes":
        lists["service_code"] = set(SPEC_SERVICES)
    for column, codes in sorted(lists.items()):
        value = row[column]
        if value and value not in codes:
            kind = "CODE_CASE" if value.strip().upper() in codes else "CODE_UNKNOWN"
            yield (file_name, key, column, kind, value)


PARENTS = {"episodes": ("client_id", "clients"), "interventions": ("episode_id", "episodes"), "reviews": ("episode_id", "episodes")}


def keys_so_far(out, extract_date, table):
    """Every id the files have carried for a table, up to and including this extract."""
    keys = set()
    for earlier in extract_dates(out):
        if earlier <= extract_date:
            keys |= {row[KEYS[table]] for row in read_csv(out / "extracts" / earlier / f"{table}.csv")[1]}
    return keys


def detect_defects(out, extract_date):
    """Find defects in one extract's files using only the spec's checks, not the manifest."""
    found = set()
    folder = out / "extracts" / extract_date
    for table in TABLES:
        file_name = f"{table}.csv"
        _, rows = read_csv(folder / file_name)
        found |= detect_duplicates(file_name, KEYS[table], rows)
        parent = PARENTS.get(table)
        parent_keys = keys_so_far(out, extract_date, parent[1]) if parent else set()
        for row in rows:
            found |= set(detect_row_defects(table, row))
            if parent and row[parent[0]] not in parent_keys:
                found.add((file_name, row[KEYS[table]], parent[0], "ORPHAN", row[parent[0]]))
    return found


def load_extract(out, extract_date, previous):
    """Apply one extract to a copy of the Silver view, doing what the manifest says Silver should do."""
    view = {table: dict(previous.get(table, {})) for table in TABLES}
    lines = defect_lines(out, extract_date)
    for table in TABLES:
        file_name = f"{table}.csv"
        _, rows = read_csv(out / "extracts" / extract_date / file_name)
        listed = [line for line in lines if line["file_name"] == file_name]
        for line in listed:
            matches = [i for i, row in enumerate(rows) if row[KEYS[table]] == line["record_key"]]
            if line["defect_type"] == "DUP_EXACT":
                assert len(matches) == 2 and rows[matches[0]] == rows[matches[1]], line
                del rows[matches[1]]
            elif line["defect_type"] == "DUP_VERSION":
                older = [i for i in matches if rows[i]["last_modified_at"] == line["injected_value"]]
                newer = [i for i in matches if rows[i]["last_modified_at"] > line["injected_value"]]
                assert len(matches) == 2 and len(older) == 1 and len(newer) == 1, line
                del rows[older[0]]
            elif line["expected_outcome"] == "QUARANTINED":
                assert len(matches) == 1, line
                del rows[matches[0]]
            elif line["expected_outcome"] == "CORRECTED":
                assert len(matches) == 1 and rows[matches[0]][line["field"]] == line["injected_value"], line
                rows[matches[0]][line["field"]] = line["expected_value"]
        for row in rows:
            key = row[KEYS[table]]
            loaded = view[table].get(key)
            if loaded is None or row["last_modified_at"] > loaded["last_modified_at"]:
                view[table][key] = row
            else:
                assert row == loaded, f"{key}: same or older timestamp but different content"
    return view


def silver_views(out):
    view = {}
    for extract_date in extract_dates(out):
        view = load_extract(out, extract_date, view)
        yield date.fromisoformat(extract_date), view
