"""Thin wrapper around PyCap. No GUI code here, so it can be tested on its own."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from redcap import Project, RedcapError

DEFAULT_API_URL = "https://redcap.ctsi.psu.edu/api/"


class ExportError(Exception):
    """A user-facing error (bad token, wrong project, unknown report, ...)."""


@dataclass
class ProjectInfo:
    project_id: int
    title: str
    in_production: bool
    redcap_version: str


def connect(api_url: str, token: str, expected_project_id: int | None = None) -> tuple[Project, ProjectInfo]:
    """Open a project and check that the token belongs to the expected project ID."""
    api_url = api_url.strip()
    token = token.strip()
    if not api_url.endswith("/"):
        api_url += "/"
    if not token:
        raise ExportError("API token is empty.")
    try:
        project = Project(api_url, token)
        raw = project.export_project_info()
        version = project.export_version()
    except RedcapError as e:
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
