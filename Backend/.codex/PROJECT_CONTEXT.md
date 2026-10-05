# PROJECT_CONTEXT.md

# Alfred - AI Dating Concierge
## Backend Project Context

> This document serves as the single source of truth for the backend architecture, business logic, project planning, and development decisions.
>
> Every AI coding assistant (Codex, ChatGPT, Claude, Cursor, etc.) should read this document before implementing new features or making architectural decisions.
>
> This document intentionally contains product context in addition to technical context so that future development remains consistent.

---

# Table of Contents

1. Project Overview
2. Product Vision
3. Technology Stack
4. Repository Structure
5. System Architecture
6. Backend Responsibilities
7. AI Responsibilities
8. Communication Between Backend & AI
9. Authentication & User Management
10. User Onboarding
11. Chat & Voice Conversation System
12. WebSocket Architecture
13. Conversation Persistence
14. AI Features
15. Plans & Calendar
16. Notifications
17. Subscription System
18. Admin Dashboard
19. Database Design
20. Django Applications
21. API Design Guidelines
22. Coding Standards
23. Architectural Decisions
24. Development Roadmap
25. Future Improvements
26. Instructions for AI Coding Assistants

---

# 1. Project Overview

## Project Name

**Alfred - AI Dating Concierge**

## Product Summary

Alfred is an AI-powered dating concierge that helps users plan better dates, improve conversations, discover restaurants, find gifts, receive relationship coaching, organize date plans, and much more.

The application primarily targets **voice-first interaction**, while also fully supporting traditional text conversations.

Unlike traditional chatbots, Alfred behaves more like a personal AI assistant with a consistent personality, capable of understanding user preferences and helping users organize their dating experiences.

The system consists of four major components:

- Django Backend
- FastAPI AI Service
- Flutter Mobile Application
- React Admin Dashboard

The backend acts as the central system that coordinates communication between every component.

---

# 2. Product Vision

The long-term vision of Alfred is to become an intelligent AI companion that assists users before, during, and after dates.

Examples include:

- Restaurant recommendations
- Date planning
- Gift suggestions
- Relationship coaching
- Conversation advice
- Travel planning
- Event planning
- Calendar scheduling
- Reminder notifications
- Personalized recommendations based on previous conversations

The AI should feel like a personal concierge instead of a generic chatbot.

---

# 3. Technology Stack

## Backend

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

## AI Service

The AI service is developed independently.

Technology:

- FastAPI
- OpenAI API
- Anthropic API
- SERP API
- ElevenLabs 

The AI developer owns this repository.

Backend developers should never implement AI logic inside Django.

## Frontend

### Mobile

- Flutter

### Admin Dashboard

- React

---

# 4. Repository Structure

This repository is a monorepo containing multiple projects.

```

Repository

├── Backend/
├── Ai/
├── Frontend/
└── App Developer/

```

Only the **Backend** directory is maintained by this project context.

The AI project has its own architecture and is maintained independently.

---

# 5. High-Level System Architecture

```

Flutter Mobile App

│

▼

Django Backend

│

├─────────────── PostgreSQL

│

├─────────────── Redis

│

├─────────────── Celery

│

└─────────────── FastAPI AI

│

▼

OpenAI / Anthropic / External APIs

```

The backend is the only component allowed to communicate with both the database and the AI service.

The frontend never communicates directly with the AI service.

The AI service never communicates directly with the database.

---

# 6. Backend Responsibilities

The backend is responsible for every piece of business logic.

Responsibilities include:

- Authentication
- User Management
- Profile Management
- User Onboarding
- Authorization
- AI Request Validation
- Conversation Persistence
- AI Communication
- Plan Management
- Calendar Events
- Notifications
- Subscription Validation
- Admin Dashboard APIs
- WebSocket Communication
- API Documentation
- Database Management

The backend is the **single source of truth**.

No frontend application should make business decisions.

No AI service should own business logic.

---

# 7. AI Responsibilities

The AI service is intentionally designed to be **stateless**.

It does **not** own:

