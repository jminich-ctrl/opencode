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
    print(f"  ✓ todo lo importado está declarado o es de la biblioteca estándar")
    print(f"     · inspeccionó: {len(archivos)} archivo(s) .py contra los requirements*.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
