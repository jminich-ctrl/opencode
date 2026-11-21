#!/usr/bin/env python3
"""El gate de `escribir-tests.sh`, recalculado sobre un banco PÚBLICO (TestEval).

  python3 gate_publico.py <leetcode-py.jsonl> <tests.jsonl> [--tiempo 10] [--salida v.jsonl]

Por qué existe. §29 eligió TestEval para que un tercero pueda replicar sin nuestro gate, que
no puede correr: necesita un proyecto, un plan y un worktree. Acá los cuatro criterios se
recalculan sobre 210 problemas de LeetCode con solución de referencia, en Python puro.

Lo que NO se reimplementa: la mutación. Se importan `candidatos` y `Mutador` de `mutar.py`,
así que la réplica pública usa EL MISMO operador que nuestro gate —borrado de sentencias
primero, un mutante por línea, filtrado de nodos áridos, constantes numéricas como última
prioridad y nunca cadenas—, todo eso elegido contra los dos estudios de mutación a escala. Un
puerto que inventara sus propios operadores mediría otro gate y la comparación no diría nada.

`tests.jsonl` trae una línea por intento: {"task_title": ..., "test": "<fuente>"}. El veredicto
sale con las mismas dimensiones que §23 fijó para el nuestro: un ✓ por paso superado y un solo
✗ en el que rechazó.

El banco se baja con `scripts/bajar_testeval.py`. NO vive en /tmp: este archivo ya se perdió
una vez ahí —lo escribimos en el scratchpad, el sistema limpió /tmp, y con él se fueron el
banco y el venv—. Por eso está acá adentro y versionado.
"""
import argparse
import ast
import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mutar import Mutador, candidatos  # noqa: E402

PASOS = ("archivo_y_clase", "falla_sin_implementacion", "pasa_con_implementacion", "mutantes")


def stub_de(fuente, func):
    """La referencia con el método vaciado: misma clase, mismo nombre, sin comportamiento.

    Es el equivalente público de «el código de antes» del gate. Tiene que conservar la firma,
    porque si el test no puede ni importar, el ROJO es del andamio y no del test —y el gate
    lo contaría como «falla sin la implementación», que es un ✓ regalado—."""
    arbol = ast.parse(fuente)
    tocado = False
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and nodo.name == func:
            nodo.body = [ast.Return(value=ast.Constant(value=None))]
            tocado = True
    return (ast.unparse(ast.fix_missing_locations(arbol)) if tocado else None)


def correr_test(dirtmp, impl, test, tiempo, python=None):
    """(paso, motivo, roto). `paso` es True si la suite del item quedó VERDE.

    `roto` es True cuando pytest ni siquiera pudo RECOLECTAR —un import que falta, un
    SyntaxError—, y distinguirlo no es cosmético: la primera corrida de humo de este script
    no tenía `sortedcontainers` instalado, la referencia no importaba, y el gate informó «el
    test no pasa ni con la implementación». O sea le cobró al TEST una falla del entorno.
    Es el defecto que persigue todo MEDICION.md —ante algo que no previó, deja de mirar y
    culpa al sujeto— cometido por el instrumento que iba a medirlo.

    El timeout cuenta como NO verde, y hace falta: un mutante puede entrar en bucle infinito
    —pasó montando esto— y sin tope la corrida entera no termina. Un mutante que cuelga es un
    mutante que el test notó.
    """
    (dirtmp / "solucion.py").write_text(impl)
    (dirtmp / "test_item.py").write_text(test)
    try:
        r = subprocess.run([python or sys.executable, "-m", "pytest", "-x", "-q", "test_item.py"],
                           cwd=str(dirtmp), capture_output=True, text=True, timeout=tiempo)
        salida = (r.stdout or "") + (r.stderr or "")
        # Código 2 es «error de uso/recolección» en pytest; el texto cubre el resto.
        roto = r.returncode == 2 or "ERROR collecting" in salida or "ModuleNotFoundError" in salida
        return r.returncode == 0, salida[-400:], roto
    except subprocess.TimeoutExpired:
        return False, f"⊘ se colgó: más de {tiempo}s", False


