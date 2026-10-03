# T30 — Scaffolding Vite

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T01
**Archivos que podés tocar:** frontend/package.json, frontend/vite.config.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear el proyecto Vite con su package.json y vite.config.ts

## Alcance

Entra:
- Generar `package.json` con dependencias mínimas (react, react-dom, vite).
- Crear `vite.config.ts` básico.

No entra:
- Crear archivos de entrada como main.ts o App.jsx

## Contrato

N/A

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `frontend/tests/test_scaffolding.ts`, clase `TestScaffoldingFrontend`.

## Criterio de terminado

- [ ] Archivo `frontend/package.json` creado con dependencias de Vite y React.
- [ ] Archivo `frontend/vite.config.ts` creado con configuración básica.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A