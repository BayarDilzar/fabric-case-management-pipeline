import re

import pytest

from tests.support import CODE_FIELDS, SPEC_CODES, SPEC_SERVICES, extract_dates, read_csv

# The only free-looking values allowed: listed codes in any case or with a space, and the spec's unknown codes.
CODE_VALUES = {column: SPEC_CODES[name] for (_, column), name in CODE_FIELDS.items()}
CODE_VALUES["primary_substance"] = CODE_VALUES["primary_substance"] | {"HEROIN"}
CODE_VALUES["intervention_type"] = CODE_VALUES["intervention_type"] | {"PHARMACY"}
CODE_VALUES["service_code"] = set(SPEC_SERVICES) | {"S07"}
DATE = r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{8})?"
COLUMN_PATTERNS = {
    "client_id": r"C\d{6}",
    "episode_id": r"E\d{6}",
    "intervention_id": r"I\d{6}",
    "review_id": r"R\d{6}",
    "birth_year": r"\d{4}",
    "local_authority_code": r"(E0[6-9]\d{6})?",
    "referral_date": DATE,
    "triage_date": DATE,
    "discharge_date": DATE,
    "start_date": DATE,
    "end_date": DATE,
    "review_date": DATE,
    "days_used_last_28": r"\d{0,2}",
    "quality_of_life": r"\d{0,2}",
    "last_modified_at": r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
}
POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b")
NHS_NUMBER = re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{4}\b")


def value_has_its_shape(column, value):
    if column in CODE_VALUES:
        return value == "" or value.strip().upper() in CODE_VALUES[column]
    return re.fullmatch(COLUMN_PATTERNS[column], value) is not None


def test_privacy_patterns_catch_real_shapes():
    assert POSTCODE.search("lives at SW1A 1AA")
    assert POSTCODE.search("M1 1AE")
    assert NHS_NUMBER.search("943 476 5919")
    assert NHS_NUMBER.search("9434765919")
    assert not value_has_its_shape("sex", "Smith")
    assert value_has_its_shape("sex", " f")
    assert not value_has_its_shape("local_authority_code", "10 Downing Street")


@pytest.mark.parametrize("seed", [2026, 1])
def test_every_extract_value_has_the_shape_of_its_column(seed, output_for):
    out = output_for(seed)

    for extract_date in extract_dates(out):
        for path in sorted((out / "extracts" / extract_date).glob("*.csv")):
            header, rows = read_csv(path)
            for row in rows:
                for column in header:
                    assert value_has_its_shape(column, row[column]), (path.name, column, row[column])


@pytest.mark.parametrize("seed", [2026, 1])
def test_no_output_file_holds_a_postcode_or_nhs_number(seed, output_for):
    out = output_for(seed)

    for path in sorted(out.rglob("*.csv")):
        text = path.read_text(encoding="utf-8")
        assert not POSTCODE.search(text), path
        assert not NHS_NUMBER.search(text), path
