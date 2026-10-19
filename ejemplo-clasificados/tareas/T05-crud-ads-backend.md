# T05 — CRUD de avisos backend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T04b, T06c
**Archivos que podés tocar:** backend/app/rutas/ads.py, backend/app/servicios/ads.py, backend/app/datos/ads.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar los endpoints para crear, leer, actualizar y eliminar avisos, respetando la autorización del usuario.

## Alcance

Entra:
- Endpoints `/ads` (GET, POST) y `/ads/{id}` (GET, PUT, DELETE).
- Validación básica de datos del anuncio.
- Uso de los módulos de datos y servicios existentes.

No entra:
- Gestión de favoritos ni mensajes.

## Contrato

```python
from fastapi import APIRouter, Request, Response
from backend.app.servicios.auth import usuario_desde_token   # lo provee T04b

router = APIRouter()

@router.post("/ads")
async def crear_ad(request: Request) -> Response:
    """Crea un nuevo anuncio y devuelve su ID."""
```

**Cómo se sabe quién pide: `usuario_desde_token(token)` de `servicios/auth.py`, que la
provee T04b.** Está escrito acá porque la versión anterior de esta tarea pedía «respetando
la autorización del usuario» sin decir el medio: el agente inventó una función, cableó tres
archivos a ella y se quedó veinte minutos contra su propio `ImportError`, tres veces. Una
tarea que exige algo y no dice con qué hacerlo no es ejecutable.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_ads_backend.py`, clase `TestAdsBackend`.

## Criterio de terminado

- [ ] Endpoints CRUD funcionales y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
