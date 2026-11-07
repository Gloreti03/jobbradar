"""C — Candidature (owner: Gabriele). STUB: restituisce fixtures/application.json."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from fixtures import fixture_job, load_fixture
from schemas import ApplicationCreate, ApplicationOut, ApplicationPatch

router = APIRouter(prefix="/applications", tags=["applications"])


def _fixture_application(application_id: int) -> dict:
    app = load_fixture("application")
    if application_id != app["id"]:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return app


@router.get("", response_model=list[ApplicationOut])
def list_applications():
    return [load_fixture("application")]


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(body: ApplicationCreate):
    app = load_fixture("application")
    app.update(
        job_id=body.job_id,
        job=fixture_job(body.job_id),
        status="draft",
        snapshot=None,
        applied_at=None,
        created_at=datetime.now(timezone.utc),
    )
    return app


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int):
    return _fixture_application(application_id)


@router.patch("/{application_id}", response_model=ApplicationOut)
def patch_application(application_id: int, body: ApplicationPatch):
    app = _fixture_application(application_id)
    app.update(body.model_dump(exclude_none=True, mode="json"))
    return app
