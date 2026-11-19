import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class StudentRegistrationOTPTests(unittest.TestCase):

    def setUp(self):
        self.old_testing = app.config.get("TESTING")
        self.old_csrf = app.config.get("WTF_CSRF_ENABLED")
        self.old_secret = app.config.get("SECRET_KEY")

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = self.old_testing
        app.config["WTF_CSRF_ENABLED"] = self.old_csrf
        app.config["SECRET_KEY"] = self.old_secret
        self.app_context.pop()

    def test_registration_rejects_non_json_request(self):
        response = self.client.post(
            "/api/auth/register",
            data="not-json",
            content_type="text/plain"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_registration_rejects_privileged_role(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "Password123",
                "role": "coordinator"
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Only student registration", response.get_json()["error"])

    def test_registration_rejects_missing_register_number(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "name": "Test Student",
                "email": "student@example.com",
                "password": "Password123",
                "role": "student"
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Register number", response.get_json()["error"])

    def test_otp_verification_rejects_invalid_otp_format(self):
        response = self.client.post(
            "/api/auth/verify-registration-otp",
            json={
                "email": "student@example.com",
                "otp": "123"
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("six-digit OTP", response.get_json()["error"])

    def test_otp_verification_rejects_non_numeric_otp(self):
        response = self.client.post(
            "/api/auth/verify-registration-otp",
            json={
                "email": "student@example.com",
                "otp": "12AB56"
            }
        )

        self.assertEqual(response.status_code, 400)

    @patch("routes.auth.User.query")
    def test_resend_for_unknown_email_does_not_disclose_account(self, mock_query):
        mock_query.filter_by.return_value.first.return_value = None

        response = self.client.post(
            "/api/auth/resend-registration-otp",
            json={"email": "unknown@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("If the registration needs verification", response.get_json()["message"])

    @patch("routes.auth.User.query")
    def test_unverified_pending_student_cannot_login(self, mock_query):
        student = SimpleNamespace(
            id=10,
            name="Test Student",
            role="student",
            account_status="pending",
            email_verified_at=None,
            check_password=lambda password: True
        )

        mock_query.filter_by.return_value.first.return_value = student

        response = self.client.post(
            "/api/auth/login",
            json={
                "email": "student@example.com",
                "password": "Password123"
            }
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("verify your email", response.get_json()["error"].lower())

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    @patch("routes.auth.User.query")
    def test_verified_pending_student_cannot_login_before_approval(self, mock_query):
        student = SimpleNamespace(
            id=11,
            name="Verified Student",
            role="student",
            account_status="pending",
            email_verified_at=object(),
            check_password=lambda password: True
        )

        mock_query.filter_by.return_value.first.return_value = student

        response = self.client.post(
            "/api/auth/login",
            json={
                "email": "verified@example.com",
                "password": "Password123"
            }
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("awaiting Advisor approval", response.get_json()["error"])

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)


class AdvisorStudentRegistrationAccessTests(unittest.TestCase):

    def setUp(self):
        self.old_testing = app.config.get("TESTING")
        self.old_csrf = app.config.get("WTF_CSRF_ENABLED")

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = self.old_testing
        app.config["WTF_CSRF_ENABLED"] = self.old_csrf
        self.app_context.pop()

    def test_unauthenticated_user_cannot_list_student_registrations(self):
        response = self.client.get(
            "/api/academic-admin/students/registrations"
        )

        self.assertEqual(response.status_code, 401)

    @patch("routes.advisor_admin.db.session.get")
    def test_student_cannot_access_advisor_registration_list(self, mock_get):
        student_user = SimpleNamespace(
            id=20,
            role="student",
            account_status="active"
        )
        mock_get.return_value = student_user

        with self.client.session_transaction() as session:
            session["user_id"] = 20
            session["role"] = "student"

        response = self.client.get(
            "/api/academic-admin/students/registrations"
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Only Advisors", response.get_json()["error"])

    @patch("routes.advisor_admin.db.session.get")
    def test_advisor_reject_reason_must_be_text(self, mock_get):
        advisor = SimpleNamespace(
            id=30,
            role="advisor",
            account_status="active"
        )
        mock_get.return_value = advisor

        with self.client.session_transaction() as session:
            session["user_id"] = 30
            session["role"] = "advisor"

        response = self.client.post(
            "/api/academic-admin/students/10/reject",
            json={"reason": 123}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("must be text", response.get_json()["error"])


class StudentRegistrationSuccessTests(unittest.TestCase):

    def setUp(self):
        self.old_testing = app.config.get("TESTING")
        self.old_csrf = app.config.get("WTF_CSRF_ENABLED")
        self.old_secret = app.config.get("SECRET_KEY")

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = self.old_testing
        app.config["WTF_CSRF_ENABLED"] = self.old_csrf
        app.config["SECRET_KEY"] = self.old_secret
        self.app_context.pop()

    def test_successful_registration_creates_pending_student(self):
        class FakeUser:
            ROLE_STUDENT = "student"
            ROLE_ADVISOR = "advisor"
            STATUS_PENDING = "pending"
            STATUS_ACTIVE = "active"
            query = MagicMock()
            instances = []

            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.id = None
                self.email_verified_at = None
                self.instances.append(self)

            def set_password(self, password):
                self.password_was_set = bool(password)

        class FakeStudent:
            query = MagicMock()

            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        FakeUser.query.filter_by.return_value.first.return_value = None
        FakeStudent.query.filter_by.return_value.first.return_value = None

        advisor = SimpleNamespace(
            role="advisor",
            account_status="active"
        )

        academic_class = SimpleNamespace(
            id=7,
            course="B.Tech",
            branch="Computer Science",
            is_active=True,
            advisor=advisor
        )

        def assign_user_id():
            FakeUser.instances[-1].id = 101

        with patch("routes.auth.User", FakeUser), \
             patch("routes.auth.Student", FakeStudent), \
             patch("routes.auth.db.session.get", return_value=academic_class), \
             patch("routes.auth.db.session.add"), \
             patch("routes.auth.db.session.flush", side_effect=assign_user_id), \
             patch("routes.auth.db.session.commit"), \
             patch("routes.auth._create_student_otp", return_value=("123456", 10)), \
             patch("routes.auth.send_student_otp_email") as mock_email:

            response = self.client.post(
                "/api/auth/register",
                json={
                    "name": "Test Student",
                    "email": "STUDENT@example.com",
                    "password": "Password123",
                    "role": "student",
                    "register_number": "REG101",
                    "academic_class_id": 7,
                    "semester": 4,
                    "cgpa": 8.5
                }
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["email"], "student@example.com")
        self.assertTrue(response.get_json()["email_sent"])

        created_user = FakeUser.instances[-1]
        self.assertEqual(created_user.account_status, "pending")
        self.assertIsNone(created_user.email_verified_at)
        self.assertTrue(created_user.password_was_set)

        mock_email.assert_called_once_with(
            "student@example.com",
            "123456",
            10
        )


class StudentOTPWorkflowTests(unittest.TestCase):

    def setUp(self):
        self.old_testing = app.config.get("TESTING")
        self.old_csrf = app.config.get("WTF_CSRF_ENABLED")
        self.old_secret = app.config.get("SECRET_KEY")

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = self.old_testing
        app.config["WTF_CSRF_ENABLED"] = self.old_csrf
        app.config["SECRET_KEY"] = self.old_secret
        self.app_context.pop()

    @patch("routes.auth.db.session.commit")
    @patch("routes.auth._otp_hash", return_value="correct-hash")
    @patch("routes.auth.StudentRegistrationOTP.query")
    @patch("routes.auth.User.query")
    def test_correct_otp_verifies_email_but_keeps_account_pending(
        self,
        mock_user_query,
        mock_otp_query,
        mock_hash,
        mock_commit
    ):
        student_user = SimpleNamespace(
            id=101,
            account_status="pending",
            email_verified_at=None
        )

        otp_record = SimpleNamespace(
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            attempts=0,
            otp_hash="correct-hash",
            used_at=None
        )

        mock_user_query.filter_by.return_value.first.return_value = student_user

        (
            mock_otp_query.filter_by.return_value
            .order_by.return_value.first.return_value
        ) = otp_record

        response = self.client.post(
            "/api/auth/verify-registration-otp",
            json={
                "email": "student@example.com",
                "otp": "123456"
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["email_verified"])
        self.assertEqual(student_user.account_status, "pending")
        self.assertIsNotNone(student_user.email_verified_at)
        self.assertIsNotNone(otp_record.used_at)
        self.assertEqual(otp_record.attempts, 1)
        mock_commit.assert_called_once()


class AdvisorStudentApprovalWorkflowTests(unittest.TestCase):

    def setUp(self):
        self.old_testing = app.config.get("TESTING")
        self.old_csrf = app.config.get("WTF_CSRF_ENABLED")

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = self.old_testing
        app.config["WTF_CSRF_ENABLED"] = self.old_csrf
        self.app_context.pop()

    def make_student(self):
        advisor = SimpleNamespace(
            id=30,
            role="advisor",
            account_status="active"
        )

        user = SimpleNamespace(
            id=101,
            name="Test Student",
            email="student@example.com",
            role="student",
            account_status="pending",
            email_verified_at=datetime.utcnow(),
            reviewed_by_user_id=None,
            reviewed_at=None,
            rejection_reason="Old reason"
        )

        student = SimpleNamespace(
            id=10,
            user=user
        )

        return advisor, user, student

    @patch("routes.advisor_admin.db.session.commit")
    @patch("routes.advisor_admin.create_notification")
    @patch("routes.advisor_admin.get_assigned_pending_student")
    @patch("routes.advisor_admin.require_current_advisor")
    def test_advisor_can_approve_verified_student(
        self,
        mock_require_advisor,
        mock_find_student,
        mock_notification,
        mock_commit
    ):
        advisor, user, student = self.make_student()

        mock_require_advisor.return_value = (advisor, None)
        mock_find_student.return_value = student

        response = self.client.post(
            "/api/academic-admin/students/10/approve",
            json={}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.account_status, "active")
        self.assertEqual(user.reviewed_by_user_id, advisor.id)
        self.assertIsNotNone(user.reviewed_at)
        self.assertIsNone(user.rejection_reason)
        mock_notification.assert_called_once()
        mock_commit.assert_called_once()

    @patch("routes.advisor_admin.db.session.commit")
    @patch("routes.advisor_admin.create_notification")
    @patch("routes.advisor_admin.get_assigned_pending_student")
    @patch("routes.advisor_admin.require_current_advisor")
    def test_advisor_can_reject_verified_student(
        self,
        mock_require_advisor,
        mock_find_student,
        mock_notification,
        mock_commit
    ):
        advisor, user, student = self.make_student()

        mock_require_advisor.return_value = (advisor, None)
        mock_find_student.return_value = student

        response = self.client.post(
            "/api/academic-admin/students/10/reject",
            json={"reason": "Registration details are incorrect"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.account_status, "rejected")
        self.assertEqual(user.reviewed_by_user_id, advisor.id)
        self.assertEqual(
            user.rejection_reason,
            "Registration details are incorrect"
        )
        self.assertIsNotNone(user.reviewed_at)
        mock_notification.assert_called_once()
        mock_commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
