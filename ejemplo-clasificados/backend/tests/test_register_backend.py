import pytest
from unittest.mock import patch, MagicMock
from backend.app.servicios.register import crear_usuario
from backend.app.datos.users_register import insert_user

class TestRegisterBackend:
    
    def test_crear_usuario_valido(self):
        """Debe crear un usuario válido con email y contraseña"""
        # Mockear la función de inserción
        with patch('backend.app.datos.users_register.insert_user') as mock_insert:
            mock_insert.return_value = 123
            
            # Llamar a la función
            user_id = crear_usuario("test@example.com", "password123")
            
            # Verificar que se llamó correctamente
            assert user_id == 123
            mock_insert.assert_called_once_with(
                "test@example.com",
                "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f"
            )
    
    def test_crear_usuario_email_invalido(self):
        """Debe fallar al crear un usuario con email inválido"""
        with pytest.raises(ValueError, match="Email inválido"):
            crear_usuario("", "password123")
        
        with pytest.raises(ValueError, match="Email inválido"):
            crear_usuario("invalid-email", "password123")
    
    def test_crear_usuario_password_invalido(self):
        """Debe fallar al crear un usuario con contraseña inválida"""
        with pytest.raises(ValueError, match="Contraseña inválida"):
            crear_usuario("test@example.com", "")
        
        with pytest.raises(ValueError, match="Contraseña inválida"):
            crear_usuario("test@example.com", "123")
    
    def test_crear_usuario_hash_correcto(self):
        """Debe hashear la contraseña con sha256 como lo hace auth.py"""
        # Mockear la función de inserción
        with patch('backend.app.datos.users_register.insert_user') as mock_insert:
            mock_insert.return_value = 123
            
            # Llamar a la función
            crear_usuario("test@example.com", "password123")
            
            # Verificar que se llamó con el hash correcto
            expected_hash = "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f"
            mock_insert.assert_called_once_with(
                "test@example.com",
                expected_hash
            )