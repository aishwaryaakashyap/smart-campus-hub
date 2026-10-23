
import pytest
import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_unauthenticated_user_cannot_submit_grievance(client):
    response = client.post("/api/grievances/", json={})

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not logged in"


def test_coordinator_cannot_submit_student_grievance(client):
    with client.session_transaction() as session:
        session["user_id"] = 999
        session["role"] = "coordinator"

    response = client.post("/api/grievances/", json={})

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only students can perform this action"
    )
