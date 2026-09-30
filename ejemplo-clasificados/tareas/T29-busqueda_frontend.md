# T29 — Búsqueda frontend (UI y servicio)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
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

## Tests (ya escritos, fallando)

Los tests de esta tarea están en `tests/frontend/test_search_frontend.test.ts` bajo la clase `TestSearchFrontend`.

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
