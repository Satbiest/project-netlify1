"""Bounded API and Gemini output contracts."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Category(str, Enum):
    programming = 'Programming Languages'
    analysis = 'Data Analysis'
    databases = 'Databases'
    tools = 'Tools'
    soft = 'Soft Skills'


class Profile(Contract):
    name: str = Field(max_length=150)
    headline: str = Field(max_length=200)
    summary: str = Field(max_length=1400)


class EvidenceEntry(Contract):
    title: str = Field(min_length=1, max_length=180)
    subtitle: str = Field(max_length=220)
    detail: str = Field(max_length=1200)
    evidence: str = Field(min_length=3, max_length=800)


class Requirement(Contract):
    name: str = Field(min_length=1, max_length=80)
    category: Category
    priority: Literal['required', 'preferred']
    job_evidence: str = Field(min_length=3, max_length=500)
    resume_evidence: str = Field(max_length=500, description='An exact resume quote, or an empty string when not evidenced.')


class ParsedContext(Contract):
    job_title: str = Field(min_length=1, max_length=180)
    enriched_description: str = Field(min_length=20, max_length=6000)
    requirements: list[Requirement] = Field(max_length=60)
    profile: Profile
    education: list[EvidenceEntry] = Field(max_length=15)
    experience: list[EvidenceEntry] = Field(max_length=20)
    achievements: list[EvidenceEntry] = Field(max_length=20)


class SkillAssessment(Contract):
    name: str
    category: Category
    priority: Literal['required', 'preferred']
    status: Literal['matched', 'missing']
    evidence: str
    job_evidence: str


class Coverage(Contract):
    score: float | None = Field(ge=0, le=100)
    matched: int = Field(ge=0)
    total: int = Field(ge=0)


class Scores(Contract):
    total: float = Field(ge=0, le=100)
    required: Coverage
    preferred: Coverage
    semantic: float = Field(ge=0, le=100)
    weights: dict[str, float]


class ActionStep(Contract):
    skill: str = Field(min_length=1, max_length=100)
    priority: Literal['high', 'medium', 'low']
    horizon: str = Field(max_length=80)
    action: str = Field(min_length=10, max_length=650)
    deliverable: str = Field(min_length=5, max_length=300)


class RoleIdea(Contract):
    title: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=10, max_length=400)


class Recommendations(Contract):
    narrative: str = Field(min_length=30, max_length=2000)
    strengths: list[str] = Field(max_length=5)
    action_plan: list[ActionStep] = Field(min_length=1, max_length=6)
    related_roles: list[RoleIdea] = Field(max_length=3)


class Metadata(Contract):
    mode: Literal['live', 'demo']
    filename: str
    pages: int
    elapsed_ms: int
    analyzed_at: str
    gemini_model: str
    embedding_model: str


class AnalysisResponse(Contract):
    job_title: str
    enriched_description: str
    scores: Scores
    skills: list[SkillAssessment]
    profile: Profile
    education: list[EvidenceEntry]
    experience: list[EvidenceEntry]
    achievements: list[EvidenceEntry]
    recommendations: Recommendations
    notes: list[str]
    metadata: Metadata

