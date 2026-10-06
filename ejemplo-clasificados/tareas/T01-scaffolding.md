# T01 — Scaffolding del proyecto

**Estado:** ✅ hecha
**Depende de:** ninguna
**Archivos que podés tocar:** backend/, frontend/, backend/requirements.txt, frontend/package.json
**Prohibido tocar:** `scripts/` y `*/tests/` (el paso 0 del gate los verifica)
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear la estructura de carpetas y archivos iniciales del proyecto según la arquitectura definida.

## Cómo se versiona una carpeta

git versiona **archivos**, no directorios: una carpeta vacía no viaja en el commit y el
merge la pierde, aunque el gate del worktree la haya visto. Cada paquete de Python tiene
que tener su `__init__.py` (vacío está bien) y cada carpeta del frontend, al menos un
archivo. Si no, el tronco queda rojo después de integrar tu tarea.

## Alcance

Entra:
- Crear directorios `backend/app/datos`, `backend/app/servicios`, `backend/app/rutas`.
- Crear `backend/requirements.txt` y `frontend/package.json` básicos.
- Inicializar proyecto FastAPI y Vite.

No entra:
- Implementar lógica de negocio ni rutas.

## Contrato

N/A

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_scaffolding.py`, clase `TestScaffolding`.

## Criterio de terminado

- [ ] Estructura de carpetas creada.
- [ ] Archivos básicos presentes.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A