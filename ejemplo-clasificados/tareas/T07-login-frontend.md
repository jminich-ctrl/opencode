# T07 — Login page y servicio auth frontend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T06
**Archivos que podés tocar:** frontend/src/pages/Login.vue, frontend/src/services/auth.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear la página de login y el servicio de autenticación que envía credenciales al backend y gestiona la cookie de sesión.

## Alcance

Entra:
- Componente Vue `Login.vue` con formulario de usuario/contraseña.
- Servicio TypeScript `auth.ts` con función `login(username, password)` que hace `fetch` al endpoint `/login` y guarda la cookie.

No entra:
- Registro de usuarios ni manejo de errores avanzados.

## Contrato

```typescript
export async function login(username: string, password: string): Promise<void>
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `frontend/tests/test_login.ts`, clase `TestLoginFrontend`.

## Criterio de terminado

- [ ] Página `Login.vue` funcional y muestra errores básicos.
- [ ] Servicio `auth.ts` implementado y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
