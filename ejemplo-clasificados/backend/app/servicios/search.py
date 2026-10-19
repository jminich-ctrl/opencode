from backend.app.datos.search_ads import buscar_anuncios

def buscar_anuncios_servicio(texto: str, categoria: str | None = None) -> list[dict]:
    """Servicio que busca anuncios por texto y categoría.
    
    Args:
        texto: Texto a buscar en los anuncios
        categoria: Categoría opcional para filtrar los resultados
        
    Returns:
        Lista de diccionarios con los anuncios encontrados
    """
    return buscar_anuncios(texto, categoria)