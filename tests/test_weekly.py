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
    silver_views,
)

SEEDS = [2026, 1, 7, 99, 12345]
WEEKS = ["2026-11-01", "2026-11-08", "2026-11-15"]


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
    views = dict((cutoff.isoformat(), view) for cutoff, view in silver_views(out))
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
    views = dict((cutoff.isoformat(), view) for cutoff, view in silver_views(out))

    for extract in extracts:
        extract_date = extract.cutoff.isoformat()
        if extract_date not in views:
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


def test_each_week_brings_30_new_clients_and_40_new_episodes(built):
    extracts, out = built(2026)
    views = dict((cutoff.isoformat(), view) for cutoff, view in silver_views(out))
    dates = extract_dates(out)

    assert WEEKS == dates[1:4]
    for week in WEEKS:
        before = views[dates[dates.index(week) - 1]]
        new_clients = {row["client_id"] for row in delivered_rows(out, week, "clients")} - set(before["clients"])
        new_episodes = {row["episode_id"] for row in delivered_rows(out, week, "episodes")} - set(before["episodes"])
        returning = {row["client_id"] for row in delivered_rows(out, week, "episodes") if row["episode_id"] in new_episodes}
        assert len(new_clients) == 30
        assert len(new_episodes) == 40
        assert len(returning - new_clients) == 10
