"""Data passed between workflow steps; these classes do not call a model."""

from dataclasses import dataclass, field


@dataclass
class Profile:
    name: str
    target_roles: list[str]
    locations: list[str]
    experience_bullets: list[str]
    email: str = ""
    linkedin_url: str = ""
    resume_path: str = ""
    never_claim: list[str] = field(default_factory=list)


@dataclass
class JobPosting:
    title: str
    company: str
    location: str
    description: str
    source_url: str


@dataclass
class RelevanceDecision:
    is_relevant: bool
    reason: str


@dataclass
class Draft:
    job: JobPosting
    subject: str
    body: str
