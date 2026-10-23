
import unittest
from unittest.mock import patch, MagicMock

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


if __name__ == '__main__':
    unittest.main()
