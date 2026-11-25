
import pytest
from unittest.mock import MagicMock, patch
from flask import session
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

        with patch(
            "routes.grievance.get_session_user",
            side_effect=lambda user_id: type(
                "SessionUser", (), {"role": session.get("role")}
            )()
        ):
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
        "Only coordinators, advisors and chairpersons can access this endpoint"
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
    grievance.assigned_to = 11
    grievance.current_handler_id = 22
    grievance.current_handler_role = "chairperson"
    grievance.escalation_level = 1
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
        "You can update only grievances currently handled by you"
    )


def test_advisor_can_only_list_currently_handled_grievances(client):
    with client.session_transaction() as session:
        session["user_id"] = 11
        session["role"] = "advisor"

    with patch("routes.grievance.Grievance.query") as grievance_query:
        grievance_query.filter.return_value.order_by.return_value.all.return_value = []

        response = client.get("/api/grievances/manage")

    assert response.status_code == 200
    assert response.get_json() == []
    grievance_query.filter.assert_called_once()


def test_advisor_cannot_view_unassigned_grievance_history(client):
    grievance = MagicMock()
    grievance.id = 1
    grievance.assigned_to = 11
    grievance.current_handler_id = 22
    grievance.current_handler_role = "chairperson"
    grievance.escalation_level = 1

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
        "You can view only grievances currently handled by you"
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


def test_stale_coordinator_session_is_cleared_after_role_change(client):
    with client.session_transaction() as client_session:
        client_session["user_id"] = 11
        client_session["role"] = "coordinator"

    current_user = MagicMock()
    current_user.role = "student"

    with patch(
        "routes.grievance.get_session_user",
        return_value=current_user
    ):
        response = client.get("/api/grievances/manage")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not logged in"

    with client.session_transaction() as client_session:
        assert "user_id" not in client_session
        assert "role" not in client_session


def test_student_cannot_access_advisor_dashboard(client):
    with client.session_transaction() as session:
        session["user_id"] = 11
        session["role"] = "student"

    response = client.get("/advisor/dashboard")

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only advisors can access the advisor dashboard"
    )

def test_chairperson_can_list_escalated_grievances(client):
    with client.session_transaction() as session:
        session["user_id"] = 22
        session["role"] = "chairperson"

    with patch("routes.grievance.Grievance.query") as grievance_query:
        grievance_query.filter.return_value.order_by.return_value.all.return_value = []

        response = client.get("/api/grievances/manage")

    assert response.status_code == 200
    assert response.get_json() == []
    grievance_query.filter.assert_called_once()


def test_chairperson_can_view_escalated_grievance_history(client):
    grievance = MagicMock()
    grievance.id = 1
    grievance.current_handler_id = 22
    grievance.current_handler_role = "chairperson"
    grievance.escalation_level = 1

    update = MagicMock()
    update.old_status = "In Progress"
    update.new_status = "Under Review"
    update.comment = "Chairperson review"
    update.created_at.isoformat.return_value = "2026-11-21T09:00:00"
    update.updated_by = 22

    with client.session_transaction() as session:
        session["user_id"] = 22
        session["role"] = "chairperson"

    with patch(
        "routes.grievance.db.session.get",
        return_value=grievance
    ), patch(
        "routes.grievance.GrievanceUpdate.query"
    ) as update_query:
        update_query.filter_by.return_value.order_by.return_value.all.return_value = [
            update
        ]

        response = client.get("/api/grievances/manage/1/history")

    assert response.status_code == 200
    assert response.get_json()[0]["comment"] == "Chairperson review"


def test_chairperson_cannot_view_grievance_not_escalated_to_them(client):
    grievance = MagicMock()
    grievance.id = 1
    grievance.current_handler_id = 33
    grievance.current_handler_role = "chairperson"
    grievance.escalation_level = 1

    with client.session_transaction() as session:
        session["user_id"] = 22
        session["role"] = "chairperson"

    with patch(
        "routes.grievance.db.session.get",
        return_value=grievance
    ):
        response = client.get("/api/grievances/manage/1/history")

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "You can view only grievances escalated to you"
    )

def test_chairperson_can_update_grievance_escalated_to_them(client):
    grievance = MagicMock()
    grievance.id = 1
    grievance.title = "Classroom maintenance"
    grievance.status = "In Progress"
    grievance.current_handler_id = 22
    grievance.current_handler_role = "chairperson"
    grievance.escalation_level = 1
    grievance.student.user_id = 44

    with client.session_transaction() as session:
        session["user_id"] = 22
        session["role"] = "chairperson"

    with patch(
        "routes.grievance.db.session.get",
        return_value=grievance
    ), patch(
        "routes.grievance.GrievanceUpdate"
    ) as history_factory, patch(
        "routes.grievance.db.session.add"
    ) as add_mock, patch(
        "routes.grievance.db.session.commit"
    ) as commit_mock, patch(
        "routes.grievance.create_notification"
    ) as notification_mock:
        response = client.put(
            "/api/grievances/1/status",
            json={
                "status": "Resolved",
                "comment": "Issue resolved by Chairperson"
            }
        )

    assert response.status_code == 200
    assert grievance.status == "Resolved"
    assert grievance.current_handler_id is None
    assert grievance.current_handler_role is None
    assert grievance.sla_due_at is None
    history_factory.assert_called_once()
    add_mock.assert_called_once()
    commit_mock.assert_called_once()
    notification_mock.assert_called_once()


def test_different_chairperson_cannot_update_escalated_grievance(client):
    grievance = MagicMock()
    grievance.id = 1
    grievance.status = "In Progress"
    grievance.current_handler_id = 33
    grievance.current_handler_role = "chairperson"
    grievance.escalation_level = 1

    with client.session_transaction() as session:
        session["user_id"] = 22
        session["role"] = "chairperson"

    with patch(
        "routes.grievance.db.session.get",
        return_value=grievance
    ), patch(
        "routes.grievance.db.session.commit"
    ) as commit_mock:
        response = client.put(
            "/api/grievances/1/status",
            json={"status": "Resolved"}
        )

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "You can update only grievances escalated to you"
    )
    assert grievance.status == "In Progress"
    commit_mock.assert_not_called()
