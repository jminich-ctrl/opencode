#!/usr/bin/env python3
"""El juez PUNTUAL: un test suelto, y la pregunta es si el gate lo aceptaría.

Por qué existe teniendo el pareado. `juez_pareado.py` mide «de estos dos, elegí el que el gate
aceptó», que es la forma que la literatura midió que funciona mejor (CodeJudgeBench §5.1: pointwise
es bastante peor y cerca de la mitad de los juicios pointwise terminan en empate). Pero esa forma
NO se puede usar en un gate: en el gate hay un test, no un par. Un instrumento que sólo mide la
forma cómoda mide algo que no se va a poder desplegar.

Y lo que decide si un juez puntual sirve de pre-filtro no es su exactitud. Es:

    en un umbral donde casi no pierde material bueno, ¿cuánta basura deja pasar?

O sea el **FPR a TPR fijo**. Un juez con 55% de exactitud es inservible como veredicto y puede
ser muy útil como filtro, si su confianza ordena; y uno con 70% de exactitud puede no servir de
filtro si se equivoca justo en los casos de los que está seguro. Las dos cosas pasan, y la
exactitud sola no distingue.

Cómo se puntúa: se le pide VEREDICTO (ACEPTAR/RECHAZAR) y CONFIANZA (0-10), y la puntuación es
`(confianza + 1)` con signo —positiva si dijo ACEPTAR—. El `+1` es para que una confianza 0 no
caiga en el mismo número por los dos lados. Con eso el umbral 0 reproduce exactamente el veredicto
crudo del modelo, y los demás umbrales son el barrido.

Las cuatro referencias que van siempre, porque sin ellas el número se lee mejor de lo que es:

  · la TASA BASE del reservado, no 50%. Un reservado con 46% de aceptados tiene una clase
    mayoritaria que acierta 54% contestando siempre lo mismo.
  · aceptar TODO llega a TPR 100% con FPR 100%. Un FPR de 98% a TPR 95% no es un número: es
    «a ese TPR el juez no descarta nada».
  · las ilegibles aparte, nunca como rechazo. Si caen en «rechazado», un modelo que no
    contesta sale con especificidad perfecta.
  · cuántas PUNTUACIONES distintas hubo. Una AUC sobre una curva de dos puntos se imprime
    igual que una de veinte.

  python3 juez_puntual.py <reservado.jsonl> --modelo <id> [--tope N] [--semilla N]

`--guion <archivo>`, una respuesta cruda por línea, corre el instrumento sin plataforma. Es el
mismo recurso que en `juez_pareado.py` y por el mismo motivo: acá un error no falla, devuelve un
número mejor. Con guion la salida lo DICE.
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
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _estadistica import wilson  # noqa: E402

PROMPT = """Sos un revisor de tests. Un agente escribió un test para la tarea de abajo. Un gate que corre los tests de verdad lo va a ACEPTAR o RECHAZAR.

Criterios del gate: el test tiene que fallar sin la implementación y pasar con una que cumpla el contrato; tiene que distinguir el comportamiento y no sólo cubrir las líneas; si usa patch, el objetivo tiene que ser el módulo correcto según la forma del import que el enunciado declara; sólo puede tocar su archivo de test; el archivo y la clase tienen que ser los que el enunciado pide.

ENUNCIADO DE LA TAREA:
{enunciado}

TEST ESCRITO POR EL AGENTE:
{test}

