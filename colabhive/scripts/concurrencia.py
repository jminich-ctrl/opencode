#!/usr/bin/env python3
"""Mide cómo escala un modelo con requests en paralelo.

Responde: ¿cuántas tareas puedo lanzar a la vez antes de que la latencia se dispare?

Uso:
  source ~/.config/colabhive/env
  python3 colabhive/scripts/concurrencia.py [endpoint_id] [niveles]     # desde la raíz del repo
  python3 colabhive/scripts/concurrencia.py 1af07b1f-... 1,4,8
"""
import json, os, statistics, sys, threading, time, urllib.request

KEY = os.environ.get("COLABHIVE_API_KEY") or sys.exit("falta COLABHIVE_API_KEY")
BASE = os.environ.get("COLABHIVE_BASE_URL", "https://api.colabhive.com/v1")  # otro backend OpenAI-compatible: cambialo acá
MODELO = sys.argv[1] if len(sys.argv) > 1 else "1af07b1f-5832-4451-a61c-76d1fe43115a"
NIVELES = [int(n) for n in (sys.argv[2] if len(sys.argv) > 2 else "1,4,8").split(",")]
PROMPT_TOKENS = 2000   # parecido al contexto de una tarea chica
SALIDA = 200


def pedido(idx, resultados):
    """Una request de streaming; guarda TTFT, duración y tokens generados."""
    cuerpo = json.dumps({
        "model": MODELO,
        "messages": [{"role": "user", "content": f"sesion-{idx} " + "palabra " * PROMPT_TOKENS +
                      "\n\nEscribí un párrafo sobre control de congestión TCP."}],
        "stream": True, "max_tokens": SALIDA, "stream_options": {"include_usage": True},
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=cuerpo,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "Accept": "text/event-stream"})
    t0 = time.time(); ttft = None; tokens = 0
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            for cruda in r:
                s = cruda.decode("utf-8", "replace").strip()
                if not s.startswith("data:"):
                    continue
                p = s[5:].strip()
                if p == "[DONE]":
                    break
                d = json.loads(p)
                if d.get("usage"):
                    tokens = d["usage"].get("completion_tokens", 0)
                for c in d.get("choices", []):
                    dl = c.get("delta") or {}
                    if (dl.get("content") or dl.get("reasoning_content")) and ttft is None:
                        ttft = time.time() - t0
        resultados.append({"ttft": ttft, "total": time.time() - t0, "tokens": tokens})
    except Exception as e:
        resultados.append({"error": repr(e)[:60], "total": time.time() - t0})


print(f"modelo {MODELO}  ·  prompt ~{PROMPT_TOKENS} tokens  ·  salida {SALIDA}\n")
print(f"{'paralelas':>9} {'TTFT p50':>9} {'TTFT max':>9} {'pared':>7} {'tok/s total':>12} {'errores':>8}")
print("─" * 60)
for n in NIVELES:
    resultados = []
    hilos = [threading.Thread(target=pedido, args=(i, resultados)) for i in range(n)]
    t0 = time.time()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    pared = time.time() - t0
    ok = [r for r in resultados if "error" not in r and r.get("ttft")]
    errores = len(resultados) - len(ok)
    if not ok:
        print(f"{n:>9} {'—':>9} {'—':>9} {pared:>6.1f}s {'—':>12} {errores:>8}")
        continue
    ttfts = sorted(r["ttft"] for r in ok)
    total_tokens = sum(r["tokens"] for r in ok)
    print(f"{n:>9} {statistics.median(ttfts):>8.2f}s {max(ttfts):>8.2f}s "
          f"{pared:>6.1f}s {total_tokens / pared:>11.0f} {errores:>8}")
    time.sleep(2)

print("\nSi el TTFT p50 se mantiene y los tok/s totales suben, el modelo escala.")
print("Si el TTFT se dispara y los tok/s se estancan, ese es tu techo de paralelismo.")
