#!/usr/bin/env python3
"""Mide tokens por segundo de los modelos del equipo, separando arranque de generación.

    python3 scripts/medir-tps.py                      # los tres modelos del método
    python3 scripts/medir-tps.py --corridas 7         # más muestras
    python3 scripts/medir-tps.py --modelo <uuid>      # uno solo

Las tres reglas que este script obedece, y que salieron de equivocarnos con cada una:

1. **Separar arranque de generación.** El tiempo total mezcla dos cosas que no se parecen:
   lo que tarda el primer token (cola, arranque en frío, red) y la velocidad a la que sale
   el resto. Informar «total / tokens» hace que un arranque lento se vea como un modelo
   lento. Acá el streaming da el primer token y el tiempo de generación se mide DESDE ahí.
2. **Mediana de cinco, nunca una.** Una sola medición de una plataforma compartida mide
   quién más estaba usándola en ese segundo.
3. **El mismo protocolo que la referencia.** Un número nuevo sólo se puede comparar con el
   viejo si se tomó igual: mismo prompt, mismos max_tokens, mismo streaming. Si cambia el
   protocolo, el número anterior deja de ser una referencia y hay que decirlo.

Y una cosa que este script NO hace: medir mientras la plataforma está cambiando. Si hay un
despliegue en curso, los números describen el despliegue y no el modelo.
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("COLABHIVE_BASE_URL", "").rstrip("/")
CLAVE = os.environ.get("COLABHIVE_API_KEY", "")

# Los tres que usa el método, con el papel que cumplen: un número sin el papel no se puede
# usar para decidir nada.
EQUIPO = [
    ("f5d76140-5b4d-41c0-88da-dad6d11f341a", "Qwen3-Coder-30B · ejecutor y tester"),
    ("5d21e32a-3bbb-4040-9c34-3b06c4415b84", "gpt-oss-20b · título y explore"),
    ("1af07b1f-5832-4451-a61c-76d1fe43115a", "Qwen3.8-27B · plan y reviewer"),
]

# Un prompt fijo y corto: lo que se mide es la generación, no la lectura del contexto.
PROMPT = ("Escribí una función de Python que reciba una lista de enteros y devuelva la "
          "suma de los pares. Explicá en dos líneas por qué funciona.")


def una_corrida(modelo, max_tokens):
    """Devuelve (segundos al primer token, segundos de generación, tokens generados)."""
    cuerpo = json.dumps({
        "model": modelo, "stream": True, "max_tokens": max_tokens, "temperature": 0,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream_options": {"include_usage": True},
    }).encode()
    pedido = urllib.request.Request(
        f"{BASE}/chat/completions", data=cuerpo,
        headers={"Authorization": f"Bearer {CLAVE}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    t_primero = None
    tokens_usage = None
    trozos = 0          # trozos con contenido
    trozos_raz = 0      # trozos con razonamiento
    modo = "?"
    with urllib.request.urlopen(pedido, timeout=180) as r:
        for linea in r:
            linea = linea.decode("utf-8", "replace").strip()
            # La plataforma anuncia el modo en un comentario SSE: `: colabhive-stream-mode=...`
            if linea.startswith(":") and "stream-mode=" in linea:
                modo = linea.split("stream-mode=")[1].strip()
                continue
            if not linea.startswith("data: "):
                continue
            dato = linea[6:]
            if dato == "[DONE]":
                break
            try:
                d = json.loads(dato)
            except json.JSONDecodeError:
                continue
            if d.get("usage"):
                tokens_usage = d["usage"].get("completion_tokens")
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                # Un modelo que razona emite sus tokens en `reasoning`, no en `content`:
                # gpt-oss-20b con max_tokens=60 gastó los 60 razonando y no emitió una sola
                # palabra de contenido. Contar sólo `content` hacía que la medición lo
                # informara como «no llegó ningún token», que acusa al modelo de algo que es
                # de la medición. Los dos cuentan como generación, y se informan por separado
                # porque para el método no son lo mismo.
                if delta.get("content"):
                    if t_primero is None:
                        t_primero = time.perf_counter()
                    trozos += 1
                elif delta.get("reasoning") or delta.get("reasoning_content"):
                    if t_primero is None:
                        t_primero = time.perf_counter()
                    trozos_raz += 1
    t_fin = time.perf_counter()
    if t_primero is None:
        raise RuntimeError("no llegó ningún token, ni de contenido ni de razonamiento")
    # Los tokens los informa la plataforma; si no vienen, se cuentan los trozos, que es una
    # cota inferior y se dice.
    tokens = tokens_usage if tokens_usage else trozos
    return (t_primero - t0, t_fin - t_primero, tokens, tokens_usage is not None,
            trozos + trozos_raz, modo, trozos, trozos_raz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corridas", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--modelo", action="append")
    args = ap.parse_args()

    if not BASE or not CLAVE:
        sys.exit("✗ falta COLABHIVE_BASE_URL o COLABHIVE_API_KEY: "
                 ". ~/.config/colabhive/env")

    equipo = [(m, "") for m in args.modelo] if args.modelo else EQUIPO
    print(f"{args.corridas} corridas por modelo · max_tokens={args.max_tokens} · "
          f"mediana, no promedio\n")
    for modelo, papel in equipo:
        arranques, velocidades, fallas, sin_stream, modos = [], [], 0, 0, set()
        contenido, razonamiento = 0, 0
        exacto = True
        for _ in range(args.corridas):
            try:
                (t_arr, t_gen, tokens, exacto, trozos, modo,
                 n_cont, n_raz) = una_corrida(modelo, args.max_tokens)
            except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as e:
                fallas += 1
                print(f"  ⊘ una corrida falló: {type(e).__name__} {e}")
                continue
            modos.add(modo)
            contenido += n_cont
            razonamiento += n_raz
            arranques.append(t_arr)
            # Si toda la respuesta llegó en dos trozos o menos, NO se transmitió: el tiempo
            # de generación colapsa y el cociente da cientos de tokens por segundo, que no
            # es la velocidad del modelo sino el reflejo de un búfer. Una medición que no
            # distingue «rápido» de «entregado de golpe» no mide velocidad.
            if trozos <= 2:
                sin_stream += 1
                continue
            velocidades.append(tokens / t_gen if t_gen > 0 else 0)
        print(f"{modelo[:8]} · {papel}")
        if not velocidades:
            print(f"  ✗ ninguna corrida transmitió de verdad ({sin_stream} llegaron de "
                  f"golpe, {fallas} fallaron): no hay velocidad que informar\n")
            continue
        print(f"  primer token   mediana {statistics.median(arranques):6.2f}s   "
              f"(mín {min(arranques):.2f} · máx {max(arranques):.2f})")
        print(f"  generación     mediana {statistics.median(velocidades):6.1f} tok/s "
              f"(mín {min(velocidades):.1f} · máx {max(velocidades):.1f})")
        if fallas:
            print(f"  ⊘ {fallas} de {args.corridas} corridas fallaron: la mediana es de "
                  f"las que quedaron, y eso hay que tenerlo en cuenta")
        if sin_stream:
            print(f"  ⊘ {sin_stream} corrida(s) llegaron sin transmitir (≤2 trozos): "
                  f"excluidas, porque ahí el cociente mide el búfer y no el modelo")
        if razonamiento:
            total = contenido + razonamiento
            print(f"  · de los trozos emitidos, {100*razonamiento/total:.0f}% fueron "
                  f"razonamiento y {100*contenido/total:.0f}% contenido")
            if contenido == 0:
                print(f"  ⊘ NINGÚN token de contenido con max_tokens={args.max_tokens}: "
                      f"como generador de texto, en este presupuesto, no sirve")
        if modos - {"?"}:
            print(f"  · modo de transmisión informado por la plataforma: "
                  f"{', '.join(sorted(modos - {'?'}))}")
        if not exacto:
            print("  ⊘ la plataforma no informó `usage`: los tokens son trozos contados, "
                  "o sea una cota inferior")
        print()


if __name__ == "__main__":
    main()
