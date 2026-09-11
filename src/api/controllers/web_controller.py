from datetime import datetime
from fastapi import APIRouter, Depends, Query
from api.middleware.clerk_auth import get_current_user
from api.services import ledger_service


router = APIRouter(prefix="/api/v1/web", tags=["web-dashboard"])

@router.get("/transactions")
async def get_transactions(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    user_ref = user["user_ref"]
    tx_result = ledger_service.get_transactions(user_ref, limit=limit, offset=offset)
    rows = tx_result.get("rows", []) if isinstance(tx_result, dict) else tx_result
    return {
        "transactions": [_serialize(t) for t in rows],
        "limit": limit,
        "offset": offset,
    }

def _serialize(t: dict) -> dict:
    """Ensure all values are JSON-serializable."""
    out = {}
    for k, v in t.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "items"):
            out[k] = dict(v)
        else:
            out[k] = v
    return out
