import hashlib
from backend.app.datos.conexion import conexion

def insert_user(email: str, password_hash: str) -> int:
    """Inserta la fila y devuelve el id nuevo. Lanza si el email ya existe.
    Recibe el hash YA calculado: el hasheo es del servicio, no de la capa de datos."""
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usuarios (email, password_hash) VALUES (%s, %s)",
                (email, password_hash)
            )
            return cur.lastrowid