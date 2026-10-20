#!/usr/bin/env python3
"""Importar un paquete que el proyecto no declara. El espejo en Python del chequeo de JS.

    python3 scripts/_imports.py backend/app/rutas/auth.py ...        # los que mirar
    python3 scripts/_imports.py --todo backend/app                    # un árbol entero

Sale 0 si todo lo importado está declarado, 1 si no, y 2 si no había nada que mirar —que
no es lo mismo: un chequeo sin material no es un chequeo que pasa—.

Por qué existe: el agente de T04 importó `mysql.connector` cuando el `AGENTS.md` del
proyecto declara `pymysql`. El síntoma fue `ModuleNotFoundError` dentro del test, y el
método lo informó como «el test no pasa ni con la implementación del propio agente», que
es el diagnóstico equivocado: el test estaba bien y el código usaba algo que nadie
declaró.

Lo dejé sin hacer un rato porque pensé que hacía falta mantener a mano la lista de módulos
de la biblioteca estándar, que es larga y cambia por versión. No hace falta:
`sys.stdlib_module_names` la trae, y es la del intérprete que está corriendo. El chequeo
que parecía caro costaba una línea.
"""
import ast
import pathlib
import sys

# Nombre de import → nombre de distribución, para los casos donde no coinciden. Sale de
# los paquetes instalados, así que no hay que mantenerlo: si algo está instalado, sabemos
# qué distribución lo trae.
try:
    from importlib.metadata import packages_distributions
    DISTRIBUCION = {k: v for k, v in packages_distributions().items()}
except Exception:
    DISTRIBUCION = {}


def declarados(raiz):
    """Lo que el proyecto declara: todos los requirements*.txt que encuentre."""
    nombres = set()
    for f in sorted(raiz.rglob("requirements*.txt")):
        if ".venv" in f.parts:
            continue
        for linea in f.read_text().splitlines():
            linea = linea.split("#")[0].strip()
            if not linea:
                continue
            # `fastapi==0.104.1`, `httpx>=0.27`, `pymysql`
            for sep in ("==", ">=", "<=", "~=", ">", "<", "["):
                linea = linea.split(sep)[0]
            nombres.add(linea.strip().lower().replace("-", "_"))
    return nombres


def importados(archivos):
    """Los nombres de módulo de primer nivel que importan estos archivos."""
    nombres = set()
    for a in archivos:
        try:
            arbol = ast.parse(a.read_text())
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for n in nodo.names:
                    nombres.add(n.name.split(".")[0])
            elif isinstance(nodo, ast.ImportFrom):
                # `from . import x` es relativo: no es una dependencia.
                if nodo.level == 0 and nodo.module:
                    nombres.add(nodo.module.split(".")[0])
    return nombres


def locales(raiz):
    """Paquetes del propio proyecto: lo que tiene un __init__.py, y los directorios raíz."""
    nombres = set()
    for ini in raiz.rglob("__init__.py"):
        if ".venv" in ini.parts or "node_modules" in ini.parts:
            continue
        nombres.add(ini.parent.name)
    for d in raiz.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            nombres.add(d.name)
            for sub in d.iterdir():
                if sub.is_dir() and not sub.name.startswith("."):
                    nombres.add(sub.name)
    return nombres


def modulo_del_proyecto(nodo, archivo, raiz):
    """La ruta del módulo que este `from X import ...` nombra, si es del proyecto.

    Devuelve None si no se puede resolver a un archivo del árbol: entonces no es un import
    interno y lo juzga el chequeo de requirements, que es el de arriba.
    """
    if nodo.level:
        base = archivo.parent
        for _ in range(nodo.level - 1):
            base = base.parent
        partes = (nodo.module or "").split(".") if nodo.module else []
    else:
        if not nodo.module:
            return None
        partes, base = nodo.module.split("."), raiz
    cand = base
    for parte in partes:
        cand = cand / parte
    for ruta in (cand.with_suffix(".py"), cand / "__init__.py"):
        if ruta.is_file():
            return ruta
    return None


def expone(ruta):
    """Los nombres de nivel superior de un módulo, o None si no se puede saber.

    None y no un conjunto vacío: con `from x import *` o un `__getattr__` de módulo, los
    nombres se crean en tiempo de ejecución y afirmar que algo «no está» sería un falso
    rojo. Un chequeo que marca a todos no distingue a ninguno.
    """
    try:
        arbol = ast.parse(ruta.read_text())
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None
    # Por ALCANCE y no por lista de formas. La versión anterior enumeraba cuatro maneras de
    # definir un nombre (`Assign` con target `Name`, `AnnAssign`, los dos `import`) y todo lo
    # demás le era invisible, así que daba ROJO sobre código que Python corre sin chistar:
    # `DEBUG, VERBOSE = False, True`, un `with ... as f: HANDLE = ...`, un `for`, un `match`.
    # Y el mensaje manda a buscar el nombre donde sí está —«fijate cómo se llama»—, así que
    # la tarea quema sus reintentos contra un rojo que sólo se apaga reescribiendo una
    # asignación correcta. Un chequeo que enumera formas envejece callando: cada forma nueva
    # del lenguaje es un falso rojo esperando. Las que ligan nombres son las de contexto
    # Store, y eso el árbol ya lo dice.
    nombres = set()
    # No se baja a funciones, clases ni comprensiones: sus nombres NO son del módulo. El
    # nombre de la función sí, y por eso se agrega antes de cortar el descenso.
    CORTA = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
             ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)
    pendientes = list(arbol.body)
    while pendientes:
        n = pendientes.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nombres.add(n.name)
            continue
        if isinstance(n, CORTA):
            continue
        if isinstance(n, ast.Import):
            nombres.update((a.asname or a.name).split(".")[0] for a in n.names)
            continue
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name == "*":
                    return None
                nombres.add(a.asname or a.name)
            continue
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            nombres.add(n.id)
        # `case [x, *resto]` / `case Punto() as p` / `case {**resto}`: ligan nombres y no
        # son nodos `Name`.
        for campo in ("name", "rest"):
            v = getattr(n, campo, None)
            if isinstance(n, (getattr(ast, "MatchAs", ()), getattr(ast, "MatchStar", ()),
                              getattr(ast, "MatchMapping", ()))) and isinstance(v, str):
                nombres.add(v)
        pendientes.extend(ast.iter_child_nodes(n))
    return None if "__getattr__" in nombres else nombres


