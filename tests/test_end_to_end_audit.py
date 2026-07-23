import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_detailed():
    response = client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "supabase" in data
    assert "storage" in data


def test_dashboard_analytics_api(db_session):
    response = client.get("/api/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "recent_activity" in data
    assert data["metrics"]["total_answer_sheets"] >= 0


def test_question_analysis_api(db_session):
    response = client.get("/api/analytics/question-analysis")
    assert response.status_code == 200
    data = response.json()
    assert "taxonomy_breakdown" in data
    assert "questions" in data


def test_student_performance_api(db_session):
    response = client.get("/api/analytics/student-performance")
    assert response.status_code == 200
    data = response.json()
    assert "grade_distribution" in data
    assert "students" in data


def test_evaluation_history_api(db_session):
    response = client.get("/api/analytics/history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_reports_summary_api(db_session):
    response = client.get("/api/analytics/reports")
    assert response.status_code == 200
    data = response.json()
    assert "overview" in data
    assert "quality_metrics" in data


def test_storage_status_api():
    response = client.get("/api/storage/status")
    assert response.status_code == 200
    data = response.json()
    assert "buckets" in data
    assert len(data["buckets"]) >= 4


def test_storage_list_files_api():
    response = client.get("/api/storage/list/question-papers")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
