# T04 — Auth backend (login, sesión)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T02, T03, T06c
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

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_auth_backend.py`, clase `TestAuthBackend`.

## Criterio de terminado

- [ ] Endpoint `/login` funcional y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
