# T05c — Avisos rutas (endpoints CRUD)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T05b, T04b, T06c
**Archivos que podés tocar:** backend/app/rutas/ads.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar los endpoints HTTP CRUD para los avisos, incluyendo la autorización del usuario.

## Alcance

Los endpoints a implementar son:
- `POST /ads` - Crear un nuevo anuncio
- `GET /ads` - Listar todos los anuncios
- `GET /ads/{id}` - Obtener un anuncio específico
- `PUT /ads/{id}` - Actualizar un anuncio existente
- `DELETE /ads/{id}` - Eliminar un anuncio

Todos los endpoints requieren autenticación mediante `Authorization: Bearer <token>`.

## Implementación

### Estructura del módulo
El archivo `backend/app/rutas/ads.py` debe contener:
- Un `APIRouter` llamado `router`
- Rutas para los cinco endpoints mencionados
- Importaciones necesarias desde los módulos de servicios y autenticación

### Flujo de autenticación
Para validar la autenticación:
1. Extraer el token del encabezado `Authorization: Bearer <token>`
2. Usar la función `usuario_desde_token(token)` del módulo `backend/app/servicios/auth.py`
3. Manejar errores de autenticación (401 sin sesión)

### Manejo de errores
Los códigos HTTP deben corresponder a los especificados en el contrato:
- 400: Datos inválidos
- 401: Sin sesión
- 403: No es tu aviso (permisos)
- 404: No existe

### Detalles de implementación

#### POST /ads
- Recibe datos del anuncio en el cuerpo JSON
- Valida los datos (se asume que ya está hecho en T05b y T05a)
- Llama a `crear_anuncio(usuario_id, categoria_id, titulo, descripcion, precio_centavos)` del módulo `backend/app/servicios/ads.py`
- Retorna 201 con `{"id": <id>}`

#### GET /ads
- Retorna 200 con la lista de anuncios
- Llama a `buscar_anuncios(None)` del módulo `backend/app/servicios/search.py`
  (import exacto: `from backend.app.servicios.search import buscar_anuncios`). Sin texto ni
  categoría, esa función devuelve todos los anuncios: su consulta arranca en
  `WHERE 1=1` y sólo agrega condiciones cuando recibe filtros.
- Los campos que devuelve son `id`, `usuario_id`, `titulo` y `categoria`, y eso es TODO lo
  que el listado expone. No incluye `descripcion` ni `precio_centavos`: si alguna vez hacen
  falta en el listado, se amplía la consulta de `backend/app/datos/search_ads.py`, que es de
  T28 y está cerrada — o sea que no es trabajo de esta tarea.

#### GET /ads/{id}
- Retorna 200 con los detalles del anuncio
- Maneja el caso 404 si el anuncio no existe
- Llama a `obtener_anuncio(ad_id)` del módulo `backend/app/servicios/ads.py`

#### PUT /ads/{id}
- Recibe datos actualizados del anuncio en el cuerpo JSON
- Valida los datos (se asume que ya está hecho en T05b y T05a)
- Verifica que el usuario sea el dueño del anuncio (403 si no lo es)
- Llama a `actualizar_anuncio(ad_id, usuario_id, titulo, descripcion, precio_centavos)` del módulo `backend/app/servicios/ads.py`
- Retorna 200

#### DELETE /ads/{id}
- Verifica que el usuario sea el dueño del anuncio (403 si no lo es)
- Llama a `eliminar_anuncio(ad_id, usuario_id)` del módulo `backend/app/servicios/ads.py`
- Retorna 204

## Pruebas

Los tests para esta implementación se encuentran en `backend/tests/test_ads_rutas.py` y deben pasar sin tocar MySQL, usando mocks de las capas superiores.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Archivo: `backend/tests/test_ads_rutas.py`, clase `TestAdsRutas`.

## Criterio de terminado

- [ ] Los cinco endpoints responden los códigos del contrato y sus tests pasan sin tocar MySQL.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo, no improvises.
- Necesitás tocar un archivo prohibido: pará y decilo.
