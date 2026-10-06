# T16 — Backend rutas favoritos

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T15, T06c
**Archivos que podés tocar:** backend/app/rutas/favorites.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Exponer los endpoints de favoritos a través de FastAPI.

## Alcance

Entra:
- Endpoint para toggle favorito.
- Endpoint para listar favoritos de un usuario.

No entra:
- Lógica de negocio ni UI.

## Contrato

```python
from fastapi import APIRouter
router = APIRouter()

@router.post("/favorites/toggle")
async def toggle_favorite_endpoint(user_id: int, ad_id: int):
    """Endpoint que delega al servicio para marcar/desmarcar favorito."""
```

## Tests

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_favorites_rutas.py`, clase `TestFavoritesRutas`.

## Criterio de terminado

- [ ] Endpoints implementados.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A