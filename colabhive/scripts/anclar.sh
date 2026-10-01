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
MODELOS=(
  "1af07b1f-5832-4451-a61c-76d1fe43115a:arquitecto y reviewer  Qwen3.8-27B"
  "f5d76140-5b4d-41c0-88da-dad6d11f341a:ejecutor               Qwen3-Coder-30B"
  "5d21e32a-3bbb-4040-9c34-3b06c4415b84:rápidos (title/summary) gpt-oss-20b"
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
