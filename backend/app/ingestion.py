import os
import uuid

# Disable PyTorch's JIT compiler (TorchDynamo) to prevent "Compiler: cl is not found" errors on Windows
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TORCH_COMPILE_DISABLE"] = "1"

from docling.chunking import HierarchicalChunker
from docling.document_converter import DocumentConverter
from groq import Groq

from .schema import Chunk


def summarize_table(table_text: str) -> str:
    try:
        client = Groq()
        prompt = (
            "You are an expert data analyst. The following is a Markdown table extracted from a document. "
            "Convert this table into a highly detailed natural language summary that explicitly preserves every single fact, row, column, and relationship. "
            "State the facts clearly so a search engine can easily find them based on keyword searches.\n\n"
            f"Table Markdown:\n{table_text}"
        )
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Table summarization failed: {e}")
        return ""


def ingest_document(file_path: str) -> list[Chunk]:
    print(f"Parsing document: {file_path}")
    converter = DocumentConverter()
    doc_result = converter.convert(file_path)
    doc = doc_result.document

    chunker = HierarchicalChunker()
    doc_chunks = chunker.chunk(doc)

    result = []
    file_name = os.path.basename(file_path)

    for c in doc_chunks:
        chunk_id = str(uuid.uuid4())
        meta = {
            "source": file_name,
        }

        is_table = False
        if hasattr(c, "meta") and hasattr(c.meta, "doc_items"):
            pages = set()
            for item in c.meta.doc_items:
                if hasattr(item, "label") and "table" in str(item.label).lower():
                    is_table = True
                if hasattr(item, "prov") and item.prov:
                    for p in item.prov:
                        if hasattr(p, "page_no"):
                            pages.add(p.page_no)
            if pages:
                meta["pages"] = list(pages)

        chunk_text = c.text
        if is_table:
            print(f"Table detected in chunk {chunk_id}! Summarizing...")
            summary = summarize_table(c.text)
            if summary:
                chunk_text = f"{c.text}\n\n[Table Summary for Search]:\n{summary}"

        result.append(Chunk(id=chunk_id, text=chunk_text, metadata=meta))

    print(f"Successfully chunked {file_name} into {len(result)} chunks.")
    return result


def ingest_url(url: str) -> list[Chunk]:
    import os
    import tempfile

    try:
        from firecrawl import FirecrawlApp

        api_key = os.getenv("FIRECRAWL_API_KEY", "local_dummy_key")
        api_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:3002")

        print(f"Scraping URL with Firecrawl at {api_url}: {url}")
        app = FirecrawlApp(api_key=api_key, api_url=api_url)

        scrape_result = app.scrape_url(url, params={"formats": ["markdown"]})

        markdown_content = scrape_result.get("markdown", "")
        if not markdown_content:
            raise ValueError("Firecrawl did not return any markdown content.")

        # Save the scraped markdown to a temp file and parse it using Docling
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".md", mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(markdown_content)
            tmp_path = tmp.name

        try:
            return ingest_document(tmp_path)
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        print(
            f"Firecrawl failed ({e}). Falling back to native Docling HTML conversion..."
        )
        return ingest_document(url)
