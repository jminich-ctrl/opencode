#!/usr/bin/env python3
"""¿Los tests distinguen de verdad? Muta el código cambiado y exige que la suite lo note.

El paso 4 del gate revierte **todo** el cambio y pide que la suite falle. Eso atrapa el test
vacuo grosero y deja pasar el caso fino: una implementación con cinco condiciones donde los
tests verifican una. Mutar contesta la pregunta por pieza.

  BASE=HEAD~1 python3 scripts/mutar.py        # sale 0 si todos los mutantes mueren

Las decisiones de diseño salen de los dos sistemas de mutación medidos a escala —el de
Google sobre 16,9 millones de mutantes en 10 lenguajes, y el estudio de acoplamiento a
fallas reales de FSE 2014— y no de lo que hacen las librerías de mutación de Python:

1. **Borrar una sentencia (SBR) es el operador principal.** Es el 68% de los mutantes de
   Google, está entre los tres más acoplados a fallas reales ("debería usarse siempre") y
   produce *menos* mutantes equivalentes. Las tres librerías de Python más usadas **no lo
   tienen**, o lo marcan experimental: es exactamente la prioridad al revés.
2. **Un mutante por línea, como máximo.** Medido: "en más del 90% de los casos, o todos los
   mutantes de una línea mueren, o ninguno". Generar cinco por línea es gastar cinco
   corridas de la suite para enterarse de lo mismo.
3. **Nodos áridos.** El 85% de los mutantes sin filtrar son improductivos —triviales o
   imposibles de testear con sentido— contra el ~3% que son equivalentes. El presupuesto va
   acá y no a un oráculo de equivalencia. Las heurísticas de abajo son las publicadas para
   Python: `__main__`, logging, `print`, chequeos de versión, excepciones de contrato,
   funciones cuyas hojas son todas `return`, y comparaciones contra `len()`, `0` o `None`
   —`len(x) == 0 → len(x) <= 0` es equivalente garantizado—.
4. **Sin ABS y sin UOI.** Google desactivó ABS en todos los lenguajes; UOI es el peor de los
   suyos en las dos dimensiones (74,5% productivo, 9,5% de supervivencia) y aporta el 18,5%
   del volumen. Reemplazo de constantes tampoco: es donde vive el ruido de `mutmut`.
5. **Sólo líneas cambiadas, y sólo del código de producto** (`CODIGO`, por defecto `src`).
   Mutar el repo entero cuesta horas; mutar las herramientas del método da ruido puro,
   porque no tienen suite y entonces todo sobrevive.

Nunca imprime un puntaje de mutación. Google se niega a calcularlo y tiene razón: lo que
sirve es **qué** mutante sobrevivió, no un porcentaje que se puede subir sin mejorar nada.
"""
import ast
import os
import pathlib
import re
import subprocess
import sys

BASE = os.environ.get("BASE", "HEAD~1")
SUITE = os.environ.get("SUITE", "python3 -m unittest discover -s tests -t . -q")
LIMITE = int(os.environ.get("LIMITE", "40"))
# Sólo el código de producto. Mutar los scripts del método da ruido puro: no tienen suite,
# así que todo sobrevive y tapa la señal del código que sí importa.
CODIGO = os.environ.get("CODIGO", "src")

# Heurísticas de aridez publicadas para Python, más las generales que aplican.
ARIDAS_NOMBRE = re.compile(r"^(log|print|debug|warn|error|info|trace)", re.I)
ARIDAS_TEXTO = re.compile(
    r"__main__|sys\.version_info|NotImplementedError|abstractmethod|"
    r"timeout|deadline|backoff|sleep|retry|\bflag", re.I)


