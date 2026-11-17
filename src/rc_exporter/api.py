"""Thin wrapper around PyCap. No GUI code here, so it can be tested on its own."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import requests
from redcap import Project, RedcapError

DEFAULT_API_URL = "https://redcap.ctsi.psu.edu/api/"

# REDCap pages live under /<install path>/redcap_v<version>/...; the API is always /<install path>/api/.
_VERSION_DIR = re.compile(r"/redcap_v\d[^/]*(/|$)", re.IGNORECASE)
_API_DIR = re.compile(r"/api(/|$)", re.IGNORECASE)


class ExportError(Exception):
    """A user-facing error (bad token, wrong project, unknown report, ...)."""


def normalize_api_url(url: str) -> tuple[str, int | None]:
    """Turn any REDCap URL a user might paste into the API endpoint, plus the pid if the URL has one.

    https://redcap.example.org/redcap_v16.0.37/API/project_api.php?pid=2755
        -> ("https://redcap.example.org/api/", 2755)
    """
    url = url.strip()
    if not url:
        raise ExportError("API URL is empty.")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if not parts.netloc:
        raise ExportError(f"Not a valid URL: {url}")

    path = parts.path
    if (m := _VERSION_DIR.search(path)) or (m := _API_DIR.search(path)):
        base = path[: m.start()]
    else:
        base = re.sub(r"/[^/]*\.php$", "", path)  # e.g. .../index.php
    api_url = f"{parts.scheme}://{parts.netloc}{base.rstrip('/')}/api/"

    pid = parse_qs(parts.query).get("pid", [None])[0]
    return api_url, int(pid) if pid and pid.isdigit() else None


def _diagnose(api_url: str, token: str) -> str:
    """Explain a response PyCap couldn't parse (usually a firewall/login page instead of the API)."""
    try:
        r = requests.post(api_url, data={"token": token, "content": "version"}, timeout=30)
    except requests.RequestException as e:
        return f"Could not reach {api_url}: {e}"
    if "html" in r.headers.get("Content-Type", "").lower() or r.text.lstrip().startswith("<"):
        hint = (
            " This usually means a firewall is blocking you: connect to the institution's VPN or network and try again."
            if r.status_code in (401, 403)
            else " Check that the URL points at the REDCap server."
        )
        return f"{api_url} returned a web page (HTTP {r.status_code}) instead of REDCap data.{hint}"
    return f"Unexpected response from {api_url} (HTTP {r.status_code}): {r.text[:200]}"


@dataclass
class ProjectInfo:
    project_id: int
    title: str
    in_production: bool
    redcap_version: str


def connect(api_url: str, token: str, expected_project_id: int | None = None) -> tuple[Project, ProjectInfo]:
    """Open a project and check that the token belongs to the expected project ID."""
    api_url, _ = normalize_api_url(api_url)
    token = token.strip()
    if not token:
        raise ExportError("API token is empty.")
    try:
        project = Project(api_url, token)
        raw = project.export_project_info()
        version = project.export_version()
    except (RedcapError, ValueError) as e:
        # A non-JSON reply (firewall or login page) surfaces as a JSONDecodeError (a ValueError),
        # sometimes raised directly and sometimes wrapped in RedcapError by PyCap.
        if isinstance(e, ValueError) or isinstance(e.__cause__, ValueError):
            raise ExportError(_diagnose(api_url, token)) from e
        raise ExportError(f"REDCap rejected the request: {e}") from e
    except Exception as e:  # network errors, bad URL, etc.
        raise ExportError(f"Could not reach {api_url}: {e}") from e

    info = ProjectInfo(
        project_id=int(raw["project_id"]),
        title=raw["project_title"],
        in_production=bool(raw.get("in_production")),
        redcap_version=str(version),
    )
    if expected_project_id is not None and info.project_id != expected_project_id:
        raise ExportError(
            f"This token belongs to project {info.project_id} ({info.title}), not project {expected_project_id}."
        )
    return project, info


def fetch_csv(project: Project, report_id: int | None, labels: bool) -> str:
    """Return REDCap's CSV text for a report, or for all records if report_id is None."""
    raw_or_label = "label" if labels else "raw"
    try:
        if report_id is None:
            return project.export_records(
                format_type="csv",
                raw_or_label=raw_or_label,
                raw_or_label_headers=raw_or_label,
            )
        return project.export_report(
            report_id=str(report_id),
            format_type="csv",
            raw_or_label=raw_or_label,
            raw_or_label_headers=raw_or_label,
        )
    except RedcapError as e:
        raise ExportError(str(e)) from e


def save(csv_text: str, path: Path) -> int:
    """Write the export to .csv (unchanged) or .xlsx. Returns the number of data rows."""
    # Read everything as text so ZIP codes, IDs, and dates keep their exact form.
    df = pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)
    if path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False)
    else:
        path.write_text(csv_text, encoding="utf-8-sig")  # BOM so Excel opens UTF-8 correctly
    return len(df)
