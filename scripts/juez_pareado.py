#!/usr/bin/env python3
"""Línea base del juez, PAREADO y con el orden invertido.

Por qué no pointwise: está medido que juzgar generación de tests es la tarea más difícil para
un juez LLM, que **pointwise es mucho peor que pareado** —cerca de la mitad de los juicios
terminan en empate— y que **invertir el orden A/B mueve la exactitud hasta 14 puntos**
(CodeJudgeBench §5.1-§5.3). Mi primera medición de este juez fue pointwise y dio 50% de acuerdo,
exactamente lo que acierta contestar siempre lo mismo. Antes de concluir que el modelo no sabe
juzgar hay que preguntarle de la forma que el campo midió que funciona.

Acá se le muestran DOS tests de la misma familia —uno que el gate aceptó y uno que rechazó— y se
le pide elegir. Cada par se pregunta en los dos órdenes:

  · acierta     = eligió el aceptado en los dos órdenes
  · falla       = eligió el rechazado en los dos órdenes
  · inconsistente = cambió de opinión al invertir el orden; NO se cuenta como acierto, porque un
                    juez que depende del orden no está juzgando el contenido

Esa tercera categoría es la que un número agregado esconde, y es la que decide si el juez sirve
para un gate.

  python3 juez_pareado.py <reservado.jsonl> --modelo <id> [--tope N]

Y para probar el INSTRUMENTO sin plataforma: `--guion <archivo>`, una respuesta cruda por
línea, consumidas en orden. Es el mismo recurso que `_ensayo_agente.sh` —un ejecutor
determinista que no llama a ningún modelo— aplicado al juez: la contabilidad de los dos
órdenes es donde un error se esconde sin que nadie lo vea, porque un bug ahí no falla, sólo
devuelve un número mejor. Con guion la salida lo DICE, para que nadie confunda el número del
instrumento con el número de un modelo.
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import random
import re
import sys
import urllib.error
import urllib.request

PROMPT = """Sos un revisor de tests. Una tarea de software fue dada a dos agentes, y cada uno escribió un test para ella. Uno de los dos tests fue ACEPTADO por un gate que corre los tests de verdad; el otro fue RECHAZADO.

Criterios del gate: el test tiene que fallar sin la implementación y pasar con una que cumpla el contrato; tiene que distinguir el comportamiento y no sólo cubrir las líneas; si usa patch, el objetivo tiene que ser el módulo correcto según la forma del import que el enunciado declara; sólo puede tocar su archivo de test; el archivo y la clase tienen que ser los que el enunciado pide.

ENUNCIADO DE LA TAREA:
{enunciado}

TEST A:
{a}

TEST B:
{b}

