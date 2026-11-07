"""CONTRATTO tra frontend, estensione e backend (BLUEPRINT sez. 6).

- Tutti i campi sono snake_case.
- I file in fixtures/ hanno ESATTAMENTE queste forme: se un'API reale risponde
  diversamente è un bug dell'API.
- Chi cambia questo file lo dice nel gruppo (owner: Gabriele).
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Tipi comuni
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
    """Forma di TUTTI gli errori."""

    error: str


# ---------------------------------------------------------------------------
# A — Profilo
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
    end_date: str | None = None  # "YYYY-MM"; null = in corso
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


class Profile(Schema):
    """Profilo strutturato estratto dal CV (colonna profiles.data)."""

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
    search_terms: list[str] = Field(default=[], description="20-30 parole chiave EN + NO")
    missing_info: list[str] = Field(default=[], description="max 5 domande per l'utente")


class ProfileOut(Schema):
    """GET /profile, PUT /profile, POST /profile/upload."""

    id: int
    profile: Profile
    extra_text: str = ""
    updated_at: datetime


class ProfileUpdate(Schema):
    """Body di PUT /profile."""

    profile: Profile
    extra_text: str | None = None


# ---------------------------------------------------------------------------
# B — Annunci e Radar
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
    posted_at: datetime | None = None  # null = "date unknown" (MAI sostituire con discovered_at)
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
    """Body di POST /radar."""

    days: Literal[3, 7, 14, 30] = 7
    english_only: bool = False
    refresh: bool = False


class RadarResult(Schema):
    job: JobOut
    match: MatchOut


class RadarResponse(Schema):
    days_requested: int
    days_used: int  # > days_requested se si è allargata la finestra
    widened: bool  # la UI deve dirlo
    scanned_count: int  # annunci nel DB considerati
    candidates_count: int  # passati i filtri e mandati al ranking
    results: list[RadarResult]  # max 15, ordinati per score
    generated_at: datetime


class ApplicationRef(Schema):
    id: int
    status: ApplicationStatus


class JobDetail(Schema):
    """GET /jobs/{id}."""

    job: JobOut
    match: MatchOut | None = None
    application: ApplicationRef | None = None


class JobImportRequest(Schema):
    """Body di POST /jobs/import (dall'estensione)."""

    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    text: str | None = None  # testo visibile della pagina
    json_ld: dict[str, Any] | None = None  # JobPosting schema.org, se presente


class JobImportResponse(Schema):
    job_id: int
    created: bool  # false se l'annuncio era già nel DB


# ---------------------------------------------------------------------------
# C — Candidature
# ---------------------------------------------------------------------------


class TailoredCV(Schema):
    """CV su misura: SOLO fatti presenti nel profilo."""

    name: str
    headline: str = ""
    contacts: Contacts = Contacts()
    summary: str = ""
    skills: list[str] = []
    experiences: list[Experience] = []
    education: list[Education] = []
    projects: list[Project] = []
    languages: list[LanguageSkill] = []


class ApplicationNotes(Schema):
    keywords_covered: list[str] = []
    missing_requirements: list[str] = []  # lacune: MAI dichiarate nel CV
    changes: list[str] = []  # "cosa ho cambiato" rispetto al profilo


class Snapshot(Schema):
    """Fotografia salvata con "I applied": base del colloquio simulato."""

    job: JobOut
    cv: TailoredCV
    cover_letter: str
    applied_at: datetime


class ApplicationCreate(Schema):
    """Body di POST /applications."""

    job_id: int


class ApplicationPatch(Schema):
    """Body di PATCH /applications/{id}: solo i campi da cambiare."""

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
# D — Colloquio simulato e voce
# ---------------------------------------------------------------------------


class InterviewQuestion(Schema):
    id: int  # 1..6
    kind: QuestionKind
    question: str
    focus: str  # cosa vuole verificare la domanda


class TranscriptTurn(Schema):
    role: Literal["interviewer", "candidate"]
    content: str
    question_id: int | None = None


class QuestionFeedback(Schema):
    question_id: int
    question: str
    score: int = Field(ge=1, le=5)
    comment: str
    better_answer: str  # costruita SOLO con fatti veri del profilo/CV


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
    plan: list[InterviewQuestion]  # 6 domande
    message: str  # primo messaggio dell'intervistatore
    question_index: int  # indice (0-based) della domanda in corso


class InterviewTurnRequest(Schema):
    answer: str


class InterviewTurnResponse(Schema):
    interview_id: int
    message: str  # prossima domanda (o chiusura)
    question_index: int
    done: bool  # true dopo la 6a risposta → chiamare /feedback


class InterviewOut(Schema):
    """Colloquio completo (fixtures/interview.json)."""

    id: int
    application_id: int
    mode: InterviewMode
    plan: list[InterviewQuestion]
    transcript: list[TranscriptTurn]
    feedback: InterviewFeedback | None = None


class SignedUrlResponse(Schema):
    signed_url: str
