# Alfred AI Service Integration Guide for Django Backend

## 1. Purpose of This Document
This document is a backend handoff for Django developers integrating with the Alfred AI service.
It explains:
- Why each API exists
- Which fields are required vs optional
- What data Django should send now vs later
- How to design clean backend code for reliability and maintainability
- What responses mean and how to handle errors

This guide is written so both humans and AI code assistants can use it as a reliable implementation reference.

## 2. Service Overview
Alfred AI is a stateless AI service that your Django backend calls over HTTP.

Key principles:
- Frontend should not call Alfred directly in production
- Django backend owns user identity, auth, business rules, persistence
- Alfred receives context and returns structured intelligence
- Alfred does not mutate your database directly

Current LAN base URL:
- http://10.10.28.170:8000

Docs:
- http://10.10.28.170:8000/docs

OpenAPI:
- http://10.10.28.170:8000/openapi.json

## 3. Authentication and Environment Behavior
### Development mode
When ENV is development and REQUIRE_SERVICE_API_KEY_IN_DEV is false in Alfred service:
- X-API-Key is not required

### Production mode
When Alfred runs in production mode:
- Django must send header X-API-Key: <AI_SERVICE_API_KEY>

Recommendation for Django:
- Always send X-API-Key from Django settings in all environments
- That keeps behavior consistent between dev/staging/prod

## 4. Endpoint Catalog

## 4.0 Quick Reference: Required and Optional Fields + Real Examples

This section is a fast scan for backend developers. Detailed endpoint explanations remain below.

| API | Required Fields | Optional Fields |
| --- | --- | --- |
| GET /health | None | None |
| POST /chat | message | conversation_id, memory, location, calendar, budget, conversation_history, subscription_status |
| POST /recommend | category, location | budget, memory, preferences |
| POST /plan-date | location | budget, memory, calendar, date_type, preferences |
| POST /coach | topic | message, memory, conversation_history |
| POST /gift | None | occasion, budget, memory, location |
| POST /travel | origin, destination, start_date, end_date | budget, memory, preferences |
| POST /budget/analyze | None | currency, current_budget, expenses_text, previous_month_expenses, file_base64, file_type, notes, memory |
| POST /budget/analyze/upload | file (UploadFile) | currency, current_budget, notes |

### Real Request/Response Examples (Copy-Paste)

### GET /health
Request:
~~~http
GET /health
~~~

Response:
~~~json
{
  "status": "ok",
  "service": "Alfred AI Concierge",
  "env": "development",
  "llm_provider": "anthropic"
}
~~~

### POST /chat
Request:
~~~json
{
  "message": "Plan a cozy date night for Friday"
}
~~~

Response:
~~~json
{
  "reply": "Great plan. Do you prefer rooftop or indoor seating?",
  "intent": "date_planning",
  "confidence": 0.9,
  "actions": [],
  "recommendations": [],
  "memory_updates": []
}
~~~

### POST /recommend
Request:
~~~json
{
  "category": "restaurant",
  "location": "Bangalore",
  "budget": 2500,
  "preferences": "rooftop, romantic",
  "memory": {
    "partner_name": "Riya",
    "favorite_food": "Italian"
  }
}
~~~

Response:
~~~json
{
  "recommendations": [
    {
      "name": "Olive Beach",
      "category": "restaurant",
      "rating": 4.6,
      "price_level": "$$$",
      "address": "Wood St, Bengaluru",
      "url": "https://example.com",
      "reason": "Matches romantic preference and budget",
      "source": "serpapi"
    }
  ],
  "reply": "Here are the strongest restaurant options for your date plan.",
  "confidence": 0.87
}
~~~

### POST /plan-date
Request:
~~~json
{
  "location": "Pune",
  "budget": 2000,
  "date_type": "anniversary",
  "preferences": "quiet indoor places",
  "memory": {
    "partner_name": "Meera",
    "favorite_food": "Thai"
  }
}
~~~

Response:
~~~json
{
  "reply": "Here is a relaxed anniversary plan in Pune.",
  "timeline": [
    {
      "time": "18:30",
      "activity": "Sunset walk",
      "location": "Koregaon Park",
      "notes": "Start with a light walk"
    }
  ],
  "restaurant": null,
  "activity": null,
  "estimated_cost": 1800,
  "travel_notes": "Cab recommended due evening traffic",
  "actions": [],
  "memory_updates": [],
  "confidence": 0.83
}
~~~

