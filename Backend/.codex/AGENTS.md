# AGENTS.md

# Alfred - AI Dating Concierge
## Backend AI Coding Instructions

This document defines how AI coding assistants (Codex, ChatGPT, Claude, etc.) should contribute to this backend project.

---

# Read First

Before implementing any feature:

1. Read `PROJECT_CONTEXT.md`.
2. Understand the existing architecture.
3. Follow the established project conventions.
4. Preserve consistency across the codebase.

Do **not** make architectural changes without explicit approval.

---

# Project Overview

This repository contains the backend for **Alfred - AI Dating Concierge**, an AI-powered dating assistant that communicates through both **text** and **voice**.

The backend is responsible for:

- Business logic
- Authentication
- Database
- AI integration
- Conversation persistence
- Scheduling
- Notifications
- REST chat orchestration for the current MVP
- Future WebSocket communication when real-time chat/voice is prioritized

The backend **is the single source of truth**.

The AI service is completely **stateless**.

---

# Technology Stack

Backend:

- Python
- Django
- Django REST Framework
- PostgreSQL
- Django Channels
- Redis
- Celery
- Celery Beat
- JWT Authentication
- drf-spectacular (Swagger)

Frontend:

- React (Admin Dashboard)
- Flutter (Mobile App)

AI Service:

- FastAPI
- OpenAI
- Anthropic
- SERP API

---

# Architecture Rules

Follow a feature-based architecture.

Each Django app owns its own:

- models
- serializers
- views
- services
- permissions
- urls
- admin
- tasks (when necessary)

Avoid cross-app coupling whenever possible.

---

# Business Logic

Business logic belongs inside the **service layer**.

Views should remain thin.

Views should only:

- validate request
- call service
- return response

Avoid placing business logic inside:

- views
- serializers
- models (except simple helpers)

---

# AI Integration

Never implement AI logic inside Django.

Django only:

- prepares payload
- calls AI service
- receives response
- stores response
- returns response

The AI service is responsible for:

- reasoning
- recommendations
- planning
- prompt engineering
- LLM interactions

---

# Database

Use UUID primary keys.

Every model should contain timestamps whenever appropriate.

Prefer explicit relationships over unnecessary JSON fields.

Use JSONField only when flexibility is required.

Avoid premature optimization.

---

# API Development

Prefer REST APIs for:

- CRUD
- Authentication
- Profile
- Plans
- Calendar
- Notifications

Current MVP chat decision:

- Use REST for chat through Django.
- Frontend calls Django, not FastAPI AI.
- Django calls FastAPI AI `/chat`.
- Django stores conversations, messages, AI session IDs, and structured AI response JSON.
- Clients continue chat by sending Django `conversation_id`, not AI `session_id`.
- Pass FastAPI `session_status` (`new`, `active`, `expired`) through to clients.
- For `mode=speak`, premium users may receive Alfred voice audio from FastAPI AI `/voice/speak`.
- The multipart flow is `POST /api/chat/`; the cached-audio flow is `POST /api/chat/cached-audio/` plus `GET /api/chat/messages/{message_id}/audio/`.
- For free users, return `voice_agent=flutter_tts` and no audio payload.
- Do not store generated audio in the database.

Use WebSockets later for:

- Live chat
- Voice conversations
- Streaming AI responses
- Typing indicators
- Real-time events

---

# Coding Standards

Follow:

- PEP 8
- Django Best Practices
- DRF Best Practices

Use:

- meaningful variable names
- type hints whenever possible
- readable code
- reusable components

Prioritize readability over clever implementations.

---

# Performance

When querying related models:

Use:

- select_related()
- prefetch_related()

Avoid N+1 queries.

Always paginate list APIs.

Avoid unnecessary database hits.

---

# Security

Always:

- validate permissions
- authenticate users
- validate input
- never trust client data

Never expose internal exceptions.

Never expose sensitive information.

---

# Before Creating New Code

Before adding:

- models
- apps
- services
- websocket consumers

Check whether similar functionality already exists.

Prefer extending existing code instead of creating duplicates.

---

# Do Not

Do NOT:

- change architecture without approval
- move files unnecessarily
- introduce new frameworks
- create unnecessary abstractions
- duplicate business logic
- bypass service layer
- place AI logic inside Django

---

# When Creating New Features

Unless instructed otherwise, follow this order:

1. Model
2. Migration
3. Serializer
4. Service
5. Permission
6. View
7. URL
8. Admin
9. Swagger Documentation

---

# Existing Project Decisions

Assume these decisions are intentional:

- UUID primary keys
- Email authentication
- User model stores onboarding information
- AI is stateless
- Backend is source of truth
- REST-first architecture for MVP conversations
- WebSockets are deferred for future real-time/streaming work
- React Admin Dashboard
- Flutter Mobile App
- FastAPI AI Service

Do not attempt to redesign these without explicit instruction.

---

# Communication Style

When proposing changes:

- explain reasoning briefly
- mention trade-offs
- avoid over-engineering
- prefer MVP-friendly solutions

When uncertain:

Ask before making architectural changes.

Do not make assumptions that could affect the database schema or public APIs.

---

# Primary Goal

Generate production-ready, maintainable, scalable Django code while preserving the existing architecture and keeping the backend clean, consistent, and easy to extend.
