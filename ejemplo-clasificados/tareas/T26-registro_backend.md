# T26 — Registro backend (creación de cuenta)

**Estado:** ✅ hecha
**Depende de:** T03, T06c
**Archivos que podés tocar:** backend/app/rutas/register.py, backend/app/servicios/register.py, backend/app/datos/users_register.py
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Permitir crear una cuenta de usuario mediante endpoint POST `/register` que almacene los datos en la tabla `users`.

## Alcance

Entra:
- Validación básica de datos (email, password).
- Hash de la contraseña **con el mismo esquema que usa `backend/app/servicios/auth.py`
  para verificarla**. Leé ese archivo: `login` compara contra `password_hash`, y si registro
  guarda con otro esquema, ningún usuario registrado va a poder entrar.
- Creación del registro en MySQL.

No entra:
- Verificación de email.
- Roles o permisos avanzados.
- **Cambiar el esquema de hash.** El del ejemplo es un `sha256` sin sal, que es de juguete:
  migrar a `scrypt` o `bcrypt` toca registro Y login a la vez, así que es una tarea propia con
  un test que cruce los dos. Acá decía «hash con `hashlib.scrypt`» mientras `login` comparaba
  `sha256`: las dos tareas pasaban sus tests y juntas rompían el login, porque ninguna prueba
  cruza registro con login y el paso 5 del gate mira capas, no esquemas.

## Contrato

Tres archivos, y los tres los importa el test — no son opcionales:

```python
# backend/app/datos/users_register.py
def insert_user(email: str, password_hash: str) -> int:
    """Inserta la fila y devuelve el id nuevo. Lanza si el email ya existe.
    Recibe el hash YA calculado: el hasheo es del servicio, no de la capa de datos."""

# backend/app/servicios/register.py
def crear_usuario(email: str, password: str) -> int:
    """Valida, hashea con el mismo esquema que `auth.py` y delega en
    `users_register.insert_user`. Devuelve el id."""

# backend/app/rutas/register.py
router  # APIRouter con POST /register — main.py monta solo los módulos de rutas/ que
        # tengan un atributo `router`, así que sin ese nombre el endpoint no existe
```

**Tres cosas que el test impone y que no se deducen leyéndolo rápido:**

1. **La costura para aislar MySQL es `insert_user`, y el test la mockea por su nombre
   completo:** `@patch('backend.app.datos.users_register.insert_user')`. Es la misma forma
   que usa `backend/tests/test_auth_backend.py` con `users.read_user_by_email`.
   **No mockees la conexión.** El escritor de tests inventó
   `users_register.get_db_connection` tres corridas seguidas —un nombre que no está en
   ninguna parte del repo— y el test falló contra la implementación del propio agente con
   `AttributeError: module ... does not have the attribute 'get_db_connection'`. El
   enunciado pedía un test de algo que todavía no existe sin decir por dónde cortarlo, así
   que el agente eligió por nosotros. Quien abre conexiones de verdad es
   `backend/app/datos/conexion.py` (`conexion()`, un context manager), y `insert_user` es
   el único que la usa en esta tarea.

2. **`insert_user` se llama como ATRIBUTO del módulo**: `users_register.insert_user(...)`
   con `from backend.app.datos import users_register`. Con
   `from backend.app.datos.users_register import insert_user` el servicio se queda con su
   propia referencia, el `@patch` del test no aplica, la consulta va a la base de verdad y
   el rojo no se parece a su causa. Misma trampa que documenta T04.

3. **El hash es `sha256` hex del password, sin sal** — lo mismo que verifica `login` en
   `backend/app/servicios/auth.py`. El test tiene que comparar contra
   `hashlib.sha256(password.encode()).hexdigest()`.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_register_backend.py`, clase `TestRegisterBackend`.

## Criterio de terminado

- [ ] Endpoint `/register` creado y funciona.
- [ ] Contraseña almacenada en forma hash.
- [ ] `bash scripts/gate.sh` verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

- ¿Se muestra un mensaje de error claro al intentar registrar un email ya existente?
- Responsable: Jose.

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo, no improvises.
- Necesitás tocar un archivo prohibido: pará y decilo.
