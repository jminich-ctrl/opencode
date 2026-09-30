# T14 — Backend datos favoritos

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T05
**Archivos que podés tocar:** backend/app/datos/favorites.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar la capa de acceso a datos para favoritos, permitiendo agregar y remover favoritos en la base.

## Alcance

Entra:
- Función para crear/eliminar registro de favorito.
- Consulta de favoritos por usuario.

No entra:
- Lógica de negocio ni exposición vía API.

## Contrato

```python
def toggle_favorite(user_id: int, ad_id: int) -> bool:
    """Marca o desmarca el anuncio como favorito para el usuario. Devuelve True si quedó como favorito."""
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/backend/test_favorites_datos.py`, clase `TestFavoritesDatos`.

## Criterio de terminado

- [ ] Funciones de datos implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
