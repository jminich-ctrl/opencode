#!/usr/bin/env python3
"""Cuánto del contexto que un modelo DECLARA puede usar de verdad.

    COLABHIVE_BASE_URL=... python3 scripts/medir-ventana.py [id|@papel ...]

Sin argumentos mide los modelos que la corrida va a usar. Para cada uno arma un prompt con
relleno y una AGUJA —un dato único— a varias profundidades, y pregunta por la aguja.

POR QUÉ. El monitoreo cruza el contexto DECLARADO contra el SERVIDO (`max_model_len`), y las
dos cifras pueden coincidir mientras el modelo no pueda recuperar nada del medio del prompt.
Udgam Labs lo midió en su propio modelo: la recuperación a 3.500 tokens pasó del 1% al 83%
después de preentrenar en ventana larga — con el mismo tamaño declarado antes y después. O
sea que «declara 32000» no dice nada sobre si a los 20000 ve algo.

Para este método importa más que para un chat: los prompts que mandamos son el enunciado más
AGENTS.md más los archivos que la tarea nombra, y si el modelo no recupera del medio, lo que
se degrada en silencio es el ENUNCIADO — y el veredicto que salga va a nombrar a la tarea.

TEMPERATURA 0, que es lo que hace esto reproducible. Medido hoy: sin fijarla, cinco llamadas
al mismo prompt daban dos respuestas distintas. Esta medición no tendría sentido antes de eso.

LO QUE NO MIDE: una aguja recuperada no es comprensión. Esto mide el piso —si no encuentra un
dato literal, tampoco va a seguir una instrucción que esté ahí— y nada más que eso.
"""
import json, os, pathlib, subprocess, sys, time

AQUI = pathlib.Path(__file__).resolve().parent
# ~4 caracteres por token es la regla gruesa habitual. Se informa el tamaño en CARACTERES
# además del estimado, porque el estimado es nuestro y el real lo sabe el tokenizador.
CHARS_POR_TOKEN = 4
RELLENO = ("El plan se corre por etapas y cada tarea tiene su propio gate. "
           "Los veredictos se miden, no se suponen. ")
# Techo de tokens por omisión: el 27B declara 117000 y un prompt al 90% de eso es enorme.
# Se mide hasta acá salvo que alguien suba el techo a propósito.
TECHO = int(os.environ.get("TECHO_TOKENS", "24000"))
PROFUNDIDADES = [float(x) for x in os.environ.get("PROFUNDIDADES", "0.25,0.5,0.9").split(",")]
AGUJA_CLAVE = "El código de la bitácora de Rosario es"
AGUJA_VALOR = "7314-QX"


def declarado(modelo: str) -> int:
    cfg = pathlib.Path(os.environ.get("CONFIG_OC",
                                      os.path.expanduser("~/.config/opencode/opencode.json")))
    try:
        datos = json.loads(cfg.read_text())
    except Exception:
        return 0
    for prov in (datos.get("provider") or {}).values():
        m = (prov.get("models") or {}).get(modelo)
        if m:
            lim = (m.get("limit") or {}).get("context") or m.get("context") or 0
            try:
                return int(lim)
            except (TypeError, ValueError):
                return 0
    return 0


def prompt_con_aguja(tokens: int, fraccion: float) -> str:
    """Relleno de `tokens` estimados con la aguja insertada a `fraccion` del camino."""
    total = tokens * CHARS_POR_TOKEN
    cuerpo = (RELLENO * (total // len(RELLENO) + 1))[:total]
    corte = int(len(cuerpo) * fraccion)
    aguja = f"\n\n{AGUJA_CLAVE} {AGUJA_VALOR}.\n\n"
    return (cuerpo[:corte] + aguja + cuerpo[corte:]
            + f"\n\nRespondé SOLO con el código que aparece después de «{AGUJA_CLAVE}». "
              "Sin explicación.")


def preguntar(modelo: str, texto: str, paciencia: str):
    t0 = time.time()
    r = subprocess.run([sys.executable, str(AQUI / "pedir.py"), modelo],
                       input=texto, capture_output=True, text=True,
                       env=dict(os.environ, PACIENCIA=paciencia, TEMPERATURA="0"))
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip(), time.time() - t0


def main() -> int:
    if not os.environ.get("COLABHIVE_BASE_URL"):
        print("⊘ sin COLABHIVE_BASE_URL no hay nada que medir", file=sys.stderr)
        return 2
    pedidos = sys.argv[1:]
    if not pedidos:
        salida = subprocess.run(["bash", "-c",
                                 f'. "{AQUI}/_comun.sh" >/dev/null 2>&1; modelos_de_la_corrida'],
                                capture_output=True, text=True).stdout
        pedidos = [l.split()[0] for l in salida.splitlines() if l.strip()]
    if not pedidos:
        print("⊘ no pude saber qué modelos medir", file=sys.stderr)
        return 2

    print(f"ventana usable · techo {TECHO} tokens estimados · temperatura 0")
    peor = {}
    for modelo in pedidos:
        dec = declarado(modelo)
        tope = min(dec, TECHO) if dec else TECHO
        print(f"\n  {modelo}  declara {dec or '?'} · se mide hasta {tope}")
        for frac in PROFUNDIDADES:
            tokens = max(200, int(tope * 0.9))
            texto = prompt_con_aguja(tokens, frac)
            rc, out, err, dt = preguntar(modelo, texto, "400")
            donde = f"{int(frac * 100)}% de ~{tokens} tokens"
            if rc != 0:
                # ⊘ y no fallo: un error de plataforma no es un modelo que no recupera.
                print(f"    ⊘ {donde}: no se pudo medir ({err[:60]})")
                continue
            ok = AGUJA_VALOR in out
            # LA EVIDENCIA QUE SE IMPRIME TIENE QUE SOSTENER EL VEREDICTO. La primera versión
            # mostraba los primeros 48 caracteres crudos, y para el 27B eso era «We need answer
            # user's request...» —su razonamiento— junto a un ✓: el valor estaba más adelante.
            # Un ✓ al lado de una evidencia que no lo muestra es ilegible en el mejor caso y
            # una mentira en el peor, que es el defecto que este repo persigue.
            limpio = subprocess.run(
                [sys.executable, str(AQUI / "limpiar.py"), "--ultima-linea", "/dev/stdin"],
                input=out, capture_output=True, text=True).stdout.strip()
            muestra = limpio if AGUJA_VALOR in limpio else out[out.find(AGUJA_VALOR):][:32]
            # Y si hizo falta normalizar para verlo, eso es un dato aparte: el modelo recuperó
            # pero NO respetó «respondé sólo con el código». Importa para repartir papeles.
            sucio = "" if AGUJA_VALOR in limpio else "  ·formato sucio: contestó con razonamiento"
            print(f"    {'✓' if ok else '✗'} {donde}: {dt:5.1f}s  {muestra[:48]!r}{sucio}")
            if not ok:
                peor.setdefault(modelo, []).append(donde)
    if peor:
        print("\n✗ modelos que NO recuperan a la profundidad declarada:")
        for m, ds in peor.items():
            print(f"    {m}: falla en {', '.join(ds)}")
        print("  Una ventana declarada no es una ventana usable. Si el enunciado que le")
        print("  mandamos cae en esa zona, lo que se degrada es el enunciado — y el veredicto")
        print("  va a nombrar a la tarea.")
        return 1
    print("\n✓ todos recuperaron la aguja a todas las profundidades medidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
