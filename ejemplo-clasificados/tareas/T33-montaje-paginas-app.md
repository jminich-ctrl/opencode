# T33 — Montaje de páginas en App.jsx

**Estado:** pendiente
**Depende de:** T07, T08, T27, T29, T31
**Archivos que podés tocar:** frontend/src/App.jsx
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Que App.jsx monte Login, Register, AdsList, AdDetail y SearchBar.

## Alcance

Entra:
- Montar en `frontend/src/App.jsx` las páginas Login, Register, AdsList, AdDetail y SearchBar.

No entra:
- Crear las páginas (ya hechas en T07, T08, T27, T29).
- El punto de entrada React `main.tsx` (ya hecho en T31).

## Contrato

Navegación por estado dentro de App.jsx: un estado `pagina` (una cadena) y una condición por página. SIN react-router, porque la lista cerrada de dependencias del proyecto no lo incluye.

Las cinco páginas que se montan, y de dónde vienen:
- `Login` — `frontend/src/pages/Login.jsx`
- `Register` — `frontend/src/pages/Register.jsx`
- `AdsList` — `frontend/src/pages/AdsList.jsx`
- `AdDetail` — `frontend/src/pages/AdDetail.jsx`
- `SearchBar` — `frontend/src/components/SearchBar.jsx`

Cómo agrega su página una tarea posterior, sin coordinarse: importar el componente y agregar su caso (su condición sobre `pagina`). Si App.jsx ya tiene otras páginas montadas, se PRESERVAN: se agregan las cinco sin borrar lo que ya está.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_montaje_app_frontend.test.tsx`, clase `TestMontajeAppFrontend`.

> El test monta componentes, así que tiene que ser `.tsx`; el JSX en un archivo `.ts` no compila.

## Criterio de terminado

- [ ] `frontend/src/App.jsx` monta Login, Register, AdsList, AdDetail y SearchBar.
- [ ] Navegación por estado `pagina`, una condición por página, sin react-router.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
