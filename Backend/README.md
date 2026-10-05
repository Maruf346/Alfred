# Alfred - AI Dating Concierge (Backend)

## Overview

The backend of **Alfred - AI Dating Concierge** is built with **Django** and **Django REST Framework (DRF)**.

The backend acts as the central business layer of the application. It is responsible for authentication, user management, subscriptions, conversation history, AI integration, scheduling, notifications, and all database operations.

The AI service itself is completely **stateless** and does not directly communicate with the mobile application. Instead, the backend works as a middleware between the frontend and the AI service.

```
Flutter App
      │
      ▼
 Django Backend
      │
      ▼
 FastAPI AI Service
      │
      ▼
 OpenAI / Anthropic / External APIs
```

---

# Technology Stack

## Backend

- Python
- Django
- Django REST Framework
- PostgreSQL
- JWT Authentication
- Django Channels (WebSockets)
- Redis
- Celery
- Celery Beat
- drf-spectacular (Swagger/OpenAPI)

## External Services

- FastAPI AI Service
- OpenAI API
- Anthropic API
- SERP API
- Future Payment Providers
- Firebase Cloud Messaging (planned)

---

# Local Development

These commands are intended for day-to-day backend development on Windows from the VS Code terminal.

## 1. Setup

From the repository root:

```powershell
cd Backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Create or update `Backend/.env`. At minimum for local development:

```env
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,10.10.28.178
DB_ENGINE=django.db.backends.sqlite3
REDIS_HOST=localhost
REDIS_PORT=6379
ALFRED_AI_BASE_URL=http://127.0.0.1:8001
ALFRED_AI_API_KEY=
ALFRED_AI_TIMEOUT_SECONDS=30
ALFRED_AI_SESSION_TTL_SECONDS=7200
ALFRED_AI_HISTORY_LIMIT=20
ALFRED_CHAT_AUDIO_TTL_SECONDS=3600
```

Use your own LAN IP in `ALLOWED_HOSTS` if another device or collaborator needs to access the backend from the same network.

If the FastAPI AI service is running on another machine or port, update `ALFRED_AI_BASE_URL`, for example `http://10.10.28.170:8001`.

## 2. Database

Run migrations:

```powershell
python manage.py migrate
```

Create an admin user:

```powershell
python manage.py createsuperuser
```

Check the project:

```powershell
python manage.py check
```

Run tests:

```powershell
python manage.py test
```

## 3. Start The Full Dev Stack

Use the helper script:

```powershell
.\scripts\start-dev.cmd
```

This starts:

- Redis, if `redis-server` is available in `PATH`
- Daphne ASGI server on `0.0.0.0:8888`
- Celery worker
- Celery beat

Open Swagger:

```text
http://localhost:8888/api/docs/
```

For another device on the same network, use your LAN IP:

```text
http://10.10.28.178:8888/api/docs/
```

The server must be running on `0.0.0.0`, and the LAN IP must be included in `ALLOWED_HOSTS`.

## 4. Stop The Dev Stack

```powershell
.\scripts\stop-dev.cmd
```

The script stops the processes it started using PID records stored in:

```text
Backend/.runtime/
```

This folder is ignored by git.

## 5. Useful Start Options

Run on another port:

```powershell
.\scripts\start-dev.cmd -Port 8899
```

Skip Redis if it is already running separately:

```powershell
.\scripts\start-dev.cmd -SkipRedis
```

View logs:

```powershell
Get-ChildItem .\.runtime\logs
Get-Content .\.runtime\logs\asgi.err.log -Tail 100
Get-Content .\.runtime\logs\celery-worker.err.log -Tail 100
Get-Content .\.runtime\logs\celery-beat.err.log -Tail 100
```

## 6. Redis Notes

For local Windows development without Docker, Redis should usually be reachable at:

```text
redis://localhost:6379
```

In `.env`, that means:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
```

That setting is correct only if Redis is actually running. Registration OTPs, password reset OTPs, Celery, and Channels use Redis. If Redis is not reachable, endpoints like registration initiation can fail with:

```text
Error 10061 connecting to localhost:6379
```

If `redis-server` is not installed or not available in `PATH`, start Redis manually and then run:

```powershell
.\scripts\start-dev.cmd -SkipRedis
```

When Docker Compose is added later, `REDIS_HOST=redis` will be correct inside containers. For local Windows scripts, use `REDIS_HOST=localhost`.

Quick Docker Redis option:

```powershell
docker run --name alfred-redis -p 6379:6379 -d redis:7
.\scripts\start-dev.cmd -SkipRedis
```

## 7. Manual Fallback Commands

If you ever want to run each process manually in separate terminals:

Terminal 1:

```powershell
redis-server --port 6379
```

Terminal 2:

```powershell
python -m daphne -b 0.0.0.0 -p 8888 core.asgi:application
```

Terminal 3:

```powershell
python -m celery -A core worker --loglevel=info --pool=solo
```

Terminal 4:

```powershell
python -m celery -A core beat --loglevel=info
```

---

# Architecture

The backend follows a **feature-based architecture**.

```
Backend/
│
├── core/
│
├── apps/
│   ├── users/
│   ├── authentication/
│   ├── chat/
│   ├── ai_gateway/
│   ├── plans/
│   ├── calendar/
│   ├── notifications/
│   ├── subscriptions/
│   ├── common/
│   └── api/
│
├── requirements.txt
└── manage.py
```

Each application owns its own models, serializers, services, permissions, views, urls, tasks and business logic.

---

# Backend Responsibilities

The backend is responsible for:

- User authentication
- JWT authorization
- User profile management
- Onboarding
- AI request validation
- Calling AI APIs
- Persisting AI responses
- Conversation history
- REST chat orchestration for the current MVP
- Future WebSocket communication when real-time chat/voice is prioritized
- Date plans
- Calendar events
- Notifications
- Subscription validation
- API documentation
- Business rules

The backend **does not contain AI logic**.

---

# AI Integration

The AI service is designed to be **stateless**.

The backend is the source of truth.

```
User

