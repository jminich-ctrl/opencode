"""
Ruta de búsqueda de anuncios.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from backend.app.servicios.search import buscar_anuncios_servicio

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
def buscar_anuncios_ruta(q: str, category: Optional[str] = None):
    """
    Endpoint para buscar anuncios por texto y categoría.
    
    Args:
        q: Texto a buscar
        category: ID de categoría opcional para filtrar
        
    Returns:
        Lista de anuncios que coinciden con los criterios de búsqueda
    """
    try:
        anuncios = buscar_anuncios_servicio(q, category)
        return {"anuncios": anuncios}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la búsqueda: {str(e)}")