¿Cuál de los dos aceptó el gate? Contestá sólo con la letra: A o B."""


def preguntar(url, clave, modelo, enunciado, a, b, tiempo=180):
    cuerpo = json.dumps({
        "model": modelo,
        "messages": [{"role": "user", "content": PROMPT.format(
            enunciado=(enunciado or "")[:4000], a=(a or "")[:4000], b=(b or "")[:4000])}],
        "max_tokens": 600, "temperature": 0,
    }).encode()
    pedido = urllib.request.Request(
        f"{url.rstrip('/')}/chat/completions", data=cuerpo,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {clave}"})
    with urllib.request.urlopen(pedido, timeout=tiempo) as r:
        d = json.loads(r.read())
    return (d["choices"][0]["message"].get("content") or "").strip()


def eleccion(cruda):
    """La ÚLTIMA letra que nombra: un modelo que razona dice «A» y «B» mientras piensa."""
    letras = re.findall(r"\b([AB])\b", cruda.upper())
    return letras[-1] if letras else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--modelo", default=os.environ.get("MODELO_JUEZ", ""))
    ap.add_argument("--tope", type=int, default=0,
                    help="muestra aleatoria de N pares, con --semilla. NO es un prefijo: "
                         "los pares están ordenados por corrida, así que cortar los "
                         "primeros mide qué campañas entraron, no qué juez es")
    ap.add_argument("--semilla", type=int, default=0,
                    help="la semilla de la muestra, para que el subconjunto se pueda repetir")
    ap.add_argument("--guion", default=None,
                    help="archivo con una respuesta cruda por línea: juez de fixture, sin modelo")
    args = ap.parse_args()
    url, clave = os.environ.get("COLABHIVE_BASE_URL", ""), os.environ.get("COLABHIVE_API_KEY", "")
    guion = None
    if args.guion:
        guion = iter(pathlib.Path(args.guion).read_text().splitlines())
    elif not url or not clave or not args.modelo:
        print("⊘ falta COLABHIVE_BASE_URL, COLABHIVE_API_KEY o --modelo: NO se midió nada.")
        return 2

    rs = [json.loads(l) for l in pathlib.Path(args.jsonl).read_text().splitlines() if l.strip()]
    rs = [r for r in rs if r.get("test") and r.get("enunciado")]
    # Los pares se arman DENTRO DE LA MISMA TAREA, no sólo de la misma corrida. Apareé por
    # corrida en la primera versión y el número salía inflado por una razón que no es juicio:
    # si el aceptado es de T01 y el rechazado de T03, el enunciado que se le muestra es el de
    # T01, y entonces el rechazado se delata solo —otra clase, otro archivo— y el juez acierta
    # notando el desajuste. Mismo enunciado para los dos tests, o el par no se usa.
    por_tarea = collections.defaultdict(lambda: {"aceptado": [], "rechazado": []})
    for r in rs:
        por_tarea[(r.get("corrida") or "x", r.get("tarea") or "?")][r["veredicto"]].append(r)
    pares, sueltos = [], 0
    for (fam, tarea), d in sorted(por_tarea.items()):
        if d["aceptado"] and d["rechazado"]:
            for bueno, malo in zip(d["aceptado"], d["rechazado"]):
                pares.append((f"{fam}/{tarea}", bueno, malo))
        else:
            sueltos += len(d["aceptado"]) + len(d["rechazado"])
    total_pares = len(pares)
    if args.tope and args.tope < total_pares:
        # Al azar y no los primeros. Los pares salen ordenados por `(corrida, tarea)`, así que
        # un prefijo es una muestra de las corridas más viejas: mediría con qué campañas se
        # armó el dataset y lo reportaría como habilidad del juez. La semilla queda en la
        # salida para que el subconjunto se pueda repetir.
        random.Random(args.semilla).shuffle(pares)
        pares = pares[:args.tope]
    if not pares:
        print("⊘ no se pudo armar ningún par aceptado/rechazado dentro de una misma TAREA.")
        print("   No es un pase: ninguna tarea del reservado tiene las dos clases. Aparear")
        print("   contra otra tarea daría número, pero mediría desajuste de enunciado.")
        return 2
    print(f"  {len(pares)} par(es) dentro de la MISMA TAREA, de {len(por_tarea)} tarea(s)")
    if len(pares) < total_pares:
        # La huella de QUÉ pares entraron, no sólo cuántos: sin esto, dos corridas con la
        # misma semilla y distinto dataset informan lo mismo y no hay cómo notarlo. Es lo
        # que hace reproducible una muestra.
        huella = hashlib.sha256("\n".join(f for f, _, _ in pares).encode()).hexdigest()[:8]
        print(f"  · muestra AL AZAR de {len(pares)} de {total_pares} pares disponibles, "
              f"semilla {args.semilla} · huella de la muestra {huella}")
    print(f"  ⊘ {sueltos} registro(s) quedaron afuera: su tarea no tiene las dos clases.\n     No se aparean contra otra tarea: eso mediría desajuste de enunciado, no juicio.")

    bien = mal = inconsistente = ilegible = 0
    for fam, bueno, malo in pares:
        res = {}
        for orden, (a, b) in (("ab", (bueno, malo)), ("ba", (malo, bueno))):
            if guion is not None:
                cruda = next(guion, "")
            else:
                try:
                    cruda = preguntar(url, clave, args.modelo, bueno["enunciado"],
                                      a["test"], b["test"])
                except (urllib.error.URLError, OSError, KeyError, ValueError):
                    res[orden] = None
                    continue
            letra = eleccion(cruda)
            if letra is None:
                res[orden] = None
            else:
                # ¿eligió el aceptado? en "ab" el aceptado es A; en "ba" es B.
                res[orden] = (letra == "A") if orden == "ab" else (letra == "B")
        if None in res.values():
            ilegible += 1
        elif res["ab"] and res["ba"]:
            bien += 1
        elif not res["ab"] and not res["ba"]:
            mal += 1
        else:
            inconsistente += 1

    n = bien + mal + inconsistente
    print(f"\n── juez SIN AFINAR, pareado y con orden invertido: {args.modelo}")
    if guion is not None:
        print("  ⊘ CON GUION: estas respuestas salieron de un archivo, no de un modelo.")
        print("     El número mide el INSTRUMENTO. No se reporta como medición de nadie.")
    print(f"  pares juzgados {n} · ilegibles {ilegible}")
    if n == 0:
        print("  ⊘ ninguna respuesta legible: NO se midió nada. No es un pase.")
        return 2
    print(f"  eligió bien en los DOS órdenes:  {bien}/{n} = {bien/n:.0%}")
    print(f"  eligió mal en los dos órdenes:   {mal}/{n} = {mal/n:.0%}")
    print(f"  cambió con el orden (inconsistente): {inconsistente}/{n} = {inconsistente/n:.0%}")
    # El azar: 50% es lo que acierta contestando al azar UNA pregunta. Esta métrica son DOS
    # —el par en los dos órdenes— así que el azar reparte 25% bien / 25% mal / 50% inconsistente.
    # Puse 50% acá la primera vez y el número quedaba leyéndose como «está en el azar» cuando
    # en realidad estaba arriba. Las dos líneas de referencia van explícitas, no de memoria.
    print(f"  ⊘ contra el azar: bien 25% · mal 25% · inconsistente 50% (dos preguntas, no una)")
    consistentes = bien + mal
    if consistentes:
        print(f"  ⊘ sólo entre los {consistentes} consistente(s): {bien}/{consistentes} ="
              f" {bien/consistentes:.0%} (azar 50%)")
    print(f"  ⊘ la inconsistencia no es ruido: un juez que depende del orden no está juzgando")
    print(f"     el contenido, y en un gate eso es un veredicto que cambia según cómo se")
    print(f"     pregunte. Para un gate, esa categoría cuenta como NO sirve, no como empate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
