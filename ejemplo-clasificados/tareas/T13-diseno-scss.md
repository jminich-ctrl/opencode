# T13 — Sistema de diseño propio en SCSS

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T30
**Archivos que podés tocar:** frontend/src/design/_variables.scss, frontend/src/design/_mixins.scss, frontend/src/design/main.scss
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Definir y estructurar el sistema de diseño propio usando SCSS, sin depender de Tailwind.

## Alcance

Entra:
- Variables de colores, tipografía, espacios en `_variables.scss`.
- Mixins reutilizables en `_mixins.scss`.
- Archivo `main.scss` que importa los parciales y establece estilos base.

No entra:
- Componentes UI específicos ni estilos de páginas concretas.

## Contrato

N/A (solo archivos de estilo).

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_design_system_frontend.test.ts`, clase `TestDesignSystemFrontend`.

## Criterio de terminado

- [ ] `_variables.scss`, `_mixins.scss` y `main.scss` creados y con contenido básico.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
