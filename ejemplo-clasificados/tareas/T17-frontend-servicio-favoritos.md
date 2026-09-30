# T17 — Favoritos servicio frontend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T16, T08
**Archivos que podés tocar:** frontend/src/services/favorites.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar el cliente de API para favoritos en el frontend.

## Alcance

Entra:
- Función que llama al endpoint `/favorites/toggle`.
- Función para obtener la lista de favoritos.

No entra:
- UI ni lógica de negocio.

## Contrato

```typescript
export async function toggleFavorite(userId: number, adId: number): Promise<boolean> {
    // llama al backend y devuelve true si quedó como favorito
}
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_favorites_servicio.test.ts`, clase `TestFavoritesServicioFrontend`.

## Criterio de terminado

- [ ] Funciones del servicio implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A