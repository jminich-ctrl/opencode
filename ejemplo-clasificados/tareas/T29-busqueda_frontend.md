# T29 — Búsqueda frontend (UI y servicio)

**Estado:** ✅ hecha
**Depende de:** T08
**Archivos que podés tocar:** frontend/src/components/SearchBar.jsx, frontend/src/services/search.ts
**Prohibido tocar:** Ninguno
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`

## Objetivo

Implementar la barra de búsqueda en la UI y el servicio que consulta al backend `/search` para buscar anuncios por texto y categoría.

## Alcance

Entra:
- Componente `SearchBar.jsx` con campo de texto y selector de categoría.
- Llamada al servicio `search.ts` que envía los parámetros `q` y `category` al endpoint backend.
- Manejo de resultados y errores en la UI.

No entra:
- Búsqueda inteligente ni paginación avanzada.

## Contrato

```typescript
export async function buscarAnuncios(texto: string, categoria?: string): Promise<Anuncio[]>;
```

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_search_frontend.test.ts`, clase `TestSearchFrontend`.

## Criterio de terminado

- [ ] Componente `SearchBar.jsx` muestra el formulario y llama al servicio.
- [ ] Servicio `search.ts` realiza la petición GET y devuelve los anuncios.
- [ ] `bash scripts/gate.sh` verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

- ¿La UI muestra resultados relevantes y permite filtrar por categoría?
- Responsable: Jose.

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo.
- Necesitás tocar un archivo prohibido: pará y decilo.
