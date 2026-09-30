# T06 — Scaffolding frontend (Vite, React)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T01
**Archivos que podés tocar:** frontend/package.json, frontend/vite.config.ts, frontend/src/main.ts, frontend/src/App.vue
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Inicializar el proyecto frontend con Vite y React, crear la estructura básica de carpetas y archivos de entrada.

## Alcance

Entra:
- Generar `package.json` con dependencias mínimas (react, react-dom, vite).
- Crear `vite.config.ts` básico.
- Crear `src/main.ts` que monta la app.
- Crear `src/App.vue` componente raíz sencillo.

No entra:
- Implementar lógica de páginas ni estilos.

## Contrato

N/A

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `frontend/tests/test_scaffolding.ts`, clase `TestScaffoldingFrontend`.

## Criterio de terminado

- [ ] Estructura de proyecto Vite+React creada.
- [ ] Archivos básicos presentes.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
