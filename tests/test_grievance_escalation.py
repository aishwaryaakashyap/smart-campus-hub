import unittest
from datetime import datetime, timedelta
from flask import Flask

from extensions import db
from models import (
    AcademicClass,
    ChairpersonSettings,
    Grievance,
    GrievanceCategory,
    GrievanceEscalation,
    Notification,
    Student,
    User,
)
from services.grievance_escalation import escalate_overdue_grievances


class GrievanceEscalationIntegrationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            TESTING=True,
            SECRET_KEY="grievance-escalation-test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )

        db.init_app(cls.app)

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
            GrievanceCategory.__table__,
            Grievance.__table__,
            GrievanceEscalation.__table__,
            Notification.__table__,
            ChairpersonSettings.__table__,
        ]

        db.metadata.create_all(
            bind=db.engine,
            tables=self.test_tables
        )

        self.advisor = self.create_user(
            "advisor",
            "advisor@example.com"
        )
        self.student_user = self.create_user(
            "student",
            "student@example.com"
        )
        self.chairperson = self.create_user(
            "chairperson",
            "chairperson@example.com"
        )

        self.student = Student(
            user_id=self.student_user.id,
            register_number="ESC-TEST-001"
        )
        self.category = GrievanceCategory(
            name="Escalation Test Category"
        )

        db.session.add_all([self.student, self.category])
        db.session.flush()

        self.now = datetime(2026, 11, 21, 10, 0, 0)
        db.session.commit()

    def tearDown(self):
        db.session.remove()

        db.metadata.drop_all(
            bind=db.engine,
            tables=list(reversed(self.test_tables))
        )

        self.context.pop()

    def create_user(self, role, email, account_status="active"):
        user = User(
            name=email.split("@")[0],
            email=email,
            password_hash="integration-test-password-hash",
            role=role,
            account_status=account_status,
        )
        db.session.add(user)
        db.session.flush()
        return user

    def configure_primary_chairperson(self, user=None):
        settings = ChairpersonSettings(
            singleton_id=1,
            primary_chairperson_user_id=(
                user.id if user else None
            )
        )
        db.session.add(settings)
        db.session.commit()
        return settings

    def create_assigned_grievance(
        self,
        title="Overdue grievance",
        due_at=None,
        status="In Progress"
    ):
        grievance = Grievance(
            student_id=self.student.id,
            category_id=self.category.id,
            title=title,
            description="Integration test grievance",
            priority="Medium",
            status=status,
            assigned_to=self.advisor.id,
            current_handler_id=self.advisor.id,
            current_handler_role=User.ROLE_ADVISOR,
            sla_due_at=(
                due_at if due_at is not None
                else self.now - timedelta(minutes=1)
            ),
            escalation_level=0,
        )
        db.session.add(grievance)
        db.session.commit()
        return grievance

    def test_overdue_grievance_escalates_to_primary_chairperson(self):
        self.configure_primary_chairperson(self.chairperson)
        grievance = self.create_assigned_grievance()

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(grievance)

        self.assertEqual(result, 1)
        self.assertEqual(grievance.assigned_to, self.advisor.id)
        self.assertEqual(
            grievance.current_handler_id,
            self.chairperson.id
        )
        self.assertEqual(
            grievance.current_handler_role,
            User.ROLE_CHAIRPERSON
        )
        self.assertEqual(grievance.escalation_level, 1)
        self.assertEqual(grievance.last_escalated_at, self.now)
        self.assertIsNone(grievance.sla_due_at)

        event = GrievanceEscalation.query.filter_by(
            grievance_id=grievance.id
        ).one()

        self.assertEqual(event.from_user_id, self.advisor.id)
        self.assertEqual(event.to_user_id, self.chairperson.id)
        self.assertEqual(event.from_role, User.ROLE_ADVISOR)
        self.assertEqual(event.to_role, User.ROLE_CHAIRPERSON)
        self.assertEqual(event.escalation_level, 1)
        self.assertEqual(
            event.sla_due_at,
            self.now - timedelta(minutes=1)
        )
        self.assertIsNone(event.triggered_by_user_id)

        notification = Notification.query.filter_by(
            user_id=self.chairperson.id
        ).one()

        self.assertEqual(
            notification.title,
            "Grievance Escalated to You"
        )
        self.assertEqual(notification.notification_type, "grievance")

    def test_grievance_without_sla_deadline_is_not_escalated(self):
        self.configure_primary_chairperson(self.chairperson)
        grievance = self.create_assigned_grievance(due_at=None)
        grievance.sla_due_at = None
        db.session.commit()

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(grievance)

        self.assertEqual(result, 0)
        self.assertEqual(
            grievance.current_handler_id,
            self.advisor.id
        )
        self.assertEqual(
            grievance.current_handler_role,
            User.ROLE_ADVISOR
        )
        self.assertEqual(grievance.escalation_level, 0)
        self.assertIsNone(grievance.sla_due_at)
        self.assertEqual(GrievanceEscalation.query.count(), 0)
        self.assertEqual(
            Notification.query.filter_by(
                user_id=self.chairperson.id
            ).count(),
            0
        )

    def test_grievance_is_not_escalated_before_deadline(self):
        self.configure_primary_chairperson(self.chairperson)
        grievance = self.create_assigned_grievance(
            due_at=self.now + timedelta(seconds=1)
        )

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(grievance)

        self.assertEqual(result, 0)
        self.assertEqual(
            grievance.current_handler_id,
            self.advisor.id
        )
        self.assertEqual(grievance.escalation_level, 0)
        self.assertEqual(
            GrievanceEscalation.query.count(),
            0
        )

    def test_missing_primary_chairperson_leaves_grievance_eligible(self):
        grievance = self.create_assigned_grievance()

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(grievance)

        self.assertEqual(result, 0)
        self.assertEqual(
            grievance.current_handler_id,
            self.advisor.id
        )
        self.assertEqual(grievance.escalation_level, 0)
        self.assertEqual(
            GrievanceEscalation.query.count(),
            0
        )

    def test_inactive_primary_does_not_fall_back_to_another_chairperson(self):
        inactive_primary = self.create_user(
            "chairperson",
            "inactive-primary@example.com",
            account_status="deactivated"
        )
        other_active_chairperson = self.create_user(
            "chairperson",
            "other-chairperson@example.com"
        )

        self.configure_primary_chairperson(inactive_primary)
        grievance = self.create_assigned_grievance()

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(grievance)

        self.assertEqual(result, 0)
        self.assertNotEqual(
            grievance.current_handler_id,
            other_active_chairperson.id
        )
        self.assertEqual(
            grievance.current_handler_id,
            self.advisor.id
        )
        self.assertEqual(grievance.escalation_level, 0)
        self.assertEqual(
            GrievanceEscalation.query.count(),
            0
        )

    def test_resolved_and_rejected_grievances_are_not_escalated(self):
        self.configure_primary_chairperson(self.chairperson)

        resolved = self.create_assigned_grievance(
            title="Already resolved",
            status="Resolved"
        )
        rejected = self.create_assigned_grievance(
            title="Already rejected",
            status="Rejected"
        )

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(resolved)
        db.session.refresh(rejected)

        self.assertEqual(result, 0)

        for grievance in (resolved, rejected):
            self.assertEqual(
                grievance.current_handler_id,
                self.advisor.id
            )
            self.assertEqual(grievance.escalation_level, 0)

        self.assertEqual(
            GrievanceEscalation.query.count(),
            0
        )

    def test_repeated_runs_do_not_create_duplicate_escalations(self):
        self.configure_primary_chairperson(self.chairperson)
        grievance = self.create_assigned_grievance()

        first_result = escalate_overdue_grievances(now=self.now)
        second_result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(grievance)

        self.assertEqual(first_result, 1)
        self.assertEqual(second_result, 0)
        self.assertEqual(grievance.escalation_level, 1)
        self.assertEqual(
            GrievanceEscalation.query.filter_by(
                grievance_id=grievance.id
            ).count(),
            1
        )
        self.assertEqual(
            Notification.query.filter_by(
                user_id=self.chairperson.id
            ).count(),
            1
        )


    def test_primary_account_with_wrong_role_is_rejected(self):
        self.configure_primary_chairperson(self.advisor)
        grievance = self.create_assigned_grievance()

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(grievance)

        self.assertEqual(result, 0)
        self.assertEqual(
            grievance.current_handler_id,
            self.advisor.id
        )
        self.assertEqual(grievance.escalation_level, 0)
        self.assertEqual(GrievanceEscalation.query.count(), 0)
        self.assertEqual(Notification.query.count(), 0)

    def test_multiple_overdue_grievances_all_escalate(self):
        self.configure_primary_chairperson(self.chairperson)

        first = self.create_assigned_grievance(
            title="First overdue grievance"
        )
        second = self.create_assigned_grievance(
            title="Second overdue grievance",
            due_at=self.now - timedelta(hours=2)
        )

        result = escalate_overdue_grievances(now=self.now)

        db.session.refresh(first)
        db.session.refresh(second)

        self.assertEqual(result, 2)

        for grievance in (first, second):
            self.assertEqual(
                grievance.current_handler_id,
                self.chairperson.id
            )
            self.assertEqual(
                grievance.current_handler_role,
                User.ROLE_CHAIRPERSON
            )
            self.assertEqual(grievance.escalation_level, 1)

        self.assertEqual(GrievanceEscalation.query.count(), 2)
        self.assertEqual(
            Notification.query.filter_by(
                user_id=self.chairperson.id
            ).count(),
            2
        )


if __name__ == "__main__":
    unittest.main()
