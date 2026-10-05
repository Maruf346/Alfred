# PROMPTS.md

# Alfred - AI Dating Concierge
## Reusable Development Prompts

This document contains reusable prompts for AI coding assistants working on the Alfred backend.

These prompts help maintain consistency across development sessions.

---

# General Instruction

Before completing any task:

- Read `AGENTS.md`
- Read `PROJECT_CONTEXT.md`
- Follow the existing architecture.
- Preserve consistency.
- Do not redesign the project unless explicitly instructed.

---

# New Django App

Prompt:

> Create a new Django application following the project's feature-based architecture.
>
> The app should include:
>
> - models.py
> - serializers.py
> - services.py
> - permissions.py
> - views.py
> - urls.py
> - admin.py
> - tasks.py (if needed)
> - tests.py (optional for MVP)
>
> Follow existing naming conventions.
>
> Keep views thin.
>
> Place business logic inside services.

---

# New Model

Prompt:

> Create the Django model following project conventions.
>
> Requirements:
>
> - UUID primary key
> - created_at
> - updated_at
> - proper verbose names
> - proper Meta class
> - meaningful __str__()
> - indexes where appropriate
> - clean relationships
>
> Do not over-engineer.

---

# CRUD API

Prompt:

> Implement a complete CRUD API.
>
> Include:
>
> - serializers
> - services
> - permissions
> - views
> - urls
> - Swagger documentation
>
> Use pagination.
>
> Add filtering and searching where applicable.
>
> Keep business logic inside services.

---

# WebSocket Feature

Prompt:

> Implement a Django Channels WebSocket feature.
>
> Requirements:
>
> - JWT authentication
> - clean consumer
> - proper event handling
> - error handling
> - Redis compatible
> - scalable architecture
>
> Do not place business logic inside the consumer.

---

# AI Integration

Prompt:

> Implement backend communication with the FastAPI AI service.
>
> The backend should:
>
> - prepare payload
> - validate user
> - validate subscription
> - load conversation history
> - call AI endpoint
> - process response
> - persist AI response
>
> Do not implement AI reasoning inside Django.

---

# API Integration

Prompt:

> Integrate an external REST API.
>
> Use:
>
> - service layer
> - proper exception handling
> - configurable timeout
> - environment variables
> - reusable client
> - logging
>
> Never call external APIs directly from views.

---

# Serializer

Prompt:

> Create clean DRF serializers.
>
> Validation belongs here.
>
> Business logic does not.

---

# Service Layer

Prompt:

> Implement business logic inside services.
>
> Services should:
>
> - be reusable
> - be testable
> - avoid duplicated logic
> - contain database operations
> - contain transactions when necessary
>
> Views should simply call services.

---

# Permission

Prompt:

> Implement DRF permissions.
>
> Keep authorization logic inside permission classes.
>
> Do not duplicate permission checks inside views.

---

# Pagination

Prompt:

> Every list endpoint should support:
>
> - server-side pagination
> - searching
> - filtering
> - ordering
>
> Never return unbounded datasets.

---

# Performance Optimization

Prompt:

> Before finalizing implementation:
>
> - check for N+1 queries
> - use select_related()
> - use prefetch_related()
> - avoid duplicate database hits
> - optimize queryset usage

---

# Code Review

Prompt:

> Review this code as a senior Django backend engineer.
>
> Look for:
>
> - architecture violations
> - business logic inside views
> - duplicated code
> - performance issues
> - security concerns
> - scalability
> - readability
> - Django best practices
>
> Suggest improvements before writing code.

---

# Refactoring

Prompt:

> Refactor the code without changing functionality.
>
> Goals:
>
> - improve readability
> - improve maintainability
> - remove duplication
> - preserve APIs
> - preserve architecture

---

# Database Changes

Prompt:

> Before modifying any model:
>
> Explain:
>
> - why the change is needed
> - migration impact
> - backward compatibility
> - possible risks
>
> Wait for approval before making architectural changes.

---

# Documentation

Prompt:

> After implementing a feature:
>
> - update README if necessary
> - update PROJECT_CONTEXT.md if architecture changed
> - explain important implementation decisions
> - document new APIs

---

# Commit Message

Prompt:

> Generate a Conventional Commit message.
>
> Examples:
>
> feat(chat): add websocket conversation support
>
> fix(users): resolve profile update validation
>
> refactor(ai): move AI client into service layer
>
> docs(readme): update backend architecture

---

# Pull Request

Prompt:

> Generate a pull request description including:
>
> - Summary
> - Changes
> - Database Changes
> - Breaking Changes
> - Testing
> - Future Improvements

---

# Final Verification

Before considering any task complete, verify:

- Architecture consistency
- Business logic placement
- Service layer usage
- API consistency
- Error handling
- Permissions
- Swagger documentation
- Performance
- Readability
- Maintainability

If any of these fail, improve the implementation before finishing.