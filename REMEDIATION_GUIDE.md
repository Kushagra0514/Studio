# Studio Repository Remediation Guide

This guide turns the current Studio prototype into a clean, reproducible, and verifiably working application. It is intentionally staged: fix correctness and protect data first, then reorganize files, then add automation.

Each phase contains:

- the problem being solved;
- a copyable prompt for a coding agent;
- concrete implementation steps;
- verification commands; and
- acceptance criteria.

Run the phases in order. Commit after every phase that passes its checks. Do not combine all phases into one large change.

## Safety rules for every phase

1. Never delete or overwrite `.env`, `qdrant_data/`, `model_cache/`, `model_local/`, `documents/`, `dataset.json`, or `eval_history.csv` without first making an explicit backup.
2. Treat all existing uncommitted files as user-owned.
3. Never commit API keys, uploaded documents, chat history, vector data, model files, virtual environments, or `node_modules`.
4. Before editing, run `git status --short` and record the existing state.
5. Make the smallest change that solves the phase. Do not introduce a framework, service, or abstraction unless the phase explicitly requires it.
6. After each phase, run its verification commands. Stop if a check fails and fix that phase before continuing.

## Target structure

The final structure should be approximately:

```text
Studio/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── backend/
│   ├── .dockerignore
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── ingestion.py
│   │   ├── retrieval.py
│   │   ├── schema.py
│   │   ├── storage.py
│   │   └── studio_paths.py
│   ├── Dockerfile
│   ├── requirements-dev.txt
│   ├── requirements.txt
│   └── requirements.lock
├── frontend/
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── package-lock.json
├── scripts/
│   ├── rag_cli.py
│   └── start.bat
├── evals/
│   ├── evaluate.py
│   └── generate_dataset.py
├── infra/
│   └── firecrawl-docker-compose.yaml
├── prototypes/
│   └── studio-ui.html
├── tests/
└── data/                     # ignored; created at runtime
    ├── chat/
    ├── documents/
    ├── models/
    └── qdrant/
```

The exact names may differ if the existing code makes another minimal layout safer. The important boundary is that source code is tracked while secrets, generated state, downloads, and user data are not.

---

## Phase 0: Establish a reproducible baseline

### Problem

There is no recorded proof of what currently works. Restructuring without a baseline can turn an existing failure into an ambiguous new failure.

### Copyable implementation prompt

> Inspect the Studio repository without changing source code. Record the current Git state, Python and Node versions, Docker availability, existing ignored runtime data, and the results of the frontend lint/build and Python import/compile checks. Do not print secret values from `.env`; report only variable names and whether each is present. Do not delete, move, or regenerate persistent data. Create a short baseline report listing every command, result, and pre-existing failure. Distinguish environment failures from application failures.

### Steps

1. Record `git status --short` and `git diff --stat`.
2. Record tool versions: Python, pip, Node, npm, Docker, and Docker Compose.
3. List environment-variable names without exposing values.
4. Run a Python syntax check against the tracked Python files.
5. Run the frontend lint and production build.
6. Run `docker compose config --quiet` to validate Compose syntax without printing resolved environment values.
7. If Docker is available and starting the app will not overwrite existing data, start the current stack and record whether the frontend and `/docs` load.
8. Save the results in a temporary working note or the phase commit message. Do not commit machine-specific diagnostics unless desired.

### Suggested commands

```powershell
git status --short
git diff --stat
python --version
python -m pip --version
node --version
npm --version
docker --version
docker compose version
python -m compileall -q backend scripts evals tests
npm --prefix frontend run lint
npm --prefix frontend run build
docker compose config --quiet
```

### Acceptance criteria

- The original working-tree state is known.
- No secret value appears in logs or committed files.
- Every current failure is recorded before code is moved.
- No source or persistent data has been changed.

---

## Phase 1: Protect secrets, user data, caches, and build contexts

### Problems

- `model_cache/` is untracked but is not ignored.
- `model_local/` is not clearly managed.
- Docker can receive model caches, local documents, evaluation artifacts, and other files through `COPY . .`.
- There is no safe, committed environment-variable template.

### Copyable implementation prompt

> Harden repository and Docker ignore rules for Studio. Preserve all existing local data. Update `.gitignore` so secrets, virtual environments, Node dependencies, model caches, uploaded documents, Qdrant state, chat history, generated evaluation data, logs, build output, and Python caches cannot be committed. Update `.dockerignore` so neither backend nor frontend images receive secrets, Git metadata, local data, caches, tests not required at runtime, virtual environments, `node_modules`, frontend build output, or local evaluation artifacts. Add `.env.example` containing variable names, safe defaults where appropriate, and placeholder values only. Do not change `.env`. Verify the rules with `git check-ignore` and inspect the Docker build contexts. Do not delete ignored files.

