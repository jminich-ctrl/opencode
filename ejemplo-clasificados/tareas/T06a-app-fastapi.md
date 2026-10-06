# T06a — Aplicación FastAPI (la instancia y /salud)

**Estado:** ✅ hecha
**Depende de:** T02
**Archivos que podés tocar:** backend/app/main.py
**Prohibido tocar:** `scripts/` y `*/tests/` (el paso 0 del gate los verifica)
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante)

## Objetivo

El objeto `app` de FastAPI: lo que arranca el servidor y lo que los tests usan como
cliente. Nada más que eso y un endpoint de salud.

## Por qué está como tarea aparte

Seis tareas escriben un módulo en `rutas/` y **ninguna tenía asignado el `main.py`** donde
esos endpoints se registran. El agente de T04 lo creó por su cuenta —hacía falta para que
su propio test pudiera llamar al endpoint— y el chequeo de alcance lo reprobó por eso.

Y por qué está partida en tres (T06a, T06b, T06c): la versión anterior juntaba la
instancia, el montaje automático de routers y la normalización de errores en una sola
tarea de 114 líneas y 7 criterios, contra las 44–87 líneas y 2–4 criterios de todas las
tareas que sí cerraron. El agente gastaba su presupuesto entero razonando sobre semántica
de `importlib.reload` y no escribía una línea. **Una tarea que es el doble de grande que
las que pasan no es una tarea difícil: es dos o tres tareas.**

## Alcance

Entra:
- Crear la instancia `app = FastAPI()` en `backend/app/main.py`.
- Un endpoint `GET /salud` que devuelva `{"estado": "ok"}`. Es lo que el smoke test de
  pre-deploy usa para saber que el proceso levantó.

No entra:
- El montaje automático de routers: eso es T06b.
- La normalización de errores: eso es T06c.
- Cualquier endpoint de negocio: ésos son de las tareas de `rutas/`.
- Middleware, CORS, autenticación: no los pide el encargo.

## Contrato

```python
from fastapi import FastAPI

app: FastAPI

# GET /salud → 200 {"estado": "ok"}
```

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_app.py`, clase `TestApp`.

## Criterio de terminado

- [ ] `from app.main import app` funciona y `app` es una instancia de FastAPI.
- [ ] `GET /salud` responde 200 con `{"estado": "ok"}`.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
