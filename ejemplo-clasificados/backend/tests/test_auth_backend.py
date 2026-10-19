from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.servicios.auth import login
from backend.app.datos.users import read_user_by_email

# El esquema de hash de este ejemplo: sha256 hex del password, sin sal.
#
# Está escrito acá porque el test lo IMPONE: la versión anterior mockeaba
# `password_hash: 'hashed_password'` y esperaba 200 con `password: 'password'`, lo que no
# cumple ningún hash real — así que sólo pasaba con una verificación falsa. Dos agentes
# implementando bien hubieran quedado en rojo, que es el caso de T40 en pacman.
#
# Sin sal a propósito y sólo para el ejemplo: con sal, el hash depende de un valor que el
# test tendría que conocer, y entonces el test pasa a especificar el formato de almacenamiento
# en vez del comportamiento del login.
HASH_DE_PASSWORD = '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8'


class TestAuthBackend(TestCase):
    def setUp(self):
        self.client = TestClient(app)

    # El parche es sobre el módulo `users`, así que la implementación tiene que llamarlo
    # como ATRIBUTO del módulo (`users.read_user_by_email(...)`). Con
    # `from ...users import read_user_by_email` el servicio se queda con su propia
    # referencia, el parche no aplica, la consulta va a la base de verdad y el test falla
    # con 401 — un rojo que no se parece a su causa.
    @patch('backend.app.datos.users.read_user_by_email')
    def test_login_success(self, mock_read_user):
        mock_read_user.return_value = {
            'id': 1, 'email': 'test@example.com', 'password_hash': HASH_DE_PASSWORD}
        response = self.client.post(
            '/auth/login', json={'email': 'test@example.com', 'password': 'password'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.json())

    @patch('backend.app.datos.users.read_user_by_email')
    def test_login_failure_wrong_password(self, mock_read_user):
        mock_read_user.return_value = {
            'id': 1, 'email': 'test@example.com', 'password_hash': HASH_DE_PASSWORD}
        response = self.client.post(
            '/auth/login', json={'email': 'test@example.com', 'password': 'wrongpassword'})
        self.assertEqual(response.status_code, 401)

    @patch('backend.app.datos.users.read_user_by_email')
    def test_login_failure_nonexistent_user(self, mock_read_user):
        mock_read_user.return_value = None
        response = self.client.post(
            '/auth/login', json={'email': 'nonexistent@example.com', 'password': 'password'})
        self.assertEqual(response.status_code, 401)
