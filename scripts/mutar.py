#!/usr/bin/env python3
"""¿Los tests distinguen de verdad? Muta el código cambiado y exige que la suite lo note.

El paso 4 del gate revierte **todo** el cambio y pide que la suite falle. Eso atrapa el
test vacuo grosero, y deja pasar el caso fino: una implementación con cinco condiciones
donde los tests sólo verifican una. Mutar contesta la pregunta por pieza.

Cómo: por cada línea NUEVA o MODIFICADA de un archivo Python, genera variantes con un
cambio mínimo (invertir una comparación, mover un límite en uno, negar un booleano) y corre
la suite. **Un mutante que sobrevive es una línea que ningún test verifica.**

  bash scripts/gate.sh                       # el paso 4, grueso y barato
  BASE=HEAD~1 python3 scripts/mutar.py       # el fino, sobre el diff

Sale 0 si todos los mutantes mueren. Los sobrevivientes se listan con archivo y línea.
Está acotado al diff a propósito: mutar el repo entero cuesta horas y no dice nada nuevo
sobre el código que nadie tocó.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.environ.get("BASE", "HEAD~1")
SUITE = os.environ.get("SUITE", "python3 -m unittest discover -s tests -t . -q")
LIMITE = int(os.environ.get("LIMITE", "60"))   # tope de mutantes, para que no se vaya de tiempo

# Un cambio mínimo cada uno, del tipo que un test flojo no distingue.
MUTACIONES = [
    (r"(?<![<>=!])==(?!=)", "!="), (r"(?<![<>=!])!=(?!=)", "=="),
    (r"(?<![<>=!])<=(?!=)", "<"), (r"(?<![<>=!])>=(?!=)", ">"),
    (r"(?<![<>=!])<(?![=<])", "<="), (r"(?<![<>=!])>(?![=>])", ">="),
    (r"\bTrue\b", "False"), (r"\bFalse\b", "True"),
    (r"\band\b", "or"), (r"\bor\b", "and"),
    (r"\+ 1\b", "+ 2"), (r"- 1\b", "- 2"),
]


def correr(cwd):
    r = subprocess.run(SUITE, shell=True, cwd=cwd, capture_output=True, text=True)
    return r.returncode == 0


def lineas_cambiadas(archivo):
    """Números de línea nuevos o modificados respecto de BASE."""
    d = subprocess.run(["git", "diff", "-U0", BASE, "--", archivo],
                       capture_output=True, text=True).stdout
    nums = set()
    for cab in re.findall(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", d, re.M):
        ini = int(cab[0]); n = int(cab[1] or 1)
        nums.update(range(ini, ini + n))
    return nums


archivos = [a for a in subprocess.run(
    ["git", "diff", "--name-only", "--relative", BASE], capture_output=True, text=True
).stdout.split() if a.endswith(".py") and not a.startswith("tests/")]

if not archivos:
    print("  · no hay código Python cambiado que mutar")
    sys.exit(0)

if not correr("."):
    print("  ✗ la suite ya está en rojo: arreglala antes de mutar")
    sys.exit(1)

mutantes = []
for archivo in archivos:
    p = pathlib.Path(archivo)
    if not p.exists():
        continue
    lineas = p.read_text().split("\n")
    for n in sorted(lineas_cambiadas(archivo)):
        if n > len(lineas):
            continue
        linea = lineas[n - 1]
        if not linea.strip() or linea.strip().startswith("#"):
            continue
        # Sin la parte de comentario: mutar un comentario no prueba nada.
        codigo = linea.split("#")[0]
        for patron, reemplazo in MUTACIONES:
            if re.search(patron, codigo):
                mutantes.append((archivo, n, patron, reemplazo, linea))

if len(mutantes) > LIMITE:
    print(f"  · {len(mutantes)} mutantes posibles; se prueban los primeros {LIMITE} "
          f"(subí LIMITE si querés todos)")
    mutantes = mutantes[:LIMITE]

if not mutantes:
    print("  · el diff no tiene comparaciones ni booleanos que mutar")
    sys.exit(0)

sobrevivientes = []
respaldo = tempfile.mkdtemp()
for archivo, n, patron, reemplazo, linea in mutantes:
    p = pathlib.Path(archivo)
    guardado = p.read_text()
    shutil.copy(p, pathlib.Path(respaldo) / p.name)
    lineas = guardado.split("\n")
    lineas[n - 1] = re.sub(patron, reemplazo, lineas[n - 1], count=1)
    p.write_text("\n".join(lineas))
    try:
        if correr("."):      # la suite pasó CON el código mutado: nadie lo verifica
            sobrevivientes.append((archivo, n, linea.strip(), reemplazo))
    finally:
        p.write_text(guardado)
shutil.rmtree(respaldo, ignore_errors=True)

print(f"  {len(mutantes)} mutante(s) probados sobre el diff")
if sobrevivientes:
    print(f"  ✗ {len(sobrevivientes)} sobrevivieron: la suite no nota estos cambios")
    for archivo, n, texto, reemplazo in sobrevivientes[:10]:
        print(f"     {archivo}:{n}  → {reemplazo}   {texto[:60]}")
    sys.exit(1)
print("  ✓ todos los mutantes murieron: la suite distingue el código cambiado")
