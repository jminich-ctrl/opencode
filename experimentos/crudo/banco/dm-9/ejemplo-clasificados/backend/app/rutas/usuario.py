from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict
from app.services.usuario import UsuarioService

router = APIRouter()

# Inyectamos el servicio de usuarios
usuario_service = UsuarioService()

@router.get("/usuarios")
async def obtener_usuarios() -> List[Dict]:
    usuarios = usuario_service.obtener_todos()
    return [usuario.to_dict() for usuario in usuarios]

@router.get("/usuarios/{id}")
async def obtener_usuario(id: int) -> Dict:
    usuario = usuario_service.obtener_usuario(id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario.to_dict()

@router.post("/usuarios")
async def crear_usuario(nombre: str = Body(...), email: str = Body(...)) -> Dict:
    nuevo_usuario = usuario_service.crear_usuario(nombre, email)
    return nuevo_usuario.to_dict()

@router.put("/usuarios/{id}")
async def actualizar_usuario(id: int, nombre: str = Body(...), email: str = Body(...)) -> Dict:
    if not usuario_service.actualizar_usuario(id, nombre, email):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario_service.obtener_usuario(id).to_dict()

@router.delete("/usuarios/{id}")
async def eliminar_usuario(id: int) -> Dict:
    if not usuario_service.eliminar_usuario(id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"mensaje": "Usuario eliminado correctamente"}