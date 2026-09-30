# T15 — Backend servicios favoritos

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T14
**Archivos que podés tocar:** backend/app/servicios/favorites.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Implementar la capa de servicio para la lógica de favoritos, usando la capa de datos.

## Alcance

Entra:
- Función que llama a `toggle_favorite` del módulo de datos.
- Validaciones básicas de entrada.

No entra:
- Exposición vía API ni UI.

## Contrato

```python
def toggle_favorite_service(user_id: int, ad_id: int) -> bool:
    """Servicio que delega a la capa de datos para marcar/desmarcar favorito."""
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/backend/test_favorites_servicio.py`, clase `TestFavoritesServicio`.

## Criterio de terminado

- [ ] Funciones de servicio implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A