from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from backend.app.servicios.search import buscar_anuncios

router = APIRouter(prefix="/search", tags=["Búsqueda"])

@router.get("/")
async def search(
    q: Optional[str] = None,
    category: Optional[str] = None
):
    """
    Busca anuncios por texto libre y/o categoría.
    
    Args:
        q: Texto a buscar en el título
        category: Categoría a filtrar
        
    Returns:
        Lista de anuncios que coinciden con los criterios de búsqueda
    """
    try:
        resultados = buscar_anuncios(texto=q, categoria=category)
        return {"anuncios": resultados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la búsqueda: {str(e)}")