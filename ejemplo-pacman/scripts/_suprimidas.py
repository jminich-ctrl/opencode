#!/usr/bin/env python3
"""Señales suprimidas, incluida la forma multilínea que un grep por línea no ve.

    python3 scripts/_suprimidas.py backend/app frontend/src

Apagar una señal es más barato que arreglar la causa y no deja rastro en los tests, así que
el gate lo busca. Pero lo buscaba con un grep línea por línea, y la forma más común en
Python ocupa tres:

    except Exception:
        # un comentario que explica por qué está bien
        pass

Pasó en serio: el `main.py` de T06 montaba los routers con `except Exception: pass` en
líneas separadas —y citando mi propio texto de la tarea para justificarlo—, así que un
módulo de rutas roto quedaba sin montar en silencio y el síntoma era un 404 donde el test
esperaba un 400. Es la vacuidad otra vez: «no pude» disfrazado de «no hay nada».

Sale 0 si no encontró nada, 1 si encontró, 2 si no había archivos que mirar.
"""
import ast
import pathlib
import sys

PATRONES_TEXTO = (
    ("# noqa", "noqa"),
    ("# type: ignore", "type: ignore"),
    ("eslint-disable", "eslint-disable"),
    ("|| true", "|| true"),
)


def vacio(cuerpo):
    """Un bloque que no hace nada: sólo `pass`, `...` o un docstring."""
    reales = [n for n in cuerpo if not (isinstance(n, ast.Expr) and
                                        isinstance(n.value, ast.Constant))]
    if not reales:
        return True
    return all(isinstance(n, ast.Pass) for n in reales)


def revisar(archivo):
    hallazgos = []
    texto = archivo.read_text(errors="replace")
    for i, linea in enumerate(texto.splitlines(), 1):
        # Sin distinguir mayúsculas: `# NOQA` es tan supresión como `# noqa`, y el grep que
        # esto reemplazó usaba -i. Lo atrapó el caso que cubre las formas habituales.
        bajo = linea.lower()
        for aguja, nombre in PATRONES_TEXTO:
            if aguja in bajo:
                hallazgos.append((i, f"{nombre}: {linea.strip()[:70]}"))
    if archivo.suffix == ".py":
        try:
            arbol = ast.parse(texto)
        except SyntaxError:
            return hallazgos
        for nodo in ast.walk(arbol):
            # El except que no hace nada, en una línea o en cinco.
            if isinstance(nodo, ast.ExceptHandler) and vacio(nodo.body):
                que = ast.unparse(nodo.type) if nodo.type else "todo"
                hallazgos.append((nodo.lineno,
                                  f"except {que} y no hace nada: la falla se pierde"))
            # Un test salteado.
            if isinstance(nodo, (ast.FunctionDef, ast.ClassDef)):
                for d in nodo.decorator_list:
                    if "skip" in ast.unparse(d):
                        hallazgos.append((nodo.lineno, f"{nodo.name} está salteado: {ast.unparse(d)}"))
    return hallazgos


def main():
    dirs = [pathlib.Path(a) for a in sys.argv[1:]]
    archivos = [p for d in dirs if d.exists()
                for p in d.rglob("*")
                if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".js", ".jsx")
                and "node_modules" not in p.parts and "__pycache__" not in p.parts]
    if not archivos:
        print("  ⊘ no hay archivos que revisar por señales suprimidas — no pudo verificarse")
        return 2
    todos = []
    for a in sorted(archivos):
        for ln, que in revisar(a):
            todos.append(f"{a}:{ln} — {que}")
    if todos:
        print("  ✗ hay señales suprimidas:")
        for t in todos[:5]:
            print(f"     {t}")
        if len(todos) > 5:
            print(f"     … y {len(todos) - 5} más")
        return 1
    print("  ✓ sin señales suprimidas")
    print(f"     · inspeccionó: {len(archivos)} archivo(s), texto y árbol sintáctico")
    return 0


if __name__ == "__main__":
    sys.exit(main())
