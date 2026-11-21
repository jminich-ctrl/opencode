import pytest
import pymysql
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.rutas.register_backend import RegisterRequest, RegisterResponse

# Cliente de prueba
client = TestClient(app)

class TestRegisterBackend:
    """Tests para la funcionalidad de registro backend."""
    
    def setup_method(self):
        """Configura la base de datos mockeada antes de cada test."""
        self.mock_connection = MagicMock()
        self.mock_cursor = MagicMock()
        
        # Mockear la conexión a la base de datos
        self.db_patch = patch('backend.app.rutas.register_backend.pymysql.connect', return_value=self.mock_connection)
        self.db_mock = self.db_patch.start()
        
        # Configurar el mock del cursor para que devuelva el contexto correctamente
        self.mock_connection.cursor.return_value.__enter__.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = None  # Por defecto, no hay usuarios existentes
        
    def teardown_method(self):
        """Limpia los mocks después de cada test."""
        self.db_patch.stop()
        
    def test_registro_usuario_exitoso(self):
        """Test que verifica un registro de usuario exitoso."""
        # Configurar el mock para que no encuentre usuarios existentes
        self.mock_cursor.fetchone.return_value = None
        
        # Ejecutar la solicitud de registro
        response = client.post(
            "/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "nombre": "Juan",
                "apellido": "Pérez"
            }
        )
        
        # Verificaciones
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["nombre"] == "Juan"
        assert data["apellido"] == "Pérez"
        assert "id" in data
        
        # Verificar que se llamó a la base de datos correctamente
        self.mock_cursor.execute.assert_called()
        
    def test_registro_usuario_email_duplicado(self):
        """Test que verifica el error al registrar un usuario con email duplicado."""
        # Configurar el mock para que encuentre un usuario existente
        self.mock_cursor.fetchone.return_value = {"id": 1}
        
        # Ejecutar la solicitud de registro
        response = client.post(
            "/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "nombre": "Juan",
                "apellido": "Pérez"
            }
        )
        
        # Verificaciones
        assert response.status_code == 409
        assert "ya está en uso" in response.json()["error"]
        
    def test_registro_usuario_error_base_datos(self):
        """Test que verifica el manejo de errores de base de datos."""
        # Configurar el mock para lanzar una excepción
        self.mock_cursor.execute.side_effect = Exception("Error de base de datos")
        
        # Ejecutar la solicitud de registro
        response = client.post(
            "/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "nombre": "Juan",
                "apellido": "Pérez"
            }
        )
        
        # Verificaciones
        assert response.status_code == 500
        assert "Error al registrar el usuario" in response.json()["error"]
        
    def test_registro_usuario_datos_invalidos(self):
        """Test que verifica el manejo de datos inválidos."""
        # Ejecutar la solicitud de registro con datos incompletos
        response = client.post(
            "/register",
            json={
                "email": "test@example.com",
                "password": "password123"
                # Falta nombre y apellido
            }
        )
        
        # Verificaciones - Los errores de validación se convierten a 400
        assert response.status_code == 400  # Error de validación convertido a 400