# T31 — Punto de entrada frontend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
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

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `frontend/tests/test_scaffolding.ts`, clase `TestScaffoldingFrontend`.

## Criterio de terminado

- [ ] Archivo `frontend/src/main.tsx` creado con montaje de la app React.
- [ ] Archivo `frontend/src/App.jsx` creado con componente raíz básico.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A