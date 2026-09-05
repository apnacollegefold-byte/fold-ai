import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_CLASS_TO_PROVIDER: dict[str, str] = {
    "gpay": "gpay",
    "google_pay": "gpay",
    "google-pay": "gpay",
    "phonepe": "phonepe",
    "phone_pe": "phonepe",
    "phone-pe": "phonepe",
    "paytm": "paytm",
    "bhim": "bhim",
    "cred": "cred",
    "amazonpay": "amazonpay",
    "amazon_pay": "amazonpay",
    "mobikwik": "mobikwik",
}


class UPIAppDetector:
    def __init__(
        self,
        api_key: str,
        model_id: str = "document-classification/upi/1",
        confidence: int = 40,
        base_url: str = "https://serverless.roboflow.com",
    ) -> None:
        self.api_key = api_key
        self.model_id = model_id.strip().strip("/")
        self.confidence = confidence
        self.base_url = base_url.rstrip("/")

    def detect(self, image_path: str) -> str | None:

        try:
            dbg = self.detect_with_debug(image_path)
            predictions = dbg.get("predictions", [])
            if not predictions:
                return None

            best = max(predictions, key=lambda p: p.get("confidence", 0))
            cls_raw = (
                best.get("class", "")
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
                .strip()
            )
            provider = _CLASS_TO_PROVIDER.get(cls_raw)
            if provider:
                logger.info(
                    "UPI logo detected: class=%s → provider=%s (confidence=%.2f)",
                    cls_raw,
                    provider,
                    best.get("confidence", 0),
                )
            return provider
        except Exception:
            logger.exception("UPI logo detection failed — falling back to text-only")
            return None

    def detect_with_debug(self, image_path: str) -> dict:
 
        out: dict = {
            "ok": False,
            "model_id": self.model_id,
            "endpoint": f"{self.base_url}/{self.model_id}",
            "status_code": None,
            "predictions": [],
            "provider": None,
            "best_class": None,
            "best_confidence": None,
            "error": None,
        }
        try:
            img_bytes = Path(image_path).read_bytes()
            suffix = Path(image_path).suffix.lower() or ".jpg" 
            filename = f"upload{suffix if suffix in ('.jpg', '.jpeg', '.png', '.webp') else '.jpg'}"
            url = f"{self.base_url}/{self.model_id}"
            base_params = {"api_key": self.api_key, "confidence": self.confidence}

            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    url,
                    params=base_params,
                    files={"file": (filename, img_bytes, "application/octet-stream")},
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 405:
                    b64 = base64.b64encode(img_bytes).decode("ascii")
                    resp = client.post(
                        url,
                        params={**base_params, "name": filename},
                        content=b64,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Accept": "application/json",
                        },
                    )
                out["status_code"] = resp.status_code
                resp.raise_for_status()

            body = resp.json()
            preds = body.get("predictions", []) or []
            out["predictions"] = preds
            if preds:
                best = max(preds, key=lambda p: p.get("confidence", 0))
                cls_raw = (
                    str(best.get("class", ""))
                    .lower()
                    .replace("-", "_")
                    .replace(" ", "_")
                    .strip()
                )
                out["best_class"] = cls_raw
                out["best_confidence"] = best.get("confidence", None)
                out["provider"] = _CLASS_TO_PROVIDER.get(cls_raw)
            out["ok"] = True
            return out
        except Exception as exc:
            out["error"] = str(exc)
            logger.exception("UPI logo debug detection failed")
            return out
