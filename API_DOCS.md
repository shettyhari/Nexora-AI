# NEXORA AI – REST & Streaming API Documentation

This document provides a comprehensive reference for the NEXORA AI backend API (v1).

**Base URL**: `http://localhost:8000/api/v1`  
**Interactive Swagger UI**: `http://localhost:8000/docs`  
**OpenAPI Specification**: `http://localhost:8000/openapi.json`

---

## Table of Contents
1. [Authentication & Authorization](#1-authentication--authorization)
2. [Authentication Endpoints](#2-authentication-endpoints)
3. [User & Profile Endpoints](#3-user--profile-endpoints)
4. [Conversations Endpoints](#4-conversations-endpoints)
5. [Messages & Streaming Endpoints](#5-messages--streaming-endpoints)
6. [Attachments Endpoints](#6-attachments-endpoints)
7. [Feedback Endpoints](#7-feedback-endpoints)
8. [Models Endpoints](#8-models-endpoints)
9. [Projects Endpoints](#9-projects-endpoints)
10. [Error Handling & Status Codes](#10-error-handling--status-codes)

---

## 1. Authentication & Authorization

NEXORA AI uses JWT (JSON Web Tokens) with a dual-token strategy:
- **Access Token**: Short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, default: 30 minutes) token sent in the HTTP header.
- **Refresh Token**: Long-lived (`REFRESH_TOKEN_EXPIRE_DAYS`, default: 7 days) token used to obtain fresh access tokens.

### Header Format
```http
Authorization: Bearer <access_token>
```

All protected endpoints enforce strict tenant data isolation. Queries verify `user_id == current_user.id` on every database operation.

---

## 2. Authentication Endpoints

### 2.1 Register New User
Creates a new user account, associated profile, default user preferences, and returns JWT tokens.

- **Method**: `POST`
- **Path**: `/auth/register`
- **Auth Required**: No

#### Request Body
```json
{
  "email": "user@nexora.ai",
  "password": "SecurePassword123!",
  "full_name": "Jane Doe"
}
```

#### Response (`201 Created`)
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": "e9a08e17-7e61-4890-a3e1-31464dd297ff",
    "email": "user@nexora.ai",
    "is_active": true,
    "is_verified": false,
    "role": "user",
    "created_at": "2026-11-08T12:00:00Z"
  }
}
```

---

### 2.2 User Login
Authenticates an existing user and returns fresh access and refresh tokens.

- **Method**: `POST`
- **Path**: `/auth/login`
- **Auth Required**: No

#### Request Body
```json
{
  "email": "user@nexora.ai",
  "password": "SecurePassword123!"
}
```

#### Response (`200 OK`)
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": "e9a08e17-7e61-4890-a3e1-31464dd297ff",
    "email": "user@nexora.ai",
    "is_active": true,
    "is_verified": false,
    "role": "user",
    "created_at": "2026-11-08T12:00:00Z"
  }
}
```

---

### 2.3 Refresh Token
Generates a new access token using a valid refresh token.

- **Method**: `POST`
- **Path**: `/auth/refresh`
- **Auth Required**: No

#### Request Body
```json
{
  "refresh_token": "eyJhbGciOi..."
}
```

#### Response (`200 OK`)
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

---

### 2.4 Forgot Password
Initiates a password reset flow.

- **Method**: `POST`
- **Path**: `/auth/forgot-password`
- **Auth Required**: No

#### Request Body
```json
{
  "email": "user@nexora.ai"
}
```

#### Response (`200 OK`)
```json
{
  "message": "If this email is registered, password reset instructions have been sent."
}
```

---

### 2.5 Reset Password
Completes the password reset process using a reset token.

- **Method**: `POST`
- **Path**: `/auth/reset-password`
- **Auth Required**: No

#### Request Body
```json
{
  "token": "reset-token-string",
  "new_password": "NewSecurePassword456!"
}
```

#### Response (`200 OK`)
```json
{
  "message": "Password successfully updated."
}
```

---

## 3. User & Profile Endpoints

### 3.1 Get Current User
- **Method**: `GET`
- **Path**: `/users/me`
- **Auth Required**: Yes

#### Response (`200 OK`)
```json
{
  "id": "e9a08e17-7e61-4890-a3e1-31464dd297ff",
  "email": "user@nexora.ai",
  "is_active": true,
  "is_verified": false,
  "role": "user",
  "created_at": "2026-11-08T12:00:00Z"
}
```

---

### 3.2 Get User Profile
- **Method**: `GET`
- **Path**: `/users/profile`
- **Auth Required**: Yes

#### Response (`200 OK`)
```json
{
  "id": "a1b2c3d4-...",
  "user_id": "e9a08e17-7e61-4890-a3e1-31464dd297ff",
  "full_name": "Jane Doe",
  "avatar_url": null,
  "bio": "AI Researcher & Builder",
  "timezone": "UTC",
  "created_at": "2026-11-08T12:00:00Z",
  "updated_at": "2026-11-08T12:00:00Z"
}
```

---

### 3.3 Update User Profile
- **Method**: `PUT`
- **Path**: `/users/profile`
- **Auth Required**: Yes

#### Request Body
```json
{
  "full_name": "Jane Doe, Ph.D.",
  "bio": "Autonomous AI System Lead",
  "timezone": "America/New_York"
}
```

#### Response (`200 OK`)
```json
{
  "id": "a1b2c3d4-...",
  "user_id": "e9a08e17-7e61-4890-a3e1-31464dd297ff",
  "full_name": "Jane Doe, Ph.D.",
  "avatar_url": null,
  "bio": "Autonomous AI System Lead",
  "timezone": "America/New_York",
  "created_at": "2026-11-08T12:00:00Z",
  "updated_at": "2026-11-08T12:05:00Z"
}
```

---

## 4. Conversations Endpoints

### 4.1 List Conversations
Lists conversations for the authenticated user with filtering, pagination, and search.

- **Method**: `GET`
- **Path**: `/conversations`
- **Auth Required**: Yes
- **Query Parameters**:
  - `page` (integer, default: 1)
  - `per_page` (integer, default: 50, max: 100)
  - `search` (string, optional)
  - `is_archived` (boolean, default: false)
  - `is_pinned` (boolean, optional)

#### Response (`200 OK`)
```json
[
  {
    "id": "4cf517be-5d7d-4ba6-86c4-722ff4ce6ce7",
    "title": "Quantum Algorithm Optimization",
    "model_id": "nexora-flagship",
    "is_pinned": true,
    "is_archived": false,
    "created_at": "2026-11-08T12:00:00Z",
    "updated_at": "2026-11-08T12:15:00Z"
  }
]
```

---

### 4.2 Create Conversation
- **Method**: `POST`
- **Path**: `/conversations`
- **Auth Required**: Yes

#### Request Body
```json
{
  "title": "New Chat",
  "model_id": "gemini-1.5-pro",
  "system_instruction": "You are NEXORA, an expert systems architect.",
  "project_id": null
}
```

#### Response (`201 Created`)
```json
{
  "id": "4cf517be-5d7d-4ba6-86c4-722ff4ce6ce7",
  "title": "New Chat",
  "model_id": "gemini-1.5-pro",
  "system_instruction": "You are NEXORA, an expert systems architect.",
  "is_pinned": false,
  "is_archived": false,
  "created_at": "2026-11-08T12:00:00Z",
  "updated_at": "2026-11-08T12:00:00Z",
  "messages": []
}
```

---

### 4.3 Get Conversation Details
Retrieves a conversation by ID with all messages ordered chronologically.

- **Method**: `GET`
- **Path**: `/conversations/{id}`
- **Auth Required**: Yes

#### Response (`200 OK`)
```json
{
  "id": "4cf517be-5d7d-4ba6-86c4-722ff4ce6ce7",
  "title": "Quantum Algorithm Optimization",
  "model_id": "gemini-1.5-pro",
  "is_pinned": false,
  "is_archived": false,
  "created_at": "2026-11-08T12:00:00Z",
  "updated_at": "2026-11-08T12:01:00Z",
  "messages": [
    {
      "id": "11111111-...",
      "role": "user",
      "content": "Explain Grover's search algorithm.",
      "thought": null,
      "tokens_prompt": 14,
      "tokens_completion": 0,
      "created_at": "2026-11-08T12:00:10Z"
    },
    {
      "id": "22222222-...",
      "role": "assistant",
      "content": "Grover's algorithm provides quadratic speedup for unstructured search...",
      "thought": "1. Analyze quantum superposition state\n2. Oracle phase inversion\n3. Amplitude amplification",
      "tokens_prompt": 14,
      "tokens_completion": 145,
      "created_at": "2026-11-08T12:00:15Z"
    }
  ]
}
```

---

### 4.4 Update Conversation (Rename)
- **Method**: `PATCH`
- **Path**: `/conversations/{id}`
- **Auth Required**: Yes

#### Request Body
```json
{
  "title": "Quantum Computing & Complexity Theory"
}
```

---

### 4.5 Pin / Unpin Conversation
- **Method**: `PATCH`
- **Path**: `/conversations/{id}/pin`
- **Auth Required**: Yes

---

### 4.6 Archive / Unarchive Conversation
- **Method**: `PATCH`
- **Path**: `/conversations/{id}/archive`
- **Auth Required**: Yes

---

### 4.7 Delete Conversation
Deletes the conversation and cascades deletion to all associated messages, attachments, and feedback.

- **Method**: `DELETE`
- **Path**: `/conversations/{id}`
- **Auth Required**: Yes

#### Response (`204 No Content`)

---

## 5. Messages & Streaming Endpoints

### 5.1 Send Message & Stream Response (SSE)
Sends a user message and returns a real-time Server-Sent Events (SSE) token stream with reasoning tokens and metadata.

- **Method**: `POST`
- **Path**: `/messages/stream`
- **Auth Required**: Yes
- **Headers**:
  - `Accept: text/event-stream`
  - `Content-Type: application/json`

#### Request Body
```json
{
  "conversation_id": "4cf517be-5d7d-4ba6-86c4-722ff4ce6ce7",
  "content": "Synthesize a parallel reduction algorithm in CUDA C++.",
  "model_id": "gemini-1.5-pro",
  "reasoning_mode": true,
  "web_search": false,
  "attachment_ids": []
}
```

#### SSE Stream Protocol (`text/event-stream`)
The server streams chunks structured as JSON events:

```
data: {"type": "user_message", "message": {"id": "msg-1", "role": "user", "content": "..."}}

data: {"type": "thought", "delta": "Analyzing warp-level shuffle primitives..."}

data: {"type": "token", "delta": "Here"}
data: {"type": "token", "delta": " is a"}
data: {"type": "token", "delta": " high-performance"}
data: {"type": "token", "delta": " CUDA kernel:\n\n```cuda\n..."}

data: {"type": "done", "message_id": "msg-2", "prompt_tokens": 12, "completion_tokens": 320}
```

#### Event Types:
| Event Type | Payload Fields | Description |
| :--- | :--- | :--- |
| `user_message` | `message: MessageResponse` | Confirms user message persistence |
| `thought` | `delta: string` | Deep reasoning thought tokens |
| `token` | `delta: string` | Standard assistant response tokens |
| `error` | `detail: string` | Streaming or provider execution failure |
| `done` | `message_id`, `prompt_tokens`, `completion_tokens` | Stream completion signal |

---

### 5.2 Edit Message
Updates a previous user message.

- **Method**: `PUT`
- **Path**: `/messages/{id}`
- **Auth Required**: Yes

#### Request Body
```json
{
  "content": "Synthesize a parallel reduction kernel using warp shuffle (__shfl_down_sync)."
}
```

---

### 5.3 Regenerate Assistant Response
Regenerates an AI response for a specific conversation using prior conversation context.

- **Method**: `POST`
- **Path**: `/messages/{id}/regenerate`
- **Auth Required**: Yes

#### Response: Returns Server-Sent Events stream identical to `/messages/stream`.

---

## 6. Attachments Endpoints

### 6.1 Upload File Attachment
- **Method**: `POST`
- **Path**: `/attachments/upload`
- **Auth Required**: Yes
- **Content-Type**: `multipart/form-data`

#### Form Fields:
- `file`: Binary file upload
- `conversation_id`: Optional UUID string

#### Response (`201 Created`)
```json
{
  "id": "33333333-...",
  "filename": "dataset.csv",
  "file_size": 1048576,
  "mime_type": "text/csv",
  "url": "/uploads/33333333-dataset.csv",
  "created_at": "2026-11-08T12:00:00Z"
}
```

---

## 7. Feedback Endpoints

### 7.1 Submit Message Feedback
Records thumbs-up (`rating=1`) or thumbs-down (`rating=-1`) feedback on an assistant message.

- **Method**: `POST`
- **Path**: `/feedback`
- **Auth Required**: Yes

#### Request Body
```json
{
  "message_id": "22222222-...",
  "rating": 1,
  "comment": "Exceptionally clear CUDA explanation."
}
```

#### Response (`200 OK`)
```json
{
  "id": "55555555-...",
  "message_id": "22222222-...",
  "rating": 1,
  "comment": "Exceptionally clear CUDA explanation.",
  "created_at": "2026-11-08T12:01:00Z"
}
```

---

## 8. Models Endpoints

### 8.1 List Configured Models
Lists all available LLM models and their operational capabilities.

- **Method**: `GET`
- **Path**: `/models`
- **Auth Required**: Yes

#### Response (`200 OK`)
```json
[
  {
    "id": "nexora-flagship",
    "name": "NEXORA Flagship",
    "provider": "nexora",
    "description": "NEXORA Autonomous reasoning engine with integrated search.",
    "is_default": true,
    "context_window": 128000,
    "supports_vision": true,
    "supports_reasoning": true
  },
  {
    "id": "gemini-1.5-pro",
    "name": "Google Gemini 1.5 Pro",
    "provider": "google",
    "description": "State-of-the-art multimodal reasoning with 2M token context.",
    "is_default": false,
    "context_window": 2000000,
    "supports_vision": true,
    "supports_reasoning": true
  },
  {
    "id": "gpt-4o",
    "name": "OpenAI GPT-4o",
    "provider": "openai",
    "description": "High-intelligence multimodal flagship model.",
    "is_default": false,
    "context_window": 128000,
    "supports_vision": true,
    "supports_reasoning": true
  },
  {
    "id": "claude-3-5-sonnet",
    "name": "Anthropic Claude 3.5 Sonnet",
    "provider": "anthropic",
    "description": "Leading model for coding, analysis, and nuanced reasoning.",
    "is_default": false,
    "context_window": 200000,
    "supports_vision": true,
    "supports_reasoning": true
  }
]
```

---

## 9. Projects Endpoints

### 9.1 List User Projects
- **Method**: `GET`
- **Path**: `/projects`
- **Auth Required**: Yes

### 9.2 Create Project
- **Method**: `POST`
- **Path**: `/projects`
- **Auth Required**: Yes

---

## 10. Error Handling & Status Codes

All errors return standard RFC 7807 compliant JSON:

```json
{
  "detail": "Descriptive error message"
}
```

### Standard Status Codes:
- `200 OK`: Request succeeded.
- `201 Created`: Resource successfully created.
- `204 No Content`: Resource deleted successfully.
- `400 Bad Request`: Invalid payload or missing parameters.
- `401 Unauthorized`: Missing, expired, or invalid JWT token.
- `403 Forbidden`: User does not have permission to access resource.
- `404 Not Found`: Target entity does not exist or belongs to another user.
- `422 Unprocessable Entity`: Pydantic validation failure.
- `500 Internal Server Error`: Server exception.
- `503 Service Unavailable`: Upstream LLM provider failure or network timeout.
