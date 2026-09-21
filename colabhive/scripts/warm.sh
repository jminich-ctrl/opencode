#!/usr/bin/env bash
# Deja calientes los modelos del equipo de OpenCode.
# Consulta readiness, y a cada modelo le manda un ping con streaming: con streaming el
# gateway mantiene viva la conexión mientras el modelo carga (hasta 20 min), así que
# el ping vuelve recién cuando el modelo está listo.
#
# Uso (desde la raíz del repo): bash colabhive/scripts/warm.sh   · o bien: oc --warm
set -uo pipefail
: "${COLABHIVE_API_KEY:?source ~/.config/colabhive/env primero}"
BASE="${COLABHIVE_BASE_URL:-https://api.colabhive.com/v1}"
BUILDER="${COLABHIVE_BUILDER_URL:-https://api.colabhive.com/api/builder/v1}"

# id de endpoint : nombre legible  (los 3 del equipo, ver config/opencode.json)
MODELS=(
  "5d21e32a-3bbb-4040-9c34-3b06c4415b84:gpt-oss-20b (plan, explore, títulos)"
  "1af07b1f-5832-4451-a61c-76d1fe43115a:Qwen3.8-27B FP8 (reviewer)"
  "f5d76140-5b4d-41c0-88da-dad6d11f341a:Qwen3-Coder-30B (build/tester)"
)

auth() { printf 'X-API-Key: %s\n' "$COLABHIVE_API_KEY"; }

echo "→ estado actual"
auth | curl -sS -m 60 -H @- "$BUILDER/inference/models?include_readiness=true" \
  | python3 "$(dirname "${BASH_SOURCE[0]}")/_status.py" || true

for entry in "${MODELS[@]}"; do
  id="${entry%%:*}"; nombre="${entry#*:}"
  printf '→ %s … ' "$nombre"
  start=$(date +%s)
  cuerpo="$(mktemp)"
  code=$(printf 'Authorization: Bearer %s\n' "$COLABHIVE_API_KEY" \
    | curl -sS -N -o "$cuerpo" -w '%{http_code}' -m 1800 -H @- \
      -H 'Content-Type: application/json' -H 'Accept: text/event-stream' \
      -d "{\"model\":\"$id\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"stream\":true,\"max_tokens\":4}" \
      "$BASE/chat/completions")
  secs=$(( $(date +%s) - start ))
  # Con streaming el 200 sale ANTES de que el modelo cargue (el gateway manda comentarios
  # ": keep-alive" mientras espera): el 200 solo no prueba nada. Listo = llegó una
  # respuesta del modelo ("choices") y ningún evento de error.
  if [ "$code" = "200" ] && grep -q '"choices"' "$cuerpo" && ! grep -q '"error"' "$cuerpo"; then
    if [ "$secs" -gt 20 ]; then echo "listo (arrancó en frío, ${secs}s)"; else echo "ya estaba caliente (${secs}s)"; fi
  else
    echo "FALLÓ (HTTP $code, ${secs}s): $(grep -m1 -oE '"message": *"[^"]*"' "$cuerpo" | cut -c1-120)"
  fi
  rm -f "$cuerpo"
done
echo "Listo. Siguen calientes mientras se usen: los modelos del catálogo compartido los"
echo "carga y descarga la plataforma según la demanda. Para uno siempre caliente,"
echo "servilo desde tu cuenta (ver OPENCODE.md §6)."
