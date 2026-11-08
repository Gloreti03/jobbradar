"""D — Mock interview (owner: Matilde).

Flow (text mode):
  POST /interview/{application_id}/start     -> plan of 6 questions + first message
  POST /interview/{application_id}/turn      -> candidate answer -> next question (6 times)
  POST /interview/{application_id}/feedback  -> final evaluation (saved, returned again on later calls)
  GET  /interview/{application_id}           -> latest interview (plan + transcript + feedback), extra

Flow (voice mode, ElevenLabs):
  POST /interview/{application_id}/start  {"mode": "voice"}  -> same plan; the frontend passes it to the agent
  ... the conversation happens between the browser and ElevenLabs ...
  POST /interview/{application_id}/voice-transcript          -> saves what was said (question ids assigned here)
  POST /interview/{application_id}/feedback                  -> same evaluation as text mode

Unlocked only for applications in status applied/interviewing/rejected/offer (with a snapshot).
Proxy (BLUEPRINT sec. 9): if application_id is not in the DB but is the id of
fixtures/application.json, that fake application (already applied) is used.
"""

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from fixtures import load_fixture
from llm import LLMError
from models import ApplicationRow, InterviewRow
from schemas import (
    ApplicationNotes,
    InterviewFeedback,
    InterviewOut,
    InterviewQuestion,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
    Snapshot,
    TranscriptTurn,
)
from services import interview as svc

router = APIRouter(prefix="/interview", tags=["interview"])

UNLOCKED = {"applied", "interviewing", "rejected", "offer"}


class VoiceTurn(BaseModel):
    role: Literal["interviewer", "candidate"]
    content: str


class VoiceTranscriptRequest(BaseModel):
    """Body of POST /interview/{id}/voice-transcript: the messages of the ElevenLabs call, in order."""

    transcript: list[VoiceTurn] = Field(max_length=200)


def _load_application(db: Session, application_id: int) -> tuple[Snapshot, ApplicationNotes, str]:
    """-> (snapshot, notes, document language) of an application that has been sent."""
    row = db.get(ApplicationRow, application_id)
    if row is not None:
        status, snapshot, notes, language = row.status, row.snapshot, row.notes, row.language
    else:
        fake = load_fixture("application")
        if fake["id"] != application_id:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        status, snapshot, notes, language = fake["status"], fake["snapshot"], fake["notes"], fake["language"]

    if status not in UNLOCKED or not snapshot:
        raise HTTPException(
            status_code=409,
            detail="The mock interview unlocks after you apply: press \"I applied\" first",
        )
    return Snapshot.model_validate(snapshot), ApplicationNotes.model_validate(notes or {}), language or "en"


