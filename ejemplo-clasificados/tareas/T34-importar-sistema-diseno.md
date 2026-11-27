# T34 — Importar el sistema de diseño en el punto de entrada

**Estado:** pendiente
**Depende de:** T13, T31
**Archivos que podés tocar:** frontend/src/main.tsx
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Que `frontend/src/main.tsx` importe `./design/main.scss`, para que el sistema de diseño llegue a la aplicación. Hoy no lo importa nadie y el sitio se renderiza sin estilos.

## Alcance

Entra:
- Agregar el import de `./design/main.scss` en `frontend/src/main.tsx`.

No entra:
- El sistema de diseño en SCSS (ya hecho en T13).
- El punto de entrada React `main.tsx` (ya hecho en T31).

## Contrato

N/A

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_import_diseno_frontend.test.ts`, clase `TestImportDisenoFrontend`.

## Criterio de terminado

- [ ] `frontend/src/main.tsx` importa `./design/main.scss`.
- [ ] `npm --prefix frontend run build` termina sin error.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    npm --prefix frontend run build
    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
