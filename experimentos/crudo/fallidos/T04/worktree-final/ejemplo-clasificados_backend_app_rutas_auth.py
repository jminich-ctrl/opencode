"""
Rutas de autenticación.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.servicios.auth import login

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/auth/login", response_model=LoginResponse)
def login_endpoint(request: LoginRequest):
    """
    Endpoint para iniciar sesión.
    
    Verifica las credenciales y devuelve un token si son válidas.
    """
    result = login(request.email, request.password)
    
    if result is None:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    return result