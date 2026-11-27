# T32 — Punto de entrada HTML del frontend

**Estado:** pendiente
**Depende de:** T30, T31
**Archivos que podés tocar:** frontend/index.html
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Que `frontend/index.html` exista, con `<div id="root"></div>` y la referencia a `/src/main.tsx`, para que vite pueda construir.

## Alcance

Entra:
- Crear `frontend/index.html` con `<div id="root"></div>` y la referencia a `/src/main.tsx`.

No entra:
- Configuración de Vite o package.json (ya hecho en T30).
- El punto de entrada React `main.tsx` (ya hecho en T31).

## Contrato

N/A

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_index_html_frontend.test.ts`, clase `TestIndexHtmlFrontend`.

## Criterio de terminado

- [ ] Archivo `frontend/index.html` creado con `<div id="root"></div>` y la referencia a `/src/main.tsx`.
- [ ] `npm --prefix frontend run build` termina sin error.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    npm --prefix frontend run build
    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
