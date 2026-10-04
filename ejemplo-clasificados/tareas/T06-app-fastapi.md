# T06 — Aplicación FastAPI (punto de entrada)

**Estado:** ✅ hecha
**Depende de:** T02
**Archivos que podés tocar:** backend/app/main.py
**Prohibido tocar:** `scripts/` y `*/tests/` (el paso 0 del gate los verifica)
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante)

## Objetivo

El objeto `app` de FastAPI, que es lo que arranca el servidor y lo que los tests usan como
cliente. Monta automáticamente los routers que encuentre en `backend/app/rutas/`.

## Por qué está como tarea aparte, y por qué monta solo

Seis tareas escriben un módulo en `rutas/` y **ninguna tenía asignado el `main.py`** donde
esos endpoints se registran. El agente de T04 lo creó por su cuenta —hacía falta para que
su propio test pudiera llamar al endpoint— y el chequeo de alcance lo reprobó por eso: es
el mismo hueco que el módulo de conexión y las dependencias del corredor de tests.

La parte que sí es una decisión: **el montaje es automático.** Si cada tarea de rutas
tuviera que agregar su `include_router` a `main.py`, seis tareas editarían el mismo archivo
—choque garantizado en el deductor de etapas, y merges en serie donde podría haber
paralelo—. Descubriendo los routers, `main.py` se escribe una vez y nadie más lo toca.

El precio es que un módulo de `rutas/` que no exponga `router` queda montado en silencio.
A cambio, queda verificable de un lado: el test de esta tarea monta un router de prueba y
comprueba que respondió.

## Alcance

Entra:
- Crear la instancia `app = FastAPI()`.
- Recorrer `backend/app/rutas/*.py`, importar cada módulo y, si expone un objeto `router`,
  incluirlo con `app.include_router(router)`.
- Un endpoint `GET /salud` que devuelva `{"estado": "ok"}`. Es lo que el smoke test de
  pre-deploy usa para saber que el proceso levantó.

No entra:
- Cualquier endpoint de negocio: ésos son de las tareas de `rutas/`.
- Middleware, CORS, autenticación: no los pide el encargo.

## Contrato

```python
from fastapi import FastAPI

app: FastAPI
# Montado al importar el módulo. Los routers de `backend/app/rutas/` se incluyen solos:
# un módulo que exponga `router` queda publicado sin tocar este archivo.

# GET /salud → 200 {"estado": "ok"}
```

Y el contrato del otro lado, que vale para las seis tareas de rutas: **un módulo de
`rutas/` expone un `router` de FastAPI y nada más. No importa `main.py` ni lo modifica.**

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `backend/tests/test_app.py`, clase `TestApp`.

## Criterio de terminado

- [ ] `from app.main import app` funciona y `app` es una instancia de FastAPI.
- [ ] `GET /salud` responde 200 con `{"estado": "ok"}`.
- [ ] Un router nuevo en `backend/app/rutas/` queda montado sin tocar `main.py`.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
