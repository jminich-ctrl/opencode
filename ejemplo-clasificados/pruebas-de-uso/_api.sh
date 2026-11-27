# Levanta la API de este proyecto y deja su base en $URL. Lo usan las pruebas de uso.
# Vive en el PROYECTO y no en el método: el método no sabe con qué se levanta esto.
set -uo pipefail
PROY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROY" || exit 1
PUERTO="${PUERTO:-8123}"
URL="http://127.0.0.1:$PUERTO"
[ -f .entorno ] && { set -a; . ./.entorno; set +a; }
PYTHONPATH="$PROY" .venv/bin/python -m uvicorn backend.app.main:app --port "$PUERTO" \
  > /tmp/pruebadeuso.$$.log 2>&1 &
API_PID=$!
limpiar_api() { kill -TERM "$API_PID" 2>/dev/null; wait "$API_PID" 2>/dev/null; rm -f /tmp/pruebadeuso.$$.log; }
trap limpiar_api EXIT
for _ in $(seq 1 25); do
  curl -fsS -m 2 "$URL/openapi.json" >/dev/null 2>&1 && break
  kill -0 "$API_PID" 2>/dev/null || { echo "la API se murió al arrancar:"; tail -5 /tmp/pruebadeuso.$$.log; exit 1; }
  sleep 1
done
curl -fsS -m 2 "$URL/openapi.json" >/dev/null 2>&1 || { echo "la API no contestó en 25s"; exit 1; }
