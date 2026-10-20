#!/usr/bin/env bash
# Gate G1: decide si una tarea está terminada. No opina, ejecuta.
#   1) tests   2) alcance   3) higiene
# Verde => imprime "GATE VERDE". Cualquier rojo => sale con código 1.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
FALLOS=0
# Los chequeos que el MÉTODO provee, no el proyecto. Estaban copiados en cada proyecto y en
# la plantilla —`_imports.py` y `_suprimidas.py`, idénticos byte a byte en las tres copias—,
# así que cada arreglo había que escribirlo tres veces y dos veces una copia quedó atrás (la
# auditoría del 2026-10-19 encontró las dos).
#
# La cadena de búsqueda, en orden y sin silencios:
#   1. `$AGENTES`, que el runner exporta desde `_comun.sh`;
#   2. la raíz del repo, para cuando el proyecto vive dentro del repo del método (los dos
#      ejemplos) y alguien corre el gate a mano;
#   3. `scripts/` del propio proyecto, para un proyecto que se lo llevó aparte.
# Si no está en ninguna, el paso que lo necesita da ROJO y dice que es del método: un chequeo
# que no se encuentra no es un chequeo que pasa.
aux_del_metodo() {
  local n="$1" c
  for c in "${AGENTES:+$AGENTES/scripts/$n}" \
           "$(git rev-parse --show-toplevel 2>/dev/null)/scripts/$n" \
           "scripts/$n"; do
    case "$c" in /scripts/*|"") continue ;; esac
    [ -f "$c" ] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

VACIOS=0
rojo() { echo "  ✗ $1"; FALLOS=$((FALLOS+1)); }
verde() { echo "  ✓ $1"; }
# Un chequeo que no pudo correr NO es un chequeo que pasó. Marcarlo distinto es la defensa
# publicada contra la clase de falla que más veces nos mordió: un pase vacío se ve igual que
# un pase, y por eso cuatro bugs de rutas vivieron semanas detrás de un ✓.
vacuo() { echo "  ⊘ $1 — no pudo verificarse"; VACIOS=$((VACIOS+1)); }
# Lo que el chequeo miró. Sin esto, "no encontré nada" y "no miré nada" se ven igual.
testigo() { echo "     · inspeccionó: $1"; }

# Punto de partida del diff. Lo escribe el runner al crear el worktree, ANTES de que el
# agente toque nada: si lo dedujéramos acá, el primer commit del agente movería la base y
# los pasos 0 y 2 dejarían de ver sus propios cambios.
RAIZ_WT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -f "$RAIZ_WT/.base-ref" ]; then
  BASE_REF="$(cat "$RAIZ_WT/.base-ref")"; ORIGEN_BASE="fijada por el runner en .base-ref"
else
  BASE_REF="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD)"
  ORIGEN_BASE="deducida (no había .base-ref)"
fi
echo "base del diff: ${BASE_REF:0:12} — $ORIGEN_BASE"

# ── 0. Integridad (solo en modo tarea)
# El gate y los tests viven dentro del worktree del agente, así que son editables.
# Esta lista NO sale del archivo de tarea: un agente que puede ampliarse el alcance
# deja de estar limitado por él. Medido en la literatura y acá: pedirlo por prompt no
# alcanza, el límite tiene que ser un comando que corre alguien más.
INTOCABLES='^(tests/|scripts/)'
if [ -n "${TAREA:-}" ]; then
  echo "── 0. Integridad"
  TOCADO="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null | grep -E "$INTOCABLES" || true)"
  if [ -n "$TOCADO" ]; then
    rojo "tocó archivos intocables (tests o el propio gate):"; echo "$TOCADO" | sed 's/^/     /'
  else
    verde "tests y scripts intactos"
  fi
fi

echo "── 1. Tests"
# El gate NO sabe cómo se corre la suite: lo sabe `scripts/correr-suite.sh`, y es el mismo
# comando que usa el validador de `escribir-tests.sh`. Esa separación no es prolijidad.
# Mientras cada uno tenía su propia invocación, diferían en cuatro cosas a la vez —el
# directorio de trabajo, el PYTHONPATH, el corredor y sus flags— y **cada diferencia
# producía un test imposible de pasar** que el método informaba como "el test está mal":
# acusaba al agente de un defecto nuestro.
#
# Los códigos de salida son contrato: 0 verde, 1 rojo, 2 no corrió ningún test, 3 falta el
# corredor. Los tres últimos son ROJO, y el 3 dice que el defecto es del método.
SALIDA="$(bash scripts/correr-suite.sh 2>&1)"; RC=$?

# En modo tarea el veredicto se mide contra una LÍNEA BASE. El método es tests-first: al
# empezar la etapa el tronco tiene los tests de todas sus tareas y la implementación de
# ninguna, así que la suite entera no puede estar verde y exigirlo haría que ninguna tarea
# pudiera cerrar. Lo que se exige es lo que esta tarea sí controla:
#   · sus propios tests pasan, y
#   · ningún test que andaba antes dejó de andar.
# La línea base la escribe el runner al crear el worktree, antes de que el agente toque
# nada. Misma regla que `integrar.sh` usa para los merges, un nivel más abajo.
# Qué archivo y clase de test declara la tarea. UN solo lector para UNA sola declaración:
# antes el paso 1 la leía con un patrón y el paso 4 con otro (o no la leía). La declaración
# canónica, en el marcador de fase del archivo de tarea:
#     Archivo: `<ruta>`, clase `<Clase>`.
# Devuelve «ruta clase», o vacío si la tarea no la declara.
test_de_la_tarea() {
  # Sin anclar en «Archivo:»: la declaración aparece en dos formas en el repo,
  #     Archivo: `backend/tests/test_errores.py`, clase `TestErrores`.
  #     (`tests/test_juego.py`, clase `TestFruta`)
  # y lo que la identifica es la ruta y la clase juntas, no el prefijo. Anclar en «Archivo:»
  # perdía T16; anclar en `tests/` perdía las 31 de clasificados, cuyas rutas son
  # `backend/tests/` y `frontend/tests/`. Con esto: 34 de 50 tareas acotables, contra 3.
  sed -n 's/.*`\([^`]*\)`, *clase `\([A-Za-z0-9_]*\)`.*/\1 \2/p' \
    "tareas/${TAREA}"-*.md 2>/dev/null | head -1
}

