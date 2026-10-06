# T06b — Montaje automático de routers

**Estado:** ✅ hecha
**Depende de:** T06a
**Archivos que podés tocar:** backend/app/main.py
**Prohibido tocar:** `scripts/` y `*/tests/` (el paso 0 del gate los verifica)
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante)

## Objetivo

Que `app` monte solo los routers que encuentre en `backend/app/rutas/`, y que un módulo
roto haga fallar el arranque en vez de desaparecer en silencio.

## Por qué monta solo, y por qué falla ruidosamente

Si cada tarea de rutas tuviera que agregar su `include_router` a `main.py`, seis tareas
editarían el mismo archivo —choque garantizado en el deductor de etapas, y merges en serie
donde podría haber paralelo—. Descubriendo los routers, `main.py` se escribe una vez y
nadie más lo toca.

**Un módulo de `rutas/` que no se pueda importar tiene que hacer fallar el arranque, con el
nombre del módulo y el error original.** No se atrapa la excepción para seguir: si un
módulo de rutas está roto, la aplicación levanta sin sus endpoints y el síntoma es un 404
donde debería haber un 400 —un error que no se parece en nada a su causa—.

Esto ya pasó, y por culpa de cómo estaba escrita la tarea anterior: decía que un módulo sin
`router` «queda montado en silencio», el agente lo leyó como permiso para
`except Exception: pass`, y los endpoints de T04 desaparecieron sin un solo mensaje.

Un módulo que **sí** importa y no expone `router` es otra cosa y es legítimo (un helper).
Ése se saltea, y para que no haya que adivinar cuáles se montaron, la lista queda en
`app.state.routers_montados`.

## Alcance

Entra:
- Recorrer `backend/app/rutas/*.py`, importar cada módulo y, si expone un objeto `router`,
  incluirlo con `app.include_router(router)`.
- Dejar en `app.state.routers_montados` la lista de nombres de módulo que se montaron.
- Si un módulo **no se puede importar**, propagar el error con el nombre del módulo
  adelante. No se atrapa para seguir.

No entra:
- La instancia `app` ni `/salud`: ya están, son de T06a.
- La normalización de errores: eso es T06c.
- Cualquier endpoint de negocio.

## Contrato

```python
# Montado al importar el módulo. Los routers de `backend/app/rutas/` se incluyen solos:
# un módulo que exponga `router` queda publicado sin tocar este archivo.
#
# app.state.routers_montados: list[str]  — qué módulos se montaron, para poder verificarlo.
#
# Un módulo de rutas que no se pueda importar hace fallar el import de app.main, con su
# nombre en el mensaje.
```

Y el contrato del otro lado, que vale para las seis tareas de rutas: **un módulo de
`rutas/` expone un `router` de FastAPI y nada más. No importa `main.py` ni lo modifica.**

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_montaje.py`, clase `TestMontaje`.

Los dos casos necesitan crear un módulo en `rutas/` en tiempo de ejecución y recargar
`app.main`. Un esqueleto que sirve para los dos, para no tener que deducirlo:

```python
import importlib, pathlib, sys

RUTAS = pathlib.Path("backend/app/rutas")

def _recargar():
    """Reimporta app.main y devuelve el módulo. La instancia nueva es `mod.app`."""
    import app.main as mod
    return importlib.reload(mod)

def _sembrar(nombre, contenido):
    """Escribe un módulo de rutas y devuelve una función para limpiarlo."""
    f = RUTAS / f"{nombre}.py"
    f.write_text(contenido)
    def limpiar():
        f.unlink(missing_ok=True)
        sys.modules.pop(f"app.rutas.{nombre}", None)
        _recargar()          # deja app.main sano para los tests que siguen
    return limpiar
```

## Criterio de terminado

- [ ] Un router nuevo en `backend/app/rutas/` queda montado sin tocar `main.py`, y su nombre
      aparece en `app.state.routers_montados`.

      **El router de prueba lo crea el test en tiempo de ejecución y lo borra al terminar**,
      con la limpieza en un `finally`. No es un entregable: no se commitea y no está en el
      alcance de esta tarea. Un intento anterior lo dejó como archivo y el chequeo de
      alcance lo reprobó, con razón.
- [ ] Un módulo de `rutas/` que tira error al importarse **hace fallar el import de
      `app.main`**, con el nombre del módulo en el mensaje. Un `except` que lo deje pasar es
      exactamente lo que esta tarea no tiene que hacer.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
