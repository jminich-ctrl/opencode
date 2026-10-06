# T31 — Punto de entrada frontend

**Estado:** ✅ hecha
**Depende de:** T30
**Archivos que podés tocar:** frontend/src/main.tsx, frontend/src/App.jsx
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear el punto de entrada principal del frontend con React y JSX

## Alcance

Entra:
- Crear `frontend/src/main.tsx` que monta la aplicación React.
- Crear `frontend/src/App.jsx` componente raíz sencillo.

No entra:
- Configuración de Vite o package.json (ya hecho en T30).

## Contrato

N/A

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_entrypoint_frontend.test.ts`, clase `TestEntrypointFrontend`.

## Criterio de terminado

- [ ] Archivo `frontend/src/main.tsx` creado con montaje de la app React.
- [ ] Archivo `frontend/src/App.jsx` creado con componente raíz básico.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A