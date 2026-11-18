import hashlib

from tests.support import read_csv

SEED = 2026


def manifest_rows(out):
    """Every files.csv row, keyed by the path of the data file it describes."""
    described = {}
    for manifest in sorted((out / "manifests").glob("*/files.csv")):
        header, rows = read_csv(manifest)
        assert header == ["extract_date", "seed", "file_name", "row_count", "sha256"]
        data_folder = out / "reference" if manifest.parent.name == "reference" else out / "extracts" / manifest.parent.name
        for row in rows:
            described[(data_folder / row["file_name"]).relative_to(out).as_posix()] = row
    return described


def data_files(out):
    folders = [out / "reference", out / "extracts"]
    return sorted(path for folder in folders for path in folder.rglob("*.csv"))


def test_every_data_file_has_one_manifest_row_with_its_row_count_and_hash(output_for):
    out = output_for(SEED)
    described = manifest_rows(out)

    paths = data_files(out)
    assert sorted(described) == [path.relative_to(out).as_posix() for path in paths]
    for path in paths:
        row = described[path.relative_to(out).as_posix()]
        assert int(row["row_count"]) == len(read_csv(path)[1])
        assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert row["seed"] == str(SEED)


def test_extract_manifests_name_their_extract_date(output_for):
    out = output_for(SEED)
    manifests = [path for path in sorted((out / "manifests").glob("*/files.csv")) if path.parent.name != "reference"]

    assert [path.parent.name for path in manifests] == sorted(path.name for path in (out / "extracts").iterdir())
    for manifest in manifests:
        _, rows = read_csv(manifest)
        assert {row["extract_date"] for row in rows} == {manifest.parent.name}
