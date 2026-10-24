import unittest
from unittest.mock import MagicMock, patch

from app import app


class NotificationIntegrationTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.client = app.test_client()

    def set_session(self, user_id, role):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id
            session['role'] = role

    def test_placement_status_change_notifies_correct_student(self):
        self.set_session(202, 'coordinator')

        application = MagicMock()
        application.status = 'Applied'
        application.remarks = None
        application.student.user_id = 101
        application.drive.job_role = 'Python Developer'

        with patch(
            'routes.application.db.session.get',
            return_value=application
        ), patch(
            'routes.application.create_notification'
        ) as notify, patch(
            'routes.application.db.session.commit'
        ) as commit:

            response = self.client.put(
                '/api/applications/1/status',
                json={'status': 'Shortlisted'}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(application.status, 'Shortlisted')
        notify.assert_called_once_with(
            user_id=101,
            title='Placement Application Update',
            message=(
                'Your application for Python Developer '
                'has been updated from Applied to Shortlisted.'
            ),
            notification_type='placement_status'
        )
        commit.assert_called_once()

    def test_unchanged_placement_status_does_not_notify(self):
        self.set_session(202, 'coordinator')

        application = MagicMock()
        application.status = 'Applied'
        application.remarks = None
        application.student.user_id = 101
        application.drive.job_role = 'Python Developer'

        with patch(
            'routes.application.db.session.get',
            return_value=application
        ), patch(
            'routes.application.create_notification'
        ) as notify, patch(
            'routes.application.db.session.commit'
        ) as commit:

            response = self.client.put(
                '/api/applications/1/status',
                json={'status': 'Applied'}
            )

        self.assertEqual(response.status_code, 200)
        notify.assert_not_called()
        commit.assert_called_once()

    def test_grievance_status_change_notifies_submitting_student(self):
        self.set_session(202, 'coordinator')

        grievance = MagicMock()
        grievance.id = 10
        grievance.title = 'Broken classroom fan'
        grievance.status = 'In Progress'
        grievance.student.user_id = 101

        with patch(
            'routes.grievance.db.session.get',
            return_value=grievance
        ), patch(
            'routes.grievance.create_notification'
        ) as notify, patch(
            'routes.grievance.db.session.add'
        ), patch(
            'routes.grievance.db.session.commit'
        ) as commit:

            response = self.client.put(
                '/api/grievances/10/status',
                json={'status': 'Resolved'}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(grievance.status, 'Resolved')
        notify.assert_called_once_with(
            user_id=101,
            title='Grievance Resolved',
            message=(
                'Your grievance "Broken classroom fan" '
                'has been resolved.'
            ),
            notification_type='grievance'
        )
        commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()


class GrievanceNotificationIntegrationTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)
        self.client = app.test_client()

    def set_session(self, user_id, role):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id
            session['role'] = role

    def test_submission_notifies_all_coordinators(self):
        from datetime import datetime

        self.set_session(101, 'student')

        student = MagicMock()
        student.id = 1

        category = MagicMock()
        category.id = 2
        category.name = 'Infrastructure'
        category.is_active = True

        coordinator_one = MagicMock()
        coordinator_one.id = 202
        coordinator_two = MagicMock()
        coordinator_two.id = 203

        with patch(
            'routes.grievance.Student.query'
        ) as student_query, patch(
            'routes.grievance.db.session.get',
            return_value=category
        ), patch(
            'routes.grievance.User.query'
        ) as user_query, patch(
            'routes.grievance.db.session.add'
        ), patch(
            'routes.grievance.db.session.flush'
        ), patch(
            'routes.grievance.db.session.commit'
        ) as commit, patch(
            'routes.grievance.create_notification'
        ) as notify:

            student_query.filter_by.return_value.first.return_value = student
            user_query.filter_by.return_value.all.return_value = [
                coordinator_one, coordinator_two
            ]

            with patch(
                'routes.grievance.Grievance'
            ) as grievance_model:
                grievance = MagicMock()
                grievance.id = 10
                grievance.created_at = datetime(2026, 10, 24)
                grievance.status = 'Submitted'
                grievance.title = 'Broken classroom fan'
                grievance.priority = 'Medium'
                grievance.location = None
                grievance_model.return_value = grievance

                response = self.client.post(
                    '/api/grievances/',
                    json={
                        'title': 'Broken classroom fan',
                        'description': 'The fan is not working.',
                        'category_id': 2
                    }
                )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(notify.call_count, 2)
        notify.assert_any_call(
            user_id=202,
            title='New Grievance Submitted',
            message='A new grievance "Broken classroom fan" has been submitted.',
            notification_type='grievance'
        )
        notify.assert_any_call(
            user_id=203,
            title='New Grievance Submitted',
            message='A new grievance "Broken classroom fan" has been submitted.',
            notification_type='grievance'
        )
        commit.assert_called_once()

    def test_assignment_notifies_selected_advisor(self):
        self.set_session(202, 'coordinator')

        grievance = MagicMock()
        grievance.id = 10
        grievance.title = 'Broken classroom fan'

        advisor = MagicMock()
        advisor.id = 303
        advisor.role = 'advisor'

        with patch(
            'routes.grievance.db.session.get',
            side_effect=[grievance, advisor]
        ), patch(
            'routes.grievance.create_notification'
        ) as notify, patch(
            'routes.grievance.db.session.commit'
        ) as commit:

            response = self.client.put(
                '/api/grievances/10/assign',
                json={'advisor_id': 303}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(grievance.assigned_to, 303)
        notify.assert_called_once_with(
            user_id=303,
            title='Grievance Assigned to You',
            message='Grievance "Broken classroom fan" has been assigned to you.',
            notification_type='grievance'
        )
        commit.assert_called_once()
