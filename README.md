# Fold — AI-Powered Financial Ledger

Multi-modal expense tracker: add transactions by typing, speaking, or
uploading a receipt/UPI screenshot, and Fold extracts amount, category,
payment method, and bank account automatically.

## Stack

- **Backend:** FastAPI, PostgreSQL (Neon), psycopg3
- **Auth:** Clerk
- **NLP:** DistilBERT (multi-head classification) + spaCy NER (amounts)
- **Speech-to-text:** Sarvam AI
- **OCR:** PaddleOCR
- **UPI logo detection:** Roboflow
- **LLM structuring:** Groq
- **Frontend:** Vanilla HTML/CSS/JS, no build step

## Running locally

```
pip install -r requirements.txt
cp .env.example .env   # fill in your own credentials
uvicorn src.api.main:app --reload --port 8000
```
