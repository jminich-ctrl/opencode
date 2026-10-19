import hashlib
from backend.app.datos.users_register import insert_user

def crear_usuario(email: str, password: str) -> int:
    """Valida, hashea con el mismo esquema que `auth.py` y delega en
    `users_register.insert_user`. Devuelve el id."""
    
    # Validar email
    if not email or "@" not in email:
        raise ValueError("Email inválido")
    
    # Validar contraseña
    if not password or len(password) < 4:
        raise ValueError("Contraseña inválida")
    
    # Hashear contraseña con el mismo esquema que auth.py
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Insertar usuario
    user_id = insert_user(email, password_hash)
    
    return user_id