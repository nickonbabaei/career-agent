"""Run with python -m agent.draft_one to review one live outreach draft."""

from agent.drafting import DraftingError, draft_outreach
from agent.profile import load_profile
from agent.relevance import RelevanceError, classify_relevance
from agent.storage import DraftSaveError, save_draft
from agent.tools import JobSearchError, search_jobs


def retry_once(action, error_type):
    for attempt in range(2):
        try:
            return action()
        except error_type as error:
            if attempt == 1:
                raise
            print(f"Step failed; retrying once: {error}")


def main():
    profile = load_profile("profile/profile.yaml")
    jobs = retry_once(lambda: search_jobs(profile), JobSearchError)
    if not jobs:
        print("No jobs found; nothing drafted.")
        return
    job = jobs[0]
    print(f"Checking: {job.title} | {job.company}")
    decision = retry_once(lambda: classify_relevance(job, profile), RelevanceError)
    print(decision.reason)
    if not decision.is_relevant:
        print("First job is not relevant; nothing drafted in this one-job demo.")
        return
    draft = retry_once(lambda: draft_outreach(job, profile), DraftingError)
    path = retry_once(lambda: save_draft(draft), DraftSaveError)
    print(f"\nSubject: {draft.subject}\n\n{draft.body}\n\nSaved for review: {path}")
    print("Nothing sent.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, JobSearchError, RelevanceError, DraftingError, DraftSaveError) as error:
        raise SystemExit(f"Stopped: {error}")
