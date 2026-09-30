# T19 — Favoritos SCSS

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T18
**Archivos que podés tocar:** frontend/src/design/_favorites.scss
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Agregar los estilos SCSS necesarios para el icono de favorito.

## Alcance

Entra:
- Definición de clases/variables para el icono activo e inactivo.

No entra:
- Cambios en componentes JSX.

## Contrato

N/A (solo estilos).

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_favorites_scss.test.ts`, clase `TestFavoritesSCSS`.

## Criterio de terminado

- [ ] SCSS actualizado y compilado sin errores.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A