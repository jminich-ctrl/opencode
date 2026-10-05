# T08 — Listado y detalle de avisos frontend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T07
**Archivos que podés tocar:** frontend/src/pages/AdsList.jsx, frontend/src/pages/AdDetail.jsx, frontend/src/services/ads.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear las vistas para listar los avisos y mostrar el detalle de cada anuncio, y el servicio que consume la API de anuncios.

## Alcance

Entra:
- Componente React `AdsList.jsx` que muestra una lista de anuncios obtenidos del backend.
- Componente React `AdDetail.jsx` que muestra los datos de un anuncio seleccionado.
- Servicio TypeScript `ads.ts` con funciones `getAds()` y `getAd(id)` que hacen `fetch` a los endpoints correspondientes.

No entra:
- Funcionalidad de favoritos ni mensajes.

## Contrato

```typescript
export async function getAds(): Promise<any[]>;
export async function getAd(id: string): Promise<any>;
```

## Tests

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_ads_frontend.test.ts`, clase `TestAdsFrontend`.

## Criterio de terminado

- [ ] Componentes `AdsList.jsx` y `AdDetail.jsx` creados y renderizan datos.
- [ ] Servicio `ads.ts` implementado y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
