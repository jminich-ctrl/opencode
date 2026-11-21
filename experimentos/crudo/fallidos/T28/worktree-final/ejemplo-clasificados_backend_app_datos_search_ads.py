"""
Módulo de datos para búsqueda de anuncios.
"""

from backend.app.datos.conexion import conexion


def buscar_anuncios(texto: str, categoria: str | None = None) -> list[dict]:
    """
    Busca anuncios que coincidan con el texto y, opcionalmente, la categoría.
    
    Args:
        texto: Texto a buscar en los anuncios
        categoria: ID de categoría opcional para filtrar
        
    Returns:
        Lista de diccionarios con los anuncios encontrados
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            # Construimos la consulta SQL dinámica
            if categoria is not None:
                # Si hay categoría, filtramos por ella
                cur.execute("""
                    SELECT id, usuario_id, titulo, descripcion, precio, categoria_id, fecha_creacion
                    FROM anuncios 
                    WHERE titulo LIKE %s OR descripcion LIKE %s
                    AND categoria_id = %s
                    ORDER BY fecha_creacion DESC
                """, (f"%{texto}%", f"%{texto}%", categoria))
            else:
                # Si no hay categoría, buscamos en todos
                cur.execute("""
                    SELECT id, usuario_id, titulo, descripcion, precio, categoria_id, fecha_creacion
                    FROM anuncios 
                    WHERE titulo LIKE %s OR descripcion LIKE %s
                    ORDER BY fecha_creacion DESC
                """, (f"%{texto}%", f"%{texto}%"))
            
            return cur.fetchall()