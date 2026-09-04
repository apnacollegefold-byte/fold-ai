import logging
import os
import api.config
from api.repositories.ledger_repository import (
    get_or_create_account,
    get_account_by_name,
    set_account_as_default,
    list_accounts as repo_list_accounts,
    list_accounts_by_user_id,
    get_payment_profile_by_provider,
    get_default_account_for_type,
    get_account_by_id,
    create_transaction,
    create_payment_profile,
    list_payment_profiles as repo_list_payment_profiles,
    get_transactions as repo_get_transactions,
    reassign_expense_category as repo_reassign_expense_category,
)
from api.repositories.user_repository import (
    get_or_create_user_from_clerk,
    get_user_by_clerk_id,
    set_default_account as set_user_default_account,
)

_logger = logging.getLogger(__name__)


def _to_minor(amount: float) -> int:
    amount_minor = int(round(amount * 100))
    if amount_minor <= 0:
        raise ValueError("Amount must be positive")
    cap = float(os.getenv("MAX_TRANSACTION_INR", "1000000"))
    if amount > cap:
        raise ValueError(
            f"Amount ₹{amount:,.2f} exceeds the single-transaction limit of ₹{cap:,.2f}. "
            "If this is real, adjust MAX_TRANSACTION_INR."
        )
    return amount_minor


def upsert_account(
    user_ref: str,
    name: str,
    account_type: str,
    institution_name: str | None = None,
    account_number_last4: str | None = None,
) -> dict:
    user = get_or_create_user_from_clerk(user_ref)
    account_last4 = account_number_last4

    # For cash wallets, institution and last4 are optional
    if account_type == "cash":
        account_last4 = None
        institution = institution_name or "Cash"
    else:
        institution = institution_name
        if account_last4 is not None:
            account_last4 = "".join(ch for ch in account_last4 if ch.isdigit())
            if len(account_last4) != 4:
                raise ValueError("account_number_last4 must contain exactly 4 digits")

    account = get_or_create_account(
        user_id=int(user["id"]),
        name=name,
        account_type=account_type,
        institution_name=institution,
        account_number_last4=account_last4,
    )
    # If this is the first account, make it default
    if not user.get("default_account_id"):
        set_user_default_account(user_ref, account["id"])

    return account


def ensure_cash_wallet_account(user_ref: str) -> dict:
    return upsert_account(
        user_ref=user_ref,
        name="Physical Cash",
        account_type="cash",
        institution_name="Cash",
    )


def set_primary_funding_account(user_ref: str, account_name: str) -> dict:
    user = get_or_create_user_from_clerk(user_ref)
    account = get_account_by_name(user["id"], account_name)
    if not account:
        raise ValueError(f"Account {account_name} not found.")
    set_user_default_account(user_ref, account["id"])
    return {"primary_funding_name": account_name}


def set_default_account(user_ref: str, account_name: str) -> dict:

    user = get_user_by_clerk_id(user_ref)
    if not user:
        raise ValueError("User not found")

    account = get_account_by_name(user["id"], account_name)
    if not account:
        raise ValueError(f"Account {account_name} not found")

    return set_account_as_default(user["id"], account["id"])


def list_accounts(user_ref: str) -> list[dict]:
    return repo_list_accounts(user_ref)


def _find_account_by_hint(user_id: int, hint: str) -> dict | None:
    """
    Find account by fuzzy matching on bank hint.
    Matches against account name and institution name (case-insensitive, partial match).
    """
    all_accounts = list_accounts_by_user_id(user_id)
    hint_lower = hint.lower().strip()

    # First try exact match on name
    for acc in all_accounts:
        if acc["name"].lower() == hint_lower:
            return acc

    # Then try partial match on name or institution
    for acc in all_accounts:
        name_lower = acc["name"].lower()
        inst_lower = (acc.get("institution_name") or "").lower()

        # Check if hint is contained in name or institution
        if hint_lower in name_lower or hint_lower in inst_lower:
            _logger.info(f"Fuzzy matched bank hint '{hint}' to account '{acc['name']}'")
            return acc

    return None


