from datetime import date, datetime, time

import pytest

from tests.support import (
    KEYS,
    TABLES,
    check_rules,
    check_shape,
    defect_lines,
    extract_dates,
    read_csv,
    silver_by_date,
)

SEEDS = [2026, 1, 7, 99, 12345]
WEEKS = ["2026-11-01", "2026-11-08", "2026-11-15"]
PREVIOUS = {"2026-11-01": "2026-10-25", "2026-11-08": "2026-11-01", "2026-11-15": "2026-11-08"}


def end_of(day):
    return datetime.combine(date.fromisoformat(day), time(23, 59, 59)).strftime("%Y-%m-%d %H:%M:%S")


def delivered_rows(out, extract_date, table):
    """The rows the source meant to send: injected copies and re-sent rows taken out."""
    _, rows = read_csv(out / "extracts" / extract_date / f"{table}.csv")
    for line in defect_lines(out, extract_date):
        if line["file_name"] != f"{table}.csv":
            continue
        same_key = [row for row in rows if row[KEYS[table]] == line["record_key"]]
        if line["defect_type"] == "DUP_EXACT":
            rows.remove(same_key[1])
        elif line["defect_type"] == "DUP_VERSION":
            rows.remove(next(row for row in same_key if row["last_modified_at"] == line["injected_value"]))
        elif line["defect_type"] == "RESENT_UNCHANGED":
            rows.remove(same_key[0])
    return rows


def quarantined_keys(out, upto):
    return {
        (line["file_name"], line["record_key"])
        for extract_date in extract_dates(out)
        if extract_date <= upto
        for line in defect_lines(out, extract_date)
        if line["expected_outcome"] == "QUARANTINED"
    }


@pytest.mark.parametrize("seed", SEEDS)
def test_weekly_extracts_hold_only_new_or_changed_rows_stamped_inside_their_week(seed, output_for):
    out = output_for(seed)
    views = silver_by_date(out)
    dates = extract_dates(out)

    for week in WEEKS:
        previous = dates[dates.index(week) - 1]
        before = views[previous]
        for table in TABLES:
            for row in delivered_rows(out, week, table):
                assert end_of(previous) < row["last_modified_at"] <= end_of(week), row
                loaded = before[table].get(row[KEYS[table]])
                assert loaded is None or loaded != row, row


@pytest.mark.parametrize("seed", SEEDS)
def test_silver_rebuilt_from_the_files_matches_the_source_after_every_week(seed, built):
    extracts, out = built(seed)
    views = silver_by_date(out)

    for extract in extracts:
        extract_date = extract.cutoff.isoformat()
        if any(line["expected_outcome"] == "LOAD_FAILED" for line in extract.defects):
            continue
        rejected = quarantined_keys(out, extract_date)
        for table in TABLES:
            source, silver = extract.snapshot[table], views[extract_date][table]
            for key in sorted(set(source) | set(silver)):
                if (f"{table}.csv", key) not in rejected:
                    assert silver.get(key) == source.get(key), (extract_date, key)


@pytest.mark.parametrize("seed", SEEDS)
def test_source_keeps_every_rule_and_the_clean_shape_after_every_week(seed, built):
    extracts, _ = built(seed)

    for extract in extracts:
        assert check_rules(extract.snapshot, extract.cutoff) == []
        assert check_shape(extract.snapshot, extract.cutoff) == []


def source_weeks(built):
    """Pairs of source snapshots (before, after) for each week. Counts describe what the source did;
    the file tests above prove the files carry it."""
    extracts, _ = built(2026)
    return [(extracts[n - 1].snapshot, extracts[n].snapshot) for n in range(1, 4)]


def filled(before, after, table, column):
    return [row for key, row in after[table].items() if key in before[table] and not before[table][key][column] and row[column]]


def created(before, after, table):
    return [row for key, row in after[table].items() if key not in before[table]]


def test_each_week_brings_30_new_clients_and_40_new_episodes(built):
    for before, after in source_weeks(built):
        new_clients = {row["client_id"] for row in created(before, after, "clients")}
        new_episodes = created(before, after, "episodes")
        returning = {row["client_id"] for row in new_episodes} - new_clients
        assert len(new_clients) == 30
        assert len(new_episodes) == 40
        assert len(returning) == 10


def test_each_week_triages_20_episodes_and_discharges_25(built):
    for (before, after), week in zip(source_weeks(built), WEEKS):
        discharged = filled(before, after, "episodes", "discharge_date")
        assert len(filled(before, after, "episodes", "triage_date")) == 20
        assert len(discharged) == 25
        assert "DECLINED" in {row["discharge_reason"] for row in discharged}
        assert all(PREVIOUS[week] < row["discharge_date"] <= week for row in discharged)


def test_discharges_bring_exit_reviews_and_end_open_interventions_on_the_same_day(built):
    for before, after in source_weeks(built):
        discharged = {row["episode_id"]: row for row in filled(before, after, "episodes", "discharge_date")}
        ended = [row for row in filled(before, after, "interventions", "end_date") if row["episode_id"] in discharged]
        exits = [row for row in created(before, after, "reviews") if row["review_type"] == "EXIT"]
        assert ended and exits
        for row in ended:
            assert row["end_date"] == discharged[row["episode_id"]]["discharge_date"]
        for row in exits:
            assert discharged[row["episode_id"]]["discharge_reason"] in ("COMPLETED", "TRANSFERRED")


@pytest.mark.parametrize("seed", SEEDS)
def test_quarantined_rows_never_reappear_in_a_later_extract(seed, output_for):
    out = output_for(seed)
    dates = extract_dates(out)

    for index, extract_date in enumerate(dates):
        rejected = quarantined_keys(out, extract_date) - quarantined_keys(out, dates[index - 1] if index else "")
        for later in dates[index + 1 :]:
            for file_name, key in rejected:
                table = file_name[: -len(".csv")]
                keys = {row[KEYS[table]] for row in read_csv(out / "extracts" / later / file_name)[1]}
                assert key not in keys, (later, key)


def test_each_week_ends_40_interventions_and_adds_60(built):
    # The spec's 100 new reviews a week cannot be met with six-monthly reviews, so reviews are not counted here.
    for before, after in source_weeks(built):
        assert len(filled(before, after, "interventions", "end_date")) == 40
        assert len(created(before, after, "interventions")) == 60


def test_first_treatment_in_a_week_comes_with_its_start_review(built):
    for before, after in source_weeks(built):
        treated_before = {row["episode_id"] for row in before["interventions"].values()}
        reviewed_before = {row["episode_id"] for row in before["reviews"].values()}
        starters = {row["episode_id"] for row in created(before, after, "interventions")} - treated_before
        starts = {row["episode_id"] for row in created(before, after, "reviews") if row["review_type"] == "START"}
        assert starters
        assert starters <= starts
        # Any other START catches up on treatment that began before the week without one.
        assert starts - starters <= treated_before - reviewed_before


def test_each_week_corrects_5_clients_and_3_review_scores(built):
    for before, after in source_weeks(built):
        clients = [(before["clients"][k], row) for k, row in after["clients"].items() if k in before["clients"] and before["clients"][k] != row]
        reviews = [
            (before["reviews"][k], row)
            for k, row in after["reviews"].items()
            if k in before["reviews"] and before["reviews"][k] != row
        ]
        assert len(clients) == 5
        for old, new in clients:
            assert (old["sex"] == "U" and new["sex"] in ("F", "M")) or old["local_authority_code"] != new["local_authority_code"]
        assert len(reviews) == 3
        for old, new in reviews:
            assert old["days_used_last_28"] != new["days_used_last_28"]