### POST /coach
Request:
~~~json
{
  "topic": "texting_advice",
  "message": "She replied after two days. What should I send now?",
  "memory": {
    "relationship_status": "dating"
  }
}
~~~

Response:
~~~json
{
  "reply": "Keep it calm and warm; avoid sounding reactive.",
  "tips": [
    "Acknowledge her response naturally",
    "Ask one easy follow-up question",
    "Avoid pressure or double texting"
  ],
  "confidence": 0.88
}
~~~

### POST /gift
Request:
~~~json
{
  "occasion": "birthday",
  "budget": 4000,
  "location": "Delhi",
  "memory": {
    "partner_name": "Aisha",
    "favorite_activity": "reading"
  }
}
~~~

Response:
~~~json
{
  "reply": "Here are thoughtful birthday options for Aisha.",
  "recommendations": [
    {
      "name": "Personalized leather bookmark set",
      "category": "gift",
      "rating": null,
      "price_level": "$$",
      "address": null,
      "url": null,
      "reason": "Matches reading preference and budget",
      "source": "general_advice"
    }
  ],
  "confidence": 0.8,
  "memory_updates": []
}
~~~

### POST /travel
Request:
~~~json
{
  "origin": "Mumbai",
  "destination": "Goa",
  "start_date": "2026-08-14",
  "end_date": "2026-08-17",
  "budget": 25000,
  "preferences": "beachside, relaxed"
}
~~~

Response:
~~~json
{
  "reply": "Here is a balanced Goa weekend plan.",
  "flights": [],
  "hotels": [],
  "activities": [],
  "estimated_cost": 22000,
  "actions": [
    {
      "action": "search_flights",
      "payload": {
        "origin": "Mumbai",
        "destination": "Goa"
      }
    }
  ],
  "confidence": 0.81
}
~~~

## 4.1 GET /health
### Purpose
Health check for service readiness and basic runtime metadata.

### Request
- Method: GET
- Body: none

### Response example
~~~json
{
  "status": "ok",
  "service": "Alfred AI Concierge",
  "env": "development",
  "llm_provider": "anthropic"
}
~~~

### Django use case
- Startup health probe
- Monitoring job
- Circuit-breaker readiness check

---

## 4.2 POST /chat
### Purpose
Primary conversational endpoint. Detects intent and generates structured AI output.

### Minimum required request
Only message is required.

~~~json
{
  "message": "Plan a cozy date night for Friday"
}
~~~

### Optional context fields (recommended in production)
- conversation_id: string
- memory: object
- location: object
- calendar: array
- budget: number
- conversation_history: array
- subscription_status: string

### Full request example
~~~json
{
  "message": "Plan a romantic date this weekend",
  "conversation_id": "conv_10293",
  "memory": {
    "partner_name": "Ananya",
    "favorite_food": "Italian",
    "budget": 3000
  },
  "location": {
    "city": "Mumbai",
    "country": "India",
    "latitude": 19.076,
    "longitude": 72.8777
  },
  "calendar": [
    {
      "title": "Office call",
      "date": "2026-07-12",
      "time": "18:00",
      "notes": "Can shift by 30 minutes"
    }
  ],
  "budget": 3000,
  "conversation_history": [
    {
      "role": "user",
      "content": "She likes quiet places"
    },
    {
      "role": "assistant",
      "content": "Noted, should I focus on rooftop venues?"
    }
  ],
  "subscription_status": "premium"
}
~~~

### Response meaning
- reply: AI text to show to user
- intent: classified intent label
- confidence: confidence score 0 to 1
- actions: backend-action suggestions (not auto-executed)
- recommendations: optional recommendation list
- memory_updates: key/value suggestions backend may persist