### Steps

1. Extend `.gitignore` for:
   - `.env` and local environment variants, while allowing `.env.example`;
   - `venv/`, `.venv/`, `__pycache__/`, `*.pyc`, and test caches;
   - `frontend/node_modules/` and `frontend/dist/`;
   - `model_cache/`, `model_local/`, and the eventual `data/` directory;
   - `qdrant_data/`, `documents/`, chat history, logs, datasets, and evaluation output.
2. Extend `.dockerignore` with all local/private/generated files.
3. Ensure the backend build context does not include `frontend/` once the Docker build is narrowed in Phase 5. Until then, ignoring `frontend/` is acceptable because it has its own build context.
4. Add `.env.example` with at least:

```env
GROQ_API_KEY=
FIRECRAWL_API_KEY=
FIRECRAWL_API_URL=http://host.docker.internal:3002
STUDIO_DATA_DIR=/app/data
```

5. Check that `.env.example` itself is not ignored.

### Verification

```powershell
git check-ignore -v .env model_cache model_local qdrant_data documents venv frontend/node_modules frontend/dist
git check-ignore .env.example
git status --short
docker compose config --quiet
```

`git check-ignore .env.example` should return no match. All private/generated paths should return an ignore rule.

### Acceptance criteria

- `.env` remains unchanged and untracked.
- `.env.example` contains no real credentials.
- Model data, vector data, chat history, documents, dependencies, and build output are ignored.
- Docker cannot copy those artifacts into an image.
- No user data is deleted or moved in this phase.

---

## Phase 2: Fix the duplicate storage method and lock its behavior with tests

### Problem

`backend/app/storage.py` previously defined `delete_all_documents` twice. Python silently replaced the first method with the second, so the actual behavior was determined by file order rather than a deliberate choice.

### Copyable implementation prompt

> Fix the duplicate `VectorStorage.delete_all_documents` definition in Studio. First inspect every caller and the Qdrant client behavior. Keep exactly one method with an explicit contract: deleting all documents must leave the collection present, empty, and immediately usable for new inserts. Prefer the smallest reliable implementation supported by the installed Qdrant client. Add one focused test that would fail if the method disappeared, left points behind, or left the collection unusable. Do not change unrelated retrieval or embedding behavior and do not touch the user's real `qdrant_data` directory; use a temporary test directory and mock/stub embedding initialization if necessary.

### Steps

1. Find all definitions and callers of `delete_all_documents`.
2. Decide on one behavior. The existing API expects the collection to remain usable after deletion.
3. Remove the duplicate definition.
4. Ensure deletion waits for completion where supported.
5. Add a test using temporary storage, never `./qdrant_data`.
6. Test the API-facing behavior: delete, list/scroll, then insert again.

### Verification

```powershell
rg -n "delete_all_documents" . -g "!venv/**" -g "!frontend/node_modules/**"
python -m compileall -q backend/app/storage.py backend/app/api.py
python -m pytest -q
```

### Acceptance criteria

- Exactly one `delete_all_documents` method exists.
- Deleting an empty collection succeeds.
- Deleting a populated collection leaves zero document points.
- The collection accepts new points afterward.
- Tests never read or modify the real vector database.

---

## Phase 3: Separate persistent data and make paths environment-independent

### Problems

- Qdrant data and chat history share `qdrant_data/` even though they have different lifecycles.
- Relative paths depend on the process working directory.
- Local runs and Docker runs can resolve storage paths differently.

### Copyable implementation prompt

> Introduce one configurable Studio data root without overengineering configuration. Read `STUDIO_DATA_DIR` from the environment, with a safe local default resolved from the repository/application location rather than the caller's current working directory. Store Qdrant data, chat history, uploaded documents, and model/cache mounts in separate subdirectories. Create required directories at startup. Update Docker Compose volume mounts accordingly. Preserve existing local data: do not delete or automatically migrate it. Document a manual, reversible migration procedure and support the old data only through that documented migration. Add focused tests proving paths resolve correctly with and without `STUDIO_DATA_DIR`.

### Recommended mapping

| Concern | Local/Docker subdirectory |
|---|---|
| Qdrant database | `data/qdrant/` |
| Chat history | `data/chat/history.json` |
| Uploaded documents | `data/documents/` |
| Model caches | `data/models/` |

