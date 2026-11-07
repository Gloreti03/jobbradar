# RADAR

Webapp + estensione per chi cerca lavoro a Oslo. Tutto il progetto è descritto in [BLUEPRINT.md](BLUEPRINT.md).

## Avvio backend

Serve solo [uv](https://docs.astral.sh/uv/) (installa da solo Python 3.12).

```bash
cd backend
uv sync                      # crea .venv identico per tutti (da uv.lock)
cp .env.example .env         # poi inserisci DEEPSEEK_API_KEY
uv run uvicorn main:app --reload --port 8000
```

- API: http://localhost:8000 · documentazione interattiva: http://localhost:8000/docs
- All'inizio ogni endpoint è uno **stub** che restituisce il file corrispondente in `fixtures/`.
- Nuova libreria: `uv add <pacchetto>` e committa `pyproject.toml` + `uv.lock` (avvisa il gruppo).
- Se cambi una fixture: `uv run python scripts/check_fixtures.py`.
- Se cambiano le tabelle (`models.py`): cancella `backend/radar.db` e riavvia.

## Git

Un branch per persona (`git switch -c <nome>`), aggiornato spesso con `git pull origin main`.
Il merge su `main` lo fa Gabriele.
