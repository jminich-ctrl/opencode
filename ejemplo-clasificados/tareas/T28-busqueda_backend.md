# T28 — Búsqueda backend (texto y categoría)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T05
**Archivos que podés tocar:** backend/app/rutas/search.py, backend/app/servicios/search.py, backend/app/datos/search_ads.py
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Implementar búsqueda de anuncios por texto libre y filtrado por categoría mediante endpoint GET `/search`.

## Alcance

Entra:
- Parámetros query `q` (texto) y `category` (opcional).
- Búsqueda en la tabla `ads` usando LIKE para texto y filtro por columna `category`.
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

## Tests (ya escritos, fallando)

Los tests de esta tarea están en `tests/backend/test_search_backend.py` bajo la clase `TestSearchBackend`.

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
