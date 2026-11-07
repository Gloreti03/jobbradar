"""Lettura/scrittura del profilo nel DB. Un solo utente demo → una sola riga (id 1).

Per gli altri moduli (ranking, tailoring, colloquio):
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
    """Crea o aggiorna il profilo. extra_text=None lascia quello esistente."""
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


def to_out(row: ProfileRow) -> dict[str, Any]:
    """Riga DB → forma di ProfileOut."""
    return {"id": row.id, "profile": row.data, "extra_text": row.extra_text, "updated_at": row.updated_at}