### Steps

1. Introduce a small path/config module or a few constants in the existing application package. Do not add a configuration framework.
2. Resolve and create the directories once during startup.
3. Pass the Qdrant directory to `QdrantClient`.
4. Move the history-file reference out of Qdrant storage.
5. Write chat history atomically: write a temporary sibling file and replace the destination after a successful write.
6. Point Docker Compose at `./data/...` host directories and `/app/data/...` container directories.
7. Document how to copy existing data from `qdrant_data/` into the new layout while the application is stopped.
8. Do not run that migration automatically and do not remove the old directory.

### Verification

```powershell
$env:STUDIO_DATA_DIR = Join-Path $env:TEMP "studio-data-check"
python -m pytest -q
Remove-Item Env:STUDIO_DATA_DIR
docker compose config --quiet
```

Use a unique temporary directory in tests. Do not point tests at the repository's real `data/` or `qdrant_data/`.

### Acceptance criteria

- Local and Docker runs use predictable paths.
- Qdrant and chat history no longer share a directory.
- Missing directories are created safely.
- A failed history write cannot truncate the last valid history file.
- Existing user data remains untouched, with migration instructions available.

---

## Phase 4: Make API boundaries reliable

### Problems

- Uploads and URL ingestion need explicit validation and predictable errors.
- Broad exception handling can expose internal exception text or hide failures.
- History payloads are not modeled or bounded.
- Empty-collection handling and startup readiness are not explicit.

### Copyable implementation prompt

> Harden Studio's FastAPI boundary while preserving current frontend behavior. Validate non-empty questions, supported upload extensions, configured upload-size limits, HTTP/HTTPS URLs, chat roles, and history payload structure. Reject invalid input with useful 4xx responses. Avoid returning raw internal exception details to clients; log the detailed exception server-side and return a stable message. Add a lightweight `/api/health` endpoint that confirms the process is ready without calling Groq, Firecrawl, or downloading models. Keep CORS limited to the documented development origins. Add focused tests for valid and invalid inputs, empty storage, and health. Do not add authentication or a database unless deployment requirements explicitly call for them.

### Steps

1. Use Pydantic models for history entries and saved history.
2. Replace mutable-looking collection defaults with `default_factory` for clarity and safety.
3. Define supported upload extensions based on what `ingestion.py` actually handles.
4. Enforce a request-size limit at Nginx and validate the received file at the API boundary.
5. Accept only `http` and `https` for URL ingestion.
6. For network-facing deployments, block loopback, link-local, and private-address targets to reduce SSRF risk. If Studio is strictly local-only, document that assumption instead of adding a complex policy prematurely.
7. Log traceback/context on the server without logging keys or uploaded contents.
8. Return stable user-facing errors.
9. Add `/api/health` and tests that do not require external APIs.

### Verification

```powershell
python -m pytest -q
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/api/health
docker compose logs backend --tail 100
```

### Acceptance criteria

- Unsupported files and malformed URLs receive 4xx responses.
- Internal exceptions do not leak filesystem paths, credentials, or stack traces to clients.
- The health endpoint works without external API calls.
- Empty storage produces a valid empty result rather than a server error.
- Existing frontend API calls still match the backend contract.

---

## Phase 5: Make Docker builds lean, deterministic, and health-checked

### Problems

- The backend uses a broad root build context and `COPY . .`.
- The frontend uses `npm install` even though a lock file exists.
- Python dependencies are not locked.
- Compose configuration includes avoidable ambiguity and no health verification.

### Copyable implementation prompt

> Refactor Studio's Docker setup for small, reproducible images while preserving the two-service architecture. Give the backend and frontend isolated build contexts. Copy dependency manifests before source files to retain build caching. Use `npm ci` with `package-lock.json`. Create a verified Python lock file from a clean compatible environment and install it in the image. Use a Node version compatible with the installed Vite release and keep Python 3.11 unless tests prove a change is required. Remove obsolete Compose fields, use portable `env_file` syntax, mount only the required data directories, and add backend health checking. Do not add a separate Qdrant container because the application currently uses embedded Qdrant. Do not copy `.env`, caches, model data, documents, tests, Git metadata, or frontend source into the backend runtime image.

### Steps

