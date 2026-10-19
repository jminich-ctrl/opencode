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


def configs():
    """Las configs a sincronizar, **empezando por la que OpenCode usa de verdad**.

    Antes esto era una sola ruta clavada: `ROOT/config/opencode.json`, la copia del repo.
    Y `~/.config/opencode/opencode.json` es un **symlink a otro repo**
    (`colabhive-opencode/config/opencode.json`), así que el `--write` arreglaba la copia que
    nadie carga y dejaba intacta la que sirve.

    Lo peor no era que no arreglara: es que **el guardia se quedaba callado después**.
    `correr-todo.sh` detecta la deriva corriendo este script, así que al sincronizar la copia
    del repo el chequeo pasaba a verde mientras la config viva seguía declarando un contexto
    más grande que el real — y cada tarea moriría con un 400 que no se parece a su causa.
    Un arreglo que ciega a su propio chequeo es peor que no tener el arreglo.

    Es «medí el artefacto que corre, no el árbol», en la herramienta cuyo trabajo es
    justamente que una declaración no mienta.
    """
    vistas, salida = set(), []
    candidatas = [
        os.environ.get("CONFIG_OC"),
        pathlib.Path.home() / ".config" / "opencode" / "opencode.json",
        ROOT / "config" / "opencode.json",
    ]
    for c in candidatas:
        if not c:
            continue
        ruta = pathlib.Path(c)
        if not ruta.exists():
            continue
        # resolve(): si es symlink, se escribe el archivo real y no se reemplaza el enlace.
        real = ruta.resolve()
        if real in vistas:
            continue
        vistas.add(real)
        salida.append((ruta, real))
    return salida


def catalogo():
    key = os.environ.get("COLABHIVE_API_KEY")
    if not key:
        sys.exit("Falta COLABHIVE_API_KEY (source ~/.config/colabhive/env)")
    base = os.environ.get("COLABHIVE_BASE_URL", "https://api.colabhive.com/v1")
    req = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return {m["id"]: m for m in json.load(r)["data"]}


def sincronizar(cat, ruta, destino, escribir):
    """Una config. Devuelve cuántos modelos cambiarían (o cambiaron).

    El parámetro se llama `destino` y no `real`: el bucle de abajo usa `real` para el
    `max_model_len` del modelo, y con el mismo nombre lo tapaba — así que al escribir,
    `real.write_text(...)` recibía un entero. La corrida en seco no lo tocaba, porque no
    llega al write: verifiqué con el único camino que no ejercita el defecto.
    """
    etiqueta = str(ruta) if ruta == destino else f"{ruta} → {destino}"
    print(f"\n── {etiqueta}")
    cfg = json.loads(destino.read_text())
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

    if cambios and escribir:
        destino.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        print(f"  {cambios} modelo(s) actualizados en {destino}")
    return cambios


def main():
    escribir = "--write" in sys.argv
    cat = catalogo()
    destinos = configs()
    if not destinos:
        sys.exit("No encontré ninguna config de OpenCode (ni CONFIG_OC, ni ~/.config, ni la del repo)")
    total = sum(sincronizar(cat, ruta, destino, escribir) for ruta, destino in destinos)
    if not total:
        print("\nNada que cambiar.")
        return
    if not escribir:
        print(f"\n{total} cambio(s) pendientes en {len(destinos)} config(s). "
              f"Aplicalos con: python3 {pathlib.Path(__file__).resolve()} --write")


if __name__ == "__main__":
    main()
