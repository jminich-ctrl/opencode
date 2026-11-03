#!/usr/bin/env python3
"""Parte el dataset de veredictos en entrenamiento y RESERVADO, por familia de tareas.

La guarda número uno contra el sobreajuste, y la que la literatura señala primero: se reserva
por PROYECTO —acá, por semilla del generador— y no por tarea. Dos variantes del mismo test no
pueden caer una de cada lado: si caen, el número de la evaluación mide memoria y no juicio.

Y lo que hace a esto verificable en vez de declarativo: al final CUENTA la fuga. Si alguna
huella de test normalizada aparece en los dos lados, sale 1 y lo dice. Una partición que no se
comprueba es una promesa.

  python3 scripts/particionar_veredictos.py <veredictos.jsonl> [--reservadas N] [--salida DIR]
"""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _estadistica import fisher_exacto_2x2

# `estado_del_enunciado` vive en `juntar_veredictos.py` y se importa en vez de copiarse: una
# regla copiada en dos lados es una regla que va a divergir, y esta decide si una evaluación
# vale. Si el import falla, el chequeo lo DICE en vez de callar el rasgo.
try:
    from juntar_veredictos import estado_del_enunciado
except Exception:
    estado_del_enunciado = None


def familia(registro):
    """La familia es la CORRIDA: cada una nace de una semilla y produce sus propias tareas.

    No la tarea (`T01b` se repite en todas las corridas) ni el brazo (mezcla semillas).
    """
    return registro.get("corrida") or registro.get("brazo") or "sin-familia"


