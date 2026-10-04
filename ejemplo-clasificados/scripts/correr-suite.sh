#!/usr/bin/env bash
# La ÚNICA forma de correr los tests de este proyecto. La usan el gate (para juzgar) y
# `escribir-tests.sh` (para validar). Que sea una sola no es prolijidad:
#
# El validador corría `python3 -m unittest` desde la raíz del proyecto y el gate corría
# `cd backend && pytest`. Un test de scaffolding que chequeaba `backend/app/datos` fue
# aceptado por el validador y era **imposible de pasar** en el gate, porque ahí la ruta
# resolvía a `backend/backend/app/datos`. Y el mensaje que imprimía el método era "el test
# está mal": acusaba al agente de un defecto nuestro.
#
# Todo lo que puede divergir entre los dos —el directorio de trabajo, el PYTHONPATH, el
# corredor, sus flags— vive acá y en un solo lugar.
#
#   bash scripts/correr-suite.sh                                  # toda la suite
#   bash scripts/correr-suite.sh backend/tests/test_x.py           # un archivo
#   bash scripts/correr-suite.sh backend/tests/test_x.py::TestX    # una clase
#   bash scripts/correr-suite.sh frontend/tests/x.test.ts          # un archivo del frontend
#
# Sale 0 si verde. Sale 2 si no corrió ningún test (una suite vacía pasa siempre, así que
# "no pude verificar" no puede parecerse a "verifiqué"). Sale 3 si falta el corredor.
# El cwd es siempre la raíz del proyecto, para todos.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 3
# El intérprete se resuelve ACÁ, que es de quien corre la suite. En un worktree el venv
# no viaja (está gitignorado) y el runner lo enlaza, así que mirarlo alcanza; si el runner
# pasa PY_PROYECTO, manda eso.
if [ -n "${PY_PROYECTO:-}" ]; then PY="$PY_PROYECTO"
elif [ -x .venv/bin/python ]; then PY=".venv/bin/python"
elif [ -x ../.venv/bin/python ]; then PY="../.venv/bin/python"
else PY="python3"; fi
[ -f .entorno ] && . ./.entorno

SEL="${1:-}"

correr_backend() {
  local sel="${1:-backend/tests}"
  ls backend/tests/test_*.py >/dev/null 2>&1 || return 9   # 9 = no hay nada que correr
  "$PY" -c "import pytest" >/dev/null 2>&1 || { echo "FALTA_CORREDOR pytest en $PY"; return 3; }
  # PYTHONPATH=backend: los tests importan `app.x`, y el paquete vive ahí. Sin esto el
  # import falla y el diagnóstico que sale es "el test está mal".
  PYTHONPATH="$PWD/backend" "$PY" -m pytest -q "$sel" 2>&1
}

correr_frontend() {
  local sel="${1:-}"
  [ -f frontend/package.json ] && grep -q '"vitest"' frontend/package.json 2>/dev/null || return 9
  [ -d frontend/node_modules ] || { echo "FALTA_CORREDOR node_modules (bash \$AGENTES/scripts/preparar-entorno.sh)"; return 3; }
  ( cd frontend && npx --no-install vitest run --reporter=basic ${sel#frontend/} ) 2>&1
}

case "$SEL" in
  "")            # toda la suite: las dos mitades, y basta con que una no tenga tests
    SB="$(correr_backend)"; RB=$?
    SF="$(correr_frontend)"; RF=$?
    [ "$RB" != 9 ] && echo "$SB"
    [ "$RF" != 9 ] && echo "$SF"
    [ "$RB" = 3 ] || [ "$RF" = 3 ] && exit 3
    [ "$RB" = 9 ] && [ "$RF" = 9 ] && exit 2
    { [ "$RB" = 0 ] || [ "$RB" = 9 ]; } && { [ "$RF" = 0 ] || [ "$RF" = 9 ]; } && exit 0
    exit 1 ;;
  *.py|*.py::*)  correr_backend "$SEL"; exit $? ;;
  frontend/*)    correr_frontend "$SEL"; exit $? ;;
  *) echo "no sé cómo correr «$SEL»"; exit 3 ;;
esac
