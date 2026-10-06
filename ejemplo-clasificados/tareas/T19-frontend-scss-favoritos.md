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

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_favorites_scss.test.ts`, clase `TestFavoritesSCSS`.

## Criterio de terminado

- [ ] SCSS actualizado y compilado sin errores.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A