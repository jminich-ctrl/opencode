# T05a — Avisos datos (CRUD en MySQL)

**Estado:** ✅ hecha
**Depende de:** T03
**Archivos que podés tocar:** backend/app/datos/ads.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

La capa de datos de los avisos: las cuatro operaciones contra la tabla `anuncios`, con SQL a mano.
> **Esta tarea sale de partir T05.** T05 pedía las tres capas y los cinco endpoints en un
> solo enunciado, y falló seis veces con seis diagnósticos distintos —presupuesto, un test
> que contradecía el esquema, el dialecto SQL, la capa del test, la autenticación y el patch
> mal apuntado—. Cada arreglo la hacía llegar un paso más lejos, que es la firma de una tarea
> que pide demasiado de una vez. Y el plan ya partía así todo lo demás: favoritos en
> T14/T15/T16 y mensajes en T20/T21/T22, una capa por tarea. T05 era la anomalía.


## Alcance

Entra:
- `insert_ad`, `get_ad_by_id`, `update_ad`, `delete_ad`.
- SQL a mano con `pymysql`, usando `conexion()` (ver `AGENTS.md`).

No entra:
- Validación de datos: eso es de T05b.
- Autorización: el dueño se verifica en T05b, no acá.
- Endpoints HTTP: son de T05c.

## Contrato

```python
# backend/app/datos/ads.py
def insert_ad(usuario_id: int, categoria_id: int, titulo: str, descripcion: str,
              precio_centavos: int) -> int: ...          # devuelve el id nuevo
def get_ad_by_id(ad_id: int) -> dict | None: ...
def update_ad(ad_id: int, usuario_id: int, titulo: str, descripcion: str,
              precio_centavos: int) -> bool: ...         # False si el aviso no es de ese usuario
def delete_ad(ad_id: int, usuario_id: int) -> bool: ...  # ídem
```

**Los nombres de columna salen del esquema que `PLAN.md` ya cerró, no se inventan:**
`anuncios(id, usuario_id NOT NULL, categoria_id NOT NULL, titulo, descripcion,
precio_centavos, …)`, con FOREIGN KEY a `usuarios` y a `categorias`. Es `precio_centavos`,
no `precio`: plata en enteros.

**Cómo se abre la conexión y cómo se obtiene el id insertado está en `AGENTS.md`**, y las dos
cosas ya costaron una corrida cada una: `conexion()` es el único ayudante —`get_db_connection`
no existe— y el id sale de `cur.lastrowid`, porque `INSERT … RETURNING id` es de PostgreSQL y
MySQL contesta un 1064.

**El filtro por dueño va en el `WHERE`:** `update_ad` y `delete_ad` reciben `usuario_id` y
devuelven `False` cuando no afectaron ninguna fila. Así la autorización no se puede saltear
desde arriba.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Archivo: `backend/tests/test_ads_datos.py`, clase `TestAdsDatos`.

## Criterio de terminado

- [ ] Las cuatro funciones existen con la firma del contrato y sus tests pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo, no improvises.
- Necesitás tocar un archivo prohibido: pará y decilo.
