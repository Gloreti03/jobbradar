"""D — URL firmato ElevenLabs (owner: Matilde). STUB: URL finto."""

from fastapi import APIRouter

from schemas import SignedUrlResponse

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/signed-url", response_model=SignedUrlResponse)
def signed_url():
    return {"signed_url": "wss://example.invalid/stub-signed-url"}
