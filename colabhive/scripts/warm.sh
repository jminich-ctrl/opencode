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

# Los modelos salen de la config de OpenCode, NO de una lista acá. Tenerla a mano
# garantiza que quede vieja: cuando los agentes pasaron a Devstral, este archivo siguió
# calentando el Qwen3-Coder-30B —el que devuelve basura— y dejó frío al que la corrida iba
# a usar. El modelo frío arranca en ~253s, la sonda de plataforma lo consulta con 45s de
# tope, se come el timeout, y la corrida se niega a empezar diciendo «la plataforma no
# responde» con la plataforma arriba. El diagnóstico no se parecía en nada a la causa.
#
# Calentar uno que no se usa no es gratis: tarda, y despertar un modelo desaloja a otro.
# Por eso se calienta exactamente lo que los agentes declaran, ni más ni menos.
CONFIG_OC="${CONFIG_OC:-$HOME/.config/opencode/opencode.json}"
[ -f "$CONFIG_OC" ] || CONFIG_OC="$(dirname "${BASH_SOURCE[0]}")/../config/opencode.json"
[ -f "$CONFIG_OC" ] || { echo "✗ no encuentro la config de opencode ($CONFIG_OC)" >&2; exit 1; }
# Con ids por argumento se calienta ESO y nada más. Es un override explícito, no un default:
# la lista por omisión sigue saliendo de la config por el motivo de arriba. Sirve para calentar
# candidatos que todavía no tiene asignado ningún agente (los de OpenHands, los CodeScout).
#
#   bash warm.sh                          # lo que los agentes declaran
#   bash warm.sh 66a57a2b-... 4fb55ab3-…  # exactamente esos
MODELS=()
if [ "$#" -gt 0 ]; then
  for arg in "$@"; do
    nombre="$(python3 - "$CONFIG_OC" "$arg" <<'PYNOM'
import json, sys
cfg = json.load(open(sys.argv[1]))
m = (cfg.get("provider", {}).get("colabhive", {}).get("models", {}) or {}).get(sys.argv[2])
print((m or {}).get("name", sys.argv[2][:8]).split("·")[0].strip())
PYNOM
)"
    MODELS+=("$arg:${nombre:-${arg:0:8}} (por argumento)")
  done
  echo "→ ${#MODELS[@]} modelo(s) pedidos por argumento"
else
while IFS= read -r linea; do
  [ -n "$linea" ] && MODELS+=("$linea")
done < <(python3 - "$CONFIG_OC" <<'PYLISTA'
import json, sys
cfg = json.load(open(sys.argv[1]))
modelos = cfg.get("provider", {}).get("colabhive", {}).get("models", {})
usos = {}
for agente, v in (cfg.get("agent") or {}).items():
    mid = (v or {}).get("model")
    if mid:
        usos.setdefault(mid.split("/")[-1], []).append(agente)
for mid, agentes in usos.items():
    nombre = (modelos.get(mid) or {}).get("name", mid[:8])
    print(f"{mid}:{nombre.split('·')[0].strip()} ({', '.join(sorted(agentes))})")
PYLISTA
)
echo "→ ${#MODELS[@]} modelo(s) que los agentes usan, según $CONFIG_OC"
fi
[ "${#MODELS[@]}" -gt 0 ] || { echo "✗ no hay modelos para calentar" >&2; exit 1; }

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
