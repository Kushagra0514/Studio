# Studio

Studio is a local retrieval-augmented generation (RAG) application for indexing PDF, DOCX, and TXT documents, optionally ingesting web pages, and asking questions with source citations. It combines a React frontend, a FastAPI backend, embedded Qdrant storage, local embedding models, and Groq-hosted language models.

Studio is intended for one trusted local user per installation. Compose publishes Studio and the optional local Firecrawl API on `127.0.0.1` only. Each user supplies their own Groq API key through the browser prompt; `.env` remains available as an optional server-side fallback for CLI and evaluation tools. Studio does not provide the controls required for a LAN-shared or internet-facing service.

## What it does

- Routes questions between conversation, local document search, and optional web search.
- Indexes documents with dense `BAAI/bge-small-en-v1.5` and sparse `Qdrant/bm25` embeddings.
- Uses reciprocal-rank fusion for hybrid retrieval.
- Stores indexed chunks and vectors locally.
- Displays cited source passages alongside generated answers.
- Saves one shared chat history on disk.

## Architecture

The main Compose file starts two services:

| Service | Implementation | Host port |
|---|---|---:|
| `frontend` | React production build served by Nginx | `127.0.0.1:80` |
| `backend` | FastAPI application running with Uvicorn | `127.0.0.1:8000` |

Qdrant is **not** a separate server or Compose service. The backend opens an embedded, file-backed Qdrant database through `QdrantClient(path=...)`. Only one backend process should use that directory at a time.

The optional Firecrawl stack is separate from the main application. When enabled, its API is exposed at `127.0.0.1:3002`.

The following data flow describes the Docker deployment:

```text
Browser
  └─ http://localhost (Nginx + React)
       └─ /api/* → backend:8000
                      ├─ embedded Qdrant → data/qdrant/
                      ├─ chat JSON       → data/chat/history.json
                      ├─ local models    → data/models/
                      ├─ Groq API
                      └─ optional Firecrawl API → host:3002 or hosted service
```

## Repository layout

```text
backend/       FastAPI package, dependency files, and backend Dockerfile
frontend/      React source, Nginx configuration, and frontend Dockerfile
scripts/       Command-line client
evals/         Dataset generation and evaluation utilities
infra/         Optional local Firecrawl Compose stack
tests/         Offline backend tests
data/          Ignored runtime data; created automatically
```

## Prerequisites

For the Docker quick start:

- Docker Desktop, or Docker Engine with the Compose plugin.
- Internet access for the first image build and model downloads.
- A personal Groq API key for LLM-powered actions. Normal UI users enter it through the browser prompt; `.env` is optional.

For local development without the application containers:

- Python 3.11 is the reference backend version used by the Docker image and lock file.
- Node.js `^20.19.0` or `>=22.12.0`, as required by the installed Vite release.
- npm.
- Docker only if using the optional local Firecrawl stack.

## Docker quick start

Run these commands from the repository root.

1. Create `.env` from the committed template if it does not already exist:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

   On macOS or Linux:

   ```bash
   test -e .env || cp .env.example .env
   ```

2. Leave `GROQ_API_KEY` blank for the normal personal-key flow and enter your own key when the frontend prompts. Set it in `.env` only when CLI or evaluation tools need a server-side fallback. Never commit `.env`.

3. Validate, build, and start Studio:

   ```powershell
   docker compose config --quiet
   docker compose up --build -d
   docker compose ps
   ```

   The first startup can take several minutes because the backend downloads embedding models. The frontend waits for the backend health check before starting. Follow progress with:

   ```powershell
   docker compose logs backend --tail 100 -f
   ```

4. Verify the application:

   ```powershell
   Invoke-RestMethod http://localhost:8000/api/health
   (Invoke-WebRequest http://localhost/).StatusCode
   ```

   On macOS or Linux:

   ```bash
   curl --fail http://localhost:8000/api/health
   curl --fail --head http://localhost/
   ```

Open the following URLs after the backend reports healthy:

