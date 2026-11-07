# JobbRadar

Web app + browser extension for people job hunting in Oslo. The whole project is described in [BLUEPRINT.md](BLUEPRINT.md) (in Italian).

## Run the backend

You only need [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 by itself).

```bash
cd backend
uv sync                      # creates the same .venv for everyone (from uv.lock)
cp .env.example .env         # then set DEEPSEEK_API_KEY
uv run uvicorn main:app --reload --port 8000
```

- API: http://localhost:8000 · interactive docs: http://localhost:8000/docs
- Load the shared job seed into your local DB: `uv run python scripts/scan.py --load-seed`
- Load the sample profile (to work without uploading a CV): `uv run python scripts/load_fixture_profile.py`
- Endpoints that are not implemented yet are **stubs** that return the matching file in `fixtures/`.
- New library: `uv add <package>`, then commit `pyproject.toml` + `uv.lock` (tell the group).
- If you change a fixture: `uv run python scripts/check_fixtures.py`.
- Full path check A -> B -> C -> D against the running backend: `uv run python scripts/e2e.py`
  (~1.5 min, uses `fixtures/sample_cv.pdf`; it writes to your DB, so never run it on the demo DB).
- If the tables change (`models.py`): delete `backend/radar.db` and restart.

## Git

One branch per person (`git switch -c <name>`), kept up to date with `git pull origin main`.
Gabriele merges into `main`.

## Language

Code, comments, docstrings, commit messages and this README are in English.
Only `BLUEPRINT.md` stays in Italian.