def _latest_interview(db: Session, application_id: int) -> InterviewRow:
    row = db.scalar(
        select(InterviewRow)
        .where(InterviewRow.application_id == application_id)
        .order_by(InterviewRow.id.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No interview started for this application: call /start first")
    return row


def _answers(transcript: list[dict]) -> int:
    return sum(1 for t in transcript if t["role"] == "candidate")


@router.post("/{application_id}/start", response_model=InterviewStartResponse)
def start_interview(application_id: int, body: InterviewStartRequest | None = None, db: Session = Depends(get_db)):
    """Creates a NEW interview every time (restart = new plan). ~5-15 s."""
    snapshot, notes, language = _load_application(db, application_id)
    mode = body.mode if body else "text"

    plan, first_message = svc.make_plan(snapshot, notes, language)

    row = InterviewRow(
        application_id=application_id,
        mode=mode,
        plan=[q.model_dump() for q in plan],
        transcript=[TranscriptTurn(role="interviewer", content=first_message, question_id=plan[0].id).model_dump()],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "interview_id": row.id,
        "application_id": application_id,
        "mode": mode,
        "plan": plan,
        "message": first_message,
        "question_index": 0,
    }


@router.post("/{application_id}/turn", response_model=InterviewTurnResponse)
def interview_turn(application_id: int, body: InterviewTurnRequest, db: Session = Depends(get_db)):
    snapshot, _, language = _load_application(db, application_id)
    row = _latest_interview(db, application_id)
    plan = [InterviewQuestion.model_validate(q) for q in row.plan]
    transcript = list(row.transcript)

    index = _answers(transcript)  # question being answered now (0-based)
    if index >= len(plan):
        raise HTTPException(status_code=409, detail="The interview is over: ask for the feedback")

    answer = body.answer.strip()
    transcript.append(TranscriptTurn(role="candidate", content=answer, question_id=plan[index].id).model_dump())

    next_index = index + 1
    if next_index < len(plan):
        message = svc.next_message(plan[index], answer, plan[next_index], language)
        transcript.append(
            TranscriptTurn(role="interviewer", content=message, question_id=plan[next_index].id).model_dump()
        )
        done = False
    else:
        message = svc.closing_message(snapshot, language)
        transcript.append(TranscriptTurn(role="interviewer", content=message, question_id=None).model_dump())
        done = True

    row.transcript = transcript  # reassign: SQLAlchemy does not track in-place JSON changes
    db.commit()
    return {"interview_id": row.id, "message": message, "question_index": next_index, "done": done}


# expressive voice tags the agent puts in its text ("[enthusiastic] Great..."): spoken as tone, not words
_VOICE_TAG = re.compile(r"\[[A-Za-z][A-Za-z ,'-]{0,40}\]\s*")


# hesitation sounds the speech recogniser writes for the candidate ("Um, I think... hmm")
_FILLER = re.compile(
    r"(?<![\w'-])(?:mm+-?hmm+|uh-?huh|u+h+m*|u+m+|h+u+m+|h+m+|m+h*m+|e+r+m+|e+h+m*|a+h+)(?![\w'-])[,.…]*\s*",
    re.IGNORECASE,
)


def _clean(turn: VoiceTurn) -> str:
    text = turn.content.strip()
    if turn.role == "interviewer":
        text = _VOICE_TAG.sub("", text).strip()
    else:
        text = re.sub(r"\s+([,.?!])", r"\1", _FILLER.sub("", text))  # "dashboard , in" -> "dashboard, in"
        text = re.sub(r",{2,}", ",", text).lstrip(" ,.…").rstrip(" ,")
        text = text[:1].upper() + text[1:]
    return text


_STOPWORDS = {"that", "this", "with", "your", "what", "which", "about", "would", "have", "from", "there",
              "they", "were", "been", "into", "when", "where", "while", "could", "should", "tell", "more"}
QUESTION_MATCH_MIN = 0.35  # share of a plan question's words that an interviewer message must contain
CLOSING_MARK = "that's all from my side"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zæøå0-9]+", text.lower()) if len(w) >= 4 and w not in _STOPWORDS}


def _question_text(text: str) -> str:
    """Keep the spoken question, excluding acknowledgements about the preceding answer."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentence for sentence in sentences if "?" in sentence or re.match(
        r"(?:tell me|describe|explain|walk me through|share\b|(?:can|could|would) you\b|"
        r"how\b|what\b|why\b|when\b|where\b|which\b|do you\b|did you\b)", sentence, re.I,
    ))


def _asked_question(text: str, plan: list[InterviewQuestion], index: int) -> int | None:
    """Match only the question, not an acknowledgement mentioning the preceding topic."""
    said = _words(text)
    best, best_score = index, 0.0
    for i in range(index, len(plan)):
        q = _words(plan[i].question)
        score = len(q & said) / len(q) if q else 0.0
        if score > best_score:
            best, best_score = i, score
    return best if best_score >= QUESTION_MATCH_MIN else None


def _question_starts(turns: list[VoiceTurn], plan: list[InterviewQuestion]) -> dict[int, int]:
    starts = {}
    questions = {}
    index, answered, ambiguous = 0, False, False
    for i, turn in enumerate(turns):
        if turn.role == "candidate":
            answered = True
            continue
        if CLOSING_MARK in turn.content.lower().replace("’", "'"):
            break
        question = _question_text(turn.content)
        if not question:
            continue
        questions[i] = question
        match = _asked_question(question, plan, index)
        if match is None:
            if answered:
                ambiguous = True
            elif not starts and index == 0:
                starts[i] = plan[0].id
        elif match > index:
            index, answered = match, False
            starts[i] = plan[index].id
        elif not starts and not answered:
            starts[i] = plan[index].id
    if ambiguous:
        transcript = [TranscriptTurn(role=t.role, content=t.content, question_id=None) for t in turns]
        try:
            return svc.map_voice_questions(plan, transcript, starts, questions)
        except OpenAIError as error:
            raise LLMError("Could not align the voice questions. Retry saving the transcript.") from error
    return starts


def _assign_questions(
    turns: list[VoiceTurn], plan: list[InterviewQuestion]
) -> tuple[list[TranscriptTurn], list[InterviewQuestion]]:
    """Assign answers to question slots and retain the questions actually spoken.

    Exact/close plan questions need no model call. Ambiguous new topics versus clarifications are
    resolved together, once, before saving. Follow-ups remain on the current question, split answers
    are merged and speech after the closing line is ignored.
    """
    turns = [VoiceTurn(role=t.role, content=text) for t in turns if (text := _clean(t))]
    starts = _question_starts(turns, plan)
    spoken_plan = list(plan)
    positions = {q.id: i for i, q in enumerate(plan)}
    out: list[TranscriptTurn] = []
    index = 0  # current question (0-based); len(plan) = interview closed
    for i, turn in enumerate(turns):
        text = turn.content
        if turn.role == "candidate":
            if index >= len(plan):
                continue  # talking after the closing line: not part of the interview
            if out and out[-1].role == "candidate":
                out[-1] = out[-1].model_copy(update={"content": f"{out[-1].content} {text}"})
            else:
                out.append(TranscriptTurn(role="candidate", content=text, question_id=plan[index].id))
        else:
            if CLOSING_MARK in text.lower().replace("’", "'"):
                index = len(plan)
            elif index < len(plan) and i in starts:
                index = positions[starts[i]]
                question = _question_text(text)
                if not question:
                    raise LLMError("Voice question mapping points to a turn without a question")
                # A planned question may start with a factual context sentence. Preserve that
                # context when the agent used its exact wording after an acknowledgement.
                original = plan[index]
                if original.question not in text:
                    spoken_plan[index] = original.model_copy(update={
                        "question": question,
                        "focus": "Evaluate the answer to the question actually asked",
                    })
            qid = plan[index].id if index < len(plan) else None
            out.append(TranscriptTurn(role="interviewer", content=text, question_id=qid))
    return out, spoken_plan


@router.post("/{application_id}/voice-transcript", response_model=InterviewOut)
def save_voice_transcript(application_id: int, body: VoiceTranscriptRequest, db: Session = Depends(get_db)):
    """Saves the transcript of the voice call into the latest interview (started with mode "voice"),
    replacing what was there; then POST /feedback evaluates it like a text interview."""
    _load_application(db, application_id)
    row = _latest_interview(db, application_id)
    plan = [InterviewQuestion.model_validate(q) for q in row.plan]
    transcript, spoken_plan = _assign_questions(body.transcript, plan)
    if not any(t.role == "candidate" for t in transcript):
        raise HTTPException(status_code=422, detail="No answers in the voice transcript: nothing to evaluate")

    row.mode = "voice"
    row.plan = [q.model_dump() for q in spoken_plan]
    row.transcript = [t.model_dump() for t in transcript]
    row.feedback = None  # a new transcript needs a new evaluation
    db.commit()
    return {
        "id": row.id,
        "application_id": row.application_id,
        "mode": row.mode,
        "plan": row.plan,
        "transcript": row.transcript,
        "feedback": None,
    }


@router.post("/{application_id}/feedback", response_model=InterviewFeedback)
def interview_feedback(application_id: int, db: Session = Depends(get_db)):
    """Evaluate answered questions only, including an interview stopped early.
    Computed once, then returned from the DB."""
    snapshot, _, language = _load_application(db, application_id)
    row = _latest_interview(db, application_id)
    if row.feedback:
        return row.feedback
    if _answers(row.transcript) == 0:
        raise HTTPException(status_code=409, detail="Answer at least one question before asking for feedback")

    plan = [InterviewQuestion.model_validate(q) for q in row.plan]
    transcript = [TranscriptTurn.model_validate(t) for t in row.transcript]
    feedback = svc.make_feedback(snapshot, plan, transcript, language)

    row.feedback = feedback.model_dump(mode="json")
    db.commit()
    return feedback


@router.get("/{application_id}", response_model=InterviewOut)
def get_interview(application_id: int, db: Session = Depends(get_db)):
    """Latest interview of the application (to resume the page or show the feedback again)."""
    row = _latest_interview(db, application_id)
    return {
        "id": row.id,
        "application_id": row.application_id,
        "mode": row.mode,
        "plan": row.plan,
        "transcript": row.transcript,
        "feedback": row.feedback,
    }
