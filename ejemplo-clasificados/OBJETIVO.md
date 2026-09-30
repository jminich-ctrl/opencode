# Objetivo del proyecto

Un sitio de clasificados usable: publicás un aviso, la gente lo encuentra, te escribe.

**Entra:** registro y login, publicar/editar/borrar avisos propios, listado con búsqueda y
filtro por categoría, detalle del aviso, favoritos, mensajes entre usuarios.

**No entra:** pagos, moderación, mails, subida de archivos (las fotos van por URL),
búsqueda con ranking. Un idioma, un país.

## Decisiones ya cerradas por un humano

No las rediscutas. Si algo del plan parece pedir lo contrario, avisá.

- **Backend: FastAPI + MySQL con SQL crudo** (sin ORM), como el `api-v2` de la casa.
- **Migraciones: archivos `.sql` numerados con `-- up` y `-- down`**, aplicadas por un
  script propio. Cada una reversible.
- **Frontend: React + Vite + SCSS + Vitest/Testing Library.** Sin Tailwind y sin librerías
  de componentes: el diseño es propio.
- **Sesión por cookie `httpOnly` con `SameSite=Lax`.** No JWT en localStorage.
- **Contraseñas con `hashlib.scrypt`** (biblioteca estándar), sal por usuario. Sin bcrypt.
- **Todo en UTC**: `DATETIME` en la base, ISO-8601 en la API.
- **IDs enteros autoincrement.**
- **Los tests se escriben ANTES de cada tarea**: cada tarea llega con sus tests fallando y
  el agente los hace pasar sin tocarlos. Tu plan tiene que decir, por tarea, **qué tests
  hay que escribir primero y qué nombre tienen**.
- **El backend sirve el frontend compilado** en producción: un proceso, un deploy.
- **Una sola puerta al backend desde el front**: todo `fetch` vive en `src/services/api.js`.

## Estructura que ya existe

```
backend/app/  backend/migraciones/  backend/tests/
frontend/src/{design,pages,services}/  frontend/tests/
scripts/  tareas/
```

## Entorno

MySQL 8 instalado localmente (hoy apagado: `brew services start mysql`). Python 3.12,
Node disponible. Nada de Docker.
