import base64
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies import verify_service_api_key
from app.llm_client import get_llm_client
from app.schemas import ExpenseAnalysisRequest, ExpenseAnalysisResponse
from app.services import handle_budget_analysis

router = APIRouter(tags=["budget"], dependencies=[Depends(verify_service_api_key)])


@router.post(
    "/budget/analyze",
    response_model=ExpenseAnalysisResponse,
    summary="Analyze expenses & receipts (JSON payload)",
    description=(
        "Analyzes itemized expenses or base64 receipt documents (image or PDF). "
        "Calculates cost breakdowns, identifies spending patterns, and constructs "
        "a recommended budget plan for next month."
    ),
)
async def analyze_budget(
    req: ExpenseAnalysisRequest = Body(
        ...,
        openapi_examples={
            "structured_expenses": {
                "summary": "Structured expense list",
                "description": "Send itemized expenses array with budget targets.",
                "value": {
                    "currency": "USD",
                    "current_budget": 1000.0,
                    "previous_month_expenses": [
                        {"category": "Groceries", "amount": 320.50, "merchant": "Walmart", "date": "2026-08-05"},
                        {"category": "Utilities", "amount": 150.00, "merchant": "Electric Co", "date": "2026-08-10"},
                        {"category": "Dining Out", "amount": 210.00, "merchant": "Local Restaurants", "date": "2026-08-15"},
                    ],
                    "notes": "Looking to save 15% next month.",
                },
            },
            "with_base64_document": {
                "summary": "Base64 image or PDF receipt document",
                "description": "Send base64-encoded receipt/invoice document for AI vision parsing.",
                "value": {
                    "currency": "USD",
                    "current_budget": 500.0,
                    "file_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                    "file_type": "image/png",
                    "notes": "Analyze uploaded store receipt",
                },
            },
        },
    )
) -> ExpenseAnalysisResponse:
    llm = get_llm_client()
    return await handle_budget_analysis(req, llm)


@router.post(
    "/budget/analyze/upload",
    response_model=ExpenseAnalysisResponse,
    summary="Upload image or PDF receipt for expense analysis",
    description="Upload a receipt file directly (image/jpeg, image/png, image/webp, application/pdf).",
)
async def upload_budget_receipt(
    file: UploadFile = File(..., description="Receipt image or PDF file"),
    currency: str = Form("USD"),
    current_budget: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
) -> ExpenseAnalysisResponse:
    content_type = file.content_type or ""
    filename = file.filename or ""

    if not content_type:
        if filename.lower().endswith(".pdf"):
            content_type = "application/pdf"
        elif filename.lower().endswith(".png"):
            content_type = "image/png"
        elif filename.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".webp"):
            content_type = "image/webp"

    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
    if content_type and content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{content_type}'. Allowed types: JPEG, PNG, WEBP, GIF, PDF.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        if b"/Encrypt" in file_bytes or b"/Encrypted" in file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This PDF is password-protected by your bank. Please remove password protection before uploading.",
            )

    file_b64 = base64.b64encode(file_bytes).decode("utf-8")

    req = ExpenseAnalysisRequest(
        currency=currency,
        current_budget=current_budget,
        file_base64=file_b64,
        file_type=content_type or "image/jpeg",
        notes=notes or f"Uploaded receipt: {filename}",
    )

    llm = get_llm_client()
    return await handle_budget_analysis(req, llm)
