# T30 — Scaffolding Vite

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T01
**Archivos que podés tocar:** frontend/package.json, frontend/vite.config.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear el proyecto Vite con su package.json y vite.config.ts

## El corredor de tests es parte del andamiaje

El plan tiene catorce archivos `.test.ts` y **ninguna otra tarea declara con qué se corren**.
Entonces los declara esta: `package.json` tiene que traer, en `devDependencies`, `vite`,
`@vitejs/plugin-react`, `vitest`, `jsdom` y `@testing-library/react`, más un script
`"test": "vitest run"`. Y `vite.config.ts` tiene que configurar `test.environment = "jsdom"`.

**No borres lo que ya estaba declarado.** El `package.json` que encontrás lo creó T01:
ampliálo, no lo reescribas de cero. En el primer intento esta tarea perdió
`@vitejs/plugin-react`, que su propio `vite.config.ts` importaba, y la validación se cayó
con un «Cannot find package» que no decía nada de la causa.

Sin eso, cada tarea de frontend se cae con «falta el corredor», que no es culpa de quien
escribe el test.

## Alcance

Entra:
- Generar `package.json` con dependencias mínimas (react, react-dom, vite).
- Crear `vite.config.ts` básico.

No entra:
- Crear archivos de entrada como main.ts o App.jsx

## Contrato

N/A

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `frontend/tests/test_scaffolding_frontend.test.ts`, clase `TestScaffoldingFrontend`.

## Criterio de terminado

- [ ] Archivo `frontend/package.json` creado con dependencias de Vite y React.
- [ ] Archivo `frontend/vite.config.ts` creado con configuración básica.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A