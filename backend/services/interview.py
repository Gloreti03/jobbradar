"""D — Mock interview logic (owner: Matilde): question plan, turns, feedback.

Everything is based on the SNAPSHOT saved with "I applied" (job + CV + cover letter actually sent).
Model: "fast" (deepseek-flash) for all calls; the smart model is 45-100 s per call, too slow for
a conversation. Switch FEEDBACK_MODEL to "smart" only if the feedback quality is not good enough.
"""

import json
import logging
import re

from pydantic import BaseModel, Field, field_validator

from llm import LLMError, complete_json
from prompts import (
    INTERVIEW_FEEDBACK_SYSTEM,
    INTERVIEW_FEEDBACK_USER,
    INTERVIEW_PLAN_SYSTEM,
    INTERVIEW_PLAN_USER,
    INTERVIEW_TURN_SYSTEM,
    INTERVIEW_TURN_USER,
)
from schemas import (
    ApplicationNotes,
    InterviewFeedback,
    InterviewQuestion,
    QuestionFeedback,
    Snapshot,
    TranscriptTurn,
)

log = logging.getLogger("interview")

PLAN_MODEL = "fast"
TURN_MODEL = "fast"
FEEDBACK_MODEL = "fast"
# "none" = no hidden reasoning: much faster (feedback ~30 s -> ~10 s). Set to None to turn it off.
PLAN_REASONING = "none"
TURN_REASONING = "none"
FEEDBACK_REASONING = "none"

N_QUESTIONS = 6
EXPECTED_KINDS = ["intro", "behavioral", "behavioral", "technical", "technical", "motivation"]
DESCRIPTION_MAX_CHARS = 6000

CLOSING = {
    "en": "Thank you {name}, that's all from my side. You'll get your feedback now.",
    "no": "Takk, {name}, det var alt fra min side. Du får tilbakemeldingen din nå.",
}


# --- LLM output models (internal; the API contract stays in schemas.py) ---


class _Plan(BaseModel):
    greeting: str
    questions: list[InterviewQuestion] = Field(min_length=N_QUESTIONS, max_length=N_QUESTIONS)

    @field_validator("questions")
    @classmethod
    def _check_order(cls, questions: list[InterviewQuestion]) -> list[InterviewQuestion]:
        for i, (q, expected) in enumerate(zip(questions, EXPECTED_KINDS), start=1):
            if q.id != i:
                raise ValueError(f"question ids must be 1..{N_QUESTIONS} in order (got {q.id} at position {i})")
            ok = q.kind == expected or (q.kind == "gap" and expected == "technical")
            if not ok:
                raise ValueError(f"question {i} must have kind '{expected}' (or 'gap' for 4-5), got '{q.kind}'")
        return questions


class _TurnMessage(BaseModel):
    message: str


_PLACEHOLDERS = {"", "n/a", "na", "n.a.", "none", "-", "null", "not applicable", "not answered", "tbd"}


class _QuestionFeedback(QuestionFeedback):
    @field_validator("better_answer")
    @classmethod
    def _real_answer(cls, value: str) -> str:
        if value.strip().strip(".").casefold() in _PLACEHOLDERS or len(value.split()) < 8:
            raise ValueError("better_answer must be a full example answer built from the CV facts, never n/a or empty")
        return value


class _Feedback(InterviewFeedback):
    questions: list[_QuestionFeedback]


# --- helpers ---


def first_name(snapshot: Snapshot) -> str:
    return (snapshot.cv.name or "").split(" ")[0] or "there"


def _description(snapshot: Snapshot) -> str:
    return (snapshot.job.description or "(no description available)")[:DESCRIPTION_MAX_CHARS]


def _cv_json(snapshot: Snapshot) -> str:
    return json.dumps(snapshot.cv.model_dump(mode="json"), ensure_ascii=False)


def _requirement_map(notes: ApplicationNotes) -> str:
    """requirement_map of the application (requirement -> status + proof) as short lines."""
    lines = []
    for r in getattr(notes, "requirement_map", []) or []:
        proof = "; ".join(f'"{e}"' for e in r.evidence[:2]) or "no proof"
        lines.append(f"- [{r.status}, {r.importance}] {r.requirement} — proof: {proof}")
    return "\n".join(lines) or "(not available)"


# --- plan ---


