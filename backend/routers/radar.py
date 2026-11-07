"""B — Radar (owner: Stefano). STUB: returns fixtures/radar_response.json."""

from fastapi import APIRouter

from fixtures import load_fixture
from schemas import RadarRequest, RadarResponse

router = APIRouter(prefix="/radar", tags=["radar"])


@router.post("", response_model=RadarResponse)
def run_radar(body: RadarRequest):
    data = load_fixture("radar_response")
    if body.english_only:
        data["results"] = [r for r in data["results"] if not r["job"]["norwegian_required"]]
    data["days_requested"] = body.days
    data["days_used"] = max(body.days, data["days_used"])
    return data
