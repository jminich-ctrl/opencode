from fastapi import APIRouter, Request, Response
from ..servicios.auth import login, logout

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login_endpoint(request: Request) -> Response:
    """Endpoint para iniciar sesión."""
    return login(request)

@router.post("/logout")
def logout_endpoint(response: Response) -> Response:
    """Endpoint para cerrar sesión."""
    return logout(response)