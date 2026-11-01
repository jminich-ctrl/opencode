#!/usr/bin/env python3
"""Los dos controles del juez pareado. Sin ellos, el número de acierto no se puede leer.

El juez pareado mide «eligió el test que el gate aceptó». Ese número se puede ganar por tres
razones, y sólo una es juicio:

  1. juzgando la calidad del test            ← la que queremos
  2. prefiriendo una posición                ← sesgo posicional; CodeJudgeBench midió 14 puntos
  3. notando rasgos de superficie del test   ← sin mirar el enunciado para nada

Cada control apaga una vía y deja las otras:

  --posicion   el MISMO test en las dos posiciones. No hay nada que juzgar: cualquier cosa que
               no sea mitad y mitad es preferencia por una posición. Un juez sano acá queda
               indeciso o reparte; si contesta siempre «A», su acierto de la medición principal
               vale lo que valga su suerte de haber puesto al bueno en A.

  --enunciado-ajeno   el par verdadero, pero con el enunciado de OTRA tarea. Si el acierto no
               se cae, el juez no está usando el enunciado: está puntuando el test por su forma,
               y entonces no mide cumplimiento del contrato, que es lo que el gate decide.

Un control que sale como se espera no es un trámite: es lo que permite leer el número de al lado.

  python3 juez_controles.py <reservado.jsonl> --modelo <id> [--posicion|--enunciado-ajeno] [--tope N]

`--guion <archivo>` corre con respuestas de archivo en vez de modelo, igual que en
`juez_pareado.py`: sirve para probar que el control DETECTA lo que dice detectar. Un control
que nunca se vio salir mal no es un control, es una decoración.
"""
import argparse
import collections
import json
import os
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from juez_pareado import eleccion, preguntar  # noqa: E402  el mismo prompt y el mismo parser


def pares_de(rs):
    por_tarea = collections.defaultdict(lambda: {"aceptado": [], "rechazado": []})
    for r in rs:
        por_tarea[(r.get("corrida") or "x", r.get("tarea") or "?")][r["veredicto"]].append(r)
    out = []
    for clave, d in sorted(por_tarea.items()):
        for bueno, malo in zip(d["aceptado"], d["rechazado"]):
            out.append((clave, bueno, malo))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--modelo", default=os.environ.get("MODELO_JUEZ", ""))
    ap.add_argument("--tope", type=int, default=0)
    ap.add_argument("--posicion", action="store_true")
    ap.add_argument("--enunciado-ajeno", action="store_true", dest="ajeno")
    ap.add_argument("--guion", default=None,
                    help="archivo con una respuesta cruda por línea: control de fixture, sin modelo")
    args = ap.parse_args()
    url, clave = os.environ.get("COLABHIVE_BASE_URL", ""), os.environ.get("COLABHIVE_API_KEY", "")
    guion = iter(pathlib.Path(args.guion).read_text().splitlines()) if args.guion else None
    if not (args.posicion or args.ajeno):
        print("⊘ no se eligió control (--posicion o --enunciado-ajeno). NO se midió nada.")
        return 2
    if guion is None and (not url or not clave or not args.modelo):
        print("⊘ falta base/clave/--modelo, o no se eligió control. NO se midió nada.")
        return 2

    rs = [json.loads(l) for l in pathlib.Path(args.jsonl).read_text().splitlines() if l.strip()]
    rs = [r for r in rs if r.get("test") and r.get("enunciado")]
    pares = pares_de(rs)
    if args.tope:
        pares = pares[:args.tope]
    if not pares:
        print("⊘ no se pudo armar ningún par dentro de una misma tarea. No es un pase.")
        return 2

    if args.posicion:
        # El mismo test en A y en B. No hay respuesta correcta: sólo posición.
        eligio_a = eligio_b = ilegible = 0
        for _clave_tarea, bueno, _ in pares:
            if guion is not None:
                cruda = next(guion, "")
            else:
                try:
                    cruda = preguntar(url, clave, args.modelo,
                                      bueno["enunciado"], bueno["test"], bueno["test"])
                except Exception:
                    ilegible += 1
                    continue
            letra = eleccion(cruda)
            if letra == "A":
                eligio_a += 1
            elif letra == "B":
                eligio_b += 1
            else:
                ilegible += 1
        n = eligio_a + eligio_b
        if guion is not None:
            print("  ⊘ CON GUION: respuestas de archivo. Mide el instrumento, no a un modelo.")
        print(f"  CONTROL DE POSICIÓN · el mismo test en las dos posiciones, {len(pares)} intento(s)")
        print(f"    eligió A: {eligio_a}   ·   eligió B: {eligio_b}   ·   ilegible: {ilegible}")
        if n == 0:
            print("    ⊘ ninguna respuesta legible: el control no midió nada.")
            return 2
        sesgo = abs(eligio_a - eligio_b) / n
        print(f"    desbalance: {sesgo:.0%}  (0% = sin preferencia de posición)")
        print("    → fuerte preferencia por una posición: el acierto de la medición principal"
              if sesgo >= 0.6 else
              "    → sin preferencia marcada de posición: la medición principal se puede leer")
        if sesgo >= 0.6:
            print("       queda contaminado y hay que leerlo sólo en la categoría «inconsistente».")
        return 0

    # --enunciado-ajeno: el par verdadero con el enunciado de otra tarea.
    rnd = random.Random(20261031)
    bien = mal = inconsistente = ilegible = 0
    for i, (_clave_tarea, bueno, malo) in enumerate(pares):
        otros = [p for j, p in enumerate(pares) if j != i
                 and p[1]["enunciado"].strip() != bueno["enunciado"].strip()]
        if not otros:
            ilegible += 1
            continue
        ajeno = rnd.choice(otros)[1]["enunciado"]
        res = {}
        for orden, (a, b) in (("ab", (bueno, malo)), ("ba", (malo, bueno))):
            if guion is not None:
                cruda = next(guion, "")
            else:
                try:
                    cruda = preguntar(url, clave, args.modelo, ajeno, a["test"], b["test"])
                except Exception:
                    res[orden] = None
                    continue
            letra = eleccion(cruda)
            res[orden] = None if letra is None else ((letra == "A") if orden == "ab" else (letra == "B"))
        if None in res.values():
            ilegible += 1
        elif res["ab"] and res["ba"]:
            bien += 1
        elif not res["ab"] and not res["ba"]:
            mal += 1
        else:
            inconsistente += 1
    n = bien + mal + inconsistente
    if guion is not None:
        print("  ⊘ CON GUION: respuestas de archivo. Mide el instrumento, no a un modelo.")
    print(f"  CONTROL DE ENUNCIADO AJENO · el par verdadero con el enunciado de otra tarea")
    print(f"    pares: {len(pares)}  ·  legibles: {n}  ·  ilegible/sin par: {ilegible}")
    print(f"    acertó en los dos órdenes: {bien}   ·   falló en los dos: {mal}"
          f"   ·   cambió con el orden: {inconsistente}")
    if n:
        print(f"    acierto con enunciado ajeno: {bien}/{n} ({bien / n:.0%})")
        print("    Para leerlo: compararlo contra el acierto de `juez_pareado.py` sobre los"
              " MISMOS pares.\n    Si no baja, el juez no usa el enunciado y no está midiendo"
              " cumplimiento del contrato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
