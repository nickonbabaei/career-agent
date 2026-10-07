"""Terminal entry point: python -m agent.cli."""

import argparse

from agent.profile import load_profile
from agent.workflow import run_workflow


def positive_integer(value):
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer")
    if result < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def main():
    parser = argparse.ArgumentParser(description="Find jobs and save outreach for human review. Nothing sends.")
    parser.add_argument("--profile", default="profile/profile.yaml", help="Local YAML profile path")
    parser.add_argument("--max-jobs", type=positive_integer, default=10,
                        help="Maximum unique jobs to assess (default: 10)")
    parser.add_argument("--max-search-requests", type=positive_integer, default=4, help="JSearch request cap including retries (default: 4)")
    parser.add_argument("--top-k", type=positive_integer, default=3, help="Shortlist size (default: 3)")
    parser.add_argument("--draft", action="store_true", help="Also draft outreach for shortlisted jobs")
    parser.add_argument("--from-results", help="Reassess saved results.json postings without JSearch; writes a new run")
    parser.add_argument("--resume-results", help="Reuse successful assessments; retry remaining jobs and rank in a new run")
    parser.add_argument("--gemini-rpm", type=positive_integer, default=10, help="Gemini request pacing per run (default: 10 per minute); use your project limits")
    args = parser.parse_args()
    try:
        profile = load_profile(args.profile)
        directory, report = run_workflow(profile, args.max_jobs, max_search_requests=args.max_search_requests, top_k=args.top_k, generate_drafts=args.draft, from_results=args.from_results, resume_results=args.resume_results, gemini_rpm=args.gemini_rpm)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Stopped: {error}\n")
    print(f"\nFound: {report['found']} | Attempted this run: {report['checked']} | Assessed: {report['assessed']} | Reused: {report['reused']} | "
          f"Relevant: {report['relevant']} | Drafted: {report['drafted']} | Failed jobs: {report['failed']}")
    print(f"Shortlisted: {len(report['shortlist'])} | Search requests: {report['search_requests']} | Unassessed: {report['unassessed']} | Queries not attempted: {report['queries_not_attempted']}")
    print(f"Status: {report['status']}\nReview files: {directory}\nNothing sent.")
    return 1 if report["status"] in ("search_failed", "ranking_failed", "completed_with_errors", "quota_limited") else 0


if __name__ == "__main__":
    raise SystemExit(main())
