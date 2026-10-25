import unittest
from unittest.mock import patch

from app import app


class AuthRegistrationTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_rejects_privileged_role(self):
        response = self.client.post(
            '/api/auth/register',
            json={
                'name': 'Security Test',
                'email': 'security-test@example.com',
                'password': 'TestPass123',
                'role': 'coordinator'
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('student', response.get_json()['error'])

    def test_rejects_short_password(self):
        response = self.client.post(
            '/api/auth/register',
            json={
                'name': 'Test Student',
                'email': 'test@example.com',
                'password': '123',
                'role': 'student'
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Password must be at least 8 characters long'
        )

    def test_rejects_blank_email(self):
        response = self.client.post(
            '/api/auth/register',
            json={
                'name': 'Test Student',
                'email': '   ',
                'password': 'TestPass123',
                'role': 'student'
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Name and email cannot be blank'
        )

    def test_rejects_non_string_name(self):
        response = self.client.post(
            '/api/auth/register',
            json={
                'name': 123,
                'email': 'test@example.com',
                'password': 'TestPass123',
                'role': 'student'
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Name, email, and password must be strings'
        )

    def test_rejects_privileged_role_before_database_write(self):
        with patch('routes.auth.db.session.add') as mock_add, \
             patch('routes.auth.db.session.commit') as mock_commit:

            response = self.client.post(
                '/api/auth/register',
                json={
                    'name': 'Security Test',
                    'email': 'security-test@example.com',
                    'password': 'TestPass123',
                    'role': 'coordinator'
                }
            )

        self.assertEqual(response.status_code, 400)
        mock_add.assert_not_called()
        mock_commit.assert_not_called()


class AuthLoginTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_rejects_missing_password(self):
        response = self.client.post(
            '/api/auth/login',
            json={'email': 'test@example.com'}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'Email and password are required'
        )

    def test_rejects_malformed_json_object(self):
        response = self.client.post(
            '/api/auth/login',
            json=['unexpected']
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['error'],
            'A valid JSON object is required'
        )

    def test_rejects_invalid_credentials(self):
        with app.app_context():
            with patch(
                'routes.auth.User.query',
                create=True
            ) as mock_query:
                mock_query.filter_by.return_value.first.return_value = None

                response = self.client.post(
                    '/api/auth/login',
                    json={
                        'email': 'missing-user@example.com',
                        'password': 'WrongPass123'
                    }
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json()['error'],
            'Invalid email or password'
        )

    def test_logout_clears_session(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        response = self.client.post('/api/auth/logout')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()['message'],
            'Logged out successfully'
        )

        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
            self.assertNotIn('role', session)


if __name__ == '__main__':
    unittest.main()


class StudentDashboardTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_unauthenticated_user_redirected(self):
        response = self.client.get(
            '/api/auth/student-dashboard'
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            '/api/auth/login-page',
            response.headers['Location']
        )

    def test_student_can_access_dashboard(self):
        mock_user = type(
            'MockUser',
            (),
            {
                'id': 1,
                'role': 'student',
                'name': 'Test Student'
            }
        )()

        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        with patch(
            'routes.auth.db.session.get',
            return_value=mock_user
        ):
            response = self.client.get(
                '/api/auth/student-dashboard'
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b'Test Student',
            response.data
        )

    def test_coordinator_cannot_access_student_dashboard(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 2
            session['role'] = 'coordinator'

        response = self.client.get(
            '/api/auth/student-dashboard'
        )

        self.assertEqual(response.status_code, 403)

    def test_missing_user_redirects_and_clears_session(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 999
            session['role'] = 'student'

        with patch(
            'routes.auth.db.session.get',
            return_value=None
        ):
            response = self.client.get(
                '/api/auth/student-dashboard'
            )

        self.assertEqual(response.status_code, 302)

        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
            self.assertNotIn('role', session)
