# 🚀 Exam Eval Platform — Start Commands

## ⚠️ IMPORTANT: Working Directory
ALL backend commands must be run from the **inner project folder**:
```
D:\exam_eval_platform\exam_eval_platform\
```
NOT from `D:\exam_eval_platform\` (the outer folder).

---

## 1. Start Backend (FastAPI on Port 8000)

Open PowerShell and run:

```powershell
# Step 1 — Go to the correct project folder
cd D:\exam_eval_platform\exam_eval_platform

# Step 2 — Start the backend using the project's own Python venv
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```


#- Start the backend in Linux
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


✅ Backend is running when you see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

- API Base URL  → http://localhost:8000
- Swagger Docs  → http://localhost:8000/docs
- ReDoc         → http://localhost:8000/redoc

> ❌ Do NOT use the bare `uvicorn` command — it picks up the system Python (3.14)
>    instead of the project venv (3.10), causing import failures.
> ✅ Always use `.\.venv\Scripts\python.exe -m uvicorn ...`

---

## 2. Start Frontend (Vite + React on Port 3000)

Open a **second** PowerShell window:

```powershell
# Step 1 — Go to the frontend folder
cd D:\exam_eval_platform\exam_eval_platform\frontend

# Step 2 — Install dependencies (first time only)
npm install

# Step 3 — Start the dev server
npm run dev
```

✅ Frontend is running when you see:
```
VITE v6.x  ready in xxx ms
➜  Local:   http://localhost:3000/
```

> All API calls (/api/*, /evaluations, /blueprints, /health) are
> automatically proxied to the backend on port 8000.
> You do NOT need to change any API URLs in the frontend.

---

## 3. Install Poppler (Required for PDF Upload Support)

The pipeline uses `pdf2image` to process uploaded PDF answer sheets.
`pdf2image` requires **Poppler** to be installed on Windows.

Without it you will see this error:
```
Unable to get page count. Is poppler installed and in PATH?
```

### Install Poppler on Windows:

**Option A — via winget (recommended)**
```powershell
winget install --id=oschwartz10612.Poppler -e
```
Then restart your terminal so PATH updates take effect.

**Option B — Manual install**
1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\poppler\`
3. Add `C:\poppler\Library\bin` to your system PATH:
   ```powershell
   [Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\poppler\Library\bin", "Machine")
   ```
4. Restart your terminal.

**Verify Poppler is working:**
```powershell
pdftoppm -v
```
You should see a version string like `pdftoppm version 24.x`.

> ℹ️ Poppler is only needed when uploading PDF files.
>    Uploading image files (JPG/PNG) works without Poppler.

---

## 4. (Optional) Run Database Migrations

```powershell
cd D:\exam_eval_platform\exam_eval_platform
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## 5. (Optional) Seed Sample Data

```powershell
cd D:\exam_eval_platform\exam_eval_platform
.\.venv\Scripts\python.exe -c "from app.seed import seed_database; seed_database()"
```

---

## Quick Reference

| Service      | URL                        | Command                                              |
|--------------|----------------------------|------------------------------------------------------|
| Backend      | http://localhost:8000       | `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Frontend     | http://localhost:3000       | `npm run dev` (inside `frontend/`)                   |
| API Docs     | http://localhost:8000/docs  | Open in browser after backend starts                 |
| ReDoc        | http://localhost:8000/redoc | Open in browser after backend starts                 |

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `.venv\Scripts\Activate.ps1 not recognized` | Wrong working directory | Run from `D:\exam_eval_platform\exam_eval_platform\` |
| `ModuleNotFoundError` on startup | Using system Python instead of venv | Use `.\.venv\Scripts\python.exe -m uvicorn ...` |
| `Unable to get page count. Is poppler installed?` | Poppler missing | See Section 3 above |
| `ForeignKeyViolation on evaluation_records` | DB write order bug | Fixed in `routers/evaluation.py` (two-commit approach) |
| Frontend shows blank page | Backend not running | Start backend first on port 8000 |
