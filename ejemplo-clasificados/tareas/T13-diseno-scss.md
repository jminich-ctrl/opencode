# T13 — Sistema de diseño propio en SCSS

**Estado:** ✅ hecha
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

Los archivos no exportan una API, pero el sistema de diseño **sí tiene conducta
verificable**: compila. Eso es lo que el test tiene que mirar, y no el texto de los
archivos —un test que busca una cadena en un `.scss` pasa o falla según cómo esté escrito,
no según qué haga—.

```js
// Lo que el test puede hacer, con `sass`, que está en devDependencies:
import * as sass from 'sass';
const { css } = sass.compile('frontend/src/design/main.scss');
```

Y entonces verificar sobre el CSS compilado:

- que compilar **no tira error**, que es lo que prueba que los `@use`/`@import` resuelven
  y que las variables y mixins que `main.scss` usa existen de verdad;
- que la salida trae una regla para `body` con `color` y `font-family` resueltos a valores
  concretos —no a nombres de variable—, que es lo que prueba que los parciales se
  aplicaron;
- que un mixin de `_mixins.scss`, usado en una prueba, produce las declaraciones que
  promete.

Las tres fallan si `_variables.scss` o `_mixins.scss` no están, o si `main.scss` no los
importa, que es exactamente el criterio de terminado de esta tarea.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_design_system_frontend.test.ts`, clase `TestDesignSystemFrontend`.

## Criterio de terminado

- [ ] `_variables.scss`, `_mixins.scss` y `main.scss` creados y con contenido básico.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
