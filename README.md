# Anonymous Exam Evaluation & Blueprint Platform

FastAPI production service for anonymous exam-script ingestion, image quality validation, Qwen2.5-VL OCR, exam layout blueprint modeling, S3/Supabase storage, and PostgreSQL persistence.

## Features
- **Phase 1 (Ingestion & OCR)**: Anonymous student answer script upload, OpenCV quality validation (blur, brightness, contrast, deskew, perspective warp, noise removal), Qwen2.5-VL OCR extraction, transcript artifact generation, and zero-trust HMAC student identity hashing.
- **Phase 2 (Blueprint Modeling)**: Question paper layout modeling, section detection, marks extraction, question classification (MCQ, Short Answer, Descriptive, Diagram), and optional faculty answer key mapping.
- **Web Frontend**: Built-in responsive SPA interfaces at `/static/index.html` (Student Ingestion) and `/static/blueprint.html` (Blueprint Dashboard) with PWA support.

## Quick Start (Local Run)

Target Python 3.10 – 3.12 (Python 3.14 is unsupported locally due to missing pre-built OpenCV wheels).

1. Copy `.env.example` to `.env` (a pre-configured default `.env` is included for rapid local testing).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run Alembic migrations:
   ```bash
   alembic upgrade head
   ```
4. Start the server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
5. Open your browser:
   - Ingestion Portal: `http://localhost:8000/` or `http://localhost:8000/static/index.html`
   - Blueprint Portal: `http://localhost:8000/static/blueprint.html`
   - API Docs: `http://localhost:8000/docs`

## Quick Start (Docker Compose)

Run the full container stack (PostgreSQL database, migration runner, and API web server):

```bash
docker compose up --build
```

The database migrations run automatically via a dedicated `db-migrate` service before the main API container launches.

## Key Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (Supabase or local Postgres).
- `IDENTITY_HASH_SECRET`: Salt key for keyed SHA-256 HMAC student identity hashing.
- `STORAGE_PROVIDER`: Storage abstraction target (`s3` or `supabase`).
- `S3_BUCKET_NAME`: Target bucket name for uploaded answer sheets and blueprints.
- `QWEN_API_BASE`: OpenAI-compatible API base URL for Qwen2.5-VL server (vLLM, DashScope, or Ollama).

## Storage Bucket Layout

All uploaded files are organized into structured prefixes:

```
answer-sheets/
    original/
    enhanced/
    transcripts/
exam-blueprints/
faculty-answer-keys/
reports/
```

## Running Tests

Run the unit and integration test suite:

```bash
pytest
```
