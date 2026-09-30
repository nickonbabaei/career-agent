"""Fixed search/filter/draft/save workflow shared by CLI and future app."""

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agent.models import Profile
from agent.tools import search_jobs, JobSearchError
from agent.relevance import classify_relevance, RelevanceError
from agent.drafting import draft_outreach, DraftingError
from agent.storage import save_draft, DraftSaveError


def run_workflow(profile: Profile, max_jobs: int = 3) -> tuple[Path, dict]:
    """Return run directory and report after processing at most max_jobs.

    Missing keys/invalid limit raise ValueError before network calls. Provider
    and draft-save failures retry once, are recorded, and skip the affected job;
    exhausted search ends the run. Filesystem report failures raise OSError.
    Writes only to ignored drafts/; does not send or approve messages.
    """
    if type(max_jobs) is not int or max_jobs < 1:
        raise ValueError("max_jobs must be a positive integer.")
    for key in ("OPENWEBNINJA_API_KEY", "GEMINI_API_KEY"):
        if not os.environ.get(key, "").strip():
            raise ValueError(f"Set {key} in this terminal before running.")

    directory = Path("drafts") / f"run-{uuid4().hex}"
    directory.mkdir(parents=True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running", "max_jobs": max_jobs,
        "found": 0, "checked": 0, "relevant": 0, "drafted": 0, "failed": 0,
        "jobs": [], "errors": [],
    }

    def persist():
        temporary = directory / "results.json.tmp"
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(directory / "results.json")

    def attempt(stage, operation, error_type, job_index=None):
        for number in (1, 2):
            try:
                return operation()
            except error_type as error:
                report["errors"].append({"stage": stage, "job_index": job_index,
                                         "attempt": number, "message": str(error)})
                persist()
                print(f"{stage} attempt {number} failed: {error}")
                if number == 2:
                    raise

    persist()
    try:
        jobs = attempt("search", lambda: search_jobs(profile), JobSearchError)
    except JobSearchError:
        report["status"] = "search_failed"
        persist()
        return directory.resolve(), report

    report["found"] = len(jobs)
    persist()
    for index, job in enumerate(jobs[:max_jobs], start=1):
        entry = {"job": asdict(job), "status": "checking"}
        report["jobs"].append(entry)
        report["checked"] += 1
        print(f"Checking {index}: {job.title} | {job.company}")
        persist()
        try:
            decision = attempt("relevance", lambda: classify_relevance(job, profile),
                               RelevanceError, index)
            entry["decision"] = asdict(decision)
            entry["status"] = "relevant" if decision.is_relevant else "rejected"
            persist()
            if not decision.is_relevant:
                continue
            report["relevant"] += 1
            draft = attempt("drafting", lambda: draft_outreach(job, profile), DraftingError, index)
            # Retain generated text even if its Markdown save subsequently fails.
            entry["draft"] = {"subject": draft.subject, "body": draft.body}
            persist()
            path = attempt("save", lambda: save_draft(draft, directory), DraftSaveError, index)
            entry["draft_file"] = path.name
            entry["status"] = "drafted_pending_review"
            report["drafted"] += 1
        except (RelevanceError, DraftingError, DraftSaveError) as error:
            entry["status"] = "failed"
            entry["error"] = str(error)
            report["failed"] += 1
            print("Skipping this job after two failures.")
        finally:
            persist()

    report["status"] = "completed_with_errors" if report["failed"] else "completed"
    persist()
    return directory.resolve(), report
