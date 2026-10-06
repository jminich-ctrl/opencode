# T24 — Mensajes UI lista

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T23
**Archivos que podés tocar:** frontend/src/pages/Messages.jsx
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Mostrar la lista de conversaciones de mensajes en la página de mensajes.

## Alcance

Entra:
- Modificación del componente `Messages.jsx` para renderizar la lista obtenida del servicio.
- Uso de `listMessages` del servicio frontend.

No entra:
- Detalle de mensaje ni envío de nuevo mensaje.

## Contrato

N/A (modificación de UI existente).

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_messages_ui_lista.test.ts`, clase `TestMessagesUILista`.

## Criterio de terminado

- [ ] UI muestra correctamente la lista de conversaciones.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A