def arido_simple(nodo, fuente_linea):
    """La función `expert` del algoritmo publicado: reglas a mano sobre un nodo simple.

    Improductivo = trivialmente equivalente, o detectable pero sin que agregar un test para
    él mejore la suite. Son heurísticas y no son sólidas, a propósito: el sistema medido
    reporta que las heurísticas *no* sólidas dieron las mejoras más importantes.
    """
    if ARIDAS_TEXTO.search(fuente_linea):
        return True
    # Logging y print: la regla con 99 de 100 aciertos en el muestreo publicado.
    if isinstance(nodo, ast.Call):
        nombre = getattr(nodo.func, "id", None) or getattr(nodo.func, "attr", "")
        objeto = getattr(getattr(nodo.func, "value", None), "id", "")
        if ARIDAS_NOMBRE.match(nombre or "") or "log" in objeto.lower():
            return True
    # Comparaciones contra len(), 0 o None: mutar el operador da un equivalente garantizado.
    if isinstance(nodo, ast.Compare):
        lados = [nodo.left] + list(nodo.comparators)
        for lado in lados:
            if isinstance(lado, ast.Call) and getattr(lado.func, "id", "") in ("len", "size"):
                return True
            if isinstance(lado, ast.Constant) and lado.value in (0, None, True, False):
                return True
    # Excepciones de contrato: cambiar el mensaje o la condición no mejora ninguna suite.
    if isinstance(nodo, ast.Raise):
        return True
    return False


def es_arido(nodo, fuente):
    """La regla recursiva publicada:

        arido(N) = expert(N)                        si N es simple
                   todos los hijos son áridos       si no

    Sin la recursión el filtro no sirve: el candidato que se elige para borrar una sentencia
    es la sentencia, y la razón por la que es árida vive en sus hijos. `logging.info(...)` es
    un `Expr` cuyo único hijo es la llamada árida, y `if x is None: raise ...` es un `If`
    cuyos dos hijos son áridos.
    """
    linea = getattr(nodo, "lineno", 0)
    texto = fuente[linea - 1] if 0 < linea <= len(fuente) else ""
    if arido_simple(nodo, texto):
        return True
    hijos = list(ast.iter_child_nodes(nodo))
    if not hijos:
        return False
    return all(es_arido(h, fuente) for h in hijos)


def hojas_todas_return(nodo):
    """Patrón publicado: una función cuyas hojas son todas `return` no se muta con provecho."""
    if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    cuerpo = [c for c in nodo.body if not (isinstance(c, ast.Expr)
                                           and isinstance(c.value, ast.Constant))]
    return bool(cuerpo) and all(isinstance(c, ast.Return) for c in cuerpo)


OPERADORES_ROR = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
                  ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}


class Mutador(ast.NodeTransformer):
    """Aplica UNA mutación, la del nodo elegido, y deja el resto intacto."""

    def __init__(self, objetivo):
        self.objetivo = objetivo
        self.aplicada = False

    def generic_visit(self, nodo):
        nodo = super().generic_visit(nodo)
        if nodo is self.objetivo and not self.aplicada:
            self.aplicada = True
            return self.mutar(nodo)
        return nodo

    def mutar(self, nodo):
        if isinstance(nodo, ast.Compare):          # ROR
            nuevo = OPERADORES_ROR.get(type(nodo.ops[0]))
            if nuevo:
                nodo.ops = [nuevo()] + list(nodo.ops[1:])
            return nodo
        if isinstance(nodo, ast.BoolOp):           # LCR
            nodo.op = ast.Or() if isinstance(nodo.op, ast.And) else ast.And()
            return nodo
        if isinstance(nodo, ast.BinOp):            # AOR
            cambio = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv,
                      ast.FloorDiv: ast.Mult}.get(type(nodo.op))
            if cambio:
                nodo.op = cambio()
            return nodo
        return ast.Pass()                          # SBR: la sentencia se borra


