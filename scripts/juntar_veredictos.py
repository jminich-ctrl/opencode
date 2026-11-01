#!/usr/bin/env python3
"""Junta el dataset de veredictos prefiriendo la fuente NATIVA sobre el log parseado.

Hay dos fuentes para el mismo hecho, y no son equivalentes:

  · NATIVA — `scripts/_veredicto.py` emite un registro en el momento en que el gate decide, a
    `.metricas/veredictos.jsonl` de la corrida. Es el hecho.
  · PARSEADA — `exportar_veredictos.py` reconstruye los registros leyendo el log y el worktree
    cuando la corrida ya terminó. Su propio docstring dice que es «un puente, no la vía
    definitiva». Este script es el que lo jubila para las corridas que tienen nativo.

Las dos coinciden en lo que el puente hacía bien, y eso se midió antes de confiar: sobre las 23
corridas con las dos fuentes, 814 registros contra 814, las 634 celdas
(corrida, tarea, veredicto) iguales, cero discrepancias. El puente NO inventa veredictos.

Dónde sí pierde, y por qué conviene jubilarlo:

  1. **Filtra el resultado al enunciado.** Lee el archivo de la tarea del worktree FINAL, así que
     el enunciado que guarda dice `**Estado:** ✅ hecha`: 1138 de 1335 registros parseados le
     cuentan al lector que la tarea terminó bien. Los nativos dicen `pendiente`, que es el estado
     cuando se juzgó. Para entrenar o evaluar un juez eso es contaminación en la entrada.
  2. **Colapsa textos de test distintos.** Recupera el test del archivo final, así que todos los
     intentos de una tarea quedan con el mismo texto: 360 huellas únicas contra 511 de los
     nativos en las mismas 23 corridas, y las 360 son subconjunto. Prefiriendo nativo el dataset
     pasa de 534 a 680 tests únicos sin agregar una sola corrida.

Lo que el puente sí aporta y el nativo no tiene: las 17 corridas viejas, de antes de que el
emisor existiera. Por eso esto es una fusión y no un reemplazo.

  python3 juntar_veredictos.py --nativos <dir> --parseado <jsonl> --salida <jsonl>
"""
import argparse
import collections
import json
import pathlib
import sys


def leer_nativos(directorio):
    """Un archivo por corrida, llamado como la corrida. El emisor no escribe su propio nombre
    adentro —no lo sabe— así que la corrida sale del nombre del archivo."""
    out = []
    for f in sorted(pathlib.Path(directorio).glob("*.jsonl")):
        for linea in f.read_text().splitlines():
            if not linea.strip():
                continue
            r = json.loads(linea)
            r["corrida"] = f.stem
            r["fuente"] = "nativo"
            out.append(r)
    return out


def leer_parseado(ruta):
    p = pathlib.Path(ruta)
    if not p.exists():
        return []
    return [dict(json.loads(l), fuente="parseado")
            for l in p.read_text().splitlines() if l.strip()]


def estado_del_enunciado(r):
    """`✅ hecha` en el enunciado es el resultado filtrado a la entrada. Se CUENTA, no se
    corrige: un enunciado reescrito ya no es el que el agente vio."""
    e = r.get("enunciado") or ""
    if "Estado:** ✅" in e:
        return "hecha"
    return "pendiente" if "pendiente" in e else "otro"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nativos", required=True)
    ap.add_argument("--parseado", default=None)
    ap.add_argument("--salida", required=True)
    args = ap.parse_args()

    nat = leer_nativos(args.nativos)
    par = leer_parseado(args.parseado) if args.parseado else []
    if not nat and not par:
        print("⊘ ninguna de las dos fuentes tiene registros. NO se escribió nada.")
        return 2

    con_nativo = {r["corrida"] for r in nat}
    solo_viejas = [r for r in par if r.get("corrida") not in con_nativo]
    fusion = nat + solo_viejas

    pisados = len(par) - len(solo_viejas)
    print(f"  nativos {len(nat)} de {len(con_nativo)} corrida(s)")
    print(f"  parseados {len(par)}: {len(solo_viejas)} se conservan (corridas sin nativo),"
          f" {pisados} los pisa el nativo")

    # El contraste que justifica la preferencia, contado sobre lo que se está escribiendo.
    for etiqueta, rs in (("nativo", nat), ("parseado conservado", solo_viejas)):
        if not rs:
            continue
        c = collections.Counter(estado_del_enunciado(r) for r in rs)
        fuga = c.get("hecha", 0)
        print(f"  enunciados con el resultado ya adentro · {etiqueta}: {fuga}/{len(rs)}"
              f"{'  ← contaminación en la entrada' if fuga else ''}")

    salida = pathlib.Path(args.salida)
    salida.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in fusion))
    v = collections.Counter(r.get("veredicto") for r in fusion)
    print(f"  escrito: {len(fusion)} registros · aceptados {v['aceptado']}"
          f" · rechazados {v['rechazado']} · {len({r.get('corrida') for r in fusion})} corridas")
    print(f"  con borrador descartado: {sum(1 for r in fusion if r.get('borrador_descartado'))}")
    print(f"  → {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
