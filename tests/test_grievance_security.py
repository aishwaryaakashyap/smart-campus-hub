
import pytest
from unittest.mock import MagicMock, patch
import app as app_module


@pytest.fixture
def client():
    previous_csrf = app_module.app.config.get(
        "WTF_CSRF_ENABLED", True
    )
    previous_testing = app_module.app.config.get(
        "TESTING", False
    )

    try:
        # Apply test configuration before yielding the client.
        app_module.app.config["TESTING"] = True
        app_module.app.config["WTF_CSRF_ENABLED"] = False

        with app_module.app.app_context():
            yield app_module.app.test_client()

    finally:
        # Always restore the original application settings.
        app_module.app.config["WTF_CSRF_ENABLED"] = previous_csrf
        app_module.app.config["TESTING"] = previous_testing


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


def test_student_cannot_view_another_students_grievance(client):
    student = MagicMock()
    student.id = 10

    grievance = MagicMock()
    grievance.student_id = 20

    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "student"

    with patch(
        "routes.grievance.Student.query"
    ) as student_query:
        student_query.filter_by.return_value.first.return_value = student

        with patch(
            "routes.grievance.db.session.get",
            return_value=grievance
        ):
            response = client.get("/api/grievances/1")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Grievance not found"


def test_student_cannot_view_another_students_grievance_history(client):
    student = MagicMock()
    student.id = 10

    grievance = MagicMock()
    grievance.id = 1
    grievance.student_id = 20

    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "student"

    with patch(
        "routes.grievance.Student.query"
    ) as student_query:
        student_query.filter_by.return_value.first.return_value = student

        with patch(
            "routes.grievance.db.session.get",
            return_value=grievance
        ):
            response = client.get("/api/grievances/1/history")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Grievance not found"


def test_advisor_cannot_update_unassigned_grievance(client):
    grievance = MagicMock()
    grievance.id = 1
    grievance.assigned_to = 22
    grievance.status = "Submitted"

    with client.session_transaction() as session:
        session["user_id"] = 11
        session["role"] = "advisor"

    with patch(
        "routes.grievance.db.session.get",
        return_value=grievance
    ):
        response = client.put(
            "/api/grievances/1/status",
            json={"status": "Resolved"}
        )

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "You can update only grievances assigned to you"
    )


def test_advisor_can_only_list_assigned_grievances(client):
    with client.session_transaction() as session:
        session["user_id"] = 11
        session["role"] = "advisor"

    with patch("routes.grievance.Grievance.query") as grievance_query:
        grievance_query.filter_by.return_value.order_by.return_value.all.return_value = []

        response = client.get("/api/grievances/manage")

    assert response.status_code == 200
    assert response.get_json() == []
    grievance_query.filter_by.assert_called_once_with(assigned_to=11)


def test_advisor_cannot_view_unassigned_grievance_history(client):
    grievance = MagicMock()
    grievance.id = 1
    grievance.assigned_to = 22

    with client.session_transaction() as session:
        session["user_id"] = 11
        session["role"] = "advisor"

    with patch(
        "routes.grievance.db.session.get",
        return_value=grievance
    ):
        response = client.get("/api/grievances/manage/1/history")

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "You can view only grievances assigned to you"
    )


def test_advisor_cannot_assign_grievances(client):
    with client.session_transaction() as session:
        session["user_id"] = 11
        session["role"] = "advisor"

    response = client.put(
        "/api/grievances/1/assign",
        json={"advisor_id": 22}
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only coordinators can assign grievances"
    )


def test_student_cannot_access_advisor_dashboard(client):
    with client.session_transaction() as session:
        session["user_id"] = 11
        session["role"] = "student"

    response = client.get("/advisor/dashboard")

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only advisors can access the advisor dashboard"
    )
