# T00 — <título en una línea>

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** <TNN, TNN | ninguna>
<!-- El archivo de test NUNCA va en el alcance: los tests llegan escritos y el paso 0 del
     gate verifica que no se toquen. Tampoco `scripts/`, que es el verificador mismo.
     `validar-plan.py` rechaza una tarea que los declare: sería insatisfacible. -->
**Archivos que podés tocar:** <rutas exactas>
<!-- LO PROHIBIDO VA ACÁ Y NO EN PROSA, y no se explica cómo hacerlo.
     Medido el 2026-10-24: el enunciado de T05c decía, en el cuerpo, «si alguna vez hacen
     falta esos campos, se amplía la consulta de backend/app/datos/search_ads.py, que es de
     T28 y está cerrada — o sea que no es trabajo de esta tarea». El ejecutor fue y editó ese
     archivo. La prohibición estaba escrita, en castellano, dos líneas antes de la receta.
     Le di el cómo y después le dije que no.
     Udgam Labs midió la misma cosa de otra forma: a su modelo de 95M, un número IRRELEVANTE
     insertado en el enunciado le baja el acierto de 54,7% a 20,7%. Un dato que no hace falta
     no es neutro: compite por la atención.
     Dos reglas, entonces:
       · lo que no se puede tocar se declara en este campo, que es el que el gate lee;
       · nombrar un archivo ajeno está BIEN si es para decir dónde vive algo que la tarea
         importa —eso es lo más útil que un enunciado hace— y está MAL si viene con
         instrucciones de cómo modificarlo. -->
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

<Y si el contrato fija CÓMO traer un nombre de otra capa, decí también la consecuencia:
dónde hay que parchearlo si el test necesita controlarlo. Eso es lo único medido del método
que cerró un plan de 21 tareas con modelos chicos sin intervención humana, dos veces de dos
—MEDICION.md §13—, y no cuesta nada escribirlo:>

    Usa `from src.datos.d1 import leer1`.

    Si el test necesita controlar lo que devuelve `leer1()`, parcheá
    `src.servicios.s1.leer1` —el módulo donde se USA—, no `src.datos.d1.leer1`:
    con ese import el nombre ya quedó ligado cuando el patch corre.

<Sin esa línea, el modelo chico parchea donde el nombre se DEFINE —8 o 9 veces sobre siete
tareas, en tres brazos medidos— el patch no pega, y el rojo lo paga el que implementa.
Decírselo en `AGENTS.md` no alcanza: llegó a 7 de 7 agentes y 4 no lo aplicaron.>

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. El trabajo del agente es hacerlos
pasar sin modificarlos. Archivo: `tests/test_<modulo>.py`, clase `<Clase>`.

> La **clase** es cómo el gate le pide al corredor *sólo los tests de esta tarea*, y con eso
> contesta si distinguen el cambio. En un stack sin clases hace falta el agrupador
> equivalente —un `describe("<Clase>")` en JS— o el selector no casa ningún test y el paso 4
> sale ⊘: medido el 2026-10-26 en un proyecto JS armado de cero.

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
