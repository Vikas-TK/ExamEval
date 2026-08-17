import uuid
from app.models import EvaluationRecord, EvaluationStatus, StudentIdentity

def test_manual_review_workflow(db_session, monkeypatch):
    # Create test identity and record needing manual review
    eval_id = uuid.uuid4()
    identity = StudentIdentity(
        evaluation_id=eval_id,
        register_number="312221104099",
        regulation="R2021",
        semester="SEM-04",
        subject_id="CS8451"
    )
    record = EvaluationRecord(
        evaluation_id=eval_id,
        subject_id="CS8451",
        status=EvaluationStatus.NEEDS_REVIEW,
        needs_manual_review=True,
        error_message="Image blurry",
        blur_score=45.0,
        brightness_score=120.0,
        contrast_score=30.0,
        skew_angle=1.0,
        is_skewed=False,
        quality_passed=False,
        width=1000,
        height=1000,
        noise_score=10.0,
        resolution_passed=True
    )
    db_session.add(identity)
    db_session.add(record)
    db_session.commit()

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. GET /evaluations/manual-review
    response = client.get("/evaluations/manual-review")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    found = next((item for item in data["items"] if item["evaluation_id"] == str(eval_id)), None)
    assert found is not None
    assert found["status"] == "NEEDS_REVIEW"

    # 2. POST /evaluations/{id}/review (approve)
    review_resp = client.post(f"/evaluations/{eval_id}/review", json={"action": "approve", "notes": "Approved after visual check"})
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "COMPLETED"
    assert review_resp.json()["needs_manual_review"] == False
