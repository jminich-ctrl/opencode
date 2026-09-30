# T09 — Favoritos

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T05, T08
**Archivos que podés tocar:** backend/app/rutas/favorites.py, backend/app/servicios/favorites.py, backend/app/datos/favorites.py, frontend/src/services/favorites.ts, frontend/src/pages/AdsList.jsx, frontend/src/design/_favorites.scss
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Permitir a los usuarios marcar y desmarcar anuncios como favoritos y visualizar la lista de favoritos.

## Alcance

Entra:
- Endpoint API para agregar/quitar favoritos.
- Servicio frontend para consumir esos endpoints.
- UI en la lista de anuncios para marcar como favorito.
- Estilos SCSS para el icono de favorito.

No entra:
- Página dedicada de favoritos (se implementará después).

## Contrato

```python
def toggle_favorite(user_id: int, ad_id: int) -> bool:
    """Marca o desmarca el anuncio como favorito para el usuario. Devuelve True si quedó como favorito."""
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_favorites_frontend.test.ts`, clase `TestFavoritesFrontend`.

## Criterio de terminado

- [ ] Endpoints creados y funcionan.
- [ ] Servicio frontend implementado.
- [ ] UI muestra estado de favorito.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
