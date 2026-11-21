#!/usr/bin/env python3
"""Lee readiness de la API (por stdin) y muestra el estado de los modelos DEL EQUIPO.
Sale con código 1 si alguno quedó frío o no se pudo verificar.

Los papeles salen de la config de OpenCode, NO de una tabla acá adentro. La tabla existió y
quedó vieja: decía `arquitecto → gpt-oss-120b` y `worker → Qwen3-8B` cuando la config ya
asignaba el arquitecto al Qwen3.8-27B FP8 y ningún agente usaba el 8B. O sea que la
VERIFICACIÓN FINAL de `warm.sh` —la que existe para avisar que despertar un modelo desalojó
a otro— informaba sobre modelos que la corrida no iba a usar, y callaba sobre los que sí.

Es el mismo defecto que `warm.sh` documenta haber resuelto de su lado con la lista de
modelos: ahí la sacó de la config y acá la dejó escrita a mano, así que el calentador
calentaba lo correcto y el verificador miraba otra cosa. El patrón de METODO.md: el arreglo
vive en un hermano y no en el otro.

## El puente entre los dos id

Hay DOS espacios de identificadores y no son el mismo, cosa que costó una tabla vieja no ver:

  - la config de OpenCode usa el id del **despliegue** (`1af07b1f-…`), que es lo que acepta
    `/v1/chat/completions` y lo que `warm.sh` manda como `"model"`;
  - `/api/builder/v1/inference/models` —el único que publica `readiness`— usa el id del
    **catálogo** (`4cbffec1-…`) en su campo `model_id`.

El puente es `/v1/models`, que trae los dos: `id` (despliegue) y `model_config_id`
(catálogo). Por eso este script pide `/v1/models` aunque el readiness le llegue por stdin.
Emparejar por NOMBRE no sirve: la config dice «Qwen3.8-27B FP8», `/v1/models` dice
«Qwen3.8-27B-FP8» y el catálogo «hf-Qwen-Qwen3.8-27B-FP8», y el ejecutor directamente se
llama distinto en cada uno («Qwen3-Coder-30B-A3B» en la config, «Qwen3 Coder 30B-A3B AWQ»
en `/v1/models`). Tres nombres para un modelo es exactamente de donde salen las tablas a mano.
"""
import json
import os
import pathlib
import sys
import urllib.request

ICON = {"warm": "●", "cached": "◐", "cold": "○"}


def config_de_opencode():
    """La misma resolución que `warm.sh`: el override por entorno, la config viva, y recién
    después la copia del repo."""
    candidatas = [os.environ.get("CONFIG_OC"),
                  pathlib.Path.home() / ".config/opencode/opencode.json",
                  pathlib.Path(__file__).resolve().parent.parent / "config/opencode.json"]
    for c in candidatas:
        if not c:
            continue
        p = pathlib.Path(c)
        if p.is_file():
            try:
                return json.loads(p.read_text())
            except Exception:
                continue
    return {}


def papeles():
    """{id_de_despliegue: 'build, ejecutor, tester'} — los agentes que declaran cada modelo.

    La clave es el modelo y no el papel: un modelo puede tener varios papeles, y al revés se
    perdían agentes en silencio."""
    usos = {}
    for agente, v in (config_de_opencode().get("agent") or {}).items():
        mid = (v or {}).get("model")
        if mid:
            usos.setdefault(mid.split("/")[-1], []).append(agente)
    return {k: ", ".join(sorted(v)) for k, v in usos.items()}


def puente():
    """{id_de_catálogo: {id_de_despliegue, ...}}, desde /v1/models. {} si no se pudo.

    El valor es un CONJUNTO porque la relación es uno a muchos: un modelo del catálogo
    puede tener varios despliegues. Hoy `gpt-oss-20b` tiene dos —el del equipo y uno
    llamado `R6 · gpt-oss-20b`— y el ejecutor también. La primera versión de esto guardaba
    `{catálogo: despliegue}` y el segundo tapaba al primero: los dos modelos del equipo
    salieron informados como «NO están en el catálogo con readiness», o sea un ⚠ inventado
    sobre dos modelos que estaban perfectamente listados. Lo vi porque corrí el script
    contra la API de verdad en vez de confiar en que el join era uno a uno.

    `readiness` lo publica el catálogo, no el despliegue, así que todos los despliegues de
    un mismo modelo comparten estado y alcanza con que el del equipo esté entre ellos."""
    key = os.environ.get("COLABHIVE_API_KEY")
    if not key:
        return {}
    base = os.environ.get("COLABHIVE_BASE_URL", "https://api.colabhive.com/v1")
    req = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            datos = json.load(r)["data"]
    except Exception:
        return {}
    mapa = {}
    for m in datos:
        if m.get("model_config_id"):
            mapa.setdefault(m["model_config_id"], set()).add(m["id"])
    return mapa


def main():
    try:
        models = json.load(sys.stdin)["models"]
    except Exception as e:
        print(f"  no se pudo leer el estado ({e})")
        return 0

    roles = papeles()
    if not roles:
        print("  ⚠ no pude leer los papeles de la config de OpenCode: no sé qué modelos va a")
        print("    usar la corrida, así que NO puedo decir si quedó alguno frío.")
        return 1

    despliegue_de = puente()
    if not despliegue_de:
        print("  ⚠ no pude pedir /v1/models: sin ese puente no sé cuál de los modelos del")
        print("    catálogo es cada agente. NO es «están todos bien»: es que no miré.")
        return 1

    frias, vistos = 0, set()
    for m in models:
        nuestros = sorted(despliegue_de.get(m.get("model_id"), set()) & set(roles))
        for mid in nuestros:
            vistos.add(mid)
            st = m["readiness"]
            frias += st == "cold"
            print(f"  {ICON.get(st, '?')} {roles[mid]:30.30} {st:7} {m['model_name'][:40]}")

    # Un modelo que los agentes declaran y que no aparece en el catálogo no es «todo bien»:
    # es un modelo que la corrida va a pedir y que nadie va a servir. Callarlo deja el mismo
    # verde falso que la tabla vieja: el verificador no vio nada malo porque no miró.
    faltan = [f"{rol} ({mid[:8]})" for mid, rol in roles.items() if mid not in vistos]
    if faltan:
        print(f"  ⚠ {len(faltan)} modelo(s) que los agentes declaran NO están en el catálogo "
              "con readiness: " + "; ".join(faltan))
        frias += len(faltan)
    return 1 if frias else 0


if __name__ == "__main__":
    sys.exit(main())
