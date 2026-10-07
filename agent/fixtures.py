"""Explicitly load fictional jobs for offline development; never calls an API."""

import json
from dataclasses import fields, MISSING
from pathlib import Path

from agent.models import JobPosting


class FixtureError(ValueError):
    """A sample-jobs file cannot be read or does not match the fixture format."""


def load_sample_jobs(path: str | Path) -> list[JobPosting]:
    """Read a JSON fixture path and return all its fictional jobs, unfiltered.

    Expects {"fictional": true, "jobs": [...]} with required JobPosting fields as
    nonempty strings; provider_id is optional. An empty jobs list is valid. Raises FixtureError for file,
    JSON, or schema errors; no retries or network fallback. Relative paths use
    the working directory. The fictional marker is required to identify samples.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError(f"Cannot read sample jobs JSON: {path}") from exc

    if not isinstance(data, dict) or set(data) != {"fictional", "jobs"}:
        raise FixtureError("Fixture must contain only fictional and jobs fields.")
    if data["fictional"] is not True or not isinstance(data["jobs"], list):
        raise FixtureError("Fixture requires fictional: true and a jobs list.")

    required = {item.name for item in fields(JobPosting) if item.default is MISSING}
    allowed = {item.name for item in fields(JobPosting)}
    jobs = []
    for index, row in enumerate(data["jobs"], start=1):
        if not isinstance(row, dict) or not required <= set(row) or not set(row) <= allowed:
            raise FixtureError(f"Sample job {index} must contain all JobPosting fields only.")
        if any(not isinstance(value, str) or not value.strip() for value in row.values()):
            raise FixtureError(f"Sample job {index} fields must be nonempty strings.")
        jobs.append(JobPosting(**{key: value.strip() for key, value in row.items()}))
    return jobs
