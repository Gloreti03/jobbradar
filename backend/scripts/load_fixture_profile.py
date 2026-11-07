"""Saves fixtures/profile.json into the local DB, to work without uploading a CV.
Usage (from backend/):  uv run python scripts/load_fixture_profile.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal, init_db  # noqa: E402
from fixtures import load_fixture  # noqa: E402
from schemas import Profile  # noqa: E402
from services.profile_store import save_profile  # noqa: E402

init_db()
fx = load_fixture("profile")
with SessionLocal() as db:
    row = save_profile(db, Profile.model_validate(fx["profile"]), fx["extra_text"])
    print(f"Profile '{row.data['name']}' saved with id {row.id}")
