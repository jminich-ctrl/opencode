# T11 — Editar propios avisos

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T05, T08
**Archivos que podés tocar:** frontend/src/pages/EditAd.jsx, frontend/src/services/ads.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Permitir a los usuarios editar sus propios anuncios desde el frontend.

## Alcance

Entra:
- Página React para editar anuncio.
- Servicio frontend que llama al endpoint de actualización.
- Validaciones básicas de formulario.

No entra:
- Cambios de esquema de base de datos.

## Contrato

```typescript
export async function updateAd(adId: number, data: Partial<Ad>): Promise<Ad> {
    // Llama al backend para actualizar y devuelve el anuncio actualizado.
}
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_edit_ad_frontend.test.ts`, clase `TestEditAdFrontend`.

## Criterio de terminado

- [ ] Página EditAd.jsx implementada.
- [ ] Servicio `updateAd` funciona.
- [ ] UI muestra cambios y errores.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
