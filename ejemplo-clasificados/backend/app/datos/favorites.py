from .conexion import conexion

def toggle_favorite(user_id: int, ad_id: int) -> bool:
    """Marca o desmarca el anuncio como favorito para el usuario. Devuelve True si quedó como favorito."""
    with conexion() as conn:
        with conn.cursor() as cur:
            # Intentamos borrar el favorito existente (si hay uno)
            cur.execute("DELETE FROM favoritos WHERE usuario_id = %s AND anuncio_id = %s", (user_id, ad_id))
            
            # Si se eliminó algún registro, entonces el favorito estaba y ahora no está
            # Si no se eliminó ningún registro, entonces el favorito no estaba y debemos crearlo
            if cur.rowcount == 0:
                # Insertamos el nuevo favorito
                cur.execute("INSERT INTO favoritos (usuario_id, anuncio_id) VALUES (%s, %s)", (user_id, ad_id))
                return True
            else:
                # El favorito fue eliminado
                return False

def get_user_favorites(user_id: int) -> list[int]:
    """Devuelve una lista con los IDs de los anuncios favoritos del usuario."""
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT anuncio_id FROM favoritos WHERE usuario_id = %s", (user_id,))
            results = cur.fetchall()
            # Extraer los IDs de las tuplas
            return [row[0] for row in results]