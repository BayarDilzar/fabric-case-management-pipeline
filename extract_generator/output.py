from pathlib import Path

from extract_generator.csvfile import write_csv
from extract_generator.reference import CODE_LISTS, SERVICES


def write_reference(out):
    services = [dict(zip(["service_code", "service_name", "local_authority_code"], row)) for row in SERVICES]
    write_csv(out / "reference" / "services.csv", ["service_code", "service_name", "local_authority_code"], services)
    codes = [dict(zip(["list_name", "code", "label"], row)) for row in CODE_LISTS]
    write_csv(out / "reference" / "code_lists.csv", ["list_name", "code", "label"], codes)


def write_all(extracts, out_dir):
    out = Path(out_dir)
    write_reference(out)
    for extract in extracts:
        folder = out / "extracts" / extract.cutoff.isoformat()
        for name, rows in extract.files.items():
            write_csv(folder / name, extract.columns[name], rows)