def post_expense(
    user_ref: str,
    source: str,
    description: str,
    amount: float,
    funding_account_name: str | None = None,
    external_ref: str | None = None,
    occurred_at: str | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    payment_provider: str | None = None,
    receipt_account_last4: str | None = None,
    receipt_institution_hint: str | None = None,
    bank_hint: str | None = None,
) -> dict:
    amount_minor = _to_minor(amount)
    user = get_user_by_clerk_id(user_ref)
    if not user:
        raise ValueError("User not found")

    account_id = None
    payment_profile_id = None
    resolved_method = "unknown"
    resolved_account_name = "unknown"

    _logger.info("="*80)
    _logger.info(f"[ExpenseResolution] Starting account resolution for user {user_ref}")
    _logger.info(f"  INPUT DATA:")
    _logger.info(f"    - description: {description}")
    _logger.info(f"    - amount: {amount}")
    _logger.info(f"    - payment_method: {payment_method}")
    _logger.info(f"    - payment_provider: {payment_provider}")
    _logger.info(f"    - bank_hint: {bank_hint}")
    _logger.info(f"    - funding_account_name: {funding_account_name}")
    _logger.info(f"    - category: {category}")

    all_accounts = list_accounts_by_user_id(user["id"])
    _logger.info(f"  AVAILABLE ACCOUNTS:")
    for acc in all_accounts:
        _logger.info(f"    - {acc['name']} (type={acc['account_type']}, institution={acc.get('institution_name')}, is_default={acc.get('is_default')})")

    # Priority 1: Explicit funding account name
    if funding_account_name:
        _logger.info(f"  [Priority 1] Checking explicit funding_account_name: {funding_account_name}")
        acc = get_account_by_name(user["id"], funding_account_name)
        if acc:
            account_id = acc["id"]
            resolved_method = "explicit_funding_account"
            resolved_account_name = acc["name"]
            _logger.info(f"    ✓ MATCHED: {acc['name']} (id={acc['id']})")
        else:
            _logger.info(f"    ✗ NO MATCH")

    # Priority 2: Bank hint (from NLP or OCR)
    if not account_id and bank_hint:
        hint_lower = bank_hint.lower().strip()
        _logger.info(f"  [Priority 2] Checking bank_hint: '{bank_hint}'")
        if hint_lower == "cash":
            acc = _find_account_by_hint(user["id"], "cash")
            if not acc:
                acc = ensure_cash_wallet_account(user_ref)
            account_id = acc["id"]
            resolved_method = "bank_hint_cash"
            resolved_account_name = acc["name"]
        else:
            acc = _find_account_by_hint(user["id"], bank_hint)
            if acc:
                account_id = acc["id"]
                resolved_method = "bank_hint_fuzzy"
                resolved_account_name = acc["name"]

    # Priority 3: Payment provider (UPI app)
    if not account_id and payment_provider:
        pp = get_payment_profile_by_provider(user_ref, payment_provider)
        if pp:
            payment_profile_id = pp["id"]
            account_id = pp["linked_account_id"]
            resolved_method = "payment_provider"
            resolved_account_name = f"profile:{pp.get('profile_name', 'unknown')}"

    # Priority 4: Payment method type
    if not account_id and payment_method:
        method_to_type = {"cash": "cash", "upi": "bank", "card": "credit"}
        account_type = method_to_type.get(payment_method)
        if account_type:
            default_acc = get_default_account_for_type(user["id"], account_type)
            if default_acc:
                account_id = default_acc["id"]
                resolved_method = f"default_{account_type}_account"
                resolved_account_name = default_acc["name"]

    # Priority 5: User's global default account
    if not account_id and user.get("default_account_id"):
        account_id = user["default_account_id"]
        resolved_method = "global_default"
        acc = get_account_by_id(user["id"], account_id)
        if acc:
            resolved_account_name = acc["name"]

    if not account_id:
        raise ValueError("Could not determine funding source. Please set a default account or link a payment profile.")

    _logger.info(f"  ✅ FINAL RESOLUTION: {resolved_account_name} ({resolved_method})")

    txn = create_transaction(
        clerk_user_id=user_ref,
        amount=amount_minor,
        type="expense",
        category=category or "expense",
        description=description,
        account_id=account_id,
        to_account_id=None,
        payment_profile_id=payment_profile_id,
        source=source,
    )

    txn["_resolution_method"] = resolved_method
    txn["_resolved_account_name"] = resolved_account_name
    txn["_resolved_account_id"] = account_id

    return txn