veredicto_con_linea_base() {
  local base_f ahora mios nuevas esperado ruta_t
  ahora="$(bash scripts/correr-suite.sh --fallas 2>/dev/null | sort -u)"
  base_f="$(sort -u .tests-base 2>/dev/null)"
  nuevas="$(comm -13 <(printf '%s\n' "$base_f") <(printf '%s\n' "$ahora") | grep . || true)"

  # Si la suite dice ROJO y el extractor no entendió NADA de su salida, juzgar con una lista
  # vacía es juzgar nada: `mios` y `nuevas` salen vacíos y el veredicto es VERDE. Pasó con
  # vitest: `fallas()` enumeraba formatos de línea de falla y el de vitest lleva dos espacios
  # donde el patrón pedía uno, así que las 15 tareas de frontend de clasificados no podían
  # dar rojo acá. La evidencia es de un log real: en T11 el agente murió sin tocar un archivo
  # y este paso escribió «✓ los tests de T11 pasan … y <su test> en verde».
  #
  # Esto es lo que vuelve durable el arreglo: el patrón se puede volver a quedar corto —toda
  # lista de formatos envejece—, pero un extractor que devuelve vacío contra una suite en
  # rojo ya no puede pasar por verde.
  if [ "${RC:-0}" != "0" ] && [ -z "$(printf '%s' "$ahora" | grep . || true)" ]; then
    rojo "la suite da rojo y el extractor de fallas no entendió su salida: no hay con qué juzgar"
    echo "     Un extractor que devuelve vacío con la suite en rojo vuelve VERDE a toda tarea."
    echo "     Arreglá \`fallas()\` en scripts/correr-suite.sh. Lo que la suite dijo:"
    printf '%s\n' "$SALIDA" | tail -5 | sed 's/^/       /'
    return
  fi

  esperado="$(test_de_la_tarea | cut -d' ' -f1)"
  ruta_t="${esperado:-}"
  # Los ids vienen en dos formatos según el corredor: pytest nombra el archivo
  # (`FAILED backend/tests/test_x.py::TestX::test_y`) y unittest nombra el módulo
  # (`FAIL: test_y (tests.test_x.TestX.test_y)`). Buscamos las dos formas, o el chequeo
  # pasa por alto justo lo que no puede pasar por alto: los tests de la propia tarea.
  if [ -n "$ruta_t" ]; then
    local mod_t
    mod_t="$(echo "${ruta_t%.py}" | tr / .)"
    mios="$(printf '%s\n' "$ahora" | grep -F -e "$ruta_t" -e "$mod_t" || true)"
  else
    mios=""
  fi

  # ¿Falta el corredor de LA MITAD donde vive el test de esta tarea? Entonces sus tests no
  # corrieron y no hay con qué juzgarla. La línea base de `FALTA_CORREDOR` no nombra ninguna
  # ruta de test, así que `mios` queda vacío POR CONSTRUCCIÓN y el veredicto salía:
  #     ✓ los tests de T02 pasan; sigue fallando sólo lo de la línea base (tests-first)
  # con CERO tests ejecutados. El comentario de la rama que llega acá afirma «la regla sigue
  # exigiendo que SUS tests pasen»: no podía, no tenía con qué.
  #
  # Y no es rojo a secas: si falta el corredor del frontend, los tests de una tarea de
  # backend SÍ corrieron. Ése era el cadáver original —el gate reprobando a T02 y T03 porque
  # el package.json de T30 no había aterrizado—, así que el veredicto depende de la mitad.
  if [ -n "$ruta_t" ] || true; then
    local mitad=""
    case "${ruta_t:-}" in frontend/*) mitad="frontend" ;; backend/*) mitad="backend" ;; esac
    if printf '%s\n%s\n' "$ahora" "$base_f" | grep -q "FALTA_CORREDOR${mitad:+ $mitad}"; then
      rojo "falta el corredor de ${mitad:-la suite}${ruta_t:+, que es donde vive $ruta_t}: sus tests no corrieron"
      echo "     Cero tests de $TAREA se ejecutaron: no hay con qué juzgarla. Un ⊘ no es un pase."
      echo "     Es del método y no del código: bash \$AGENTES/scripts/preparar-entorno.sh"
      return
    fi
  fi

  if [ -n "$mios" ]; then
    rojo "los tests de $TAREA siguen fallando:"
    printf '%s\n' "$mios" | head -5 | sed 's/^/     /'
    # Y POR QUÉ fallan, no sólo cuáles. Sin esta línea el reintento recibía «ERROR
    # test_errores.py» y volvía a escribir el mismo código: la causa real era de una línea
    # —`from fastapi import RequestValidationError`, que vive en `fastapi.exceptions`— y
    # estaba en la salida de la suite, que el gate no mostraba. Dos intentos por un dato
    # que ya teníamos. Es la tercera vez que esta lección aparece en otro lugar del método.
    PRIMER_ERROR="$(printf '%s\n' "$SALIDA" \
      | grep -m2 -E '^E +|(Import|Module|Attribute|Type|Name|Assertion|Value)Error|^ *>? *assert ' \
      | sed 's/^ *//' | tr '\n' ' ' | cut -c1-200)"
    [ -n "$PRIMER_ERROR" ] && echo "     por qué falla: $PRIMER_ERROR"
    return
  fi
  if [ -n "$nuevas" ]; then
    rojo "rompiste tests que andaban antes de esta tarea:"
    printf '%s\n' "$nuevas" | head -5 | sed 's/^/     /'
    return
  fi
  if [ -n "$base_f" ]; then
    verde "los tests de $TAREA pasan; sigue fallando sólo lo de la línea base (tests-first)"
    testigo "$(printf '%s\n' "$base_f" | grep -c . ) falla(s) de línea base, 0 nuevas${ruta_t:+, y $ruta_t en verde}"
  else
    verde "los tests de $TAREA pasan y nada más falla"
    testigo "${ruta_t:-la suite entera} contra una línea base vacía"
  fi
}

