
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from app import app


class PlacementDriveRouteTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.client = app.test_client()

    def set_session(self, user_id=1, role="coordinator"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    # CREATE AUTHORIZATION

    def test_rejects_unauthenticated_create(self):
        response = self.client.post(
            "/api/drives/",
            json={"company_id": 1, "job_role": "Python Developer"}
        )
        self.assertEqual(response.status_code, 401)

    def test_rejects_student_creating_drive(self):
        self.set_session(role="student")

        response = self.client.post(
            "/api/drives/",
            json={"company_id": 1, "job_role": "Python Developer"}
        )
        self.assertEqual(response.status_code, 403)

    # REQUIRED FIELD VALIDATION

    def test_rejects_missing_company_id(self):
        self.set_session()

        response = self.client.post(
            "/api/drives/",
            json={"job_role": "Python Developer"}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_blank_job_role(self):
        self.set_session()

        response = self.client.post(
            "/api/drives/",
            json={"company_id": 1, "job_role": "   "}
        )
        self.assertEqual(response.status_code, 400)

    # COMPANY VALIDATION

    @patch("routes.placement_drive.Company.query")
    def test_returns_404_when_company_does_not_exist(self, company_query):
        self.set_session()
        company_query.get.return_value = None

        response = self.client.post(
            "/api/drives/",
            json={"company_id": 999, "job_role": "Python Developer"}
        )

        self.assertEqual(response.status_code, 404)

    def test_rejects_invalid_company_id(self):
        self.set_session()

        for company_id in ("1", True, 0, -1):
            with self.subTest(company_id=company_id):
                response = self.client.post(
                    "/api/drives/",
                    json={
                        "company_id": company_id,
                        "job_role": "Python Developer"
                    }
                )
                self.assertEqual(response.status_code, 400)

    # JSON VALIDATION

    def test_rejects_json_array(self):
        self.set_session()

        response = self.client.post(
            "/api/drives/",
            json=[{"company_id": 1, "job_role": "Developer"}]
        )

        self.assertEqual(response.status_code, 400)

    # STATUS VALIDATION

    def test_rejects_invalid_status(self):
        self.set_session()

        for status in ("Pending", "Cancelled", 123):
            with self.subTest(status=status):
                response = self.client.post(
                    "/api/drives/",
                    json={
                        "company_id": 1,
                        "job_role": "Developer",
                        "status": status
                    }
                )
                self.assertEqual(response.status_code, 400)

    # CGPA VALIDATION

    def test_rejects_invalid_cgpa(self):
        self.set_session()

        for cgpa in (-1, "8.0", True, float("nan"), float("inf")):
            with self.subTest(cgpa=cgpa):
                response = self.client.post(
                    "/api/drives/",
                    json={
                        "company_id": 1,
                        "job_role": "Developer",
                        "min_cgpa": cgpa
                    }
                )
                self.assertEqual(response.status_code, 400)

    # SEMESTER VALIDATION

    def test_rejects_invalid_semester(self):
        self.set_session()

        for semester in (0, -1, "5", True):
            with self.subTest(semester=semester):
                response = self.client.post(
                    "/api/drives/",
                    json={
                        "company_id": 1,
                        "job_role": "Developer",
                        "eligible_semester": semester
                    }
                )
                self.assertEqual(response.status_code, 400)

    # BRANCH VALIDATION

    def test_rejects_invalid_branches(self):
        self.set_session()

        for branches in (123, "CSE,,ISE", ","):
            with self.subTest(branches=branches):
                response = self.client.post(
                    "/api/drives/",
                    json={
                        "company_id": 1,
                        "job_role": "Developer",
                        "eligible_branches": branches
                    }
                )
                self.assertEqual(response.status_code, 400)

    # DATE VALIDATION

    @patch("routes.placement_drive.Company.query")
    def test_rejects_invalid_date(self, company_query):
        self.set_session()
        company_query.get.return_value = MagicMock(id=1)

        response = self.client.post(
            "/api/drives/",
            json={
                "company_id": 1,
                "job_role": "Developer",
                "drive_date": "invalid-date"
            }
        )

        self.assertEqual(response.status_code, 400)

    @patch("routes.placement_drive.Company.query")
    def test_rejects_deadline_after_drive_date(self, company_query):
        self.set_session()
        company_query.get.return_value = MagicMock(id=1)

        response = self.client.post(
            "/api/drives/",
            json={
                "company_id": 1,
                "job_role": "Developer",
                "drive_date": "2026-12-10",
                "application_deadline": "2026-12-15"
            }
        )

        self.assertEqual(response.status_code, 400)

    # DATABASE ERROR HANDLING

    @patch("routes.placement_drive.Company.query")
    def test_handles_database_error_when_creating_drive(self, company_query):
        self.set_session()
        company_query.get.return_value = MagicMock(id=1)

        with patch(
            "routes.placement_drive.db.session.add"
        ), patch(
            "routes.placement_drive.db.session.commit",
            side_effect=SQLAlchemyError("Database error")
        ), patch(
            "routes.placement_drive.db.session.rollback"
        ) as mock_rollback:

            response = self.client.post(
                "/api/drives/",
                json={
                    "company_id": 1,
                    "job_role": "Python Developer"
                }
            )

        self.assertEqual(response.status_code, 500)
        mock_rollback.assert_called_once()

    # SUCCESSFUL DRIVE CREATION

    @patch("routes.placement_drive.Company.query")
    @patch("routes.placement_drive.PlacementDrive")
    def test_create_drive_success(self, mock_drive_class, company_query):
        self.set_session()
        company_query.get.return_value = MagicMock(id=1)
        mock_drive_class.return_value = MagicMock(id=77)

        with patch("routes.placement_drive.db.session.add"), patch(
            "routes.placement_drive.db.session.commit"
        ):
            response = self.client.post(
                "/api/drives/",
                json={
                    "company_id": 1,
                    "job_role": "Python Developer"
                }
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["id"], 77)

    # CLOSE DRIVE AUTHORIZATION

    def test_rejects_unauthenticated_close(self):
        response = self.client.put("/api/drives/1/close")
        self.assertEqual(response.status_code, 401)

    def test_rejects_student_closing_drive(self):
        self.set_session(role="student")

        response = self.client.put("/api/drives/1/close")
        self.assertEqual(response.status_code, 403)

    # SUCCESSFUL DRIVE CLOSURE

    @patch("routes.placement_drive.PlacementDrive.query")
    def test_close_drive_success(self, drive_query):
        self.set_session()

        mock_drive = MagicMock()
        mock_drive.status = "Open"
        drive_query.get.return_value = mock_drive

        with patch("routes.placement_drive.db.session.commit"):
            response = self.client.put("/api/drives/1/close")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_drive.status, "Closed")


if __name__ == "__main__":
    unittest.main()
