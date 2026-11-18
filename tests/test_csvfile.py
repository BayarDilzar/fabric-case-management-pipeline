from extract_generator.csvfile import write_csv


def test_write_csv_writes_utf8_lf_and_quotes_only_values_with_commas(tmp_path):
    path = tmp_path / "nested" / "services.csv"
    rows = [
        {"code": "S01", "name": "Kingston upon Hull, City of"},
        {"code": "S02", "name": ""},
    ]

    write_csv(path, ["code", "name"], rows)

    assert path.read_bytes() == b'code,name\nS01,"Kingston upon Hull, City of"\nS02,\n'