¿Qué va a decidir el gate? Contestá exactamente en dos líneas:
VEREDICTO: ACEPTAR o RECHAZAR
CONFIANZA: un entero de 0 a 10"""


# 10000, y los tres números anteriores están acá porque cada uno fue un defecto.
#
# 600 fue el primero: el modelo se cortaba en `finish_reason=length` a los 600 tokens de
# razonamiento SIN haber contestado, y lo que quedaba era su propio repaso de la consigna,
# cuya última palabra es RECHAZAR. El pareado, con el mismo modelo, cierra en 395 y por eso
# nunca tocó este techo.
#
# 4000 fue el segundo, y se eligió mirando UNA muestra de humo donde el modelo cerraba en
# 611 tokens. Esa muestra eran los casos fáciles. En campo (§24) cortó el 27% del reservado,
# y el diagnóstico sobre el crudo fue que NINGUNA de las 39 cortadas había cerrado el bloque
# de razonamiento: no era el juez, era el tope.
#
# 10000 es el primero medido. Sondeo del 2026-11-03 contra entrenamiento, 40 registros al
# azar con semilla 3 y tope 16000: mediana 1423, p90 5586, máximo 6726, cero cortadas. Con
# 4000 se habrían cortado 6 de 37; con 8000, ninguna. 10000 deja 1,5x de margen sobre el
# máximo observado y cuesta sólo espera (500 s, que sólo se paga si la plataforma se cuelga).
# Y si quedara apretado, el informe AVISA: el máximo gastado sale impreso al lado del tope.
TOPE_TOKENS = 10000


def espera_para(tope):
    """Segundos de espera para un tope de `tope` tokens. El tiempo de espera NO puede quedar
    fijo cuando el tope se mueve: §24 midió ~40 tokens/s contra `1af07b1f` (147 respuestas de
    hasta 4000 tokens en 100 s cada una), así que un tope de 16000 son 400 s de generación y
    una espera de 300 convertiría el sondeo del presupuesto en un sondeo de timeouts —y una
    falla de herramienta no se distingue de «el modelo no supo» en ningún número de abajo—.

    `tope // 20` es el doble de lo medido, de margen; y nunca baja de 300, que es lo que ya
    estaba y funcionaba."""
    return max(300, tope // 20)


def preguntar(url, clave, modelo, enunciado, test, tiempo=None, tope=None):
    """Devuelve (texto, motivo_de_corte, tokens). El motivo IMPORTA: `length` significa que
    el modelo no llegó a contestar, y una respuesta cortada tiene adentro las palabras ACEPTAR y RECHAZAR
    —las de la consigna— así que cualquier parser las encuentra y devuelve un veredicto que el
    modelo nunca dio. Es la falla que tuvo este script en su primera corrida de campo: informó
    «contesta siempre rechazado» sobre seis registros donde no había contestado ninguno."""
    cuerpo = json.dumps({
        "model": modelo,
        "messages": [{"role": "user", "content": PROMPT.format(
            enunciado=(enunciado or "")[:4000], test=(test or "")[:4000])}],
        "max_tokens": tope or TOPE_TOKENS, "temperature": 0,
    }).encode()
    pedido = urllib.request.Request(
        f"{url.rstrip('/')}/chat/completions", data=cuerpo,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {clave}"})
    espera = tiempo or espera_para(tope or TOPE_TOKENS)
    with urllib.request.urlopen(pedido, timeout=espera) as r:
        d = json.loads(r.read())
    eleccion = d["choices"][0]
    # Los tokens gastados se devuelven porque sin ellos no se puede saber si el tope está
    # apretado. §24 midió con tope 4000 y 27% de las respuestas se cortaron SIN cerrar el
    # razonamiento: ninguna de las 39 emitió `</think>`. Ese 27% no es una propiedad del
    # juez, es el presupuesto, y para distinguir una cosa de la otra hay que contar.
    return ((eleccion["message"].get("content") or "").strip(),
            eleccion.get("finish_reason"),
            (d.get("usage") or {}).get("completion_tokens"))


# Códigos que valen un reintento, y los demás NO. Un 400 es un pedido mal armado: pedirlo
# tres veces no lo arregla y gasta tres esperas. Un 429 o un 5xx es la plataforma ocupada o
# una réplica arrancando en frío, y eso pasa solo.
TRANSITORIOS = (408, 409, 425, 429, 500, 502, 503, 504)


def detalle_de(e):
    """Nombre del error con su código HTTP y lo que dijo el cuerpo. `HTTPError` a secas no
    sirve: en el sondeo del 2026-11-03 tres de 40 registros se perdieron con «⊘ falla de
    herramienta: HTTPError» y no había forma de saber si fue un 429 de plataforma ocupada
    —que se reintenta— o un 400 de pedido mal armado —que no—. Un error sin nombre es
    indistinguible de «el modelo no supo» en todos los números de abajo."""
    nombre = type(e).__name__
    codigo = getattr(e, "code", None)
    cuerpo = ""
    try:
        cuerpo = (e.read() or b"").decode("utf-8", "replace")[:200].replace("\n", " ")
    except Exception:
        cuerpo = str(getattr(e, "reason", "") or "")[:200]
    return f"{nombre}{f' {codigo}' if codigo else ''}{f': {cuerpo}' if cuerpo else ''}"


def preguntar_insistiendo(url, clave, modelo, enunciado, test, tope, intentos=3, pausa=2):
    """`preguntar` con reintento acotado ante códigos transitorios.

    Devuelve (texto, motivo, tokens, reintentos, detalle). Sin esto, una plataforma ocupada
    un segundo se cobra un registro del banco: el sondeo del presupuesto perdió 7,5% de la
    muestra así. Los reintentos se CUENTAN y se declaran, porque reintentar en silencio
    cambia el denominador de la medición sin que nadie lo vea."""
    ultimo = None
    for i in range(intentos):
        try:
            texto, motivo, tokens = preguntar(url, clave, modelo, enunciado, test, tope=tope)
            return texto, motivo, tokens, i, None
        except urllib.error.HTTPError as e:
            ultimo = detalle_de(e)
            if e.code not in TRANSITORIOS:
                return None, "error", None, i, ultimo
        except (urllib.error.URLError, OSError) as e:
            ultimo = detalle_de(e)
        except (KeyError, ValueError) as e:
            # Respuesta que no tiene la forma esperada: insistir no la va a cambiar.
            return None, "error", None, i, detalle_de(e)
        if i + 1 < intentos:
            time.sleep(pausa * (i + 1))
    return None, "error", None, intentos - 1, ultimo


OPCIONES = r"\s*(?:O|OR|/|\||,\s*O)\s*(?:ACEPTAR|RECHAZAR)"


def leer(cruda):
    """(veredicto, confianza) de una respuesta cruda. `None` de veredicto es ILEGIBLE.

    El veredicto sale de la LÍNEA ETIQUETADA —«VEREDICTO: ACEPTAR»— y nunca de la última
    palabra suelta. La primera versión tomaba la última palabra, como el pareado, y eso no
    falla: devuelve un número. Un modelo que razona repasa la consigna —«User asks: VEREDICTO:
    ACEPTAR or RECHAZAR»— y ahí la última palabra es RECHAZAR, así que una respuesta cortada
    antes de contestar sale clasificada como rechazo. Pasó en campo el 2026-11-03: seis de seis
    «rechazado» sobre seis respuestas donde el modelo no había contestado nada.

    Por eso también se descarta la etiqueta seguida de la ALTERNATIVA: «VEREDICTO: ACEPTAR o
    RECHAZAR» es la consigna repetida, no una respuesta.

    Y si no hay etiqueta, se mira sólo la COLA —lo que viene después del último `</think>`, o
    los últimos 150 caracteres— y se acepta una palabra suelta sólo si está una de las dos y no
    las dos: con las dos, no se sabe cuál es la respuesta, y no saber es ⊘ y no un veredicto.

    La confianza devuelve `None` cuando no hay número legible, y el llamador lo CUENTA: rellenar
    con 5 en silencio mueve el barrido sin que nadie lo vea.
    """
    texto = (cruda or "").upper()
    candidatos = []
    for m in re.finditer(r"VEREDICTO\s*[:\-]?\s*\**(ACEPTAR|ACEPTADO|RECHAZAR|RECHAZADO)", texto):
        if re.match(OPCIONES, texto[m.end():m.end() + 24]):
            continue
        candidatos.append(m.group(1))
    if not candidatos:
        cola = texto.rsplit("</THINK>", 1)[-1][-150:]
        sueltas = set(re.findall(r"\b(ACEPTAR|ACEPTADO|RECHAZAR|RECHAZADO)\b", cola))
        familias = {s[:6] for s in sueltas}
        if len(familias) != 1:
            return None, None
        candidatos = [sueltas.pop()]
    veredicto = "aceptado" if candidatos[-1].startswith("ACEPTA") else "rechazado"
    m = re.findall(r"CONFIANZA\D{0,4}(\d{1,2})", texto)
    if not m:
        m = re.findall(r"\b(\d{1,2})\s*/\s*10\b", texto)
    conf = None
    if m:
        v = int(m[-1])
        if 0 <= v <= 10:
            conf = v
    return veredicto, conf


def pct(x):
    return f"{round(x * 100)}%"


def coma(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def barrido(puntos):
    """[(puntuación, es_aceptado)] → lista de (umbral, tpr, fpr, tp, fp) de mayor a menor umbral.

    La regla del umbral es `aceptar si puntuación >= umbral`. Los umbrales candidatos son las
    puntuaciones observadas más una arriba del máximo, que es el punto «rechazar todo».
    """
    pos = [p for p, ok in puntos if ok]
    neg = [p for p, ok in puntos if not ok]
    if not pos or not neg:
        return []
    umbrales = sorted({p for p, _ in puntos}, reverse=True)
    filas = [(umbrales[0] + 1, 0.0, 0.0, 0, 0)]
    for u in umbrales:
        tp = sum(1 for p in pos if p >= u)
        fp = sum(1 for p in neg if p >= u)
        filas.append((u, tp / len(pos), fp / len(neg), tp, fp))
    return filas


def auc_de(puntos):
    """AUC por Mann-Whitney, contando los empates como medio par. Sin empates explícitos una
    AUC de un juez que contesta siempre la misma puntuación sale 0 o 1 según cómo se ordene."""
    pos = [p for p, ok in puntos if ok]
    neg = [p for p, ok in puntos if not ok]
    if not pos or not neg:
        return None
    suma = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg)
    return suma / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--modelo", default=os.environ.get("MODELO_JUEZ", ""))
    ap.add_argument("--tope", type=int, default=0,
                    help="muestra AL AZAR de N registros, con --semilla. No es un prefijo: "
                         "los registros vienen ordenados por corrida")
    ap.add_argument("--semilla", type=int, default=0)
    ap.add_argument("--guion", default=None,
                    help="archivo con una respuesta cruda por línea: juez de fixture, sin "
                         "modelo. Un `\\n` literal en la línea se convierte en salto: una "
                         "respuesta de verdad tiene varias líneas, y un fixture que no pueda "
                         "representarla no puede reproducir la falla que importa")
    ap.add_argument("--tokens", type=int, default=TOPE_TOKENS,
                    help=f"tope de tokens por respuesta (por omisión {TOPE_TOKENS}). NO es "
                         f"el tamaño de la muestra, eso es --tope. Subirlo es lo único que "
                         f"puede bajar el porcentaje de respuestas que no llegan a contestar")
    ap.add_argument("--crudo", default=None,
                    help="archivo donde dejar una línea jsonl por registro juzgado, para poder "
                         "volver a calcular cualquier número de abajo sin volver a preguntar")
    args = ap.parse_args()
    url, clave = os.environ.get("COLABHIVE_BASE_URL", ""), os.environ.get("COLABHIVE_API_KEY", "")
    guion = None
    if args.guion:
        # El `\\n` literal pasa a salto de línea. Sin esto el fixture sólo puede escribir
        # respuestas de una línea, y la falla que hubo que arreglar acá —una respuesta de
        # varias líneas donde el veredicto está en la última— no se puede reproducir.
        # Se lee PEREZOSO, línea por línea y no de un saque. Que el guion pueda ser una
        # tubería con nombre es lo que permite probar que el crudo se escribe A MEDIDA: el
        # test le da dos respuestas, mira el crudo, y recién después le da el resto.
        guion = iter(l.rstrip("\n").replace("\\n", "\n")
                     for l in open(args.guion, encoding="utf-8"))
    elif not url or not clave or not args.modelo:
        print("⊘ falta COLABHIVE_BASE_URL, COLABHIVE_API_KEY o --modelo: NO se midió nada.")
        return 2

    todos = [json.loads(l) for l in pathlib.Path(args.jsonl).read_text().splitlines() if l.strip()]
    rs = [r for r in todos if r.get("test") and r.get("enunciado")
          and r.get("veredicto") in ("aceptado", "rechazado")]
    afuera = len(todos) - len(rs)
    if not rs:
        print("⊘ ningún registro con test, enunciado y veredicto. No es un pase.")
        return 2
    total = len(rs)
    if args.tope and args.tope < total:
        random.Random(args.semilla).shuffle(rs)
        rs = rs[:args.tope]

    base = sum(1 for r in rs if r["veredicto"] == "aceptado")
    print(f"  {len(rs)} registro(s) del reservado · {base} aceptado(s) / {len(rs) - base} "
          f"rechazado(s)")
    if afuera:
        print(f"  ⊘ {afuera} registro(s) quedaron afuera: sin test, sin enunciado o sin veredicto."
              f"\n     Se declaran para que un n chico no se confunda con un reservado chico.")
    if len(rs) < total:
        huella = hashlib.sha256("\n".join(str(r.get("id")) for r in rs).encode()).hexdigest()[:8]
        print(f"  · muestra AL AZAR de {len(rs)} de {total}, semilla {args.semilla} · "
              f"huella {huella}")

    # El crudo se escribe A MEDIDA, no al final. Antes se armaba una lista y se volcaba
    # recién al terminar: una corrida de dos horas que muriera en el registro 140 dejaba
    # CERO respuestas en disco —140 llamadas al modelo pagadas y perdidas— y mientras corría
    # no había NINGUNA señal de avance. `wc -l` del crudo es esa señal.
    salida = open(args.crudo, "w", encoding="utf-8") if args.crudo else None

    def anotar(c):
        if salida is None:
            return
        salida.write(json.dumps(c, ensure_ascii=False) + "\n")
        salida.flush()

    puntos = []
    ilegibles = sin_confianza = cortadas = fallas = reintentos = 0
    veredictos = []
    gastados, detalles = [], []
    for r in rs:
        corte = tokens = detalle = None
        if guion is not None:
            cruda = next(guion, "")
        else:
            cruda, corte, tokens, veces, detalle = preguntar_insistiendo(
                url, clave, args.modelo, r["enunciado"], r["test"], args.tokens)
            reintentos += veces
            if corte == "error":
                cruda = f"⊘ falla de herramienta: {detalle}"
                fallas += 1
                detalles.append(detalle)
        dijo, conf = leer(cruda)
        if corte == "length":
            # El modelo no llegó a contestar. No se parsea: adentro de una respuesta cortada
            # están las palabras de la consigna, y cualquier parser devuelve un veredicto que
            # nadie dio. ⊘ no es «rechazado».
            cortadas += 1
            dijo = None
        if dijo is None:
            ilegibles += 1
            anotar({"id": r.get("id"), "veredicto": r["veredicto"], "dijo": None,
                    "confianza": None, "corte": corte, "tokens": tokens,
                    "detalle": detalle, "cruda": cruda[-600:]})
            continue
        if conf is None:
            sin_confianza += 1
            conf = 5
        punt = (conf + 1) * (1 if dijo == "aceptado" else -1)
        puntos.append((punt, r["veredicto"] == "aceptado"))
        veredictos.append(dijo)
        if tokens is not None:
            gastados.append(tokens)
        anotar({"id": r.get("id"), "veredicto": r["veredicto"], "dijo": dijo,
                "confianza": conf, "puntuacion": punt, "corte": corte, "tokens": tokens,
                "detalle": detalle, "cruda": cruda[-600:]})
    if salida is not None:
        salida.close()

    n = len(puntos)
    print(f"\n── juez PUNTUAL, sin afinar: {args.modelo or '(guion)'}")
    if guion is not None:
        print("  ⊘ CON GUION: estas respuestas salieron de un archivo, no de un modelo.")
        print("     El número mide el INSTRUMENTO. No se reporta como medición de nadie.")
    print(f"  juzgados {n} · ilegibles {ilegibles} (no cuentan como rechazo: si cayeran ahí,")
    print(f"     un modelo que no contesta nada saldría con especificidad perfecta)")
    if cortadas:
        # args.tokens y NO TOPE_TOKENS: informar la constante en vez del tope que se usó
        # haría que una corrida con --tokens mintiera sobre su propio presupuesto.
        print(f"  ⊘ {cortadas} de esas ilegibles se cortaron por el tope de"
              f" {args.tokens} tokens:\n     el modelo no llegó a contestar, y una respuesta"
              f" cortada NO se parsea.")
    if gastados:
        # Sin esto no se puede distinguir «el juez no sabe» de «no le alcanzó el
        # presupuesto». §24 informó 27% de cortadas sin poder decir cuánto faltaba.
        techo, medio = max(gastados), sorted(gastados)[len(gastados) // 2]
        print(f"  ⊘ presupuesto: tope {args.tokens} tokens. De las que CONTESTARON, la que"
              f" más gastó\n     usó {techo} ({100 * techo // args.tokens}% del tope), mediana"
              f" {medio}.")
        if techo >= 0.9 * args.tokens:
            print(f"     ⚠ el máximo ROZA el tope: el número de abajo está limitado por el"
                  f"\n       presupuesto y no por el juez. Subir --tokens y volver a medir.")
    if fallas:
        resumen = ", ".join(f"{k} ×{v}" for k, v in
                            collections.Counter(detalles).most_common(3))
        print(f"  ⊘ {fallas} falla(s) de herramienta: tampoco cuentan como veredicto."
              f"\n     {resumen}")
    if reintentos:
        # Declarado porque reintentar en silencio cambia el denominador sin que nadie lo vea.
        print(f"  ⊘ {reintentos} reintento(s) por códigos transitorios: la plataforma falló"
              f"\n     y se insistió. Lo que se informa abajo incluye esos registros.")
    if sin_confianza:
        print(f"  ⊘ {sin_confianza} respuesta(s) sin confianza legible: se les puso 5 por"
              f" omisión.\n     Se declara porque rellenar en silencio mueve el barrido.")
    if n == 0:
        print("  ⊘ ninguna respuesta legible: NO se midió nada. No es un pase.")
        return 2

    pos = [p for p, ok in puntos if ok]
    neg = [p for p, ok in puntos if not ok]
    tasa = len(pos) / n
    mayor = max(tasa, 1 - tasa)
    etiqueta = "aceptar siempre" if tasa >= 0.5 else "rechazar siempre"
    print(f"  ⊘ la tasa base de ESTE reservado es {pct(tasa)} de aceptados ({len(pos)}/{n}).")
    print(f"     La referencia de un juicio puntual es la clase mayoritaria —{etiqueta},"
          f" {pct(mayor)}—,\n     no 50%: una exactitud por debajo de {pct(mayor)} es peor que"
          f" contestar siempre lo mismo.")

    if len(set(veredictos)) == 1:
        print(f"  ⊘ el modelo contesta siempre lo mismo ({veredictos[0]}) en los {n} registros."
              f"\n     Lo que siga es la contabilidad de un constante, no de un juez.")

    # Punto de operación crudo: umbral 0, que por el `+1` del signo es exactamente su veredicto.
    tp = sum(1 for p in pos if p > 0)
    fp = sum(1 for p in neg if p > 0)
    aciertos = tp + (len(neg) - fp)
    print(f"\n  punto de operación tal como contesta el modelo (umbral 0):")
    print(f"    exactitud {aciertos}/{n} = {pct(aciertos / n)}   ·   clase mayoritaria"
          f" ({etiqueta}) {pct(mayor)}")
    if neg:
        lo, hi = wilson(fp, len(neg))
        print(f"    TPR {pct(tp / len(pos))} ({tp}/{len(pos)} aceptados conservados)   ·   "
              f"FPR {pct(fp / len(neg))} ({fp}/{len(neg)} rechazados que pasarían)"
              f" [IC95 {pct(lo)}–{pct(hi)}]")
    else:
        print(f"    TPR {pct(tp / len(pos))} ({tp}/{len(pos)})   ·   FPR — : no hay ningún"
              f" rechazado legible, así que el FPR no existe (no es 0%)")

    filas = barrido(puntos)
    distintas = len({p for p, _ in puntos})
    plural = "puntuaciones distintas" if distintas != 1 else "puntuación distinta"
    print(f"\n  barrido de umbral sobre la confianza: {distintas} {plural}")
    if distintas <= 1:
        print("    ⊘ con una sola puntuación no hay curva que leer: el barrido tiene dos puntos")
        print("       —aceptar todo y rechazar todo— y una AUC de eso no dice nada del juez.")
    if not filas:
        print("    ⊘ falta una de las dos clases entre lo legible: sin rechazados no hay FPR y")
        print("       sin aceptados no hay TPR. El barrido no se puede hacer.")
        return 0
    auc = auc_de(puntos)
    print(f"    AUC {coma(auc)}  (0,50 = no ordena; empates contados como medio par)")
    for objetivo in (0.90, 0.95, 1.00):
        candidatas = [f for f in filas if f[1] >= objetivo - 1e-9]
        if not candidatas:
            print(f"    FPR a TPR≥{coma(objetivo)}: — ningún umbral alcanza ese TPR")
            continue
        u, tpr, fpr, _tp, fpr_n = min(candidatas, key=lambda f: (f[2], -f[1]))
        lo, hi = wilson(fpr_n, len(neg))
        cola = ""
        if fpr >= 1 - 1e-9:
            cola = "  ← no descarta nada: a ese TPR el único umbral es aceptar todo"
        print(f"    FPR a TPR≥{coma(objetivo)}: {pct(fpr)} ({fpr_n}/{len(neg)})"
              f" [IC95 {pct(lo)}–{pct(hi)}] con umbral {u}, TPR real {pct(tpr)}{cola}")
    print(f"  ⊘ para leer el FPR: aceptar TODO da TPR 100% y FPR 100%, sin juez ninguno. El")
    print(f"     juez aporta en la medida en que su FPR baje de 100% al TPR que uno exija.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
