"""Checks that fixtures/*.json comply with schemas.py.  Usage (from backend/):  uv run python scripts/check_fixtures.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import TypeAdapter, ValidationError  # noqa: E402

from fixtures import load_fixture  # noqa: E402
from schemas import ApplicationOut, InterviewOut, JobOut, ProfileOut, RadarResponse  # noqa: E402

CHECKS = {
    "profile": ProfileOut,
    "jobs": list[JobOut],
    "radar_response": RadarResponse,
    "application": ApplicationOut,
    "interview": InterviewOut,
}

ok = True
for name, schema in CHECKS.items():
    try:
        TypeAdapter(schema).validate_python(load_fixture(name))
        print(f"OK    {name}.json")
    except (ValidationError, FileNotFoundError) as err:
        ok = False
        print(f"ERROR {name}.json\n{err}\n")
sys.exit(0 if ok else 1)
