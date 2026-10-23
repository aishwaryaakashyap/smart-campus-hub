
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


def test_unauthenticated_user_cannot_list_notifications(client):
    response = client.get("/api/notifications/")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not logged in"


def test_unauthenticated_user_cannot_mark_notification_read(client):
    response = client.put("/api/notifications/1/read")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not logged in"


def test_unauthenticated_user_cannot_view_grievance(client):
    response = client.get("/api/grievances/1")
    assert response.status_code == 401


def test_unauthenticated_user_cannot_view_grievance_history(client):
    response = client.get("/api/grievances/1/history")
    assert response.status_code == 401


def test_unauthenticated_user_cannot_manage_grievances(client):
    response = client.get("/api/grievances/manage")
    assert response.status_code == 401


def test_unauthenticated_user_cannot_assign_grievance(client):
    response = client.put(
        "/api/grievances/1/assign",
        json={"advisor_id": 2}
    )
    assert response.status_code == 401


def test_unauthenticated_user_cannot_update_grievance_status(client):
    response = client.put(
        "/api/grievances/1/status",
        json={"status": "Resolved"}
    )
    assert response.status_code == 401


def test_student_cannot_manage_grievances(client):
    with client.session_transaction() as session:
        session["user_id"] = 999
        session["role"] = "student"

    response = client.get("/api/grievances/manage")

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only coordinators and advisors can access this endpoint"
    )
