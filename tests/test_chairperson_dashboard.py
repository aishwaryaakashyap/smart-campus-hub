from types import SimpleNamespace
from unittest.mock import patch

import pytest

import app as app_module


@pytest.fixture
def client():
    previous_testing = app_module.app.config.get("TESTING", False)
    previous_csrf = app_module.app.config.get("WTF_CSRF_ENABLED", True)

    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False

    try:
        with app_module.app.test_client() as test_client:
            yield test_client
    finally:
        app_module.app.config["TESTING"] = previous_testing
        app_module.app.config["WTF_CSRF_ENABLED"] = previous_csrf


def set_session(client, user_id=14, role="chairperson"):
    with client.session_transaction() as current_session:
        current_session["user_id"] = user_id
        current_session["role"] = role


def make_user(role="chairperson", status="active"):
    return SimpleNamespace(
        id=14,
        name="Test Chairperson",
        role=role,
        account_status=status,
    )


def test_unauthenticated_user_is_redirected_to_login(client):
    response = client.get("/chairperson/dashboard")

    assert response.status_code == 302
    assert "/api/auth/login" in response.headers["Location"]


def test_non_chairperson_is_forbidden(client):
    set_session(client, user_id=5, role="advisor")

    response = client.get("/chairperson/dashboard")

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only chairpersons can access the Chairperson dashboard"
    )


def test_active_chairperson_can_open_dashboard(client):
    set_session(client)

    with patch("app.db.session.get", return_value=make_user()):
        response = client.get("/chairperson/dashboard")

    assert response.status_code == 200
    assert b"Chairperson Dashboard" in response.data
    assert b"Grievances escalated to me" in response.data
    assert b"Pending Student Registrations" not in response.data


def test_missing_chairperson_account_clears_session_and_redirects(client):
    set_session(client)

    with patch("app.db.session.get", return_value=None):
        response = client.get("/chairperson/dashboard")

    assert response.status_code == 302
    assert "/api/auth/login" in response.headers["Location"]

    with client.session_transaction() as current_session:
        assert "user_id" not in current_session
        assert "role" not in current_session


def test_inactive_chairperson_account_clears_session_and_redirects(client):
    set_session(client)

    with patch(
        "app.db.session.get",
        return_value=make_user(status="deactivated")
    ):
        response = client.get("/chairperson/dashboard")

    assert response.status_code == 302
    assert "/api/auth/login" in response.headers["Location"]

    with client.session_transaction() as current_session:
        assert "user_id" not in current_session
        assert "role" not in current_session
