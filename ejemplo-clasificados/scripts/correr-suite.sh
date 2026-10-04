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
# corredor, sus flags, los códigos de salida— vive acá y en un solo lugar.
#
#   bash scripts/correr-suite.sh                                  # toda la suite
#   bash scripts/correr-suite.sh backend/tests/test_x.py           # un archivo
#   bash scripts/correr-suite.sh backend/tests/test_x.py::TestX    # una clase
#   bash scripts/correr-suite.sh frontend/tests/x.test.ts          # un archivo del frontend
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
# encuentra el archivo y 5 cuando no colecta nada, y los dos se escapaban. El gate caía en
# "la suite está en rojo" y el validador en "el test está mal": dos diagnósticos falsos
# para situaciones que el contrato ya sabe nombrar.
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

# Sentinelas internos, que NO salen de este archivo: 8 falta el corredor, 9 esta mitad no
# tiene nada que correr. El 9 existe para poder combinar backend y frontend cuando se pide
# la suite entera.
correr_backend() {
  local sel="${1:-backend/tests}" rc
  ls backend/tests/test_*.py >/dev/null 2>&1 || return 9
  "$PY" -c "import pytest" >/dev/null 2>&1 || { echo "falta pytest en $PY"; return 8; }
  # PYTHONPATH=backend: los tests importan `app.x`, y el paquete vive ahí. Sin esto el
  # import falla y el diagnóstico que sale es "el test está mal".
  PYTHONPATH="$PWD/backend" "$PY" -m pytest -q "$sel" 2>&1
  rc=$?
  # Los códigos de pytest, traducidos al contrato. 4 es "usage error" (el archivo que le
  # pedimos no existe) y 5 es "no collected": las dos son "no corrió ningún test".
  case "$rc" in
    0) return 0 ;;
    4|5) return 9 ;;
    *) return 1 ;;
  esac
}

correr_frontend() {
  local sel="${1:-}" archivo="" filtro="" salida rc
  [ -f frontend/package.json ] || return 9
  grep -q '"vitest"' frontend/package.json 2>/dev/null || {
    # No es "no hay nada que correr": es que no hay CON QUÉ. La diferencia importa cuando
    # el archivo de test existe, y pasó: T30 escribió un package.json de Vite + React sin
    # vitest, y el plan le asigna catorce `.test.ts`.
    ls frontend/tests/*.test.* >/dev/null 2>&1 || return 9
    echo "hay tests en frontend/tests y el package.json no declara vitest"
    return 8; }
  [ -x frontend/node_modules/.bin/vitest ] || { echo "falta vitest en frontend/node_modules"; return 8; }
  # `ruta::clase` es un selector de pytest; vitest no lo entiende y no encuentra el archivo.
  # Acá se traduce: el archivo es el selector y el nombre va por `-t`. Sin esto, toda tarea
  # de frontend se rechazaba con "el test no pasa ni con la implementación del agente".
  if [ -n "$sel" ]; then
    archivo="${sel%%::*}"
    filtro="${sel#*::}"; [ "$filtro" = "$sel" ] && filtro=""
  fi
  # `--root frontend` desde la RAÍZ DEL PROYECTO, y no `cd frontend && vitest`: con el cd,
  # el `process.cwd()` de los tests es `frontend/` y un test que abre `frontend/package.json`
  # busca `frontend/frontend/package.json`. Es exactamente el mismo defecto que teníamos en
  # el backend —`backend/backend/app/datos`— y la misma regla lo arregla: **el cwd de la
  # suite es la raíz del proyecto, para todos**. Con --root, vitest resuelve su config en
  # frontend/ y deja el cwd en la raíz; medido.
  #
  # El binario directo en vez de `npx`: npx busca en el node_modules del cwd, que ahora es
  # la raíz, y ahí no está.
  salida="$( frontend/node_modules/.bin/vitest run --root frontend --reporter=basic \
               ${archivo:+"$archivo"} ${filtro:+-t "$filtro"} 2>&1 )"
  rc=$?
  echo "$salida"
  # Una suite que no corrió nada no es una suite verde, y vitest lo dice con texto.
  echo "$salida" | grep -qE 'No test files found|No test found|no tests' && return 9
  [ "$rc" = "0" ] && return 0
  return 1
}

# Las fallas actuales, normalizadas, una por línea. No es un veredicto: es una consulta, y
# sale 0 siempre.
#
# Existe porque el método es tests-first: mientras una etapa está en vuelo, el tronco tiene
# los tests de varias tareas y la implementación de ninguna. Si el gate de cada tarea
# exigiera la suite entera en verde, **ninguna tarea podría cerrar**: la vería roja por los
# tests de sus hermanas. Y peor con pytest, que interrumpe la colección ante un ImportError
# y entonces una sola tarea sin implementar esconde a todas las demás.
#
# El runner guarda esta lista al crear el worktree, antes de que el agente toque nada, y el
# gate culpa sólo por las fallas NUEVAS. Es la misma regla que `integrar.sh` ya usa para los
# merges, aplicada un nivel más abajo.
fallas() {
  local salida
  salida="$( { correr_backend; correr_frontend; } 2>&1 )"
  echo "$salida" \
    | grep -oE '^(FAILED|ERROR) [^ ]+|^ *(FAIL|×) [^ ]+ *>[^>]*' \
    | sed 's/^ *//; s/ *$//' | sort -u
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

case "$SEL" in
  "")
    SB="$(correr_backend)"; RB=$?
    SF="$(correr_frontend)"; RF=$?
    [ "$RB" != 9 ] && [ -n "$SB" ] && echo "$SB"
    [ "$RF" != 9 ] && [ -n "$SF" ] && echo "$SF"
    # Si a alguna le falta el corredor, eso manda: es un defecto del método, y verlo importa
    # más que el veredicto de la otra mitad.
    { [ "$RB" = 8 ] || [ "$RF" = 8 ]; } && salir 8
    { [ "$RB" = 9 ] && [ "$RF" = 9 ]; } && salir 9
    { [ "$RB" = 0 ] || [ "$RB" = 9 ]; } && { [ "$RF" = 0 ] || [ "$RF" = 9 ]; } && salir 0
    salir 1 ;;
  *.py|*.py::*)   correr_backend "$SEL";  salir $? ;;
  frontend/*)     correr_frontend "$SEL"; salir $? ;;
  *) echo "no sé cómo correr «${SEL}»: declaralo en el plan con una extensión que el método"
     echo "sepa ejecutar (.py o .test.ts)"
     salir 8 ;;
esac
