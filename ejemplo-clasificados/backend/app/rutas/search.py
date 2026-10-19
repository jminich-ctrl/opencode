from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.app.servicios.search import buscar_anuncios_servicio

router = APIRouter()

@router.get("/search")
async def search_endpoint(
    q: str = Query(..., description="Texto a buscar"),
    category: Optional[str] = Query(None, description="Filtro por categoría")
):
    """Endpoint para buscar anuncios por texto y categoría.
    
    Args:
        q: Texto a buscar en los anuncios
        category: Categoría opcional para filtrar los resultados
        
    Returns:
        Lista de anuncios que coinciden con los criterios de búsqueda
    """
    try:
        resultados = buscar_anuncios_servicio(q, category)
        return {"results": resultados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la búsqueda: {str(e)}")