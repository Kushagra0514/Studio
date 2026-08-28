# Phase 10 release verification report

Date: 2026-08-28
Repository: `D:\Code\Studio`

## Outcome

Phase 10 is **partially complete**. The isolated end-to-end application flow passed, and every automated repository check passed. The Docker-specific build, container restart, and image-content checks could not run because Docker Desktop's Linux engine crashes before exposing its named pipe on this Windows host.

No real Studio data or credentials were used, moved, printed, or deleted. The application checks used a temporary release copy, a throwaway data root, a placeholder-only environment file, a small text fixture, and a local mock of the Groq-compatible endpoint.

## Isolation used

- Temporary release copy: `D:\Code\Studio\.phase10-e2e`
- Throwaway data/model root: `C:\Users\kusha\AppData\Local\Temp\studio-phase10-e2e-data`
- Fixture: `phase10-fixture.txt`
- Distinctive fixture fact: `ORBIT-742`
- Local fallback ports: backend `8000`, frontend `5173`, mock provider `9000`
- Planned isolated Compose ports: backend `18080`, frontend `18081`

The release copy contained only the backend and frontend build inputs, a temporary Compose override, and the test harness. It did not copy the repository's `.git`, real `.env`, `data`, `qdrant_data`, model caches, virtual environment, evaluation data, or user documents.

## Docker attempt

The temporary Compose file validated:

```powershell
docker compose -f D:\Code\Studio\.phase10-e2e\docker-compose.yml config --quiet
```

Result: **PASS**, exit code 0.

The required clean image build was attempted:

```powershell
docker compose -f D:\Code\Studio\.phase10-e2e\docker-compose.yml build --no-cache --progress plain
```

Result: **BLOCKED before build execution**. No build context was transferred and no Studio image was created because the Docker Desktop Linux engine was unavailable.

Current diagnostic:

```powershell
docker version
```

Result: client `29.7.2`; server connection failed at `npipe:////./pipe/dockerDesktopLinuxEngine` because the pipe did not exist. The host reports `Microsoft Windows NT 10.0.26200.0` and Docker Desktop `4.86.0`.

Docker Desktop logs showed AF_UNIX socket/reparse-point failures under its own local runtime directories, including `Docker\run\dockerInference` and `docker-secrets-engine\engine.sock`. This matches open Docker Desktop Windows reports such as [docker/desktop-feedback#527](https://github.com/docker/desktop-feedback/issues/527) and [docker/desktop-feedback#531](https://github.com/docker/desktop-feedback/issues/531). Disabling Model Runner in the settings did not prevent the crash. A host reboot is the next safe recovery step; if it persists, use a Docker Desktop version unaffected on this host before rerunning the commands below.

Two inaccessible Docker runtime directories were renamed, not deleted, while diagnosing the crash:

- `C:\Users\kusha\AppData\Local\Docker\run.phase10-stale-20260828`
- `C:\Users\kusha\AppData\Local\docker-secrets-engine.phase10-stale-20260828`

They are Docker Desktop runtime artifacts, not Studio data. Leave them in place until after a reboot; then Docker Desktop or the user can remove them if they are no longer locked.

## End-to-end application flow

Because the engine failure is external to Studio, the same temporary source tree was exercised locally with the throwaway paths and mock provider. Frontend dependencies were installed in the temporary copy with `npm ci`; backend/model state was confined to the throwaway data root.

Representative verification requests:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-WebRequest http://127.0.0.1:5173/
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/ingest -Form @{ file = Get-Item 'D:\Code\Studio\.phase10-e2e\e2e\phase10-fixture.txt' }
Invoke-RestMethod http://127.0.0.1:8000/api/documents
Invoke-RestMethod -Method Delete -Uri 'http://127.0.0.1:8000/api/document?filename=phase10-fixture.txt'
Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:8000/api/documents
```

Question and history requests were sent as JSON to `/api/ask` and `/api/history`, using only the placeholder key and the mock endpoint. Results:

| Check | Result |
| --- | --- |
| Health endpoint | PASS: `{status: ok}` without an external provider call |
| Frontend load | PASS: HTTP 200 |
| Upload | PASS: fixture ingested as 2 chunks |
| Document listing | PASS: one `phase10-fixture.txt` document with 2 chunks |
| Question through backend | PASS: answer contained `ORBIT-742 [1]` |
| Returned sources | PASS: 2 chunks; source name and fixture fact matched |
| Frontend `/api/` proxy | PASS: same answer and sources through Vite proxy |
| Citation rendering | PASS: citation `1` opened Retrieved Passages and highlighted `The launch code is ORBIT-742.` |
| Browser diagnostics | PASS: no console errors in either tested local-host form |
| History save/read | PASS: one entry round-tripped with question and source |
| Process restart persistence | PASS: document, 2 chunks, and history entry survived backend restart |
| Single-document delete | PASS: document count changed from 1 to 0 |
| Delete-all | PASS: document count changed from 1 to 0 |
| Reuse after delete-all | PASS: re-ingestion succeeded and listing returned the fixture |

The browser check used the project UI, not a synthetic DOM test. It confirmed that the restored answer displayed an inline citation and that selecting it opened the matching retrieved passage.

## Build-context and secret review

Static context review: **PASS**.

- Backend context is `./backend`; its `.dockerignore` is an allowlist for the Dockerfile, lock file, and `app/**/*.py` only.
- Frontend context is `./frontend`; its `.dockerignore` is an allowlist for manifests, build configuration, `public/**`, and `src/**` only.
- The temporary `.env`, mock provider, fixture, real repository data, `.git`, tests, caches, virtual environments, and `node_modules` are outside the allowlists.
- Dockerfiles copy explicit paths and do not use `COPY . .`.

Actual image filesystem inspection: **BLOCKED**, because no image could be built while the Docker engine was unavailable. This remains an acceptance item.

## Automated verification

Run from `D:\Code\Studio`:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check backend scripts evals tests
.\.venv\Scripts\python.exe -m ruff format --check backend scripts evals tests
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
docker compose config --quiet
```

Results:

- `pip check`: PASS, no broken requirements.
- Ruff lint: PASS.
- Ruff format check: PASS, 16 files already formatted.
- Pytest: PASS, 24 tests in 2.14 seconds.
- `npm ci`: PASS, 124 packages installed from the lock file.
- Frontend tests: PASS, 2 of 2.
- Frontend lint: PASS with 3 non-fatal unused-parameter warnings.
- Frontend production build: PASS, Vite built 272 modules.
- Compose validation: PASS.

## Remaining release gate

After Docker Desktop is healthy, rerun from a clean temporary checkout or equivalent isolated release copy:

```powershell
docker version
docker compose config --quiet
docker compose build --no-cache --progress plain
docker compose up -d
docker compose ps
Invoke-RestMethod http://localhost:8000/api/health
Invoke-WebRequest http://localhost/
docker compose restart
Invoke-RestMethod http://localhost:8000/api/health
docker compose logs --tail 200
docker compose down
```

Then repeat the upload/question/history/delete flow with a throwaway `STUDIO_DATA_DIR`, and inspect the built image filesystems for `.env`, credentials, documents, runtime data, `.git`, tests, caches, and unintended source trees. Phase 10 is complete only after those Docker-specific checks pass.

## Cleanup

The three temporary local services and the two browser tabs were stopped. After resolving and comparing both absolute paths, the following test-only directories were removed successfully:

- `D:\Code\Studio\.phase10-e2e`
- `C:\Users\kusha\AppData\Local\Temp\studio-phase10-e2e-data`

The repository's real `data`, `qdrant_data`, `.env`, model caches, and documents were not modified or removed.
