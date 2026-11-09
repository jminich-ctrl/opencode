#!/usr/bin/env python3
"""Recalcula los intervalos de una medición del juez AGRUPANDO por tarea o por corrida.

  python3 ic_agrupado.py <crudo.jsonl> <banco.jsonl> [--por tarea|corrida] [--reps N]

Por qué existe. §24 a §27 informaron intervalos de Wilson sobre los 147 registros del
reservado tratándolos como independientes, y no lo son: salen de 15 tareas y 7 corridas, y dos
registros de la misma tarea comparten el enunciado. El n efectivo está más cerca de 15 que de
147, así que esos intervalos afirman una precisión que no se midió.

No es una objeción teórica: es la MISMA falla que §26 ya cobró una vez, cuando leí un control
sin poder como evidencia de ausencia. Un intervalo demasiado angosto no falla; da un número
mejor.

El crudo trae `id`, `veredicto` (la verdad del gate), `puntuacion` (la del juez) y los demás
campos; el banco aporta `tarea` y `corrida`. Nada se vuelve a preguntarle al modelo: esto se
recalcula sobre lo ya medido, que es justo para lo que el crudo se escribe.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _estadistica import bootstrap_agrupado, wilson  # noqa: E402
from juez_puntual import auc_de, coma, pct  # noqa: E402


def exactitud(g):
    return sum(1 for c in g if (c["puntuacion"] > 0) == c["ok"]) / len(g) if g else None


def tpr(g):
    ac = [c for c in g if c["ok"]]
    return sum(1 for c in ac if c["puntuacion"] > 0) / len(ac) if ac else None


def fpr(g):
    rc = [c for c in g if not c["ok"]]
    return sum(1 for c in rc if c["puntuacion"] > 0) / len(rc) if rc else None


def auc(g):
    return auc_de([(c["puntuacion"], c["ok"]) for c in g])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("crudo")
    ap.add_argument("banco")
    ap.add_argument("--por", default="tarea", choices=("tarea", "corrida"))
    ap.add_argument("--reps", type=int, default=10000)
    ap.add_argument("--semilla", type=int, default=1)
    args = ap.parse_args()

    leer = lambda p: [json.loads(l) for l in pathlib.Path(p).read_text().splitlines() if l.strip()]
    banco = {r.get("id"): r for r in leer(args.banco)}
    cs = []
    for c in leer(args.crudo):
        if c.get("puntuacion") is None or c["id"] not in banco:
            continue
        c["ok"] = c["veredicto"] == "aceptado"
        c["grupo"] = banco[c["id"]].get(args.por)
        cs.append(c)
    if not cs:
        print("⊘ ningún registro con puntuación que empalme con el banco. No es un pase.")
        return 2

    grupos = {}
    for c in cs:
        grupos.setdefault(c["grupo"], []).append(c)
    k = len(grupos)
    print(f"  {len(cs)} registro(s) juzgados · {k} grupo(s) por {args.por}")
    print(f"  tamaños: {sorted((len(v) for v in grupos.values()), reverse=True)}")
    if k < 10:
        # Declarado arriba del número y no abajo: con K chico el bootstrap de clusters toma
        # el contenido de cada cluster como FIJO, así que puede salir engañosamente angosto.
        print(f"  ⚠ sólo {k} grupos: la varianza ENTRE grupos está mal estimada y el intervalo")
        print(f"     puede salir ENGAÑOSAMENTE ANGOSTO. Indicativo, no intervalo.")

    n = len(cs)
    npos = sum(1 for c in cs if c["ok"])
    nok = sum(1 for c in cs if (c["puntuacion"] > 0) == c["ok"])
    ntp = sum(1 for c in cs if c["ok"] and c["puntuacion"] > 0)
    nfp = sum(1 for c in cs if not c["ok"] and c["puntuacion"] > 0)
    naive = {"exactitud": wilson(nok, n), "TPR": wilson(ntp, npos),
             "FPR": wilson(nfp, n - npos), "AUC": None}

    print(f"\n  {'':10} {'punto':>7}  {'Wilson (independencia)':>24}  {'agrupado por ' + args.por:>24}")
    for nombre, f in (("exactitud", exactitud), ("TPR", tpr), ("FPR", fpr), ("AUC", auc)):
        v = f(cs)
        lo, hi, desc = bootstrap_agrupado(grupos, f, reps=args.reps, semilla=args.semilla)
        w = (f"[{pct(naive[nombre][0])} – {pct(naive[nombre][1])}]" if naive[nombre] else "—")
        fmt = coma if nombre == "AUC" else pct
        print(f"  {nombre:10} {fmt(v):>7}  {w:>24}  {'[' + fmt(lo) + ' – ' + fmt(hi) + ']':>24}"
              + (f"  ⊘ {desc} rep. nulas" if desc else ""))
    print(f"\n  bootstrap percentil, {args.reps} repeticiones, semilla {args.semilla}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
