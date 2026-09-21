#!/usr/bin/env python3
"""Smoke test de ColabHive para uso con OpenCode.

Por cada modelo mide:
  1. warmup: request streaming con tool -> tiempo al primer byte/token (incluye carga si está cached/cold)
  2. tool calling: ¿devuelve tool_calls bien formados con argumentos JSON válidos?
  3. warm: segunda request (texto) -> TTFT y tokens/s ya con el modelo cargado

Uso:
  source ~/.config/colabhive/env
  python3 colabhive/scripts/smoke_test.py <endpoint_id_o_nombre> [...]     # desde la raíz del repo
Solo stdlib. Resultados en research/live/smoke-<timestamp>.json
"""
import json, os, sys, time, urllib.request, urllib.error, pathlib

BASE = os.environ.get("COLABHIVE_BASE_URL", "https://api.colabhive.com/v1")
KEY = os.environ.get("COLABHIVE_API_KEY")
TIMEOUT = 1800  # 30 min: un cold start puede tardar varios minutos

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from the repository",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "start_line": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
}]


def stream(model, messages, tools=None, max_tokens=512):
    body = {"model": model, "messages": messages, "stream": True,
            "max_tokens": max_tokens, "temperature": 0.2,
            "stream_options": {"include_usage": True}}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "Accept": "text/event-stream"})
    t0 = time.monotonic()
    out = {"http": None, "ttfb_s": None, "ttft_s": None, "total_s": None, "content": "",
           "reasoning_chars": 0, "tool_calls": {}, "finish_reason": None, "usage": None,
           "stream_mode": None, "chunks": 0, "error": None}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            out["http"] = resp.status
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                if out["ttfb_s"] is None:
                    out["ttfb_s"] = round(time.monotonic() - t0, 2)
                if line.startswith(":"):
                    if "colabhive-stream-mode" in line:
                        out["stream_mode"] = line
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if chunk.get("usage"):
                    out["usage"] = chunk["usage"]
                for ch in chunk.get("choices", []):
                    d = ch.get("delta") or {}
                    got = d.get("content") or d.get("reasoning_content") or d.get("reasoning") or d.get("tool_calls")
                    if got and out["ttft_s"] is None:
                        out["ttft_s"] = round(time.monotonic() - t0, 2)
                    if got:
                        out["chunks"] += 1
                    out["content"] += d.get("content") or ""
                    out["reasoning_chars"] += len(d.get("reasoning_content") or d.get("reasoning") or "")
                    for tc in d.get("tool_calls") or []:
                        slot = out["tool_calls"].setdefault(tc.get("index", 0), {"name": "", "arguments": ""})
                        fn = tc.get("function") or {}
                        slot["name"] += fn.get("name") or ""
                        slot["arguments"] += fn.get("arguments") or ""
                    if ch.get("finish_reason"):
                        out["finish_reason"] = ch["finish_reason"]
    except urllib.error.HTTPError as e:
        out["http"] = e.code
        out["error"] = {"body": e.read().decode("utf-8", "replace")[:500],
                        "retry_after": e.headers.get("Retry-After")}
    except Exception as e:  # timeouts, conexión
        out["error"] = repr(e)
    out["total_s"] = round(time.monotonic() - t0, 2)
    toks = (out["usage"] or {}).get("completion_tokens")
    gen_s = out["total_s"] - (out["ttft_s"] or out["total_s"])
    out["tok_per_s"] = round(toks / gen_s, 1) if toks and gen_s > 0.05 else None
    return out


def check_tools(r):
    calls = list(r["tool_calls"].values())
    if not calls:
        return "NO tool_calls (¿parser no configurado o tool call en texto?)"
    c = calls[0]
    try:
        args = json.loads(c["arguments"] or "{}")
    except json.JSONDecodeError:
        return f"tool_call con argumentos NO-JSON: {c['arguments'][:120]!r}"
    ok = c["name"] == "read_file" and "path" in args
    return f"{'OK' if ok else 'RARO'}: {c['name']}({json.dumps(args)}) finish={r['finish_reason']}"


def main():
    if not KEY:
        sys.exit("Falta COLABHIVE_API_KEY (source ~/.config/colabhive/env)")
    results = {}
    for model in sys.argv[1:]:
        print(f"\n=== {model} ===", flush=True)
        print("1) warmup + tool call (streaming)...", flush=True)
        r1 = stream(model, [
            {"role": "system", "content": "You are a coding agent. Use tools when needed."},
            {"role": "user", "content": "Open src/app.py starting at line 10 so we can inspect the bug."},
        ], tools=TOOLS, max_tokens=1024)
        print(f"   http={r1['http']} ttfb={r1['ttfb_s']}s ttft={r1['ttft_s']}s total={r1['total_s']}s "
              f"mode={r1['stream_mode']} chunks={r1['chunks']}")
        print("   tools:", check_tools(r1) if not r1["error"] else f"ERROR {r1['error']}")
        if r1["content"]:
            print("   content:", r1["content"][:200].replace("\n", " "))

        print("2) warm: generación de texto...", flush=True)
        r2 = stream(model, [{"role": "user", "content":
            "Write a Python function that parses an ISO-8601 date string with timezone and returns a UTC datetime. Include a docstring and 3 pytest tests."}],
            max_tokens=700)
        print(f"   http={r2['http']} ttft={r2['ttft_s']}s total={r2['total_s']}s "
              f"tokens={(r2['usage'] or {}).get('completion_tokens')} tok/s={r2['tok_per_s']} "
              f"reasoning_chars={r2['reasoning_chars']} finish={r2['finish_reason']}")
        if r2["error"]:
            print("   ERROR", r2["error"])
        results[model] = {"warmup_tool": r1, "warm_text": r2}

    outdir = pathlib.Path(__file__).resolve().parent.parent / "research" / "live"
    outdir.mkdir(parents=True, exist_ok=True)
    f = outdir / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}.json"
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\nResultados: {f}")


if __name__ == "__main__":
    main()
