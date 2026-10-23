from backend.app.datos.conexion import conexion


def search_ads(titulo: str | None = None, categoria: str | None = None) -> list[dict]:
    """
    Busca anuncios por título y/o categoría.
    
    Args:
        titulo: Texto a buscar en el título (opcional)
        categoria: Categoría a filtrar (opcional)
        
    Returns:
        Lista de diccionarios con los anuncios encontrados
    """
    condiciones = []
    parametros = []
    
    # Construimos las condiciones dinámicamente
    if titulo is not None:
        condiciones.append("titulo LIKE %s")
        parametros.append(f"%{titulo}%")
    
    if categoria is not None:
        condiciones.append("categoria = %s")
        parametros.append(categoria)
    
    # Construimos la consulta SQL
    consulta = "SELECT id, usuario_id, titulo, categoria FROM anuncios WHERE 1=1"
    
    if condiciones:
        consulta += " AND " + " AND ".join(condiciones)
    
    consulta += " ORDER BY id DESC"
    
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(consulta, parametros)
            return cur.fetchall()