# T26 — Registro backend (creación de cuenta)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T03
**Archivos que podés tocar:** backend/app/rutas/register.py, backend/app/servicios/register.py, backend/app/datos/users_register.py
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Permitir crear una cuenta de usuario mediante endpoint POST `/register` que almacene los datos en la tabla `users`.

## Alcance

Entra:
- Validación básica de datos (email, password).
- Hash de la contraseña con `hashlib.scrypt`.
- Creación del registro en MySQL.

No entra:
- Verificación de email.
- Roles o permisos avanzados.

## Contrato

```python
def crear_usuario(email: str, password: str) -> int:
    """Crea un usuario y devuelve su id.
    Lanza excepción si el email ya existe.
    """
```

## Tests (ya escritos, fallando)

Los tests de esta tarea están en `tests/backend/test_register_backend.py` bajo la clase `TestRegisterBackend`.

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