def candidatos(archivo, lineas_cambiadas):
    """Un candidato por línea cambiada, con SBR primero y los demás como alternativa."""
    try:
        arbol = ast.parse(archivo.read_text())
    except SyntaxError:
        return []
    fuente = archivo.read_text().split("\n")
    aridos = set()
    for nodo in ast.walk(arbol):
        if hojas_todas_return(nodo):
            aridos.update(range(nodo.lineno, (nodo.end_lineno or nodo.lineno) + 1))

    por_linea = {}
    for nodo in ast.walk(arbol):
        linea = getattr(nodo, "lineno", None)
        if linea is None or linea not in lineas_cambiadas or linea in aridos:
            continue
        if es_arido(nodo, fuente):
            continue
        # Prioridad por evidencia: SBR, ROR, LCR, AOR.
        if isinstance(nodo, ast.stmt) and not isinstance(
                nodo, (ast.Return, ast.Raise, ast.Import, ast.ImportFrom,
                       ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                       ast.Pass, ast.Global, ast.Nonlocal)):
            if isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant):
                continue                        # docstring o cadena suelta
            por_linea.setdefault(linea, (0, nodo, "borrar la sentencia"))
        elif isinstance(nodo, ast.Compare):
            if por_linea.get(linea, (9,))[0] > 1:
                por_linea[linea] = (1, nodo, "invertir la comparación")
            por_linea.setdefault(linea, (1, nodo, "invertir la comparación"))
        elif isinstance(nodo, ast.BoolOp):
            por_linea.setdefault(linea, (2, nodo, "cambiar and por or"))
        elif isinstance(nodo, ast.BinOp):
            por_linea.setdefault(linea, (3, nodo, "cambiar el operador aritmético"))
    return [(archivo, linea, nodo, que) for linea, (_, nodo, que) in sorted(por_linea.items())]


def correr():
    return subprocess.run(SUITE, shell=True, capture_output=True, text=True).returncode == 0


def lineas_cambiadas(archivo):
    d = subprocess.run(["git", "diff", "-U0", BASE, "--", str(archivo)],
                       capture_output=True, text=True).stdout
    nums = set()
    for ini, n in re.findall(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", d, re.M):
        nums.update(range(int(ini), int(ini) + int(n or 1)))
    return nums


def main():
    archivos = [a for a in subprocess.run(
        ["git", "diff", "--name-only", "--relative", BASE],
        capture_output=True, text=True).stdout.split()
        if a.endswith(".py") and "test" not in a and a.startswith(CODIGO + "/")]
    if not archivos:
        print("  · no hay código Python cambiado que mutar")
        return 0
    if not correr():
        print("  ✗ la suite ya está en rojo: arreglala antes de mutar")
        return 1

    todos = []
    for a in archivos:
        p = pathlib.Path(a)
        if p.exists():
            todos += candidatos(p, lineas_cambiadas(p))
    if not todos:
        print("  · el diff no tiene nada que mutar con provecho (todo árido o sin operadores)")
        return 0
    if len(todos) > LIMITE:
        print(f"  · {len(todos)} mutantes; se prueban los primeros {LIMITE} (subí LIMITE)")
        todos = todos[:LIMITE]

    sobrevivientes = []
    for archivo, linea, nodo, que in todos:
        original = archivo.read_text()
        try:
            arbol = ast.parse(original)
            # Hay que ubicar el nodo equivalente en el árbol nuevo, por línea y tipo.
            objetivo = next((x for x in ast.walk(arbol)
                             if getattr(x, "lineno", None) == linea
                             and type(x) is type(nodo)), None)
            if objetivo is None:
                continue
            mutado = ast.fix_missing_locations(Mutador(objetivo).visit(arbol))
            archivo.write_text(ast.unparse(mutado))
            if correr():          # la suite pasó CON el código mutado: nadie lo verifica
                sobrevivientes.append((archivo, linea, que, original.split("\n")[linea - 1]))
        except (SyntaxError, ValueError, RecursionError):
            continue
        finally:
            archivo.write_text(original)

    print(f"  {len(todos)} mutante(s) probados sobre el diff, uno por línea")
    if sobrevivientes:
        print(f"  ✗ {len(sobrevivientes)} sobrevivieron: la suite no nota estos cambios")
        for archivo, linea, que, texto in sobrevivientes[:10]:
            print(f"     {archivo}:{linea}  [{que}]   {texto.strip()[:60]}")
        return 1
    print("  ✓ todos los mutantes murieron: la suite distingue el código cambiado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
