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


def wilson(k, n, z=1.96):
    """Intervalo de Wilson al 95% para k de n. Devuelve (bajo, alto).

    Por qué Wilson y no la normal de toda la vida: en los bordes —0 de 3, que es exactamente
    el tamaño de los reservados chicos de acá— la normal da un intervalo de ancho CERO, o sea
    afirma que el FPR es 0% sin margen. Wilson no se degenera ahí.

    Y por qué no Clopper-Pearson, que sería el exacto: necesita la inversa de la beta, que no
    está en la biblioteca estándar. Wilson es cerrado, está a un par de puntos del exacto en
    estos tamaños, y se puede recalcular con lápiz.

    Verificado contra tres casos que se recalculan a mano:
      · 5/10  → (0,23659, 0,76341), el valor tabulado del intervalo de Wilson
      · 0/10  → (0, 0,27754): centro y semiancho dan lo mismo, así que el bajo es 0 exacto
      · 0/3   → (0, 0,56152): el techo queda ARRIBA del 50%, que es el punto de tenerlo
    """
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denom
    semi = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centro - semi), min(1.0, centro + semi))
