# T22 — Backend rutas mensajes

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T21
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

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/backend/test_messages_rutas.py`, clase `TestMessagesRutas`.

## Criterio de terminado

- [ ] Endpoints implementados.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A