def internos_rotos(archivos, raiz):
    """`from <modulo del proyecto> import <algo que no está>`.

    Por qué existe: T14 se integró con `from .conexion import get_db_connection` y
    conexion.py sólo exporta `configuracion()` y `conexion()`. El módulo no se podía
    importar, el gate la cerró en VERDE —no tenía test declarado— y nadie se enteró hasta
    que la tarea siguiente se estrelló contra ella. El chequeo de arriba no lo veía porque
    SALTEA los módulos locales: eran el agujero justo en el medio del chequeo de imports.

    Y el nombre inventado no fue casualidad: `get_db_connection` aparece en intentos de
    TRES tareas distintas (T04, T15, T26). Está nombrado en AGENTS.md ahora; esto lo
    reprueba cuando igual pasa.
    """
    rotos = []
    for a in archivos:
        try:
            arbol = ast.parse(a.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ImportFrom):
                continue
            destino = modulo_del_proyecto(nodo, a, raiz)
            if destino is None or destino == a:
                continue
            tiene = expone(destino)
            if tiene is None:
                continue
            # `from paquete import submodulo` lo resuelve Python importando el submódulo:
            # el `__init__.py` no tiene por qué nombrarlo. Sin esto el chequeo reprobaba
            # `from backend.app.datos import users`, que es como el código que ANDA accede a
            # la capa de datos —y es la forma que el propio método exige, para que el
            # `@patch` del test aplique—. Lo encontró el control negativo contra el tronco:
            # dos falsos positivos antes de que el chequeo viera la luz.
            if destino.name == "__init__.py":
                for sub in destino.parent.iterdir():
                    if sub.suffix == ".py":
                        tiene.add(sub.stem)
                    elif sub.is_dir() and (sub / "__init__.py").is_file():
                        tiene.add(sub.name)
            for al in nodo.names:
                if al.name != "*" and al.name not in tiene:
                    rotos.append((a, al.name, destino))
    return rotos


def main():
    args = sys.argv[1:]
    raiz = pathlib.Path.cwd()
    if args and args[0] == "--todo":
        archivos = [p for d in args[1:] for p in pathlib.Path(d).rglob("*.py")]
    else:
        archivos = [pathlib.Path(a) for a in args if a.endswith(".py")]
    archivos = [a for a in archivos if a.is_file() and ".venv" not in a.parts]
    if not archivos:
        print("  ⊘ no hay archivos .py que cruzar contra los requirements — no pudo verificarse")
        return 2

    permitidos = set(sys.stdlib_module_names) | declarados(raiz) | locales(raiz)
    fuera = []
    for nombre in sorted(importados(archivos)):
        clave = nombre.lower().replace("-", "_")
        if clave in permitidos:
            continue
        # Puede estar declarado con el nombre de su distribución y no del módulo.
        dists = {d.lower().replace("-", "_") for d in DISTRIBUCION.get(nombre, [])}
        if dists & permitidos:
            continue
        fuera.append(nombre)

    if fuera:
        print(f"  ✗ importa paquetes que los requirements no declaran: {' '.join(fuera)}")
        print("     Declaralo en el requirements que corresponda o no lo importes. Si no está")
        print("     permitido en AGENTS.md, pará y decilo: la lista se amplía, no se esquiva.")
        return 1
    rotos = internos_rotos(archivos, raiz)
    if rotos:
        print("  ✗ importa de un módulo del proyecto algo que ese módulo no define:")
        for a, nombre, destino in rotos[:5]:
            print(f"     {a}: `{nombre}` no está en {destino}")
        print("     Mirá qué exporta ese módulo antes de importarle un nombre. Si el ayudante")
        print("     que buscás no aparece, no es que falte: fijate cómo se llama (AGENTS.md).")
        return 1

    print(f"  ✓ todo lo importado está declarado o es de la biblioteca estándar")
    print(f"     · inspeccionó: {len(archivos)} archivo(s) .py contra los requirements*.txt,")
    print(f"       y los imports internos contra lo que cada módulo define")
    return 0


if __name__ == "__main__":
    sys.exit(main())
