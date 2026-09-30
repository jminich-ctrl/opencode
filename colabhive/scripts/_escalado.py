#!/usr/bin/env python3
"""Imprime en una línea cómo quedó el escalado de un endpoint.

Lee el JSON de la API por stdin; el nombre legible viene por argumento.
Está en un archivo aparte y no embebido en el .sh a propósito: anidar comillas
de bash, python y f-strings es una fuente segura de errores.
"""
import json
import sys

nombre = sys.argv[1] if len(sys.argv) > 1 else "?"
try:
    d = json.load(sys.stdin)
except Exception:
    print(f"  ✗ {nombre}  respuesta ilegible")
    raise SystemExit(1)

if not d.get("scaling_mode"):
    print(f"  ✗ {nombre}  {str(d)[:110]}")
    raise SystemExit(1)

modo = d["scaling_mode"]
marca = "✓" if modo == "minimum" else "·"
print(f"  {marca} {nombre}  modo={modo:<10} min={d.get('min_replicas','?')} "
      f"actuales={d.get('current_replicas', '?')}")
