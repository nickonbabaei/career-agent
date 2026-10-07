"""Operations called by the fixed workflow."""

import os

import requests

from agent.models import JobPosting, Profile


class JobSearchError(RuntimeError):
    """The jobs provider failed or returned an unusable response."""


def search_jobs(profile: Profile) -> list[JobPosting]:
    """Legacy one-query helper; broader workflow uses search_query per planned query."""
    return search_query(plan_queries(profile)[0])


def plan_queries(profile: Profile) -> list[dict]:
    """Return distinct role/location query parameters; no network calls.

    Raises ValueError if roles or locations are absent. Remote searches are
    constrained to search_country, not assumed to allow worldwide employment.
    """
    if not profile.target_roles or not profile.locations:
        raise ValueError("Search requires target roles and locations.")
    roles = list(dict.fromkeys(x.strip() for x in profile.target_roles))
    locations = list(dict.fromkeys(x.strip() for x in profile.locations))
    queries = []
    for location in locations:
        for role in roles:
            remote = location.casefold() == "remote"
            params = {"query": f"{role} in {profile.search_country.upper()}" if remote else f"{role} in {location}",
                      "country": profile.search_country}
            if remote:
                params["work_from_home"] = "true"
            queries.append(params)
    return queries


def search_query(params: dict) -> list[JobPosting]:
    """Fetch one JSearch page for planned parameters; no internal retries.

    Return postings or []. Missing key raises ValueError; provider errors or
    malformed results raise JobSearchError. Caller owns budget, retry and logging.
    """
    api_key = os.environ.get("OPENWEBNINJA_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Set OPENWEBNINJA_API_KEY in your terminal before searching.")
    try:
        response = requests.get(
            "https://api.openwebninja.com/jsearch/search-v2",
            headers={"X-API-Key": api_key},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        status = exc.response.status_code if exc.response is not None else "connection/timeout"
        raise JobSearchError(f"JSearch request failed ({status}); check API access, quota, or connectivity.") from exc

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
            provider_id=row.get("job_id") if isinstance(row.get("job_id"), str) else "",
        ))
    return jobs


def merge_batches(batches: list[list[JobPosting]]) -> list[JobPosting]:
    """Interleave query results and deduplicate exact URLs or provider IDs.

    Deterministic, no network or fuzzy title matching. Returns unique jobs.
    """
    from itertools import zip_longest
    seen_ids, seen_urls, merged = set(), set(), []
    for group in zip_longest(*batches):
        for job in group:
            if job is None:
                continue
            duplicate = job.source_url in seen_urls or (job.provider_id and job.provider_id in seen_ids)
            seen_urls.add(job.source_url)
            if job.provider_id:
                seen_ids.add(job.provider_id)
            if not duplicate:
                merged.append(job)
    return merged
