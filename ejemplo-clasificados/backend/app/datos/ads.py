from .conexion import conexion

def insert_ad(usuario_id: int, categoria_id: int, titulo: str, descripcion: str,
              precio_centavos: int) -> int:
    """Inserta un nuevo anuncio en la base de datos y devuelve su ID.
    
    Args:
        usuario_id: ID del usuario dueño del anuncio
        categoria_id: ID de la categoría del anuncio
        titulo: Título del anuncio
        descripcion: Descripción del anuncio
        precio_centavos: Precio en centavos
        
    Returns:
        int: El ID del nuevo anuncio insertado
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO anuncios (usuario_id, categoria_id, titulo, descripcion, precio_centavos) VALUES (%s, %s, %s, %s, %s)",
                (usuario_id, categoria_id, titulo, descripcion, precio_centavos)
            )
            return cur.lastrowid

def get_ad_by_id(ad_id: int) -> dict | None:
    """Obtiene un anuncio por su ID.
    
    Args:
        ad_id: ID del anuncio a buscar
        
    Returns:
        dict | None: Los datos del anuncio si existe, None si no existe
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, usuario_id, categoria_id, titulo, descripcion, precio_centavos FROM anuncios WHERE id = %s",
                (ad_id,)
            )
            return cur.fetchone()

def update_ad(ad_id: int, usuario_id: int, titulo: str, descripcion: str,
              precio_centavos: int) -> bool:
    """Actualiza un anuncio si pertenece al usuario especificado.
    
    Args:
        ad_id: ID del anuncio a actualizar
        usuario_id: ID del usuario que intenta actualizar
        titulo: Nuevo título del anuncio
        descripcion: Nueva descripción del anuncio
        precio_centavos: Nuevo precio en centavos
        
    Returns:
        bool: True si se actualizó el anuncio, False si no pertenece al usuario
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE anuncios SET titulo = %s, descripcion = %s, precio_centavos = %s WHERE id = %s AND usuario_id = %s",
                (titulo, descripcion, precio_centavos, ad_id, usuario_id)
            )
            return cur.rowcount > 0

def delete_ad(ad_id: int, usuario_id: int) -> bool:
    """Elimina un anuncio si pertenece al usuario especificado.
    
    Args:
        ad_id: ID del anuncio a eliminar
        usuario_id: ID del usuario que intenta eliminar
        
    Returns:
        bool: True si se eliminó el anuncio, False si no pertenece al usuario
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM anuncios WHERE id = %s AND usuario_id = %s",
                (ad_id, usuario_id)
            )
            return cur.rowcount > 0