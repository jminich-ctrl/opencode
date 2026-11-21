from fastapi import APIRouter, HTTPException
from backend.app.datos.favorites import toggle_favorite, get_user_favorites
from pydantic import BaseModel

router = APIRouter()

class ToggleFavoriteRequest(BaseModel):
    user_id: int
    ad_id: int

@router.post("/favorites/toggle")
async def toggle_favorite_endpoint(request: ToggleFavoriteRequest):
    """
    Endpoint que delega al servicio para marcar/desmarcar favorito.
    """
    try:
        # Llamar al servicio de favoritos
        result = toggle_favorite(request.user_id, request.ad_id)
        return {"status": "success", "favorited": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/favorites/list/{user_id}")
async def list_user_favorites(user_id: int):
    """
    Endpoint para listar favoritos de un usuario.
    """
    try:
        # Obtener los favoritos del usuario
        favorites = get_user_favorites(user_id)
        return {"favorites": favorites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))