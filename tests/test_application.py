
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import app


class ApplicationValidationTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.client = app.test_client()

        with self.client.session_transaction() as session:
            session['user_id'] = 101
            session['role'] = 'student'

        self.student_lookup = patch(
            'routes.application.Student.query'
        )
        self.mock_student_query = self.student_lookup.start()

        self.mock_student_query.filter_by.return_value.first.return_value = (
            MagicMock(id=101, user_id=101)
        )

        self.addCleanup(self.student_lookup.stop)

    def test_rejects_request_without_json_content_type(self):
        response = self.client.post(
            '/api/applications/',
            data='drive_id=1',
            content_type='application/x-www-form-urlencoded'
        )
        self.assertEqual(response.status_code, 415)

    def test_rejects_malformed_json(self):
        response = self.client.post(
            '/api/applications/',
            data='{"drive_id":',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_json_array(self):
        response = self.client.post(
            '/api/applications/',
            json=[{'drive_id': 1}]
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_missing_drive_id(self):
        response = self.client.post(
            '/api/applications/',
            json={}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_string_drive_id(self):
        response = self.client.post(
            '/api/applications/',
            json={'drive_id': '1'}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_boolean_drive_id(self):
        response = self.client.post(
            '/api/applications/',
            json={'drive_id': True}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_positive_drive_id(self):
        for drive_id in (0, -1):
            with self.subTest(drive_id=drive_id):
                response = self.client.post(
                    '/api/applications/',
                    json={'drive_id': drive_id}
                )
                self.assertEqual(response.status_code, 400)

    def test_duplicate_integrity_error_returns_409(self):
        drive = MagicMock(id=1, status='Open')

        duplicate_error = IntegrityError(
            'INSERT INTO applications',
            {},
            Exception(1062)
        )

        with patch(
            'routes.application.db.session.get',
            return_value=drive
        ), patch(
            'routes.application.Application.query'
        ) as mock_query, patch(
            'routes.application.check_eligibility',
            return_value=(True, [])
        ), patch(
            'routes.application.db.session.add'
        ), patch(
            'routes.application.db.session.commit',
            side_effect=duplicate_error
        ), patch(
            'routes.application.db.session.rollback'
        ) as mock_rollback:

            mock_query.filter_by.return_value.first.return_value = None

            response = self.client.post(
                '/api/applications/',
                json={'drive_id': 1}
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()['error'],
            'You have already applied for this drive'
        )
        mock_rollback.assert_called_once()

    def test_other_integrity_error_returns_500(self):
        drive = MagicMock(id=1, status='Open')

        integrity_error = IntegrityError(
            'INSERT INTO applications',
            {},
            Exception(1452)
        )

        with patch(
            'routes.application.db.session.get',
            return_value=drive
        ), patch(
            'routes.application.Application.query'
        ) as mock_query, patch(
            'routes.application.check_eligibility',
            return_value=(True, [])
        ), patch(
            'routes.application.db.session.add'
        ), patch(
            'routes.application.db.session.commit',
            side_effect=integrity_error
        ), patch(
            'routes.application.db.session.rollback'
        ) as mock_rollback:

            mock_query.filter_by.return_value.first.return_value = None

            response = self.client.post(
                '/api/applications/',
                json={'drive_id': 1}
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json()['error'],
            'Unable to submit application at this time'
        )
        mock_rollback.assert_called_once()


class ApplicationStatusValidationTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.client = app.test_client()

        with self.client.session_transaction() as session:
            session['user_id'] = 202
            session['role'] = 'coordinator'

    def test_rejects_invalid_status(self):
        mock_application = MagicMock()
        mock_application.status = 'Applied'
        mock_application.remarks = None

        with patch(
            'routes.application.db.session.get',
            return_value=mock_application
        ):
            response = self.client.put(
                '/api/applications/1/status',
                json={'status': 'Invalid Status'}
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Invalid status'
        )

    def test_rejects_non_string_status(self):
        mock_application = MagicMock()
        mock_application.status = 'Applied'
        mock_application.remarks = None

        with patch(
            'routes.application.db.session.get',
            return_value=mock_application
        ):
            response = self.client.put(
                '/api/applications/1/status',
                json={'status': 123}
            )

        self.assertEqual(response.status_code, 400)

    def test_rejects_non_string_remarks(self):
        mock_application = MagicMock()
        mock_application.status = 'Applied'
        mock_application.remarks = None

        with patch(
            'routes.application.db.session.get',
            return_value=mock_application
        ):
            response = self.client.put(
                '/api/applications/1/status',
                json={
                    'status': 'Shortlisted',
                    'remarks': 123
                }
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'remarks must be a string or null'
        )


class CoordinatorApplicationListTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.client = app.test_client()

    def test_rejects_unauthenticated_request(self):
        response = self.client.get(
            '/api/applications/manage'
        )

        self.assertEqual(response.status_code, 401)

    def test_rejects_student_access(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 101
            session['role'] = 'student'

        response = self.client.get(
            '/api/applications/manage'
        )

        self.assertEqual(response.status_code, 403)

    def test_coordinator_can_view_applications(self):

        with self.client.session_transaction() as session:
            session['user_id'] = 202
            session['role'] = 'coordinator'

        application = MagicMock()
        application.id = 1
        application.status = 'Applied'
        application.remarks = None
        application.applied_date = datetime(2026, 11, 2)

        application.student.register_number = 'TEST001'
        application.student.branch = 'BCA'
        application.student.semester = 5
        application.student.cgpa = 7.67
        application.student.user.name = 'Test Student'
        application.student.user.email = 'student@example.com'

        application.drive.job_role = 'Python Developer'
        application.drive.company.name = 'Test Company'

        with patch(
            'routes.application.Application.query'
        ) as mock_query:

            mock_query.order_by.return_value.all.return_value = [
                application
            ]

            response = self.client.get(
                '/api/applications/manage'
            )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['student_name'], 'Test Student')
        self.assertEqual(data[0]['student_email'], 'student@example.com')
        self.assertEqual(data[0]['register_number'], 'TEST001')
        self.assertEqual(data[0]['branch'], 'BCA')
        self.assertEqual(data[0]['semester'], 5)
        self.assertEqual(data[0]['cgpa'], 7.67)
        self.assertEqual(data[0]['company_name'], 'Test Company')
        self.assertEqual(data[0]['job_role'], 'Python Developer')
        self.assertEqual(data[0]['status'], 'Applied')


if __name__ == '__main__':
    unittest.main()
