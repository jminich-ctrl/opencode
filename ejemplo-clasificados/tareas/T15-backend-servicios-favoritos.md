# T15 — Backend servicios favoritos

**Estado:** ✅ hecha
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

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `backend/tests/test_favorites_servicio.py`, clase `TestFavoritesServicio`.

## Criterio de terminado

- [ ] Funciones de servicio implementadas.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A