# Un test DECLARADO Y AUSENTE es un rojo, no un verde — y va antes del `case` porque no
# depende de cómo salió la suite: con la suite entera en verde, el caso 0 también pasaba.
#
# El veredicto por línea base se mide contra las fallas que MENCIONAN el archivo declarado:
# si el archivo no existe, no hay fallas que lo mencionen, así que no hay rojo. Y el testigo
# llegaba a afirmar «y <ruta> en verde», nombrando algo que no está en el árbol: un veredicto
# que no puede fallar Y que afirma algo falso.
#
# Pasó el 2026-10-19 con T14, T20 y T28 de clasificados: un salteo de etapa hizo que se
# implementaran sin que nadie escribiera sus tests, y las tres cerraron en VERDE e
# integraron. La de T14 ni se podía importar —`from .conexion import get_db_connection`, que
# no existe— y nadie se enteró hasta que la tarea siguiente se rompió contra ella.
RUTA_DECLARADA="$(test_de_la_tarea | cut -d' ' -f1)"
JUZGABLE=1
if [ -n "${TAREA:-}" ] && [ -n "$RUTA_DECLARADA" ] && [ ! -f "$RUTA_DECLARADA" ]; then
  rojo "la tarea declara el test \`$RUTA_DECLARADA\` y no está en el árbol: no hay con qué juzgarla"
  echo "     Un test declarado y ausente no es un test que pasa. Se escribe primero:"
  echo "       bash \$AGENTES/scripts/escribir-tests.sh $TAREA"
  JUZGABLE=0
