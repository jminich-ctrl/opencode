# T26 — Registro backend (creación de cuenta)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
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

```python
def crear_usuario(email: str, password: str) -> int:
    """Crea un usuario y devuelve su id.
    Lanza excepción si el email ya existe.
    """
```

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