### Response example
~~~json
{
  "reply": "Since Ananya enjoys Italian food, I suggest a quiet candlelight dinner in Bandra. Do you prefer rooftop or indoor seating?",
  "intent": "date_planning",
  "confidence": 0.91,
  "actions": [
    {
      "action": "search_restaurants",
      "payload": {
        "location": "Mumbai",
        "vibe": "quiet,candlelight"
      }
    }
  ],
  "recommendations": [],
  "memory_updates": [
    {
      "key": "preferred_vibe",
      "value": "quiet"
    }
  ]
}
~~~

---

## 4.3 POST /recommend
### Purpose
Returns ranked recommendations based on category, location, and context.

### Required fields
- category: restaurant | activity | gift | hotel
- location: string

### Optional fields
- budget
- memory
- preferences

### Request example
~~~json
{
  "category": "restaurant",
  "location": "Bangalore",
  "budget": 2500,
  "preferences": "rooftop, romantic, live music",
  "memory": {
    "partner_name": "Riya",
    "favorite_food": "Italian"
  }
}
~~~

### Response example
~~~json
{
  "recommendations": [
    {
      "name": "Olive Beach",
      "category": "restaurant",
      "rating": 4.6,
      "price_level": "$$$",
      "address": "Wood St, Bengaluru",
      "url": "https://example.com",
      "reason": "Matches romantic preference and budget",
      "source": "serpapi"
    }
  ],
  "reply": "Here are the strongest restaurant options for your date plan.",
  "confidence": 0.87
}
~~~

---

## 4.4 POST /plan-date
### Purpose
Creates a structured date plan timeline from context + optional search results.

### Required fields
- location

### Optional fields
- budget
- memory
- calendar
- date_type
- preferences

### Request example
~~~json
{
  "location": "Pune",
  "budget": 2000,
  "date_type": "anniversary",
  "preferences": "quiet indoor places",
  "memory": {
    "partner_name": "Meera",
    "favorite_food": "Thai"
  }
}
~~~

### Response example
~~~json
{
  "reply": "Here is a relaxed anniversary plan in Pune.",
  "timeline": [
    {
      "time": "18:30",
      "activity": "Sunset walk",
      "location": "Koregaon Park",
      "notes": "Start with a light walk"
    },
    {
      "time": "20:00",
      "activity": "Dinner",
      "location": "Thai shortlist",
      "notes": "Reserve seating in advance"
    }
  ],
  "restaurant": null,
  "activity": null,
  "estimated_cost": 1800,
  "travel_notes": "Cab recommended due evening traffic",
  "actions": [],
  "memory_updates": [],
  "confidence": 0.83
}
~~~

---

## 4.5 POST /coach
### Purpose
Relationship and dating coaching suggestions.

### Required field
- topic: first_date | second_date | texting_advice | relationship_advice | conversation_starters

### Optional fields
- message
- memory
- conversation_history

### Request example
~~~json
{
  "topic": "texting_advice",
  "message": "She replied after two days. What should I send now?",
  "memory": {
    "relationship_status": "dating"
  }
}
~~~

### Response example
~~~json
{
  "reply": "Keep it calm and warm; avoid sounding reactive.",
  "tips": [
    "Acknowledge her response naturally",
    "Ask one easy follow-up question",
    "Avoid pressure or double texting"
  ],
  "confidence": 0.88
}
~~~

---

## 4.6 POST /gift
### Purpose
Generates gift suggestions from occasion, budget, location, and memory.

### Required fields
- none

### Optional fields
- occasion
- budget
- memory
- location

### Request example
~~~json
{
  "occasion": "birthday",
  "budget": 4000,
  "location": "Delhi",
  "memory": {
    "partner_name": "Aisha",
    "favorite_activity": "reading"
  }
}
~~~

### Response example
~~~json
{
  "reply": "Here are thoughtful birthday options for Aisha.",
  "recommendations": [
    {
      "name": "Personalized leather bookmark set",
      "category": "gift",
      "rating": null,
      "price_level": "$$",
      "address": null,
      "url": null,
      "reason": "Matches reading preference and budget",
      "source": "general_advice"
    }
  ],
  "confidence": 0.8,
  "memory_updates": []
}
~~~

---

## 4.7 POST /travel
### Purpose
Travel planning for flights, hotels, and activities.

### Required fields
- origin
- destination
- start_date
- end_date

### Optional fields
- budget
- memory
- preferences

