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

# id de endpoint : nombre legible — los 3 del equipo, ver config/opencode.json.
# Calentar uno que no se usa no es gratis: tarda, y despertar un modelo desaloja a otro.
MODELS=(
  "1af07b1f-5832-4451-a61c-76d1fe43115a:Qwen3.8-27B (arquitecto, plan, reviewer, seguridad)"
  "f5d76140-5b4d-41c0-88da-dad6d11f341a:Qwen3-Coder-30B (ejecutor y los suyos)"
  "5d21e32a-3bbb-4040-9c34-3b06c4415b84:gpt-oss-20b (title, summary, explore)"
)

auth() { printf 'X-API-Key: %s\n' "$COLABHIVE_API_KEY"; }

echo "→ estado actual"
auth | curl -sS -m 60 -H @- "$BUILDER/inference/models?include_readiness=true" \
  | python3 -c '
import json,sys
for m in json.load(sys.stdin)["models"]:
    if m["readiness"] != "cold":
        print("   %-48s %-7s warm=%s" % (m["model_name"][:48], m["readiness"], m["warm_nodes"]))' || true

for entry in "${MODELS[@]}"; do
  id="${entry%%:*}"; nombre="${entry#*:}"
  printf '→ %s … ' "$nombre"
  start=$(date +%s)
  # Tope por modelo: sin esto, un modelo que la plataforma no despacha cuelga el script
  # para siempre. Nos pasó: dos procesos 16 minutos esperando algo que nunca llegó.
  code=$(printf 'Authorization: Bearer %s\n' "$COLABHIVE_API_KEY" \
    | curl -sS -N -o /dev/null -w '%{http_code}' -m "${TOPE_POR_MODELO:-1800}" -H @- \
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

# Verificación final: despertar un modelo puede desalojar a otro (lo medimos: al despertar
# el reviewer perdimos el arquitecto). No alcanza con pedir la carga; hay que confirmarla.
echo
echo "→ verificando que sigan todos arriba"
FRIOS="$(auth | curl -sS -m 30 -H @- "$BUILDER/inference/models?include_readiness=true" \
  | python3 "$(dirname "${BASH_SOURCE[0]}")/_status.py" || true)"
echo "$FRIOS"
if echo "$FRIOS" | grep -qE '○|◐'; then
  echo
  echo "⚠ Quedaron modelos fríos. Si están anclados (bash scripts/anclar.sh estado),"
  echo "  la plataforma NO los repone sola: hay que volver a correr este script."
fi
