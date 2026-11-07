"""CONTRACT between frontend, extension and backend (BLUEPRINT sec. 6).

- All fields are snake_case.
- The files in fixtures/ have EXACTLY these shapes: if a real API answers
  differently, that is an API bug.
- Whoever changes this file tells the group (owner: Gabriele).
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Common types
# ---------------------------------------------------------------------------

JobSource = Literal["nav", "teamtailor", "greenhouse", "lever", "ashby", "extension", "fixture"]
JobStatus = Literal["active", "inactive"]
JobLanguage = Literal["no", "en"]
Verdict = Literal["strong", "good", "stretch", "poor"]
ApplicationStatus = Literal["draft", "applied", "interviewing", "rejected", "offer"]
DocLanguage = Literal["en", "no"]
InterviewMode = Literal["text", "voice"]
QuestionKind = Literal["intro", "behavioral", "technical", "motivation", "gap"]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(Schema):
    """Shape of ALL errors."""

    error: str


# ---------------------------------------------------------------------------
# A — Profile
# ---------------------------------------------------------------------------


class Contacts(Schema):
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class LanguageSkill(Schema):
    language: str  # "English", "Norwegian", ...
    level: str  # "native" oppure CEFR: "A1".."C2"


class Experience(Schema):
    role: str
    company: str
    location: str | None = None
    start_date: str | None = None  # "YYYY-MM"
    end_date: str | None = None  # "YYYY-MM"; null = ongoing
    bullets: list[str] = []


class Education(Schema):
    degree: str
    institution: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    details: list[str] = []


class Project(Schema):
    name: str
    description: str
    tools: list[str] = []
    url: str | None = None


class Preferences(Schema):
    roles: list[str] = []
    cities: list[str] = []
    seniority: str | None = None  # "intern" | "junior" | "mid" | "senior"
    work_modes: list[str] = []  # "onsite" | "hybrid" | "remote"
    industries: list[str] = []  # sectors / interests the candidate stated, e.g. "energy", "public sector"


class Profile(Schema):
    """Structured profile extracted from the CV (column profiles.data)."""

    name: str
    headline: str = ""
    contacts: Contacts = Contacts()
    summary: str = ""
    skills: list[str] = []
    tools: list[str] = []
    languages: list[LanguageSkill] = []
    experiences: list[Experience] = []
    education: list[Education] = []
    projects: list[Project] = []
    preferences: Preferences = Preferences()
    search_terms: list[str] = Field(default=[], description="20-30 keywords, English + Norwegian")
    missing_info: list[str] = Field(default=[], description="max 5 questions for the user")


class ProfileOut(Schema):
    """GET /profile, PUT /profile, POST /profile/upload."""

    id: int
    profile: Profile
    extra_text: str = ""
    updated_at: datetime
    # files that could not be read properly in the last upload (the UI shows them to the user)
    warnings: list[str] = []


class ProfileUpdate(Schema):
    """Body of PUT /profile."""

    profile: Profile
    extra_text: str | None = None


class MissingInfoAnswer(Schema):
    question: str  # one of profile.missing_info, copied as is
    answer: str


class ProfileAnswers(Schema):
    """Body of POST /profile/answers: the user's answers to profile.missing_info."""

    answers: list[MissingInfoAnswer]


# ---------------------------------------------------------------------------
# B — Jobs and Radar
# ---------------------------------------------------------------------------


class JobOut(Schema):
    id: int
    source: JobSource
    source_id: str
    title: str
    company: str | None = None
    location: str | None = None
    description: str | None = None
    url: str
    apply_url: str | None = None
    posted_at: datetime | None = None  # null = "date unknown" (NEVER replace with discovered_at)
    expires_at: datetime | None = None
    discovered_at: datetime
    status: JobStatus = "active"
    language: JobLanguage | None = None
    norwegian_required: bool | None = None


class MatchOut(Schema):
    score: int = Field(ge=0, le=100)
    verdict: Verdict
    reasons: list[str] = Field(default=[], max_length=3)
    gaps: list[str] = Field(default=[], max_length=3)
    to_clarify: list[str] = Field(default=[], max_length=2)


class RadarRequest(Schema):
    """Body of POST /radar."""

    days: Literal[3, 7, 14, 30] = 7
    english_only: bool = False
    refresh: bool = False


class RadarResult(Schema):
    job: JobOut
    match: MatchOut


class RadarFunnel(Schema):
    """Jobs left after each step of the Radar, in order. Shows WHY there are few results."""

    total: int  # active jobs in the catalogue
    recent: int  # posted within the window (or unknown date)
    location: int  # in the Oslo area / Norway / remote
    language: int  # after the English-only filter (= location if off)
    keywords: int  # title matches the profile's search terms
    deduplicated: int
    live: int  # still open (liveness check)
    ranked: int  # sent to the AI ranking