def make_plan(snapshot: Snapshot, notes: ApplicationNotes, language: str) -> tuple[list[InterviewQuestion], str]:
    """-> (6 questions, interviewer's first message)."""
    user = INTERVIEW_PLAN_USER.format(
        title=snapshot.job.title,
        company=snapshot.job.company or "(unknown)",
        location=snapshot.job.location or "(unknown)",
        description=_description(snapshot),
        cv_json=_cv_json(snapshot),
        cover_letter=snapshot.cover_letter,
        requirement_map=_requirement_map(notes),
        missing="\n".join(f"- {m}" for m in notes.missing_requirements) or "(none)",
    )
    plan = complete_json(
        PLAN_MODEL,
        system=INTERVIEW_PLAN_SYSTEM.format(language=language),
        user=user,
        schema=_Plan,
        temperature=0.5,
        reasoning_effort=PLAN_REASONING,
    )
    first_message = f"{plan.greeting.strip()} {plan.questions[0].question.strip()}"
    return plan.questions, first_message


# --- turns ---


def next_message(question: InterviewQuestion, answer: str, next_question: InterviewQuestion, language: str) -> str:
    """Short acknowledgement + next question. If the model fails, the plain next question
    (the interview must never get stuck)."""
    try:
        out = complete_json(
            TURN_MODEL,
            system=INTERVIEW_TURN_SYSTEM.format(language=language),
            user=INTERVIEW_TURN_USER.format(
                question=question.question, answer=answer, next_question=next_question.question
            ),
            schema=_TurnMessage,
            temperature=0.4,
            max_tokens=400,
            retries=1,
            reasoning_effort=TURN_REASONING,
        )
        if out.message.strip():
            return out.message.strip()
    except (LLMError, Exception) as err:  # network errors included
        log.warning("turn message failed, falling back to the plain question: %s", err)
    return next_question.question


def closing_message(snapshot: Snapshot, language: str) -> str:
    return CLOSING.get(language, CLOSING["en"]).format(name=first_name(snapshot))


# --- feedback ---


def _transcript_text(transcript: list[TranscriptTurn]) -> str:
    return "\n".join(
        f"[{t.role.upper()}{f' Q{t.question_id}' if t.question_id else ''}] {t.content}" for t in transcript
    )


def make_feedback(
    snapshot: Snapshot, plan: list[InterviewQuestion], transcript: list[TranscriptTurn], language: str
) -> InterviewFeedback:
    # Only the questions the candidate answered are evaluated: the interview may be stopped
    # early on purpose (the demo does 2 exchanges), unasked questions must not be scored.
    answered_ids = {t.question_id for t in transcript if t.role == "candidate" and t.question_id is not None}
    evaluated = [q for q in plan if q.id in answered_ids]
    turns = [t for t in transcript if t.question_id in answered_ids]  # drops unanswered question + closing
    stopped_note = (
        f"; the interview was stopped on purpose after {len(evaluated)} of {len(plan)} questions"
        if len(evaluated) < len(plan)
        else ""
    )
    user = INTERVIEW_FEEDBACK_USER.format(
        title=snapshot.job.title,
        company=snapshot.job.company or "(unknown)",
        description=_description(snapshot),
        cv_json=_cv_json(snapshot),
        cover_letter=snapshot.cover_letter,
        stopped_note=stopped_note,
        plan_json=json.dumps([q.model_dump() for q in evaluated], ensure_ascii=False),
        transcript=_transcript_text(turns),
    )
    feedback = complete_json(
        FEEDBACK_MODEL,
        system=INTERVIEW_FEEDBACK_SYSTEM.format(language=language),
        user=user,
        schema=_Feedback,  # rejects "n/a" better answers -> llm.py retries with the error
        temperature=0.3,
        max_tokens=6000,
        reasoning_effort=FEEDBACK_REASONING,
    )
    feedback = InterviewFeedback.model_validate(feedback.model_dump())
    # One entry per ANSWERED question, in plan order, with the exact question text.
    by_id = {q.question_id: q for q in feedback.questions}
    fixed = []
    for q in evaluated:
        item = by_id.get(q.id)
        if item is None:
            continue
        better = _strip_invented_lessons(item.better_answer)
        fixed.append(item.model_copy(update={"question": q.question, "better_answer": better}))
    return feedback.model_copy(update={"questions": fixed})


_LESSON = re.compile(
    r"\b(what i (took|learned|learnt|took away)|i (learned|learnt|realised|realized|discovered) (that|how|the)"
    r"|(this|it|that) taught me|taught me (that|how)|my (key |main )?takeaway|the (key |main )?(lesson|insight))\b",
    re.IGNORECASE,
)


def _strip_invented_lessons(text: str) -> str:
    """Safety net: drop sentences that add a "lesson learned" / insight (BLUEPRINT sec. 8).
    Keeps the text unchanged if removing them would leave almost nothing."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [s for s in sentences if not _LESSON.search(s)]
    if len(kept) == len(sentences) or len(" ".join(kept).split()) < 8:
        return text
    return " ".join(kept)
