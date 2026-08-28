import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
)

from .studio_paths import ensure_data_directories

load_dotenv()

logger = logging.getLogger(__name__)

SUPPORTED_UPLOAD_EXTENSIONS = frozenset({".pdf", ".docx", ".txt"})
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_COPY_CHUNK_BYTES = 1024 * 1024


def _configured_upload_limit() -> int:
    raw_value = os.getenv("STUDIO_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    try:
        value = int(raw_value)
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        logger.warning("Invalid STUDIO_MAX_UPLOAD_BYTES; using the 50 MiB default.")
        return DEFAULT_MAX_UPLOAD_BYTES


MAX_UPLOAD_BYTES = _configured_upload_limit()

# Global singletons (loaded once at startup)
storage = None
pipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize heavy models once at server startup, not per-request."""
    global storage, pipeline
    app.state.ready = False
    try:
        from .retrieval import RetrievalPipeline
        from .storage import VectorStorage

        data_paths = ensure_data_directories()
        app.state.data_paths = data_paths
        storage = VectorStorage(data_path=data_paths.qdrant)
        pipeline = RetrievalPipeline(storage)
        app.state.ready = True
        logger.info("Studio API is ready.")
        yield
    finally:
        app.state.ready = False


app = FastAPI(title="Studio API", lifespan=lifespan)
app.state.ready = False

# Allow the Vite dev server to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# Request / Response Models
# ========================================
NonEmptyQuestion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000),
]
MessageContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000),
]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: MessageContent


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: NonEmptyQuestion
    chat_history: list[Message] = Field(default_factory=list, max_length=20)


class SourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(max_length=250_000)]
    source: Annotated[str, Field(max_length=2_048)]
    pages: list[int | str] = Field(default_factory=list, max_length=100)


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class DocumentInfo(BaseModel):
    name: str
    chunks: int


class HistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: int | Annotated[str, Field(max_length=128)]
    question: NonEmptyQuestion
    answer: Annotated[str, Field(max_length=100_000)] | None = None
    is_searching: bool = Field(default=False, alias="isSearching")
    sources: list[SourceItem] = Field(default_factory=list, max_length=20)


HistoryPayload = Annotated[list[HistoryEntry], Field(max_length=200)]
history_payload_adapter = TypeAdapter(HistoryPayload)


class URLIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl


def _safe_upload_name(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="No file provided.")
    return safe_name


def _copy_upload_to_temporary_file(file: UploadFile, suffix: str) -> Path:
    temporary_path = None
    try:
        total_bytes = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_path = Path(temporary_file.name)
            while chunk := file.file.read(UPLOAD_COPY_CHUNK_BYTES):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {MAX_UPLOAD_BYTES} byte upload limit.",
                    )
                temporary_file.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        return temporary_path
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


# ========================================
# API Endpoints
# ========================================
@app.get("/api/health")
def health(request: Request):
    """Report readiness without invoking any external service or model."""
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(status_code=503, detail="Service is starting.")
    return {"status": "ok"}


@app.post("/api/ask", response_model=AskResponse)
def ask_question(req: AskRequest, request: Request):
    """Ask a question against the ingested documents."""
    try:
        groq_api_key = request.headers.get("x-groq-api-key")
        chat_history_dicts = [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ]
        result = pipeline.answer_question(
            req.question,
            chat_history_dicts,
            groq_api_key=groq_api_key,
        )

        sources = []
        for res in result["sources"]:
            payload = res.payload or {}
            sources.append(
                SourceItem(
                    text=payload.get("text", ""),
                    source=payload.get("source", "Unknown"),
                    pages=payload.get("pages", []),
                )
            )

        return AskResponse(answer=result["answer"], sources=sources)
    except Exception:
        logger.exception("Question answering failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to generate an answer.",
        ) from None


@app.post("/api/ingest")
def ingest_file(file: UploadFile = File(...)):
    """Upload and ingest a document (PDF, DOCX, TXT)."""
    filename = _safe_upload_name(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_UPLOAD_EXTENSIONS))
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Supported extensions: {supported}.",
        )

    temporary_path = None
    try:
        temporary_path = _copy_upload_to_temporary_file(file, suffix)
        from .ingestion import ingest_document

        chunks = ingest_document(str(temporary_path))
        for chunk in chunks:
            chunk.metadata["source"] = filename

        storage.add_chunks(chunks)

        return {
            "message": f"Successfully ingested {filename}",
            "filename": filename,
            "chunks": len(chunks),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Document ingestion failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to ingest the document.",
        ) from None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.post("/api/ingest/url")
def ingest_url_endpoint(req: URLIngestRequest):
    """Scrape and ingest a URL using Firecrawl."""
    url = str(req.url)
    try:
        from .ingestion import ingest_url

        chunks = ingest_url(url)
        for chunk in chunks:
            chunk.metadata["source"] = url

        storage.add_chunks(chunks)

        return {
            "message": f"Successfully ingested {url}",
            "filename": url,
            "chunks": len(chunks),
        }
    except Exception:
        logger.exception("URL ingestion failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to ingest the URL.",
        ) from None


@app.get("/api/documents")
def list_documents():
    """List all unique documents that have been ingested."""
    try:
        all_sources = {}
        offset = None

        while True:
            results, next_offset = storage.client.scroll(
                collection_name=storage.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
            )

            for point in results:
                source = (point.payload or {}).get("source", "Unknown")
                if source not in all_sources:
                    all_sources[source] = 0
                all_sources[source] += 1

            if next_offset is None:
                break
            offset = next_offset

        documents = [
            DocumentInfo(name=name, chunks=count) for name, count in all_sources.items()
        ]

        return {"documents": documents}
    except Exception:
        logger.exception("Document listing failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to list documents.",
        ) from None


@app.delete("/api/documents")
def delete_all_documents():
    """Delete all documents in the database."""
    try:
        storage.delete_all_documents()
        return {"message": "Successfully deleted all documents"}
    except Exception:
        logger.exception("Deleting all documents failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete documents.",
        ) from None


@app.delete("/api/document")
def delete_document(filename: str):
    """Delete all chunks for a given document."""
    try:
        storage.delete_document(filename)
        return {"message": f"Successfully deleted {filename}"}
    except Exception:
        logger.exception("Deleting a document failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete the document.",
        ) from None


def _write_json_atomically(destination: Path, value: object) -> None:
    """Replace a JSON file only after its complete temporary file is durable."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(value, temporary_file, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


@app.get("/api/history")
def get_history(request: Request):
    """Retrieve the saved chat history from disk."""
    history_file = request.app.state.data_paths.history_file
    if history_file.exists():
        try:
            with history_file.open("r", encoding="utf-8") as f:
                history = history_payload_adapter.validate_python(json.load(f))
                return [entry.model_dump(by_alias=True) for entry in history]
        except (OSError, ValueError):
            logger.warning("Ignoring an unreadable or invalid chat history file.")
            return []
    return []


@app.post("/api/history")
def save_history(history: HistoryPayload, request: Request):
    """Save the chat history to disk."""
    serialized_history = [entry.model_dump(by_alias=True) for entry in history]
    try:
        _write_json_atomically(
            request.app.state.data_paths.history_file,
            serialized_history,
        )
        return {"status": "ok"}
    except OSError:
        logger.exception("Saving chat history failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to save chat history.",
        ) from None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.api:app", host="127.0.0.1", port=8000, reload=True)
