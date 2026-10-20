# T05 — CRUD de avisos backend

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T04b, T06c
**Archivos que podés tocar:** backend/app/rutas/ads.py, backend/app/servicios/ads.py, backend/app/datos/ads.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar los endpoints para crear, leer, actualizar y eliminar avisos, respetando la autorización del usuario.

## Alcance

Entra:
- Endpoints `/ads` (GET, POST) y `/ads/{id}` (GET, PUT, DELETE).
- Validación básica de datos del anuncio.
- Uso de los módulos de datos y servicios existentes.

No entra:
- Gestión de favoritos ni mensajes.

## Contrato

```python
from fastapi import APIRouter, Request, Response
from backend.app.servicios.auth import usuario_desde_token   # lo provee T04b

router = APIRouter()

@router.post("/ads")
async def crear_ad(request: Request) -> Response:
    """Crea un nuevo anuncio y devuelve su ID."""
```

**Las firmas de las capas que el test importa, con los nombres de columna que el esquema de
`PLAN.md` ya cerró.** No son una invención de esta tarea: son transcripción del esquema.

```python
# backend/app/datos/ads.py
def insert_ad(usuario_id: int, categoria_id: int, titulo: str, descripcion: str,
              precio_centavos: int) -> int: ...
def get_ad_by_id(ad_id: int) -> dict | None: ...
def update_ad(ad_id: int, usuario_id: int, titulo: str, descripcion: str,
              precio_centavos: int) -> bool: ...     # False si el aviso no es de ese usuario
def delete_ad(ad_id: int, usuario_id: int) -> bool: ...

# backend/app/servicios/ads.py — es lo que importa el test
def crear_anuncio(usuario_id: int, categoria_id: int, titulo: str, descripcion: str,
                  precio_centavos: int) -> int: ...
def obtener_anuncio(ad_id: int) -> dict | None: ...
def actualizar_anuncio(ad_id: int, usuario_id: int, titulo: str, descripcion: str,
                       precio_centavos: int) -> bool: ...
def eliminar_anuncio(ad_id: int, usuario_id: int) -> bool: ...
```

**Tres cosas que el esquema impone y que un test las puede contradecir sin que nadie se
entere:**

1. **Un aviso TIENE dueño y categoría**: `anuncios.usuario_id INT NOT NULL` y
   `categoria_id INT NOT NULL`, las dos con FOREIGN KEY. Un `crear_anuncio(titulo,
   descripcion, precio)` sin ellos no puede insertar una fila válida.
2. **La columna es `precio_centavos`, no `precio`.** Está cerrada así en `PLAN.md` a
   propósito: plata en enteros.
3. **El dueño se verifica en la capa de servicios**, no en la de rutas: por eso
   `actualizar_anuncio` y `eliminar_anuncio` reciben `usuario_id` y devuelven `False` cuando
   el aviso no es de ese usuario. T11 («editar propios avisos») cuenta con eso.

El 2026-10-19 el test aceptado de esta tarea llamaba `crear_anuncio(titulo, descripcion,
precio)` y afirmaba que `insert_ad` recibía esos tres y nada más: contradecía el esquema en
los tres puntos de arriba. Pasó el validador porque su paso 3 —el de mutantes, el único que
pregunta si el test distingue— **no corría** por un defecto de rutas, y los pasos 1, 2 y 4
comparan el test contra la implementación del propio agente, las dos con la misma firma
inventada. Se rechazó el test y se escribió esto.

**A qué capa apunta el test, y cómo se autentica.** El test ejercita el ENDPOINT con
`TestClient(app)`, igual que `backend/tests/test_auth_backend.py`, porque ahí viven los
errores de cableado. Y como `/ads` exige sesión, la autenticación se mockea:

```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app

with patch('backend.app.rutas.ads.usuario_desde_token', return_value=7):
    with patch('backend.app.datos.ads.insert_ad', return_value=123) as mock_insert:
        r = TestClient(app).post("/ads", json={...},
                                 headers={"Authorization": "Bearer cualquiera"})
        assert r.status_code == 201
```

**Ojo con DÓNDE se parchea:** `backend.app.rutas.ads.usuario_desde_token`, o sea el módulo
que la USA, no `backend.app.servicios.auth...`, que es donde está definida. La ruta puede
importarla como quiera —`from backend.app.servicios.auth import usuario_desde_token` está
bien— porque se parchea el nombre tal como la ruta lo ve.

La versión anterior de esta tarea pedía lo contrario: parchear el módulo que la define y
exigirle a la ruta que la llamara como atributo (`auth.usuario_desde_token(...)`). El agente
escribió el import directo las dos veces —es lo natural— y se comió `assert 401 == 201` las
dos, porque con el import directo ese patch no aplica. **La regla estaba al revés: no se le
pide al código un estilo antinatural para que funcione un patch mal apuntado; se apunta el
patch donde el nombre se busca.** Una convención que el agente viola dos veces, habiendo una
alternativa que hace correcto el código natural, es un defecto de la convención.

Esto está escrito porque el 2026-10-20 el agente escribió tests de ruta y se comió
`assert 401 == 201` dos veces: en el proyecto no había NINGÚN precedente de test sobre una
ruta autenticada —T04 prueba `/auth/login`, que no exige sesión porque la crea, y T04b llama
a la función directo—, así que tenía que inventarlo. Una tarea que exige autorización y no
dice cómo se simula en un test no es ejecutable, que es la misma lección que esta tarea ya
aprendió una vez con `obtener_usuario_id_desde_token`.

**Cómo se sabe quién pide: `usuario_desde_token(token)` de `servicios/auth.py`, que la
provee T04b.** Está escrito acá porque la versión anterior de esta tarea pedía «respetando
la autorización del usuario» sin decir el medio: el agente inventó una función, cableó tres
archivos a ella y se quedó veinte minutos contra su propio `ImportError`, tres veces. Una
tarea que exige algo y no dice con qué hacerlo no es ejecutable.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_ads_backend.py`, clase `TestAdsBackend`.

## Criterio de terminado

- [ ] Endpoints CRUD funcionales y pruebas pasan.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
