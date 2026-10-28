# AI Research Assistant

Small, local research agent that:
- plans sub-searches for a question
- searches the web via Tavily
- scrapes content with BeautifulSoup
- embeds text with sentence-transformers into pgvector
- writes a cited report using Google Generative AI (Gemini)

This README explains setup, configuration (including which Gemini model to use), and troubleshooting for quota-related issues.

**Stack:** Django (backend) · React (frontend) · pgvector · Tavily · Gemini

---

## Quick Start (Docker)

1. Copy the example env and edit it:

```bash
cp .env.example .env
# open .env and add your keys/config
```

2. Set these important vars in `.env`:

- `GEMINI_API_KEY` — your Google API key (from the project with Generative AI enabled)
- `TAVILY_API_KEY` — your Tavily key
- `GEMINI_MODEL` — model to use (defaults to `gemini-2.5-flash`) — see notes below
- `FORCE_MOCK_GEMINI` — set `True` to force mock Gemini responses
- `FORCE_MOCK_EMBEDDINGS` — set `True` to avoid loading heavy embedding models (returns zero vectors)

Example `.env` snippet:

```
GEMINI_API_KEY=AIzaSy...
TAVILY_API_KEY=tvly-...
GEMINI_MODEL=gemini-2.5-flash
FORCE_MOCK_GEMINI=False
FORCE_MOCK_EMBEDDINGS=False
```

3. Start with Docker Compose:

```bash
docker compose up --build
```

The first run may take several minutes while Python packages and the embedding model download.

Open the frontend at http://localhost:5173 and register/login.

---

## Configuration: Gemini model

Recent Google quota changes restrict some older models (for example `gemini-2.0-flash` may show `limit: 0`). The project defaults to `gemini-2.5-flash` which is commonly available.

To change model, edit `.env`:

```
GEMINI_MODEL=gemini-2.5-flash-lite
```

If you keep hitting `ResourceExhausted` with `limit: 0`, either:

- enable billing on the Google Cloud project that created the API key, or
- choose a different allowed model (e.g., `gemini-2.5-flash-lite`).

Check quotas in Google Cloud: Console → APIs & Services → Quotas → filter `generativelanguage.googleapis.com`.

---

## Running / Development commands

```bash
docker compose up --build    # first time (or after changes)
docker compose up            # subsequent runs
docker compose down          # stop
docker compose down -v       # stop + wipe DB
docker logs -f research_backend
```

Backend API endpoints (prefix `/api/`):

- `POST /api/auth/register/` — register
- `POST /api/auth/login/` — login
- `GET /api/auth/me/` — current user
- `POST /api/research/` — create research job
- `GET /api/research/<id>/stream/` — SSE stream (needs `?token=...` query)

---

## Testing the Gemini connection (quick)

If you want to verify the Gemini key from inside the backend container:

```bash
docker exec -it research_backend python - <<'PY'
import os
import google.generativeai as genai
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
m = genai.GenerativeModel(os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'))
print(m.generate_content('Say hello in one line').text)
PY
```

If this raises `ResourceExhausted` with `limit: 0`, follow the troubleshooting steps below.

---

## Troubleshooting

- Backend crashes on startup:

```bash
docker compose down -v && docker compose up --build
```

- SSE returns `406 Not Acceptable`:

Rebuild the backend (`docker compose up --build`) — the SSE view uses a plain Django view (not DRF) and requires the current `views.py`.

- Gemini `ResourceExhausted (limit: 0)`:

1. Confirm which Google Cloud project created the key (top-left project selector in Console).
2. Enable the **Generative Language API** (a.k.a. Generative AI) for that project.
3. Link a billing account to the project. Many quotas are 0 until billing is enabled.
4. Check Quotas: Console → APIs & Services → Quotas → filter `generativelanguage.googleapis.com`.
5. If the selected model is restricted, try switching `GEMINI_MODEL` to `gemini-2.5-flash-lite`.

- Want to avoid using the real API during development?

Set these in `.env`:

```
FORCE_MOCK_GEMINI=True
FORCE_MOCK_EMBEDDINGS=True
```

With those set the backend will not call Gemini or load sentence-transformers; useful for offline UI testing.

---

## Project structure (high level)

```
ai-research-assistant/
├── docker-compose.yml
├── .env.example
├── backend/         # Django app, API, agent pipeline
└── frontend/        # React app
```

Key backend files:

- `backend/research/agent/tools.py` — Gemini client, scraper, embedder, retriever
- `backend/research/agent/agent.py` — 5-step pipeline (plan, search, scrape, embed, write)
- `backend/research/views.py` — auth, research endpoints, SSE stream

---

## Deploying (Render + optional Vercel)

The backend can't run on Vercel: a research run takes minutes and streams progress over SSE, and
Vercel's serverless functions time out and stop background threads. Host the **backend and database
on Render**; the frontend can go on Render or Vercel.

### 1. Backend + database on Render

1. Push this repo to GitHub.
2. Render dashboard → **New → Blueprint** → select the repo. `render.yaml` creates:
   - `research-db` — Postgres (pgvector is enabled by the first migration)
   - `research-backend` — Django API with gunicorn
   - `research-frontend` — the React app as a static site (delete it from the blueprint if you use Vercel)
3. When prompted, fill in `GEMINI_API_KEY`, `TAVILY_API_KEY`, `CORS_ALLOWED_ORIGINS` (your frontend URL)
   and `VITE_API_URL` (your backend URL, e.g. `https://research-backend.onrender.com`).
4. Check `https://<backend>/api/health/` — it shows the active Gemini model and whether mocks are on.

Notes:
- Free/Starter plans have 512 MB RAM, too little for the sentence-transformers model, so the blueprint
  sets `FORCE_MOCK_EMBEDDINGS=True` (keyword-hash retrieval). On Standard (2 GB) or higher set it to `False`.
- Free web services sleep after 15 min idle (the first request then takes ~1 min); free databases expire after 30 days.
- `VITE_API_URL` is baked in at build time — redeploy the frontend after changing it.

### 2. Frontend on Vercel (instead of Render)

1. Vercel → **Add New Project** → import the repo, set **Root Directory** to `frontend`
   (`frontend/vercel.json` configures the Vite build and SPA routing).
2. Add the environment variable `VITE_API_URL=https://<your-backend>.onrender.com` and deploy.
3. Add the Vercel URL (e.g. `https://my-app.vercel.app`) to the backend's `CORS_ALLOWED_ORIGINS` on Render.