- Frontend: [http://localhost](http://localhost)
- API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Readiness endpoint: [http://localhost:8000/api/health](http://localhost:8000/api/health)

`docker compose down` stops the application without removing the bind-mounted files under `data/`.

## Environment variables

The safe template is [.env.example](.env.example). Compose reads the root `.env` file but does not copy it into either image.

| Variable | Required | Meaning |
|---|---|---|
| `GROQ_API_KEY` | CLI/evaluation fallback only | Optional server-side key used by CLI, evaluation, and other non-browser LLM paths. Normal UI users supply their own key through the browser prompt. |
| `FIRECRAWL_API_KEY` | Hosted Firecrawl only | Credential for the hosted Firecrawl service. The local stack accepts the development placeholder. |
| `FIRECRAWL_API_URL` | No | Firecrawl endpoint. Use `http://host.docker.internal:3002` from the backend container, `http://localhost:3002` from a local Python process, or `https://api.firecrawl.dev` for hosted Firecrawl. |
| `STUDIO_DATA_DIR` | No | Root for Qdrant, chat history, and application-managed directories. Local Python defaults to the repository's `data/`; Compose explicitly uses `/app/data` in the container. |
| `STUDIO_MAX_UPLOAD_BYTES` | No | Backend upload limit in bytes; defaults to `52428800` (50 MiB). Nginx separately limits requests to `50M`. |

The frontend stores the key entered in its modal in browser `localStorage` under `groq_api_key` and sends it only to the loopback backend in the `X-Groq-Api-Key` header. This is acceptable for Studio's trusted local-only model, but it is not a secure secret store. Clear the browser's site data to remove it. Do not change the loopback bindings to LAN or public interfaces without completing the optional production-hardening phase.

## Local development

Local commands assume the repository root is the current directory and `.env` exists. Keep `STUDIO_DATA_DIR=data` for the repository-local data layout. If a locally running backend should use local Firecrawl, set `FIRECRAWL_API_URL=http://localhost:3002`.

### Backend

Create the environment and install the locked runtime plus test dependencies:

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Start the API:

```powershell
venv\Scripts\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --reload --port 8000
```

On macOS or Linux, replace `venv\Scripts\python.exe` with `venv/bin/python`.

### Frontend

In another shell, install exactly the locked dependencies and start Vite:

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to `http://localhost:8000`; the backend permits development CORS only from `localhost:5173` and `127.0.0.1:5173`.

### CLI and evaluation tools

The CLI preserves the `ingest` and `ask` commands:

```powershell
venv\Scripts\python.exe -m scripts.rag_cli ingest <document-path>
venv\Scripts\python.exe -m scripts.rag_cli ask "<question>"
```

Evaluation utilities use the ignored root-level `dataset.json` and `eval_history.csv` files:

```powershell
venv\Scripts\python.exe -m evals.generate_dataset
venv\Scripts\python.exe -m evals.evaluate
```

These commands call external LLM services and can incur API usage. They are not part of the offline test suite.

## Document and URL ingestion

- Direct uploads accept `.pdf`, `.docx`, and `.txt` files.
- The backend and Nginx both default to a 50 MiB limit.
- Uploads are parsed from temporary files. Original uploaded files are deleted afterward; indexed chunks and source metadata are stored in Qdrant.
- URL ingestion accepts only HTTP and HTTPS URLs.
- Firecrawl is attempted first for URL ingestion. If it fails, Studio attempts direct URL conversion with Docling.
- Web-search routing uses Firecrawl and falls back to local document search when Firecrawl fails.

If `STUDIO_MAX_UPLOAD_BYTES` is raised above 50 MiB, update `client_max_body_size` in `frontend/nginx.conf` too. A smaller backend value requires no Nginx change.

## Firecrawl options

Firecrawl is optional for ordinary document ingestion and local document search.

### Hosted Firecrawl

Set the following in `.env` and do not start the local Firecrawl Compose stack:

```env
FIRECRAWL_API_KEY=replace_with_your_firecrawl_api_key
FIRECRAWL_API_URL=https://api.firecrawl.dev
```

Hosted usage is subject to the provider's availability, billing, and limits.

### Local Firecrawl

Validate and start the separate stack:

```powershell
docker compose -f infra\firecrawl-docker-compose.yaml config --quiet
docker compose -f infra\firecrawl-docker-compose.yaml up -d
docker compose -f infra\firecrawl-docker-compose.yaml ps
```

The stack starts Firecrawl API, Playwright, Redis, RabbitMQ, and PostgreSQL containers. Its images currently use `latest` tags and its configured resource limits are substantial, so it is less reproducible and heavier than the main Studio stack.

Use the endpoint appropriate to where the backend runs:

```env
# Main Studio backend in Docker
FIRECRAWL_API_URL=http://host.docker.internal:3002

# Backend running directly on the host
FIRECRAWL_API_URL=http://localhost:3002
```

Inspect or stop the optional stack with:

```powershell
docker compose -f infra\firecrawl-docker-compose.yaml logs api --tail 100
docker compose -f infra\firecrawl-docker-compose.yaml down
```

The Firecrawl stack does not contain Studio's Qdrant database or chat history.

## Persistent data

The Compose deployment keeps its runtime state under one ignored data root. Compose bind-mounts these host directories into the backend container:

| Host path | Contents |
|---|---|
| `data/qdrant/` | Embedded Qdrant collection, indexed chunks, and vectors |
| `data/chat/history.json` | One shared chat-history JSON document |
| `data/models/cache/` | Downloaded model and library caches |
| `data/models/local/` | Additional library-local model state |
| `data/documents/` | Reserved upload directory; the current API does not retain uploaded originals |

For a backend run directly on the host, `STUDIO_DATA_DIR` still controls Qdrant, chat history, and the application-managed directories. Hugging Face, FastEmbed, and related libraries currently use their normal per-user cache locations instead of `data/models/`. Removing the repository's `data/` directory therefore does not clear those host-level caches.

Do not copy or back up the embedded Qdrant directory while the backend is running. Stop Studio first so its files are consistent.

### Back up data

The following PowerShell commands stop Studio and copy `data/` to a timestamped sibling directory outside the repository:

```powershell
docker compose down
$studioBackup = Join-Path .. ("Studio-data-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
Copy-Item -LiteralPath .\data -Destination $studioBackup -Recurse
Write-Host "Backup created at $studioBackup"
```

On macOS or Linux:

```bash
docker compose down
cp -a ./data "../Studio-data-backup-$(date +%Y%m%d-%H%M%S)"
```

Retain the backup until the application has restarted and its documents and history have been checked. Restore only while Studio is stopped, and preserve or rename the current `data/` directory before copying a backup into its place.

### Migrate the previous layout

This migration is manual and copy-only. Stop Studio, copy existing files, verify them in the new layout, and keep the old directories as a rollback copy.

```powershell
docker compose down
New-Item -ItemType Directory -Force -Path data\qdrant, data\chat, data\documents, data\models\cache, data\models\local

if (Test-Path qdrant_data\collection) { Copy-Item qdrant_data\collection data\qdrant\ -Recurse -Force }
if (Test-Path qdrant_data\meta.json) { Copy-Item qdrant_data\meta.json data\qdrant\meta.json -Force }
if (Test-Path qdrant_data\chat_history.json) { Copy-Item qdrant_data\chat_history.json data\chat\history.json -Force }
if (Test-Path documents) { Copy-Item documents\* data\documents\ -Recurse -Force }
if (Test-Path model_cache) { Copy-Item model_cache\* data\models\cache\ -Recurse -Force }
if (Test-Path model_local) { Copy-Item model_local\* data\models\local\ -Recurse -Force }
```

Do not copy `qdrant_data/.lock`; embedded Qdrant creates its own lock.

### Destructive reset

> **Warning:** This is not a routine startup or shutdown procedure. It permanently removes indexed documents, chat history, and model caches used by the Compose deployment. Back up `data/` first if anything matters. Model files cached elsewhere by a host-run Python process are not removed.

From the repository root on Windows, resolve and inspect the exact target before confirming deletion:

```powershell
docker compose down
$studioDataPath = (Resolve-Path -LiteralPath .\data).Path
Write-Host "Permanently deleting $studioDataPath"
Remove-Item -LiteralPath $studioDataPath -Recurse -Force -Confirm
```

On macOS or Linux, verify that `pwd` is the Studio repository before running the final command:

```bash
docker compose down
pwd
rm -rf -- ./data
```

Studio recreates the empty directory structure and downloads models again on the next startup.

## Quality checks and CI

The backend tests use temporary directories and fakes; they do not need Groq, Firecrawl, or the real Qdrant data directory.

Studio uses Ruff for both Python linting and formatting checks. Ruff is pinned with the other development dependencies in `backend/requirements-dev.txt`; there is no second Python style tool. The frontend keeps its existing Oxlint configuration.

GitHub Actions runs the following command set on every push and pull request using Python 3.11.16 and Node.js 20.20.2. Dependency caches are intentionally disabled so the job verifies a clean lock-file install. No API credentials are supplied: tests use fakes, and CI copies the placeholder-only `.env.example` solely because Compose requires an environment file.

```powershell
venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
venv\Scripts\python.exe -m pip check
venv\Scripts\python.exe -m ruff check backend scripts evals tests
venv\Scripts\python.exe -m ruff format --check backend scripts evals tests
venv\Scripts\python.exe -m pytest -q
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
docker compose config --quiet
docker compose build
```

On macOS or Linux, replace `venv\Scripts\python.exe` with `venv/bin/python`. Run `python -m ruff format backend scripts evals tests` to apply the configured formatter before rerunning the check. The optional Firecrawl stack is not part of CI because it is a separate upstream infrastructure bundle.

Full container smoke check:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/api/health
(Invoke-WebRequest http://localhost/).StatusCode
```

Expected results are a healthy backend, `{"status":"ok"}` from the readiness endpoint, and HTTP `200` from the frontend.

## Operations and troubleshooting

### Backend stays in `starting`

The initial embedding-model download can be slow. Confirm internet access, free disk space, and writable `data/models/` directories, then inspect:

```powershell
docker compose ps
docker compose logs backend --tail 100
```

### Frontend does not start

The frontend depends on a healthy backend. Test the backend directly at `http://localhost:8000/api/health` and inspect its logs before debugging Nginx.

### Groq requests fail

Confirm that either `GROQ_API_KEY` is set in `.env` or the browser has a current key. After changing `.env`, recreate the backend configuration:

```powershell
docker compose up -d --force-recreate backend
```

Browser-entered keys apply to question answering. CLI, evaluations, routing without a browser key, and document table summarization require the server-side environment key.

### Firecrawl requests fail

Confirm that `FIRECRAWL_API_URL` matches the backend location and inspect the optional stack:

```powershell
docker compose -f infra\firecrawl-docker-compose.yaml ps
docker compose -f infra\firecrawl-docker-compose.yaml logs api --tail 100
```

### Qdrant reports a lock or storage error

Stop other local backend processes or containers that use the same data directory. Embedded Qdrant storage is not designed to be shared by multiple Studio backend processes.

### Upload returns HTTP 413

The effective limit is the smaller of `STUDIO_MAX_UPLOAD_BYTES` and Nginx's `client_max_body_size`. Keep both settings aligned when raising the limit.

### Port is already in use

Studio needs host ports `80` and `8000`; local Vite uses `5173`; local Firecrawl uses `3002`. Stop the conflicting process or change the relevant Compose port mapping and any matching frontend/backend URL.

## Known limitations

- No authentication, authorization, TLS termination, rate limiting, or per-user isolation; this is deliberate for the loopback-only, single-user deployment model.
- The user's Groq API key is stored in browser `localStorage` and transmitted over loopback HTTP by default.
- URL ingestion can reach loopback, link-local, and private-network addresses. Do not expose it to untrusted users.
- Chat history is a single shared JSON file, suitable only for one local deployment/process.
- Embedded Qdrant is file-backed and intended for one backend process, not horizontal scaling.
- Uploaded source files are not retained; only parsed chunks and metadata are indexed.
- Firecrawl failures can silently change web search into local document search.
- Firecrawl's local images are not pinned to immutable versions.
- Host-run model-library caches are not redirected by `STUDIO_DATA_DIR`.
- The application has no automated frontend browser test yet.
