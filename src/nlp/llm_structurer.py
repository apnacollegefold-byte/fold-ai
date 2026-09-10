import logging
from typing import Any
_log = logging.getLogger(__name__)
import requests
import logging
import re
import json


def structure_from_ocr(
    raw_text: str,
    text_source: str,
    api_key: str,
    hints: dict[str, Any] | None = None,
    model: str = "openai/gpt-oss-120b",
    timeout_seconds: int = 25,
    max_amount: float = 1_000_000.0,
) -> dict[str, Any]:
    """
    Extract structured data from raw OCR text using Groq API.
    """
    if not api_key:
        raise ValueError("Groq API key is required")

    _log.info(
        "[Groq] structuring start source=%s text_len=%d hints_keys=%s",
        text_source,
        len(raw_text or ""),
        sorted((hints or {}).keys()),
    )
    prompt = _build_prompt(raw_text=raw_text, text_source=text_source)

    # We explicitly inject the JSON schema requirements directly into the system prompt
    # since Groq strictly requires the word "JSON" in the prompt when using json_object mode.
    prompt = "Return your response in JSON format matching the requested keys.\n\n" + prompt

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }

    resp = requests.post(url, headers=headers, json=body, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()

    raw_out = data["choices"][0]["message"]["content"]
    _log.debug("[Groq] raw response preview=%s", (raw_out or "")[:300].replace("\n", " "))

    parsed = _parse_json(raw_out)
    normalized = _normalize_data(parsed, max_amount)

    _log.info(
        "[Groq] structuring done amount=%s pm=%s provider=%s bank=%s",
        normalized.get("amount"),
        normalized.get("payment_method"),
        normalized.get("payment_provider"),
        normalized.get("bank_account")
    )
    return normalized


def _build_prompt(*, raw_text: str, text_source: str) -> str:
    prompt = (
        "You are a financial extraction parser for India-focused OCR text.\n"
        "Return a strict JSON object with EXACTLY the following keys (use null if missing):\n"
        '{"amount": number|null, "payment_method": string|null, "payment_provider": string|null, '
        '"bank_account": string|null, "description": string, "card_network": string|null, '
        '"card_last4": string|null, "transaction_ref": string|null, "occurred_at": string|null}\n\n'
        f"text_source: {text_source}\n"
        "Allowed payment_method: upi, card, cash, null\n\n"
        "Rules:\n"
        "1) Use ₹, Rs, Pay, INR, R-prefixed amounts (e.g. R500.00 => 500.00).\n"
        "2) CRITICAL: Never use a 10-digit phone number or 12-digit UPI reference ID as the amount. If the number looks like an ID, ignore it entirely.\n"
    )

    if text_source == "upi_ocr":
        prompt += (
            "3) PIPELINE A [UPI SCREENSHOT]: This is a digital UPI payment screenshot. Prioritize finding the 'Paid to' / 'Received' amount. Look for UPI apps (GPay, PhonePe, Paytm) and set payment_method='upi'.\n"
        )
    else:
        prompt += (
            "3) PIPELINE B [NORMAL RECEIPT]: This is a standard paper receipt or invoice. Prioritize the final 'Total' or 'Amount Payable' usually found at the bottom.\n"
        )

    prompt += (
        "4) If card evidence exists (visa/mastercard/amex/rupay/debit/credit), set payment_method=card and card_network.\n\n"
        "Raw OCR text:\n"
        f"{raw_text[:6000]}"
    )
    return prompt

def _parse_json(raw: str) -> dict[str, Any]:
    t = (raw or "").strip()
    if not t:
        _log.warning("[Groq] empty response body")
        return {}
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if not m:
            _log.warning("[Groq] no JSON object found in response")
            return {}
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            _log.warning("[Groq] JSON parse failed even after object extraction")
            return {}


def _normalize_data(data: dict[str, Any], max_amount: float) -> dict[str, Any]:
    out: dict[str, Any] = {
        "amount": None,
        "payment_method": None,
        "payment_provider": None,
        "bank_account": None,

        "description": "",
        "card_network": None,
        "card_last4": None,
        "transaction_ref": None,
        "occurred_at": None,
    }
    out.update({k: v for k, v in data.items() if k in out})

    amt = out.get("amount")
    try:
        out["amount"] = float(amt) if amt is not None else None
        if out["amount"] is not None:
            # Reject negative amounts or exactly zero
            if out["amount"] <= 0:
                out["amount"] = None
            # Reject amounts that look like phone numbers or IDs
            elif out["amount"] > max_amount:
                _log.warning(f"[Groq] Amount {out['amount']} exceeds sanity limit ({max_amount}), clamping to None.")
                out["amount"] = None
    except (TypeError, ValueError):
        out["amount"] = None

    pm = str(out.get("payment_method") or "").lower().strip()
    out["payment_method"] = pm if pm in {"upi", "card", "cash"} else None


    for k in ("payment_provider", "bank_account", "card_network", "transaction_ref", "occurred_at"):
        v = out.get(k)
        if v is None:
            continue
        s = str(v).strip()
        out[k] = s if s and s.lower() not in {"none", "null", "unknown", "n/a"} else None

    d = out.get("description")
    out["description"] = (str(d).strip() if d is not None else "")[:500]

    last4 = out.get("card_last4")
    if last4 is not None:
        digits = re.sub(r"\D", "", str(last4))
        out["card_last4"] = digits[-4:] if len(digits) >= 4 else None
    else:
        out["card_last4"] = None

    return out
