import os
import subprocess
import sys
from pathlib import Path

from tests.support import SPEC_CODES, SPEC_SERVICES, read_csv

REPO = Path(__file__).resolve().parents[1]
HISTORY = "2026-10-25"
SPEC_HEADERS = {
    "clients.csv": ["client_id", "birth_year", "sex", "local_authority_code", "last_modified_at"],
    "episodes.csv": [
        "episode_id",
        "client_id",
        "service_code",
        "referral_date",
        "referral_source",
        "primary_substance",
        "triage_date",
        "discharge_date",
        "discharge_reason",
        "last_modified_at",
    ],
    "interventions.csv": ["intervention_id", "episode_id", "intervention_type", "start_date", "end_date", "last_modified_at"],
    "reviews.csv": [
        "review_id",
        "episode_id",
        "review_date",
        "review_type",
        "days_used_last_28",
        "quality_of_life",
        "last_modified_at",
    ],
}


def run_cli(seed, out, hash_seed):
    # Separate processes with different hash seeds expose any reliance on set or dict order.
    env = dict(os.environ, PYTHONHASHSEED=str(hash_seed))
    command = [sys.executable, "-m", "extract_generator", "--seed", str(seed), "--out", str(out)]
    subprocess.run(command, cwd=REPO, env=env, check=True)


def all_files(folder):
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in sorted(folder.rglob("*")) if path.is_file()}


def test_cli_writes_reference_files_matching_the_spec(tmp_path):
    run_cli(2026, tmp_path, hash_seed=0)

    services_header, services = read_csv(tmp_path / "reference" / "services.csv")
    codes_header, codes = read_csv(tmp_path / "reference" / "code_lists.csv")

    assert services_header == ["service_code", "service_name", "local_authority_code"]
    assert {row["service_code"]: row["local_authority_code"] for row in services} == SPEC_SERVICES
    assert codes_header == ["list_name", "code", "label"]
    assert len(codes) == 25
    listed = {}
    for row in codes:
        listed.setdefault(row["list_name"], set()).add(row["code"])
    assert listed == SPEC_CODES


def test_historical_extract_has_spec_headers(output_for):
    folder = output_for(2026) / "extracts" / HISTORY

    for name, header in SPEC_HEADERS.items():
        assert read_csv(folder / name)[0] == header


def test_same_seed_gives_identical_bytes_in_separate_processes(tmp_path):
    run_cli(2026, tmp_path / "first", hash_seed=1)
    run_cli(2026, tmp_path / "second", hash_seed=4242)

    first, second = all_files(tmp_path / "first"), all_files(tmp_path / "second")

    assert first and first == second


def test_different_seed_gives_different_extract_files(tmp_path, output_for):
    run_cli(2027, tmp_path, hash_seed=0)

    other, ours = all_files(tmp_path), all_files(output_for(2026))

    for name in SPEC_HEADERS:
        path = f"extracts/{HISTORY}/{name}"
        assert other[path] != ours[path]


def test_output_files_have_no_carriage_returns_or_byte_order_marks(output_for):
    for path, content in all_files(output_for(2026)).items():
        assert b"\r" not in content, path
        assert not content.startswith(b"\xef\xbb\xbf"), path
