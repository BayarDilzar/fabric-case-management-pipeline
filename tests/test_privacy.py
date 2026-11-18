import re

import pytest

from tests.support import extract_dates, read_csv

CODE = r"( ?[A-Za-z_]+ ?)?"
DATE = r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{8})?"
COLUMN_PATTERNS = {
    "client_id": r"C\d{6}",
    "episode_id": r"E\d{6}",
    "intervention_id": r"I\d{6}",
    "review_id": r"R\d{6}",
    "birth_year": r"\d{4}",
    "sex": CODE,
    "local_authority_code": r"(E0[6-9]\d{6})?",
    "service_code": r"S\d{2}",
    "referral_date": DATE,
    "referral_source": CODE,
    "primary_substance": CODE,
    "triage_date": DATE,
    "discharge_date": DATE,
    "discharge_reason": CODE,
    "intervention_type": CODE,
    "start_date": DATE,
    "end_date": DATE,
    "review_date": DATE,
    "review_type": CODE,
    "days_used_last_28": r"\d{0,2}",
    "quality_of_life": r"\d{0,2}",
    "last_modified_at": r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
}
POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b")
NHS_NUMBER = re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{4}\b")


def test_privacy_patterns_catch_real_shapes():
    assert POSTCODE.search("lives at SW1A 1AA")
    assert POSTCODE.search("M1 1AE")
    assert NHS_NUMBER.search("943 476 5919")
    assert NHS_NUMBER.search("9434765919")
    assert not re.fullmatch(COLUMN_PATTERNS["sex"], "Jane Smith")
    assert not re.fullmatch(COLUMN_PATTERNS["local_authority_code"], "10 Downing Street")


@pytest.mark.parametrize("seed", [2026, 1])
def test_every_extract_value_has_the_shape_of_its_column(seed, output_for):
    out = output_for(seed)

    for extract_date in extract_dates(out):
        for path in sorted((out / "extracts" / extract_date).glob("*.csv")):
            header, rows = read_csv(path)
            for row in rows:
                for column in header:
                    assert re.fullmatch(COLUMN_PATTERNS[column], row[column]), (path.name, column, row[column])


@pytest.mark.parametrize("seed", [2026, 1])
def test_no_output_file_holds_a_postcode_or_nhs_number(seed, output_for):
    out = output_for(seed)

    for path in sorted(out.rglob("*.csv")):
        text = path.read_text(encoding="utf-8")
        assert not POSTCODE.search(text), path
        assert not NHS_NUMBER.search(text), path
