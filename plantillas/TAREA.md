# T00 — <título en una línea>

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** <TNN, TNN | ninguna>
**Archivos que podés tocar:** <rutas exactas>
**Prohibido tocar:** <rutas que el agente no debe abrir para escribir>
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

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

## Verificación humana (si aplica)

Si esta tarea tiene algo que un comando no puede medir —cómo se siente, si el resultado
es usable, si cubre los casos reales— escribilo acá como preguntas cerradas y decí quién
las responde. Si no lo escribís, no lo verifica nadie.

## Si algo no cierra

- Bug fuera del alcance: reportalo, no lo arregles.
- El plan no cierra: pará y decilo, no improvises.
- Necesitás tocar un archivo prohibido: pará y decilo.
