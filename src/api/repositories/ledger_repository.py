from psycopg.rows import dict_row
import logging
from api.db.connection import get_db_connection

_logging = logging.getLogger(__name__)

def get_or_create_account(
    user_id: int,
    name: str,
    account_type: str,
    institution_name: str | None = None,
    account_number_last4: str | None = None,
    conn=None,
) -> dict:
    owns_conn = conn is None
    if owns_conn:
        with get_db_connection() as own_conn:
            result = get_or_create_account(
                user_id, name, account_type, institution_name, account_number_last4, conn=own_conn
            )
            own_conn.commit()
            return result

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO accounts (user_id, name, account_type, institution_name, account_number_last4)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, name) DO UPDATE
            SET account_type = EXCLUDED.account_type,
                institution_name = COALESCE(EXCLUDED.institution_name, accounts.institution_name),
                account_number_last4 = COALESCE(EXCLUDED.account_number_last4, accounts.account_number_last4)
            RETURNING *
            """,
            (user_id, name, account_type, institution_name, account_number_last4),
        )
        return cur.fetchone()

def get_account_by_id(user_id: int, account_id: int) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM accounts WHERE user_id = %s AND id = %s",
                (user_id, account_id)
            )
            return cur.fetchone()

def set_account_as_default(user_id: int, account_id: int, conn=None) -> dict:
    """Set an account as the default for its type."""
    owns_conn = conn is None
    if owns_conn:
        with get_db_connection() as own_conn:
            result = set_account_as_default(user_id, account_id, conn=own_conn)
            own_conn.commit()
            return result

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT account_type FROM accounts WHERE id = %s AND user_id = %s",
            (account_id, user_id)
        )
        account = cur.fetchone()
        if not account:
            raise ValueError("Account not found")

        cur.execute(
            "UPDATE accounts SET is_default = FALSE WHERE user_id = %s AND account_type = %s",
            (user_id, account["account_type"])
        )

        cur.execute(
            "UPDATE accounts SET is_default = TRUE WHERE id = %s RETURNING *",
            (account_id,)
        )
        return cur.fetchone()

def get_default_account_for_type(user_id: int, account_type: str) -> dict | None:
    """Get the default account for a specific type."""
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM accounts WHERE user_id = %s AND account_type = %s AND is_default = TRUE LIMIT 1",
                (user_id, account_type)
            )
            return cur.fetchone()

def get_account_by_name(user_id: int, name: str) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM accounts WHERE user_id = %s AND name = %s",
                (user_id, name)
            )
            return cur.fetchone()

def list_accounts(clerk_user_id: str) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT a.*
                FROM users u
                JOIN accounts a ON a.user_id = u.id
                WHERE u.clerk_user_id = %s
                ORDER BY a.name
                """,
                (clerk_user_id,),
            )
            return cur.fetchall()

def list_accounts_by_user_id(user_id: int) -> list[dict]:
    """List all accounts for a user by user_id (not clerk_user_id)."""
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM accounts WHERE user_id = %s ORDER BY name",
                (user_id,)
            )
            return cur.fetchall()

def update_account_balance(account_id: int, amount_delta: int, conn=None):
    """
    Update account balance with negative balance protection.
    Raises ValueError if the update would result in a negative balance.
    """
    owns_conn = conn is None
    if owns_conn:
        with get_db_connection() as own_conn:
            update_account_balance(account_id, amount_delta, conn=own_conn)
            own_conn.commit()
            return

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT balance, name, account_type FROM accounts WHERE id = %s", (account_id,))
        account = cur.fetchone()
        if not account:
            raise ValueError(f"Account {account_id} not found")

        new_balance = account["balance"] + amount_delta

        if new_balance < 0 and account["account_type"] != "credit": 
            current_inr = account["balance"] / 100
            required_inr = abs(amount_delta) / 100
            raise ValueError(
                f"Insufficient balance in {account['name']}. "
                f"Current: ₹{current_inr:,.2f}, Required: ₹{required_inr:,.2f}"
            )

        cur.execute(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s",
            (amount_delta, account_id)
        )

