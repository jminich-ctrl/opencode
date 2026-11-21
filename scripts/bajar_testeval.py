#!/usr/bin/env python3
"""Baja el banco público de TestEval y verifica que sea EL banco, no uno parecido.

  python3 scripts/bajar_testeval.py [--destino DIR] [--venv]

Qué baja: `leetcode-py.jsonl` del repo de los autores (210 problemas de LeetCode en Python,
con enunciado, solución de referencia y `func_name`). Es el banco que §29 eligió para que un
tercero pueda replicar nuestro gate sin nuestro gate, que necesita un proyecto, un plan y un
worktree para correr. Lo consume `scripts/gate_publico.py`.

Por qué es un script y no un archivo versionado: son datos de terceros, y un descargador con
el hash clavado es tan reproducible como la copia —si el upstream cambia el archivo, esto lo
dice en vez de medir sobre otro banco sin enterarse— y además deja clara la procedencia.

Por qué existe: el 2026-11-10 el banco se bajó a mano al scratchpad de /tmp, el sistema
limpió /tmp, y rearmarlo costó una búsqueda y una verificación que no tenían por qué
repetirse. El trabajo que no está en un script hay que volver a hacerlo.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import urllib.request

URL = ("https://raw.githubusercontent.com/LLM4SoftwareTesting/TestEval/main/"
       "data/leetcode-py.jsonl")
# Clavado el 2026-11-21 contra el archivo que §29 describe (506 KB, 210 ítems). Si el
# upstream lo cambia, el hash no coincide y el script PARA: medir sobre un banco distinto
# sin saberlo convierte toda comparación con §29 en una que no dice nada.
SHA256 = "a37bcaae5fd88c978254aff5633355c7c76a324ad90b8d965f6213e522e022bf"
FILAS = 210
# Los únicos tres campos que `gate_publico.py` usa. Se verifican acá y no allá porque un
# banco incompleto tiene que fallar al bajarlo, no a las dos horas de corrida.
CAMPOS = ("task_title", "func_name", "python_solution")
# TestEval importa `sortedcontainers` en varias soluciones de referencia. Sin eso la
# referencia no importa, y el gate informaba «el test no pasa ni con la implementación»:
# le cobraba al TEST una falla del entorno. Ver el guarda de `correr_test`.
PAQUETES = ("pytest", "sortedcontainers")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default=str(
        pathlib.Path(__file__).resolve().parent.parent / "experimentos" / "crudo" / "testeval"))
    ap.add_argument("--venv", action="store_true",
                    help="además arma el venv que --python de gate_publico.py necesita")
    args = ap.parse_args()

    destino = pathlib.Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)
    banco = destino / "leetcode-py.jsonl"

    if banco.exists() and hashlib.sha256(banco.read_bytes()).hexdigest() == SHA256:
        print(f"✓ el banco ya está y es el correcto: {banco}")
    else:
        print(f"→ bajando {URL}")
        with urllib.request.urlopen(URL, timeout=120) as r:
            crudo = r.read()
        visto = hashlib.sha256(crudo).hexdigest()
        if visto != SHA256:
            sys.exit(f"✗ el archivo que sirve el upstream NO es el que §29 midió.\n"
                     f"  esperado {SHA256}\n  recibido {visto}\n"
                     f"  Si el cambio es legítimo, hay que remedir y actualizar el hash a mano:\n"
                     f"  comparar contra un banco distinto no dice nada.")
        banco.write_bytes(crudo)
        print(f"✓ {banco} ({len(crudo)} bytes)")

    filas = [json.loads(l) for l in banco.read_text().splitlines() if l.strip()]
    if len(filas) != FILAS:
        sys.exit(f"✗ {len(filas)} ítems, esperaba {FILAS}")
    faltan = sorted({c for f in filas for c in CAMPOS if c not in f})
    if faltan:
        sys.exit(f"✗ hay ítems sin los campos que el gate usa: {faltan}")
    print(f"✓ {len(filas)} ítems, todos con {', '.join(CAMPOS)}")

    if args.venv:
        v = destino / "venv"
        if not (v / "bin" / "python").exists():
            print(f"→ armando el venv en {v}")
            subprocess.run([sys.executable, "-m", "venv", str(v)], check=True)
        subprocess.run([str(v / "bin" / "python"), "-m", "pip", "-q", "install", *PAQUETES],
                       check=True)
        print(f"✓ venv listo. Usalo así:\n"
              f"  python3 scripts/gate_publico.py {banco} <tests.jsonl> --python {v}/bin/python")
    else:
        print("  (sin --venv. gate_publico.py necesita un intérprete con "
              f"{' y '.join(PAQUETES)}: corré con --venv para armarlo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
