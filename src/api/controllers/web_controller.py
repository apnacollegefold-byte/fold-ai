from datetime import datetime
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from api.middleware.clerk_auth import get_current_user
from api.repositories.ledger_repository import get_report_window_summary, get_breakdown
from api.services import ledger_service
from api.db.connection import get_db_connection

router = APIRouter(prefix="/api/v1/web", tags=["web-dashboard"])

@router.get("/dashboard")
async def get_dashboard(
    user: dict = Depends(get_current_user),
    period: str = Query(default="monthly", pattern="^(weekly|monthly)$"),
):
    """
    Single composite endpoint for the reports dashboard.
    Returns summary totals, breakdowns, balances, and recent transactions.
    """
    user_ref = user["user_ref"]
    user_id = user["user_id"]

    now = datetime.utcnow()
    days = 7 if period == "weekly" else max(1, now.day)

    
    with get_db_connection() as conn:
        summary = get_report_window_summary(user_id, days=days, conn=conn)
        income = int(summary["income_minor"])
        expense = int(summary["expense_minor"])
        net = income - expense

        by_category = get_breakdown(user_id, days=days, group_by="category", conn=conn)
        by_payment_method = get_breakdown(user_id, days=days, group_by="payment_method", conn=conn)
        by_account = get_breakdown(user_id, days=days, group_by="account", conn=conn)

        accounts = ledger_service.list_accounts(user_ref)
        tx_result = ledger_service.get_transactions(user_ref, limit=20, offset=0)
        transactions = tx_result.get("rows", []) if isinstance(tx_result, dict) else tx_result

    period_label = (
        "Last 7 days"
        if period == "weekly"
        else f"{now.strftime('%B %Y')} (month to date)"
    )

    return {
        "period": period,
        "period_label": period_label,
        "window_days": days,
        "summary": {
            "income_minor": income,
            "expense_minor": expense,
            "investment_minor": 0,
            "net_cashflow_minor": net,
        },
        "by_category": [dict(r) for r in by_category],
        "by_payment_method": [dict(r) for r in by_payment_method],
        "by_account": [dict(r) for r in by_account],
        "accounts": [dict(r) for r in accounts],
        "recent_transactions": [_serialize(t) for t in transactions],
    }


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

@router.get("/accounts")
async def get_accounts(user: dict = Depends(get_current_user)):
    accounts = ledger_service.list_accounts(user["user_ref"])
    return {"accounts": accounts}


@router.post("/accounts")
async def create_account(
    user: dict = Depends(get_current_user),
    name: str = Body(...),
    account_type: str = Body(...),
    institution_name: str | None = Body(default=None),
    account_number_last4: str | None = Body(default=None),
    opening_balance: float | None = Body(default=None),
):
    try:
        account = ledger_service.upsert_account(
            user_ref=user["user_ref"],
            name=name,
            account_type=account_type,
            institution_name=institution_name,
            account_number_last4=account_number_last4,
        )
        if opening_balance and opening_balance > 0:
            ledger_service.post_opening_balance(
                user_ref=user["user_ref"],
                source="account_creation",
                account_name=name,
                amount=opening_balance,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"account": account}

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
