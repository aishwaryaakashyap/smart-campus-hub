
import unittest
from unittest.mock import MagicMock, patch

from flask import session
from sqlalchemy.exc import IntegrityError

from app import app


class CompanyRouteTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.client = app.test_client()

        self.current_user_patcher = patch(
            "routes.company.get_session_user",
            side_effect=lambda user_id: type(
                "SessionUser", (), {"role": session.get("role")}
            )()
        )
        self.current_user_patcher.start()
        self.addCleanup(self.current_user_patcher.stop)

    def set_session(self, user_id=1, role='coordinator'):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id
            session['role'] = role

    # ---------------- CREATE COMPANY ----------------

    def test_rejects_unauthenticated_company_creation(self):
        response = self.client.post(
            '/api/companies/',
            json={'name': 'Google'}
        )

        self.assertEqual(response.status_code, 401)

    def test_rejects_student_company_creation(self):
        self.set_session(role='student')

        response = self.client.post(
            '/api/companies/',
            json={'name': 'Google'}
        )

        self.assertEqual(response.status_code, 403)

    def test_stale_coordinator_session_is_cleared_after_role_change(self):
        self.set_session(user_id=99, role='coordinator')

        current_user = MagicMock()
        current_user.role = 'student'

        with patch(
            'routes.company.get_session_user',
            return_value=current_user
        ):
            response = self.client.post(
                '/api/companies/',
                json={'name': 'Google'}
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Not logged in')

        with self.client.session_transaction() as current_session:
            self.assertNotIn('user_id', current_session)
            self.assertNotIn('role', current_session)

    def test_rejects_invalid_company_json(self):
        self.set_session()

        response = self.client.post(
            '/api/companies/',
            json=['Google']
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_missing_company_name(self):
        self.set_session()

        response = self.client.post(
            '/api/companies/',
            json={}
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_blank_company_name(self):
        self.set_session()

        response = self.client.post(
            '/api/companies/',
            json={'name': '   '}
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_non_string_company_name(self):
        self.set_session()

        response = self.client.post(
            '/api/companies/',
            json={'name': 123}
        )

        self.assertEqual(response.status_code, 400)

    @patch('routes.company.Company')
    def test_successfully_creates_company(self, company_model):
        self.set_session()

        company = MagicMock()
        company.id = 10
        company.name = 'Google'
        company_model.return_value = company

        with patch(
            'routes.company.db.session.add'
        ) as mock_add, patch(
            'routes.company.db.session.commit'
        ):
            response = self.client.post(
                '/api/companies/',
                json={
                    'name': '  Google  ',
                    'industry': 'Technology'
                }
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['name'], 'Google')
        mock_add.assert_called_once_with(company)

    # ---------------- UPDATE COMPANY ----------------

    def test_rejects_unauthenticated_company_update(self):
        response = self.client.put(
            '/api/companies/1',
            json={'name': 'Microsoft'}
        )

        self.assertEqual(response.status_code, 401)

    def test_rejects_invalid_company_update_json(self):
        self.set_session()

        response = self.client.put(
            '/api/companies/1',
            json=['Microsoft']
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_blank_updated_company_name(self):
        self.set_session()

        company = MagicMock()

        with patch(
            'routes.company.Company.query'
        ) as mock_query:
            mock_query.get.return_value = company

            response = self.client.put(
                '/api/companies/1',
                json={'name': '   '}
            )

        self.assertEqual(response.status_code, 400)

    def test_returns_404_when_updating_missing_company(self):
        self.set_session()

        with patch(
            'routes.company.Company.query'
        ) as mock_query:
            mock_query.get.return_value = None

            response = self.client.put(
                '/api/companies/999',
                json={'name': 'Microsoft'}
            )

        self.assertEqual(response.status_code, 404)

    # ---------------- DELETE COMPANY ----------------

    def test_rejects_unauthenticated_company_deletion(self):
        response = self.client.delete('/api/companies/1')

        self.assertEqual(response.status_code, 401)

    def test_returns_404_when_deleting_missing_company(self):
        self.set_session()

        with patch(
            'routes.company.Company.query'
        ) as mock_query:
            mock_query.get.return_value = None

            response = self.client.delete('/api/companies/999')

        self.assertEqual(response.status_code, 404)

    def test_returns_409_when_company_has_linked_records(self):
        self.set_session()

        company = MagicMock()

        integrity_error = IntegrityError(
            'DELETE FROM companies',
            {},
            Exception(1451)
        )

        with patch(
            'routes.company.Company.query'
        ) as mock_query, patch(
            'routes.company.db.session.delete'
        ), patch(
            'routes.company.db.session.commit',
            side_effect=integrity_error
        ), patch(
            'routes.company.db.session.rollback'
        ) as mock_rollback:

            mock_query.get.return_value = company

            response = self.client.delete('/api/companies/1')

        self.assertEqual(response.status_code, 409)
        mock_rollback.assert_called_once()


if __name__ == '__main__':
    unittest.main()
