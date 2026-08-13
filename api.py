import os
import shutil
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Global singletons (loaded once at startup)
storage = None
pipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize heavy models once at server startup, not per-request."""
    global storage, pipeline
    from storage import VectorStorage
    from retrieval import RetrievalPipeline
    
    storage = VectorStorage()
    pipeline = RetrievalPipeline(storage)
    print("\n✅ Studio API is ready!\n")
    yield

app = FastAPI(title="Studio API", lifespan=lifespan)

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
class Message(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    chat_history: list[Message] = []

class SourceItem(BaseModel):
    text: str
    source: str
    pages: list = []

class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]

class DocumentInfo(BaseModel):
    name: str
    chunks: int

# ========================================
# API Endpoints
# ========================================
@app.post("/api/ask", response_model=AskResponse)
def ask_question(req: AskRequest, request: Request):
    """Ask a question against the ingested documents."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
    # Extract the Groq API key from the request header
    groq_api_key = request.headers.get("x-groq-api-key")
    
    # Generate the answer and get sources (routing + search + lost in middle)
    chat_history_dicts = [{"role": msg.role, "content": msg.content} for msg in req.chat_history]
    result = pipeline.answer_question(req.question, chat_history_dicts, groq_api_key=groq_api_key)
    
    # Build the sources list for the frontend
    sources = []
    for res in result["sources"]:
        payload = res.payload or {}
        sources.append(SourceItem(
            text=payload.get("text", ""),
            source=payload.get("source", "Unknown"),
            pages=payload.get("pages", [])
        ))
    
    return AskResponse(answer=result["answer"], sources=sources)


@app.post("/api/ingest")
def ingest_file(file: UploadFile = File(...)):
    """Upload and ingest a document (PDF, DOCX, TXT)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    
    # Save the uploaded file to a temp location
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    try:
        from ingestion import ingest_document
        chunks = ingest_document(tmp_path)
        
        # Override the source name with the original filename
        for chunk in chunks:
            chunk.metadata["source"] = file.filename
        
        storage.add_chunks(chunks)
        
        return {
            "message": f"Successfully ingested {file.filename}",
            "filename": file.filename,
            "chunks": len(chunks)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


class URLIngestRequest(BaseModel):
    url: str

@app.post("/api/ingest/url")
def ingest_url_endpoint(req: URLIngestRequest):
    """Scrape and ingest a URL using Firecrawl."""
    if not req.url:
        raise HTTPException(status_code=400, detail="No URL provided.")
        
    try:
        from ingestion import ingest_url
        chunks = ingest_url(req.url)
        
        # Override the source name with the URL
        for chunk in chunks:
            chunk.metadata["source"] = req.url
            
        storage.add_chunks(chunks)
        
        return {
            "message": f"Successfully ingested {req.url}",
            "filename": req.url,
            "chunks": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
def list_documents():
    """List all unique documents that have been ingested."""
    try:
        # Scroll through all points to collect unique source names
        all_sources = {}
        offset = None
        
        while True:
            results, next_offset = storage.client.scroll(
                collection_name=storage.collection_name,
                limit=100,
                offset=offset,
                with_payload=True
            )
            
            for point in results:
                source = point.payload.get("source", "Unknown")
                if source not in all_sources:
                    all_sources[source] = 0
                all_sources[source] += 1
            
            if next_offset is None:
                break
            offset = next_offset
        
        documents = [
            DocumentInfo(name=name, chunks=count)
            for name, count in all_sources.items()
        ]
        
        return {"documents": documents}
    except Exception:
        return {"documents": []}

@app.delete("/api/documents")
def delete_all_documents():
    """Delete all documents in the database."""
    try:
        storage.delete_all_documents()
        return {"message": "Successfully deleted all documents"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/documents/{filename:path}")
def delete_document(filename: str):
    """Delete all chunks for a given document."""
    try:
        storage.delete_document(filename)
        return {"message": f"Successfully deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

HISTORY_FILE = "qdrant_data/chat_history.json"

@app.get("/api/history")
def get_history():
    """Retrieve the saved chat history from disk."""
    import os
    if os.path.exists(HISTORY_FILE):
        try:
            import json
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


@app.post("/api/history")
async def save_history(request: Request):
    """Save the chat history to disk."""
    import json
    history = await request.json()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
