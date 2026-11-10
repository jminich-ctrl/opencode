import hashlib
from backend.app.datos.users_register import insert_user

def crear_usuario(email: str, password: str) -> int:
    """Valida, hashea con el mismo esquema que `auth.py` y delega en
    `users_register.insert_user`. Devuelve el id."""
    # Validación básica
    if not email or '@' not in email:
        raise ValueError("Email inválido")
    
    if not password or len(password) < 6:
        raise ValueError("Contraseña inválida")
        
    # Hashear contraseña con sha256 (igual que auth.py)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Insertar usuario
    return insert_user(email, password_hash)