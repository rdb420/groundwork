# Groundwork

YSH's knowledge-gathering portal. Staff sign in with an emailed link, share the files they work
from, and map how their work flows on a BPMN canvas. Mapping sessions can be recorded and
transcribed, and AI drafts SOPs, map suggestions and follow-up questions for people to review.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design, security model and rollout plan,
[docs/LIVE_MAPPING.md](docs/LIVE_MAPPING.md) for the live canvas driven by Jev, and
[docs/TEST_RUN.md](docs/TEST_RUN.md) for a first test run with stand-in models, and
[docs/AUDIT.md](docs/AUDIT.md) for the pre-pilot audit and its progress.

## Tooling

The backend is managed with [uv](https://docs.astral.sh/uv/) and the frontend with
[pnpm](https://pnpm.io/). Don't use pip, venv, npm or yarn in this repository.

| | Backend | Frontend |
|---|---|---|
| Runtime | Python 3.12, pinned in `backend/.python-version`; `uv python install` fetches it | Node 22 |
| Dependencies | `pyproject.toml` and `uv.lock`; `uv add <pkg>`, `uv add --dev <pkg>` | `package.json` and `pnpm-lock.yaml`; `pnpm add <pkg>`, `pnpm add -D <pkg>` |
| Install | `uv sync` | `corepack enable && pnpm install` |
| Run a command | `uv run <cmd>` | `pnpm run <script>` |

## Run it locally

```bash
# API
cd backend
uv python install     # once; uv sync also fetches it when missing
uv sync
GW_DATA_DIR=../data uv run uvicorn app.main:app --reload --port 8000

# Worker (second terminal)
cd backend
GW_DATA_DIR=../data uv run python -m app.worker

# Frontend (third terminal)
cd frontend
pnpm install
pnpm run dev          # http://localhost:5173, proxies /api to :8000
```

With no SMTP configured, sign-in links print to the API console. Copy the link into the browser.

To make yourself an analyst locally, start the API with `GW_ANALYST_EMAILS=you@example.com.au`.

## Deploy on one host

```bash
cp .env.example .env        # fill in hostname, domains, SMTP, AI and transcription settings
docker compose up -d --build
```

Choose the HTTPS option in `deploy/Caddyfile` (office network, public subdomain, or Tailscale).
Schedule `deploy/backup.sh` nightly and copy `data/backups/` off the host.

To catch sign-in emails while testing: `docker compose --profile dev up -d`, set
`GW_SMTP_HOST=mailpit`, `GW_SMTP_PORT=1025`, `GW_SMTP_STARTTLS=false`, and open port 8025.

## AI and transcription

| Setting | Values |
|---|---|
| `GW_AI_PROVIDER` | `none`, `openai` (OpenAI with `GW_OPENAI_API_KEY` and `GW_OPENAI_MODEL`, or any OpenAI-compatible endpoint), `ollama` (local, point `GW_OLLAMA_URL` at the inference box), `anthropic` |
| `GW_DECISION_PROVIDER` | `none`, `openrouter` (TypeSafe Jev through OpenRouter's System One API, with `GW_OPENROUTER_API_KEY`), `jev` (TypeSafe directly, or a Laya or OpenJev server via `GW_DECISION_URL`) |
| `GW_TRANSCRIPTION_PROVIDER` | `none`, `faster_whisper` (build with `WITH_WHISPER=true`, or `uv sync --extra whisper` locally), `openai_compatible` (a Whisper server URL) |

The default set-up runs live mapping on Jev through OpenRouter and drafting and review on OpenAI.
Put both keys in `.env`, then check they answer:

```bash
cd backend && uv run python -m scripts.check_providers
```

Maps and files flagged as holding personal information never go to a cloud model unless
`GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO=true`.

## Checks

CI runs the same checks on every push and pull request.

```bash
cd backend && uv run ruff check app tests scripts && uv run mypy app && uv run pytest -q
cd frontend && pnpm run lint && pnpm run test && pnpm run build
```

## Layout

```
backend/app/
  main.py              app, routers, serves the built frontend
  config.py            every setting (env prefix GW_)
  models.py            tables
  security.py          tokens, sessions, roles, CSRF header
  routers/             auth, artifacts, processes (catalogue, merge), boards (maps, recordings, AI), admin (coverage, retention, purge)
  ai/context.py        canvas to structured text
  ai/generate.py       prompts, personal-info guard, draft storage
  ai/providers.py      Ollama, Anthropic and OpenAI-compatible over HTTP
  live/                live mapping: Jev client, vocabulary, spans, interpreter, reviewer, rule tables, combiner
  routers/live.py      sentence in, map changes out; passes, parking lot, rules, checks, review, combine, document
  processing/          workbook profiler, document text extraction
  worker.py            job loop, daily retention
  scan.py              ClamAV malware check for uploads
  retention.py         purge withdrawn files and old session audio
  backup.py            snapshot, archive, restore check
  seed.py              starter process catalogue (confirm with the business)
frontend/src/
  pages/               Login, Verify, Home, Share, Library, Boards, BoardPage, Coverage, ProcessList, Retention
  canvas/              BPMN and context nodes, palette, op engine, live, recording, document and AI panels
backend/scripts/       live_eval.py, labelled sample sentences, fake_models.py (stand-ins for testing)
deploy/                Dockerfile, Caddyfile, backup script
docs/ARCHITECTURE.md
```
