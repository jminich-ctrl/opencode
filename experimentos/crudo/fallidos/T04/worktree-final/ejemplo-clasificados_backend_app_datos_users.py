"""
Datos de usuarios.
"""
from backend.app.datos.conexion import conexion


def read_user_by_email(email: str) -> dict | None:
    """
    Lee un usuario por email.
    
    Retorna un diccionario con los datos del usuario o None si no existe.
    El diccionario debe contener al menos `id`, `email` y `password_hash`.
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
            fila = cur.fetchone()
            return fila