1. Move/rename Dockerfiles to `backend/Dockerfile` and `frontend/Dockerfile` when Phase 6 performs the final source move, or first narrow copy instructions in place if restructuring has not happened yet.
2. Use `backend/` as the backend context after the code move.
3. Use `frontend/` as the frontend context.
4. Change frontend dependency installation to `npm ci`.
5. Confirm the Node base image satisfies Vite's `engines` requirement.
6. Generate a Python lock file using the exact versions that pass tests; keep the human-edited direct dependency list separate if useful.
7. Consolidate backend `RUN` layers where it improves cache use and image size without obscuring failures.
8. Remove the obsolete top-level Compose `version` key if current Compose warns about it.
9. Use a simple `.env` entry for `env_file` unless the project explicitly requires newer optional-file syntax.
10. Add a backend health check against `/api/health`.
11. Build with plain progress once and review the context sizes.

### Verification

```powershell
docker compose config --quiet
docker compose build --no-cache --progress plain
docker compose up -d
docker compose ps
Invoke-WebRequest http://localhost/api/health
Invoke-WebRequest http://localhost/
docker image ls
```

Inspect build output to ensure local data and the frontend tree are not transferred to the backend build.

### Acceptance criteria

- Fresh builds use lock files and succeed twice consistently.
- Backend and frontend have isolated contexts.
- Neither image contains `.env`, user data, model caches, `node_modules`, `.git`, or the Python virtual environment.
- Both services start and the backend reports healthy.
- The frontend can proxy `/api/` requests to the backend.

---

## Phase 6: Reorganize source code without changing behavior

Completed on 2026-08-27. Production Python code now lives in the importable `backend.app` package with explicit relative imports. Backend image files and dependency manifests live in `backend/`; local commands live in `scripts/`; evaluation tools live in `evals/`; optional Firecrawl infrastructure lives in `infra/`; and the retained reference UI lives in `prototypes/`.

The CLI still provides `ingest` and `ask`. Evaluation tools continue reading the ignored root-level `dataset.json` and `eval_history.csv`, so no local evaluation data was moved. The local default data root remains the repository's ignored `data/` directory, while the backend image explicitly uses `/app/data`.

### Current verification

```powershell
python -m compileall -q backend scripts evals tests
python -m pytest -q
npm --prefix frontend run lint
npm --prefix frontend run build
docker compose config --quiet
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/api/health
```

### Verified result

- Production backend code is one importable package.
- CLI, evaluation, infrastructure, and prototype files have clear homes.
- Local commands and Docker use the new paths.
- Persistent and ignored data was not moved or deleted.

---

## Phase 7: Replace placeholder documentation with accurate operating instructions

Completed on 2026-08-27. The root README is now the complete operating guide, while `frontend/README.md` is a concise Studio-specific frontend reference rather than generated Vite prose.

The documentation now distinguishes embedded Qdrant from a separate server, documents Docker and local development, explains server and browser API-key behavior, covers hosted and local Firecrawl, identifies every persistent-data path, and separates safe shutdown and backup procedures from an explicitly destructive reset. It also records the current local-only security and scaling limitations.

### Verified result

- Main and Firecrawl Compose files validate.
- The main Docker stack builds and starts with a healthy backend.
- The local packaged backend starts and serves `/api/health` and `/docs`.
- Vite starts on port 5173 and proxies `/api/health` successfully.
- The optional Firecrawl stack starts its API, Playwright, Redis, RabbitMQ, and PostgreSQL services.
- Backend compilation and all 21 tests pass.
- Frontend dependency installation, lint, and production build succeed.
- Obsolete-path search results are limited to current package paths, current Firecrawl paths, and the explicitly labeled legacy-data migration.

---

## Phase 8: Add a minimal but meaningful test suite

Completed on 2026-08-27. The backend suite now covers all nine required contracts with temporary Qdrant storage and fake external clients. The frontend uses Node's built-in test runner, the existing Vite transformer, and React's server renderer, so no test dependency or browser stack was added.

### Current verification

