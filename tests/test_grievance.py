import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from app import app


class GrievanceSecurityTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_rejects_unauthenticated_submission(self):
        response = self.client.post(
            '/api/grievances/',
            json={
                'title': 'Test grievance',
                'description': 'Test description',
                'category_id': 1
            }
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Not logged in')

    def test_rejects_non_student_submission(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 2
            session['role'] = 'coordinator'

        response = self.client.post(
            '/api/grievances/',
            json={
                'title': 'Test grievance',
                'description': 'Test description',
                'category_id': 1
            }
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()['error'],
            'Only students can perform this action'
        )

    def test_rejects_missing_student_profile(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 999999
            session['role'] = 'student'

        with patch('routes.grievance.Student.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = None

            response = self.client.post(
                '/api/grievances/',
                json={
                    'title': 'Test grievance',
                    'description': 'Test description',
                    'category_id': 1
                }
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()['error'],
            'Create your student profile first'
        )

    def test_rejects_non_object_json(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_student = MagicMock()
        mock_student.id = 1

        with patch('routes.grievance.Student.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_student

            response = self.client.post(
                '/api/grievances/',
                json=['unexpected']
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Request body must be a JSON object'
        )

    def test_rejects_missing_title(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_student = MagicMock()
        mock_student.id = 1

        with patch('routes.grievance.Student.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_student

            response = self.client.post(
                '/api/grievances/',
                json={
                    'description': 'Test description',
                    'category_id': 1
                }
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'Title is required')

    def test_rejects_title_over_200_characters(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_student = MagicMock()
        mock_student.id = 1

        with patch('routes.grievance.Student.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_student

            response = self.client.post(
                '/api/grievances/',
                json={
                    'title': 'T' * 201,
                    'description': 'Test description',
                    'category_id': 1
                }
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Title must be 200 characters or fewer'
        )

    def test_rejects_missing_description(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_student = MagicMock()
        mock_student.id = 1

        with patch('routes.grievance.Student.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_student

            response = self.client.post(
                '/api/grievances/',
                json={
                    'title': 'Test grievance',
                    'category_id': 1
                }
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Description is required'
        )

    def test_rejects_invalid_category_id(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_student = MagicMock()
        mock_student.id = 1

        with patch('routes.grievance.Student.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_student

            response = self.client.post(
                '/api/grievances/',
                json={
                    'title': 'Test grievance',
                    'description': 'Test description',
                    'category_id': 'invalid'
                }
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'A valid category_id is required'
        )

    def test_rejects_invalid_priority(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_student = MagicMock()
        mock_student.id = 1

        mock_category = MagicMock()
        mock_category.id = 1
        mock_category.is_active = True

        with patch('routes.grievance.Student.query') as mock_query, \
             patch('routes.grievance.db.session.get', return_value=mock_category):

            mock_query.filter_by.return_value.first.return_value = mock_student

            response = self.client.post(
                '/api/grievances/',
                json={
                    'title': 'Test grievance',
                    'description': 'Test description',
                    'category_id': 1,
                    'priority': 'Urgent'
                }
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Priority must be Low, Medium, or High'
        )

    def test_rejects_non_string_location(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_student = MagicMock()
        mock_student.id = 1

        mock_category = MagicMock()
        mock_category.id = 1
        mock_category.is_active = True

        with patch('routes.grievance.Student.query') as mock_query, \
             patch('routes.grievance.db.session.get', return_value=mock_category):

            mock_query.filter_by.return_value.first.return_value = mock_student

            response = self.client.post(
                '/api/grievances/',
                json={
                    'title': 'Test grievance',
                    'description': 'Test description',
                    'category_id': 1,
                    'location': 123
                }
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Location must be text'
        )
    def test_submission_assigns_sla_deadline_for_each_priority(self):
        cases = [
            ("High", datetime(2026, 11, 11, 10, 0, 0)),
            ("Medium", datetime(2026, 11, 12, 10, 0, 0)),
            ("Low", datetime(2026, 11, 13, 10, 0, 0)),
        ]

        for index, (priority, expected_deadline) in enumerate(cases):
            with self.subTest(priority=priority):
                with self.client.session_transaction() as session:
                    session["user_id"] = 1
                    session["role"] = "student"

                student = MagicMock()
                student.id = 1

                category = MagicMock()
                category.id = 1
                category.name = "Infrastructure"
                category.is_active = True

                grievance = MagicMock()
                grievance.id = 100 + index
                grievance.title = "SLA test grievance"
                grievance.priority = priority
                grievance.status = "Submitted"
                grievance.created_at = datetime(
                    2026, 11, 10, 10, 0, 0
                )

                with patch(
                    "routes.grievance.Student.query"
                ) as student_query, patch(
                    "routes.grievance.db.session.get",
                    return_value=category
                ), patch(
                    "routes.grievance.Grievance",
                    return_value=grievance
                ) as grievance_factory, patch(
                    "routes.grievance.calculate_sla_due_at",
                    return_value=expected_deadline
                ) as sla_mock, patch(
                    "routes.grievance.db.session.add"
                ), patch(
                    "routes.grievance.db.session.flush"
                ), patch(
                    "routes.grievance.db.session.commit"
                ), patch(
                    "routes.grievance.User.query"
                ) as user_query, patch(
                    "routes.grievance.create_notification"
                ):
                    student_query.filter_by.return_value.first.return_value = (
                        student
                    )
                    user_query.filter_by.return_value.all.return_value = []

                    response = self.client.post(
                        "/api/grievances/",
                        json={
                            "title": "SLA test grievance",
                            "description": "Testing priority-based SLA",
                            "category_id": 1,
                            "priority": priority
                        }
                    )

                self.assertEqual(response.status_code, 201)

                self.assertEqual(
                    grievance_factory.call_args.kwargs["sla_due_at"],
                    expected_deadline
                )

                sla_mock.assert_called_once_with(priority)


    def test_assignment_updates_legacy_and_current_handler_fields(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "coordinator"

        grievance = MagicMock()
        grievance.id = 10
        grievance.title = "Test grievance"

        advisor = MagicMock()
        advisor.id = 6
        advisor.role = "advisor"

        with patch(
            "routes.grievance.db.session.get",
            side_effect=[grievance, advisor]
        ), patch(
            "routes.grievance.create_notification"
        ) as notification_mock, patch(
            "routes.grievance.db.session.commit"
        ) as commit_mock:

            response = self.client.put(
                "/api/grievances/10/assign",
                json={"advisor_id": 6}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["message"],
                         "Grievance assigned successfully")

        self.assertEqual(grievance.assigned_to, 6)
        self.assertEqual(grievance.current_handler_id, 6)
        self.assertEqual(grievance.current_handler_role, "advisor")

        notification_mock.assert_called_once()
        commit_mock.assert_called_once()


    def test_assignment_rejects_boolean_advisor_id(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'coordinator'

        with patch(
            'routes.grievance.db.session.get'
        ) as mock_get:
            mock_grievance = MagicMock()
            mock_grievance.id = 10

            mock_advisor = MagicMock()
            mock_advisor.id = 1
            mock_advisor.role = 'advisor'

            mock_get.side_effect = [mock_grievance, mock_advisor]

            with patch('routes.grievance.create_notification'), \
                 patch('routes.grievance.db.session.commit'):
                response = self.client.put(
                    '/api/grievances/10/assign',
                    json={'advisor_id': True}
                )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'A valid advisor_id is required'
        )

    def test_resolution_endpoints_reject_unauthenticated_users(self):
        confirm_response = self.client.put(
            "/api/grievances/10/confirm-resolution"
        )
        reopen_response = self.client.put(
            "/api/grievances/10/reopen"
        )

        self.assertEqual(confirm_response.status_code, 401)
        self.assertEqual(reopen_response.status_code, 401)

    def test_confirm_resolution_records_history_and_notifies_staff(self):

        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "student"
        student = MagicMock()
        student.id = 1

        grievance = MagicMock()
        grievance.id = 10
        grievance.student_id = 1
        grievance.title = "Classroom maintenance"
        grievance.status = "Resolved"
        grievance.resolution_confirmed_at = None

        with patch(
            "routes.grievance.require_student",
            return_value=(student, None)
        ), patch(
            "routes.grievance.db.session.get",
            return_value=grievance
        ), patch(
            "routes.grievance.GrievanceUpdate"
        ) as history_factory, patch(
            "routes.grievance.db.session.add"
        ) as add_mock, patch(
            "routes.grievance.notify_grievance_staff"
        ) as notification_mock, patch(
            "routes.grievance.db.session.commit"
        ) as commit_mock:

            response = self.client.put(
                "/api/grievances/10/confirm-resolution"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Grievance resolution confirmed successfully"
        )
        self.assertIsNotNone(grievance.resolution_confirmed_at)

        history_factory.assert_called_once()
        history_data = history_factory.call_args.kwargs
        self.assertEqual(history_data["grievance_id"], 10)
        self.assertEqual(history_data["updated_by"], 1)
        self.assertEqual(history_data["old_status"], "Resolved")
        self.assertEqual(history_data["new_status"], "Resolved")

        add_mock.assert_called_once_with(history_factory.return_value)
        notification_mock.assert_called_once()
        commit_mock.assert_called_once()

    def test_confirm_resolution_is_idempotent(self):
        student = MagicMock()
        student.id = 1

        confirmed_at = datetime(2026, 11, 10, 10, 0, 0)

        grievance = MagicMock()
        grievance.id = 10
        grievance.student_id = 1
        grievance.status = "Resolved"
        grievance.resolution_confirmed_at = confirmed_at

        with patch(
            "routes.grievance.require_student",
            return_value=(student, None)
        ), patch(
            "routes.grievance.db.session.get",
            return_value=grievance
        ), patch(
            "routes.grievance.GrievanceUpdate"
        ) as history_factory, patch(
            "routes.grievance.db.session.add"
        ) as add_mock, patch(
            "routes.grievance.notify_grievance_staff"
        ) as notification_mock, patch(
            "routes.grievance.db.session.commit"
        ) as commit_mock:

            response = self.client.put(
                "/api/grievances/10/confirm-resolution"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Resolution has already been confirmed"
        )
        self.assertEqual(
            response.get_json()["resolution_confirmed_at"],
            confirmed_at.isoformat()
        )

        history_factory.assert_not_called()
        add_mock.assert_not_called()
        notification_mock.assert_not_called()
        commit_mock.assert_not_called()

    def test_reopen_grievance_updates_status_sla_and_history(self):

        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "student"
        student = MagicMock()
        student.id = 1

        old_confirmation = datetime(2026, 11, 10, 10, 0, 0)
        new_deadline = datetime(2026, 11, 12, 10, 0, 0)

        grievance = MagicMock()
        grievance.id = 10
        grievance.student_id = 1
        grievance.title = "Classroom maintenance"
        grievance.priority = "Medium"
        grievance.status = "Resolved"
        grievance.assigned_to = 6
        grievance.resolution_confirmed_at = old_confirmation
        grievance.reopen_count = 2

        with patch(
            "routes.grievance.require_student",
            return_value=(student, None)
        ), patch(
            "routes.grievance.db.session.get",
            return_value=grievance
        ), patch(
            "routes.grievance.calculate_sla_due_at",
            return_value=new_deadline
        ) as sla_mock, patch(
            "routes.grievance.GrievanceUpdate"
        ) as history_factory, patch(
            "routes.grievance.db.session.add"
        ) as add_mock, patch(
            "routes.grievance.notify_grievance_staff"
        ) as notification_mock, patch(
            "routes.grievance.db.session.commit"
        ) as commit_mock:

            response = self.client.put(
                "/api/grievances/10/reopen",
                json={"comment": "The problem is still not fixed."}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Grievance reopened successfully"
        )
        self.assertEqual(grievance.status, "In Progress")
        self.assertIsNone(grievance.resolution_confirmed_at)
        self.assertEqual(grievance.reopen_count, 3)
        self.assertEqual(grievance.sla_due_at, new_deadline)
        self.assertEqual(grievance.current_handler_id, 6)
        self.assertEqual(grievance.current_handler_role, "advisor")

        sla_mock.assert_called_once_with("Medium")

        history_data = history_factory.call_args.kwargs
        self.assertEqual(history_data["old_status"], "Resolved")
        self.assertEqual(history_data["new_status"], "In Progress")
        self.assertEqual(
            history_data["comment"],
            "The problem is still not fixed."
        )

        add_mock.assert_called_once_with(history_factory.return_value)
        notification_mock.assert_called_once()
        commit_mock.assert_called_once()

    def test_reopen_rejects_grievance_that_is_not_resolved(self):
        student = MagicMock()
        student.id = 1

        grievance = MagicMock()
        grievance.id = 10
        grievance.student_id = 1
        grievance.status = "In Progress"

        with patch(
            "routes.grievance.require_student",
            return_value=(student, None)
        ), patch(
            "routes.grievance.db.session.get",
            return_value=grievance
        ):
            response = self.client.put(
                "/api/grievances/10/reopen"
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["error"],
            "Only resolved grievances can be reopened"
        )

    def test_resolution_actions_reject_grievances_owned_by_another_student(self):
        student = MagicMock()
        student.id = 1

        grievance = MagicMock()
        grievance.id = 10
        grievance.student_id = 2

        paths = [
            "/api/grievances/10/confirm-resolution",
            "/api/grievances/10/reopen"
        ]

        for endpoint in paths:
            with self.subTest(endpoint=endpoint):
                with patch(
                    "routes.grievance.require_student",
                    return_value=(student, None)
                ), patch(
                    "routes.grievance.db.session.get",
                    return_value=grievance
                ):
                    response = self.client.put(endpoint)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.get_json()["error"],
                    "Grievance not found"
                )

    def test_reopen_rejects_non_object_json(self):
        student = MagicMock()
        student.id = 1

        grievance = MagicMock()
        grievance.id = 10
        grievance.student_id = 1
        grievance.status = "Resolved"

        with patch(
            "routes.grievance.require_student",
            return_value=(student, None)
        ), patch(
            "routes.grievance.db.session.get",
            return_value=grievance
        ):
            response = self.client.put(
                "/api/grievances/10/reopen",
                json=["invalid"]
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "Request body must be a JSON object"
        )


if __name__ == '__main__':
    unittest.main()