### Request example
~~~json
{
  "origin": "Mumbai",
  "destination": "Goa",
  "start_date": "2026-08-14",
  "end_date": "2026-08-17",
  "budget": 25000,
  "preferences": "beachside, relaxed"
}
~~~

### Response example
~~~json
{
  "reply": "Here is a balanced Goa weekend plan.",
  "flights": [],
  "hotels": [],
  "activities": [],
  "estimated_cost": 22000,
  "actions": [
    {
      "action": "search_flights",
      "payload": {
        "origin": "Mumbai",
        "destination": "Goa"
      }
    }
  ],
  "confidence": 0.81
}
~~~

---

## 4.8 POST /budget/analyze and POST /budget/analyze/upload
### Purpose
Analyzes receipt images, PDF documents, or itemized expense text. Calculates category cost breakdowns, identifies spending patterns & major expense areas, and generates an estimated next-month budget plan with suggested category allocations.

### JSON Request Example (`POST /budget/analyze`)
~~~json
{
  "currency": "USD",
  "current_budget": 1000.0,
  "previous_month_expenses": [
    {"category": "Groceries", "amount": 320.50, "merchant": "Walmart", "date": "2026-08-05"},
    {"category": "Utilities", "amount": 150.00, "merchant": "Electric Co", "date": "2026-08-10"},
    {"category": "Dining Out", "amount": 210.00, "merchant": "Local Restaurants", "date": "2026-08-15"}
  ],
  "notes": "Goal is to save 15% next month"
}
~~~

### Multipart Upload Request (`POST /budget/analyze/upload`)
Header: `Content-Type: multipart/form-data`
Form Fields:
- `file`: (binary receipt image PNG/JPEG/WEBP or PDF file)
- `currency`: "USD"
- `current_budget`: 1000.0
- `notes`: "Monthly grocery receipt"

### Response Example
~~~json
{
  "reply": "Here is your previous month's expense analysis and next month spending plan.",
  "receipt_summary": {
    "total_expense": 680.50,
    "currency": "USD",
    "item_count": 3,
    "period_detected": "August 2026",
    "merchant_names": ["Walmart", "Electric Co", "Local Restaurants"]
  },
  "analyzed_expenses": [
    {"category": "Groceries", "amount": 320.50, "merchant": "Walmart", "date": "2026-08-05"},
    {"category": "Utilities", "amount": 150.00, "merchant": "Electric Co", "date": "2026-08-10"},
    {"category": "Dining Out", "amount": 210.00, "merchant": "Local Restaurants", "date": "2026-08-15"}
  ],
  "spending_breakdown": [
    {"category": "Groceries", "total_amount": 320.50, "percentage": 47.1, "expense_count": 1},
    {"category": "Dining Out", "total_amount": 210.00, "percentage": 30.9, "expense_count": 1},
    {"category": "Utilities", "total_amount": 150.00, "percentage": 22.0, "expense_count": 1}
  ],
  "major_expense_areas": [
    "Groceries (47.1% of spending)",
    "Dining Out (30.9% of spending)"
  ],
  "spending_patterns": [
    "High proportion of dining out expenditures"
  ],
  "insights_and_recommendations": [
    "Meal planning on weekends can reduce dining out expenses by up to 25%"
  ],
  "next_month_plan": {
    "estimated_total_budget": 580.00,
    "currency": "USD",
    "projected_savings": 100.50,
    "suggested_allocations": [
      {"category": "Groceries", "recommended_amount": 300.00, "notes": "Bulk purchasing"},
      {"category": "Dining Out", "recommended_amount": 140.00, "notes": "Reduced eating out frequency"},
      {"category": "Utilities", "recommended_amount": 140.00, "notes": "Standard monthly estimate"}
    ],
    "planner_tips": [
      "Set weekly dining out cap at $35"
    ]
  },
  "confidence": 0.94,
  "actions": [
    {
      "action": "save_budget_plan",
      "payload": {
        "estimated_total_budget": 580.00,
        "currency": "USD"
      }
    }
  ],
  "memory_updates": [
    {"key": "last_analyzed_monthly_spending", "value": 680.50},
    {"key": "recommended_next_month_budget", "value": 580.00}
  ]
}
~~~

