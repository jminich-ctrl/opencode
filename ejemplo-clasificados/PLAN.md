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
| T30 | Scaffolding Vite | T01 | frontend/package.json, frontend/vite.config.ts | pendiente |
| T31 | Punto de entrada frontend | T30 | frontend/src/main.tsx, frontend/src/App.jsx | pendiente |
| T07 | Login page y servicio auth frontend | T31 | frontend/src/pages/Login.jsx, frontend/src/services/auth.ts | pendiente |
| T08 | Listado y detalle de avisos frontend | T07 | frontend/src/pages/AdsList.jsx, frontend/src/pages/AdDetail.jsx, frontend/src/services/ads.ts | pendiente |
| T14 | Favoritos datos | T05 | backend/app/datos/favorites.py | pendiente |
| T15 | Favoritos servicio | T14 | backend/app/servicios/favorites.py | pendiente |
| T16 | Favoritos rutas | T15 | backend/app/rutas/favorites.py | pendiente |
| T17 | Favoritos servicio frontend | T16, T08 | frontend/src/services/favorites.ts | pendiente |
| T18 | Favoritos UI lista | T17 | frontend/src/pages/AdsList.jsx | pendiente |
| T19 | Favoritos SCSS | T18 | frontend/src/design/_favorites.scss | pendiente |
| T20 | Mensajes datos | T05 | backend/app/datos/messages.py | pendiente |
| T21 | Mensajes servicio | T20 | backend/app/servicios/messages.py | pendiente |
| T22 | Mensajes rutas | T21 | backend/app/rutas/messages.py | pendiente |
| T23 | Mensajes servicio frontend | T22 | frontend/src/services/messages.ts | pendiente |
| T24 | Mensajes UI lista | T23 | frontend/src/pages/Messages.jsx | pendiente |
| T25 | Mensajes UI detalle | T23 | frontend/src/pages/MessageDetail.jsx | pendiente |
| T11 | Editar propios avisos | T05, T08 | frontend/src/pages/EditAd.jsx, frontend/src/services/ads.ts | pendiente |
| T12 | Filtro por categoría en listado | T08 | frontend/src/pages/AdsList.jsx, frontend/src/design/_filters.scss | pendiente |
| T13 | Sistema de diseño propio en SCSS | T31 | frontend/src/design/_variables.scss, frontend/src/design/_mixins.scss, frontend/src/design/main.scss | pendiente |
| T26 | Registro backend (creación de cuenta) | T03 | backend/app/rutas/register.py, backend/app/servicios/register.py, backend/app/datos/users_register.py | pendiente |
| T27 | Registro frontend (página y servicio) | T31 | frontend/src/pages/Register.jsx, frontend/src/services/register.ts | pendiente |
| T28 | Búsqueda backend (texto y categoría) | T05 | backend/app/rutas/search.py, backend/app/servicios/search.py, backend/app/datos/search_ads.py | pendiente |
| T29 | Búsqueda frontend (UI y servicio) | T08 | frontend/src/components/SearchBar.jsx, frontend/src/services/search.ts | pendiente |

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
| T14 | tests/backend/test_favorites_datos.py | TestFavoritesDatos |
| T15 | tests/backend/test_favorites_servicio.py | TestFavoritesServicio |
| T16 | tests/backend/test_favorites_rutas.py | TestFavoritesRutas |
| T17 | tests/frontend/test_favorites_servicio.test.ts | TestFavoritesServicioFrontend |
| T18 | tests/frontend/test_favorites_ui.test.ts | TestFavoritesUILista |
| T19 | tests/frontend/test_favorites_scss.test.ts | TestFavoritesSCSS |
| T20 | tests/backend/test_messages_datos.py | TestMessagesDatos |
| T21 | tests/backend/test_messages_servicio.py | TestMessagesServicio |
| T22 | tests/backend/test_messages_rutas.py | TestMessagesRutas |
| T23 | tests/frontend/test_messages_servicio.test.ts | TestMessagesServicioFrontend |
| T24 | tests/frontend/test_messages_ui_lista.test.ts | TestMessagesUILista |
| T25 | tests/frontend/test_messages_ui_detalle.test.ts | TestMessagesUIDetalle |
| T11 | tests/frontend/test_edit_ad_frontend.test.ts | TestEditAdFrontend |
| T12 | tests/frontend/test_filters_frontend.test.ts | TestFiltersFrontend |
| T13 | tests/frontend/test_design_system_frontend.test.ts | TestDesignSystemFrontend |
| T26 | tests/backend/test_register_backend.py | TestRegisterBackend |
| T27 | tests/frontend/test_register_frontend.test.ts | TestRegisterFrontend |
| T28 | tests/backend/test_search_backend.py | TestSearchBackend |
| T29 | tests/frontend/test_search_frontend.test.ts | TestSearchFrontend |

### Un choque que encontró el arquitecto

T01 y T06 escriben los dos `frontend/package.json`. **No es un problema de paralelismo**
—T06 depende de T01, así que van en serie— pero sí hay que saberlo: T01 crea el archivo
básico y T06 lo **modifica**, no lo crea. Lo anotamos acá porque el deductor de etapas no
puede saber cuál de los dos lo crea y cuál lo edita, y el agente de T06 necesita esperarlo.

Salió de una corrida del arquitecto que no escribió ningún archivo pero razonó bien: revisó
las 27 tareas buscando choques sobre `main.tsx` y `App.jsx` y encontró este otro de paso.

### Sobre el aviso de T06

`validar-plan.py` marca T06 porque toca cuatro archivos. **Revisado y aceptado:** son
`package.json`, `vite.config.ts`, `main.ts` y `App.jsx`, y no le hacen escribir ni una
función — es andamiaje. La regla que manda es cuántas cosas nuevas tiene que escribir el
agente, no cuántos archivos toca (DESCOMPOSICION.md §4), y el aviso es una heurística sobre
el proxy, no sobre la regla.

Queda anotado acá a propósito: **un aviso que nadie resuelve por escrito vuelve a aparecer
en cada revisión y se empieza a ignorar.**

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
- [ ] ¿Se puede publicar un aviso, encontrarlo desde otra cuenta, marcarlo favorito y
      escribirle al que publica, sin leer documentación ni tocar la base a mano?

## Riesgos

| Riesgo | Qué haríamos |
|---|---|
| Falta de claridad en el esquema DB | Definir schema en revisión temprana |
| Cambios simultáneos en mismos archivos | Usar dependencias y etapas para serializar |
| Integración frontend/backend tardía | Tests de contrato API desde inicio |
