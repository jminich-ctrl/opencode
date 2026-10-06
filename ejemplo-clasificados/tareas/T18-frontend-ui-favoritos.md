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

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_favorites_ui.test.ts`, clase `TestFavoritesUILista`.

## Criterio de terminado

- [ ] UI muestra correctamente estado de favorito.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A