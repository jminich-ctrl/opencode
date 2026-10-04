# T00 — <título en una línea>

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** <TNN, TNN | ninguna>
<!-- El archivo de test NUNCA va en el alcance: los tests llegan escritos y el paso 0 del
     gate verifica que no se toquen. Tampoco `scripts/`, que es el verificador mismo.
     `validar-plan.py` rechaza una tarea que los declare: sería insatisfacible. -->
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

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. El trabajo del agente es hacerlos
pasar sin modificarlos. Archivo: `tests/test_<modulo>.py`, clase `<Clase>`.

Si no podés escribir el test antes, la tarea todavía no está entendida: no la lances.

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

## Si no se puede

Si la tarea es imposible o se contradice a sí misma, escribí `IMPOSIBLE: <motivo>` y pará.
El runner lo registra como tal, **no lo reintenta**, y lo decide una persona.

Está acá por una medición, no por cortesía: dos estudios independientes muestran que darle
al agente una salida explícita cuando la tarea no se puede hacer **baja el reward hacking de
54% a 9%** en uno y **de 23,6% a 5,3%** en el otro, sin costo de rendimiento. Sin esa salida,
un modelo al que se le pide lo imposible hace pasar el test de alguna forma.
