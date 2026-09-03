import os
import logging
from contextlib import contextmanager
import api.config
import psycopg

_logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Open a connection to the database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Missing required env variable: DATABASE_URL")
    with psycopg.connect(database_url, connect_timeout=10) as conn:
        yield conn


def run_migrations() -> None:
    """Create all tables if they don't exist."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    clerk_user_id TEXT UNIQUE NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    avatar_url TEXT,
                    default_account_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    account_type TEXT NOT NULL CHECK (account_type IN ('cash', 'bank', 'credit')),
                    balance BIGINT NOT NULL DEFAULT 0,
                    institution_name TEXT,
                    account_number_last4 TEXT,
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, name),
                    CONSTRAINT positive_balance_non_credit CHECK (
                        account_type = 'credit' OR balance >= 0
                    )
                );

                -- Foreign key for default_account_id on users
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'fk_default_account'
                    ) THEN
                        ALTER TABLE users ADD CONSTRAINT fk_default_account
                        FOREIGN KEY (default_account_id) REFERENCES accounts(id) ON DELETE SET NULL;
                    END IF;
                END $$;

                CREATE TABLE IF NOT EXISTS payment_profiles (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    profile_name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    linked_account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, provider, profile_name)
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    amount BIGINT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('income', 'expense', 'transfer', 'opening_balance')),
                    category TEXT NOT NULL,
                    description TEXT,
                    account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
                    to_account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
                    payment_profile_id BIGINT REFERENCES payment_profiles(id) ON DELETE SET NULL,
                    source TEXT NOT NULL,
                    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
        conn.commit()
    _logger.info("Migrations complete.")
