#!/usr/bin/env python3
"""Sincroniza los limit.context de config/opencode.json con el max_model_len real de ColabHive.

Desde 2026-09-20 /v1/models devuelve `max_model_len` (y `max_model_len_source`:
`resident` = la réplica que está corriendo, `configured` = lo que declara el catálogo).
Este script lee ese valor y lo escribe en la config, dejando un margen de seguridad.

Uso:
  source ~/.config/colabhive/env
  python3 colabhive/scripts/sync_limits.py          # muestra qué cambiaría (desde la raíz del repo)
  python3 colabhive/scripts/sync_limits.py --write  # lo aplica
"""
import json, os, pathlib, sys, urllib.request

MARGEN = 0.92  # el prompt no debe llegar al tope: OpenCode compacta antes
ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "opencode.json"


def catalogo():
    key = os.environ.get("COLABHIVE_API_KEY")
    if not key:
        sys.exit("Falta COLABHIVE_API_KEY (source ~/.config/colabhive/env)")
    base = os.environ.get("COLABHIVE_BASE_URL", "https://api.colabhive.com/v1")
    req = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return {m["id"]: m for m in json.load(r)["data"]}


def main():
    escribir = "--write" in sys.argv
    cat = catalogo()
    cfg = json.loads(CFG.read_text())
    modelos = cfg["provider"]["colabhive"]["models"]
    cambios = 0

    for mid, entry in modelos.items():
        vivo = cat.get(mid)
        if not vivo:
            print(f"  ? {entry.get('name', mid)[:40]:40} no está en /v1/models")
            continue
        real = vivo.get("max_model_len")
        if not real:
            print(f"  ? {entry.get('name', mid)[:40]:40} sin max_model_len publicado")
            continue
        nuevo = int(real * MARGEN) // 1000 * 1000
        salida = min(entry.get("limit", {}).get("output", 8192), max(nuevo // 8, 2048))
        viejo = entry.get("limit", {}).get("context")
        marca = "=" if viejo == nuevo else "→"
        print(f"  {marca} {entry.get('name', mid)[:40]:40} {str(viejo):>7} {marca} {nuevo:>7} "
              f"(real {real}, {vivo.get('max_model_len_source')})")
        if viejo != nuevo:
            entry["limit"] = {"context": nuevo, "output": salida}
            cambios += 1

    if not cambios:
        print("\nNada que cambiar.")
        return
    if escribir:
        CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        print(f"\n{cambios} modelo(s) actualizados en {CFG}")
    else:
        print(f"\n{cambios} cambio(s) pendientes. Aplicalos con: python3 {pathlib.Path(__file__).resolve()} --write")


if __name__ == "__main__":
    main()
