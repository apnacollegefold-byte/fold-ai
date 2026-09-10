import api.config
from nlp.inference import TransactionExtractor
from ocr.extractor import ReceiptOCR
from ocr.upi_detector import UPIAppDetector
from nlp.llm_structurer import structure_from_ocr
import os
import logging

_logger = logging.getLogger(__name__)


nlp= TransactionExtractor()
ocr =ReceiptOCR()

_roboflow_api_key = os.getenv("ROBOFLOW_API_KEY", "")

upi_detector = (
    UPIAppDetector(
        api_key=_roboflow_api_key,
        model_id=os.getenv("ROBOFLOW_UPI_MODEL_ID", "document-classification/upi/1"),
    )
    if _roboflow_api_key
    else None
)
if upi_detector is None:
    _logger.info("ROBOFLOW_API_KEY not set — UPI logo detection disabled")

def extract_from_image(image_path: str) -> dict:

    groq_api_key = os.getenv("GROQ_API_KEY", "")

    # Step 1: Visual UPI logo detection (is this a GPay/PhonePe screenshot?)
    visual_provider: str | None = None
    if upi_detector is not None:
        visual_provider = upi_detector.detect(image_path)
        _logger.info("[Image] UPI provider: %s", visual_provider or "none")

    # Step 2: PaddleOCR — extract raw text from the image
    ocr_result = ocr.process_receipt(image_path)
    all_text = ocr_result.get("raw_text", "")
    _logger.info("[Image] OCR extracted %d lines", len(ocr_result.get("all_lines", [])))

    # Step 3: Groq structures the noisy OCR text into clean fields.
    # OCR text from receipts is messy and unordered — an LLM is the best
    # tool to make sense of scattered text fragments.
    text_source = "upi_ocr" if visual_provider else "receipt_ocr"
    llm_result: dict = {}
    if groq_api_key:
        try:
            llm_result = structure_from_ocr(
                raw_text=all_text,
                text_source=text_source,
                api_key=groq_api_key,
                hints={"visual_provider": visual_provider},
            )
            _logger.info(
                "[Image] LLM structured: amount=%s method=%s provider=%s bank=%s",
                llm_result.get("amount"),
                llm_result.get("payment_method"),
                llm_result.get("payment_provider"),
                llm_result.get("bank_account"),
            )
        except Exception:
            _logger.exception("[Image] Groq structuring failed; continuing with NLP fallback")

    # Step 4: NLP classification. We prepend the LLM's structured output so
    # DistilBERT gets clean, readable text for category classification.
    preprocessed_text = all_text
    if llm_result:
        llm_lines = []
        if llm_result.get("description"):
            llm_lines.append(str(llm_result["description"]))
        if llm_result.get("amount") is not None:
            llm_lines.append(f"amount rs {llm_result['amount']}")
        if llm_result.get("payment_method"):
            llm_lines.append(f"payment method {llm_result['payment_method']}")
        if llm_result.get("payment_provider"):
            llm_lines.append(f"provider {llm_result['payment_provider']}")
        if llm_result.get("bank_account"):
            llm_lines.append(f"bank {llm_result['bank_account']}")
        llm_hint_text = " ; ".join(llm_lines).strip()
        if llm_hint_text:
            preprocessed_text = f"{llm_hint_text}\n{all_text}".strip()

    nlp_result = nlp.extract(preprocessed_text or "expense")

    # Step 5: Merge — the LLM wins for OCR-shaped fields, NLP for category
    final_amount = llm_result.get("amount") or nlp_result.get("amount")
    final_payment = llm_result.get("payment_method") or nlp_result.get("payment_method")
    final_provider = (
        visual_provider
        or llm_result.get("payment_provider")
        or nlp_result.get("payment_provider")
    )
    final_bank = llm_result.get("bank_account") or nlp_result.get("bank_account")

    # If we know the UPI app, the payment method must be "upi"
    if final_provider and (not final_payment or final_payment == "unknown"):
        final_payment = "upi"

    return {
        "amount": final_amount,
        "category": nlp_result["category"],
        "payment_method": final_payment,
        "payment_provider": final_provider,
        "bank_account": final_bank,
        "raw_text": all_text[:500],
    }
