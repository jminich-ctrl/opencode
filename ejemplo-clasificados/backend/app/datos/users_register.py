import hashlib
from backend.app.datos.conexion import conexion

def insert_user(email: str, password_hash: str) -> int:
    """Inserta la fila y devuelve el id nuevo. Lanza si el email ya existe.
    Recibe el hash YA calculado: el hasheo es del servicio, no de la capa de datos."""
    # Validar que el email no exista ya
    with conexion() as conn:
        cursor = conn.cursor()
        try:
            # Insertar el nuevo usuario
            cursor.execute("""
                INSERT INTO users (email, password_hash) 
                VALUES (%s, %s)
            """, (email, password_hash))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            # Revertir transacción en caso de error
            conn.rollback()
            raise e