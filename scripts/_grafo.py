#!/usr/bin/env python3
"""Un ciclo CONCRETO entre tareas trabadas, para poder nombrarlo.

Vive solo porque lo necesitan dos scripts —`validar-plan.py`, que juzga la forma del plan, y
`_etapas.py`, que calcula el orden— y porque la lección de las tres copias del motor de
arquitectura ya se pagó: `cocambio.py` midió que la plantilla y su copia cambiaban juntas el
67% de las veces, o sea que una copia es un defecto futuro.

El motivo de nombrar el ciclo y no sólo decir «revisá las dependencias» es la misma regla que
el método ya le exige a sus rojos: tiene que decir QUÉ está mal, no que algo está mal. Con 20
tareas, «revisá sus dependencias en el plan» es una tarde de lectura; `T04 → T11 → T07 → T04`
es un renglón.
"""


def un_ciclo(deps_de):
    """`deps_de`: {tarea: {dependencias}}. Devuelve el ciclo como lista cerrada
    —`[T01, T03, T02, T01]`— o None si no hay ninguno entre esos nodos.

    Las dependencias que apuntan afuera de `deps_de` se ignoran: una tarea que depende de algo
    que no está en la tabla está trabada, pero no por un ciclo, y confundir las dos causas es
    lo que vuelve inútil al diagnóstico."""
    visitados, en_camino = set(), []

    def bajar(t):
        if t in en_camino:
            return en_camino[en_camino.index(t):] + [t]
        if t in visitados or t not in deps_de:
            return None
        visitados.add(t)
        en_camino.append(t)
        for d in sorted(deps_de[t]):
            hallado = bajar(d)
            if hallado:
                return hallado
        en_camino.pop()
        return None

    for t in deps_de:
        hallado = bajar(t)
        if hallado:
            return hallado
    return None
