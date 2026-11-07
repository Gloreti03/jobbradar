"""D — Colloquio simulato (owner: Matilde). STUB: segue il piano di fixtures/interview.json.

Lo stub tiene il numero di domanda in memoria (si azzera al riavvio).
"""

from fastapi import APIRouter

from fixtures import load_fixture
from schemas import (
    InterviewFeedback,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
)

router = APIRouter(prefix="/interview", tags=["interview"])

_progress: dict[int, int] = {}  # application_id -> indice della domanda in corso


def _interviewer_messages() -> list[str]:
    return [t["content"] for t in load_fixture("interview")["transcript"] if t["role"] == "interviewer"]


@router.post("/{application_id}/start", response_model=InterviewStartResponse)
def start_interview(application_id: int, body: InterviewStartRequest | None = None):
    interview = load_fixture("interview")
    _progress[application_id] = 0
    return {
        "interview_id": interview["id"],
        "application_id": application_id,
        "mode": body.mode if body else "text",
        "plan": interview["plan"],
        "message": _interviewer_messages()[0],
        "question_index": 0,
    }


@router.post("/{application_id}/turn", response_model=InterviewTurnResponse)
def interview_turn(application_id: int, body: InterviewTurnRequest):
    messages = _interviewer_messages()  # 6 domande + messaggio di chiusura
    index = min(_progress.get(application_id, 0) + 1, len(messages) - 1)
    _progress[application_id] = index
    return {
        "interview_id": load_fixture("interview")["id"],
        "message": messages[index],
        "question_index": index,
        "done": index == len(messages) - 1,
    }


@router.post("/{application_id}/feedback", response_model=InterviewFeedback)
def interview_feedback(application_id: int):
    return load_fixture("interview")["feedback"]
