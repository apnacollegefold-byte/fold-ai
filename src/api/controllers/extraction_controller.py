import os
import re
import tempfile
import api.config
import logging
from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile, File
from api.middleware.clerk_auth import get_current_user
from api.services.extraction_service import nlp, extract_from_image
from api.services import ledger_service
from stt.transcriber import transcribe_audio


_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/web/extract", tags=["web-extraction"])

INCOME_KEYWORDS = [
    "received", "salary", "credited", "refund", "cashback",
    "got paid", "payment received", "deposited", "bonus",
]


def _is_income(text: str) -> bool:
    """Whole-word keyword check for transaction direction (in vs out)."""
    lower = text.lower()
    return any(re.search(r"\b" + re.escape(kw) + r"\b", lower) for kw in INCOME_KEYWORDS)


def _save_transaction(
    user_ref: str, source: str, description: str, extracted: dict, raw_text: str | None = None
) -> tuple[dict, str]:

    if not extracted.get("amount"):
        return {"status": "skipped", "reason": "no_amount"}, "Extracted data but no amount found"

    accounts = ledger_service.list_accounts(user_ref)
    payment_accounts = [a for a in accounts if a.get("account_type") in ("cash", "bank", "credit")]
    if not payment_accounts:
        return (
            {"status": "pending", "reason": "no_payment_method"},
            f"Found a ₹{extracted['amount']} transaction. "
            "Please add a payment method first to save it.",
        )

    if _is_income(raw_text or description):
        ledger_result = ledger_service.post_income(
            user_ref=user_ref,
            source=source,
            description=description,
            amount=extracted["amount"],
            payment_method=extracted.get("payment_method"),
            bank_hint=extracted.get("bank_account"),
        )
        return ledger_result, f"Saved ₹{extracted['amount']} income"

    ledger_result = ledger_service.post_expense(
        user_ref=user_ref,
        source=source,
        description=description,
        amount=extracted["amount"],
        category=extracted.get("category"),
        payment_method=extracted.get("payment_method"),
        payment_provider=extracted.get("payment_provider"),
        bank_hint=extracted.get("bank_account"),
    )
    return ledger_result, f"Saved {extracted['category']} expense of ₹{extracted['amount']}"

async def _save_upload_to_temp(file: UploadFile, default_suffix: str) -> str:
    """Write an uploaded file to a temp path and return the path."""
    suffix = os.path.splitext(file.filename or default_suffix)[1] or default_suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="fold_") as tmp:
        tmp.write(await file.read())
        return tmp.name


@router.post("/text")
async def extract_and_save_text(
    text: str = Body(embed=True),
    user_info: dict = Depends(get_current_user),
):

    try:
        extracted = nlp.extract(text)
        ledger_result, message = _save_transaction(
            user_info["user_ref"], "web_text", text[:200], extracted, raw_text=text
        )
        return {
            "source": "text",
            "extracted_data": extracted,
            "ledger_result": ledger_result,
            "message": message,
        }
    except Exception as e:
        _logger.exception("Text extraction failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/audio")
async def extract_and_save_audio(
    file: UploadFile = File(...),
    user_info: dict = Depends(get_current_user),
):

    tmp_path = await _save_upload_to_temp(file, ".ogg")
    try:
        transcript = transcribe_audio(tmp_path, api_key=os.getenv("SARVAM_API_KEY", ""))
        extracted = nlp.extract(transcript)
        extracted["transcript"] = transcript

        ledger_result, message = _save_transaction(
            user_info["user_ref"], "web_audio", transcript[:200], extracted, raw_text=transcript
        )
        if ledger_result.get("status") == "skipped":
            message = f"Transcribed: {transcript}"

        return {
            "source": "audio",
            "extracted_data": extracted,
            "ledger_result": ledger_result,
            "message": message,
        }
    except Exception as e:
        _logger.exception("Audio extraction failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.post("/image")
async def extract_and_save_image(
    file: UploadFile = File(...),
    user_info: dict = Depends(get_current_user),
):

    tmp_path = await _save_upload_to_temp(file, ".jpg")
    try:
        extracted = extract_from_image(tmp_path)
        ledger_result, message = _save_transaction(
            user_info["user_ref"],
            "web_image",
            f"{extracted['category']} from receipt",
            extracted,
            raw_text=extracted.get("raw_text"),
        )
        return {
            "source": "image",
            "extracted_data": extracted,
            "ledger_result": ledger_result,
            "message": message,
        }
    except Exception as e:
        _logger.exception("Image extraction failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