class RadarResponse(Schema):
    days_requested: int
    days_used: int  # > days_requested if the window was widened
    widened: bool  # the UI must say so
    scanned_count: int  # jobs in the DB that were considered
    candidates_count: int  # passed the filters and were sent to ranking
    results: list[RadarResult]  # max 15, sorted by score
    generated_at: datetime
    funnel: RadarFunnel | None = None  # how many jobs survive each step (filled by the Radar)



class ApplicationRef(Schema):
    id: int
    status: ApplicationStatus


class JobDetail(Schema):
    """GET /jobs/{id}."""

    job: JobOut
    match: MatchOut | None = None
    application: ApplicationRef | None = None


class JobImportRequest(Schema):
    """Body of POST /jobs/import (from the extension)."""

    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    text: str | None = None  # visible text of the page
    json_ld: dict[str, Any] | None = None  # schema.org JobPosting, if present


class JobImportResponse(Schema):
    job_id: int
    created: bool  # false if the job was already in the DB


# ---------------------------------------------------------------------------
# C — Applications
# ---------------------------------------------------------------------------


class TailoredCV(Schema):
    """Tailored CV: ONLY facts present in the profile."""

    name: str
    headline: str = ""
    contacts: Contacts = Contacts()
    summary: str = ""
    skills: list[str] = []
    experiences: list[Experience] = []
    education: list[Education] = []
    projects: list[Project] = []
    languages: list[LanguageSkill] = []


class RequirementMatch(Schema):
    """One requirement of the ad and the proof for it, quoted from the candidate's material."""

    requirement: str
    importance: Literal["required", "nice_to_have"]
    status: Literal["met", "partial", "missing"]
    # verbatim quotes from the profile / extra material; checked in code, never invented
    evidence: list[str] = []


class ApplicationNotes(Schema):
    keywords_covered: list[str] = []
    missing_requirements: list[str] = []  # gaps: NEVER claimed in the CV
    changes: list[str] = []  # "what I changed" compared to the profile
    requirement_map: list[RequirementMatch] = []  # "why this CV fits": requirement -> proof


class Snapshot(Schema):
    """Snapshot saved with "I applied": basis of the mock interview."""

    job: JobOut
    cv: TailoredCV
    cover_letter: str
    applied_at: datetime


class ApplicationCreate(Schema):
    """Body of POST /applications."""

    job_id: int


class ApplicationPatch(Schema):
    """Body of PATCH /applications/{id}: only the fields to change."""

    cv: TailoredCV | None = None
    cover_letter: str | None = None
    status: ApplicationStatus | None = None


class ApplicationOut(Schema):
    id: int
    job_id: int
    job: JobOut
    status: ApplicationStatus
    language: DocLanguage
    cv: TailoredCV
    cover_letter: str
    notes: ApplicationNotes
    snapshot: Snapshot | None = None
    created_at: datetime
    applied_at: datetime | None = None


# ---------------------------------------------------------------------------
# D — Mock interview and voice
# ---------------------------------------------------------------------------


class InterviewQuestion(Schema):
    id: int  # 1..6
    kind: QuestionKind
    question: str
    focus: str  # what the question wants to verify


class TranscriptTurn(Schema):
    role: Literal["interviewer", "candidate"]
    content: str
    question_id: int | None = None


class QuestionFeedback(Schema):
    question_id: int
    question: str
    score: int = Field(ge=1, le=5)
    comment: str
    better_answer: str  # built ONLY from true facts of the profile/CV


class InterviewFeedback(Schema):
    overall_score: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str]
    improvements: list[str]
    questions: list[QuestionFeedback]


class InterviewStartRequest(Schema):
    mode: InterviewMode = "text"


class InterviewStartResponse(Schema):
    interview_id: int
    application_id: int
    mode: InterviewMode
    plan: list[InterviewQuestion]  # 6 questions
    message: str  # the interviewer's first message
    question_index: int  # (0-based) index of the current question


class InterviewTurnRequest(Schema):
    answer: str


class InterviewTurnResponse(Schema):
    interview_id: int
    message: str  # next question (or closing)
    question_index: int
    done: bool  # true after the 6th answer -> call /feedback


class InterviewOut(Schema):
    """Full interview (fixtures/interview.json)."""

    id: int
    application_id: int
    mode: InterviewMode
    plan: list[InterviewQuestion]
    transcript: list[TranscriptTurn]
    feedback: InterviewFeedback | None = None


class SignedUrlResponse(Schema):
    signed_url: str
