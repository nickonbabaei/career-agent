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
    search_country: str = "ca"
    seniority_preferences: list[str] = field(default_factory=list)
    employment_preferences: list[str] = field(default_factory=list)
    work_arrangements: list[str] = field(default_factory=list)
    work_experience: list[dict] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)

    @property
    def background_facts(self) -> list[str]:
        """Keep role attribution explicit for every model-visible achievement."""
        facts = []
        for role in self.work_experience:
            context = f"{role['title']} at {role['company']}"
            dates = ' – '.join(d for d in (role['start_date'], role['end_date']) if d)
            if dates:
                context += f" ({dates})"
            facts.append(context)
            facts.extend(f"{context}: {item}" for item in role['achievements'])
        for label, items in [('Project', self.projects), ('Education', self.education), ('Skill', self.skills)]:
            facts.extend(f'{label}: {item}' for item in items)
        return facts + self.experience_bullets


@dataclass
class JobPosting:
    title: str
    company: str
    location: str
    description: str
    source_url: str
    provider_id: str = ""


@dataclass
class RelevanceDecision:
    is_relevant: bool
    reason: str


@dataclass
class Draft:
    job: JobPosting
    subject: str
    body: str
