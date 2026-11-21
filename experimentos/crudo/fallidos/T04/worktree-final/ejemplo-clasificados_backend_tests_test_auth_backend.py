"""
Tests para el backend de autenticación.
"""
from unittest.mock import patch
import hashlib
from backend.app.servicios.auth import login
from backend.app.rutas.auth import router
from fastapi.testclient import TestClient
from backend.app.main import app


class TestAuthBackend:
    """Tests para el backend de autenticación."""

    def test_login_con_credenciales_validas(self):
        """Prueba que el login funcione con credenciales válidas."""
        # Mockear la función read_user_by_email para devolver un usuario válido
        with patch('backend.app.datos.users.read_user_by_email') as mock_read_user:
            # Configurar el mock con un usuario válido
            mock_user = {
                'id': 1,
                'email': 'test@example.com',
                'password_hash': hashlib.sha256('password'.encode()).hexdigest()
            }
            mock_read_user.return_value = mock_user
            
            # Llamar a la función de login
            result = login('test@example.com', 'password')
            
            # Verificar que se devuelve un token
            assert result is not None
            assert 'token' in result
            assert result['token'] == 'dummy-token-for-testing'

    def test_login_con_password_incorrecto(self):
        """Prueba que el login falle con password incorrecto."""
        # Mockear la función read_user_by_email para devolver un usuario válido
        with patch('backend.app.datos.users.read_user_by_email') as mock_read_user:
            # Configurar el mock con un usuario válido
            mock_user = {
                'id': 1,
                'email': 'test@example.com',
                'password_hash': hashlib.sha256('password'.encode()).hexdigest()
            }
            mock_read_user.return_value = mock_user
            
            # Llamar a la función de login con password incorrecto
            result = login('test@example.com', 'wrongpassword')
            
            # Verificar que se devuelve None
            assert result is None

    def test_login_con_usuario_inexistente(self):
        """Prueba que el login falle con usuario inexistente."""
        # Mockear la función read_user_by_email para devolver None
        with patch('backend.app.datos.users.read_user_by_email') as mock_read_user:
            # Configurar el mock para que devuelva None (usuario no encontrado)
            mock_read_user.return_value = None
            
            # Llamar a la función de login
            result = login('nonexistent@example.com', 'password')
            
            # Verificar que se devuelve None
            assert result is None

    def test_endpoint_login_con_credenciales_validas(self):
        """Prueba el endpoint POST /auth/login con credenciales válidas."""
        with patch('backend.app.datos.users.read_user_by_email') as mock_read_user:
            # Configurar el mock con un usuario válido
            mock_user = {
                'id': 1,
                'email': 'test@example.com',
                'password_hash': hashlib.sha256('password'.encode()).hexdigest()
            }
            mock_read_user.return_value = mock_user
            
            # Crear cliente de test
            client = TestClient(app)
            
            # Hacer la solicitud POST
            response = client.post(
                "/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "password"
                }
            )
            
            # Verificar que se devuelve 200
            assert response.status_code == 200
            
            # Verificar que el cuerpo contiene un token
            data = response.json()
            assert 'token' in data
            assert data['token'] == 'dummy-token-for-testing'

    def test_endpoint_login_con_password_incorrecto(self):
        """Prueba el endpoint POST /auth/login con password incorrecto."""
        with patch('backend.app.datos.users.read_user_by_email') as mock_read_user:
            # Configurar el mock con un usuario válido
            mock_user = {
                'id': 1,
                'email': 'test@example.com',
                'password_hash': hashlib.sha256('password'.encode()).hexdigest()
            }
            mock_read_user.return_value = mock_user
            
            # Crear cliente de test
            client = TestClient(app)
            
            # Hacer la solicitud POST con password incorrecto
            response = client.post(
                "/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "wrongpassword"
                }
            )
            
            # Verificar que se devuelve 401
            assert response.status_code == 401

    def test_endpoint_login_con_usuario_inexistente(self):
        """Prueba el endpoint POST /auth/login con usuario inexistente."""
        with patch('backend.app.datos.users.read_user_by_email') as mock_read_user:
            # Configurar el mock para que devuelva None (usuario no encontrado)
            mock_read_user.return_value = None
            
            # Crear cliente de test
            client = TestClient(app)
            
            # Hacer la solicitud POST
            response = client.post(
                "/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": "password"
                }
            )
            
            # Verificar que se devuelve 401
            assert response.status_code == 401