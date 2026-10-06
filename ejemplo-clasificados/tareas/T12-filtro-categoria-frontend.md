# T12 — Filtro por categoría en listado

**Estado:** ✅ hecha
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

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_filters_frontend.test.ts`, clase `TestFiltersFrontend`.

## Criterio de terminado

- [ ] UI de filtro implementada en AdsList.jsx.
- [ ] Función `filterAdsByCategory` **definida y exportada desde
      `frontend/src/pages/AdsList.jsx`**, y usada ahí mismo. No va en un módulo aparte: el
      alcance de esta tarea no incluye ningún otro archivo de código, y un helper suelto en
      `lib/` o `utils/` queda fuera y el gate lo reprueba —con razón—.
- [ ] Estilos en **`frontend/src/design/_filters.scss`**, que es el único archivo de estilos
      del alcance. No crear un `.scss` al lado de la página.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
