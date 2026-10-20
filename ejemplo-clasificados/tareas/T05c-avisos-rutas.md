# T05c — Avisos rutas (endpoints CRUD)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T05b, T04b, T06c
**Archivos que podés tocar:** backend/app/rutas/ads.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Los endpoints HTTP de los avisos, con la autorización del usuario.
> **Esta tarea sale de partir T05.** T05 pedía las tres capas y los cinco endpoints en un
> solo enunciado, y falló seis veces con seis diagnósticos distintos —presupuesto, un test
> que contradecía el esquema, el dialecto SQL, la capa del test, la autenticación y el patch
> mal apuntado—. Cada arreglo la hacía llegar un paso más lejos, que es la firma de una tarea
> que pide demasiado de una vez. Y el plan ya partía así todo lo demás: favoritos en
> T14/T15/T16 y mensajes en T20/T21/T22, una capa por tarea. T05 era la anomalía.


## Alcance

Entra:
- `POST /ads`, `GET /ads`, `GET /ads/{id}`, `PUT /ads/{id}`, `DELETE /ads/{id}`.
- Autenticación por `Authorization: Bearer <token>`.
- Traducción de errores a códigos HTTP: 400 inválido, 401 sin sesión, 403 no es tu aviso, 404 no existe.

No entra:
- Validación de datos ni SQL: ya están en T05b y T05a.
- Favoritos ni mensajes.

## Contrato

```python
# backend/app/rutas/ads.py
router  # APIRouter — main.py monta solo los módulos de rutas/ que tengan `router`
```

| endpoint | 2xx | errores |
|---|---|---|
| `POST /ads` | 201 con `{"id": …}` | 400 inválido · 401 sin sesión |
| `GET /ads` | 200 con la lista | — |
| `GET /ads/{id}` | 200 con el aviso | 404 no existe |
| `PUT /ads/{id}` | 200 | 400 · 401 · 403 no es tuyo · 404 |
| `DELETE /ads/{id}` | 204 | 401 · 403 · 404 |

**Cómo se sabe quién pide:** `usuario_desde_token(token)` de `servicios/auth.py`, que provee
T04b. El token viaja en `Authorization: Bearer <token>`.

**El test NO toca MySQL ni la base: mockea lo que esta capa USA, y lo mockea en ESTE módulo**
—se parchea donde el nombre se busca, no donde se define (`AGENTS.md`)—:

```python
with patch('backend.app.rutas.ads.usuario_desde_token', return_value=7), \
     patch('backend.app.rutas.ads.crear_anuncio', return_value=123) as mock_crear:
    r = TestClient(app).post("/ads", json={...},
                             headers={"Authorization": "Bearer cualquiera"})
    assert r.status_code == 201
```

Así la ruta puede importar como quiera (`from backend.app.servicios.ads import crear_anuncio`
está bien) y no hace falta recordar ninguna convención de import. La versión anterior de esta
tarea pedía parchear el módulo que DEFINE las funciones y exigirle a la ruta un estilo de
import antinatural: el agente escribió el import directo las dos veces y se comió
`assert 401 == 201` las dos. **Se apunta el patch donde el nombre se busca; no se le pide al
código un estilo raro para que funcione un patch mal apuntado.**

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
