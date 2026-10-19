from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.servicios.auth import login

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/auth/login")
async def login_endpoint(request: LoginRequest):
    """Endpoint para login que verifica credenciales y devuelve un token."""
    result = login(request.email, request.password)
    
    if result is None:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    return result