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
    parser.add_argument("--max-jobs", type=positive_integer, default=3,
                        help="Maximum first-page jobs to assess (default: 3; not a relevance ranking)")
    args = parser.parse_args()
    try:
        profile = load_profile(args.profile)
        directory, report = run_workflow(profile, args.max_jobs)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Stopped: {error}\n")
    print(f"\nFound: {report['found']} | Checked: {report['checked']} | "
          f"Relevant: {report['relevant']} | Drafted: {report['drafted']} | Failed jobs: {report['failed']}")
    print(f"Status: {report['status']}\nReview files: {directory}\nNothing sent.")
    return 1 if report["status"] in ("search_failed", "completed_with_errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
