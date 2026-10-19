import hashlib
from backend.app.datos import users

def login(email: str, password: str) -> dict | None:
    """Verifica credenciales. Devuelve algo con `token` si son válidas, o None."""
    # Obtener el usuario por email
    user = users.read_user_by_email(email)
    
    if user is None:
        return None
    
    # Calcular el hash del password proporcionado
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Comparar el hash calculado con el almacenado
    if password_hash == user.get("password_hash"):
        # Si las credenciales son válidas, devolver un token (simulado)
        return {"token": "mocked-token-for-user-" + str(user.get("id"))}
    
    # Si las credenciales no son válidas
    return None