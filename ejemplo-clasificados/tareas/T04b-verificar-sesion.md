# T04b — Verificar la sesión a partir del token

**Estado:** pendiente
**Depende de:** T04
**Archivos que podés tocar:** backend/app/servicios/auth.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Dar a las rutas una forma de saber **qué usuario** hizo el pedido, a partir del token que
emite el login.

## Por qué existe esta tarea

T05 pide, textual, «respetando la autorización del usuario», pero no podía: su contrato no
decía cómo obtener el usuario actual, sus archivos permitidos no incluyen
`servicios/auth.py`, y T04 entrega sólo `login`. El agente hizo lo único que podía —inventó
`obtener_usuario_id_desde_token`, cableó tres archivos a ella, y se quedó veinte minutos
iterando contra su propio `ImportError`— tres veces seguidas.

La tarea exigía autorización, prohibía tocar auth, y el medio no existía. Esto lo provee.

## Alcance

Entra:
- Una función que recibe el token y devuelve el id del usuario, o `None`.

No entra:
- Cambiar el formato del token. El de este ejemplo es **simulado** (ver abajo); cambiarlo a
  un esquema real —firmado, con vencimiento— es una tarea propia con sus tests.
- Middleware ni dependencias de FastAPI: las rutas llaman a la función.

## Contrato

```python
# backend/app/servicios/auth.py  (ya existe, se le agrega esto)
def usuario_desde_token(token: str) -> int | None:
    """El id del usuario dueño del token, o None si el token no es válido."""
```

**El formato del token lo define `login`, que ya está en ese mismo archivo: leelo.** Hoy
emite un token **simulado**, no firmado y sin vencimiento. No lo cambies acá: esta función
tiene que aceptar exactamente lo que `login` emite, y nada más. Un token inválido, vacío o
con otra forma devuelve `None` — no una excepción.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_sesion.py`, clase `TestSesion`.

## Criterio de terminado

- [ ] El token que devuelve `login` para un usuario da el id de ese usuario.
- [ ] Un token inválido, vacío o de otra forma devuelve `None`, sin levantar excepción.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A

## Reabierta

la capa de datos de T04 no implementa nada: backend/app/datos/users.py tiene una sola funcion y devuelve None sin hacer nada, declarado en su propio comentario (Por ahora retornamos None como placeholder). Los tres tests de T04 la mockean, asi que el verde no lo gano el producto. Y usuario_desde_token de T04b devuelve el id de cualquier token bien formado sin consultar la base: con un id inexistente contesta ese id en vez de None. Las dos comparten backend/app/servicios/auth.py, asi que se reabren juntas

Se reabrió con scripts/reabrir.sh el 2026-10-25 13:37 UTC. Su código anterior
se sacó del tronco (copia en reabrir-T04+T04b-previo): esta tarea vuelve a pasar por tests-first,
así que el test tiene que fallar antes de que exista la implementación.
