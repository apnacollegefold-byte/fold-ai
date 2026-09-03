import logging
from psycopg.rows import dict_row
from api.db.connection import get_db_connection

_logger = logging.getLogger(__name__)

def get_or_create_user_from_clerk(
    clerk_user_id: str,
    email,
    full_name,
    avatar_url,
) -> dict:

    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, clerk_user_id, email, full_name, avatar_url, default_account_id
                FROM users
                WHERE clerk_user_id = %s
                """,
                (clerk_user_id,)
            )
            row = cur.fetchone()

            if row:
                cur.execute(
                    """
                    UPDATE users
                    SET email = COALESCE(%s, email),
                        full_name = COALESCE(%s, full_name),
                        avatar_url = COALESCE(%s, avatar_url),
                        updated_at = NOW()
                    WHERE clerk_user_id = %s
                    RETURNING id, clerk_user_id, email, full_name, avatar_url, default_account_id
                    """,
                    (email, full_name, avatar_url, clerk_user_id)
                )
                row = cur.fetchone()
                conn.commit()
                return row

            cur.execute(
                """
                INSERT INTO users (clerk_user_id, email, full_name, avatar_url)
                VALUES (%s, %s, %s, %s)
                RETURNING id, clerk_user_id, email, full_name, avatar_url, default_account_id
                """,
                (clerk_user_id, email, full_name, avatar_url)
            )
            row = cur.fetchone()
            conn.commit()
            _logger.info(f"Created new user from Clerk: {clerk_user_id}")
            return row


def get_user_by_clerk_id(clerk_user_id: str):
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, clerk_user_id, email, full_name, avatar_url, default_account_id
                FROM users
                WHERE clerk_user_id = %s
                """,
                (clerk_user_id,)
            )
            return cur.fetchone()


def set_default_account(clerk_user_id: str, account_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users SET default_account_id = %s WHERE clerk_user_id = %s
                """,
                (account_id, clerk_user_id)
            )
            conn.commit()
