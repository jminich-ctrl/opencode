# Plan — sitio de clasificados

**Estado del gate G0:** borrador | aprobado por <quién> el <fecha>

## Objetivo

Crear un sitio de clasificados funcional con backend FastAPI (MySQL sin ORM) y frontend React + Vite. Debe permitir registro/login con cookie de sesión, publicar y editar avisos, listarlos con filtro por categoría, ver la ficha del aviso, marcar favoritos y enviar mensajes entre usuarios. No incluye pagos, moderación, subida de archivos ni búsqueda inteligente.

## Decisiones tomadas

- Scaffolding es la tarea T01 — no se hace antes de planificar.
- Sin gestores extra: `requirements.txt` en backend, `npm` en frontend.
- Tests con pytest y vitest, escritos antes de cada tarea y fallando.
- Primera migración y su reversa forman parte de la tarea del esquema.
- G3 lo hace Jose, 15 min.
- Capas del backend: `app/datos` → `app/servicios` → `app/rutas`.
- El orden de las etapas lo decide el equipo.

## Decisiones abiertas

- Orden exacto de las etapas (agrupación de tareas en cada ETAPA).
- Detalles del esquema de la base de datos (columnas exactas de usuarios, anuncios, favoritos, mensajes).
- Convenciones de nombres de rutas y servicios en el frontend.
- Estrategia de manejo de errores y códigos de respuesta en la API.

## Arquitectura

- **backend/app**
  - `datos/` : acceso directo a MySQL mediante SQL manual.
  - `servicios/` : lógica de negocio.
  - `rutas/` : endpoints FastAPI.
- **backend/migraciones** : scripts SQL con reversa.
- **frontend/src**
  - `pages/` : componentes de página (Login, AdsList, AdDetail, etc.).
  - `services/` : llamadas HTTP al backend.
  - `design/` : estilos SCSS.
- **scripts/_arquitectura.py** : verifica la dirección de dependencias entre capas.

## Tareas

| # | Tarea | Depende de | Archivos | Estado |
|---|---|---|---|---|
| T01 | Scaffolding del proyecto | — | backend/, frontend/, scripts/, backend/requirements.txt, frontend/package.json | pendiente |
| T02 | Script de arquitectura (_arquitectura.py) | T01 | scripts/_arquitectura.py | pendiente |
| T03 | Primera migración (usuarios y anuncios) | T01 | backend/migraciones/001_initial.sql | pendiente |
| T04 | Auth backend (login, sesión) | T03 | backend/app/rutas/auth.py, backend/app/servicios/auth.py, backend/app/datos/users.py | pendiente |
| T05 | CRUD de avisos backend | T04 | backend/app/rutas/ads.py, backend/app/servicios/ads.py, backend/app/datos/ads.py | pendiente |
| T06 | Scaffolding frontend (Vite, React) | T01 | frontend/package.json, frontend/vite.config.ts, frontend/src/main.ts, frontend/src/App.jsx | pendiente |
| T07 | Login page y servicio auth frontend | T06 | frontend/src/pages/Login.jsx, frontend/src/services/auth.ts | pendiente |
| T08 | Listado y detalle de avisos frontend | T07 | frontend/src/pages/AdsList.jsx, frontend/src/pages/AdDetail.jsx, frontend/src/services/ads.ts | pendiente |

> Las etapas **no se declaran acá**: se deducen de la tabla de arriba, que es lo que
> respeta las dependencias y los choques de archivo sin que nadie tenga que acordarse.
> Verlas: `SOLO_ETAPAS=1 bash $AGENTES/scripts/correr-plan.sh`

## Tests que tenemos que escribir

| Tarea | Archivo de test | Clase |
|---|---|---|
| T01 | tests/test_scaffolding.py | TestScaffolding |
| T02 | tests/test_arquitectura.py | TestArquitectura |
| T03 | tests/test_migracion.py | TestMigracion |
| T04 | tests/test_auth_backend.py | TestAuthBackend |
| T05 | tests/test_ads_backend.py | TestAdsBackend |
| T06 | tests/frontend/test_scaffolding_frontend.test.ts | TestScaffoldingFrontend |
| T07 | tests/frontend/test_login_frontend.test.ts | TestLoginFrontend |
| T08 | tests/frontend/test_ads_frontend.test.ts | TestAdsFrontend |

## Gates

- **G0** este plan aprobado
- **G1** por tarea: `scripts/gate.sh` verde
- **G2** revisión humana del diff (ver `plantillas/REVISION.md`)
- **G3** integración: gate completo sobre el tronco + prueba de uso
- **G4** pre-deploy: `scripts/pre-deploy.sh` (secretos, deps, migraciones, build, smoke)
- **G5** deploy: `scripts/deploy.sh` — lo corre una persona, siempre

### G3 — prueba de uso (responsable: Jose, 15 min)

- [ ] ¿Se siente bien usarlo? (latencia, fluidez, pasos comunes)
- [ ] ¿Qué pasa cuando el usuario se equivoca?
- [ ] ¿Cubre los casos reales, o solo el mínimo?
- [ ] ¿Lo entiende alguien que no lo programó?
- [ ] <pregunta propia del proyecto>

## Riesgos

| Riesgo | Qué haríamos |
|---|---|
| Falta de claridad en el esquema DB | Definir schema en revisión temprana |
| Cambios simultáneos en mismos archivos | Usar dependencias y etapas para serializar |
| Integración frontend/backend tardía | Tests de contrato API desde inicio |
