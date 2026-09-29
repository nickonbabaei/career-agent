"""Workflow operations. Live implementations are intentionally left for you."""

from agent.models import JobPosting, Profile


class JobSearchError(RuntimeError):
    """The jobs provider failed or returned an unusable response."""


def search_jobs(profile: Profile) -> list[JobPosting]:
    """Search a third-party jobs API using profile.target_roles and locations.

    Return normalized JobPosting objects, or [] for a successful empty search.
    Do not classify relevance here or send personal experience to the provider.
    Raise JobSearchError for provider failures (including malformed responses).
    The future workflow owns the single retry and logs failure before ending
    the run. This unfinished stub raises NotImplementedError without retries.
    """
    # Your implementation: call the chosen API and map its results to JobPosting.
    raise NotImplementedError(
        "Implement search_jobs with a jobs API. For fictional sample data, "
        "call load_sample_jobs explicitly from agent.fixtures."
    )
