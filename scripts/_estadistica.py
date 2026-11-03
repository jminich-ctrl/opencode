"""Lo mínimo para no reportar una diferencia que el muestreo explica solo.

Sin scipy a propósito: esta Mac tiene las CLT viejas y `brew` no puede compilar, así que una
dependencia binaria acá es un script que no corre el día que alguien clone el repo. Todo lo de
abajo sale de `math.comb`, que es exacto y está en la biblioteca estándar.

Por qué existe: §19 tuvo que calcular su p y su IC fuera del repo, y un número que se calcula
a mano al costado es un número que nadie puede volver a sacar. Si está acá, se audita.
"""
import math


def fisher_exacto_2x2(a, b, c, d):
    """p a dos colas de la tabla [[a, b], [c, d]].

    El criterio de «a dos colas» es el de Fisher: sumar la probabilidad de TODAS las tablas con
    los mismos márgenes cuya probabilidad hipergeométrica es menor o igual que la observada. No
    es duplicar la cola —eso da otro número— y la diferencia importa en tablas asimétricas.

    Verificado a mano contra dos casos que se pueden recalcular con lápiz:
      · [[2,0],[0,2]] → 2/6 = 0,3333…  (las dos tablas extremas de N=4)
      · [[3,1],[1,3]] → 34/70 = 0,4857…  (la tabla del té de Fisher)
    """
    n = a + b + c + d
    if n == 0:
        return 1.0
    fila1, col1 = a + b, a + c
    # P(X = k) con los márgenes fijos: hipergeométrica.
    def p(k):
        return (math.comb(fila1, k) * math.comb(n - fila1, col1 - k)) / math.comb(n, col1)
    lo = max(0, col1 - (n - fila1))
    hi = min(fila1, col1)
    observada = p(a)
    # El `+ 1e-12` es contra el ruido de punto flotante: dos tablas con la MISMA probabilidad
    # exacta pueden diferir en el último bit y entonces una entra y la otra no, que convierte
    # un p simétrico en uno que depende de cómo se ordenó la tabla.
    return min(1.0, sum(p(k) for k in range(lo, hi + 1) if p(k) <= observada + 1e-12))
