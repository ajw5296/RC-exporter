"""Live tests against REDCap. Need REDCAP_API_URL, REDCAP_PROJECT_ID, REDCAP_API_TOKEN in .env."""

import os

import pytest
from dotenv import load_dotenv

from rc_exporter import api

load_dotenv(".env")
URL = os.getenv("REDCAP_API_URL", api.DEFAULT_API_URL)
TOKEN = os.getenv("REDCAP_API_TOKEN")
PID = int(os.getenv("REDCAP_PROJECT_ID", "0"))
REPORT_ID = os.getenv("REDCAP_REPORT_ID")

pytestmark = pytest.mark.skipif(not TOKEN, reason="no REDCAP_API_TOKEN in .env")


@pytest.fixture(scope="module")
def project():
    return api.connect(URL, TOKEN, PID)[0]


def test_connect_matches_project_id():
    _, info = api.connect(URL, TOKEN, PID)
    assert info.project_id == PID


def test_wrong_project_id_rejected():
    with pytest.raises(api.ExportError, match="belongs to project"):
        api.connect(URL, TOKEN, PID + 1)


def test_bad_token_rejected():
    with pytest.raises(api.ExportError):
        api.connect(URL, "0" * 32, PID)


def test_unknown_report_rejected(project):
    with pytest.raises(api.ExportError, match="does not belong"):
        api.fetch_csv(project, 1, labels=False)


@pytest.mark.parametrize("ext", ["csv", "xlsx"])
def test_full_export_saves(project, tmp_path, ext):
    text = api.fetch_csv(project, None, labels=False)
    rows = api.save(text, tmp_path / f"out.{ext}")
    assert rows > 0


@pytest.mark.skipif(not REPORT_ID, reason="set REDCAP_REPORT_ID in .env to test a real report")
def test_report_export(project, tmp_path):
    text = api.fetch_csv(project, int(REPORT_ID), labels=True)
    assert api.save(text, tmp_path / "report.csv") >= 0
