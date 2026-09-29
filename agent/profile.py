"""Load explicit profile facts from local YAML configuration."""

from dataclasses import fields
from pathlib import Path

import yaml

from agent.models import Profile


class ProfileConfigError(ValueError):
    """The profile file cannot be read or does not match the expected schema."""


def load_profile(path: str | Path) -> Profile:
    """Read a YAML path and return a validated Profile.

    Raises ProfileConfigError for unreadable files, invalid YAML, unknown keys,
    missing required values, or incorrect field types. Does not retry, fetch
    LinkedIn data, or open resumes. Relative config paths use the working directory.
    """
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise ProfileConfigError(f"Cannot read profile: {path}") from exc
    except yaml.YAMLError as exc:
        # Avoid including personal file contents in the error message.
        raise ProfileConfigError("Profile must contain valid YAML.") from exc

    if not isinstance(data, dict):
        raise ProfileConfigError("Profile must be a YAML mapping of field names to values.")

    allowed = {item.name for item in fields(Profile)}
    if any(key not in allowed for key in data):
        raise ProfileConfigError("Unknown profile field; compare with profile.yaml.example.")

    values = {}
    for name in ("name", "email", "linkedin_url", "resume_path"):
        value = data.get(name, "")
        if not isinstance(value, str) or (name == "name" and not value.strip()):
            raise ProfileConfigError(f"{name} must be {'a nonempty' if name == 'name' else 'a'} string.")
        values[name] = value.strip()

    for name in ("target_roles", "locations", "experience_bullets", "never_claim"):
        value = data.get(name, [])
        if not isinstance(value, list):
            raise ProfileConfigError(f"{name} must be a list of strings.")
        if name != "never_claim" and not value:
            raise ProfileConfigError(f"{name} must contain at least one entry.")
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ProfileConfigError(f"{name} entries must be nonempty strings.")
        values[name] = [item.strip() for item in value]

    return Profile(**values)