def huella(texto):
    """Normalizando los números de grupo: `test_s1` y `test_s7` son el mismo test con otro
    número, y contarlos como distintos es la forma más fácil de creerse una variedad que no
    existe."""
    if not texto:
        return None
    return hashlib.sha256(" ".join(re.sub(r"\d+", "N", texto).split()).encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--reservadas", type=int, default=2,
                    help="cuántas familias enteras van al reservado")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--dedup", action="store_true",
                    help="una sola copia por huella de test antes de partir")
    args = ap.parse_args()

    p = pathlib.Path(args.jsonl)
    if not p.is_file():
        print(f"✗ no existe {p}")
        return 2
    registros = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    if not registros:
        print("✗ el archivo no tiene registros: no hay nada que partir")
        return 2

    # La partición por familia es NECESARIA y no suficiente. Medido el 2026-10-31: con las
    # 31 familias de hoy, 19 huellas de test aparecían en los dos lados — no porque la
    # partición estuviera mal, sino porque las familias viejas son CLONES: el generador variaba
    # una sola de sus tres capas, así que el mismo test aparece literalmente en varias semillas.
    # Con el sustrato nuevo eso baja, pero mientras conviva con el viejo hay que deduplicar, y
    # entonces el tamaño del dataset cae al número real de ejemplos distintos. Esa caída es el
    # dato, no un problema del script.
    if args.dedup:
        vistas, unicos = set(), []
        for r in registros:
            h = huella(r.get("test"))
            if h is not None and h in vistas:
                continue
            if h is not None:
                vistas.add(h)
            unicos.append(r)
        print(f"  dedup: {len(registros)} registros → {len(unicos)} con huella de test única")
        registros = unicos

    por_familia = collections.defaultdict(list)
    for r in registros:
        por_familia[familia(r)].append(r)
    familias = sorted(por_familia)
    if len(familias) <= args.reservadas:
        print(f"✗ hay {len(familias)} familia(s) y se piden {args.reservadas} reservadas: "
              f"no quedaría nada para entrenar")
        return 2

    # Determinista: las familias se ordenan por nombre y se reservan las últimas. Sin azar, para
    # que la partición de hoy sea la misma la semana que viene y el número siga comparable.
    reservadas = set(familias[-args.reservadas:])
    train = [r for r in registros if familia(r) not in reservadas]
    heldout = [r for r in registros if familia(r) in reservadas]

    hs_train = {huella(r.get("test")) for r in train} - {None}
    hs_held = {huella(r.get("test")) for r in heldout} - {None}
    fuga = hs_train & hs_held

    print(f"  familias: {len(familias)} · entrenamiento {len(familias) - len(reservadas)} · "
          f"reservado {len(reservadas)}")
    print(f"  registros: {len(train)} entrenamiento · {len(heldout)} reservado")
    for nombre, parte in (("entrenamiento", train), ("reservado", heldout)):
        ac = sum(1 for r in parte if r["veredicto"] == "aceptado")
        print(f"    {nombre:14s} aceptados {ac} · rechazados {len(parte) - ac} · "
              f"tests distintos {len({huella(r.get('test')) for r in parte} - {None})}")
    if fuga:
        print(f"  ✗ FUGA: {len(fuga)} huella(s) de test aparecen en los dos lados.")
        print("     La evaluación mediría memoria y no juicio. Hay que rehacer la partición.")
    else:
        print("  ✓ sin fuga: ninguna huella de test está en los dos lados")

    # ── Sin fuga NO es lo mismo que comparable ──
    #
    # «✓ sin fuga» era todo lo que este script decía, y lo leí como que el reservado servía
    # para evaluar. No servía. Medido el 2026-11-03 sobre la partición de 1446 registros: el
    # reservado tenía 133 de 137 enunciados con la tarea ya marcada `✅ hecha` y el
    # entrenamiento 52 de 660 — p de Fisher 2e-12—, y la tasa base de aceptación era 69%
    # contra 43%. Dos poblaciones distintas, y encima el «azar» de cualquier medición puntual
    # contra ese reservado es 69% y no 50%.
    #
    # No es un defecto de la partición por familias, que es correcta: es que agrupar por
    # familia agrupa también la procedencia —las corridas viejas parseadas traen el enunciado
    # del final, con la tarea marcada— y las puso todas de un lado. Lo que estaba mal era
    # callarlo. El número que decide una evaluación es la tasa base del conjunto contra el que
    # se evalúa, y este script la tenía y no la decía.
    #
    # Se informa SIEMPRE y no sólo cuando hay un problema: un chequeo que habla sólo al fallar
    # deja al lector sin saber si corrió.
    print("  · ¿son comparables los dos lados? (sin fuga no implica comparable)")
    ac_t = sum(1 for r in train if r["veredicto"] == "aceptado")
    ac_h = sum(1 for r in heldout if r["veredicto"] == "aceptado")
    if heldout:
        print(f"      el AZAR de una medición puntual contra este reservado es "
              f"{100 * ac_h / len(heldout):.0f}% (la clase mayoritaria), no 50%")
    rasgos = [("tasa de aceptación", ac_t, len(train) - ac_t, ac_h, len(heldout) - ac_h)]
    if estado_del_enunciado is not None:
        he_t = sum(1 for r in train if estado_del_enunciado(r) == "hecha")
        he_h = sum(1 for r in heldout if estado_del_enunciado(r) == "hecha")
        rasgos.append(("enunciado con el resultado adentro",
                       he_t, len(train) - he_t, he_h, len(heldout) - he_h))
    else:
        print("      ⊘ no pude importar estado_del_enunciado: NO chequeé la contaminación "
              "del enunciado (⊘ no es «no hay»)")
    distintas = []
    for nombre, a, b, c, d in rasgos:
        p = fisher_exacto_2x2(a, b, c, d)
        pt = 100 * a / (a + b) if a + b else 0.0
        ph = 100 * c / (c + d) if c + d else 0.0
        marca = "✗" if p < 1e-3 else "·"
        print(f"      {marca} {nombre}: entrenamiento {pt:.0f}% · reservado {ph:.0f}% "
              f"· p={p:.2g}")
        if p < 1e-3:
            distintas.append(nombre)
    if distintas:
        print(f"     ✗ los dos lados NO son la misma población en: {', '.join(distintas)}.")
        print("        Un número medido en el reservado no se puede comparar con uno medido")
        print("        en entrenamiento, y el azar no es 50%. Umbral p<0,001: con este n una")
        print("        diferencia así no la explica el muestreo.")
    else:
        print("      ✓ ningún rasgo chequeado difiere entre los dos lados (p≥0,001)")

    if args.salida:
        d = pathlib.Path(args.salida)
        d.mkdir(parents=True, exist_ok=True)
        for nombre, parte in (("entrenamiento", train), ("reservado", heldout)):
            with (d / f"{nombre}.jsonl").open("w") as f:
                for r in parte:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        (d / "familias-reservadas.txt").write_text("\n".join(sorted(reservadas)) + "\n")
        print(f"  escrito en {d}")
    return 1 if fuga else 0


if __name__ == "__main__":
    sys.exit(main())
