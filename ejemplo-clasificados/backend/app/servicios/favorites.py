"""
Capa de servicios para la lógica de favoritos.
"""

from backend.app.datos.favorites import toggle_favorite


def toggle_favorite_service(user_id: int, ad_id: int) -> bool:
    """Servicio que delega a la capa de datos para marcar/desmarcar favorito."""
    return toggle_favorite(user_id, ad_id)