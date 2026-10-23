import hashlib
from backend.app.datos import users_register

def crear_usuario(email: str, password: str) -> int:
    """Valida, hashea con el mismo esquema que `auth.py` y delega en
    `users_register.insert_user`. Devuelve el id."""
    # Validar datos básicos
    if not email or not isinstance(email, str) or "@" not in email:
        raise ValueError("Email inválido")
    
    if not password or not isinstance(password, str) or len(password) < 6:
        raise ValueError("Contraseña inválida")
    
    # Hashear la contraseña usando el mismo esquema que auth.py
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Delegar en la capa de datos
    return users_register.insert_user(email, password_hash)