#!/usr/bin/env bash
# Ancla (o suelta) los modelos del equipo para que no se enfríen.
#
#   bash scripts/anclar.sh            # ancla: quedan residentes
#   bash scripts/anclar.sh soltar     # vuelve a on_demand
#   bash scripts/anclar.sh estado     # muestra cómo está cada uno
#
# `scaling_mode: minimum` con `min_replicas: 1` convierte la residencia en un
# compromiso permanente: la plataforma no los evicta aunque haga falta VRAM.
# NO hace falta `required_node_ids` (eso es sólo para fijarlos a un nodo concreto).
#
# Por qué importa: con 5 modelos en el equipo, despertar uno desaloja a otro.
# Medido: al despertar el reviewer perdimos el arquitecto.
set -uo pipefail
: "${COLABHIVE_API_KEY:?source ~/.config/colabhive/env primero}"
BUILDER="${COLABHIVE_BUILDER_URL:-https://api.colabhive.com/api/builder/v1}"
ACCION="${1:-anclar}"

# Tres modelos, no cinco. gpt-oss-120b y Qwen3-8B quedaron sin rol el 2026-10-01:
# el primero porque la medición en su rango de tamaño encontró cero ganancia de exactitud
# por planificar a 120B, y porque su formato de tool call manda los argumentos como un
# único blob JSON — un archivo entero escapado en una sola tirada, que es la forma más
# difícil justo para lo que el planificador tiene que hacer. El segundo porque para títulos
# y resúmenes medimos 12,8s contra 1,1s de gpt-oss-20b.
# Salen de la config de OpenCode, no de una lista acá: esta lista anclaba el
# Qwen3-Coder-30B mucho después de que ningún agente lo usara. Un id de modelo escrito en
# un script es una copia de lo que declara opencode.json, y una copia que nadie cruza queda
# vieja el día que cambia el original.
CONFIG_OC="${CONFIG_OC:-$HOME/.config/opencode/opencode.json}"
[ -f "$CONFIG_OC" ] || CONFIG_OC="$(dirname "${BASH_SOURCE[0]}")/../config/opencode.json"
MODELOS=()
while IFS= read -r l; do [ -n "$l" ] && MODELOS+=("$l"); done < <(python3 - "$CONFIG_OC" <<'PYANC'
import json, sys
cfg = json.load(open(sys.argv[1]))
mods = cfg.get("provider", {}).get("colabhive", {}).get("models", {})
usos = {}
for ag, v in (cfg.get("agent") or {}).items():
    if (v or {}).get("model"):
        usos.setdefault(v["model"].split("/")[-1], []).append(ag)
for mid, ags in usos.items():
    print(f"{mid}:{', '.join(sorted(ags))[:38]:38s} {(mods.get(mid) or {}).get('name', mid[:8]).split('·')[0].strip()}")
PYANC
)

auth() { printf 'X-API-Key: %s\n' "$COLABHIVE_API_KEY"; }

case "$ACCION" in
  anclar) MODO='{"scaling_mode":"minimum","min_replicas":1,"max_replicas":2}' ;;
  soltar) MODO='{"scaling_mode":"on_demand","min_replicas":0,"max_replicas":2}' ;;
  estado) MODO="" ;;
  *) echo "uso: $0 [anclar|soltar|estado]" >&2; exit 1 ;;
esac

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for entrada in "${MODELOS[@]}"; do
  id="${entrada%%:*}"; nombre="${entrada#*:}"
  if [ "$ACCION" = "estado" ]; then
    auth | curl -sS -m 30 -H @- "$BUILDER/endpoints/$id" \
      | python3 "$AQUI/_escalado.py" "$nombre"
  else
    auth | curl -sS -m 60 -X PATCH -H @- -H 'Content-Type: application/json' \
           -d "$MODO" "$BUILDER/endpoints/$id/scaling" \
      | python3 "$AQUI/_escalado.py" "$nombre"
  fi
done
