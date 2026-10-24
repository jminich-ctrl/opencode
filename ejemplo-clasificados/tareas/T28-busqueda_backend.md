# T28 — Búsqueda backend (texto y categoría)

**Estado:** pendiente
**Depende de:** T05a, T06c
**Archivos que podés tocar:** backend/app/rutas/search.py, backend/app/servicios/search.py, backend/app/datos/search_ads.py
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Implementar búsqueda de anuncios por texto libre y filtrado por categoría mediante endpoint GET `/search`.

## Alcance

Entra:
- Parámetros query `q` (texto) y `category` (opcional).
- Búsqueda en la tabla `anuncios` usando LIKE para texto y filtro por columna `categoria`.
- Retorno de lista de anuncios.

No entra:
- Búsqueda inteligente (full‑text, ranking).
- Paginación avanzada.

## Contrato

```python
def buscar_anuncios(texto: str, categoria: str | None = None) -> list[dict]:
    """Devuelve anuncios que coinciden con el texto y, opcionalmente, la categoría.
    """
```

## Archivos que deben existir

- `backend/app/datos/search_ads.py` - datos de búsqueda
- `backend/app/servicios/search.py` - lógica de búsqueda
- `backend/app/rutas/search.py` - endpoint de búsqueda

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_search_backend.py`, clase `TestSearchBackend`.

## Criterio de terminado

- [ ] Ruta `/search` implementada y responde correctamente.
- [ ] Función de servicio y acceso a datos cumplen el contrato.
- [ ] `bash scripts/gate.sh` verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

- ¿Los resultados son relevantes y el filtro por categoría funciona?
- Responsable: Jose.

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo.
- Necesitás tocar un archivo prohibido: pará y decilo.

## Reabierta

su codigo consulta la columna categoria y la tabla anuncios tiene categoria_id

Se reabrió con scripts/reabrir.sh el 2026-10-24 18:47 UTC. Su código anterior
se sacó del tronco (copia en ../reabrir-T28-previo): esta tarea vuelve a pasar por tests-first,
así que el test tiene que fallar antes de que exista la implementación.
