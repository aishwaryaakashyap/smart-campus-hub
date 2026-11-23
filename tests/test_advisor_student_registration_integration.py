import unittest
from datetime import datetime

from flask import Flask

from extensions import db
from models import ActivityLog, AcademicClass, Notification, Student, User
from routes.advisor_admin import advisor_admin_bp


class AdvisorStudentRegistrationIntegrationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            TESTING=True,
            SECRET_KEY="advisor-integration-test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            WTF_CSRF_ENABLED=False,
        )

        db.init_app(cls.app)

        cls.app.register_blueprint(
            advisor_admin_bp,
            url_prefix="/api/academic-admin"
        )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()

        self.test_tables = [
            User.__table__,
            AcademicClass.__table__,
            Student.__table__,
            Notification.__table__,
            ActivityLog.__table__,
        ]

        db.metadata.create_all(
            bind=db.engine,
            tables=self.test_tables
        )

        self.client = self.app.test_client()

        self.advisor_a = self.create_user(
            "advisor",
            "advisor.a@example.com"
        )
        self.advisor_b = self.create_user(
            "advisor",
            "advisor.b@example.com"
        )

        self.class_a = self.create_class(
            "A",
            self.advisor_a.id
        )
        self.class_b = self.create_class(
            "B",
            self.advisor_b.id
        )

        self.inactive_class_a = self.create_class(
            "C",
            self.advisor_a.id,
            is_active=False
        )

        db.session.commit()

    def tearDown(self):
        db.session.remove()

        db.metadata.drop_all(
            bind=db.engine,
            tables=list(reversed(self.test_tables))
        )

        self.context.pop()

    def create_user(
        self,
        role,
        email,
        account_status="active",
        email_verified_at=None
    ):
        user = User(
            name=email.split("@")[0],
            email=email,
            password_hash="integration-test-password-hash",
            role=role,
            account_status=account_status,
            email_verified_at=email_verified_at,
        )

        db.session.add(user)
        db.session.flush()

        return user

    def create_class(
        self,
        section,
        advisor_id,
        is_active=True
    ):
        academic_class = AcademicClass(
            course="BCA",
            branch="Computer Applications",
            section=section,
            admission_year=2024,
            advisor_user_id=advisor_id,
            is_active=is_active,
        )

        db.session.add(academic_class)
        db.session.flush()

        return academic_class

    def create_student(
        self,
        academic_class,
        register_number,
        account_status="pending",
        email_verified=True
    ):
        verified_at = (
            datetime(2026, 11, 20, 10, 0, 0)
            if email_verified else None
        )

        user = self.create_user(
            "student",
            f"{register_number.lower()}@my.students.amrita.edu",
            account_status=account_status,
            email_verified_at=verified_at,
        )

        student = Student(
            user_id=user.id,
            register_number=register_number,
            course="BCA",
            branch="Computer Applications",
            semester=5,
            academic_class_id=academic_class.id,
        )

        db.session.add(student)
        db.session.flush()

        return student

    def login_as_advisor(self, advisor):
        with self.client.session_transaction() as session:
            session["user_id"] = advisor.id
            session["role"] = "advisor"

    def test_advisor_list_only_contains_verified_pending_students_in_own_active_classes(self):
        own_pending = self.create_student(
            self.class_a,
            "OWN001",
            account_status="pending",
            email_verified=True
        )

        self.create_student(
            self.class_a,
            "UNVER001",
            account_status="pending",
            email_verified=False
        )

        self.create_student(
            self.class_a,
            "ACTIVE001",
            account_status="active",
            email_verified=True
        )

        self.create_student(
            self.class_b,
            "OTHER001",
            account_status="pending",
            email_verified=True
        )

        self.create_student(
            self.inactive_class_a,
            "INACTIVE001",
            account_status="pending",
            email_verified=True
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.get(
            "/api/academic-admin/students/registrations"
        )

        self.assertEqual(response.status_code, 200)

        result = response.get_json()

        self.assertEqual(result["total"], 1)
        self.assertEqual(
            [item["student_id"] for item in result["students"]],
            [own_pending.id]
        )

    def test_advisor_cannot_approve_another_advisors_student(self):
        student = self.create_student(
            self.class_b,
            "OTHER002"
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.post(
            f"/api/academic-admin/students/{student.id}/approve",
            json={}
        )

        self.assertEqual(response.status_code, 404)

        db.session.refresh(student.user)

        self.assertEqual(
            student.user.account_status,
            User.STATUS_PENDING
        )

        self.assertEqual(
            db.session.query(Notification).count(),
            0
        )

    def test_advisor_cannot_reject_another_advisors_student(self):
        student = self.create_student(
            self.class_b,
            "OTHER003"
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.post(
            f"/api/academic-admin/students/{student.id}/reject",
            json={"reason": "Test rejection"}
        )

        self.assertEqual(response.status_code, 404)

        db.session.refresh(student.user)

        self.assertEqual(
            student.user.account_status,
            User.STATUS_PENDING
        )

        self.assertEqual(
            db.session.query(Notification).count(),
            0
        )

    def test_advisor_cannot_review_student_in_inactive_class(self):
        student = self.create_student(
            self.inactive_class_a,
            "INACTIVE002"
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.post(
            f"/api/academic-admin/students/{student.id}/approve",
            json={}
        )

        self.assertEqual(response.status_code, 404)

        db.session.refresh(student.user)

        self.assertEqual(
            student.user.account_status,
            User.STATUS_PENDING
        )

    def test_advisor_can_approve_verified_student_in_own_class(self):
        student = self.create_student(
            self.class_a,
            "APPROVE001"
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.post(
            f"/api/academic-admin/students/{student.id}/approve",
            json={}
        )

        self.assertEqual(response.status_code, 200)

        db.session.refresh(student.user)

        self.assertEqual(
            student.user.account_status,
            User.STATUS_ACTIVE
        )
        self.assertEqual(
            student.user.reviewed_by_user_id,
            self.advisor_a.id
        )
        self.assertIsNotNone(student.user.reviewed_at)
        self.assertIsNone(student.user.rejection_reason)

        notification = db.session.query(Notification).filter_by(
            user_id=student.user_id
        ).one()

        self.assertEqual(
            notification.title,
            "Student registration approved"
        )

    def test_advisor_can_reject_verified_student_in_own_class(self):
        student = self.create_student(
            self.class_a,
            "REJECT001"
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.post(
            f"/api/academic-admin/students/{student.id}/reject",
            json={"reason": "Registration details are incorrect"}
        )

        self.assertEqual(response.status_code, 200)

        db.session.refresh(student.user)

        self.assertEqual(
            student.user.account_status,
            User.STATUS_REJECTED
        )
        self.assertEqual(
            student.user.reviewed_by_user_id,
            self.advisor_a.id
        )
        self.assertEqual(
            student.user.rejection_reason,
            "Registration details are incorrect"
        )
        self.assertIsNotNone(student.user.reviewed_at)

        notification = db.session.query(Notification).filter_by(
            user_id=student.user_id
        ).one()

        self.assertEqual(
            notification.title,
            "Student registration update"
        )
        self.assertIn(
            "Registration details are incorrect",
            notification.message
        )

    def test_unverified_student_cannot_be_approved(self):
        student = self.create_student(
            self.class_a,
            "UNVER002",
            email_verified=False
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.post(
            f"/api/academic-admin/students/{student.id}/approve",
            json={}
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "verify their email",
            response.get_json()["error"]
        )

        db.session.refresh(student.user)

        self.assertEqual(
            student.user.account_status,
            User.STATUS_PENDING
        )

    def test_already_active_student_cannot_be_approved_again(self):
        student = self.create_student(
            self.class_a,
            "ACTIVE002",
            account_status="active"
        )

        db.session.commit()
        self.login_as_advisor(self.advisor_a)

        response = self.client.post(
            f"/api/academic-admin/students/{student.id}/approve",
            json={}
        )

        self.assertEqual(response.status_code, 409)

        db.session.refresh(student.user)

        self.assertEqual(
            student.user.account_status,
            User.STATUS_ACTIVE
        )


if __name__ == "__main__":
    unittest.main()
