"""Lettura dei file di fixtures/ (usati dagli stub finché la logica vera non è pronta)."""

import json
from typing import Any

from fastapi import HTTPException

from config import FIXTURES_DIR


def load_fixture(name: str) -> Any:
    """`load_fixture("profile")` → contenuto di fixtures/profile.json (copia nuova a ogni chiamata)."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def fixture_job(job_id: int) -> dict[str, Any]:
    for job in load_fixture("jobs"):
        if job["id"] == job_id:
            return job
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
