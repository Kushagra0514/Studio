# Studio - Agentic RAG Application

Studio is a powerful, locally-deployable Agentic Retrieval-Augmented Generation (RAG) application. It allows you to upload documents (PDF, DOCX, TXT) or provide URLs to scrape, and then chat with an AI assistant that grounds its answers in your specific data using advanced hybrid search techniques.

## ✨ Features

- **Agentic Routing:** Automatically detects whether your query requires searching your documents, searching the web, or just standard conversation.
- **Hybrid Search:** Combines dense embeddings (`BAAI/bge-small-en-v1.5`) and sparse embeddings (`Qdrant/bm25`) using Qdrant for highly accurate retrieval.
- **Document & Web Ingestion:** Upload files directly or scrape web pages using Firecrawl.
- **Persistent Chat History:** Remembers your conversations across sessions.
- **Beautiful UI:** Clean, responsive, and minimalist React frontend with inline citations.
- **Fully Dockerized:** Easy to deploy and run anywhere.

## 🚀 Getting Started

### Prerequisites

You will need the following installed on your machine:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine
- [Docker Compose](https://docs.docker.com/compose/install/)

### 1. Configure Environment Variables

The application requires API keys to function. Create a `.env` file in the root directory:

```bash
touch .env
```

Open the `.env` file and add your **Groq API Key** (required) and **Firecrawl API Key** (optional, for web scraping):

```env
# Required: Your Groq API Key for the LLM
GROQ_API_KEY=gsk_your_groq_api_key_here

# Optional: Firecrawl API for web scraping capabilities
FIRECRAWL_API_KEY=fc_your_firecrawl_api_key_here
FIRECRAWL_API_URL=https://api.firecrawl.dev
```

> **Note:** If you prefer not to use a `.env` file for the Groq API key, the frontend UI will prompt you to enter it when you first open the app, and it will be securely saved in your browser's local storage.

### 2. Build and Run the Containers

Run the following command to build the Docker images and start the application in the background:

```bash
docker-compose up --build -d
```

> **First Run:** The initial startup might take a few minutes as the backend downloads the necessary machine learning embedding models from HuggingFace (`~1.5GB` total). 

### 3. Access the Application

Once the containers are running and the backend has finished loading its models, open your browser and navigate to:

- **Frontend UI:** [http://localhost](http://localhost)
- **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

## 🏗️ Architecture

- **Frontend:** Built with React and Vite. Served efficiently using Nginx.
- **Backend:** Built with FastAPI (Python 3.11). Handles routing, retrieval, and LLM generation.
- **Vector Database:** Local Qdrant instance storing chunks and embeddings.
- **LLM Provider:** Groq (extremely fast inference using Llama 3 models).
- **Embeddings:** `fastembed` running locally for privacy and speed.

## 🧹 Maintenance

To view the backend logs (useful to check if models are still downloading):
```bash
docker-compose logs backend -f
```

To shut down the application:
```bash
docker-compose down
```

To wipe the database and chat history entirely, simply delete the local `qdrant_data` directory:
```bash
# Windows (PowerShell)
Remove-Item -Recurse -Force qdrant_data

# Mac/Linux
sudo rm -rf qdrant_data/
```
