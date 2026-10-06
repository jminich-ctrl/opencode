# T06c — Normalizar los errores al contrato del plan

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T06b
**Archivos que podés tocar:** backend/app/main.py
**Prohibido tocar:** `scripts/` y `*/tests/` (el paso 0 del gate los verifica)
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante)

## Objetivo

Que toda la aplicación devuelva los errores con la forma que el plan cerró en G0, en un
solo lugar, para que ninguna ruta tenga que armarlos a mano.

## Por qué

FastAPI responde `422` con cuerpo `{"detail": [...]}` cuando la validación del esquema
falla. El plan cerró en G0 que **la entrada inválida es `400` con cuerpo
`{"error": "<mensaje>"}`**. Son dos contratos distintos para lo mismo, y si no se concilian
acá pasa una de dos: cada ruta valida a mano para esquivar el 422 —seis tareas repitiendo
el mismo código— o el plan es mentira.

## Alcance

Entra, los dos en `backend/app/main.py`:
- Un manejador de `RequestValidationError` que responda **400** con `{"error": "<mensaje>"}`.
- Un manejador de `HTTPException` que reescriba `{"detail": ...}` como `{"error": ...}`,
  conservando el código de estado.

No entra:
- La instancia `app`, `/salud` ni el montaje de routers: ya están (T06a, T06b).
- Logging, reporte de errores a un servicio externo, middleware: no los pide el encargo.

## Contrato

```python
# Para TODA la aplicación:
#   RequestValidationError      → 400  {"error": "<mensaje para la persona>"}
#   HTTPException(code, detail) → code {"error": detail}
#
# Una ruta levanta HTTPException con el código del plan y NO arma el cuerpo: lo arma acá.
```

## Tests

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_errores.py`, clase `TestErrores`.

Para probarlo hace falta una ruta que valide un cuerpo y otra que levante `HTTPException`.
Las dos las monta el test sobre la propia `app` con `app.post(...)` / `app.get(...)`
**dentro del test**: no hace falta crear archivos en `rutas/` ni recargar nada.

## Criterio de terminado

- [ ] Un POST con el cuerpo incompleto responde **400** —no 422— y el cuerpo es
      `{"error": ...}`.
- [ ] Un `HTTPException(404, "no existe")` sale como `{"error": "no existe"}`, con código 404.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
