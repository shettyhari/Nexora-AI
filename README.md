# NEXORA AI – Enterprise Autonomous AI Platform

NEXORA AI is a production-grade, full-stack ChatGPT-style neural application built with a **Next.js (React 18 / TypeScript / Tailwind CSS)** frontend, an asynchronous **FastAPI (Python 3.12)** backend, **SQLAlchemy 2.0** with **Alembic** migrations, **PostgreSQL / SQLite**, and **Redis** caching.

---

## 🚀 Key Features

### 1. Complete Chat Experience
- **Conversation Management**: Create new chats, rename, pin, archive, search (`⌘K`), and delete conversations with confirmation modals.
- **Message Editing**: Edit previous user messages and selectively fork or regenerate responses.
- **Streaming Response Architecture**: Real-time Server-Sent Events (SSE) streaming token-by-token with glowing cursor and cancellation support via `AbortController`.
- **Markdown & Math Rendering**: Full GitHub Flavored Markdown (GFM), syntax-highlighted code blocks with language tags and copy button, responsive tables, and inline/block LaTeX formulas powered by KaTeX.
- **Deep Reasoning Mode**: Collapsible multi-step reasoning accordion displaying the model's internal thought process.
- **Grounding with Web Search**: Integrated live web search toggle grounding responses with live search results.
- **Message Feedback**: One-click thumbs up / thumbs down feedback with persistence.

### 2. Chat Composer
- Multi-line auto-resizing composer (`Enter` to send, `Shift + Enter` for new line).
- File and image attachment uploads with preview chips and size validation.
- Dynamic model selection (NEXORA Flagship, Gemini 1.5 Flash/Pro, GPT-4o, Claude 3.5 Sonnet).
- Voice input placeholder with notification tooling.
- Dynamic Send / Stop generation controls.

### 3. User Authentication & Multi-Tenant Isolation
- Secure JWT token architecture (access tokens + refresh tokens).
- Argon2 / Bcrypt password hashing.
- Complete registration, login, logout, password reset, and profile management flows.
- Strict data isolation: queries and updates enforce `user_id == current_user.id` at the database query level.

### 4. Database & Schemas
- 11 production relational tables: `users`, `profiles`, `conversations`, `messages`, `attachments`, `projects`, `user_preferences`, `model_configurations`, `usage_records`, `feedbacks`, `audit_logs`.
- Version-controlled Alembic migrations with composite indexing on foreign keys and timestamps.
- Zero-dependency local development via async SQLite with instant PostgreSQL switching in production.

---

## 🛠 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide Icons, KaTeX, React Markdown |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 Async, Uvicorn, HTTPX |
| **Database** | PostgreSQL 16 (Production) / SQLite Async (Local Dev), Alembic Migrations |
| **Cache & Session** | Redis 7 |
| **AI Providers** | Google Gemini, OpenAI, Anthropic, Groq, OpenRouter, Local Fallback Provider |

---

## ⚡ Quickstart

### Prerequisites
- Node.js 18+ and npm
- Python 3.12+ (or `uv`)
- Docker & Docker Compose (optional for containerized deployment)

### 1. Environment Setup
Copy the environment template:
```bash
cp .env.example .env
```
Add your AI provider key (e.g. `GEMINI_API_KEY` or `OPENAI_API_KEY`). If omitted, NEXORA seamlessly operates with the built-in diagnostic neural fallback.

---

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

### 3. Docker Compose Deployment
To run the full stack (PostgreSQL, Redis, FastAPI backend, Next.js frontend) with a single command:
```bash
docker-compose up --build
```

---

## 🧪 Testing

Run the automated backend test suite:
```bash
cd backend
python -m pytest -v
```

The test suite validates:
- User registration and duplicate rejection
- User login, invalid credential handling, and JWT refresh
- Protected route authentication barriers
- Conversation creation, listing, renaming, pinning, archiving, and deletion
- Message persistence and SSE streaming protocol
- Message editing and feedback recording
- Strict tenant data isolation (User B is prevented from reading, modifying, or deleting User A's assets)
- LLM provider abstraction and unconfigured error handling

---

## 📁 Repository Structure
```
├── backend/
│   ├── alembic/              # Database migration scripts
│   ├── app/
│   │   ├── api/v1/           # REST endpoints (auth, users, conversations, messages, models, etc.)
│   │   ├── core/             # Configuration, security, database engine
│   │   ├── models/           # SQLAlchemy 2.0 models (11 relational tables)
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   └── services/llm/     # Multi-provider LLM abstraction (Gemini, OpenAI, Anthropic, Fallback)
│   ├── tests/                # Automated pytest suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages (/, /c/[id], /login, /register, /profile, etc.)
│   │   ├── components/       # UI, branding, chat, and modal components
│   │   ├── hooks/            # useAuth, useChat
│   │   ├── lib/              # API client, utilities, constants
│   │   └── types/            # TypeScript definitions
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
├── ARCHITECTURE.md
└── API_DOCS.md
```
