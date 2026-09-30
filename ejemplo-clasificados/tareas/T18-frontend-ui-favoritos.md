# T18 — Favoritos UI lista

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T17
**Archivos que podés tocar:** frontend/src/pages/AdsList.jsx
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Mostrar el estado de favorito (icono activo/inactivo) en la lista de anuncios.

## Alcance

Entra:
- Modificación del componente `AdsList.jsx` para incluir botón de favorito.
- Uso del servicio `toggleFavorite` y de la lista de favoritos.

No entra:
- Página dedicada de favoritos.

## Contrato

N/A (modificación de UI existente).

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_favorites_ui.test.ts`, clase `TestFavoritesUILista`.

## Criterio de terminado

- [ ] UI muestra correctamente estado de favorito.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A