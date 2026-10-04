# T02 — Conexión a MySQL

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T01
**Archivos que podés tocar:** backend/app/datos/conexion.py
**Prohibido tocar:** `scripts/` y `*/tests/` (el paso 0 del gate los verifica)
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante)

## Objetivo

El único módulo que abre conexiones a MySQL. Todo `backend/app/datos/*.py` lo usa; nadie
más llama a `pymysql.connect` directamente.

## Por qué está como tarea aparte

Ocho tareas de `datos/` necesitan conectarse. Si cada una resuelve la conexión por su
cuenta hay ocho formas de hacerlo, ocho lugares donde cambiar el puerto y ninguno donde
esté escrito el contrato. El plan no lo declaraba y el hueco aparecía recién cuando la
primera tarea de datos lo necesitaba.

## Alcance

Entra:
- Leer la configuración de las variables de entorno `MYSQL_HOST`, `MYSQL_PORT`,
  `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`. Con valores por defecto razonables para
  `HOST` (`127.0.0.1`) y `PORT` (`3306`); `MYSQL_DB` sin valor por defecto.
- Un gestor de contexto que devuelve una conexión y la cierra siempre, con `commit` si el
  bloque termina bien y `rollback` si levanta una excepción.
- Cursores que devuelven diccionarios, no tuplas: una fila a la que se accede por nombre
  no se rompe cuando la migración agrega una columna en el medio.

No entra:
- Pool de conexiones. No lo pide el encargo y agrega estado compartido que nadie necesita.
- Crear la base ni correr migraciones: eso es T03 y el runner.
- Cualquier consulta SQL concreta.

## Contrato

```python
from contextlib import contextmanager

@contextmanager
def conexion():
    """Abre una conexión a MySQL leída del entorno.

    Hace commit al salir del bloque sin error, rollback si hubo excepción, y cierra
    siempre. Devuelve la conexión; los cursores se piden con `conn.cursor()` y devuelven
    diccionarios.
    """

def configuracion() -> dict:
    """Devuelve host, port, user, password y db leídos del entorno.

    Levanta RuntimeError si falta MYSQL_DB: conectarse a una base sin nombre es un error
    que conviene tener temprano y con mensaje, no un fallo de SQL más adelante.
    """
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `backend/tests/test_conexion.py`, clase `TestConexion`.

El runner levanta MySQL antes de lanzarte (`scripts/entorno.sh`) y exporta las variables:
los tests se conectan a una base real, no a un simulacro.

## Criterio de terminado

- [ ] `configuracion()` lee el entorno y falla con mensaje si falta `MYSQL_DB`.
- [ ] `conexion()` hace commit al salir bien, rollback si hubo excepción, y cierra siempre.
- [ ] Los cursores devuelven diccionarios.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
