"""
Servicio de autenticación.
"""
import hashlib
from backend.app.datos import users


def login(email: str, password: str) -> dict | None:
    """
    Verifica credenciales de usuario.
    
    Si las credenciales son válidas, retorna un diccionario con `token`.
    Si no, retorna None.
    """
    # Obtener el usuario
    user = users.read_user_by_email(email)
    
    # Si no existe el usuario, retornar None
    if not user:
        return None
    
    # Calcular el hash del password proporcionado
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Comparar hashes
    if password_hash == user['password_hash']:
        # En un sistema real, aquí se generarían tokens JWT o similares
        # Por ahora retornamos un token dummy
        return {"token": "dummy-token-for-testing"}
    
    # Si los hashes no coinciden, credenciales inválidas
    return None