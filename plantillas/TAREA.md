# T00 — <título en una línea>

**Depende de:** <TNN, TNN | ninguna>
**Archivos que podés tocar:** <rutas exactas>
**Prohibido tocar:** <rutas que el agente no debe abrir para escribir>
**Modelo sugerido:** build (27B) | explore (8B) para tareas de solo lectura

## Objetivo

Una frase. Qué tiene que poder hacer el código cuando esto esté listo.

## Alcance

Entra:
- <punto concreto>
- <punto concreto>

No entra:
- <lo que explícitamente queda afuera>

## Contrato

<Si la tarea define una función o clase, su firma exacta y qué devuelve.
Cuanto más preciso esto, menos improvisa el modelo.>

    def nombre_funcion(param: tipo) -> tipo:
        """Qué hace."""

## Criterio de terminado

- [ ] <condición verificable>
- [ ] <condición verificable>
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo, no improvises.
- Necesitás tocar un archivo prohibido: pará y decilo.
