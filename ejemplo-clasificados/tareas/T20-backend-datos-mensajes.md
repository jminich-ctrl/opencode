# T20 — Backend datos mensajes

**Estado:** pendiente
**Depende de:** T05a
**Archivos que podés tocar:** backend/app/datos/messages.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Implementar la capa de acceso a datos para los mensajes, con funciones para crear, listar y obtener mensajes.

## Alcance

Entra:
- Función `send_message` que inserta un registro.
- Función `list_messages(user_id)` que devuelve conversaciones.
- Función `get_message(message_id)` que devuelve detalle.

No entra:
- Lógica de negocio ni exposición vía API.

## Contrato

```python
def send_message(sender_id: int, receiver_id: int, ad_id: int, content: str) -> dict:
    """Inserta un mensaje y devuelve el registro creado."""
```

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_messages_datos.py`, clase `TestMessagesDatos`.

## Criterio de terminado

- [ ] Funciones de datos implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
## Reabierta

su codigo usa remitente_id, destinatario_id, contenido y fecha_envio, y la tabla mensajes tiene de_usuario_id, a_usuario_id, cuerpo y creado_en

Se reabrió con scripts/reabrir.sh el 2026-10-24 18:47 UTC. Su código anterior
se sacó del tronco (copia en ../reabrir-T20-previo): esta tarea vuelve a pasar por tests-first,
así que el test tiene que fallar antes de que exista la implementación.
