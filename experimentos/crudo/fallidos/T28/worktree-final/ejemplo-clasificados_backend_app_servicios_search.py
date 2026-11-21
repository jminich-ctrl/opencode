"""
Módulo de servicios para búsqueda de anuncios.
"""

from backend.app.datos.search_ads import buscar_anuncios


def buscar_anuncios_servicio(texto: str, categoria: str | None = None) -> list[dict]:
    """
    Servicio de búsqueda de anuncios que busca por texto y categoría.
    
    Args:
        texto: Texto a buscar en los anuncios
        categoria: ID de categoría opcional para filtrar
        
    Returns:
        Lista de diccionarios con los anuncios encontrados
    """
    return buscar_anuncios(texto, categoria)