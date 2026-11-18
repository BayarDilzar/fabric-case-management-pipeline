import csv

from tests.support import SPEC_HEADERS, defect_lines, extract_dates, read_csv, silver_by_date

BROKEN = "2026-11-22"


def test_broken_extract_is_the_last_and_only_interventions_lacks_end_date(output_for):
    out = output_for(2026)
    folder = out / "extracts" / BROKEN

    assert extract_dates(out)[-1] == BROKEN
    for name, header in SPEC_HEADERS.items():
        expected = [column for column in header if column != "end_date"] if name == "interventions.csv" else header
        with open(folder / name, encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert rows[0] == expected
        assert len(rows) > 1
        assert {len(row) for row in rows} == {len(expected)}


def test_broken_extract_manifest_expects_the_load_to_fail(output_for):
    lines = defect_lines(output_for(2026), BROKEN)

    assert lines == [
        {
            "defect_id": "D-20261122-0001",
            "extract_date": BROKEN,
            "file_name": "interventions.csv",
            "record_key": "",
            "field": "end_date",
            "defect_type": "SCHEMA_MISSING_COLUMN",
            "injected_value": "",
            "expected_outcome": "LOAD_FAILED",
            "expected_value": "",
            "expected_reason": "",
        }
    ]


def test_broken_extract_carries_a_normal_week_of_new_rows(output_for):
    out = output_for(2026)
    week_three = silver_by_date(out)["2026-11-15"]

    _, clients = read_csv(out / "extracts" / BROKEN / "clients.csv")

    assert len([row for row in clients if row["client_id"] not in week_three["clients"]]) == 30
    assert all("2026-11-15 23:59:59" < row["last_modified_at"] <= "2026-11-22 23:59:59" for row in clients)
