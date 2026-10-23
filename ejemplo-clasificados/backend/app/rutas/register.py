from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.servicios.register import crear_usuario

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(request: RegisterRequest):
    """Crea un nuevo usuario con email y contraseña."""
    try:
        user_id = crear_usuario(request.email, request.password)
        return {"id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Error al crear usuario")