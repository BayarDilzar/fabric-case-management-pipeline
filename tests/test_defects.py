from collections import Counter

import pytest

from tests.support import (
    KEYS,
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