```powershell
venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

### Verified result

- All 24 backend tests pass offline in a few seconds.
- Single-document and delete-all storage behavior use only temporary Qdrant directories.
- Router and Firecrawl fallback tests use fake Groq, Firecrawl, and storage clients.
- Two frontend tests verify every API route, the Groq header/body contract, and server-rendering the real empty workspace.
- The production frontend build succeeds.
- No real API key, model download, network request, or persistent Studio data is used.
- No new Python or npm package was added.

---

## Phase 9: Add automated quality checks and reproducible dependency handling

Completed on 2026-08-27. Ruff is the single Python lint/format tool, with a minimal Python 3.11 configuration and an exact development dependency pin. GitHub Actions now installs both lock files from scratch, runs the offline backend and frontend suites, enforces Ruff and Oxlint, builds the frontend, validates Compose with the safe environment template, and builds both container images using the locally verified Python 3.11.16 and Node.js 20.20.2 versions.

### Verified result

- A fresh ignored virtual environment installs `backend/requirements-dev.txt`, and `pip check` reports no broken requirements.
- Ruff lint passes and all 16 checked Python files match the configured formatter.
- All 24 backend tests and both frontend tests pass without live API calls.
- `npm ci`, Oxlint, and the Vite production build succeed. Oxlint continues to report three pre-existing unused-parameter warnings without failing the command.
- `docker compose config --quiet` succeeds and Compose builds both the backend and frontend images.
- The workflow YAML parses successfully. A hosted GitHub Actions run requires pushing the workflow to GitHub.

### Problems

- Python formatting/linting is not standardized.
- Frontend lint exists but is not enforced automatically.
- There is no CI proof that a clean checkout can test and build.
- Broad, unpinned Python requirements can change underneath the project.

### Copyable implementation prompt

> Add lightweight quality automation for Studio. Choose one Python linter/formatter tool only, configure it minimally, and avoid overlapping tools. Preserve the existing frontend Oxlint setup. Add CI that installs locked dependencies, runs Python tests and lint, runs frontend lint and build with `npm ci`, validates Docker Compose, and builds both images. Cache dependencies only where it does not hide lock-file mistakes. Pin the CI Python and Node versions to the versions verified locally. Do not add deployment, release publishing, coverage gates, or multiple style tools unless explicitly requested.

### Steps

1. Select one Python tool, preferably one that handles both formatting checks and linting.
2. Add minimal configuration for the actual supported Python version.
3. Create/update a verified dependency lock file.
4. Add CI triggers for pushes and pull requests.
5. Run backend lint and tests.
6. Run `npm ci`, frontend lint, and frontend build.
7. Validate Compose and build the images.
8. Ensure CI never requires `.env` or live API credentials.

### Verification

Run locally the exact commands used by CI. A typical set is:

```powershell
python -m pytest -q
python -m ruff check backend scripts
python -m ruff format --check backend scripts
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run build
docker compose config --quiet
docker compose build
```

If a different single Python tool is chosen, replace the Ruff commands rather than adding them alongside another tool.

### Acceptance criteria

- One command set reproduces CI locally.
- A clean checkout installs from lock files.
- CI passes without secrets or network API calls beyond dependency/image downloads.
- Python tests/lint and frontend lint/build are enforced.
- Docker images build from the clean checkout.

---

## Phase 10: End-to-end recovery and release verification

> **Status (2026-08-28): Partially verified.** The isolated local application flow, persistence, citations, deletion/reuse, and all automated checks pass. Docker image/container verification is still blocked by a Docker Desktop AF_UNIX startup failure on the Windows host. See `PHASE10_RELEASE_REPORT.md`; do not mark this phase complete until the clean image build, container restart/persistence, and image-content inspection pass.

### Problem

Individual unit checks do not prove that upload, indexing, retrieval, citations, deletion, and persistence work together.

### Copyable implementation prompt

> Perform a final end-to-end verification of Studio from a clean checkout or clean temporary worktree. Do not use or erase the developer's real persistent data. Configure throwaway data directories and test credentials, build with Docker Compose, wait for health, and exercise the complete flow: frontend load, document upload, document listing, a mocked or authorized real question, citation rendering, single-document deletion, history save/read, container restart, persistence check, and delete-all behavior. Record exact commands and results. Inspect images and build contexts for leaked secrets or local data. Fix only regressions attributable to the remediation; report unrelated external-service failures separately.

### Steps

1. Use a clean temporary checkout/worktree and a throwaway data directory.
2. Create a temporary `.env` containing test values; never commit it.
3. Build without relying on locally installed dependencies.
4. Start services and wait for backend health.
5. Confirm the frontend loads through Nginx.
6. Upload one small supported fixture and confirm it appears in `/api/documents`.
7. Ask one question. Use a mocked provider for CI; use a real provider only when explicitly authorized and a key is available.
8. Confirm sources/citations correspond to the ingested fixture.
9. Save and retrieve history.
10. Restart services and confirm vector data/history persist.
11. Delete the single document and confirm it disappears.
12. Re-ingest, delete all documents, and confirm the collection remains usable.
13. Inspect containers/images for `.env`, credentials, local user documents, and unintended source trees.
14. Stop the temporary stack and remove only the explicitly created throwaway data after resolving its absolute path.

### Suggested verification commands

```powershell
docker compose build --no-cache
docker compose up -d
docker compose ps
Invoke-RestMethod http://localhost:8000/api/health
Invoke-WebRequest http://localhost/
Invoke-RestMethod http://localhost:8000/api/documents
docker compose restart
Invoke-RestMethod http://localhost:8000/api/health
docker compose logs --tail 200
docker compose down
```

Document upload and question requests may be executed through the frontend or with `Invoke-RestMethod` using a known fixture.

### Acceptance criteria

- A clean checkout builds and starts from the documented commands.
- Frontend, backend proxying, ingestion, retrieval, citations, history, deletion, and persistence work.
- Restarting containers does not lose mounted data.
- Delete-all leaves the application ready for re-ingestion.
- Images contain no secrets or user data.
- All automated checks pass.

---

## Optional Phase 11: Production hardening only if Studio will be network-accessible

> **Status (2026-08-28): Not applicable to the selected deployment model.** Studio will remain a trusted, single-user local application. Each installation uses that user's own Groq API key through the browser prompt, and published Compose ports are bound to `127.0.0.1`. Authentication, TLS, multi-user persistence, and other internet-facing controls are intentionally not being added. Reopen this phase before exposing Studio to a LAN, shared host, public domain, tunnel, or reverse proxy.

This phase is intentionally optional. A local single-user tool does not need enterprise infrastructure. If the service will be exposed beyond a trusted machine, the trust boundary changes substantially.

### Copyable implementation prompt

> Prepare Studio for a network-accessible deployment. First document the deployment model, users, data sensitivity, reverse proxy, and threat boundary. Then add authentication and authorization for ingestion, history, document listing/deletion, and question endpoints; rate and size limits; strict origin/host controls; SSRF protections for URL ingestion; secret injection through the deployment platform; TLS at the edge; structured redacted logs; backup/restore procedures; dependency and container scanning; and a supported multi-user persistence design. Do not implement this phase until the deployment assumptions are explicitly confirmed. Preserve local-development ergonomics and add security-focused tests for every new boundary.

### Acceptance criteria

- Deployment assumptions are written down before implementation.
- Every data-changing or data-reading endpoint is appropriately authorized.
- URL ingestion cannot reach disallowed internal addresses.
- Secrets are not accepted from or persisted by untrusted clients without an explicit security design.
- Persistence supports the intended number of processes/users.
- Backup restoration is tested, not merely documented.

---

## Master prompt for coordinating all phases

Use this only with an agent that can work iteratively and stop at checkpoints:

> Remediate the Studio repository using `REMEDIATION_GUIDE.md` as the authoritative sequence. Work on exactly one phase at a time. Before each phase, inspect the current Git state and relevant code, preserve all user-owned/uncommitted files, and state the intended files. Implement the smallest root-cause fix for that phase. Run every listed verification check and report the exact result. Do not continue to the next phase until the current acceptance criteria pass and I approve continuation. Never expose `.env` values; never delete or migrate persistent data automatically; never run tests against real Qdrant, chat history, documents, model caches, datasets, or evaluation history. Keep unrelated changes untouched. At each checkpoint, summarize changed files, behavior, tests, known limitations, and any manual data-migration action still required.

## Recommended commit sequence

```text
chore: protect local data and Docker build contexts
fix: make document deletion behavior unambiguous
refactor: separate Studio persistence paths
fix: validate API inputs and stabilize errors
build: make container builds reproducible
refactor: organize backend and support files
docs: document verified setup and operations
test: cover critical Studio workflows
ci: enforce tests lint and image builds
```

Do not create a commit merely to match this list. Commit only after the corresponding phase passes its acceptance criteria.

## Definition of done

The repository is remediated when all of the following are true:

- a clean checkout can be configured from `.env.example` and the README;
- `npm ci`, frontend lint, and frontend build succeed;
- backend lint and tests succeed offline;
- Docker Compose validates, builds, starts, and reports healthy;
- source, infrastructure, scripts, and runtime data have clear boundaries;
- local secrets, documents, histories, model files, database files, dependencies, and build output are ignored and absent from images;
- deletion has one tested contract;
- persistent paths behave identically across documented local and Docker runs;
- upload, retrieval, citations, history, deletion, restart, and persistence pass an end-to-end check; and
- documentation contains no stale generated template instructions or misleading architecture claims.
