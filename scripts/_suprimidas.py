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
import os
import re
import subprocess
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
    """Hallazgos como `(linea, qué, tramo)`.

    El TRAMO —el conjunto de líneas que podrían delatar el hallazgo— y no sólo la línea
    donde se informa, porque el acote al diff compara contra las líneas que el cambio tocó
    y las dos no coinciden: quien reemplaza el cuerpo de un `except` que ya existía por
    `pass` cambia la línea del CUERPO, y el hallazgo se informa en la línea del `except`.
    Con una sola línea, ese cambio —la forma más común de apagar una señal en código
    existente— pasaba el filtro sin que nada se imprimiera.
    """
    hallazgos = []
    texto = archivo.read_text(errors="replace")
    for i, linea in enumerate(texto.splitlines(), 1):
        # Sin distinguir mayúsculas: `# NOQA` es tan supresión como `# noqa`, y el grep que
        # esto reemplazó usaba -i. Lo atrapó el caso que cubre las formas habituales.
        bajo = linea.lower()
        for aguja, nombre in PATRONES_TEXTO:
            if aguja in bajo:
                hallazgos.append((i, f"{nombre}: {linea.strip()[:70]}", {i}))
    if archivo.suffix == ".py":
        lineas_texto = texto.split("\n")
        try:
            arbol = ast.parse(texto)
        except SyntaxError:
            return hallazgos
        for nodo in ast.walk(arbol):
            # El except que no hace nada, en una línea o en cinco.
            # La forma LEGÍTIMA, nombrada: un `# best-effort` en la línea del handler o
            # justo arriba. Hoy no había ninguna —`except curses.error: pass` también caía, y
            # `# noqa` está en la lista de arriba—, así que el único camino era escribir peor
            # código (`except X: _ = None`). Un chequeo sin salida legítima se esquiva, y
            # esquivarlo deja el código peor que la señal que el chequeo buscaba.
            #
            # Queda auditable: `grep -rn best-effort` muestra todas las excepciones vivas.
            if isinstance(nodo, ast.ExceptHandler) and vacio(nodo.body) and not any(
                    "best-effort" in (lineas_texto[k - 1] if 0 < k <= len(lineas_texto) else "")
                    for k in (nodo.lineno - 1, nodo.lineno, nodo.lineno + 1)):
                que = ast.unparse(nodo.type) if nodo.type else "todo"
                # El tramo es el handler ENTERO, cuerpo incluido: apagar un handler que ya
                # existía se hace cambiando el cuerpo, no la línea del `except`.
                fin = getattr(nodo, "end_lineno", None) or nodo.lineno
                hallazgos.append((nodo.lineno,
                                  f"except {que} y no hace nada: la falla se pierde",
                                  set(range(nodo.lineno, fin + 1))))
            # Un test salteado.
            if isinstance(nodo, (ast.FunctionDef, ast.ClassDef)):
                for d in nodo.decorator_list:
                    if "skip" in ast.unparse(d):
                        # La línea del DECORADOR además de la del `def`: saltear un test que
                        # ya estaba agrega la línea del decorador y no toca el `def`.
                        hallazgos.append((nodo.lineno,
                                          f"{nodo.name} está salteado: {ast.unparse(d)}",
                                          {nodo.lineno, d.lineno}))
    return hallazgos


def lineas_cambiadas(archivo, base):
    """Las líneas que ESTE cambio agregó o tocó. Devuelve None si no se puede saber.

    El gate pasa los archivos CAMBIADOS y `revisar()` leía cada archivo ENTERO, así que una
    tarea que toca un archivo se comía las señales que ya estaban. Medido: tres `except
    Exception: pass` del idiom de curses en `ejemplo-pacman/src/pacman/render.py` y
    `__main__.py` —best effort al escribir en la última celda de la ventana— reprobaban a
    cualquier tarea nueva sobre esos archivos, que son el alcance declarado de T07, T08, T11
    y T12. Y no podía sacarlas sin romper el idiom, ni tocarlas sin que el paso 2 la
    reprobara por salirse del alcance: el único camino era escribir peor código.

    Es el mismo acote que ya tenían los imports y los directorios vacíos, y el mismo que usa
    `mutar.py`. Si no se puede saber —no hay base, git falla— no se filtra nada: un chequeo
    que no puede acotar reporta de más, no de menos.
    """
    if not base:
        return None
    # Un archivo que NO existe en la base es todo nuevo: no se filtra nada. `git diff` no
    # muestra lo que no está en la base, así que sin este caso la función devolvía un conjunto
    # vacío y filtraba TODO — apagando el chequeo justo para los archivos que la tarea CREA,
    # que son la mayoría. Lo atrapó la suite del método: al acotar un chequeo demasiado ancho
    # lo volví demasiado angosto, que es el mismo error por el otro lado.
    # `rev:ruta` lo resuelve git desde la RAÍZ DEL REPO, no desde el cwd, así que sin el
    # prefijo esto fallaba —rc 128, «path does not exist»— para TODO proyecto que viva en un
    # subdirectorio de su repo, que son los dos ejemplos y cualquier monorepo. La función
    # devolvía None siempre y el acote no existía: las tres `except Exception: pass` del
    # idiom de curses seguían reprobando a T07, T08, T11 y T12, que es el defecto que este
    # acote venía a cerrar. El gate hace esto bien dos pasos más abajo y el arreglo del
    # hermano no se copió acá. Lo encontró una auditoría, no la suite: el test armaba el
    # repo con el proyecto en la raíz, que es el único caso donde el prefijo es vacío.
    prefijo = subprocess.run(["git", "rev-parse", "--show-prefix"],
                             capture_output=True, text=True)
    pref = prefijo.stdout.strip() if prefijo.returncode == 0 else ""
    existe = subprocess.run(["git", "cat-file", "-e", f"{base}:{pref}{archivo}"],
                            capture_output=True)
    if existe.returncode != 0:
        return None
    r = subprocess.run(["git", "diff", "-U0", base, "--", str(archivo)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    nums = set()
    for linea in r.stdout.split("\n"):
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))?", linea)
        if m:
            ini, cuantas = int(m.group(1)), int(m.group(2) or 1)
            nums.update(range(ini, ini + cuantas))
    return nums


def main():
    EXT = (".py", ".ts", ".tsx", ".js", ".jsx")

    def sirve(p):
        return (p.is_file() and p.suffix in EXT
                and "node_modules" not in p.parts and "__pycache__" not in p.parts)

    # Acepta directorios y archivos sueltos: en modo tarea el gate pasa la lista de lo que
    # esa tarea tocó, no un árbol.
    archivos = []
    for a in sys.argv[1:]:
        ruta = pathlib.Path(a)
        if ruta.is_dir():
            archivos += [p for p in ruta.rglob("*") if sirve(p)]
        elif sirve(ruta):
            archivos.append(ruta)
    if not archivos:
        print("  ⊘ no hay archivos que revisar por señales suprimidas — no pudo verificarse")
        return 2
    base = os.environ.get("BASE", "")
    todos = []
    for a in sorted(archivos):
        tocadas = lineas_cambiadas(a, base)
        for ln, que, tramo in revisar(a):
            if tocadas is not None and not (tramo & tocadas):
                continue   # ya estaba antes de este cambio: no es de esta tarea
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