↓

Flutter

↓

Backend

↓

Load Conversation

↓

Prepare Context

↓

Call AI

↓

Receive Response

↓

Save Response

↓

Return to Client
```

The AI service never directly accesses the database.

---

# Chat And Voice Communication

The current MVP uses REST for chat and voice orchestration.

Frontend calls:

```http
POST /api/chat/
```

The backend then calls the FastAPI AI service:

```http
POST /chat
POST /voice/speak
```

Use `mode=chat` for text-only replies.

Use `mode=speak` when the mobile app wants voice behavior. Premium users receive a `multipart/mixed` response containing JSON metadata plus raw Alfred MP3 audio. Free users receive JSON with `voice_agent=flutter_tts` and no audio payload.

Alternative cached-audio flow for easier frontend playback:

```http
POST /api/chat/cached-audio/
GET /api/chat/messages/{message_id}/audio/
```

`POST /api/chat/cached-audio/` always returns JSON. For premium `mode=speak`, it generates Alfred audio during the request, stores the MP3 bytes in Redis temporarily, and returns `audio_url`. The frontend then calls that URL to receive a normal `audio/mpeg` file response. Audio expires after `ALFRED_CHAT_AUDIO_TTL_SECONDS`.

The frontend must use the exact returned `audio_url`, including its `token` query parameter. Tokenless or old audio URLs return `404`.

To continue a chat, the frontend sends the backend `conversation_id` returned by the previous `/api/chat/` response. The frontend should not send the AI `session_id`; Django stores that on the conversation and sends it to the FastAPI AI service when it is still active.

AI chat responses include `session_status` from FastAPI:

- `new`: no AI session was sent and a new one was created.
- `active`: the stored AI session was found and used.
- `expired`: the stored AI session was not found by the AI service, so the UI should treat prior AI context as lost and continue from a fresh context.

Generated audio is not stored in the database.

WebSockets are deferred and may be used later for:

- Live conversations
- Voice sessions
- Streaming AI responses
- Typing indicators
- Future real-time notifications

Standard CRUD operations continue to use REST APIs.

---

# Core Features

## User

Stores:

- Basic account information
- Profile
- Preferences
- Subscription state
- Authentication provider
- Device token
- Email Login
- Registration
- Password Reset
- Email Verification
- JWT Authentication
- Google Login (future)
- Apple Login (future)

---

## Chat

Responsible for:

- Conversations
- Messages
- Voice sessions
- Chat history
- WebSocket consumers

Every conversation is stored permanently inside PostgreSQL.

---

## AI Gateway

The AI Gateway communicates with the FastAPI service.

Responsibilities:

- Prepare AI requests
- Pass conversation history
- Receive AI responses
- Handle failures
- Return structured data

No AI logic exists inside Django.

---

## Plans

Stores AI-generated or manually created date plans.

Users can:

- Save plans
- Edit plans
- Delete plans
- View history
- View upcoming plans

---

## Calendar

Responsible for scheduling.

Supports:

- Upcoming events
- Date reminders
- Future Google Calendar integration

---

## Notifications

Responsible for:

- In-app notifications
- Reminder scheduling

---

## Subscriptions

Responsible for:

- Premium validation
- Subscription status
- Future payment integration

The initial MVP stores the current subscription state inside the `User` model for quick authorization checks.

A dedicated `UserSubscription` model will be introduced during payment implementation to manage subscription history, provider transactions, renewals, and billing logic while keeping the `User` model synchronized with the current active subscription.

---

# Admin Dashboard (Planned)

An internal React-based admin dashboard will be developed for administrators to manage the platform.

## Authentication

- Admin Login
- Admin Logout
- Change Password
- Update Profile
  - Profile Picture
  - Full Name
  - Bio

## Dashboard & Analytics

- User Statistics
- Active User Statistics
- Subscription & Payment Statistics
- Revenue Overview (Future)
- System Activity Summary

## User Management

- View User List
- Search & Filter Users
- Retrieve User Details
- Block / Unblock Users (Future)
- Manage User Accounts

## Subscription & Payment Management

- View Subscription List
- Retrieve Subscription Details
- View Payment History
- Manage Subscription Status (Future)

## Notifications

- View Notifications
- Mark Notifications as Read

## General Features

- Server-side Pagination
- Searching
- Filtering
- Sorting
- Secure Admin Permissions
- Role-based Access Control (Future)

---

# Design Principles

- Feature-based architecture
- Separation of concerns
- Thin Views
- Service Layer pattern
- Repository-independent business logic
- Stateless AI
- Backend as the single source of truth
- REST-first communication for MVP chat and voice orchestration
- WebSockets deferred for future real-time streaming
- REST APIs for CRUD operations
- Scalable and maintainable codebase

---

# Future Improvements

- Subscription Payments
- AI Streaming
- Google Calendar Sync
- Background Workers
- Admin Dashboard Improvements
- Multi-device Support

---

# Project Status

🚧 Currently under active development.
