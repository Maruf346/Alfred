import io
import pytest


def test_budget_analyze_structured_expenses(client, auth_headers, fake_llm):
    fake_llm.queue({
        "reply": "Here is your monthly expense breakdown and recommended spending plan for next month.",
        "receipt_summary": {
            "total_expense": 530.50,
            "currency": "USD",
            "item_count": 2,
            "period_detected": "August 2026",
            "merchant_names": ["Walmart", "Electric Co"]
        },
        "analyzed_expenses": [
            {"category": "Groceries", "amount": 380.50, "merchant": "Walmart", "date": "2026-08-05", "notes": "Weekly restock"},
            {"category": "Utilities", "amount": 150.00, "merchant": "Electric Co", "date": "2026-08-10", "notes": "Electric bill"}
        ],
        "spending_breakdown": [
            {"category": "Groceries", "total_amount": 380.50, "percentage": 71.7, "expense_count": 1},
            {"category": "Utilities", "total_amount": 150.00, "percentage": 28.3, "expense_count": 1}
        ],
        "major_expense_areas": ["Groceries (71.7%)"],
        "spending_patterns": ["High grocery expenditure at the beginning of the month"],
        "insights_and_recommendations": ["Buy non-perishables in bulk to save around 10%"],
        "next_month_plan": {
            "estimated_total_budget": 500.00,
            "currency": "USD",
            "projected_savings": 30.50,
            "suggested_allocations": [
                {"category": "Groceries", "recommended_amount": 340.00, "notes": "Optimized bulk purchase"},
                {"category": "Utilities", "recommended_amount": 140.00, "notes": "Energy saving plan"}
            ],
            "planner_tips": ["Track weekly grocery spend against target"]
        },
        "confidence": 0.95,
        "actions": [
            {"action": "save_budget_plan", "payload": {"estimated_total_budget": 500.00}}
        ],
        "memory_updates": [
            {"key": "last_analyzed_monthly_spending", "value": 530.50}
        ]
    })

    resp = client.post(
        "/budget/analyze",
        json={
            "currency": "USD",
            "current_budget": 600.0,
            "previous_month_expenses": [
                {"category": "Groceries", "amount": 380.50, "merchant": "Walmart", "date": "2026-08-05"},
                {"category": "Utilities", "amount": 150.00, "merchant": "Electric Co", "date": "2026-08-10"}
            ],
            "notes": "Reduce grocery spend"
        },
        headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["receipt_summary"]["total_expense"] == 530.50
    assert len(body["analyzed_expenses"]) == 2
    assert body["next_month_plan"]["estimated_total_budget"] == 500.00
    assert len(body["spending_breakdown"]) == 2


def test_budget_analyze_upload_receipt_image(client, auth_headers, fake_llm):
    fake_llm.queue({
        "reply": "Successfully parsed store receipt and generated next month budget plan.",
        "receipt_summary": {
            "total_expense": 85.20,
            "currency": "USD",
            "item_count": 5,
            "period_detected": "September 2026",
            "merchant_names": ["Target"]
        },
        "analyzed_expenses": [
            {"category": "Household", "amount": 85.20, "merchant": "Target", "date": "2026-09-02"}
        ],
        "spending_breakdown": [
            {"category": "Household", "total_amount": 85.20, "percentage": 100.0, "expense_count": 1}
        ],
        "major_expense_areas": ["Household essentials"],
        "spending_patterns": ["Single store transaction"],
        "insights_and_recommendations": ["Look out for Target rewards discounts"],
        "next_month_plan": {
            "estimated_total_budget": 80.00,
            "currency": "USD",
            "projected_savings": 5.20,
            "suggested_allocations": [
                {"category": "Household", "recommended_amount": 80.00, "notes": "Use store points"}
            ],
            "planner_tips": ["Utilize cashback apps"]
        },
        "confidence": 0.92,
        "actions": [],
        "memory_updates": []
    })

    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    files = {"file": ("receipt.png", io.BytesIO(file_content), "image/png")}
    data = {"currency": "USD", "current_budget": "100.0", "notes": "Uploaded Target receipt"}

    resp = client.post(
        "/budget/analyze/upload",
        files=files,
        data=data,
        headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["receipt_summary"]["merchant_names"] == ["Target"]
    assert body["receipt_summary"]["total_expense"] == 85.20
    assert body["confidence"] == 0.92


def test_budget_upload_unsupported_file_type(client, auth_headers):
    file_content = b"random executable content"
    files = {"file": ("malicious.exe", io.BytesIO(file_content), "application/x-msdownload")}
    resp = client.post("/budget/analyze/upload", files=files, headers=auth_headers)
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_budget_upload_empty_file(client, auth_headers):
    files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
    resp = client.post("/budget/analyze/upload", files=files, headers=auth_headers)
    assert resp.status_code == 400
    assert "Uploaded file is empty" in resp.json()["detail"]


def test_budget_upload_encrypted_pdf(client, auth_headers):
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Encrypt 2 0 R >>\nendobj"
    files = {"file": ("bank_statement.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    resp = client.post("/budget/analyze/upload", files=files, headers=auth_headers)
    assert resp.status_code == 400
    assert "password-protected" in resp.json()["detail"]


def test_budget_analyze_deduplicates_overlapping_transactions(client, auth_headers, fake_llm):
    fake_llm.queue({
        "reply": "Parsed Chase statement and deduplicated overlapping transactions.",
        "receipt_summary": {
            "total_expense": 50.00,
            "currency": "USD",
            "item_count": 3,
            "bank_name_detected": "Chase Bank",
            "date_range_detected": "Aug 1 - Aug 31, 2026",
            "merchant_names": ["Starbucks", "Uber"]
        },
        "analyzed_expenses": [
            {"category": "Dining", "amount": 10.00, "merchant": "Starbucks", "date": "2026-08-01"},
            {"category": "Dining", "amount": 10.00, "merchant": "Starbucks", "date": "2026-08-01"},  # duplicate
            {"category": "Travel", "amount": 40.00, "merchant": "Uber", "date": "2026-08-05"}
        ],
        "spending_breakdown": [
            {"category": "Dining", "total_amount": 10.00, "percentage": 20.0, "expense_count": 1},
            {"category": "Travel", "total_amount": 40.00, "percentage": 80.0, "expense_count": 1}
        ],
        "major_expense_areas": ["Travel"],
        "spending_patterns": ["Frequent coffee purchases"],
        "insights_and_recommendations": ["Cap daily coffee spend"],
        "next_month_plan": {
            "estimated_total_budget": 45.00,
            "currency": "USD",
            "projected_savings": 5.00,
            "suggested_allocations": [
                {"category": "Travel", "recommended_amount": 35.00}
            ],
            "planner_tips": ["Use monthly travel pass"]
        },
        "confidence": 0.95,
        "actions": [],
        "memory_updates": []
    })

    resp = client.post(
        "/budget/analyze",
        json={
            "currency": "USD",
            "notes": "Testing duplicate statement entries"
        },
        headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["receipt_summary"]["deduplicated_count"] == 1
    assert body["receipt_summary"]["item_count"] == 2
    assert body["receipt_summary"]["bank_name_detected"] == "Chase Bank"
    assert len(body["analyzed_expenses"]) == 2

