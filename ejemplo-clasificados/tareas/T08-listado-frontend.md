# T08 — Listado y detalle de avisos frontend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T07
**Archivos que podés tocar:** frontend/src/pages/AdsList.vue, frontend/src/pages/AdDetail.vue, frontend/src/services/ads.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear las vistas para listar los avisos y mostrar el detalle de cada anuncio, y el servicio que consume la API de anuncios.

## Alcance

Entra:
- Componente Vue `AdsList.vue` que muestra una lista de anuncios obtenidos del backend.
- Componente Vue `AdDetail.vue` que muestra los datos de un anuncio seleccionado.
- Servicio TypeScript `ads.ts` con funciones `getAds()` y `getAd(id)` que hacen `fetch` a los endpoints correspondientes.

No entra:
- Funcionalidad de favoritos ni mensajes.

## Contrato

```typescript
export async function getAds(): Promise<any[]>;
export async function getAd(id: string): Promise<any>;
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `frontend/tests/test_ads_frontend.ts`, clase `TestAdsFrontend`.

## Criterio de terminado

- [ ] Componentes `AdsList.vue` y `AdDetail.vue` creados y renderizan datos.
- [ ] Servicio `ads.ts` implementado y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
