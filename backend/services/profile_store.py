"""Read/write the profile in the DB. A single demo user -> a single row (id 1).

For the other modules (ranking, tailoring, interview):
    from services.profile_store import get_profile
    profile = get_profile(db)   # Profile | None
"""

from typing import Any

from sqlalchemy.orm import Session

from models import ProfileRow
from schemas import Profile

PROFILE_ID = 1


def get_profile_row(db: Session) -> ProfileRow | None:
    return db.get(ProfileRow, PROFILE_ID)


def get_profile(db: Session) -> Profile | None:
    row = get_profile_row(db)
    return Profile.model_validate(row.data) if row else None


def save_profile(db: Session, profile: Profile, extra_text: str | None = None) -> ProfileRow:
    """Create or update the profile. extra_text=None keeps the existing one."""
    row = get_profile_row(db)
    data: dict[str, Any] = profile.model_dump(mode="json")
    if row is None:
        row = ProfileRow(id=PROFILE_ID, data=data, extra_text=extra_text or "")
        db.add(row)
    else:
        row.data = data
        if extra_text is not None:
            row.extra_text = extra_text
    db.commit()
    db.refresh(row)
    return row


def to_out(row: ProfileRow, warnings: list[str] | None = None) -> dict[str, Any]:
    """DB row -> ProfileOut shape."""
    return {
        "id": row.id,
        "profile": row.data,
        "extra_text": row.extra_text,
        "updated_at": row.updated_at,
        "warnings": warnings or [],
    }
