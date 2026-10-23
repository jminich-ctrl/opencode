from backend.app.datos.search_ads import search_ads


def buscar_anuncios(texto: str, categoria: str | None = None) -> list[dict]:
    """Devuelve anuncios que coinciden con el texto y, opcionalmente, la categoría."""
    return search_ads(titulo=texto, categoria=categoria)