def juzgar(item, test, tiempo=10, tope_mutantes=25, python=None):
    """(veredicto, dimensiones, motivo). Mismas dimensiones que §23."""
    dims, func = {}, item["func_name"]
    ref = item["python_solution"]

    if "Solution" not in test or func not in test:
        return "rechazado", {"archivo_y_clase": "✗"}, "el test no apunta a Solution::" + func
    dims["archivo_y_clase"] = "✓"

    stub = stub_de(ref, func)
    if stub is None:
        return "⊘", dims, f"no pude vaciar {func} en la referencia: el item no sirve de banco"

    with tempfile.TemporaryDirectory(prefix="gate-publico-") as d:
        dd = pathlib.Path(d)
        paso_stub, salida_stub, roto = correr_test(dd, stub, test, tiempo, python)
        if roto:
            # Con el método vaciado, un import roto puede ser del ENTORNO o del propio test.
            # Se decide abajo, contra la referencia: si ahí también se rompe, es el entorno.
            pass
        if paso_stub:
            dims["falla_sin_implementacion"] = "✗"
            return "rechazado", dims, "el test PASA con el método vaciado: no prueba nada"
        dims["falla_sin_implementacion"] = "✓"

        paso_ref, salida, roto_ref = correr_test(dd, ref, test, tiempo, python)
        if roto_ref and "ModuleNotFoundError: No module named 'solucion'" not in salida:
            # La referencia no se pudo ni recolectar: falta una dependencia del banco o el
            # test tiene un error de sintaxis. En los dos casos NADIE midió nada, y eso es ⊘
            # y no un rechazo. Contarlo como rechazo es inventarle un veredicto al test.
            return "⊘", dims, "no se pudo juzgar: " + salida[-160:].replace("\n", " ")
        if not paso_ref:
            dims["pasa_con_implementacion"] = "✗"
            return "rechazado", dims, "el test no pasa ni con la implementación: " + salida[-120:]
        dims["pasa_con_implementacion"] = "✓"

        # Los mutantes van ADENTRO de la rama de «pasa con la implementación», y eso no es
        # orden casual: un test que ERRORA contra todo mata todos los mutantes y el criterio
        # informaría un ✓ justo donde más miente. Nuestro gate ya lo tiene anidado así; el
        # PoC público con el que arrancó esto no, y por eso su test flojo «mató» 23 de 25.
        ruta = dd / "solucion.py"
        ruta.write_text(ref)
        todos = candidatos(ruta, set(range(1, len(ref.split("\n")) + 1)))[:tope_mutantes]
        if not todos:
            dims["mutantes"] = "⊘"
            return "⊘", dims, "la referencia no tiene nada que mutar con provecho"
        vivos = 0
        for _arch, linea, nodo, _que in todos:
            arbol = ast.parse(ref)
            objetivo = next((x for x in ast.walk(arbol)
                             if getattr(x, "lineno", None) == linea and type(x) is type(nodo)),
                            None)
            if objetivo is None:
                continue
            mutado = ast.fix_missing_locations(Mutador(objetivo).visit(arbol))
            if ast.dump(mutado) == ast.dump(ast.parse(ref)):
                continue          # un mutante que no cambia nada no es un mutante
            sobrevive, _, _ = correr_test(dd, ast.unparse(mutado), test, tiempo, python)
            vivos += 1 if sobrevive else 0
        if vivos:
            dims["mutantes"] = "✗"
            return "rechazado", dims, f"sobreviven {vivos} de {len(todos)} mutantes"
        dims["mutantes"] = "✓"
    return "aceptado", dims, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("banco")
    ap.add_argument("tests")
    ap.add_argument("--tiempo", type=int, default=10)
    ap.add_argument("--salida", default=None)
    ap.add_argument("--python", default=None,
                    help="intérprete donde correr los tests del banco. TestEval importa "
                         "`sortedcontainers`, así que va un venv y NO el python del método: "
                         "si falta, la referencia no importa y sin el guarda de arriba eso "
                         "se informaba como «el test no pasa», culpando al test del entorno")
    args = ap.parse_args()
    leer = lambda p: [json.loads(l) for l in pathlib.Path(p).read_text().splitlines() if l.strip()]
    banco = {r["task_title"]: r for r in leer(args.banco)}
    filas, cuenta = [], {"aceptado": 0, "rechazado": 0, "⊘": 0}
    for t in leer(args.tests):
        item = banco.get(t.get("task_title"))
        if item is None:
            print(f"  ⊘ {t.get('task_title')!r} no está en el banco: se declara, no se cuenta.")
            continue
        v, dims, motivo = juzgar(item, t["test"], args.tiempo, python=args.python)
        cuenta[v] = cuenta.get(v, 0) + 1
        filas.append({"task_title": t["task_title"], "veredicto": v,
                      "dimensiones": dims, "motivo": motivo, "test": t["test"]})
        print(f"  {v:10s} {t['task_title'][:46]:46s} {motivo or ''}"[:120])
    print(f"\n  {cuenta['aceptado']} aceptado(s) · {cuenta['rechazado']} rechazado(s) · "
          f"{cuenta['⊘']} ⊘ (no son rechazos: el banco no pudo juzgarlos)")
    if args.salida:
        pathlib.Path(args.salida).write_text(
            "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
