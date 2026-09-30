# T16 — Backend rutas favoritos

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T15
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

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/backend/test_favorites_rutas.py`, clase `TestFavoritesRutas`.

## Criterio de terminado

- [ ] Endpoints implementados.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A