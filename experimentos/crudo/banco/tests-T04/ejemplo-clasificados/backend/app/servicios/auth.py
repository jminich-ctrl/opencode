import hashlib
import os
import base64
from datetime import datetime, timedelta
from fastapi import Request, Response, HTTPException
from ..datos.users import verificar_credenciales

def generar_cookie_sesion() -> str:
    """Genera un token de sesión seguro."""
    # Generar un token aleatorio de 32 bytes
    token = os.urandom(32).hex()
    return token

def login(request: Request) -> Response:
    """Valida credenciales y devuelve respuesta con cookie de sesión."""
    # Extraer las credenciales de la cabecera Authorization
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # Decodificar las credenciales
    try:
        # La cabecera Basic contiene "Basic <base64(username:password)>"
        encoded_credentials = auth_header.split(" ")[1]
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
        username, password = decoded_credentials.split(':', 1)
        
        # Verificar credenciales
        if not verificar_credenciales(username, password):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
            
    except Exception:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # Generar cookie de sesión
    session_token = generar_cookie_sesion()
    
    # Crear respuesta con cookie
    response = Response(content="Login exitoso")
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=False,  # En producción debería ser True
        samesite="lax",
        max_age=3600  # 1 hora
    )
    
    return response

def logout(response: Response) -> Response:
    """Elimina la cookie de sesión."""
    response.delete_cookie(key="session_token")
    return response