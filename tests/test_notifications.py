import unittest
from unittest.mock import patch, MagicMock

from app import app


class NotificationSecurityTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_rejects_unauthenticated_list(self):
        response = self.client.get('/api/notifications/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Not logged in')

    def test_rejects_unauthenticated_mark_read(self):
        response = self.client.put('/api/notifications/1/read')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Not logged in')

    def test_clears_stale_session_when_listing(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 999999
            session['role'] = 'student'

        with patch('routes.notifications.db.session.get', return_value=None):
            response = self.client.get('/api/notifications/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Not logged in')

        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
            self.assertNotIn('role', session)

    def test_clears_stale_session_when_marking_read(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 999999
            session['role'] = 'student'

        with patch('routes.notifications.db.session.get', return_value=None):
            response = self.client.put('/api/notifications/1/read')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Not logged in')

        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
            self.assertNotIn('role', session)

    def test_rejects_notification_not_owned_by_user(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 2
            session['role'] = 'coordinator'

        mock_user = MagicMock()
        mock_user.id = 2

        with patch(
            'routes.notifications.db.session.get',
            return_value=mock_user
        ), patch(
            'routes.notifications.Notification.query'
        ) as mock_query, patch(
            'routes.notifications.db.session.commit'
        ) as mock_commit:

            mock_query.filter_by.return_value.first.return_value = None

            response = self.client.put('/api/notifications/1/read')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()['error'],
            'Notification not found'
        )
        mock_commit.assert_not_called()

    def test_marks_owned_notification_as_read(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'student'

        mock_user = MagicMock()
        mock_user.id = 1

        mock_notification = MagicMock()
        mock_notification.id = 5
        mock_notification.is_read = False

        with patch(
            'routes.notifications.db.session.get',
            return_value=mock_user
        ), patch(
            'routes.notifications.Notification.query'
        ) as mock_query, patch(
            'routes.notifications.db.session.commit'
        ) as mock_commit:

            mock_query.filter_by.return_value.first.return_value = (
                mock_notification
            )

            response = self.client.put('/api/notifications/5/read')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_notification.is_read)
        mock_commit.assert_called_once()

        self.assertEqual(
            response.get_json()['message'],
            'Notification marked as read'
        )
        self.assertEqual(
            response.get_json()['notification_id'],
            5
        )


if __name__ == '__main__':
    unittest.main()
