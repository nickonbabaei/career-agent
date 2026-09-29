"""Operations called by the fixed workflow."""

import os

import requests

from agent.models import JobPosting, Profile


class JobSearchError(RuntimeError):
    """The jobs provider failed or returned an unusable response."""


def search_jobs(profile: Profile) -> list[JobPosting]:
    """Search JSearch once with the first target role and location in Canada.

    Return normalized JobPosting objects, or [] for a successful empty search.
    Do not classify relevance here or send personal experience to the provider.
    Raise JobSearchError for provider failures (including malformed responses).
    Missing key or preferences raise ValueError before making a request.
    Missing location becomes 'Not specified'; other required fields must exist.
    The future workflow owns the single retry and logs failure before ending
    the run. This function makes one request, with a 30-second timeout.
    """
    api_key = os.environ.get("OPENWEBNINJA_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Set OPENWEBNINJA_API_KEY in your terminal before searching.")
    if not profile.target_roles or not profile.locations:
        raise ValueError("Search requires at least one target role and location.")

    query = f"{profile.target_roles[0]} in {profile.locations[0]}"
    try:
        response = requests.get(
            "https://api.openwebninja.com/jsearch/search-v2",
            headers={"X-API-Key": api_key},
            params={"query": query, "country": "ca"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise JobSearchError("JSearch request failed; check connectivity, API access, and quota.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise JobSearchError("JSearch returned invalid JSON.") from exc

    if not isinstance(payload, dict) or payload.get("status") != "OK":
        raise JobSearchError("JSearch did not return a successful API response.")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise JobSearchError("JSearch response must contain data.jobs as a list.")

    jobs = []
    for index, row in enumerate(data["jobs"], start=1):
        if not isinstance(row, dict):
            raise JobSearchError(f"JSearch job {index} must be an object.")
        for field in ("job_title", "employer_name", "job_description", "job_apply_link"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise JobSearchError(f"JSearch job {index} has a missing or invalid {field}.")

        location = row.get("job_location")
        if location is None or (isinstance(location, str) and not location.strip()):
            location = "Not specified"
        if not isinstance(location, str):
            raise JobSearchError(f"JSearch job {index} has an invalid job_location.")

        jobs.append(JobPosting(
            title=row["job_title"].strip(),
            company=row["employer_name"].strip(),
            location=location.strip(),
            description=row["job_description"].strip(),
            source_url=row["job_apply_link"].strip(),
        ))
    return jobs
