""""I applied" + snapshot (owner: Matilde).

POST /applications/{id}/applied:
- saves a SNAPSHOT of what was actually sent (job + CV + cover letter + applied_at): the mock
  interview is based on it, so later edits to the job or to the documents do not change it;
- moves the status from draft to applied.
Idempotent: calling it again on an application already applied returns it unchanged
(the original snapshot is never overwritten).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from models import JobRow
from radar.providers.base import job_out
from schemas import ApplicationOut, Snapshot, TailoredCV
from services.application_store import application_out, get_application_row

router = APIRouter(prefix="/applications", tags=["tracking"])


@router.post("/{application_id}/applied", response_model=ApplicationOut)
def mark_applied(application_id: int, db: Session = Depends(get_db)):
    row = get_application_row(db, application_id)  # 404 if missing

    if row.snapshot is None:
        now = datetime.now(timezone.utc)
        snapshot = Snapshot(
            job=job_out(db.get(JobRow, row.job_id)),
            cv=TailoredCV.model_validate(row.cv),
            cover_letter=row.cover_letter,
            applied_at=now,
        )
        row.snapshot = snapshot.model_dump(mode="json")
        row.applied_at = now

    if row.status == "draft":
        row.status = "applied"

    db.commit()
    db.refresh(row)
    return application_out(db, row)
