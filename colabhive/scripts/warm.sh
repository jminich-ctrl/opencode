#!/usr/bin/env bash
# Deja calientes los modelos del equipo de OpenCode.
# Consulta readiness, y a los que no están warm les manda un ping con streaming
# (streaming no tiene el corte de 300s, así que espera la carga completa).
#
# Uso: bash ~/colabhive-opencode/scripts/warm.sh
set -uo pipefail
: "${COLABHIVE_API_KEY:?source ~/.config/colabhive/env primero}"
BASE="${COLABHIVE_BASE_URL:-https://api.colabhive.com/v1}"
BUILDER="${COLABHIVE_BUILDER_URL:-https://api.colabhive.com/api/builder/v1}"

# id de endpoint : nombre legible  (los 4 del equipo, ver config/opencode.json)
MODELS=(
  "9a1f0c77-4b2e-4d3a-8f6b-0c2e5a7d120b:gpt-oss-120b (arquitecto)"
  "5d21e32a-3bbb-4040-9c34-3b06c4415b84:gpt-oss-20b (orquestador)"
  "1af07b1f-5832-4451-a61c-76d1fe43115a:Qwen3.8-27B FP8 (coder)"
  "a9aa41f2-b238-4de1-8abf-c58b84eb0331:Qwen3-8B (worker)"
  "f5d76140-5b4d-41c0-88da-dad6d11f341a:Qwen3-Coder-30B (tester)"
)

auth() { printf 'X-API-Key: %s\n' "$COLABHIVE_API_KEY"; }

echo "→ estado actual"
auth | curl -sS -m 60 -H @- "$BUILDER/inference/models?include_readiness=true" \
  | python3 -c '
import json,sys
for m in json.load(sys.stdin)["models"]:
    if m["readiness"] != "cold":
        print(f"   {m[\"model_name\"][:48]:48} {m[\"readiness\"]:7} warm={m[\"warm_nodes\"]}")' || true

for entry in "${MODELS[@]}"; do
  id="${entry%%:*}"; nombre="${entry#*:}"
  printf '→ %s … ' "$nombre"
  start=$(date +%s)
  code=$(printf 'Authorization: Bearer %s\n' "$COLABHIVE_API_KEY" \
    | curl -sS -N -o /dev/null -w '%{http_code}' -m 1800 -H @- \
      -H 'Content-Type: application/json' -H 'Accept: text/event-stream' \
      -d "{\"model\":\"$id\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"stream\":true,\"max_tokens\":4}" \
      "$BASE/chat/completions")
  secs=$(( $(date +%s) - start ))
  if [ "$code" = "200" ]; then
    if [ "$secs" -gt 20 ]; then echo "listo (arrancó en frío, ${secs}s)"; else echo "ya estaba caliente (${secs}s)"; fi
  else
    echo "FALLÓ (HTTP $code, ${secs}s)"
  fi
done
echo "Listo. Los modelos siguen calientes hasta que la plataforma los desaloje;"
echo "para que no pase, hay que fijarlos con scaling_mode=minimum (ver PLAN.md)."