fi
if [ "$JUZGABLE" = 1 ]; then
case "$RC" in
  0) # TODAS las cuentas, no la última: con dos mitades, `tail -1` mostraba "3 passed"
     # del frontend y escondía los 13 del backend. Un resumen que informa una parte del
     # trabajo como si fuera todo es la clase de dato que hace confiar de más.
     RESUMEN="$(echo "$SALIDA" \
                | grep -oE '^[0-9]+ (passed|failed)[^,]*|^Ran [0-9]+ tests?[^,]*|Tests +[0-9]+ passed' \
                | sed 's/  */ /g' | tr '\n' ';' | sed 's/;/ · /g; s/ · $//')"
     verde "${RESUMEN:-$(echo "$SALIDA" | grep -E '^Ran |^OK' | tail -1)}"
     testigo "scripts/correr-suite.sh, el mismo comando que valida los tests" ;;
  2) rojo "la suite no corrió ningún test: sin tests no hay gate"
     echo "$SALIDA" | tail -5 | sed 's/^/     /' ;;
  3) if [ -n "${TAREA:-}" ] && [ -f .tests-base ] && grep -q FALTA_CORREDOR .tests-base; then
       # Ya faltaba antes de esta tarea: es la línea base, no su culpa. Pasa por la misma
       # regla que el resto, que además exige que SUS tests pasen.
       veredicto_con_linea_base
     else
       rojo "falta el corredor de tests — esto es del método, no del código que se juzga"
       echo "$SALIDA" | tail -5 | sed 's/^/     /'
       echo "     bash \$AGENTES/scripts/preparar-entorno.sh"
     fi ;;
  127) rojo "no existe scripts/correr-suite.sh: el proyecto no declara cómo se corre su suite"
     echo "     Copiala de plantillas/correr-suite.sh y adaptala. Sin ella, quien valida los"
     echo "     tests y quien los juzga vuelven a inventar cada uno su comando." ;;
  *) if [ -n "${TAREA:-}" ] && [ -f .tests-base ]; then
       veredicto_con_linea_base
     else
       rojo "la suite está en rojo"
       echo "$SALIDA" | tail -15 | sed 's/^/     /'
     fi ;;
esac
fi

echo "── 2. Alcance${TAREA:+ (tarea $TAREA)}"
# archivos modificados respecto del punto de partida de la rama
# La infraestructura del runner no es parte del trabajo de la tarea: se filtra ACÁ y no en
# el .gitignore de cada proyecto, porque olvidarse de una línea del .gitignore ponía en rojo
# toda tarea (`.base-ref` es un archivo que escribe el propio runner).
# Las dependencias instaladas (.venv, node_modules) entran por la misma razón: las
# instala el método antes de lanzar al agente, y AGENTS.md le prohíbe correr pip o npm.
# Si aparecieran en el diff, el gate pondría ROJO por «archivos generados» a la tarea
# que declaró bien su manifiesto. Depender de una línea del .gitignore del worktree no
# alcanza: el worktree se crea de HEAD, y un .gitignore arreglado después no viaja.
INFRA='^(\.base-ref|\.tests-base|\.tarea\.log|\.segundos|\.plan\.log|\.opencode-data/|\.metricas/|\.venv(/|$)|\.entorno$|\.mysql(/|$)|([A-Za-z0-9_-]+/)?node_modules(/|$)|([A-Za-z0-9_-]+/)?package-lock\.json$)'
CAMBIADOS="$( { git diff --name-only --relative "$BASE_REF" 2>/dev/null; git ls-files --others --exclude-standard; } | grep -vE "$INFRA" || true)"
if [ -z "$CAMBIADOS" ] && [ -n "${TAREA:-}" ]; then
  rojo "no hay ningún cambio: la tarea no se hizo"
elif [ -z "$CAMBIADOS" ]; then
  verde "árbol limpio (modo integración)"
