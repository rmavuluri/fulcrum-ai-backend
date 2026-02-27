# Fulcrum AI Backend

Python (Flask) backend for Fulcrum AI. The **frontend (fulcrum-ai)** gets a sandbox token from this backend, then calls API endpoints with that token.

## Flow

1. **Frontend** calls `GET /api/sandbox-token` (no auth) → receives `{ access_token, expires_in }`.
2. **Frontend** stores the token and sends `Authorization: Bearer <access_token>` on all other requests (e.g. `POST /api/chat`, `GET /api/documents`).
3. **Backend** uses the token when calling the Ally sandbox for chat (or generates one if the request has no token).

## Setup

1. Copy `.env.example` to `.env`.
2. Set `USE_ALLY_SANDBOX=1`, `SANDBOX_CLIENT_KEY`, and `SANDBOX_CLIENT_SECRET` for Ally sandbox.
3. Set `PORT` and `FRONTEND_URL` as needed.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Backend runs at `http://localhost:3001`. Frontend should set `VITE_API_URL=http://localhost:3001`.

## Endpoints

- `GET /api/health` – health check.
- `GET /api/sandbox-token` – returns `{ access_token, expires_in }` for the frontend. Call this first.
- `GET /api/documents` – list document IDs. Optional: `Authorization: Bearer <sandbox_token>`.
- `POST /api/chat` – chat. Body: `{ "message": "..." }` or `{ "query": "..." }`. Returns `{ "response": "..." }`. Send `Authorization: Bearer <sandbox_token>` (token from `/api/sandbox-token`).
