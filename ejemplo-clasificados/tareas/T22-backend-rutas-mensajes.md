# T22 — Backend rutas mensajes

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T21, T06c
**Archivos que podés tocar:** backend/app/rutas/messages.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Exponer los endpoints de mensajes a través de FastAPI.

## Alcance

Entra:
- Endpoint para enviar mensaje (`POST /messages`).
- Endpoint para listar conversaciones de un usuario (`GET /messages?user_id=`).
- Endpoint para obtener detalle de mensaje (`GET /messages/{id}`).

No entra:
- Lógica de negocio ni UI.

## Contrato

```python
from fastapi import APIRouter
router = APIRouter()

@router.post("/messages")
async def send_message_endpoint(...):
    """Endpoint que delega al servicio para crear un mensaje."""
```

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_messages_rutas.py`, clase `TestMessagesRutas`.

## Criterio de terminado

- [ ] Endpoints implementados.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A