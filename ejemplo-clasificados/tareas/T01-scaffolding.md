# T01 — Scaffolding del proyecto

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
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

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `backend/tests/test_scaffolding.py`, clase `TestScaffolding`.

## Criterio de terminado

- [ ] Estructura de carpetas creada.
- [ ] Archivos básicos presentes.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A