- users
- authentication
- conversations
- subscriptions
- notifications
- plans
- calendar
- database

Instead, it only performs intelligent reasoning.

Examples:

- Restaurant recommendations
- Date planning
- Gift suggestions
- Relationship coaching
- Conversation generation
- Travel suggestions
- Search
- LLM reasoning

The AI should behave like a function:

```

Input

↓

Reason

↓

Output

```

It should never become the source of truth for application data.

---

# 8. Backend ↔ AI Communication

The backend acts as a middleware between the frontend and the AI service.

General communication flow:

```

Flutter

↓

Backend

↓

Load User

↓

Load Conversation

↓

Load Preferences

↓

Prepare Context

↓

Call FastAPI

↓

Receive AI Response

↓

Save Response

↓

Return Response

```

The backend is responsible for:

- validating permissions
- validating subscriptions
- loading conversation history
- preparing AI context
- storing AI responses
- returning responses to clients

The AI service only receives the information necessary to generate a response.

The AI service should never know anything about database schemas or application models.

---

# Core Design Philosophy

The architecture follows several important principles.

## Backend owns the business.

The backend makes all business decisions.

## AI owns intelligence.

The AI performs reasoning only.

## Frontend owns presentation.

Flutter and React are responsible only for user interface and user experience.

## Database belongs to Django.

The AI never writes directly to the database.

## Voice is first-class.

Voice interaction is treated as a primary feature rather than an add-on.

All architecture decisions should consider voice conversations as a core feature.


---

# 9. Authentication & User Management

Authentication is handled entirely by the Django backend.

Authentication method:

- JWT Authentication
- Email & Password Login

Future authentication providers:

- Google Sign-In
- Apple Sign-In

The backend is responsible for:

- Registration
- Login
- Logout
- Password Reset
- Change Password
- Email Verification
- Token Validation

The `User` model uses email as the unique identifier.

```python
USERNAME_FIELD = "email"
username = None
```

The project uses a custom User model from the beginning.

## User Model Philosophy

The project intentionally keeps profile information inside the `User` model instead of introducing a separate `Profile` model.

Current user information includes:

- Email
- Full Name
- Gender
- Age
- Profile Picture
- Location
- Interests
- Budget Preference
- Authentication Provider
- Device Token
- Subscription Status etc. 

This approach is intentional to keep the MVP simple.

If the project grows significantly in the future, profile-related information may be extracted into a dedicated model.

---

## Admin Users

Administrators use the same User model.

Roles are determined using Django's built-in permission system.

Administrator:

```

is_staff = True
is_superuser = True

```

Application User:

```

is_staff = False
is_superuser = False

```

No custom Role model is currently planned.

---

# 10. User Onboarding

After registration, users complete an onboarding process.

The onboarding helps Alfred personalize recommendations.

Collected information:

- Age
- Gender
- Current Location
- Interests
- Budget Preference

Example interests:

```

[
"Coffee",
"Hiking",
"Movies",
"Travel",
"Books"
]

```

These are stored as JSON to allow flexibility.

Budget is intentionally stored as text because it represents user preference rather than a strict numeric value.

Examples:

- $20 - $50
- $50 - $100
- $100 - $300
- $300+ 
- $2342

Users may skip onboarding.

Future onboarding fields may include:

- Favorite Cuisine
- Music Preferences
- Personality
- Love Language
- Preferred Activities

---

# 11. Chat System

The chat system is one of the core components of Alfred.

Every conversation is permanently stored.

The chat system supports:

- Text Chat
- Voice Chat
- REST-based AI chat for the current MVP

Internally, both are stored as text messages.

Current MVP decision:

- Frontend calls Django REST APIs only.
- Django calls the FastAPI AI service over HTTP.
- The frontend must not call the AI service directly.
- WebSocket chat/voice is deferred until real-time streaming is prioritized.

Voice conversations follow this process:

Speech

↓

Speech-to-Text

↓

Text Message

↓

Backend

↓

AI

↓

Text Response

↓

Text-to-Speech

↓

Voice

Because every interaction becomes text internally, users can always review previous conversations.

