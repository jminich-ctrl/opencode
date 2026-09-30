# T25 — Mensajes UI detalle

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T23
**Archivos que podés tocar:** frontend/src/pages/MessageDetail.jsx
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Mostrar el detalle de un mensaje en la página de detalle.

## Alcance

Entra:
- Modificación del componente `MessageDetail.jsx` para renderizar el mensaje obtenido del servicio.
- Uso de `getMessage` del servicio frontend.

No entra:
- Envío de nuevo mensaje ni lista de conversaciones.

## Contrato

N/A (modificación de UI existente).

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_messages_ui_detalle.test.ts`, clase `TestMessagesUIDetalle`.

## Criterio de terminado

- [ ] UI muestra correctamente el detalle del mensaje.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A