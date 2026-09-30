# T10 — Mensajes entre usuarios

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T04, T05
**Archivos que podés tocar:** backend/app/rutas/messages.py, backend/app/servicios/messages.py, backend/app/datos/messages.py, frontend/src/pages/Messages.jsx, frontend/src/pages/MessageDetail.jsx, frontend/src/services/messages.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Permitir a usuarios enviar y recibir mensajes privados relacionados a un anuncio.

## Alcance

Entra:
- Endpoints API para crear, listar y leer mensajes.
- Servicio frontend para consumir dichos endpoints.
- UI de listado de conversaciones y detalle de mensaje.

No entra:
- Notificaciones push ni email.

## Contrato

```python
def send_message(sender_id: int, receiver_id: int, ad_id: int, content: str) -> dict:
    """Envía un mensaje y devuelve el registro creado."""
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_messages_frontend.test.ts`, clase `TestMessagesFrontend`.

## Criterio de terminado

- [ ] Endpoints implementados.
- [ ] Servicio y UI funcionales.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
