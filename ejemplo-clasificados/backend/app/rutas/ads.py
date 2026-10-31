from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.app.servicios.auth import usuario_desde_token
from backend.app.servicios.ads import crear_anuncio, obtener_anuncio, actualizar_anuncio, eliminar_anuncio
from backend.app.servicios.search import buscar_anuncios

router = APIRouter()

class AnuncioCreate(BaseModel):
    categoria_id: int
    titulo: str
    descripcion: str
    precio_centavos: int

class AnuncioUpdate(BaseModel):
    categoria_id: int
    titulo: str
    descripcion: str
    precio_centavos: int

@router.post("/ads", status_code=201)
async def crear_anuncio_endpoint(
    anuncio: AnuncioCreate,
    authorization: str = None
):
    # Verificar autenticación
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    token = authorization[7:]  # Quitar "Bearer "
    usuario = usuario_desde_token(token)
    
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    # Llamada directa al servicio sin envolver en try-except para evitar captura de validación
    ad_id = crear_anuncio(
        usuario_id=usuario,
        categoria_id=anuncio.categoria_id,
        titulo=anuncio.titulo,
        descripcion=anuncio.descripcion,
        precio_centavos=anuncio.precio_centavos
    )
    return {"id": ad_id}

@router.get("/ads")
async def listar_anuncios():
    anuncios = buscar_anuncios(None)
    return anuncios

@router.get("/ads/{id}")
async def obtener_anuncio_endpoint(id: int, authorization: str = None):
    # Verificar autenticación
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    token = authorization[7:]  # Quitar "Bearer "
    usuario = usuario_desde_token(token)
    
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    anuncio = obtener_anuncio(id)
    if anuncio is None:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    # Verificar que el usuario sea el dueño del anuncio
    if anuncio["usuario_id"] != usuario:
        raise HTTPException(status_code=403, detail="No es tu aviso")
    return anuncio

@router.put("/ads/{id}")
async def actualizar_anuncio_endpoint(
    id: int,
    anuncio: AnuncioUpdate,
    authorization: str = None
):
    # Verificar autenticación
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    token = authorization[7:]  # Quitar "Bearer "
    usuario = usuario_desde_token(token)
    
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    # Verificar que el usuario sea el dueño del anuncio
    anuncio_existente = obtener_anuncio(id)
    if anuncio_existente is None:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    if anuncio_existente["usuario_id"] != usuario:
        raise HTTPException(status_code=403, detail="No es tu aviso")
    
    actualizar_anuncio(
        ad_id=id,
        usuario_id=usuario,
        titulo=anuncio.titulo,
        descripcion=anuncio.descripcion,
        precio_centavos=anuncio.precio_centavos
    )
    return {}

@router.delete("/ads/{id}")
async def eliminar_anuncio_endpoint(id: int, authorization: str = None):
    # Verificar autenticación
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    token = authorization[7:]  # Quitar "Bearer "
    usuario = usuario_desde_token(token)
    
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sin sesión")
    
    # Verificar que el usuario sea el dueño del anuncio
    anuncio_existente = obtener_anuncio(id)
    if anuncio_existente is None:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    if anuncio_existente["usuario_id"] != usuario:
        raise HTTPException(status_code=403, detail="No es tu aviso")
    
    eliminar_anuncio(id, usuario)
    return {}