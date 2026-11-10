import pytest
from unittest.mock import patch
from backend.app.servicios.register import crear_usuario

class TestRegisterBackend:
    def test_crear_usuario_ok(self):
        """Prueba que se pueda crear un usuario correctamente"""
        with patch('backend.app.servicios.register.insert_user') as mock_insert:
            mock_insert.return_value = 123
            
            result = crear_usuario("test@example.com", "password123")
            
            assert result == 123
            mock_insert.assert_called_once_with("test@example.com", "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f")

    def test_crear_usuario_email_invalido(self):
        """Prueba que se lance un error si el email es inválido"""
        with pytest.raises(ValueError) as excinfo:
            crear_usuario("", "password123")
        assert "Email inválido" in str(excinfo.value)

    def test_crear_usuario_password_invalida(self):
        """Prueba que se lance un error si la contraseña es inválida"""
        with pytest.raises(ValueError) as excinfo:
            crear_usuario("test@example.com", "123")
        assert "Contraseña inválida" in str(excinfo.value)

    def test_crear_usuario_hash_correcto(self):
        """Prueba que se haga el hash correcto de la contraseña"""
        with patch('backend.app.servicios.register.insert_user') as mock_insert:
            mock_insert.return_value = 123
            
            crear_usuario("test@example.com", "password123")
            
            # Verificar que se haya hecho el hash correcto
            expected_hash = "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f"
            mock_insert.assert_called_once()
            args, kwargs = mock_insert.call_args
            assert args[0] == "test@example.com"
            assert args[1] == expected_hash