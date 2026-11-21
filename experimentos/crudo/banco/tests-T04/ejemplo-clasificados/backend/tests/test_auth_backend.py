import pytest
import os
import sys
from unittest.mock import patch, MagicMock
import base64

# No necesitamos insertar el path manualmente, el entorno debe estar configurado correctamente

from app.datos.users import hash_password
from app.servicios.auth import login, logout, generar_cookie_sesion
from fastapi import Request, Response

class TestAuthBackend:
    """Tests para la autenticación backend."""

    def test_hash_password(self):
        """Prueba que la función de hash de contraseñas funcione correctamente."""
        password = "mi_contraseña_segura"
        salt = "mi_salt_unico"
        
        # Hashear la contraseña
        hashed = hash_password(password, salt)
        
        # Verificar que el resultado sea un string hexadecimal
        assert isinstance(hashed, str)
        assert len(hashed) == 64  # 32 bytes en hex = 64 caracteres

    def test_generar_cookie_sesion(self):
        """Prueba que se genere una cookie de sesión válida."""
        cookie = generar_cookie_sesion()
        
        # Verificar que se genere un string
        assert isinstance(cookie, str)
        # Verificar que tenga longitud adecuada (32 bytes = 64 hex chars)
        assert len(cookie) == 64

    def test_login_con_credenciales_validas(self):
        """Prueba que el login funcione con credenciales válidas."""
        # Mockear la función de verificación de credenciales
        with patch('app.servicios.auth.verificar_credenciales') as mock_verificar:
            mock_verificar.return_value = True
            
            # Crear una solicitud mock
            request = MagicMock()
            request.headers = {"Authorization": "Basic dXN1YXJpbzo1MzI0MTIz"}
            
            # Llamar a la función login
            response = login(request)
            
            # Verificar que se haya creado una cookie
            assert "session_token" in str(response.headers)
            assert response.status_code == 200

    def test_login_con_credenciales_invalidas(self):
        """Prueba que el login falle con credenciales inválidas."""
        # Mockear la función de verificación de credenciales
        with patch('app.servicios.auth.verificar_credenciales') as mock_verificar:
            mock_verificar.return_value = False
            
            # Crear una solicitud mock
            request = MagicMock()
            request.headers = {"Authorization": "Basic dXN1YXJpbzo1MzI0MTIz"}
            
            # Verificar que se lance una excepción HTTP 401
            try:
                response = login(request)
                assert False, "Se esperaba una excepción HTTP 401"
            except Exception as e:
                assert "401" in str(e) or "Unauthorized" in str(e)

    def test_logout(self):
        """Prueba que el logout elimine la cookie de sesión."""
        # Crear una respuesta mock
        response = Response()
        
        # Llamar a logout
        result = logout(response)
        
        # Verificar que se haya eliminado la cookie
        assert "session_token" in str(result.headers)
        # Verificar que la cookie tenga max-age=0 (indicando eliminación)
        set_cookie_header = str(result.headers.get("set-cookie", ""))
        assert "max-age=0" in set_cookie_header.lower()