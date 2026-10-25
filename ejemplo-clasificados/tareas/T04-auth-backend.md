# T04 — Auth backend (login, sesión)

**Estado:** pendiente
**Depende de:** T02, T03, T06c
**Archivos que podés tocar:** backend/app/rutas/auth.py, backend/app/servicios/auth.py, backend/app/datos/users.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar el endpoint de login que verifica credenciales y devuelve un token en el cuerpo
de la respuesta.

## Alcance

Entra:
- Lectura de usuarios desde `backend/app/datos/users.py`.
- Verificación del password contra el hash almacenado.
- Manejo de errores de autenticación (401).

No entra:
- Registro de usuarios ni gestión de perfiles.
- **Cookie de sesión httpOnly y logout.** Los pedía la versión anterior de esta tarea y
  **ningún test los cubre**: por P2, lo que no verifica un comando no entra al plan. Si hacen
  falta, van en una tarea propia con sus tests.

## Contrato

Tres archivos, y los tres los importa el test — no son opcionales:

```python
# backend/app/datos/users.py
def read_user_by_email(email: str) -> dict | None:
    """El usuario como dict con al menos `id`, `email` y `password_hash`, o None."""

# backend/app/servicios/auth.py
def login(email: str, password: str) -> dict | None:
    """Verifica credenciales. Devuelve algo con `token` si son válidas, o None."""

# backend/app/rutas/auth.py
router  # APIRouter con POST /auth/login — main.py lo monta solo si existe `router`
```

**Dos cosas que el test impone y que no se deducen leyéndolo rápido:**

1. **El hash es `sha256` hex del password, sin sal.** El test mockea el usuario con
   `password_hash = sha256('password').hexdigest()`, así que la verificación tiene que calcular
   lo mismo. (La versión anterior del test mockeaba el literal `'hashed_password'`, que ningún
   hash real produce: sólo pasaba con una verificación falsa. Se corrigió el test.)
2. **`read_user_by_email` se llama como ATRIBUTO del módulo**: `users.read_user_by_email(email)`
   con `from backend.app.datos import users`. Con
   `from backend.app.datos.users import read_user_by_email` el servicio se queda con su propia
   referencia, el `@patch` del test no aplica, la consulta va a la base de verdad y el test
   falla con 401 — un rojo que no se parece a su causa.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_auth_backend.py`, clase `TestAuthBackend`.

## Criterio de terminado

- [ ] `POST /auth/login` con credenciales válidas devuelve **200** y un `token` en el cuerpo.
- [ ] Con password incorrecto devuelve **401**.
- [ ] Con usuario inexistente devuelve **401**.
- [ ] `bash scripts/gate.sh` en verde.

*(Decía «endpoint `/login`» y el test pega a `/auth/login`. El test es el contrato: P2, el juez
es un comando. El criterio estaba mal, no el test.)*

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A

## Reabierta

la capa de datos de T04 no implementa nada: backend/app/datos/users.py tiene una sola funcion y devuelve None sin hacer nada, declarado en su propio comentario (Por ahora retornamos None como placeholder). Los tres tests de T04 la mockean, asi que el verde no lo gano el producto. Y usuario_desde_token de T04b devuelve el id de cualquier token bien formado sin consultar la base: con un id inexistente contesta ese id en vez de None. Las dos comparten backend/app/servicios/auth.py, asi que se reabren juntas

Se reabrió con scripts/reabrir.sh el 2026-10-25 13:37 UTC. Su código anterior
se sacó del tronco (copia en reabrir-T04+T04b-previo): esta tarea vuelve a pasar por tests-first,
así que el test tiene que fallar antes de que exista la implementación.
