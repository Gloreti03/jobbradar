"""D — ElevenLabs signed URL (owner: Matilde).

GET /voice/signed-url asks ElevenLabs for a short-lived signed URL of our Agent, so the
API key stays in backend/.env and the frontend (SDK React) connects with the URL only.
Needs ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID in backend/.env; without them -> 503
and the UI stays in text mode.
"""

import httpx
from fastapi import APIRouter, HTTPException

from config import ELEVENLABS_AGENT_ID, ELEVENLABS_API_KEY
from schemas import SignedUrlResponse

router = APIRouter(prefix="/voice", tags=["voice"])

SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"


@router.get("/signed-url", response_model=SignedUrlResponse)
def signed_url():
    if not ELEVENLABS_API_KEY or not ELEVENLABS_AGENT_ID:
        raise HTTPException(status_code=503, detail="Voice is not configured: use text mode")
    try:
        resp = httpx.get(
            SIGNED_URL_ENDPOINT,
            params={"agent_id": ELEVENLABS_AGENT_ID},
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=10,
        )
    except httpx.HTTPError as err:
        raise HTTPException(status_code=502, detail=f"ElevenLabs not reachable: {err}") from err
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error {resp.status_code}: use text mode")
    url = resp.json().get("signed_url")
    if not url:
        raise HTTPException(status_code=502, detail="ElevenLabs returned no signed URL")
    return {"signed_url": url}