The backend stores:

- Conversations
- Messages
- Sender
- Timestamp
- Metadata
- AI session ID returned by FastAPI `/chat`
- Structured AI response JSON such as recommendations, timeline, actions, memory updates, and tips

Current REST endpoint:

```json
POST /api/chat/
{
    "message": "Plan a cozy date night for Friday",
    "mode": "chat",
    "conversation_id": "optional-existing-conversation-uuid"
}
```

`mode=chat` returns text only.

`mode=speak` returns voice metadata. Premium users receive a `multipart/mixed` response containing JSON metadata plus raw Alfred MP3 audio generated from FastAPI `/voice/speak`. Free users receive JSON with `voice_agent=flutter_tts` and no audio payload.

Alternative cached-audio flow:

```http
POST /api/chat/cached-audio/
GET /api/chat/messages/{message_id}/audio/
```

`POST /api/chat/cached-audio/` always returns JSON. For premium `mode=speak`, Django generates Alfred audio during the request, stores the MP3 bytes in Redis temporarily, and returns `audio_url`. `GET /api/chat/messages/{message_id}/audio/` returns a normal `audio/mpeg` response. Audio expires after `ALFRED_CHAT_AUDIO_TTL_SECONDS`.

The frontend must use the exact returned `audio_url`, including its `token` query parameter. Tokenless or old audio URLs return `404` to avoid stale audio playback.

To continue a chat, clients send the backend `conversation_id` from the previous `/api/chat/` response. Clients should not manage or send the AI `session_id`; Django stores and reuses it internally while it is active.

AI chat responses include `session_status` from FastAPI: `new`, `active`, or `expired`. The backend must pass this through to clients so the frontend can show a "conversation context was lost, starting over" UI when the value is `expired`.

Generated audio is not stored in the database.

---

## Conversation Philosophy

Every conversation belongs to exactly one user.

A conversation contains many messages.

Each message represents one interaction.

Messages are never stored as one large JSON object.

Instead:

Conversation

↓

Many Message rows

This makes:

- Pagination easier
- Searching easier
- Analytics easier
- Future reactions easier
- Better performance

---

# 12. Voice Conversation

Voice is treated as a first-class feature.

The application is designed around real-time communication.

Voice conversations should feel natural and responsive.

The backend should minimize latency whenever possible.

Voice conversation flow:

User Speaks

↓

Flutter captures audio

↓

Speech-to-Text

↓

Backend

↓

AI

↓

Response

↓

Flutter Text-to-Speech

↓

User hears Alfred

The backend stores voice conversations as text.

Free users use frontend/local Flutter TTS.

Premium users can receive Alfred AI-generated voice. Django calls FastAPI `/voice/speak` only with the `reply` text from `/chat`, then returns the generated audio as raw MP3 in a `multipart/mixed` REST response.

Generated audio is never saved to the database.

---

# 13. WebSocket Architecture

WebSockets are deferred for the MVP.

The current implementation uses REST for chat and voice orchestration through `/api/chat/`.

REST remains responsible for CRUD operations.

Future WebSockets may handle real-time communication.

Responsibilities include:

- Voice conversation
- Live chat
- Streaming AI responses
- Typing indicators
- Live events
- Connection management

---

## WebSocket Flow

Connection

↓

JWT Authentication

↓

Join Conversation

↓

Receive User Message

↓

Persist User Message

↓

Call AI

↓

Receive AI Response

↓

Persist AI Response

↓

Return Response

↓

Continue Conversation

---

## WebSocket Events

The application communicates through structured JSON events.

Examples:

User Message

```json
{
    "type": "chat_message",
    "message": "Hello Alfred"
}
```

AI Typing

```json
{
    "type": "typing"
}
```

Streaming Response

```json
{
    "type": "stream",
    "content": "How can I help you today?"
}
```

Completed Response

```json
{
    "type": "complete"
}
```

Notification

```json
{
    "type": "notification"
}
```

Future event types may be added without changing the connection protocol.

---

# 14. Conversation Persistence

The backend owns every conversation.

Nothing is stored inside the AI service.

