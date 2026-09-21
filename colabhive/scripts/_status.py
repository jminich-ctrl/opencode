#!/usr/bin/env python3
"""Lee readiness de la API y muestra el estado de los modelos del equipo.
Sale con código 1 si alguno está en cold."""
import json, sys

# model_name del catálogo → rol en config/opencode.json. Si cambiás de modelos, cambialo acá.
ROLES = {
    "gpt-oss-20b": "plan/explore",
    "hf-Qwen-Qwen3-Coder-30B-A3B-Instruct-FP8": "build/tester",
    "hf-Qwen-Qwen3.8-27B-FP8": "reviewer",
}
ICON = {"warm": "●", "cached": "◐", "cold": "○"}

try:
    models = json.load(sys.stdin)["models"]
except Exception as e:
    print(f"  no se pudo leer el estado ({e})")
    sys.exit(0)

frias = 0
for m in models:
    rol = ROLES.get(m["model_name"])
    if not rol:
        continue
    st = m["readiness"]
    frias += st == "cold"
    print(f"  {ICON.get(st, '?')} {rol:12} {st:7} {m['model_name'][:44]}")
sys.exit(1 if frias else 0)