else
  echo "$CAMBIADOS" | sed 's/^/     /' | sort -u
  # El alcance sale del archivo de la tarea, no de reglas hardcodeadas acá: una regla
  # escrita a mano queda vieja en cuanto el plan crece (nos pasó con render.py y T12).
  PERMITIDOS="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/${TAREA:-}"-*.md 2>/dev/null \
                | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+(\.[A-Za-z0-9]+|/)' | sort -u)"
  if [ -n "${TAREA:-}" ] && [ -z "$PERMITIDOS" ]; then
    rojo "la tarea $TAREA no declara \"Archivos que podés tocar\": sin alcance no hay gate"
  elif [ -z "${TAREA:-}" ]; then
    vacuo "sin límite de alcance declarado (modo integración)"
  else
    FUERA=""
    while read -r archivo; do
      [ -n "$archivo" ] || continue
      # por ruta y no por basename: 'entidades.py' permitido no habilita 'tests/entidades.py'
      ok=""
      while read -r permitido; do
        [ -n "$permitido" ] || continue
        case "$permitido" in
          */) case "$archivo" in "$permitido"*) ok=1 ;; esac ;;   # un directorio cubre lo de abajo
          *) { [ "$archivo" = "$permitido" ] || [ "$archivo" = "src/$permitido" ]; } && ok=1 ;;
        esac
      done <<< "$PERMITIDOS"
      [ -n "$ok" ] || FUERA="$FUERA $archivo"
    done <<< "$CAMBIADOS"
    if [ -n "$FUERA" ]; then
      rojo "archivos fuera del alcance de $TAREA:$FUERA"
      echo "     permitidos: $(echo "$PERMITIDOS" | tr '\n' ' ')"
      # Si lo que se fue del alcance parece andamiaje de un test, lo más probable es que el
      # criterio de terminado lo esté pidiendo y el alcance no lo permita: la tarea se
      # contradice a sí misma y el agente hizo lo que le pedían.
      if echo "$FUERA" | grep -qE '(^| )[^ ]*(/|^)(test_[^ /]*|[^ /]*_test)\.[a-z]+'; then
        echo "     OJO: eso parece andamiaje de un test. Revisá el criterio de terminado de"
        echo "     $TAREA: si pide crear algo que el alcance no permite, la tarea se contradice"
        echo "     y el defecto es del plan. Un archivo que un test necesita lo crea el test."
      fi
    else
      verde "todo dentro del alcance declarado en tareas/$TAREA-*.md"
    fi
  fi
fi

echo "── 3. Higiene"
# Lo mismo del lado de Python. Lo dejé sin hacer un rato porque pensé que pedía mantener a
# mano la lista de módulos de la stdlib; `sys.stdlib_module_names` la trae, así que el
# chequeo que parecía caro costaba una línea. Lo habría atrapado al toque: el agente de T04
# importó `mysql.connector` donde el proyecto declara `pymysql`, y el síntoma fue un
# ModuleNotFoundError dentro del test que el método informó como "el test está mal".
if [ -n "$(aux_del_metodo _imports.py)" ]; then
  if [ -n "${TAREA:-}" ]; then
    PY_IMPORT="$(echo "$CAMBIADOS" | grep -E '\.py$' | tr '\n' ' ')"
  else
    PY_IMPORT="--todo src tests"
  fi
  SAL_IMP="$("${PY_PROYECTO:-python3}" "$(aux_del_metodo _imports.py)" ${PY_IMPORT} 2>&1)"; RC_IMP=$?
  echo "$SAL_IMP"
  case "$RC_IMP" in
    1) FALLOS=$((FALLOS+1)) ;;
    2) VACIOS=$((VACIOS+1)) ;;
  esac
fi
# Directorios vacíos: **git no versiona directorios**, sólo archivos. Un test que verifica
# que existe una carpeta pasa en el worktree del agente —donde la carpeta está, recién
# creada— y falla en el tronco después del merge, porque el merge no la lleva. Pasó con T01
# de clasificados: `backend/app/datos` existía, el gate dio VERDE, y el tronco quedó rojo.
# El gate no puede dar por bueno algo que no va a sobrevivir al commit.
#
# Sólo las que son NUEVAS respecto de la base del diff, y sólo en modo tarea: una carpeta
# vacía que ya estaba no la creó esta tarea, y en modo integración la pregunta no aplica
# —el merge ya pasó—. Sin esa condición el chequeo informaba las carpetas que esperan a
# tareas futuras, que es ruido y encima acusa a quien no hizo nada.
if [ -n "${TAREA:-}" ]; then
  NUEVAS_VACIAS=""
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    d="${d#./}"
    # ¿Había algún archivo acá en la base? Si había, la carpeta no es nueva.
    if [ -z "$(git ls-tree -r --name-only "$BASE_REF" -- "$d" 2>/dev/null)" ]; then
      NUEVAS_VACIAS="$NUEVAS_VACIAS$d
