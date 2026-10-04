# T03 — Primera migración (usuarios y anuncios)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T01
**Archivos que podés tocar:** backend/migraciones/001_initial.sql
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear el script SQL inicial que define las tablas `usuarios`, `anuncios`, `favoritos` y `mensajes`, y su script de reversa.

## Alcance

Entra:
- Definir esquema de tablas con columnas básicas.
- Incluir sentencias `DROP TABLE IF EXISTS` para reversa.

No entra:
- Poblado de datos ni lógica de negocio.

## Contrato

El esquema está cerrado en PLAN.md, sección «Decisiones cerradas en G0». Creá exactamente
esas seis tablas, con esos nombres de columna. **No inventes columnas ni cambies nombres**:
hay 26 tareas que dependen de esto.

La migración va en `backend/migraciones/001_inicial.sql` y **tiene que tener su reversa**:
un `001_inicial_down.sql` que deje la base como estaba. Si no se puede revertir, no se sube.

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/test_migracion.py`, clase `TestMigracion`.

## Criterio de terminado

- [ ] Archivo `backend/migraciones/001_initial.sql` creado con esquema y reversa.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
