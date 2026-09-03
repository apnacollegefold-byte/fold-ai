"""
FastAPI Application Entry Point
================================
Boots the API server and initializes the Postgres schema on startup.
CORS and static frontend serving get added in Module 19, once there's
an actual frontend to serve — not needed yet.

Run with:
    uvicorn src.api.main:app --reload --port 8000
"""

import os
import sys

# ─── Ensure src/ is on the Python path ───────────────────────────────────
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Load environment variables FIRST
import api.config  # noqa: F401 -- loads .env as a side effect

from fastapi import FastAPI
from api.db.connection import run_migrations

# ─── Create Application ─────────────────────────────────────────────────
app = FastAPI(
    title="Fold — Financial Ledger Extraction API",
    description=(
        "Multi-modal API that extracts structured financial data "
        "(amount, category, payment method, bank account) from "
        "voice notes, receipt images, and text messages."
    ),
    version="1.0.0",
)


@app.on_event("startup")
def startup_event():
    # Only creates missing tables — never wipes existing data.
    run_migrations()


# ─── Health Check ────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "fold-extraction-api"}


# ─── Direct Launch ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
