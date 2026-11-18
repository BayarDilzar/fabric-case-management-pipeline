from collections import Counter
from datetime import date

import pytest

from tests.support import (
    KEYS,
    PARENTS,
    check_rules,
    defect_lines,
    detect_defects,
    extract_dates,
    listed_defects,
    read_csv,
    silver_views,
)

SEEDS = [2026, 1, 7, 99, 12345]
HISTORY = "2026-10-25"
CATALOGUE = {
    "DUP_EXACT": ("REMOVED", ""),
    "DUP_VERSION": ("REMOVED", ""),
    "MISSING_REQUIRED": ("QUARANTINED", "MISSING_REQUIRED"),
    "DATE_FORMAT": ("CORRECTED", ""),
    "CODE_CASE": ("CORRECTED", ""),
    "CODE_UNKNOWN": ("QUARANTINED", "INVALID_CODE"),
    "ORPHAN": ("QUARANTINED", "ORPHAN"),
    "RULE_DISCHARGE_BEFORE_REFERRAL": ("QUARANTINED", "RULE_R07"),
    "RULE_END_BEFORE_START": ("QUARANTINED", "RULE_R08"),
    "RULE_DAYS_RANGE": ("QUARANTINED", "RULE_R09"),
    "RULE_FUTURE_DATE": ("QUARANTINED", "RULE_R10"),
}
HISTORY_COUNTS = {
    ("DUP_EXACT", "clients.csv", ""): 20,
    ("DUP_EXACT", "episodes.csv", ""): 15,
    ("DUP_EXACT", "interventions.csv", ""): 25,
    ("DUP_EXACT", "reviews.csv", ""): 30,
    ("DUP_VERSION", "episodes.csv", ""): 10,
    ("DUP_VERSION", "interventions.csv", ""): 10,
    ("MISSING_REQUIRED", "episodes.csv", "referral_date"): 8,
    ("MISSING_REQUIRED", "interventions.csv", "start_date"): 10,
    ("MISSING_REQUIRED", "reviews.csv", "review_date"): 12,
    ("DATE_FORMAT", "episodes.csv", "referral_date"): 15,
    ("DATE_FORMAT", "episodes.csv", "discharge_date"): 15,
    ("DATE_FORMAT", "interventions.csv", "start_date"): 15,
    ("DATE_FORMAT", "reviews.csv", "review_date"): 15,
    ("CODE_CASE", "clients.csv", "sex"): 10,
    ("CODE_CASE", "episodes.csv", "referral_source"): 15,
    ("CODE_CASE", "interventions.csv", "intervention_type"): 10,
    ("CODE_UNKNOWN", "episodes.csv", "primary_substance"): 8,
    ("CODE_UNKNOWN", "episodes.csv", "service_code"): 4,
    ("CODE_UNKNOWN", "interventions.csv", "intervention_type"): 6,
    ("ORPHAN", "episodes.csv", "client_id"): 6,
    ("ORPHAN", "interventions.csv", "episode_id"): 12,
    ("ORPHAN", "reviews.csv", "episode_id"): 15,
    ("RULE_DISCHARGE_BEFORE_REFERRAL", "episodes.csv", "discharge_date"): 6,
    ("RULE_END_BEFORE_START", "interventions.csv", "end_date"): 8,
    ("RULE_DAYS_RANGE", "reviews.csv", "days_used_last_28"): 7,
    ("RULE_FUTURE_DATE", "reviews.csv", "review_date"): 5,
}


@pytest.mark.parametrize("seed", SEEDS)
def test_manifest_lists_exactly_the_defects_found_in_the_files(seed, output_for):
    out = output_for(seed)

    for extract_date in extract_dates(out):
        assert detect_defects(out, extract_date) == listed_defects(out, extract_date)


@pytest.mark.parametrize("seed", SEEDS)
def test_silver_after_each_extract_obeys_every_rule(seed, output_for):
    for cutoff, view in silver_views(output_for(seed)):
        assert check_rules(view, cutoff) == []


def test_historical_defect_counts_match_the_spec(output_for):
    lines = defect_lines(output_for(2026), HISTORY)

    counts = Counter((line["defect_type"], line["file_name"], line["field"]) for line in lines)

    assert counts == HISTORY_COUNTS


