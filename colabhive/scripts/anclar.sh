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

MODELOS=(
  "9a1f0c77-4b2e-4d3a-8f6b-0c2e5a7d120b:arquitecto  gpt-oss-120b"
  "f5d76140-5b4d-41c0-88da-dad6d11f341a:ejecutor    Qwen3-Coder-30B"
  "1af07b1f-5832-4451-a61c-76d1fe43115a:reviewer    Qwen3.8-27B"
  "5d21e32a-3bbb-4040-9c34-3b06c4415b84:orquestador gpt-oss-20b"
  "a9aa41f2-b238-4de1-8abf-c58b84eb0331:worker      Qwen3-8B"
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
