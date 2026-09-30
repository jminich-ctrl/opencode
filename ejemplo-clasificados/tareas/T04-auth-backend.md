# T04 — Auth backend (login, sesión)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T03
**Archivos que podés tocar:** backend/app/rutas/auth.py, backend/app/servicios/auth.py, backend/app/datos/users.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar el endpoint de login que verifica credenciales, crea sesión cookie httpOnly y permite logout.

## Alcance

Entra:
- Lectura de usuarios desde `backend/app/datos/users.py`.
- Creación y borrado de cookie de sesión.
- Manejo de errores de autenticación.

No entra:
- Registro de usuarios ni gestión de perfiles.

## Contrato

```python
from fastapi import Request, Response

def login(request: Request) -> Response:
    """Valida credenciales y devuelve respuesta con cookie de sesión."""
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/test_auth_backend.py`, clase `TestAuthBackend`.

## Criterio de terminado

- [ ] Endpoint `/login` funcional y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
