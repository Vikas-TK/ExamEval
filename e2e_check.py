"""
e2e_check.py -- Full end-to-end connectivity and API test (ASCII output).
Run: .\.venv\Scripts\python.exe e2e_check.py
"""
import sys, json
sys.path.insert(0, ".")

from app.core.config import get_settings
settings = get_settings()

SEP = "=" * 62

# ─────────────────────────────────────────────────────────────────
print(SEP)
print("STEP 1 -- Backend host / port")
print(SEP)
print(f"  APP_HOST  : {settings.app_host}")
print(f"  APP_PORT  : {settings.app_port}")
print(f"  Backend URL: http://localhost:{settings.app_port}")
print(f"  SUPABASE_URL: {settings.supabase_url}")

# ─────────────────────────────────────────────────────────────────
print("\n" + SEP)
print("STEP 2 -- DATABASE_URL (password masked)")
print(SEP)
try:
    from urllib.parse import urlparse, urlunparse
    p = urlparse(settings.database_url)
    masked = urlunparse(p._replace(netloc=f"{p.username}:***@{p.hostname}:{p.port}"))
    print(f"  DATABASE_URL = {masked}")
except Exception:
    print(f"  DATABASE_URL starts with: {settings.database_url[:50]}...")

# ─────────────────────────────────────────────────────────────────
print("\n" + SEP)
print("STEP 3 -- Real database queries: SELECT 1 + list tables")
print(SEP)
from app.db.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1 AS ping"))
        ping = r.fetchone()[0]
        print(f"  SELECT 1 result : {ping}  [PASS]")

        r2 = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in r2.fetchall()]
        print(f"  Tables in public: {tables}")

        required = {"academic_master", "exam_blueprints", "student_identity", "evaluation_records"}
        missing  = required - set(tables)
        if missing:
            print(f"  MISSING tables  : {missing}")
        else:
            print(f"  All required tables present [PASS]")
except Exception as e:
    print(f"  DB query failed: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────
print("\n" + SEP)
print("STEP 4 -- FastAPI route health checks (TestClient)")
print(SEP)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)

routes = [
    ("GET",  "/health",                           None),
    ("GET",  "/api/academic-master",              None),
    ("GET",  "/evaluations/manual-review",        None),
    ("GET",  "/api/analytics/dashboard",          None),
    ("GET",  "/api/analytics/student-performance",None),
    ("GET",  "/api/analytics/history",            None),
    ("GET",  "/api/analytics/reports",            None),
    ("GET",  "/api/analytics/question-analysis",  None),
    ("GET",  "/api/storage/status",               None),
    ("GET",  "/api/storage/list/question-papers", None),
]

failures = []
for method, path, body in routes:
    try:
        resp = client.get(path) if method == "GET" else client.post(path, json=body)
        ok = resp.status_code < 400
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag}] {method} {path}  HTTP {resp.status_code}")
        if not ok:
            failures.append((method, path, resp.status_code, resp.text[:400]))
    except Exception as ex:
        failures.append((method, path, 0, str(ex)))
        print(f"  [FAIL] {method} {path}  EXCEPTION: {ex}")

if failures:
    print("\n  --- Failure details ---")
    for method, path, code, body in failures:
        print(f"  {method} {path} -> {code}")
        print(f"  {body[:300]}")

# ─────────────────────────────────────────────────────────────────
print("\n" + SEP)
print("STEP 5 -- Real POST /api/academic-master with sample payload")
print(SEP)
payload = {
    "academic_year": "2024-2025",
    "regulation":    "R2021",
    "department":    "Computer Science and Engineering",
    "semester":      "SEM-04",
    "subject_code":  "E2ETEST001",
    "subject_name":  "End-to-End Test Subject",
    "credits":       4,
    "status":        "ACTIVE"
}
print("  Payload:")
print(json.dumps(payload, indent=4))

resp = client.post("/api/academic-master", json=payload)
print(f"\n  HTTP Status  : {resp.status_code}")
try:
    body = resp.json()
    print("  Response Body:")
    print(json.dumps(body, indent=4, default=str))
    if resp.status_code in (200, 201):
        print("\n  [PASS] POST /api/academic-master -> record saved to Supabase Postgres")
        rid = body.get("id")
        if rid:
            del_resp = client.delete(f"/api/academic-master/{rid}")
            print(f"  [CLEANUP] DELETE /api/academic-master/{rid} -> HTTP {del_resp.status_code}")
    else:
        print("\n  [FAIL] POST /api/academic-master failed")
except Exception:
    print("  Response (raw):", resp.text[:500])

print("\n" + SEP)
print("E2E CHECK COMPLETE")
print(SEP)
