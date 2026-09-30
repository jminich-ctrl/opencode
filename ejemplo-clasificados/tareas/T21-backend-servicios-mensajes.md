# T21 — Backend servicios mensajes

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T20
**Archivos que podés tocar:** backend/app/servicios/messages.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Implementar la capa de servicio para la lógica de mensajes, delegando en la capa de datos.

## Alcance

Entra:
- Funciones que llaman a `send_message`, `list_messages`, `get_message` del módulo de datos.
- Validaciones básicas de entrada.

No entra:
- Exposición vía API ni UI.

## Contrato

```python
def send_message_service(sender_id: int, receiver_id: int, ad_id: int, content: str) -> dict:
    """Servicio que delega a la capa de datos para crear un mensaje."""
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/backend/test_messages_servicio.py`, clase `TestMessagesServicio`.

## Criterio de terminado

- [ ] Funciones de servicio implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A