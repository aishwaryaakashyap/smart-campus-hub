import unittest
from unittest.mock import patch, MagicMock

from app import app


class GrievanceSecurityTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
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


if __name__ == '__main__':
    unittest.main()