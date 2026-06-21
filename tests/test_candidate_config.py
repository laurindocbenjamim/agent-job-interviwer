import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_save_and_retrieve_candidate_config():
    """Verify that posting and getting candidate configuration works using UUID."""
    candidate_uuid = str(uuid.uuid4())
    
    payload = {
        "interview_duration_minutes": 45,
        "avatar_gender": "male",
        "question_time_limit_seconds": 90,
        "num_questions": 8,
        "interview_objective": "Test customized interview objective.",
        "interview_topics": "Docker,FastAPI,Unit Testing",
        "speech_language": "es-ES",
        "text_language": "es",
        "is_active": True
    }
    
    # 1. Update config
    post_response = client.post(f"/admin/config/{candidate_uuid}", json=payload)
    assert post_response.status_code == 200
    assert post_response.json() == {"status": "success", "message": "Configuration updated successfully"}
    
    # 2. Retrieve config and assert values match
    get_response = client.get(f"/admin/config/{candidate_uuid}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["interview_duration_minutes"] == 45
    assert data["avatar_gender"] == "male"
    assert data["question_time_limit_seconds"] == 90
    assert data["num_questions"] == 8
    assert data["interview_objective"] == "Test customized interview objective."
    assert data["interview_topics"] == "Docker,FastAPI,Unit Testing"
    assert data["speech_language"] == "es-ES"
    assert data["text_language"] == "es"
    assert data["is_active"] is True

def test_inactive_candidate_interview_gating():
    """Verify that an inactive candidate configuration blocks start."""
    candidate_uuid = str(uuid.uuid4())
    
    payload = {
        "interview_duration_minutes": 20,
        "avatar_gender": "female",
        "question_time_limit_seconds": 30,
        "num_questions": 3,
        "interview_objective": "Test inactive gating.",
        "interview_topics": "Python",
        "speech_language": "en-US",
        "text_language": "en",
        "is_active": False
    }
    
    # Update config to inactive
    client.post(f"/admin/config/{candidate_uuid}", json=payload)
    
    # Serve interview page
    response = client.get(f"/interview/{candidate_uuid}")
    assert response.status_code == 200
    assert "This interview session is currently INACTIVE" in response.text
    # The start button should be rendered or check is_active is template variable
    assert "is_active" in response.text or "INACTIVE" in response.text

def test_candidate_creation_api():
    """Verify that candidate creation generates a UUID and sets defaults."""
    payload = {
        "name": "Jane Developer",
        "job_specialty": "Frontend Engineer"
    }
    
    response = client.post("/admin/candidate/create", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "candidate_id" in data
    assert data["candidate_name"] == "Jane Developer"
    assert data["job_specialty"] == "Frontend Engineer"
    
    # Check that config was saved in DB
    config_uuid = data["candidate_id"]
    get_res = client.get(f"/admin/config/{config_uuid}")
    assert get_res.status_code == 200
    config_data = get_res.json()
    assert config_data["candidate_name"] == "Jane Developer"
    assert config_data["job_specialty"] == "Frontend Engineer"
    assert config_data["is_active"] is True

