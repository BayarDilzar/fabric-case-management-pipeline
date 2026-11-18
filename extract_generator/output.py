from pathlib import Path

from extract_generator.csvfile import sha256_of, write_csv
from extract_generator.defects import DEFECT_COLUMNS
from extract_generator.reference import CODE_LISTS, CUTOFFS, SERVICES

FILES_COLUMNS = ["extract_date", "seed", "file_name", "row_count", "sha256"]


def write_counted(folder, name, columns, rows, extract_date, seed, listing):
    path = folder / name
    write_csv(path, columns, rows)
    listing.append(
        {
            "extract_date": extract_date,
            "seed": str(seed),
            "file_name": name,
            "row_count": str(len(rows)),
            "sha256": sha256_of(path),
        }
    )


def write_reference(out, seed):
    # Reference data is delivered with the historical extract, so it carries that date.
    extract_date = CUTOFFS[0].isoformat()
    listing = []
    services = [dict(zip(["service_code", "service_name", "local_authority_code"], row)) for row in SERVICES]
    columns = ["service_code", "service_name", "local_authority_code"]
    write_counted(out / "reference", "services.csv", columns, services, extract_date, seed, listing)
    codes = [dict(zip(["list_name", "code", "label"], row)) for row in CODE_LISTS]
    write_counted(out / "reference", "code_lists.csv", ["list_name", "code", "label"], codes, extract_date, seed, listing)
    write_csv(out / "manifests" / "reference" / "files.csv", FILES_COLUMNS, listing)


def write_all(extracts, seed, out_dir):
    out = Path(out_dir)
    write_reference(out, seed)
    for extract in extracts:
        extract_date = extract.cutoff.isoformat()
        folder = out / "extracts" / extract_date
        listing = []
        for name, rows in extract.files.items():
            write_counted(folder, name, extract.columns[name], rows, extract_date, seed, listing)
        write_csv(out / "manifests" / extract_date / "files.csv", FILES_COLUMNS, listing)
        write_csv(out / "manifests" / extract_date / "defects.csv", DEFECT_COLUMNS, extract.defects)