def create_transaction(
    clerk_user_id: str,
    amount: int,
    type: str,
    category: str,
    description: str,
    account_id: int | None,
    to_account_id: int | None,
    payment_profile_id: int | None,
    source: str,
) -> dict:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM users WHERE clerk_user_id = %s", (clerk_user_id,))
            user = cur.fetchone()
            if not user:
                raise ValueError(f"User not found: {clerk_user_id}")
            user_id = user["id"]

            cur.execute(
                """
                INSERT INTO transactions (
                    user_id, amount, type, category, description,
                    account_id, to_account_id, payment_profile_id, source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, amount, type, category, description, account_id, to_account_id, payment_profile_id, source)
            )
            txn = cur.fetchone()

            if type == 'expense' and account_id:
                update_account_balance(account_id, -amount, conn=conn)
            elif type == 'income' and account_id:
                update_account_balance(account_id, amount, conn=conn)
            elif type == 'opening_balance' and account_id:
                update_account_balance(account_id, amount, conn=conn)
            elif type == 'transfer' and account_id and to_account_id:
                update_account_balance(account_id, -amount, conn=conn)
                update_account_balance(to_account_id, amount, conn=conn)

        conn.commit()
        return txn

def create_payment_profile(clerk_user_id: str, provider: str, profile_name: str, linked_account_id: int) -> dict:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM users WHERE clerk_user_id = %s", (clerk_user_id,))
            user = cur.fetchone()
            if not user:
                raise ValueError("User not found")

            cur.execute(
                """
                INSERT INTO payment_profiles (user_id, provider, profile_name, linked_account_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, provider, profile_name) DO UPDATE
                SET linked_account_id = EXCLUDED.linked_account_id
                RETURNING *
                """,
                (user["id"], provider.lower(), profile_name, linked_account_id)
            )
            row = cur.fetchone()
        conn.commit()
        return row

def list_payment_profiles(clerk_user_id: str) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT pp.*, a.name as linked_account_name
                FROM users u
                JOIN payment_profiles pp ON pp.user_id = u.id
                JOIN accounts a ON a.id = pp.linked_account_id
                WHERE u.clerk_user_id = %s
                ORDER BY pp.provider, pp.profile_name
                """,
                (clerk_user_id,)
            )
            return cur.fetchall()

def get_payment_profile_by_provider(clerk_user_id: str, provider: str) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT pp.*, a.name as linked_account_name, a.id as linked_account_id
                FROM users u
                JOIN payment_profiles pp ON pp.user_id = u.id
                JOIN accounts a ON a.id = pp.linked_account_id
                WHERE u.clerk_user_id = %s AND pp.provider = %s
                LIMIT 1
                """,
                (clerk_user_id, provider.lower())
            )
            return cur.fetchone()

def get_transactions(clerk_user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT t.*, a.name as account_name, a.account_type, a2.name as to_account_name, pp.provider as payment_provider
                FROM users u
                JOIN transactions t ON t.user_id = u.id
                LEFT JOIN accounts a ON a.id = t.account_id
                LEFT JOIN accounts a2 ON a2.id = t.to_account_id
                LEFT JOIN payment_profiles pp ON pp.id = t.payment_profile_id
                WHERE u.clerk_user_id = %s
                ORDER BY t.occurred_at DESC
                LIMIT %s OFFSET %s
                """,
                (clerk_user_id, limit, offset)
            )
            return cur.fetchall()

def get_report_window_summary(user_id: int, days: int, conn=None) -> dict:
    owns_conn = conn is None
    if owns_conn:
        with get_db_connection() as own_conn:
            return get_report_window_summary(user_id, days, conn=own_conn)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) AS income_minor,
                COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) AS expense_minor
            FROM transactions t
            WHERE t.user_id = %s
              AND t.occurred_at >= NOW() - (%s::text || ' days')::interval
            """,
            (user_id, days),
        )
        res = cur.fetchone()
        return res or {"income_minor": 0, "expense_minor": 0}

def get_breakdown(user_id: int, days: int, group_by: str, conn=None) -> list[dict]:
    valid_group = {
        "account": "a.name",
        "payment_method": "COALESCE(pp.provider, 'direct')",
        "category": "COALESCE(t.category, 'uncategorized')",
    }
    if group_by not in valid_group:
        raise ValueError("Invalid group_by")

    owns_conn = conn is None
    if owns_conn:
        with get_db_connection() as own_conn:
            return get_breakdown(user_id, days, group_by, conn=own_conn)

    sql_group_expr = valid_group[group_by]
    query = f"""
        SELECT
            {sql_group_expr} AS key,
            COALESCE(SUM(t.amount), 0) AS amount_minor
        FROM transactions t
        LEFT JOIN accounts a ON a.id = t.account_id AND a.user_id = t.user_id
        LEFT JOIN payment_profiles pp ON pp.id = t.payment_profile_id AND pp.user_id = t.user_id
        WHERE t.user_id = %s
          AND t.occurred_at >= NOW() - (%s::text || ' days')::interval
          AND t.type = 'expense'
        GROUP BY key
        ORDER BY amount_minor DESC
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (user_id, days))
        return cur.fetchall()

def reassign_expense_category(user_ref: str, transaction_id: int, new_category: str) -> dict:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE transactions t
                SET category = %s
                FROM users u
                WHERE u.id = t.user_id AND u.clerk_user_id = %s AND t.id = %s
                RETURNING t.id, t.category
                """,
                (new_category, user_ref, transaction_id)
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("Transaction not found")
        return dict(row)
