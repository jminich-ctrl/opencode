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
  local salida_pytest
  # `--continue-on-collection-errors`: SIN esto, un solo error de colección hace que pytest
  # no corra NINGÚN test, y la salida informa ese error y nada más.
  #
  # En un método tests-first eso no es un caso raro: es el caso NORMAL. Al empezar una etapa
  # el tronco tiene los tests de todas sus tareas y la implementación de ninguna, así que al
  # menos un archivo de test no se puede importar. Resultado: la LÍNEA BASE venía truncada
  # en todas las etapas, siempre, y registraba una sola falla donde había cuatro.
  #
  # Cadáver del 2026-10-21, y es caro: la línea base de T05a decía
  #     ERROR backend/tests/test_ads_datos.py
  # y nada más. Cuando el agente implementó `ads.py` la colección pasó a funcionar y las 3
  # fallas preexistentes aparecieron por PRIMERA vez, así que el gate las leyó como nuevas y
  # acusó a la tarea de «rompiste tests que andaban antes» — tests de registro de usuarios,
  # que T05a no toca. Dos intentos, punto muerto y el plan detenido.
  #
  # Verificado a mano: con un error de colección puesto, `--fallas` informaba 1 falla; sin
  # él, 3. Mismo árbol, misma base de datos.
  salida_pytest="$(PYTHONPATH="$PWD/backend" "$PY" -m pytest -q --continue-on-collection-errors "$sel" 2>&1)"
  rc=$?
  printf '%s\n' "$salida_pytest"
  # Los códigos de pytest, traducidos al contrato. 5 es "no collected" = no corrió nada.
  #
  # El 4 es ambiguo y ahí estaba el defecto: pytest lo usa tanto para «el archivo que me
  # pediste no existe» (⊘ de verdad) como para «lo encontré y NO PUDE COLECTARLO porque su
  # import falla» — que con un selector acotado a UN archivo es exactamente la señal que se
  # busca: la implementación no está. Mapear los dos a ⊘ hacía que un ítem cuya
  # implementación es un archivo nuevo nunca pudiera establecer su estado rojo.
  # Medido al congelar el banco: dos ítems caían por esto.
  #
  # El discriminador es la salida: «ERROR <ruta>» con un error de colección significa que el
  # archivo está y falló; «file or directory not found» significa que no está.
  if [ "$rc" = "4" ]; then
    if echo "$salida_pytest" | grep -qE '^ERROR [^ ]+\.py|error[s]? in [0-9.]+s'; then
      return 1        # lo encontró y falló al colectar: es una falla, no un ⊘
    fi
    return 9          # no lo encontró: no se pudo medir
  fi
  case "$rc" in
    0) return 0 ;;
    5) return 9 ;;
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
  # Un archivo de test que FALLÓ es una falla (1), no un «no pude medir» (9) — aunque vitest
  # diga «Tests  no tests» en la misma salida.
  #
  # Pasó así: sin la implementación, vitest no puede transformar el archivo de test porque su
  # import no resuelve, y entonces imprime `Test Files  1 failed (1)` Y `Tests  no tests`. El
  # grep de abajo matcheaba «no tests» ANTES de mirar si algo falló, así que la señal más
  # fuerte que existe —la implementación no está— se informaba como ⊘. Medido al congelar el
  # banco: siete ítems de frontend cayeron por esto, y en el gate el paso 4 habría dado ⊘
  # donde correspondía un rojo que distingue.
  #
  # El orden importa: primero «¿falló algo?», después «¿corrió algo?».
  # Antes que nada: ¿falló el CORREDOR o fallaron los TESTS? Un toolchain roto no es un
  # defecto del código que se juzga, y mezclarlos se lo cobra al agente.
  #
  # Medido: el mismo selector da 0 desde una shell y «no corrió ningún test» desde un
  # subproceso, porque esbuild está instalado para otra arquitectura (`@esbuild/darwin-arm64`
  # presente y el node de turno necesita `darwin-x64`). vitest no llega ni a cargar su config,
  # y eso salía como 2: «la suite no corrió nada», culpando al proyecto.
  if echo "$salida" | grep -qE 'failed to load config|installed esbuild for another platform|Cannot find module|ERR_MODULE_NOT_FOUND'; then
    echo "     ⊘ el corredor del frontend no pudo arrancar: es del entorno, no del código"
    return 8
  fi
  echo "$salida" | grep -qE '^ *Test Files +[0-9]+ failed|[0-9]+ failed \(' && return 1
  # Y si NINGÚN test se ejecutó, no se verificó nada — aunque vitest salga con 0.
  #
  # Éste era el peor: con `-t <nombre>` que no matchea nada, vitest SALTEA todo y sale 0, así
  # que el corredor devolvía 0 = «los tests pasan». Una clase inexistente se informaba como
  # suite verde. En el paso 4 del gate eso da «los tests PASAN con la implementación vieja»
  # —culpando al test— y en el validador de escribir-tests.sh, «pasa con la implementación».
  # La salida lo dice: `Tests  3 skipped (3)`, sin un solo «passed».
  #
  # La regla, en una línea: la línea `Tests` tiene que decir «passed». Si dice sólo «skipped»
  # o «no tests», no corrió nada y es ⊘.
  if ! echo "$salida" | grep -qE '^ *Tests +.*[0-9]+ passed'; then
    echo "     ⊘ ningún test se ejecutó con ese selector: no se verificó nada"
    return 9
  fi
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
  local sb sf rb rf
  sb="$(correr_backend 2>&1)"; rb=$?
  sf="$(correr_frontend 2>&1)"; rf=$?
  {
    # pytest nombra la ruta desde la raíz del proyecto: se toma tal cual.
    printf '%s\n' "$sb" | grep -oE '^(FAILED|ERROR) [^ ]+' | sed 's/ *$//'
    # vitest, dos causas independientes, las dos medidas:
    #
    #  1. padea la etiqueta a DOS espacios y no siempre pone el `>`. Las formas reales, de
    #     logs de este repo: « FAIL  tests/x.test.ts [ tests/x.test.ts ]» y
    #     « FAIL  tests/x.test.ts > TestX > caso». El patrón viejo pedía un espacio y un `>`
    #     obligatorio: no capturaba NINGUNA. (Y el sed va con -E: el `\|` de BRE no existe
    #     en el sed de BSD, que es el de esta Mac — tercera vez en el día que muerde.)
    #  2. corre con `--root frontend`, así que imprime las rutas RELATIVAS a frontend/
    #     (`tests/x.test.ts`) mientras la tarea declara `frontend/tests/x.test.ts`. Sin el
    #     prefijo, el `grep -F "$ruta_t"` del gate no puede matchear nunca.
    #
    # Con las dos, las 15 tareas de frontend de clasificados no podían dar rojo en el paso 1
    # del gate — y 8 de ellas ya están marcadas hechas. El guardia que lo vuelve durable está
    # en el gate: un extractor vacío contra una suite en rojo ahora es ROJO, no verde.
    printf '%s\n' "$sf" \
      | grep -oE '^ *(FAIL|×)[[:space:]]+[^ ]+' \
      | sed -E 's/^ *//; s/^(FAIL|×)[[:space:]]*//; s/ *$//' \
      | grep . | sed 's#^#frontend/#'
    # Una mitad que no se puede correr también es una falla de la línea base. Pasó: el test
    # de T30 entró al tronco antes que su package.json con vitest, así que el frontend no
    # tenía corredor, y el gate reprobaba a T02 y T03 —tareas de backend— por eso.
    [ "$rb" = 8 ] && echo "FALTA_CORREDOR backend"
    [ "$rf" = 8 ] && echo "FALTA_CORREDOR frontend"
  } | sort -u
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
