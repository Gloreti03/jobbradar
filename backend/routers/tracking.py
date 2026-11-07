""""I applied" + snapshot (owner: Matilde). STUB: restituisce fixtures/application.json (già applied)."""

from fastapi import APIRouter, HTTPException

from fixtures import load_fixture
from schemas import ApplicationOut

router = APIRouter(prefix="/applications", tags=["tracking"])


@router.post("/{application_id}/applied", response_model=ApplicationOut)
def mark_applied(application_id: int):
    app = load_fixture("application")
    if application_id != app["id"]:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return app