General flow:

Receive User Message

↓

Save User Message

↓

Load Previous Messages

↓

Prepare AI Context

↓

Call AI

↓

Receive AI Response

↓

Save AI Response

↓

Return Response

The backend always persists both sides of the conversation.

Even voice interactions become text records after Speech-to-Text conversion.

This allows:

- Conversation history
- Analytics
- AI memory
- Search
- Export
- Synchronization across devices

The AI service should never be responsible for storing conversation history.

---

# 15. AI Integration

The AI system is developed and maintained independently from the Django backend.

The backend communicates with the AI service through HTTP APIs.

The frontend **never communicates directly with the AI service**.

General communication:

```
Flutter
    │
    ▼
Django Backend
    │
    ▼
FastAPI AI
    │
    ▼
OpenAI / Anthropic / SERP API
```

---

## AI Design Philosophy

The AI service is intentionally designed to be **stateless**.

It should never:

- access PostgreSQL
- know Django models
- authenticate users
- check subscriptions
- manage notifications
- save conversations
- schedule plans

Instead, the AI receives only the information required to generate a response.

Example request:

```
User Information
Conversation History
User Preferences
Current Request
```

↓

AI

↓

Structured Response

---

## Backend Responsibilities

Before calling the AI service, Django should:

- Authenticate user
- Validate subscription
- Load conversation history
- Load user preferences
- Prepare AI context
- Call AI endpoint
- Save AI response
- Return response

---

## AI Responsibilities

The AI service performs:

- Conversation generation
- Restaurant recommendations
- Gift recommendations
- Date planning
- Travel suggestions
- Relationship coaching
- Intent detection
- Search
- LLM reasoning

No business logic should ever exist inside the AI service.

---

## Planned AI Endpoints

The current AI service exposes independent endpoints.

Examples:

```
POST /chat

POST /recommend

POST /plan-date

POST /gift

POST /coach

POST /travel

GET /health
```

The backend should treat every endpoint as an external service.

---

# 16. Plans & Calendar

One of Alfred's major features is helping users organize dates.

The backend owns every plan.

Plans may originate from:

- AI recommendations
- Manual creation
- Future integrations

The AI only suggests plans.

The backend decides whether they are stored.

---

## Plan Flow

User

↓

Ask Alfred

↓

AI Suggests Plan

↓

Frontend Displays Plan

↓

User Clicks Save

↓

Backend Creates Plan

↓

Calendar Updated

↓

Notification Scheduled

---

## Planned Features

Users can:

- Save plans
- View upcoming plans
- Edit plans
- Delete plans
- View completed plans
- View history

Future:

- Invite another user
- Google Calendar Sync
- Apple Calendar Sync
- Location reminders

---

## Calendar

The calendar is independent from AI.

Responsibilities:

- Upcoming events
- Scheduled dates
- Reminder scheduling
- Event history

The calendar should support future integrations without major redesign.

---

# 17. Notifications

The backend owns notifications.

Notifications may be created by:

- AI-generated plans
- Upcoming events
- System announcements
- Subscription updates
- Admin broadcasts

Current notification types include:

- In-app notifications


Notifications should always belong to a specific user.

---

# 18. Subscription System

The application supports Free and Premium users.

Premium users unlock additional AI capabilities.

Examples:

- Premium AI voice
- Extended conversations
- Future premium features

---

## Current Implementation

The MVP stores the active subscription state inside the User model.

Current fields include:

- subscription_plan
- subscription_start
- subscription_end

This allows quick permission checks throughout the application.

Example:

```
request.user.is_subscribed
```

---

## Future Implementation

Payment integration will introduce a dedicated `UserSubscription` model.

Responsibilities:

- Purchase history
- Renewal history
- Payment provider
- Transaction IDs
- Billing status
- Subscription history

The User model will continue storing only the currently active subscription state for quick authorization checks.

---

# 19. Admin Dashboard

A React-based Admin Dashboard is part of the MVP.

Administrators use the same authentication system with elevated Django permissions.

---

## Authentication

Administrators can:

