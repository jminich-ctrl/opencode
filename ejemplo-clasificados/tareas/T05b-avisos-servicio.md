# T05b — Avisos servicio (validación y dueño)

**Estado:** ✅ hecha
**Depende de:** T05a
**Archivos que podés tocar:** backend/app/servicios/ads.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

La capa de servicios de los avisos: validación de los datos y verificación del dueño, delegando en la capa de datos.
> **Esta tarea sale de partir T05.** T05 pedía las tres capas y los cinco endpoints en un
> solo enunciado, y falló seis veces con seis diagnósticos distintos —presupuesto, un test
> que contradecía el esquema, el dialecto SQL, la capa del test, la autenticación y el patch
> mal apuntado—. Cada arreglo la hacía llegar un paso más lejos, que es la firma de una tarea
> que pide demasiado de una vez. Y el plan ya partía así todo lo demás: favoritos en
> T14/T15/T16 y mensajes en T20/T21/T22, una capa por tarea. T05 era la anomalía.


## Alcance

Entra:
- `crear_anuncio`, `obtener_anuncio`, `actualizar_anuncio`, `eliminar_anuncio`.
- Validación: título y descripción no vacíos, `precio_centavos` entero y no negativo.
- Verificación del dueño antes de actualizar o borrar.

No entra:
- SQL: ya está en T05a y no se toca.
- Endpoints HTTP: son de T05c.

## Contrato

```python
# backend/app/servicios/ads.py
def crear_anuncio(usuario_id: int, categoria_id: int, titulo: str, descripcion: str,
                  precio_centavos: int) -> int: ...
def obtener_anuncio(ad_id: int) -> dict | None: ...
def actualizar_anuncio(ad_id: int, usuario_id: int, titulo: str, descripcion: str,
                       precio_centavos: int) -> bool: ...
def eliminar_anuncio(ad_id: int, usuario_id: int) -> bool: ...
```

**El test NO toca MySQL: mockea la capa de datos**, que es lo que T05a entrega. Y lo mockea
**donde el nombre se busca** —la regla general está en `AGENTS.md`—:

```python
from backend.app.datos import ads as datos_ads     # como ATRIBUTO del módulo
...
with patch('backend.app.datos.ads.insert_ad', return_value=123) as mock_insert:
    assert crear_anuncio(7, 1, "t", "d", 10000) == 123
    mock_insert.assert_called_once_with(7, 1, "t", "d", 10000)
```

Si el servicio escribe `from backend.app.datos.ads import insert_ad`, ese patch no aplica: se
queda con su propia referencia, la consulta va a la base de verdad y sale un
`IntegrityError` que no se parece a su causa. Pasó.

**Qué validar, y qué devolver cuando no valida:** título y descripción no vacíos,
`precio_centavos` entero ≥ 0. Con datos inválidos, `ValueError`. El HTTP 400 lo traduce T05c,
no esta capa.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Archivo: `backend/tests/test_ads_servicio.py`, clase `TestAdsServicio`.

## Criterio de terminado

- [ ] Las cuatro funciones validan y delegan, y sus tests pasan sin tocar MySQL.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo, no improvises.
- Necesitás tocar un archivo prohibido: pará y decilo.