"
    fi
  done <<EOF
$(find . -type d -empty \
    -not -path './.git/*' -not -path './.venv/*' -not -path './.mysql/*' \
    -not -path '*/node_modules/*' -not -path '*/__pycache__/*' \
    -not -path './.opencode-data/*' 2>/dev/null || true)
EOF
  if [ -n "$NUEVAS_VACIAS" ]; then
    rojo "creaste directorios vacíos: git no los versiona y el merge no los lleva"
    echo "$NUEVAS_VACIAS" | grep . | head -5 | sed 's/^/     /'
    echo "     Si la carpeta es un paquete, poné su __init__.py; si no, no hace falta la carpeta."
  else
    verde "sin directorios vacíos nuevos"
    testigo "el árbol del proyecto contra $BASE_REF, salvo .git y dependencias"
  fi
fi
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
if grep -rqE '^\s*(import|from)\s+(pygame|numpy|pytest)' src/ 2>/dev/null; then rojo "dependencia externa en src/"; else verde "solo biblioteca estándar"; fi
# Una ruta absoluta dentro de un test no es un test: es una foto del directorio de una
# máquina. Pasó y tardó dos semanas en verse: el agente de T03 escribió la ruta de su
# PROPIO worktree temporal (`/Users/.../tests-T03/...`), adentro pasaba, el gate lo aceptó
# y se mergeó. Desde entonces fallaba en todos lados menos en una carpeta que ya no existe,
# y la línea base lo tapaba como «ya fallaba antes».
#
# Va en modo integración y no en modo tarea a propósito: un test con ruta absoluta que ya
# estaba en el tronco no lo escribió esta tarea, y ponerle rojo por eso es acusar a quien
# no lo hizo. El método corre siempre desde la raíz del proyecto, así que una ruta absoluta
# nunca hace falta.
if [ -z "${TAREA:-}" ]; then
  CLAVADAS="$(grep -rnE "['\"](/(Users|home|private|tmp|var)/[^'\"]{4,})['\"]" \
              --include='test_*.py' --include='*_test.py' --include='*.test.ts' \
              --include='*.test.tsx' --include='*.spec.ts' . 2>/dev/null \
              | grep -vE 'node_modules|\.venv' || true)"
  if [ -n "$CLAVADAS" ]; then
    rojo "hay tests con una ruta absoluta clavada: sólo pasan en la máquina donde se escribieron"
    echo "$CLAVADAS" | head -5 | sed 's/^/     /'
    echo "     La suite corre desde la raíz del proyecto: usá rutas relativas a ella."
  else
    verde "ningún test clava una ruta absoluta"
  fi
fi
# El TODO, acotado a lo que ESTA tarea cambió, igual que sus tres vecinos (imports, señales
# suprimidas, directorios vacíos). Barría el árbol entero: un `# TODO: paginar` que dejó otra
# tarea en un archivo ajeno reprobaba a la de al lado, que no puede sacarlo sin salirse de su
# alcance — y tocarlo la repruebe el paso 2. El único camino era escribir peor código.
if [ -n "${TAREA:-}" ]; then
  ARG_TODO="$(echo "$CAMBIADOS" | grep -E '\.(py|ts|tsx|js|jsx|scss|css|sql|md)$' | tr '\n' ' ')"
else
  ARG_TODO="src/"
fi
if [ -z "$ARG_TODO" ]; then
  vacuo "esta tarea no cambió archivos donde buscar TODO"
elif grep -rnE "\bTODO\b" src/ --exclude-dir=__pycache__ 2>/dev/null | grep -qv '^\s*$'; then rojo "quedaron TODO en src/: $(grep -rn 'TODO' src/ | head -2 | tr '\n' ' ')"; else verde "sin TODO sueltos"; fi
if ! python3 -m compileall -q src/ >/dev/null 2>&1; then rojo "src/ no compila"; else verde "src/ compila"; fi
# Apagar una señal es más barato que arreglar la causa, y no deja rastro en los tests.
# Por árbol sintáctico y no por grep de línea: la forma más común de apagar una señal
# en Python ocupa tres líneas (`except X:` / comentario / `pass`) y un grep por línea no
# la ve. Pasó en serio, y el agente citó mi propio texto de la tarea para justificarla.
if [ -z "$(aux_del_metodo _suprimidas.py)" ]; then
  rojo "falta scripts/_suprimidas.py: el gate no puede buscar señales suprimidas"
  echo "     Lo provee el método en scripts/_suprimidas.py. Esto es del método, no del código juzgado."