## 5. Data Ownership and Variable Mapping Strategy
Django should assemble Alfred payloads from your own source-of-truth systems.

### Recommended source mapping for /chat
- message: latest user message from request
- conversation_id: chat thread id from your chat model
- memory: user profile or partner preference table
- location: user profile location or most recent location service
- calendar: upcoming events from your calendar table
- budget: explicit user budget setting or session-level budget
- conversation_history: last N turns from conversation table
- subscription_status: active plan from billing/subscription table

## 6. Django Implementation Pattern
Use a dedicated service layer in Django, not direct calls from views.

Example structure:
- apps/ai_client/client.py
- apps/ai_client/schemas.py
- apps/chat/services.py
- apps/chat/views.py

### Example Django settings
~~~python
# settings.py
ALFRED_BASE_URL = env("ALFRED_BASE_URL", default="http://10.10.28.170:8000")
ALFRED_API_KEY = env("ALFRED_API_KEY", default="")
ALFRED_TIMEOUT_SECONDS = env.int("ALFRED_TIMEOUT_SECONDS", default=20)
~~~

### Example client helper
~~~python
# apps/ai_client/client.py
import httpx
from django.conf import settings

class AlfredClient:
    def __init__(self):
        self.base_url = settings.ALFRED_BASE_URL.rstrip("/")
        self.timeout = settings.ALFRED_TIMEOUT_SECONDS
        self.api_key = settings.ALFRED_API_KEY

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
~~~

### Example chat orchestration service
~~~python
# apps/chat/services.py
from apps.ai_client.client import AlfredClient


def call_alfred_chat(user, message: str, conversation_id: str | None = None) -> dict:
    payload = {
        "message": message,
        "conversation_id": conversation_id,
        "memory": {
            "partner_name": getattr(user.profile, "partner_name", None),
            "favorite_food": getattr(user.profile, "favorite_food", None),
            "budget": getattr(user.profile, "budget", None),
        },
        "location": {
            "city": getattr(user.profile, "city", None),
            "country": getattr(user.profile, "country", None),
        },
        "subscription_status": getattr(user.profile, "subscription_status", None),
    }

    # Remove None values to keep payload clean
    payload = {k: v for k, v in payload.items() if v is not None}

    client = AlfredClient()
    return client.post("/chat", payload)
~~~

### Example DRF view
~~~python
# apps/chat/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.chat.services import call_alfred_chat


class ChatAssistantView(APIView):
    def post(self, request):
        message = request.data.get("message", "").strip()
        if not message:
            return Response({"detail": "message is required"}, status=status.HTTP_400_BAD_REQUEST)

        data = call_alfred_chat(
            user=request.user,
            message=message,
            conversation_id=request.data.get("conversation_id"),
        )
        return Response(data, status=status.HTTP_200_OK)
~~~

## 7. Error Handling Contract
Handle these classes of errors in Django:
- 401 Unauthorized: missing or wrong X-API-Key in production
- 422 Validation error: invalid enums, missing required fields
- 502 Upstream/provider issue: AI/search provider unavailable
- Network timeout/connection error: retry with backoff

### Recommended retry strategy
- Retry only on network errors and 5xx responses
- Do not retry on 4xx validation/auth errors
- Use exponential backoff with jitter
- Keep max total latency bounded for user experience

## 8. Observability and Logging
Django should log:
- request_id or correlation_id
- endpoint called
- latency_ms
- status_code
- timeout/retry counts

Do not log:
- API keys
- raw private user data
- full conversation text in plain logs in production

## 9. Rollout Plan
### Phase 1 (immediate)
- Integrate /chat with only message

### Phase 2
- Add conversation_id, memory, location, budget

### Phase 3
- Add conversation_history and calendar
- Integrate /recommend, /plan-date, /gift, /travel where needed

### Phase 4
- Enable strict production auth and monitoring
- Add retries/circuit-breaker and dashboard metrics

## 10. Final Integration Checklist
- Base URL configured in Django settings
- X-API-Key configured and sent from backend
- Timeout configured
- Structured error handling implemented
- Minimal /chat call working
- Optional context enrichment enabled
- Monitoring and logs in place

This contract is aligned with the currently running Alfred AI service implementation.
