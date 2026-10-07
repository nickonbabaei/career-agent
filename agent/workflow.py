"""Fixed discovery, assessment, comparative ranking, and optional drafting."""
import json
import os
import hashlib
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agent.models import Profile
from agent.saved_results import load_saved_jobs, load_saved_decisions
from agent.quota import QuotaError
from agent.tools import plan_queries, search_query, merge_batches, JobSearchError
from agent.relevance import classify_relevance, RelevanceError, SYSTEM_PROMPT, DECISION_SCHEMA
from agent.ranking import rank_jobs, RankingError
from agent.drafting import draft_outreach, DraftingError
from agent.storage import save_draft, DraftSaveError


def run_workflow(profile: Profile, max_jobs: int = 10, *, max_search_requests: int = 4,
                 top_k: int = 3, generate_drafts: bool = False, from_results: str | None = None,
                 resume_results: str | None = None, gemini_rpm: int = 10) -> tuple[Path, dict]:
    """Save and return a budgeted discovery report and ranked shortlist.

    Positive limits and keys are required (ValueError before calls). Search budget
    includes retries. Provider failures retry once, log, then skip the affected
    query/job; rank failure prevents shortlist/drafting. OSError stops persistence.
    No sending, paid fallback, or automatic pagination. Drafting is opt-in.
    """
    for name, value in (("max_jobs", max_jobs), ("max_search_requests", max_search_requests), ("top_k", top_k), ("gemini_rpm", gemini_rpm)):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer.")
    if from_results and resume_results:
        raise ValueError('Choose reassessment or resume, not both.')
    if resume_results and generate_drafts:
        raise ValueError('Resume restores assessments/ranking only; omit --draft.')
    fingerprint = hashlib.sha256(json.dumps(
        [asdict(profile), SYSTEM_PROMPT, DECISION_SCHEMA, 'gemini-3.5-flash-lite'], sort_keys=True
    ).encode()).hexdigest()
    source = resume_results or from_results
    saved_jobs = load_saved_jobs(source) if source is not None else None
    recovery = load_saved_decisions(source, fingerprint) if resume_results else {'decisions': {}, 'legacy': False}
    if recovery['legacy']:
        print('Legacy report: profile/prompt compatibility cannot be verified; assuming unchanged profile for recovery.')
    for key in (("GEMINI_API_KEY",) if saved_jobs is not None else ("OPENWEBNINJA_API_KEY", "GEMINI_API_KEY")):
        if not os.environ.get(key, "").strip():
            raise ValueError(f"Set {key} in this terminal before running.")
    queries = [] if saved_jobs is not None else plan_queries(profile)
    directory = Path("drafts") / f"run-{uuid4().hex}"
    directory.mkdir(parents=True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "running",
        "source_results": str(Path(source).resolve()) if source is not None else None,
        "assessment_fingerprint": fingerprint, "legacy_resume": recovery["legacy"],
        "resumed": bool(resume_results), "reused": 0, "assessed": 0, "pending": 0,
        "gemini_rpm": gemini_rpm,
        "max_jobs": max_jobs, "max_search_requests": max_search_requests, "top_k": top_k,
        "found": 0, "checked": 0, "relevant": 0, "drafted": 0, "failed": 0,
        "search_requests": 0, "searches": [], "queries_planned": len(queries),
        "queries_not_attempted": len(queries), "unassessed": 0,
        "jobs": [], "ranking": [], "shortlist": [], "errors": [],
    }

    def persist():
        report['assessed'] = sum('decision' in e for e in report['jobs'])
        report['unassessed'] = report['found'] - report['assessed']
        report['pending'] = sum(e['status'] == 'pending' for e in report['jobs']) + len(report.get('unassessed_jobs', []))
        temporary = directory / "results.json.tmp"
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(directory / "results.json")

    next_model_start = 0.0

    def pace_model():
        nonlocal next_model_start
        wait = max(0.0, next_model_start - time.monotonic())
        if wait:
            print(f'Pacing Gemini: waiting {wait:.1f}s (configured {gemini_rpm} requests/minute).')
            # Keep individual sleeps bounded for low configured rates.
            while wait > 60:
                time.sleep(60)
                wait -= 60
            if wait:
                time.sleep(wait)
        next_model_start = time.monotonic() + 60.0 / gemini_rpm

    def attempt(stage, operation, error_type, job_id=None):
        for number in (1, 2):
            try:
                if stage in ('relevance', 'ranking', 'drafting'):
                    pace_model()
                return operation()
            except QuotaError as error:
                report['errors'].append({'stage': stage, 'job_id': job_id,
                                         'attempt': number, 'message': str(error), **error.details})
                persist()
                delay = error.details.get('retry_after_seconds', 30)
                if number == 2 or delay > 60:
                    print('Quota limit persists or requires a longer wait; saving progress and stopping.')
                    raise
                print(f'Gemini rate limited; waiting {delay:g}s before one retry.')
                time.sleep(delay)
            except error_type as error:
                report["errors"].append({"stage": stage, "job_id": job_id,
                                         "attempt": number, "message": str(error)})
                persist()
                print(f"{stage} attempt {number} failed: {error}")
                if number == 2:
                    raise

    def finish(status):
        report["status"] = status
        persist()
        lines = ["# Job shortlist", "", f"Run status: {status}", "",
                 f"Found {report['found']} unique jobs; attempted this run {report['checked']}; "
                 f"successfully assessed {report['assessed']} (reused {report['reused']}); "
                 f"failed jobs {report['failed']}; pending {report['pending']}; "
                 f"{report['unassessed']} unassessed. Ranking covers assessed relevant jobs only.", "",
                 f"Search requests: {report['search_requests']}/{max_search_requests}; "
                 f"queries not attempted: {report['queries_not_attempted']}.", ""]
        if not report["shortlist"]:
            lines.append("No ranked shortlist available. See results.json for decisions and errors.")
        for rank, item in enumerate(report["shortlist"], 1):
            entry = next(e for e in report["jobs"] if e["id"] == item["id"])
            job = entry["job"]
            lines.extend([f"## {rank}. {job['title']} | {job['company']}", "",
                          job["location"], "", job["source_url"], "",
                          f"Fit assessment: {entry['decision']['reason']}", "",
                          f"Ranking comparison: {item['reason']}", ""])
            if "draft_file" in entry:
                lines.extend([f"Draft pending review: {entry['draft_file']}", ""])
        lines.extend(["Nothing sent. Review all model judgments and claims.", ""])
        (directory / "shortlist.md").write_text("\n".join(lines), encoding="utf-8")
        return directory.resolve(), report

    persist()
    batches = [saved_jobs] if saved_jobs is not None else []
    for params in queries:
        if report["search_requests"] >= max_search_requests:
            break
        search = {"params": params, "status": "running"}
        report["searches"].append(search)
        report["queries_not_attempted"] -= 1
        for number in (1, 2):
            if report["search_requests"] >= max_search_requests:
                search["status"] = "failed_budget_exhausted"
                break
            report["search_requests"] += 1
            persist()
            print(f"Searching: {params['query']}")
            try:
                batch = search_query(params)
                batches.append(batch)
                search.update(status="completed", count=len(batch))
                break
            except JobSearchError as error:
                search["status"] = "failed"
                report["errors"].append({"stage": "search", "params": params,
                                         "attempt": number, "message": str(error)})
                print(f"Search attempt {number} failed: {error}")
                persist()
        persist()
    if not batches:
        return finish("search_failed")
    jobs = saved_jobs if saved_jobs is not None else merge_batches(batches)
    report["found"] = len(jobs)
    report["unassessed"] = max(0, len(jobs) - max_jobs)
    # Retain the unassessed candidates too, so coverage is inspectable.
    report["unassessed_jobs"] = [asdict(j) for j in jobs[max_jobs:]]
    report['jobs'] = [{'id': i, 'job': asdict(job), 'status': 'pending'}
                      for i, job in enumerate(jobs[:max_jobs], 1)]
    for entry in report['jobs']:
        decision = recovery['decisions'].get(entry['id'])
        if decision is not None:
            entry.update(decision=decision, status='relevant' if decision['is_relevant'] else 'rejected')
            report['reused'] += 1
            report['relevant'] += int(decision['is_relevant'])
    persist()
    for entry in report['jobs']:
        if 'decision' in entry:
            continue
        index = entry['id']
        job = jobs[index - 1]
        entry['status'] = 'checking'
        report['checked'] += 1
        print(f"Checking {index}: {job.title} | {job.company}")
        persist()
        try:
            decision = attempt("relevance", lambda: classify_relevance(job, profile), RelevanceError, index)
            entry["decision"] = asdict(decision)
            entry["status"] = "relevant" if decision.is_relevant else "rejected"
            report["relevant"] += int(decision.is_relevant)
        except QuotaError as error:
            entry.update(status='failed', error=str(error))
            report['failed'] += 1
            return finish('quota_limited')
        except RelevanceError as error:
            entry.update(status="failed", error=str(error))
            report["failed"] += 1
        persist()
    candidates = [{k: e[k] for k in ("id", "job", "decision")}
                  for e in report["jobs"] if e["status"] == "relevant"]
    try:
        report["ranking"] = attempt("ranking", lambda: rank_jobs(candidates, profile), RankingError) if candidates else []
    except QuotaError:
        return finish('quota_limited')
    except RankingError:
        return finish("ranking_failed")
    report["shortlist"] = report["ranking"][:top_k]
    persist()
    if generate_drafts:
        for item in report["shortlist"]:
            entry = next(e for e in report["jobs"] if e["id"] == item["id"])
            job = jobs[entry["id"] - 1]
            try:
                draft = attempt("drafting", lambda: draft_outreach(job, profile), DraftingError, entry["id"])
                entry["draft"] = {"subject": draft.subject, "body": draft.body}
                persist()
                path = attempt("save", lambda: save_draft(draft, directory), DraftSaveError, entry["id"])
                entry.update(draft_file=path.name, status="drafted_pending_review")
                report["drafted"] += 1
            except QuotaError as error:
                entry.update(status='failed', error=str(error))
                report['failed'] += 1
                return finish('quota_limited')
            except (DraftingError, DraftSaveError) as error:
                entry.update(status="failed", error=str(error))
                report["failed"] += 1
            persist()
    failed_queries = any(s["status"] != "completed" for s in report["searches"])
    return finish("completed_with_errors" if failed_queries or report["failed"] else "completed")
