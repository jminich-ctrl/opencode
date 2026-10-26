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
import signal
import re
import subprocess
import sys

BASE = os.environ.get("BASE", "HEAD~1")
SUITE = os.environ.get("SUITE", "python3 -m unittest discover -s tests -t . -q")
LIMITE = int(os.environ.get("LIMITE", "40"))
# Sólo el código de producto. Mutar los scripts del método da ruido puro: no tienen suite,
# así que todo sobrevive y tapa la señal del código que sí importa.
# Uno o varios prefijos separados por coma: el contrato que `escribir-tests.sh` declara en su
# comentario desde siempre («un proyecto con back y front tiene dos») y que acá se leía como
# UN solo directorio. Con `CODIGO=backend/app,frontend/src` el `startswith` no matcheaba
# nunca, en ningún proyecto.
CODIGO = [c.strip().rstrip("/") for c in os.environ.get("CODIGO", "src").split(",") if c.strip()]
# Archivos explícitos, separados por espacios. `git diff --name-only` NO lista los archivos
# sin trackear, y una tarea que CREA su implementación —el caso más común— deja el archivo
# así: el filtro no veía nada y esto devolvía 2 («nada que mutar»). Es el mismo agujero que
# el paso 4 del gate ya documenta para su reversión, «archivos nuevos: nada que revertir».
# Con `ARCHIVOS` el llamador dice cuáles son y no se adivina del índice de git.
ARCHIVOS = [a for a in os.environ.get("ARCHIVOS", "").split() if a.strip()]
# Cuántos sobrevivientes se listan: un número, o "todos" (lo que pide la auditoría).
DETALLE = os.environ.get("DETALLE", "10").strip() or "10"

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
    """Aplica UNA mutación, la del nodo elegido, y deja el resto intacto.

    Con `centinela=True` no muta: reemplaza la sentencia por una excepción que nadie
    atrapa. Eso contesta otra pregunta —¿el test llega a ejecutar esta línea?— y es la que
    hay que contestar ANTES de culpar a las aserciones. Ver `nunca_se_ejecuta`.
    """

    def __init__(self, objetivo, centinela=False):
        self.objetivo = objetivo
        self.centinela = centinela
        self.aplicada = False

    def generic_visit(self, nodo):
        nodo = super().generic_visit(nodo)
        if nodo is self.objetivo and not self.aplicada:
            self.aplicada = True
            return self.mutar(nodo)
        return nodo

    def mutar(self, nodo):
        if self.centinela:
            # `BaseException` y no `Exception`: el código de producto que envuelve su cuerpo
            # en `except Exception` se tragaría el centinela y el resultado diría «no se
            # ejecuta» sobre una línea que sí se ejecuta. La forma de abajo sólo la atrapa un
            # `except BaseException` o un `except:` desnudo, y eso merece saberse.
            return ast.Raise(
                exc=ast.Call(func=ast.Name(id="BaseException", ctx=ast.Load()),
                             args=[ast.Constant(value="centinela-mutar")], keywords=[]),
                cause=None)
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

    # Las ANOTACIONES DE TIPO no son código que un test pueda distinguir. `dict | None` es un
    # `BinOp(BitOr)` en el árbol, así que entraba como «cambiar el operador aritmético» y
    # producía un mutante INMATABLE: ningún test observa el tipo declarado, y el mutante
    # sobrevive por construcción. El efecto, medido el 2026-10-21: toda tarea cuya
    # implementación sea un archivo NUEVO —donde el diff cubre también la línea de la firma—
    # con un tipo unión moderno falla el chequeo de mutación para siempre. Fue lo que dejó a
    # T05a en punto muerto cuatro corridas seguidas, con el veredicto correcto en su forma
    # («el test cubre las líneas y no verifica su comportamiento») y falso en su contenido.
    #
    # Se excluyen por IDENTIDAD de nodo y no por línea: una línea puede llevar una anotación
    # y código de verdad, y excluir la línea entera apagaría el chequeo donde sí sirve.
    anotados = set()
    for nodo in ast.walk(arbol):
        anotaciones = []
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            anotaciones.append(nodo.returns)
            a = nodo.args
            for arg in (list(a.args) + list(a.posonlyargs) + list(a.kwonlyargs)
                        + [a.vararg, a.kwarg]):
                if arg is not None:
                    anotaciones.append(arg.annotation)
        elif isinstance(nodo, ast.AnnAssign):
            anotaciones.append(nodo.annotation)
        for an in anotaciones:
            if an is None:
                continue
            anotados.add(id(an))
            for hijo in ast.walk(an):
                anotados.add(id(hijo))

    # Las variables que NADIE LEE. Borrar `sobrante = []` cuando ese nombre no se lee en
    # ninguna parte del archivo no cambia el comportamiento POR DEFINICIÓN: el mutante es
    # inmatable, igual que el de una anotación de tipo, y ningún test puede matarlo. El
    # método lo informaba como «la suite no nota estos cambios», que culpa al test de algo
    # imposible.
    #
    # Medido el 2026-10-25 en T20 de clasificados: de sus dos mutantes sobrevivientes, uno
    # era `result = []` —una lista que el código reemplaza por `conversations` y nunca lee— y
    # el otro un bug latente de verdad. Mezclar los dos en la misma lista hace que el real
    # pese la mitad.
    #
    # Se mira si el nombre aparece como LECTURA en todo el archivo, no en la función: una
    # global o una closure pueden leerlo desde otro ámbito, y marcar eso sería declarar
    # muerta una variable viva.
    leidos = {n.id for n in ast.walk(arbol)
              if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    muertas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1 \
                and isinstance(nodo.targets[0], ast.Name) \
                and nodo.targets[0].id not in leidos:
            muertas.add(id(nodo))

    por_linea = {}
    for nodo in ast.walk(arbol):
        if id(nodo) in muertas:
            continue
        linea = getattr(nodo, "lineno", None)
        if linea is None or linea not in lineas_cambiadas or linea in aridos:
            continue
        if id(nodo) in anotados:
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


# El tope de tiempo por pasada, en segundos. Se calibra con lo que tarda la suite SIN mutar
# (`calibrar_tope`), porque una suite de 0,2 s y una de 15 minutos no pueden compartir número.
TOPE = [None]


def correr():
    """La suite, con tope de tiempo. Un mutante que CUELGA el programa cuenta como MUERTO.

    Sin tope, un mutante que deja el programa girando cuelga el gate entero y la corrida no
    termina nunca. Medido el 2026-10-25 en ejemplo-pacman: un mutante en `__main__.py` —que
    es el game loop— dejó la suite corriendo 45 MINUTOS contra una suite que tarda 0,24 s, y
    la corrida quedó trabada con un archivo mutado en el árbol. En cualquier proyecto con un
    loop, un servidor o un `input()`, eso está garantizado.
    El timeout cuenta como muerte y no como supervivencia porque el mutante cambió el
    comportamiento de una forma perfectamente observable: el programa dejó de terminar. Es lo
    mismo que hace el gate de TestForge/Meta ACH, que trata fail, error y timeout como muerte.
    Contarlo como «sobrevivió» sería cobrarle al test una diferencia que sí distingue.

    Se mata el ÁRBOL y no el proceso: `SUITE` es un shell que lanza python, así que matar al
    shell deja al nieto girando —es el defecto que este repo ya cerró en su vigilante, «miraba
    el grupo de procesos, no el árbol»—. Con `start_new_session` el hijo es líder de su grupo
    y `killpg` se lleva a todos.
    """
    proc = subprocess.Popen(SUITE, shell=True, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return proc.wait(timeout=TOPE[0]) == 0
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.wait()
        return False          # colgarse ES una diferencia observable: el mutante muere


def calibrar_tope():
    """Mide la suite sin mutar y fija el tope en 10x, con un piso de 60 s.

    El múltiplo es generoso a propósito: un tope ajustado mataría mutantes legítimos por
    lentitud y los informaría como muertos, que es un falso verde — justo lo que este método
    existe para no hacer. El piso cubre las suites muy rápidas, donde 10x son milisegundos.
    """
    import time
    t0 = time.monotonic()
    ok = subprocess.run(SUITE, shell=True, capture_output=True, text=True).returncode == 0
    tardo = time.monotonic() - t0
    # Configurable para poder MEDIR el tope sin esperarlo: sin esto, un test del propio
    # método que verifique el timeout tarda un minuto por mutante.
    forzado = os.environ.get("TOPE_MUTANTE", "").strip()
    automatico = max(60.0, tardo * 10)
    if not forzado:
        TOPE[0] = automatico
        return ok, tardo
    # Un tope por debajo de lo que tarda la suite SIN mutar hace que TODOS los mutantes den
    # timeout, y como el timeout cuenta como muerte, el veredicto sale «todos murieron: la
    # suite distingue». O sea: un falso verde producido por una configuración, que es
    # exactamente lo que este método existe para no hacer. Medido el 2026-10-25 con
    # TOPE_MUTANTE=0.01 sobre una suite de 0,14 s: tres mutantes, tres muertes, verde.
    #
    # El piso es 3x la suite base: por debajo de eso el tope no está midiendo al mutante,
    # está midiendo al reloj.
    piso = max(3.0 * tardo, 1.0)
    if float(forzado) < piso:
        print(f"  ✗ TOPE_MUTANTE={forzado}s es menor que el piso de {piso:.2f}s "
              f"(3x los {tardo:.2f}s que tarda la suite sin mutar).")
        print("     Con un tope así TODOS los mutantes dan timeout y el timeout cuenta como")
        print("     muerte: el verde lo produciría el reloj, no el test. No se sigue.")
        TOPE[0] = None
        return "tope", tardo
    TOPE[0] = float(forzado)
    return ok, tardo


def sentencia_de(arbol, linea, nodo):
    """La sentencia que hay que reemplazar para preguntar por `linea`.

    Si el candidato ya es una sentencia, es él. Si es una expresión —el `Compare` de un
    ROR, por ejemplo— el centinela tiene que ir en la sentencia que la contiene, porque
    `raise` no es una expresión y el archivo no compilaría.
    """
    if isinstance(nodo, ast.stmt):
        return next((x for x in ast.walk(arbol)
                     if getattr(x, "lineno", None) == linea and type(x) is type(nodo)), None)
    for padre in ast.walk(arbol):
        for hijo in ast.iter_child_nodes(padre):
            if getattr(hijo, "lineno", None) == linea and isinstance(hijo, ast.stmt):
                return hijo
    return next((x for x in ast.walk(arbol)
                 if isinstance(x, ast.stmt) and getattr(x, "lineno", None) == linea), None)


def nunca_se_ejecuta(archivo, linea, nodo, original):
    """¿El test llega a esta línea, o ni la toca?

    Un mutante que sobrevive admite dos lecturas opuestas, y el método daba SIEMPRE la
    primera: «el test cubre la línea y no verifica su comportamiento» —arreglá las
    aserciones—. La otra es que el test **no ejecuta** esa línea, y entonces las
    aserciones no tienen nada que ver: lo que hay que sacar es el mock que la reemplaza.
    Medido el 2026-10-25 en T26 de clasificados: el test mockeaba
    `users_register.insert_user`, que ES la función de la tarea, así que los tres mutantes
    de `users_register.py` sobrevivían por no correr nunca. El agente recibía «cubre las
    líneas», que lo mandaba al lado contrario, y la tarea quedó trabada dos corridas.

    En vez de medir cobertura —otra dependencia, otro corredor, otro cwd que diverge— se
    pregunta con la maquinaria que ya hay: se reemplaza la sentencia por una excepción que
    nadie atrapa. Si la suite PASA con eso puesto, la línea no se ejecutó. Es exacto y no
    necesita que la suite sepa nada nuevo.

    De paso contesta algo que me falló dos veces: que el mutador efectivamente escribió el
    archivo. Un centinela que no mata la suite sobre una línea que sí corre es imposible.
    """
    try:
        arbol = ast.parse(original)
        objetivo = sentencia_de(arbol, linea, nodo)
        if objetivo is None:
            return None                     # no se pudo preguntar: no se afirma nada
        tocado = ast.fix_missing_locations(Mutador(objetivo, centinela=True).visit(arbol))
        archivo.write_text(ast.unparse(tocado))
        return correr()                     # la suite pasa con la excepción puesta
    except (SyntaxError, ValueError, RecursionError):
        return None
    finally:
        archivo.write_text(original)


def lineas_cambiadas(archivo):
    d = subprocess.run(["git", "diff", "-U0", BASE, "--", str(archivo)],
                       capture_output=True, text=True).stdout
    nums = set()
    for ini, n in re.findall(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", d, re.M):
        nums.update(range(int(ini), int(ini) + int(n or 1)))
    if not nums and not subprocess.run(["git", "cat-file", "-e", f"{BASE}:{archivo}"],
                                       capture_output=True).returncode == 0:
        # El archivo no existe en BASE: es nuevo, y entonces TODAS sus líneas son cambio. Sin
        # esto el diff sale vacío y un archivo nuevo no se muta — que es justo lo que hace una
        # tarea que escribe su implementación desde cero.
        nums = set(range(1, len(archivo.read_text().split("\n")) + 1))
    return nums


def main():
    del_git = subprocess.run(
        ["git", "diff", "--name-only", "--relative", BASE],
        capture_output=True, text=True).stdout.split()
    archivos = [a for a in dict.fromkeys(del_git + ARCHIVOS)
                if a.endswith(".py") and "test" not in a
                and any(a.startswith(c + "/") for c in CODIGO)]
    if not archivos:
        # 2, no 0: «no había nada que mutar» es un ⊘ y NO un pase. Devolvía 0, y
        # `escribir-tests.sh` lo corre con `>/dev/null 2>&1` e imprime «✓ los mutantes mueren:
        # el test distingue». Con el default `CODIGO=src` y un proyecto cuyo código vive en
        # `backend/app` y `frontend/src`, eso era TODO clasificados: el único chequeo de que
        # el test distingue nunca corrió, y vendía un verde que no se ganó. Dos de los cuatro
        # tests aceptados el 2026-10-19 lo recibieron.
        #
        # El script ya sabía informar esto bien para TypeScript —«⊘ no hay mutador … No es un
        # pase»—. Este caso es el mismo ⊘ y salía ✓.
        print("  ⊘ no hay código Python cambiado que mutar bajo: " + ",".join(CODIGO))
        print("     No es un pase: nadie verificó que el test distinga.")
        return 2
    verde, tardo = calibrar_tope()
    # Los dos motivos se informan por separado: «la suite está en rojo» es del proyecto y
    # «el tope es inválido» es de la configuración, y mandan a lugares distintos. Devolver un
    # solo False hacía que un tope mal puesto se informara como suite roja —falso— y encima
    # con código 0. Es el defecto que este método viene cerrando todo el día y lo cometí dos
    # minutos después de cerrarlo.
    if verde == "tope":
        return 2
    if not verde:
        print("  ✗ la suite ya está en rojo: arreglala antes de mutar")
        return 1
    print(f"  · la suite sin mutar tarda {tardo:.2f}s; tope por mutante: {TOPE[0]:.0f}s")

    todos = []
    for a in archivos:
        p = pathlib.Path(a)
        if p.exists():
            todos += candidatos(p, lineas_cambiadas(p))
    if not todos:
        # El mismo ⊘ por otra puerta: hay archivos, pero el diff no dio un solo mutante. Si
        # nadie mutó nada, nadie verificó que el test distinga.
        print("  ⊘ el diff no tiene nada que mutar con provecho (todo árido o sin operadores)")
        print("     No es un pase: no se probó ni un mutante.")
        return 2
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
                sobrevivientes.append([archivo, linea, que,
                                       original.split("\n")[linea - 1], nodo, original])
        except (SyntaxError, ValueError, RecursionError):
            continue
        finally:
            archivo.write_text(original)

    print(f"  {len(todos)} mutante(s) probados sobre el diff, uno por línea")
    if sobrevivientes:
        # El centinela corre SÓLO sobre los que sobrevivieron: si todos murieron no hay nada
        # que diagnosticar, y son pocos cuando hay.
        muertas = 0
        for sv in sobrevivientes:
            sv.append(nunca_se_ejecuta(sv[0], sv[1], sv[4], sv[5]))
            if sv[6] is True:
                muertas += 1
                sv[2] = "la línea NO se ejecuta"
        print(f"  ✗ {len(sobrevivientes)} sobrevivieron: la suite no nota estos cambios")
        if muertas:
            print(f"  · de esos, {muertas} sobre líneas que el test NUNCA ejecuta: ahí el")
            print("    problema no son las aserciones. Algo las reemplaza —casi siempre un")
            print("    mock del propio archivo de la tarea— o son código inalcanzable.")
        # Cuántos se listan. El tope existe porque en el gate de UNA tarea son pocos y una
        # lista larga tapa el veredicto; pero imprimía "85 sobrevivieron" y mostraba 10 sin
        # decir que mostraba 10, y la auditoría de un proyecto entero —que produce decenas—
        # dejaba 75 sin forma de verlos. `DETALLE=todos` los pide todos; la auditoría lo usa.
        tope_lista = len(sobrevivientes) if DETALLE == "todos" else min(int(DETALLE), len(sobrevivientes))
        for archivo, linea, que, texto, _nodo, _orig, _ne in sobrevivientes[:tope_lista]:
            # El `→` es un CONTRATO, no decoración: `escribir-tests.sh` extrae los
            # sobrevivientes con `grep '→'` para ponerlos en el mensaje que el agente lee en
            # su reintento. Sin la flecha, esa extracción salía vacía SIEMPRE —en todas las
            # corridas de la historia— y el reintento iba a ciegas. Cuarta vez que el
            # extractor busca una forma que el productor no emite (el ✗ del gate, las fallas
            # de vitest, el TODO, esto): el que imprime y el que raspa viven en archivos
            # distintos y nadie los lee juntos. Si se cambia esta línea, se cambia allá.
            print(f"     → {archivo}:{linea}  [{que}]   {texto.strip()[:60]}")
        if tope_lista < len(sobrevivientes):
            print(f"     · y {len(sobrevivientes) - tope_lista} más sin listar: DETALLE=todos "
                  f"los muestra. Un informe que calla lo que no mostró manda a adivinar.")
        # 3 y no 1 cuando hay líneas que no se ejecutan: `escribir-tests.sh` imprime el
        # veredicto, y el que tenía escrito —«el test cubre las líneas»— es falso en ese
        # caso. Un código aparte es lo único que le permite no afirmarlo.
        return 3 if muertas else 1
    print("  ✓ todos los mutantes murieron: la suite distingue el código cambiado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