else
  # En modo tarea, sólo lo que ESTA tarea tocó: una señal suprimida que ya estaba en el
  # tronco no es de esta tarea. Es el mismo error que cometí con los imports y con el
  # corredor faltante — tests-first deja el tronco con defectos de etapas en vuelo.
  if [ -n "${TAREA:-}" ]; then
    ARG_SUP="$(echo "$CAMBIADOS" | grep -E '\.(py|ts|tsx|js|jsx)$' | tr '\n' ' ')"
  else
    ARG_SUP="src"
  fi
  # Con BASE, `_suprimidas.py` acota al diff: una señal que ya estaba en el archivo
  # no es de esta tarea. Sin esto le cobraba a cualquier tarea las tres de curses
  # que viven en el pacman desde siempre.
  SAL_SUP="$(BASE="${BASE_REF:-}" "${PY_PROYECTO:-python3}" "$(aux_del_metodo _suprimidas.py)" ${ARG_SUP} 2>&1)"; RC_SUP=$?
  echo "$SAL_SUP"
  case "$RC_SUP" in 1) FALLOS=$((FALLOS+1)) ;; 2) VACIOS=$((VACIOS+1)) ;; esac
fi

# ── 4. ¿Los tests distinguen? (sólo en modo tarea)
# Este paso NO EXISTÍA en este gate. El de clasificados y el de la plantilla sí lo tienen, así
# que las 19 tareas de este proyecto cerraron sin que nadie verificara nunca que sus tests
# distinguieran — que es el único chequeo de eso en todo el método, y el que sostiene P2.
if [ -n "${TAREA:-}" ]; then
  echo "── 4. ¿Los tests distinguen?"
  IMPL="$(echo "$CAMBIADOS" | grep -E '^src/.*\.py$' || true)"
  TMP="$(mktemp -d)"; REVERTIDOS=""
  PREFIJO="$(git rev-parse --show-prefix)"   # vacío si el proyecto es la raíz del repo
  for f in $IMPL; do
    # `git cat-file` resuelve rutas desde la raíz del repo: sin el prefijo, todo archivo
    # parecería «nuevo» y este paso daría verde sin revertir nada.
    if git cat-file -e "HEAD:${PREFIJO}$f" 2>/dev/null; then
      cp "$f" "$TMP/$(echo "$f" | tr / _)"
      git checkout HEAD -- "$f" && REVERTIDOS="$REVERTIDOS $f"
    fi
  done
  if [ -z "$IMPL" ]; then vacuo "no hay implementación que revertir"
  elif [ -z "$REVERTIDOS" ]; then vacuo "archivos nuevos (no existían en HEAD): nada que revertir"
  else
    # Qué tests tienen que fallar, no sólo que «algo» falle: con el tronco rojo por diseño
    # (tests-first) «la suite entera falla» se cumple antes de revertir y no distingue nada.
    ESPERADO="$(test_de_la_tarea)"
    if bash scripts/correr-suite.sh >/dev/null 2>&1; then
      rojo "los tests PASAN con la implementación vieja: no verifican el cambio"
      echo "     revertí:$REVERTIDOS y la suite siguió verde"
    elif [ -n "$ESPERADO" ]; then
      RUTA_T="$(echo "$ESPERADO" | cut -d' ' -f1)"
      CLASE="$(echo "$ESPERADO" | cut -d' ' -f2)"
      # El contrato de códigos de correr-suite.sh, igual que el paso 1: 0 pasa, 1 falla,
      # 2 no corrió ningún test, 3 es del método, 127 falta el corredor. Esto decía
      # `if bash ... ; then … else verde …; fi`, o sea leía TODO lo distinto de cero como
      # «los tests fallan» — y entonces un corredor ausente (127) o una suite vacía (2) se
      # informaban como «los tests distinguen». Un chequeo que no pudo correr no es un
      # chequeo que pasó, y acá era peor: era un ✓.
      bash scripts/correr-suite.sh "$RUTA_T::$CLASE" >/dev/null 2>&1; RC_T4=$?
      case "$RC_T4" in
        0) rojo "la suite falla, pero NO por los tests de esta tarea ($CLASE pasa con el código viejo)"
           echo "     o los tests de $TAREA no verifican el cambio, o rompiste otra cosa" ;;
        1) verde "fallan los tests de la tarea ($CLASE) al revertir$REVERTIDOS"
           testigo "$RUTA_T::$CLASE, revirtiendo$REVERTIDOS" ;;
        2) vacuo "$CLASE no corrió ningún test: no distingue nada" ;;
        3) vacuo "el corredor falló por el entorno, no por el código ($CLASE)" ;;
        *) vacuo "no pude correr $RUTA_T::$CLASE (código $RC_T4)" ;;
      esac
    else
      vacuo "la tarea no declara «\`ruta\`, clase \`Clase\`»: no puedo saber si SUS tests distinguen"
    fi
    for f in $REVERTIDOS; do cp "$TMP/$(echo "$f" | tr / _)" "$f"; done
  fi
  rm -rf "$TMP"