- Login
- Logout
- Change Password
- Update Profile

---

## Dashboard

The dashboard provides:

- User statistics
- Active user statistics
- Subscription statistics
- Payment statistics
- System overview

Future:

- Revenue analytics
- User growth
- Daily active users
- Monthly reports

---

## User Management

Administrators can:

- View users
- Search users
- Filter users
- Retrieve user details

Future:

- Block users
- Unblock users
- Soft delete users

---

## Subscription Management

Administrators can:

- View subscriptions
- Retrieve subscription details

Future:

- Refund management
- Payment history
- Subscription cancellation
- Manual subscription adjustments

---

## Notifications

Administrators can:

- View notifications
- Mark notifications as read

Future:

- Broadcast notifications
- Push notification campaigns

---

## General Dashboard Features

Every list API should support:

- Server-side pagination
- Searching
- Filtering
- Ordering

The dashboard should never load complete datasets.

---

# 20. Django Applications

The backend follows a feature-based architecture.

Current application responsibilities are intentionally separated.

---

## users

Responsible for:

- User model
- User profile
- Authentication provider
- Device token
- Subscription state
- User-related serializers
- User services

---

## chat

Responsible for:

- Conversations
- Messages
- WebSocket consumers
- Voice sessions
- Chat APIs
- Conversation persistence

---

## ai_gateway

Responsible for:

- AI HTTP communication
- Payload preparation
- AI response handling
- Error handling

No database models belong here.

No AI reasoning belongs here.

---

## plans

Responsible for:

- Date plans
- Saved recommendations
- Plan management

---

## calendar

Responsible for:

- Calendar events
- Scheduling
- Event retrieval
- Reminder integration

---

## notifications

Responsible for:

- User notifications
- Notification APIs
- Notification services

---

## subscriptions

Responsible for:

Current:

- Subscription validation

Future:

- UserSubscription model
- Payment providers
- Billing logic
- Purchase history

---

## api

Shared API utilities.

Only generic functionality should live here.

Business logic should never live inside the api application.

---

# 21. API Design Guidelines

The backend exposes REST APIs for standard CRUD operations and WebSockets for real-time communication.

## API Versioning

All REST APIs should be simple.

Example:

```
/api/
```

Future versions should never break existing clients unnecessarily.

---

## API Naming

Use resource-based endpoints.

Examples:

```
/api/users/
/api/chat/
/api/plans/
/api/calendar/
/api/notifications/
/api/subscriptions/
```

Avoid action-based endpoints unless absolutely necessary.

---

## HTTP Methods

Use standard REST conventions.

GET

- Retrieve data

POST

- Create resources

PUT

- Replace resources

PATCH

- Partial update

DELETE

- Delete resources

---

## Response Format

Successful responses should be consistent throughout the project.

Example:

```json
{
    "success": true,
    "message": "Profile updated successfully.",
    "data": {}
}
```

Failed responses:

```json
{
    "success": false,
    "message": "Validation failed.",
    "errors": {}
}
```

---

## Pagination

Every list endpoint must support pagination.

Examples:

- Users
- Conversations
- Messages
- Plans
- Notifications
- Subscriptions

Never return unbounded datasets.

---

## Searching

When applicable, APIs should support searching.

---

## Filtering

When applicable, APIs should support filtering.

---

## Ordering

When applicable, APIs should support ordering.

---

# 22. Coding Standards

The project prioritizes readability and maintainability over clever implementations.

---

## General Principles

Always write production-quality code.

Prefer explicit code over implicit behavior.

Avoid unnecessary abstractions.

Keep the codebase beginner-friendly while remaining scalable.

---

## Django

Follow Django best practices.

Views should remain thin.

Business logic belongs inside services.

Serializers should validate data only.

Permissions should contain authorization logic only.

Avoid placing business logic inside serializers whenever possible.

---

## Services

The service layer should contain:

- Business logic
- External API communication
- Complex database operations
- Transactions

Views should simply call services.

---

## Models

Models should contain:

- Fields
- Relationships
- Simple helper methods

Avoid placing application logic inside models.

