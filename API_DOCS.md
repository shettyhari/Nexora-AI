# NEXORA AI – REST & Streaming API Documentation (v2)

This document provides a comprehensive reference for the NEXORA AI backend API (v1), including the Unified Model Gateway, Model Registry, Intelligent Router, Memory Engine, and RAG Pipeline.

**Base URL**: `http://localhost:8000/api/v1`  
**Interactive Swagger UI**: `http://localhost:8000/docs`  
**OpenAPI Specification**: `http://localhost:8000/openapi.json`

---

## Table of Contents
1. [Authentication & Authorization](#1-authentication--authorization)
2. [Model Registry & Capabilities](#2-model-registry--capabilities)
3. [Intelligent Model Router](#3-intelligent-model-router)
4. [Gateway Health & Monitoring](#4-gateway-health--monitoring)
5. [Conversations Endpoints](#5-conversations-endpoints)
6. [Messages & Streaming Endpoints](#6-messages--streaming-endpoints)
7. [Memory Engine Endpoints](#7-memory-engine-endpoints)
8. [RAG Knowledge Engine Endpoints](#8-rag-knowledge-engine-endpoints)
9. [Attachments Endpoints](#9-attachments-endpoints)
10. [Feedback Endpoints](#10-feedback-endpoints)
11. [Error Handling & Status Codes](#11-error-handling--status-codes)

---

## 1. Authentication & Authorization

All protected routes require a Bearer token in the request header:
```http
Authorization: Bearer <access_token>
```
Tokens are acquired via `POST /api/v1/auth/login` or `POST /api/v1/auth/register`. All operations enforce strict tenant data isolation: queries explicitly restrict rows to `user_id == current_user.id`.

---

## 2. Model Registry & Capabilities

### 2.1 List All Registered Models
Retrieves all active models dynamically from the backend Model Registry.

- **Method**: `GET`
- **Path**: `/models`
- **Auth Required**: Yes

#### Response (`200 OK`)
```json
[
  {
    "id": "nexora-auto",
    "model_key": "nexora-auto",
    "display_name": "NEXORA Auto Router",
    "provider": "nexora",
    "version": "2.0",
    "description": "Intelligent autonomous model router. Matches tasks to optimal model based on intent, complexity, speed, and cost.",
    "context_window": 2000000,
    "max_tokens": 8192,
    "supports_vision": true,
    "supports_reasoning": true,
    "supports_tools": true,
    "is_default": true,
    "is_enabled": true,
    "pricing": {
      "input_per_million": 0.50,
      "output_per_million": 2.00
    },
    "deployment": "cloud",
    "status": "active",
    "recommended_intents": ["general", "auto", "coding", "reasoning", "fast"]
  },
  {
    "id": "claude-3-5-sonnet",
    "model_key": "claude-3-5-sonnet",
    "display_name": "Anthropic Claude 3.5 Sonnet",
    "provider": "anthropic",
    "version": "20241022",
    "context_window": 200000,
    "max_tokens": 8192,
    "supports_vision": true,
    "supports_reasoning": true,
    "supports_tools": true,
    "pricing": {
      "input_per_million": 3.00,
      "output_per_million": 15.00
    }
  }
]
```

### 2.2 Get Model Details
- **Method**: `GET`
- **Path**: `/models/{model_id}`
- **Auth Required**: Yes

---

## 3. Intelligent Model Router

### 3.1 Evaluate Routing Decision
Analyzes a user prompt, detects task intent and complexity, and returns the autonomous routing decision.

- **Method**: `POST`
- **Path**: `/router/evaluate`
- **Auth Required**: Yes

#### Request Body
```json
{
  "prompt": "Implement an async distributed lock in Rust using Tokio",
  "requested_model_id": "nexora-auto"
}
```

#### Response (`200 OK`)
```json
{
  "selected_model_id": "claude-3-5-sonnet",
  "provider": "anthropic",
  "reason": "Autonomous routing: High-complexity software architecture task routed to Claude 3.5 Sonnet",
  "confidence": 0.96,
  "is_override": false,
  "task_profile": {
    "intent": "coding",
    "complexity": "complex",
    "requires_vision": false,
    "requires_code": true,
    "requires_reasoning": false,
    "estimated_tokens": 24,
    "urgency": "deep_quality"
  }
}
```

---

## 4. Gateway Health & Monitoring

### 4.1 Check Provider Health
Concurrently pings all 6 integrated LLM providers and reports status, latency, and available models.

- **Method**: `GET`
- **Path**: `/gateway/health`
- **Auth Required**: Yes

#### Response (`200 OK`)
```json
{
  "nexora": {
    "provider": "nexora",
    "status": "online",
    "latency_ms": 1.2,
    "models": ["nexora-flagship", "nexora-fast", "nexora-auto"],
    "error": null
  },
  "google": {
    "provider": "google",
    "status": "online",
    "latency_ms": 112.4,
    "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
    "error": null
  },
  "openai": {
    "provider": "openai",
    "status": "online",
    "latency_ms": 94.6,
    "models": ["gpt-4o", "gpt-4o-mini"],
    "error": null
  },
  "anthropic": {
    "provider": "anthropic",
    "status": "online",
    "latency_ms": 138.1,
    "models": ["claude-3-5-sonnet", "claude-3-5-haiku"],
    "error": null
  }
}
```

---

## 5. Conversations Endpoints

- `GET /conversations`: List user conversations with pagination, search, and pin/archive filtering.
- `POST /conversations`: Create a new conversation.
- `GET /conversations/{id}`: Retrieve conversation details with all messages.
- `PATCH /conversations/{id}`: Rename conversation title.
- `PATCH /conversations/{id}/pin`: Toggle conversation pinned state.
- `PATCH /conversations/{id}/archive`: Toggle conversation archived state.
- `DELETE /conversations/{id}`: Delete conversation and all cascaded messages.

---

## 6. Messages & Streaming Endpoints

### 6.1 Stream Message (8-Stage Reasoning & Model Transparency)
Streams tokens token-by-token via Server-Sent Events (SSE) through the 8-Stage Reasoning Orchestrator.

- **Method**: `POST`
- **Path**: `/messages`
- **Auth Required**: Yes
- **Headers**:
  - `Accept: text/event-stream`
  - `Content-Type: application/json`

#### Request Body
```json
{
  "content": "What are the latency tradeoffs of Raft vs Paxos consensus?",
  "conversation_id": "4cf517be-5d7d-4ba6-86c4-722ff4ce6ce7",
  "model": "nexora-auto",
  "reasoning_mode": true,
  "web_search": false,
  "attachment_ids": []
}
```

#### SSE Stream Protocol (`text/event-stream`)
```
data: {"type": "start", "message_id": "asst_msg_123", "conversation_id": "4cf517be-..."}

data: {"type": "routing", "resolved_model": "claude-3-5-sonnet", "routing_reason": "Autonomous routing: Complex distributed systems query routed to Claude 3.5 Sonnet", "citations": [{"id": 1, "source_title": "distributed_systems.md", "chunk_index": 2, "content_snippet": "..."}]}

data: {"type": "reasoning", "content": "Analyzing consensus message round-trips in un-pipelined leader election...\n", "resolved_model": "claude-3-5-sonnet"}

data: {"type": "token", "content": "Both ", "resolved_model": "claude-3-5-sonnet"}
data: {"type": "token", "content": "Raft and Paxos ", "resolved_model": "claude-3-5-sonnet"}
data: {"type": "token", "content": "achieve consensus with $2F+1$ nodes...", "resolved_model": "claude-3-5-sonnet"}

data: {"type": "done", "finish_reason": "stop", "resolved_model": "claude-3-5-sonnet", "citations": [...]}
```

---

## 7. Memory Engine Endpoints

### 7.1 List User Memories
- **Method**: `GET`
- **Path**: `/memories`
- **Auth Required**: Yes
- **Query Parameters**: `category`, `memory_type`, `project_id`

### 7.2 Create / Store Memory (with Duplicate Detection)
Stores a memory. If an existing active memory has semantic similarity $\ge 0.88$, it updates the existing record automatically.

- **Method**: `POST`
- **Path**: `/memories`
- **Auth Required**: Yes

#### Request Body
```json
{
  "content": "User prefers async Python with SQLAlchemy 2.0 and Pydantic v2",
  "memory_type": "user_preference",
  "category": "preference",
  "project_id": null
}
```

### 7.3 Semantic Memory Search
- **Method**: `POST`
- **Path**: `/memories/search`
- **Auth Required**: Yes

#### Request Body
```json
{
  "query": "What are the user's preferred Python frameworks?",
  "top_k": 3,
  "min_similarity": 0.50
}
```

### 7.4 Delete Memory
- **Method**: `DELETE`
- **Path**: `/memories/{id}`
- **Auth Required**: Yes

---

## 8. RAG Knowledge Engine Endpoints

### 8.1 List Knowledge Collections
- **Method**: `GET`
- **Path**: `/rag/collections`
- **Auth Required**: Yes

### 8.2 Create Knowledge Collection
- **Method**: `POST`
- **Path**: `/rag/collections`
- **Auth Required**: Yes

#### Request Body
```json
{
  "name": "NEXORA Engineering Docs",
  "description": "System architecture, specifications, and design docs",
  "project_id": null
}
```

### 8.3 Ingest Document
Splits text into chunks with overlap, computes vector embeddings, and indexes chunks.

- **Method**: `POST`
- **Path**: `/rag/collections/{collection_id}/documents`
- **Auth Required**: Yes

#### Request Body
```json
{
  "title": "architecture_blueprint.md",
  "content": "Full markdown content of the blueprint...",
  "source_type": "text"
}
```

### 8.4 Hybrid Search (BM25 + Vector + RRF)
Executes dual dense vector + sparse BM25Okapi search and reciprocal rank fusion reranking.

- **Method**: `POST`
- **Path**: `/rag/search`
- **Auth Required**: Yes

#### Request Body
```json
{
  "query": "How does reciprocal rank fusion combine dense and sparse ranks?",
  "collection_ids": null,
  "top_k": 4,
  "alpha": 0.5
}
```

#### Response (`200 OK`)
```json
[
  {
    "chunk_id": "chunk-1",
    "document_id": "doc-1",
    "document_title": "architecture_blueprint.md",
    "collection_id": "col-1",
    "chunk_index": 2,
    "content": "RRF combines dense and sparse ranks using the reciprocal rank constant k=60...",
    "score": 0.016393,
    "dense_score": 0.9412,
    "sparse_score": 6.82
  }
]
```

---

## 9. Attachments Endpoints

- `POST /attachments/upload`: Multipart file upload with MIME validation and disk persistence.

---

## 10. Feedback Endpoints

- `POST /feedback`: Records thumbs up (`rating=1`) or thumbs down (`rating=-1`) for an assistant turn.

---

## 11. Document Intelligence Endpoints

### 11.1 Parse Document
- **Method**: `POST`
- **Path**: `/documents/parse`
- **Auth Required**: Yes
- **Body**:
  ```json
  {
    "file_path": "/path/to/doc.pdf",
    "attachment_id": "optional-uuid"
  }
  ```
- **Response**: Extracted structured text, page count, word count, and tables.

### 11.2 Compare Documents
- **Method**: `POST`
- **Path**: `/documents/compare`
- **Body**: `{ "file_path_1": "...", "file_path_2": "...", "focus_topic": "Architecture" }`
- **Response**: Similarities, differences, and metric delta tables.

### 11.3 RAG Ingest Document
- **Method**: `POST`
- **Path**: `/documents/rag-ingest`
- **Body**: `{ "attachment_id": "uuid", "collection_id": "uuid" }`

---

## 12. Multimodal Intelligence Endpoints

### 12.1 Image Analysis & OCR
- **Method**: `POST`
- **Path**: `/multimodal/image/analyze`
- **Body**:
  ```json
  {
    "file_path": "/path/to/diagram.png",
    "prompt": "Analyze this architecture topology",
    "analysis_type": "diagram",
    "model": "nexora-vision"
  }
  ```

### 12.2 Image Generation
- **Method**: `POST`
- **Path**: `/multimodal/image/generate`
- **Body**: `{ "prompt": "Futuristic neural data center", "size": "1024x1024" }`

### 12.3 Video Scene Analysis
- **Method**: `POST`
- **Path**: `/multimodal/video/analyze`
- **Body**: `{ "file_path": "/path/to/demo.mp4" }`
- **Response**: Scene markers with formatted timestamps `[MM:SS]`, duration, and summary.

---

## 13. Voice Intelligence Endpoints

### 13.1 Speech-to-Text Transcription
- **Method**: `POST`
- **Path**: `/voice/transcribe`
- **Body**: Multipart `file` (audio file)
- **Response**: Transcription text, duration, and confidence.

### 13.2 Text-to-Speech Synthesis
- **Method**: `POST`
- **Path**: `/voice/synthesize`
- **Body**: `{ "text": "Hello, welcome to NEXORA AI.", "voice": "alloy" }`
- **Response**: Audio binary stream (`audio/mpeg` or `audio/wav`).

---

## 14. Web Research Agent Endpoints

### 14.1 Search Web
- **Method**: `POST`
- **Path**: `/research/search`
- **Body**: `{ "query": "Transformer attention mechanisms", "max_results": 5 }`

### 14.2 Synthesize Research Report
- **Method**: `POST`
- **Path**: `/research/report`
- **Body**: `{ "query": "Quantum computing breakthroughs", "max_sources": 4 }`
- **Response**: Summary, key findings, and non-fabricated citations.

---

## 15. Multi-Agent Framework Endpoints

### 15.1 List Available Agents
- **Method**: `GET`
- **Path**: `/agents`
- **Response**: Catalog of all 8 specialized agents.

### 15.2 Execute Multi-Agent Workflow
- **Method**: `POST`
- **Path**: `/agents/run`
- **Body**:
  ```json
  {
    "goal": "Research distributed consensus algorithms and write an implementation in Python",
    "conversation_id": "optional-uuid"
  }
  ```
- **Response**: Multi-step plan, agent execution logs, and synthesized final answer.

---

## 16. Tool Execution Engine & Sandbox Endpoints

### 16.1 List Tools
- **Method**: `GET`
- **Path**: `/tools`
- **Response**: All registered tools with schemas and permission levels (`READ`, `ANALYZE`, `PREPARE`, `EXECUTE`).

### 16.2 Execute Tool
- **Method**: `POST`
- **Path**: `/tools/execute`
- **Body**:
  ```json
  {
    "tool_id": "web_search",
    "params": { "query": "FastAPI SSE architecture" },
    "is_approved": false
  }
  ```

### 16.3 Run Isolated Python Sandbox
- **Method**: `POST`
- **Path**: `/tools/sandbox/python`
- **Body**: `{ "code": "print(sum(range(100)))", "timeout_seconds": 10 }`

---

## 17. Error Handling & Status Codes

All errors return RFC 7807 compliant JSON:
```json
{
  "detail": "Error description"
}
```
- `200 OK`: Request succeeded.
- `201 Created`: Entity created.
- `400 Bad Request`: Validation failure.
- `401 Unauthorized`: Missing or invalid JWT.
- `403 Forbidden`: Insufficient permissions.
- `404 Not Found`: Target entity not found or access denied.
- `503 Service Unavailable`: Upstream provider failure (automatically recovered via fallback).
