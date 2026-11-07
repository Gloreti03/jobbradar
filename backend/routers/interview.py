"""D — Mock interview (owner: Matilde).

Flow (text mode):
  POST /interview/{application_id}/start     -> plan of 6 questions + first message
  POST /interview/{application_id}/turn      -> candidate answer -> next question (6 times)
  POST /interview/{application_id}/feedback  -> final evaluation (saved, returned again on later calls)
  GET  /interview/{application_id}           -> latest interview (plan + transcript + feedback), extra

Unlocked only for applications in status applied/interviewing/rejected/offer (with a snapshot).
Proxy (BLUEPRINT sec. 9): if application_id is not in the DB but is the id of
fixtures/application.json, that fake application (already applied) is used.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from fixtures import load_fixture
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


@router.post("/{application_id}/feedback", response_model=InterviewFeedback)
def interview_feedback(application_id: int, db: Session = Depends(get_db)):
    """Final evaluation (~10-20 s). Also works for an interview stopped early
    (unanswered questions get score 1). Computed once, then returned from the DB."""
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
