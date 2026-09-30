# T23 — Mensajes servicio frontend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T22
**Archivos que podés tocar:** frontend/src/services/messages.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Implementar el cliente de API para mensajes en el frontend.

## Alcance

Entra:
- Función `sendMessage` que llama al endpoint `/messages`.
- Función `listMessages` para obtener conversaciones.
- Función `getMessage` para detalle de mensaje.

No entra:
- UI ni lógica de negocio.

## Contrato

```typescript
export async function sendMessage(senderId: number, receiverId: number, adId: number, content: string): Promise<any> {
    // llama al backend y devuelve el mensaje creado
}
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_messages_servicio.test.ts`, clase `TestMessagesServicioFrontend`.

## Criterio de terminado

- [ ] Funciones del servicio implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A