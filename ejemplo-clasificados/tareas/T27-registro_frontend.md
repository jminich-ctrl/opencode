# T27 — Registro frontend (página y servicio)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T31
**Archivos que podés tocar:** frontend/src/pages/Register.jsx, frontend/src/services/register.ts
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Implementar la página de registro y el servicio que llama al endpoint backend `/register` para crear una cuenta.

## Alcance

Entra:
- Formulario con campos email y password.
- Validación básica en el cliente.
- Llamada HTTP POST al backend y manejo de respuestas.

No entra:
- OAuth o login social.
- Confirmación de email.

## Contrato

```typescript
export async function registrarUsuario(email: string, password: string): Promise<void>;
```

## Tests (ya escritos, fallando)

Los tests de esta tarea están en `tests/frontend/test_register_frontend.test.ts` bajo la clase `TestRegisterFrontend`.

## Criterio de terminado

- [ ] Página `Register.jsx` muestra el formulario y envía datos.
- [ ] Servicio `register.ts` realiza la petición y maneja errores.
- [ ] `bash scripts/gate.sh` verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

- ¿Muestra mensajes de error claros al intentar registrar con email ya usado?
- Responsable: Jose.

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo.
- Necesitás tocar un archivo prohibido: pará y decilo.
