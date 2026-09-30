# T12 — Filtro por categoría en listado

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T08
**Archivos que podés tocar:** frontend/src/pages/AdsList.jsx, frontend/src/design/_filters.scss
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Permitir al usuario filtrar el listado de anuncios por categoría.

## Alcance

Entra:
- UI de filtro (select o botones) en la página AdsList.
- Lógica en el componente para aplicar el filtro a los anuncios mostrados.
- Estilos SCSS para el filtro.

No entra:
- Nuevas rutas API; se asume que el backend ya devuelve la categoría en los anuncios.

## Contrato

```typescript
/** Filtra los anuncios por categoría */
export function filterAdsByCategory(ads: Ad[], category: string): Ad[] {
    return ads.filter(ad => ad.category === category);
}
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/frontend/test_filters_frontend.test.ts`, clase `TestFiltersFrontend`.

## Criterio de terminado

- [ ] UI de filtro implementada en AdsList.jsx.
- [ ] Función `filterAdsByCategory` disponible y usada.
- [ ] Estilos SCSS aplicados.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