---

## Queries

Optimize whenever possible.

Use:

- select_related()
- prefetch_related()

Avoid N+1 queries.

---

## Documentation

Every public API should appear in Swagger documentation.

Complex services should contain clear comments.

---

## Code Style

Use:

- descriptive names
- meaningful variables
- small functions
- reusable helpers
- type hints whenever practical

Follow:

- PEP 8
- Django conventions
- DRF conventions

---

# 23. Architectural Decisions

The following decisions are intentional.

AI coding assistants should preserve them unless explicitly instructed otherwise.

---

## User Model

The project intentionally keeps onboarding fields inside the User model.

A separate Profile model is not currently planned.

---

## AI

The AI service is stateless.

The backend owns all business logic.

---

## Database

UUID is used for primary keys.

---

## Authentication

Authentication uses email instead of username.

---

## Voice

Voice is a first-class feature.

The backend architecture should always prioritize real-time communication.

---

## Communication

REST is used for CRUD.

WebSockets are used for real-time communication.

---

## Backend

The backend is the single source of truth.

The AI service should never own application state.

---

## Architecture

Feature-based Django architecture is preferred.

Business logic belongs inside services.

---

## Admin

Administrators use Django's permission system.

No custom role model currently exists.

---

# 24. Development Roadmap

Development is planned in phases.

---

## Phase 1

Core Foundation

- User Authentication
- JWT
- User Management
- Swagger
- Google Sign-In
- Apple Sign-In
- Notifications

---

## Phase 2

Conversation System

- WebSockets
- Django Channels
- Redis
- Chat
- Conversation Persistence
- AI Gateway

---

## Phase 3

Planning Features

- Plans
- Calendar

---

## Phase 4

Admin Dashboard

- Authentication
- Statistics
- User Management
- Subscription Management
- Notification Management
- Analytics Dashboard
- Revenue Dashboard

---

## Phase 5

Premium Features

- Payment Integration
- UserSubscription
- Premium AI Features
- Premium AI Voice
- ElevenLabs Integration

---

## Phase 6

Optimization

- Celery
- Background Workers
- Analytics
- Monitoring
- Redis Cache
- Performance Improvements

---

# 25. Future Improvements

Possible future enhancements include:

- Google Calendar Sync
- Apple Calendar Sync
- Push Notifications
- Email Notifications
- Conversation Search
- Conversation Export
- Multi-device Support
- Recommendation History
- AI Personalization
- Feature Flags
- Soft Deletes
- Audit Logs

These items are not part of the immediate MVP unless explicitly prioritized.

---

# 26. Instructions for AI Coding Assistants

Before writing code:

- Read this document completely.
- Follow the existing architecture.
- Preserve consistency.
- Prefer extending existing components over introducing new abstractions.
- Do not redesign the system unless explicitly instructed.

Always assume the existing architecture is intentional.

---

## When Implementing New Features

Unless instructed otherwise, follow this workflow:

1. Create or update Model
2. Create Migration
3. Create Serializer
4. Create Service
5. Create Permission
6. Create View
7. Create URL
8. Register Admin
9. Document Swagger
10. Verify Pagination, Search, Filtering, and Ordering where applicable

---

## Before Changing Existing Code

Ask yourself:

- Does similar functionality already exist?
- Can I reuse existing services?
- Will this break existing APIs?
- Does this follow the feature-based architecture?

---

## Never Do These

Do not:

- Introduce unnecessary abstractions.
- Create duplicate services.
- Place business logic inside views.
- Place AI logic inside Django.
- Bypass the service layer.
- Change database architecture without approval.
- Break public APIs without discussion.

---

## Development Philosophy

The project values:

- Simplicity
- Readability
- Maintainability
- Scalability
- Consistency

Favor clean, understandable code over overly clever implementations.

When in doubt, choose the simpler solution that aligns with the existing architecture.

---

## Final Note

This document is the primary source of truth for the Alfred backend.

Future architectural decisions, implementation details, and project evolution should be reflected here so that every contributor—human or AI—shares the same understanding of the system.
