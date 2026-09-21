#!/usr/bin/env python3
"""Verifica si hay prefix caching: manda el mismo prompt largo dos veces y compara TTFT.

Con prefix caching, la 2ª tiene que bajar de ~50 s a pocos segundos.
También prueba el caso real de un agente: mismo prefijo, final distinto.

Uso:
  source ~/.config/colabhive/env
  python3 colabhive/scripts/check_cache.py [endpoint_id] [tokens]     # desde la raíz del repo
"""
import json, os, sys, time, urllib.request, uuid

KEY = os.environ.get("COLABHIVE_API_KEY") or sys.exit("falta COLABHIVE_API_KEY")
BASE = os.environ.get("COLABHIVE_BASE_URL", "https://api.colabhive.com/v1")  # otro backend OpenAI-compatible: cambialo acá
MODEL = sys.argv[1] if len(sys.argv) > 1 else "1af07b1f-5832-4451-a61c-76d1fe43115a"
TOKENS = int(sys.argv[2]) if len(sys.argv) > 2 else 60000
SESSION = "opencode-cache-check"
UNICO = f"sesion {uuid.uuid4().hex} "  # invalida el cache de corridas previas


def run(words, sufijo):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": UNICO + "palabra " * words + sufijo}],
        "stream": True, "max_tokens": 8, "stream_options": {"include_usage": True},
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "Accept": "text/event-stream", "X-Session-ID": SESSION})
    t0 = time.time(); ttft = None; usage = None
    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:
            s = raw.decode("utf-8", "replace").strip()
            if not s.startswith("data:"):
                continue
            p = s[5:].strip()
            if p == "[DONE]":
                break
            d = json.loads(p)
            if d.get("usage"):
                usage = d["usage"]
            for c in d.get("choices", []):
                dl = c.get("delta") or {}
                if (dl.get("content") or dl.get("reasoning_content")) and ttft is None:
                    ttft = time.time() - t0
    return ttft, (usage or {})


print(f"modelo {MODEL}  ·  prompt de ~{TOKENS} tokens\n")
casos = [("1ª vez (cache frío)", "\n\nResponde solo: OK"),
         ("repetido idéntico", "\n\nResponde solo: OK"),
         ("mismo prefijo, final distinto", "\n\nResponde solo: LISTO")]
res = []
for etiqueta, suf in casos:
    t, u = run(TOKENS, suf)
    res.append(t)
    det = u.get("prompt_tokens_details")
    cached = (det or {}).get("cached_tokens")
    print(f"  {etiqueta:32} ttft={'n/d' if t is None else f'{t:6.1f}s'}  "
          f"prompt={u.get('prompt_tokens')}  cached_tokens={cached if det else 'no reportado'}")

t1, t2, t3 = res
print()
if t1 and t2:
    if t2 < t1 * 0.4:
        print(f"✓ HAY prefix caching: {t1:.1f}s → {t2:.1f}s ({t1/t2:.0f}× más rápido)")
        if t3 and t3 < t1 * 0.4:
            print(f"✓ Y sirve con prefijo compartido ({t3:.1f}s) — que es el caso de un agente")
        else:
            print(f"✗ Pero NO con prefijo compartido ({t3:.1f}s): un agente no se beneficiaría")
    else:
        print(f"✗ NO hay prefix caching todavía: {t1:.1f}s → {t2:.1f}s")
