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

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_messages_servicio.py`, clase `TestMessagesServicio`.

## Criterio de terminado

- [ ] Funciones de servicio implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A