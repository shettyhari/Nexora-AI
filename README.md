# NEXORA AI – Enterprise Autonomous AI Platform

NEXORA AI is a production-grade, full-stack ChatGPT-style neural application built with a **Next.js (React 18 / TypeScript / Tailwind CSS)** frontend, an asynchronous **FastAPI (Python 3.12)** backend, **SQLAlchemy 2.0** with **Alembic** migrations, **PostgreSQL / SQLite** with **pgvector**, and **Redis** caching.

---

## 🚀 Key Features

### 1. Unified Model Gateway & Provider Adapters
- **Multi-Provider Support**: Pluggable adapters for **Google Gemini** (1.5 Flash/Pro), **OpenAI** (GPT-4o, GPT-4o-mini), **Anthropic Claude** (3.5 Sonnet, 3.5 Haiku), **Hugging Face** (Llama 3.1 70B, DeepSeek-R1), **Self-Hosted Inference** (Ollama, vLLM, LM Studio), and **NEXORA Proprietary Flagship & Local Resilience Fallback**.
- **Common Gateway Protocol**: Unified `LLMRequest`, `LLMResponse`, and `LLMStreamChunk` abstraction across all providers.
- **Resilience & Graceful Failover**: Automatic cascaded failover to local fallback if an upstream cloud provider key is missing or rate-limited.
- **Provider Health Checks**: Live latency, status, and model discovery monitored concurrently via `/api/v1/gateway/health`.

### 2. Model Registry & Dynamic Selection
- **Centralized Registry**: Dynamic catalog specifying context window, maximum output tokens, supported modalities (text, vision), capabilities (streaming, reasoning, function calling, JSON schema), deployment, and pricing metadata.
- **Token Cost Tracking**: Real-time prompt and completion token cost accounting based on input/output per million pricing.
- **Dynamic Frontend Integration**: Populates the frontend Model Selector directly from the registry.

### 3. Intelligent Model Router
- **Autonomous Selection**: Automatically routes prompts to the optimal model based on detected user intent (coding, math/reasoning, fast Q&A, vision, large context), task complexity, token length, cost, and provider health.
- **Manual User Override**: Users can explicitly pick any specific model, honoring the choice with `is_override = true`.
- **Transparency Policy (No Silent Switching)**: Every response surfaces which model answered and why (`resolved_model` and `routing_reason`) directly in the UI.

### 4. 8-Stage Advanced Reasoning Framework
- **Orchestrated Workflow**:
  1. Classify Request & Profile Task
  2. Identify Capabilities (Vision, Code, Math)
  3. Determine Tool Needs (Web Search, Memory, RAG)
  4. Context Retrieval (Semantic Memory + Hybrid RAG + Web Search)
  5. Select Appropriate Model
  6. Assemble & Budget Context Window
  7. Stream Output with Reasoning Tokens
  8. Validate & Persist Metrics and Citations
- **Private Internal Reasoning**: Displays concise calculations, conclusions, and evidence with collapsible deep thought accordions.

### 5. Memory Engine (Semantic Vector Storage)
- **Multi-Tier Memory**: Short-term conversation memory, long-term user memory, project memory, and user preferences.
- **Semantic Vector Retrieval**: Vector embeddings with cosine similarity matching.
- **Duplicate Detection**: Computes semantic similarity prior to insertion; if similarity $\ge 0.88$, updates existing memory rather than duplicating.
- **User Control & Data Isolation**: Full user-controlled inspection, manual creation, and deletion with strict `user_id == current_user.id` isolation.

### 6. RAG Engine (Hybrid Search & RRF Reranking)
- **Document Ingestion**: Recursive character chunker with overlap across text, markdown, and code documents.
- **Hybrid Search**: Dense vector retrieval + sparse **BM25Okapi** lexical search.
- **Reciprocal Rank Fusion (RRF)**: Reranks combined dense and sparse candidates ($k=60$) for superior retrieval relevance.
- **Citation Generation**: Emits explicit citations `[Source 1: filename.md (Chunk 2)]` grounding AI responses.

### 7. Context Engine & Token Budgeting
- **Exact Token Counting**: Powered by `tiktoken` (o200k_base / cl100k_base) with heuristic fallback.
- **Window Budgeting**: Calculates model input budgets reserving output space ($Context - Output - 1000$).
- **Conversation Compression**: Condenses older messages into an executive summary block when context thresholds are reached while preserving recent dialogue intact.

### 8. Complete Chat Interface & Experience
- **NEXORA Brand Identity**: Futuristic neon-cyan and deep obsidian palette with original SVG logo and wordmark.
- **Full Conversation Management**: Create, rename, pin, archive, search (`⌘K`), and delete conversations.
- **Markdown & Math**: Full GitHub Flavored Markdown (GFM), syntax-highlighted code blocks with copy button, responsive tables, and inline/block LaTeX formulas via KaTeX.
- **Chat Composer**: Multiline auto-resizing textarea (`Enter` to send, `Shift + Enter` for new line), file uploads, model selector, reasoning toggle, web grounding toggle, and voice placeholder.
- **Light & Dark Mode**: Persistent theme toggle with zero-flicker initialization.

---

## 🛠 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide Icons, KaTeX, React Markdown |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 Async, Uvicorn, HTTPX |
| **Database** | PostgreSQL 16 (Production) / SQLite Async (Local Dev), Alembic Migrations |
| **Vector Engine** | pgvector (PostgreSQL) / Cosine Vector Generator (Local Dev) |
| **Hybrid Search** | BM25Okapi + Dense Vector Embeddings + Reciprocal Rank Fusion |
| **Cache & Session**| Redis 7 |
| **AI Providers** | Google Gemini, OpenAI, Anthropic Claude, Hugging Face, Self-Hosted (Ollama/vLLM), NEXORA Local |

---

## ⚡ Quickstart

### Prerequisites
- Node.js 18+ and npm
- Python 3.12+ (or `uv`)
- Docker & Docker Compose (optional)

### 1. Environment Setup
```bash
cp .env.example .env
```
Add any API keys you wish to use (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). If omitted, NEXORA seamlessly operates with the built-in diagnostic neural fallback.

### 2. Local Development

#### Start Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```
Backend API will be accessible at `http://localhost:8000` (Swagger docs at `/docs`).

#### Start Frontend:
```bash
cd frontend
npm install
npm run dev
```
Frontend will be accessible at `http://localhost:3000`.

---

## 🧪 Automated Testing

Run the complete 32-test backend test suite:
```bash
cd backend
pytest -v
```
**Test Suites Covered:**
- `test_auth.py`: Registration, duplicate detection, login, profile, unauthorized guards.
- `test_router.py`: Intelligent model routing across coding, math, fast chat, vision, and manual override.
- `test_gateway.py`: Model registry, health checks, streaming, fallback resilience, structured output.
- `test_memory.py`: Semantic memory store, similarity retrieval, duplicate detection, tenant isolation, deletion.
- `test_rag.py`: Document ingestion, recursive chunking, hybrid BM25 + vector search, RRF reranking, citation correctness.
- `test_context.py`: Token counting, model budgeting, conversation history compression and summarization.
- `test_messages.py`: Streaming SSE responses, editing, feedback, token accounting.
- `test_conversations.py`: CRUD, pin, archive, search.
- `test_isolation.py`: Strict cross-tenant access control.
- `test_llm_provider.py`: Factory instantiation and fallback cascade.
