"""B — Job detail (owner: Stefano). STUB: reads fixtures/jobs.json + radar_response + application."""

from fastapi import APIRouter

from fixtures import fixture_job, load_fixture
from schemas import JobDetail

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: int):
    job = fixture_job(job_id)
    match = next((r["match"] for r in load_fixture("radar_response")["results"] if r["job"]["id"] == job_id), None)
    app = load_fixture("application")
    application = {"id": app["id"], "status": app["status"]} if app["job_id"] == job_id else None
    return {"job": job, "match": match, "application": application}
