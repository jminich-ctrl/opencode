#!/usr/bin/env python3
"""Ráfaga sobre UNA conexión TLS, después de una pausa, para verificar keep-warm.

- Abre 1 conexión, hace 1 request de calentamiento, espera PAUSE segundos,
  y luego manda N requests seguidas SIN cerrar la conexión.
- Reporta TTFT de cada una, si el server cerró la conexión (Connection: close)
  y si hubo que reconectar (o sea: conexión nueva => el edge no sostiene keep-alive).

Uso: python3 colabhive/scripts/keepalive_burst.py [pausa_seg] [n_requests]     # desde la raíz del repo
"""
import http.client, json, os, ssl, sys, time

KEY = os.environ["COLABHIVE_API_KEY"]
HOST = "api.colabhive.com"
MODEL = "f5d76140-5b4d-41c0-88da-dad6d11f341a"  # Qwen3-Coder-30B-A3B
PAUSE = int(sys.argv[1]) if len(sys.argv) > 1 else 90
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
MAXTOK = 120

conn = None
reconnects = 0


def get_conn():
    global conn, reconnects
    if conn is None:
        conn = http.client.HTTPSConnection(HOST, timeout=240, context=ssl.create_default_context())
        conn.connect()
        reconnects += 1
    return conn


def one(tag):
    """Devuelve (ttft, span, tokens, connection_header, reconectó)."""
    global conn
    body = json.dumps({"model": MODEL,
                       "messages": [{"role": "user", "content": "Write about TCP congestion control."}],
                       "stream": True, "max_tokens": MAXTOK,
                       "stream_options": {"include_usage": True}})
    hdrs = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
            "Accept": "text/event-stream", "Connection": "keep-alive"}
    before = reconnects
    for attempt in (1, 2):
        try:
            c = get_conn()
            t0 = time.monotonic()
            c.request("POST", "/v1/chat/completions", body, hdrs)
            r = c.getresponse()
            break
        except Exception as e:                      # conexión muerta -> reconectar
            conn = None
            if attempt == 2:
                return None, None, 0, f"ERROR {e!r}", True
    ttft = None; last = None; usage = None
    while True:
        line = r.readline()
        if not line:
            break
        t = line.decode("utf-8", "replace").strip()
        if not t.startswith("data:"):
            continue
        payload = t[5:].strip()
        if payload == "[DONE]":
            break
        d = json.loads(payload)
        if d.get("usage"):
            usage = d["usage"]
        for ch in d.get("choices", []):
            dl = ch.get("delta") or {}
            if dl.get("content") or dl.get("reasoning_content") or dl.get("tool_calls"):
                now = time.monotonic() - t0
                if ttft is None:
                    ttft = now
                last = now
    r.read()  # drenar el resto del cuerpo chunked: sin esto la conexión no se puede reutilizar
    conn_hdr = r.headers.get("Connection")
    if conn_hdr and conn_hdr.lower() == "close":
        try: conn.close()
        except Exception: pass
        conn = None
    n = (usage or {}).get("completion_tokens") or 0
    span = (last - ttft) if (ttft is not None and last is not None) else None
    return ttft, span, n, conn_hdr, reconnects > before


print(f"[{time.strftime('%H:%M:%S')}] calentando la conexión…", flush=True)
ttft, span, n, hdr, re_ = one("warm")
print(f"  warmup: ttft={ttft} conn={hdr} reconectó={re_}", flush=True)

print(f"[{time.strftime('%H:%M:%S')}] pausa de {PAUSE}s…", flush=True)
time.sleep(PAUSE)

print(f"[{time.strftime('%H:%M:%S')}] ráfaga de {N} requests sobre la misma conexión:", flush=True)
for i in range(N):
    ttft, span, n, hdr, re_ = one(f"req{i}")
    rate = (n / span) if (span and span > 0.05) else None
    print(f"  req{i}: ttft={ttft if ttft is None else round(ttft,2)}s "
          f"span={span if span is None else round(span,2)}s tok={n} "
          f"{'' if rate is None else str(round(rate))+' tok/s'} "
          f"conn={hdr} conexión_nueva={re_}", flush=True)
print(f"conexiones TLS abiertas en total: {reconnects} (1 = keep-alive real de punta a punta)")
