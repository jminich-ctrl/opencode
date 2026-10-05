# T06 — Aplicación FastAPI (punto de entrada)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
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

**Un módulo de `rutas/` que no se pueda importar tiene que hacer fallar el arranque, con
el nombre del módulo y el error original.** No se atrapa la excepción para seguir: si un
módulo de rutas está roto, la aplicación levanta sin sus endpoints y el síntoma es un 404
donde debería haber un 400 —un error que no se parece en nada a su causa—.

Esto ya pasó, y por culpa de cómo estaba escrita esta tarea: la versión anterior decía que
un módulo sin `router` «queda montado en silencio», el agente lo leyó como permiso para
`except Exception: pass`, y los endpoints de T04 desaparecieron sin un solo mensaje.

Un módulo que **sí** importa y no expone `router` es otra cosa y es legítimo (un helper).
Ése se saltea, y para que no haya que adivinar cuáles se montaron, la lista queda en
`app.state.routers_montados`.

## Alcance

Entra:
- Crear la instancia `app = FastAPI()`.
- Recorrer `backend/app/rutas/*.py`, importar cada módulo y, si expone un objeto `router`,
  incluirlo con `app.include_router(router)`.
- Dejar en `app.state.routers_montados` la lista de nombres de módulo que se montaron.
- Si un módulo **no se puede importar**, propagar el error con el nombre del módulo
  adelante. No se atrapa para seguir.
- Un endpoint `GET /salud` que devuelva `{"estado": "ok"}`. Es lo que el smoke test de
  pre-deploy usa para saber que el proceso levantó.
- **Normalizar los errores al contrato del plan.** FastAPI responde `422` con cuerpo
  `{"detail": [...]}` cuando la validación del esquema falla, y el plan cerró en G0 que la
  entrada inválida es `400` con cuerpo `{"error": "<mensaje>"}`. Entonces acá van dos
  manejadores: uno para `RequestValidationError` → 400, y otro para `HTTPException` que
  reescriba `{"detail": ...}` como `{"error": ...}`. Sin eso, cada ruta tendría que validar
  a mano para esquivar el 422, o el plan sería mentira.

No entra:
- Cualquier endpoint de negocio: ésos son de las tareas de `rutas/`.
- Middleware, CORS, autenticación: no los pide el encargo.

## Contrato

```python
from fastapi import FastAPI

app: FastAPI
# Montado al importar el módulo. Los routers de `backend/app/rutas/` se incluyen solos:
# un módulo que exponga `router` queda publicado sin tocar este archivo.
#
# app.state.routers_montados: list[str]  — qué módulos se montaron, para poder verificarlo.
#
# Un módulo de rutas que no se pueda importar hace fallar esta línea, con su nombre.

# GET /salud → 200 {"estado": "ok"}
#
# Y los errores, para TODA la aplicación:
#   RequestValidationError  → 400 {"error": "<mensaje para la persona>"}
#   HTTPException(code, detail) → code {"error": detail}
# Una ruta levanta HTTPException con el código del plan y no arma el cuerpo: lo arma acá.
```

Y el contrato del otro lado, que vale para las seis tareas de rutas: **un módulo de
`rutas/` expone un `router` de FastAPI y nada más. No importa `main.py` ni lo modifica.**

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `backend/tests/test_app.py`, clase `TestApp`.

## Criterio de terminado

- [ ] `from app.main import app` funciona y `app` es una instancia de FastAPI.
- [ ] `GET /salud` responde 200 con `{"estado": "ok"}`.
- [ ] Un router nuevo en `backend/app/rutas/` queda montado sin tocar `main.py`, y su nombre
      aparece en `app.state.routers_montados`.

      **El router de prueba lo crea el test en tiempo de ejecución y lo borra al terminar**
      —escribir el archivo, recargar `app.main`, verificar, y limpiar en un `finally`—. No
      es un entregable: no se commitea y no está en el alcance de esta tarea. Un intento
      anterior lo dejó como archivo y el chequeo de alcance lo reprobó, con razón.
- [ ] Un módulo de `rutas/` que tira error al importarse **hace fallar el import de
      `app.main`**, con el nombre del módulo en el mensaje. Un `except` que lo deje pasar es
      exactamente lo que esta tarea no tiene que hacer.
- [ ] Un POST con el cuerpo incompleto responde **400** —no 422— y el cuerpo es
      `{"error": ...}`.
- [ ] Un `HTTPException(404, "no existe")` sale como `{"error": "no existe"}`.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
