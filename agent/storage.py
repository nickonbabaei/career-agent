"""Save local review artifacts; no sending or approval functionality."""

from pathlib import Path
from uuid import uuid4

from agent.models import Draft


class DraftSaveError(RuntimeError):
    """The draft could not be saved; do not report it as saved."""


def save_draft(draft: Draft, directory: str | Path = "drafts") -> Path:
    """Save a Draft as unique Markdown and return its absolute path.

    Does not overwrite files or send messages. Raises DraftSaveError on an OS
    failure; the caller retries once then logs/skips. Default drafts/ is ignored
    by Git. Callers choosing another directory must protect personal data there.
    """
    path = Path(directory) / f"draft-{uuid4().hex}.md"
    content = (
        "# Outreach draft\n\nStatus: PENDING HUMAN REVIEW - NOT SENT\n\n"
        f"Role: {draft.job.title}\n\nCompany: {draft.job.company}\n\n"
        f"Location: {draft.job.location}\n\nSource: {draft.job.source_url}\n\n"
        "Check all claims against your profile before using this message.\n\n"
        f"## Subject\n\n{draft.subject}\n\n## Message\n\n{draft.body}\n"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except OSError as exc:
        raise DraftSaveError(f"Could not save draft to {path}") from exc
    return path.resolve()
