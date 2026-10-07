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

    country = data.get("search_country", "ca")
    if not isinstance(country, str) or len(country.strip()) != 2 or not country.strip().isascii() or not country.strip().isalpha():
        raise ProfileConfigError("search_country must be a two-letter country code, e.g. ca.")
    values["search_country"] = country.strip().lower()
    required_lists = ("target_roles", "locations")
    for name in (*required_lists, "experience_bullets", "projects", "education", "skills", "never_claim", "seniority_preferences", "employment_preferences", "work_arrangements"):
        value = data.get(name, [])
        if not isinstance(value, list):
            raise ProfileConfigError(f"{name} must be a list of strings.")
        if name in required_lists and not value:
            raise ProfileConfigError(f"{name} must contain at least one entry.")
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ProfileConfigError(f"{name} entries must be nonempty strings.")
        values[name] = [item.strip() for item in value]

    roles = data.get('work_experience', [])
    if not isinstance(roles, list):
        raise ProfileConfigError('Work experience must be a list of roles.')
    values['work_experience'] = []
    for role in roles:
        if not isinstance(role, dict) or set(role) - {'title', 'company', 'start_date', 'end_date', 'achievements'}:
            raise ProfileConfigError('Invalid work experience fields.')
        clean = {}
        for key in ('title', 'company', 'start_date', 'end_date'):
            value = role.get(key, '')
            if not isinstance(value, str) or (key in ('title', 'company') and not value.strip()):
                raise ProfileConfigError(f'Each role needs a valid {key.replace("_", " ")}.')
            clean[key] = value.strip()
        achievements = role.get('achievements', [])
        if not isinstance(achievements, list) or any(not isinstance(a, str) or not a.strip() for a in achievements):
            raise ProfileConfigError('Achievements must be nonempty text entries.')
        clean['achievements'] = [a.strip() for a in achievements]
        values['work_experience'].append(clean)
    profile = Profile(**values)
    if not profile.background_facts:
        raise ProfileConfigError('Add work experience, a project, education, a skill, or an additional background fact.')
    return profile