def post_income(
    user_ref: str,
    source: str,
    description: str,
    amount: float,
    destination_account_name: str | None = None,
    external_ref: str | None = None,
    occurred_at: str | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    bank_hint: str | None = None,
) -> dict:
    amount_minor = _to_minor(amount)
    user = get_user_by_clerk_id(user_ref)
    if not user:
        raise ValueError("User not found")

    account_id = None
    if destination_account_name:
        acc = get_account_by_name(user["id"], destination_account_name)
        if acc:
            account_id = acc["id"]

    # Same fuzzy bank-name matching post_expense uses (e.g. NLP-extracted
    # "hdfc" -> the user's "HDFC_prim" account) — an exact-name-only lookup
    # would miss it and silently fall through to the default account.
    if not account_id and bank_hint:
        acc = _find_account_by_hint(user["id"], bank_hint)
        if acc:
            account_id = acc["id"]

    if not account_id and user.get("default_account_id"):
        account_id = user["default_account_id"]

    if not account_id:
        raise ValueError("Could not determine destination account.")

    txn = create_transaction(
        clerk_user_id=user_ref,
        amount=amount_minor,
        type="income",
        category=category or "income",
        description=description,
        account_id=account_id,
        to_account_id=None,
        payment_profile_id=None,
        source=source,
    )
    return txn


def post_transfer(
    user_ref: str,
    source: str,
    description: str,
    amount: float,
    from_account_name: str,
    to_account_name: str,
    external_ref: str | None = None,
    occurred_at: str | None = None,
) -> dict:
    amount_minor = _to_minor(amount)
    user = get_user_by_clerk_id(user_ref)
    if not user:
        raise ValueError("User not found")

    from_acc = get_account_by_name(user["id"], from_account_name)
    to_acc = get_account_by_name(user["id"], to_account_name)

    if not from_acc or not to_acc:
        raise ValueError("Transfer accounts not found")

    txn = create_transaction(
        clerk_user_id=user_ref,
        amount=amount_minor,
        type="transfer",
        category="transfer",
        description=description,
        account_id=from_acc["id"],
        to_account_id=to_acc["id"],
        payment_profile_id=None,
        source=source,
    )
    return txn


def post_opening_balance(
    user_ref: str,
    source: str,
    account_name: str,
    amount: float,
    external_ref: str | None = None,
    occurred_at: str | None = None,
) -> dict:
    amount_minor = _to_minor(amount)
    user = get_user_by_clerk_id(user_ref)
    if not user:
        raise ValueError("User not found")

    acc = get_account_by_name(user["id"], account_name)
    if not acc:
        raise ValueError("Account not found")

    txn = create_transaction(
        clerk_user_id=user_ref,
        amount=amount_minor,
        type="opening_balance",
        category="opening_balance",
        description=f"Opening balance for {account_name}",
        account_id=acc["id"],
        to_account_id=None,
        payment_profile_id=None,
        source=source,
    )
    return txn


def upsert_payment_profile(
    user_ref: str,
    provider: str,
    profile_name: str,
    linked_account_name: str,
) -> dict:
    user = get_user_by_clerk_id(user_ref)
    if not user:
        raise ValueError("User not found")

    acc = get_account_by_name(user["id"], linked_account_name)
    if not acc:
        raise ValueError("Linked account not found")

    return create_payment_profile(
        clerk_user_id=user_ref,
        provider=provider,
        profile_name=profile_name,
        linked_account_id=acc["id"]
    )


def list_payment_profiles(user_ref: str) -> list[dict]:
    return repo_list_payment_profiles(user_ref)


def get_transactions(user_ref: str, limit: int = 50, offset: int = 0) -> dict:
    rows = repo_get_transactions(user_ref, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


def reassign_expense_category(user_ref: str, journal_id: int, new_category: str) -> dict:
    return repo_reassign_expense_category(
        user_ref=user_ref, transaction_id=journal_id, new_category=new_category
    )
