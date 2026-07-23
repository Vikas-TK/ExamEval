"""
verify_seed_data.py

Executes GET requests against all API endpoints and prints the exact returned JSON payloads.
"""
import sys
import json

sys.path.insert(0, ".")

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)

endpoints = [
    ("GET", "/api/academic-master"),
    ("GET", "/evaluations/manual-review"),
    ("GET", "/blueprints"),
    ("GET", "/api/analytics/dashboard"),
    ("GET", "/api/analytics/question-analysis"),
    ("GET", "/api/analytics/student-performance"),
    ("GET", "/api/analytics/history"),
    ("GET", "/api/analytics/reports"),
    ("GET", "/api/storage/status"),
]

print("==================================================================")
print("VERIFYING SEEDED DATABASE CONTENT VIA API ENDPOINTS")
print("==================================================================")

for method, path in endpoints:
    print(f"\n---> {method} {path}")
    res = client.get(path)
    print(f"Status Code: {res.status_code}")
    if res.status_code == 200:
        data = res.json()
        print("Response Payload:")
        print(json.dumps(data, indent=2, default=str))
    else:
        print("Error Response:", res.text[:500])

print("\n==================================================================")
print("VERIFICATION COMPLETE")
print("==================================================================")
