#!/usr/bin/env bash
# La ÚNICA forma de correr los tests de este proyecto. La usan el gate (para juzgar) y
# `escribir-tests.sh` (para validar). Que sea una sola no es prolijidad: todo lo que
# difiera entre quien valida y quien juzga produce un test imposible de pasar, y el método
# lo informa como "el test está mal" — acusa al agente de un defecto nuestro.
#
#   bash scripts/correr-suite.sh                         # toda la suite
#   bash scripts/correr-suite.sh tests/test_x.py         # un archivo
#   bash scripts/correr-suite.sh tests/test_x.py::TestX  # una clase
#
# **Los códigos de salida son contrato**, y nada fuera de él sale de acá:
#
#   0  verde
#   1  rojo
#   2  no corrió ningún test — una suite vacía pasa siempre, así que "no pude verificar"
#      no puede parecerse a "verifiqué"
#   3  falta el corredor — es un defecto del método o del plan, no del código que se juzga
#
# Hacerlo cumplir es la mitad del trabajo de este archivo: pytest devuelve 4 cuando no
# encuentra el archivo y 5 cuando no colecta nada, y los dos se escapaban del contrato. El
# gate los caía en "la suite está en rojo" y el validador en "el test está mal": dos
# diagnósticos falsos para situaciones que el contrato ya sabe nombrar.
#
# El cwd es siempre la raíz del proyecto. Para todos.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 3
# El intérprete se resuelve ACÁ, que es de quien corre la suite. En un worktree el venv no
# viaja (está gitignorado) y el runner lo enlaza, así que mirarlo alcanza; si el runner pasa
# PY_PROYECTO, manda eso.
if [ -n "${PY_PROYECTO:-}" ]; then PY="$PY_PROYECTO"
elif [ -x .venv/bin/python ]; then PY=".venv/bin/python"
elif [ -x ../.venv/bin/python ]; then PY="../.venv/bin/python"
else PY="python3"; fi
[ -f .entorno ] && . ./.entorno

SEL="${1:-}"

# Sentinelas internos, que NO salen de este archivo: 8 falta el corredor, 9 no hay
# nada que correr. Todo lo demás se traduce en `salir`.
correr_suite() {
  local sel="${1:-}" salida rc mod="" clase=""
  ls tests/test_*.py >/dev/null 2>&1 || return 9
  if [ -z "$sel" ]; then
    salida="$("$PY" -m unittest discover -s tests -t . -q 2>&1)"; rc=$?
  else
    # `tests/test_x.py::TestX` → `tests.test_x.TestX`
    mod="${sel%%::*}"; mod="${mod%.py}"; mod="${mod//\//.}"
    clase="${sel#*::}"; [ "$clase" = "$sel" ] && clase=""
    salida="$("$PY" -m unittest "${mod}${clase:+.$clase}" 2>&1)"; rc=$?
  fi
  echo "$salida"
  echo "$salida" | grep -qE '^Ran 0 tests' && return 9
  # El módulo QUE PEDIMOS no existe: no hay nada que correr. Acotado al selector a
  # propósito: un ModuleNotFoundError cualquiera es un test que falla por un import roto
  # —justo lo que pasa en tests-first, cuando el test existe y su implementación todavía
  # no—, y tratarlo como "no corrió nada" tapaba la suite entera.
  if [ -n "$sel" ]; then
    echo "$salida" | grep -qE "No module named '?${mod:-@@nada@@}" && return 9
  fi
  echo "$salida" | grep -qE '^OK' && return 0
  [ "$rc" = "0" ] && return 0
  return 1
}

# Las fallas actuales, normalizadas, una por línea. No es un veredicto: es una consulta, y
# sale 0 siempre.
#
# Existe porque el método es tests-first: mientras una etapa está en vuelo, el tronco tiene
# los tests de varias tareas y la implementación de ninguna. Si el gate de cada tarea
# exigiera la suite entera en verde, **ninguna tarea podría cerrar**: la vería roja por los
# tests de sus hermanas. El runner guarda esta lista al crear el worktree, antes de que el
# agente toque nada, y el gate culpa sólo por las fallas NUEVAS — la misma regla que
# `integrar.sh` ya usa para los merges, un nivel más abajo.
fallas() {
  local salida
  salida="$(correr_suite 2>&1)"
  echo "$salida" | grep -oE '^(FAIL|ERROR): [^ ]+ \([^)]*\)' | sed 's/^/ /;s/^ //' | sort -u
}

# Traduce los sentinelas al contrato y sale. Es el único punto de salida del script.
salir() {
  case "$1" in
    8) echo "FALTA_CORREDOR — lo declara una tarea del plan, no el agente que escribe el test"
       exit 3 ;;
    9) exit 2 ;;
    0|1|2|3) exit "$1" ;;
    *) exit 1 ;;
  esac
}

if [ "$SEL" = "--fallas" ]; then fallas; exit 0; fi

correr_suite "$SEL"
salir $?
