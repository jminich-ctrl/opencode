# T03 — Primera migración (usuarios y anuncios)

**Estado:** ✅ hecha
**Depende de:** T01
**Archivos que podés tocar:** backend/migraciones/001_initial.sql, backend/migraciones/001_initial_down.sql
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear el script SQL inicial que define las seis tablas del esquema cerrado en G0 —`usuarios`, `categorias`, `anuncios`, `favoritos`, `mensajes` y `sesiones`— y su script de reversa.

## Alcance

Entra:
- Definir esquema de tablas con columnas básicas.
- La reversa, en su propio archivo: `001_initial_down.sql`, con los `DROP TABLE IF EXISTS`
  en el orden que respete las claves foráneas (primero las que referencian).

No entra:
- Poblado de datos ni lógica de negocio.

## Contrato

El esquema está cerrado en PLAN.md, sección «Decisiones cerradas en G0». Creá exactamente
esas seis tablas, con esos nombres de columna. **No inventes columnas ni cambies nombres**:
hay 26 tareas que dependen de esto.

La migración va en `backend/migraciones/001_initial.sql` y **tiene que tener su reversa**:
`backend/migraciones/001_initial_down.sql`, que deje la base como estaba. Si no se puede
revertir, no se sube.

Las dos se escriben contra MySQL 8: `utf8mb4`, `INT` para los centavos, `DATETIME` en UTC.
El runner levanta la base antes de lanzarte y exporta `MYSQL_HOST`, `MYSQL_PORT`,
`MYSQL_USER`, `MYSQL_PASSWORD` y `MYSQL_DB`: los tests se conectan a una base real.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_migracion.py`, clase `TestMigracion`.

## Criterio de terminado

- [ ] `backend/migraciones/001_initial.sql` crea las seis tablas con los nombres de columna del plan.
- [ ] `backend/migraciones/001_initial_down.sql` las borra en orden y deja la base como estaba.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
