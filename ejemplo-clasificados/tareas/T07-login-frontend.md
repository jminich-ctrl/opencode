# T07 — Login page y servicio auth frontend

**Estado:** ✅ hecha
**Depende de:** T31
**Archivos que podés tocar:** frontend/src/pages/Login.jsx, frontend/src/services/auth.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear la página de login y el servicio de autenticación que envía credenciales al backend y gestiona la cookie de sesión.

## Alcance

Entra:
- Componente React `Login.jsx` con formulario de usuario/contraseña.
- Servicio TypeScript `auth.ts` con función `login(username, password)` que hace `fetch` al endpoint `/login` y guarda la cookie.

No entra:
- Registro de usuarios ni manejo de errores avanzados.

## Contrato

```typescript
export async function login(username: string, password: string): Promise<void>
```

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_login_frontend.test.ts`, clase `TestLoginFrontend`.

## Criterio de terminado

- [ ] Página `Login.jsx` funcional y muestra errores básicos.
- [ ] Servicio `auth.ts` implementado y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