@pytest.mark.parametrize("seed", SEEDS)
def test_each_defect_has_the_catalogue_outcome_and_hits_its_own_row(seed, output_for):
    out = output_for(seed)

    for extract_date in extract_dates(out):
        lines = defect_lines(out, extract_date)
        rows_hit = Counter((line["file_name"], line["record_key"]) for line in lines if line["record_key"])
        assert max(rows_hit.values(), default=1) == 1
        for number, line in enumerate(lines, start=1):
            assert line["defect_id"] == f"D-{extract_date.replace('-', '')}-{number:04d}"
            assert line["extract_date"] == extract_date
            assert (line["expected_outcome"], line["expected_reason"]) == CATALOGUE[line["defect_type"]]


def test_older_versions_sit_next_to_the_newer_row_on_either_side(output_for):
    out = output_for(2026)
    sides = Counter()

    for line in defect_lines(out, HISTORY):
        if line["defect_type"] != "DUP_VERSION":
            continue
        table = line["file_name"][: -len(".csv")]
        _, rows = read_csv(out / "extracts" / HISTORY / line["file_name"])
        first, second = [i for i, row in enumerate(rows) if row[KEYS[table]] == line["record_key"]]
        assert second == first + 1
        sides["before" if rows[first]["last_modified_at"] == line["injected_value"] else "after"] += 1

    assert sides["before"] and sides["after"]


@pytest.mark.parametrize("seed", SEEDS)
def test_quarantined_episodes_have_no_intervention_or_review_rows(seed, output_for):
    out = output_for(seed)
    parents = set()
    for extract_date in extract_dates(out):
        for name in ("interventions.csv", "reviews.csv"):
            parents |= {row["episode_id"] for row in read_csv(out / "extracts" / extract_date / name)[1]}

    rejected = {
        line["record_key"]
        for extract_date in extract_dates(out)
        for line in defect_lines(out, extract_date)
        if line["file_name"] == "episodes.csv" and line["expected_outcome"] == "QUARANTINED"
    }

    assert rejected
    assert not rejected & parents


def uk_or_compact_date(value):
    if "/" in value:
        day, month, year = value.split("/")
    else:
        year, month, day = value[:4], value[4:6], value[6:]
    return date(int(year), int(month), int(day)).isoformat()


def test_date_format_defects_use_both_formats_and_parse_to_the_expected_date(output_for):
    lines = [line for line in defect_lines(output_for(2026), HISTORY) if line["defect_type"] == "DATE_FORMAT"]

    assert {"/" in line["injected_value"] for line in lines} == {True, False}
    for line in lines:
        assert uk_or_compact_date(line["injected_value"]) == line["expected_value"]


def test_code_case_defects_correct_to_the_trimmed_upper_case_code(output_for):
    lines = [line for line in defect_lines(output_for(2026), HISTORY) if line["defect_type"] == "CODE_CASE"]

    assert lines
    for line in lines:
        assert line["injected_value"] != line["expected_value"]
        assert line["injected_value"].strip().upper() == line["expected_value"]


def test_unknown_codes_are_the_believable_values_the_spec_names(output_for):
    lines = [line for line in defect_lines(output_for(2026), HISTORY) if line["defect_type"] == "CODE_UNKNOWN"]

    values = {(line["field"], line["injected_value"]) for line in lines}

    assert values == {("primary_substance", "HEROIN"), ("service_code", "S07"), ("intervention_type", "PHARMACY")}


@pytest.mark.parametrize("seed", SEEDS)
def test_orphan_parents_look_like_normal_ids_and_never_appear_in_any_extract(seed, output_for):
    out = output_for(seed)
    issued = {table: set() for table in ("clients", "episodes")}
    orphans = []
    for extract_date in extract_dates(out):
        for table in issued:
            issued[table] |= {row[KEYS[table]] for row in read_csv(out / "extracts" / extract_date / f"{table}.csv")[1]}
        orphans += [line for line in defect_lines(out, extract_date) if line["defect_type"] == "ORPHAN"]

    assert orphans
    for line in orphans:
        parent_table = PARENTS[line["file_name"][: -len(".csv")]][1]
        assert line["injected_value"][0] == {"clients": "C", "episodes": "E"}[parent_table]
        assert len(line["injected_value"]) == 7 and line["injected_value"][1:].isdigit()
        assert line["injected_value"] not in issued[parent_table]


def test_discharge_before_referral_only_hits_episodes_that_never_started_treatment(output_for):
    out = output_for(2026)
    _, episodes = read_csv(out / "extracts" / HISTORY / "episodes.csv")
    reason = {row["episode_id"]: row["discharge_reason"] for row in episodes}

    lines = [line for line in defect_lines(out, HISTORY) if line["defect_type"] == "RULE_DISCHARGE_BEFORE_REFERRAL"]

    assert lines and {reason[line["record_key"]] for line in lines} == {"DECLINED"}
