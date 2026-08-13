import sys
import os
from dotenv import load_dotenv
from ingestion import ingest_document
from storage import VectorStorage
from retrieval import RetrievalPipeline

def main():
    load_dotenv()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py ingest <pdf_path>")
        print("  python main.py ask \"<your question>\"")
        return
        
    command = sys.argv[1]
    storage = VectorStorage()
    
    if command == "ingest":
        if len(sys.argv) < 3:
            print("Please provide a path to a PDF file.")
            return
        file_path = sys.argv[2]
        chunks = ingest_document(file_path)
        storage.add_chunks(chunks)
        
    elif command == "ask":
        if len(sys.argv) < 3:
            print("Please provide a question.")
            return
        
        if not os.environ.get("GROQ_API_KEY"):
            print("ERROR: GROQ_API_KEY environment variable is not set. Please set it in a .env file.")
            return
            
        question = sys.argv[2]
        pipeline = RetrievalPipeline(storage)
        answer = pipeline.answer_question(question)
        
        print("\n=== ANSWER ===\n")
        print(answer)
        
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
