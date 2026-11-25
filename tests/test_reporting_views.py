import importlib.util
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parents[1] / "sql" / "deploy_views.py"
spec = importlib.util.spec_from_file_location("deploy_views", DEPLOY)
deploy_views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy_views)


def test_every_file_creates_the_view_named_after_it():
    files = deploy_views.view_files()
    assert [path.stem for path in files] == sorted([
        "data_trust_by_extract", "people_in_treatment_by_service", "planned_completions_by_service",
        "primary_substances", "referrals_by_month_and_source", "wait_to_triage_by_service"])


def test_a_file_whose_view_name_differs_is_refused(tmp_path, monkeypatch):
    (tmp_path / "people_in_treatment_by_service.sql").write_text(
        "-- wrong name\nCREATE OR ALTER VIEW reporting.something_else AS\nSELECT 1 AS one;\n", encoding="utf-8")
    monkeypatch.setattr(deploy_views, "FOLDER", tmp_path)
    with pytest.raises(ValueError, match="must create the view reporting.people_in_treatment_by_service"):
        deploy_views.view_files()