fi

# ── 5. Coherencia (sólo en modo integración)
# Los pasos 0-4 miran UNA tarea. Ninguno puede ver que diez diffs correctos por separado
# dejaron la arquitectura peor: esa deriva sólo se ve mirando el conjunto, y por eso este
# paso corre sobre el tronco y no dentro del worktree de una tarea.
if [ -z "${TAREA:-}" ]; then
  echo "── 5. Coherencia"
  if [ -f scripts/_arquitectura.py ]; then
    if OUT="$(python3 scripts/_arquitectura.py 2>&1)"; then echo "$OUT"
    else echo "$OUT"; FALLOS=$((FALLOS+1)); fi
    # Los ⊘ que imprime el chequeo son vacíos del gate: si no se cuentan, el veredicto dice
    # "GATE VERDE" a secas cuando en realidad hubo cosas que no pudieron verificarse.
    N_VACUOS_ARQ="$(printf '%s\n' "$OUT" | grep -c '⊘' || true)"
    [ "${N_VACUOS_ARQ:-0}" -gt 0 ] && VACIOS=$((VACIOS+N_VACUOS_ARQ))
  else
    vacuo "no hay scripts/_arquitectura.py"
  fi
fi

# ── 6. La suite reservada (sólo en modo integración)
# Tests escritos por una persona que NINGÚN agente ve: viven fuera del directorio del
# proyecto, así que OpenCode los rechaza por `external_directory` desde cualquier worktree.
# No se nombran en el plan ni en las tareas.
#
# Por qué: los gates de tarea verifican lo que los tests de la tarea cubren, y el agente
# optimiza contra eso. Medido, la brecha de reward hacking crece ~27 puntos por cada 10× de
# tamaño de código, y los puntajes de validación se saturan mientras los reservados
# divergen — peor en modelos chicos. Es el único gate que mide lo que el agente no pudo
# haber optimizado.
#
# Y medido también: "leer los tests reservados" es el hack MÁS común. Por eso van afuera y
# no sólo sin documentar.
if [ -z "${TAREA:-}" ]; then
  # Fuera del repo, no sólo fuera del proyecto: así no viaja en los worktrees ni se
  # commitea por accidente, y OpenCode la rechaza por external_directory.
  RESERVADOS="${RESERVADOS:-$(cd "$(git rev-parse --show-toplevel)/.." && pwd)/reservados-$(basename "$PWD")}"
  echo "── 6. Suite reservada"
  N_RES="$(ls "$RESERVADOS"/test_*.py 2>/dev/null | grep -c . || true)"
  if [ "${N_RES:-0}" -gt 0 ]; then
    if OUT="$(PYTHONPATH="$PWD" python3 -m unittest discover -s "$RESERVADOS" -t "$RESERVADOS" -q 2>&1)"; then
      verde "$(echo "$OUT" | grep -E '^Ran ' | head -1) de composición"
      testigo "$N_RES archivo(s) reservado(s) en $RESERVADOS"
    else
      rojo "la suite reservada falla: pasa los tests de las tareas y no hace lo que tiene que hacer"
      echo "$OUT" | tail -15 | sed 's/^/     /'
    fi
  else
    vacuo "no hay suite reservada en $RESERVADOS"
    echo "    Es el gate que mide lo que el agente no pudo optimizar. Escribila: tests de"
    echo "    composición, invariantes de punta a punta, fuera del repo para que no la vea."
  fi
fi

echo
if [ "$FALLOS" -gt 0 ]; then
  echo "GATE ROJO ($FALLOS fallo/s)"; exit 1
elif [ "$VACIOS" -gt 0 ]; then
  # Verde, pero con constancia de qué no se pudo verificar. El código sigue siendo 0 porque
  # hay vacíos legítimos (un archivo nuevo no se puede revertir), pero quedan a la vista.
  echo "GATE VERDE — con $VACIOS chequeo/s que no pudieron correr (⊘)"; exit 0
else
  echo "GATE VERDE"; exit 0
fi
