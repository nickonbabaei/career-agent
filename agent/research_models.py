"""Research contracts for the upcoming contact-selection step; no model calls."""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ContactEvidence:
    source_url: str
    excerpt: str
    supports: str
    retrieved_at: str


@dataclass
class Contact:
    name: str
    title: str
    organization: str
    public_url: str
    relationship: Literal['employee', 'recruiter']
    selection_reason: str
    evidence: list[ContactEvidence]
    uncertainties: list[str] = field(default_factory=list)


@dataclass
class ResearchResult:
    status: Literal['contact_found', 'no_verified_contact', 'failed']
    actual_employer: str | None
    employer_reason: str
    contact: Contact | None
    uncertainties: list[str] = field(default_factory=list)

# Dataclasses describe the contract; future model output must be validated
# against inspected sources before constructing a contact_found result.
