"""Import from the browser extension (owner: Matilde). STUB: answers with a fake job_id.

Note: this router must be included in main.py BEFORE routers/jobs.py
(POST /jobs/import must not end up on /jobs/{job_id}).
"""

from fastapi import APIRouter

from schemas import JobImportRequest, JobImportResponse

router = APIRouter(prefix="/jobs", tags=["imports"])


@router.post("/import", response_model=JobImportResponse)
def import_job(body: JobImportRequest):
    return {"job_id": 1, "created": True}
