"""Offline tests for turning pasted REDCap URLs into API endpoints."""

import pytest

from rc_exporter.api import ExportError, normalize_api_url


@pytest.mark.parametrize(
    "pasted, expected",
    [
        (
            "https://redcap.einsteinmed.org/redcap_v16.0.37/API/project_api.php?pid=2755",
            ("https://redcap.einsteinmed.org/api/", 2755),
        ),
        ("https://redcap.ctsi.psu.edu/api/", ("https://redcap.ctsi.psu.edu/api/", None)),
        ("https://redcap.ctsi.psu.edu/api", ("https://redcap.ctsi.psu.edu/api/", None)),
        ("redcap.ctsi.psu.edu", ("https://redcap.ctsi.psu.edu/api/", None)),
        ("  https://redcap.ctsi.psu.edu/  ", ("https://redcap.ctsi.psu.edu/api/", None)),
        (
            "https://redcap.ctsi.psu.edu/redcap_v17.3.17/index.php?pid=14746",
            ("https://redcap.ctsi.psu.edu/api/", 14746),
        ),
        # REDCap installed in a subdirectory
        (
            "https://example.edu/redcap/redcap_v15.0.1/DataExport/index.php?pid=12&report_id=3",
            ("https://example.edu/redcap/api/", 12),
        ),
        ("https://example.edu/redcap/", ("https://example.edu/redcap/api/", None)),
        ("https://example.edu/redcap/index.php", ("https://example.edu/redcap/api/", None)),
        ("https://example.edu/redcap/api/help/", ("https://example.edu/redcap/api/", None)),
    ],
)
def test_normalize(pasted, expected):
    assert normalize_api_url(pasted) == expected


@pytest.mark.parametrize("bad", ["", "   ", "https://"])
def test_normalize_rejects(bad):
    with pytest.raises(ExportError):
        normalize_api_url(bad)
