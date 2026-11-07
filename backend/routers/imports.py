"""Import dall'estensione (owner: Matilde). STUB: risponde con un job_id finto.

Nota: questo router va incluso in main.py PRIMA di routers/jobs.py
(POST /jobs/import non deve finire su /jobs/{job_id}).
"""

from fastapi import APIRouter

from schemas import JobImportRequest, JobImportResponse

router = APIRouter(prefix="/jobs", tags=["imports"])


@router.post("/import", response_model=JobImportResponse)
def import_job(body: JobImportRequest):
    return {"job_id": 1, "created": True}
