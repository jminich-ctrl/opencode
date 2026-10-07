from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.servicios.auth import login
from backend.app.datos.users import read_user_by_email


class TestAuthBackend(TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch('backend.app.datos.users.read_user_by_email')
    def test_login_success(self, mock_read_user):
        # Mock the user retrieval
        mock_read_user.return_value = {'id': 1, 'email': 'test@example.com', 'password_hash': 'hashed_password'}
        response = self.client.post('/auth/login', json={'email': 'test@example.com', 'password': 'password'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.json())

    @patch('backend.app.datos.users.read_user_by_email')
    def test_login_failure_wrong_password(self, mock_read_user):
        # Mock the user retrieval
        mock_read_user.return_value = {'id': 1, 'email': 'test@example.com', 'password_hash': 'hashed_password'}
        response = self.client.post('/auth/login', json={'email': 'test@example.com', 'password': 'wrongpassword'})
        self.assertEqual(response.status_code, 401)

    @patch('backend.app.datos.users.read_user_by_email')
    def test_login_failure_nonexistent_user(self, mock_read_user):
        # Mock the user retrieval
        mock_read_user.return_value = None
        response = self.client.post('/auth/login', json={'email': 'nonexistent@example.com', 'password': 'password'})
        self.assertEqual(response.status_code, 401)