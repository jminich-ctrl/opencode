#!/usr/bin/env python3
"""Muta el gate mecánicamente y mide qué fracción de los mutantes mata la suite.

    python3 pruebas/mutar-gate.py [--n 16] [--semilla 7] [--solo-generar DIR]

Por qué este y no otra ronda de siembra a mano: la suite de `test_metodo.py` tiene un caso
por cada bug que tuvimos, así que **todo verde mide el sesgo de la suite**. Una ronda
sembrada por alguien que ya leyó la tabla de fallas hereda el mismo sesgo. Un mutador
mecánico no sabe nada de nuestra lista: las fallas que inventa son las que la gramática
del bash permite, no las que nosotros ya sabemos cometer. Es la única fuente de fallas
independiente que podemos conseguir sin otra persona.

Las reglas de la literatura que respetamos:

· **Un mutante por línea.** Google, 16.9M mutantes: mutar cada punto posible produce una
  avalancha que nadie mira. Uno por línea mantiene la señal legible.
· **Nodos áridos.** Un operador cuya mutación no puede cambiar la conducta observable es
  improductivo: comentarios, `echo` de ayuda, `set -u`. No se mutan.
· **El 68% de los mutantes productivos de Google eran SBR** (reemplazar una sentencia por
  un `pass`): borrar un chequeo entero es la mutación más informativa, y acá es literal —
  si borro este chequeo, ¿alguien se entera?

Lo que sale es la tasa de captura del gate. Lo que importa no es que sea alta: es saberlo.
Un mutante que sobrevive es un chequeo que el gate hace y la suite no mira — o un chequeo
que el gate cree que hace y no hace.
"""
import argparse
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent
GATE = RAIZ / "plantillas" / "gate.sh"
SUITE = AQUI / "test_metodo.py"

# (patrón, reemplazo, nombre de la clase de mutación)
REGLAS = [
    (r'\[ -n ', '[ -z ', 'vacío↔no vacío'),
    (r'\[ -z ', '[ -n ', 'no vacío↔vacío'),
    (r'if ! ', 'if ', 'quita la negación'),
    (r'grep -qE', 'grep -qvE', 'invierte el grep'),
    (r'grep -q ', 'grep -qv ', 'invierte el grep'),
    (r'-gt 0', '-ge 0', 'corre el umbral'),
    (r'\brojo "', 'verde "', 'el fallo pasa a pase'),
    (r'\bvacuo "', 'verde "', '⊘ pasa a ✓'),
    (r'exit 1', 'exit 0', 'el rojo sale 0'),
    (r' \|\| true', '', 'quita el || true'),
    (r'--relative', '', 'rutas desde la raíz del repo'),
    (r'\bsort -u\b', 'sort', 'sin deduplicar'),
    (r'head -1', 'tail -1', 'otra línea'),
    (r'FALLOS\+1', 'FALLOS+0', 'no cuenta el fallo'),
    (r'VACIOS\+1', 'VACIOS+0', 'no cuenta el vacío'),
]

# Árido: mutar acá no puede cambiar ningún veredicto observable.
def arido(linea):
    s = linea.strip()
    if not s or s.startswith("#"):
        return True
    if s.startswith("set ") or s.startswith("export PS4"):
        return True
    # Un `echo` de encabezado no decide nada; un `echo` que la suite inspecciona, sí, pero
    # esos los cubre la regla de borrado de sentencia, no las reglas de operador.
    return False


def candidatos(fuente):
    """Un mutante por línea: la primera regla que aplica, y listo."""
    salida = []
    for i, linea in enumerate(fuente):
        if arido(linea):
            continue
        for patron, reemplazo, nombre in REGLAS:
            if re.search(patron, linea):
                nueva = re.sub(patron, reemplazo, linea, count=1)
                if nueva != linea:
                    salida.append((i, nueva, nombre))
                break
    # SBR: borrar la sentencia entera. La mutación más informativa de las 16.9M de Google.
    for i, linea in enumerate(fuente):
        s = linea.strip()
        if arido(linea):
            continue
        if s.startswith(("rojo ", "verde ", "vacuo ", "testigo ")):
            salida.append((i, "", "borra el chequeo (SBR)"))
    return salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16, help="cuántos mutantes correr")
    ap.add_argument("--semilla", type=int, default=7, help="para que la medición se repita")
    ap.add_argument("--solo-generar", help="escribe los mutantes en DIR y no corre nada")
    args = ap.parse_args()

    fuente = GATE.read_text().splitlines(keepends=True)
    todos = candidatos(fuente)
    random.Random(args.semilla).shuffle(todos)
    elegidos = todos[: args.n]
    print(f"candidatos: {len(todos)} — se corren {len(elegidos)} (semilla {args.semilla})")

    if args.solo_generar:
        d = pathlib.Path(args.solo_generar)
        d.mkdir(parents=True, exist_ok=True)
        for k, (i, nueva, nombre) in enumerate(elegidos, 1):
            m = list(fuente)
            m[i] = nueva
            (d / f"variante-{k:02d}.sh").write_text("".join(m))
        print(f"escritos en {d}")
        return 0

    respaldo = pathlib.Path(tempfile.mkdtemp()) / "gate.sh"
    shutil.copy(GATE, respaldo)
    muertos, vivos = 0, []
    try:
        for k, (i, nueva, nombre) in enumerate(elegidos, 1):
            m = list(fuente)
            m[i] = nueva
            GATE.write_text("".join(m))
            etiqueta = f"linea {i+1}: {nombre}"
            if subprocess.run([sys.executable, str(SUITE)],
                              capture_output=True).returncode != 0:
                print(f"  ✓ mutante {k:02d} muerto — {etiqueta}")
                muertos += 1
            else:
                print(f"  ✗ mutante {k:02d} SOBREVIVIÓ — {etiqueta}")
                print(f"       {fuente[i].strip()[:100]}")
                print(f"    →  {nueva.strip()[:100] or '(borrada)'}")
                vivos.append((i + 1, nombre))
    finally:
        shutil.copy(respaldo, GATE)

    print()
    print(f"Tasa de captura del gate: {muertos} de {len(elegidos)}")
    if vivos:
        print("Sobrevivieron:")
        for ln, nombre in vivos:
            print(f"  · gate.sh:{ln} — {nombre}")
        print()
        print("Cada sobreviviente es una de dos cosas, y hay que decidir cuál:")
        print("  · un chequeo que el gate hace y la suite no mira → falta el caso")
        print("  · un chequeo que no cambia ningún veredicto → es árido, y sobra en el gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
