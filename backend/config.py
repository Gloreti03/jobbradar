"""Settings read from backend/.env (single place, imported by everyone)."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent
FIXTURES_DIR = REPO_DIR / "fixtures"

load_dotenv(BACKEND_DIR / ".env")

# --- DeepSeek ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_SMART = os.getenv("MODEL_SMART", "deepseek-v4-pro")
MODEL_FAST = os.getenv("MODEL_FAST", "deepseek-flash")

# --- ElevenLabs ---
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")

# --- Database: "sqlite:///./x.db" is relative to backend/, whatever the working directory ---
_db_url = os.getenv("DATABASE_URL", "sqlite:///./radar.db")
if _db_url.startswith("sqlite:///./"):
    _db_url = f"sqlite:///{(BACKEND_DIR / _db_url.removeprefix('sqlite:///./')).as_posix()}"
DATABASE_URL = _db_url

# --- CORS ---
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:8080")  # any localhost port is allowed anyway (main.py)
