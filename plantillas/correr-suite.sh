#!/usr/bin/env bash
# La ÚNICA forma de correr los tests de este proyecto. La usan el gate (para juzgar) y
# `escribir-tests.sh` (para validar). Que sea una sola no es prolijidad: todo lo que
# difiera entre quien valida y quien juzga produce un test imposible de pasar, y el
# método lo informa como "el test está mal" — acusa al agente de un defecto nuestro.
#
# PLANTILLA. ADAPTAR: el corredor, el PYTHONPATH y cómo se ve una suite vacía.
#
#   bash scripts/correr-suite.sh                        # toda la suite
#   bash scripts/correr-suite.sh tests/test_x.py         # un archivo
#   bash scripts/correr-suite.sh tests/test_x.py::TestX  # una clase
#
# Códigos de salida, y son parte del contrato:
#   0  verde
#   1  rojo
#   2  no corrió ningún test — una suite vacía pasa siempre, así que "no pude verificar"
#      no puede parecerse a "verifiqué"
#   3  falta el corredor — es un defecto del método, no del código que se juzga
#
# El cwd es siempre la raíz del proyecto. Para todos.
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
ls tests/test_*.py >/dev/null 2>&1 || exit 2

if [ -z "$SEL" ]; then
  SALIDA="$($PY -m unittest discover -s tests -t . -q 2>&1)"
else
  # `tests/test_x.py::TestX` → `tests.test_x.TestX`
  MOD="${SEL%%::*}"; MOD="${MOD%.py}"; MOD="${MOD//\//.}"
  CLASE="${SEL#*::}"; [ "$CLASE" = "$SEL" ] && CLASE=""
  SALIDA="$($PY -m unittest "${MOD}${CLASE:+.$CLASE}" 2>&1)"
fi
echo "$SALIDA"
echo "$SALIDA" | grep -qE '^Ran 0 tests' && exit 2
echo "$SALIDA" | grep -qE '^OK' && exit 0
exit 1
