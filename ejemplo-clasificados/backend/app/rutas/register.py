from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.servicios.register import crear_usuario

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(request: RegisterRequest):
    try:
        user_id = crear_usuario(request.email, request.password)
        return {"id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Manejo genérico de errores de base de datos
        raise HTTPException(status_code=500, detail="Error interno del servidor")