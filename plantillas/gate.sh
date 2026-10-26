#!/usr/bin/env bash
# Gate G1: decide si una tarea está terminada. No opina, ejecuta.
#   0) integridad  1) tests  2) alcance  3) higiene  4) ¿distinguen?  5) coherencia
#
# PLANTILLA. Buscá "ADAPTAR" — son cuatro líneas: el comando de tests, la marca de suite
# vacía, los directorios de código, y las reglas de higiene propias de tu stack.
#
# Verde => imprime "GATE VERDE" y sale 0. Cualquier rojo => sale 1.
#
# Dos reglas que no se tocan al adaptarlo, porque cada una salió de un falso verde real:
#   · Un chequeo que no pudo ejecutarse da ROJO, nunca verde.
#   · Lo que el agente no puede tocar lo decide ESTE archivo, no el archivo de tarea.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
# El intérprete del proyecto si hay uno. Con `python3` a secas el gate corre contra el del
# sistema y no ve las dependencias del proyecto.
if [ -n "${PY_PROYECTO:-}" ]; then :   # el runner lo pasa: en un worktree el venv no viaja
elif [ -x .venv/bin/python ]; then PY_PROYECTO=".venv/bin/python"
elif [ -x ../.venv/bin/python ]; then PY_PROYECTO="../.venv/bin/python"
else PY_PROYECTO="python3"; fi

# Credenciales y endpoints de los servicios del proyecto, si `scripts/entorno.sh` los dejó.
# Va acá y no en cada test: un test que trae su propia credencial escrita adentro es una
# credencial commiteada, y encima deja de valer en cuanto cambia el puerto.
# shellcheck disable=SC1091
[ -f .entorno ] && . ./.entorno

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

# El comando que corre la suite NO está acá: está en `scripts/correr-suite.sh`, porque lo
# usan dos —este gate, para juzgar, y `escribir-tests.sh`, para validar— y mientras cada
# uno tenía el suyo, diferían.
# ADAPTAR: dónde vive el código de producción (no los tests).
CODIGO="src"

# La base del diff la escribe el runner al crear el worktree, ANTES de que el agente toque
# nada. Si la dedujera este script, el primer commit del agente movería la base y los pasos
# 0 y 2 dejarían de ver sus propios cambios.
RAIZ_WT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -f "$RAIZ_WT/.base-ref" ]; then
  BASE_REF="$(cat "$RAIZ_WT/.base-ref")"; ORIGEN_BASE="fijada por el runner"
else
  BASE_REF="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD)"
  ORIGEN_BASE="deducida (no había .base-ref)"
fi
# Qué base se usó y de dónde salió. Una falla sembrada la cambiaba por otra y no
# se notaba: los pasos 0, 2 y 4 dependen de esto y ninguno lo informaba.
echo "base del diff: $(echo "$BASE_REF" | cut -c1-12) — $ORIGEN_BASE"

# ── 0. Integridad (sólo en modo tarea)
# Los tests y este archivo viven DENTRO del worktree del agente al que juzgan. La lista es
# fija acá y el archivo de tarea no puede ampliarla: un límite que el limitado puede
# reescribir no es un límite. Pedirlo por prompt está medido que no alcanza.
# Por NOMBRE de archivo y no sólo por directorio: `^(tests/|scripts/)` no cubre
# `backend/tests/test_x.py` ni `frontend/tests/x.test.ts`, que es el layout de cualquier
# proyecto con dos mitades. Un proyecto nuevo copiado de esta plantilla obtenía «✓ tests y
# scripts intactos» mientras el agente editaba su propio test — la regla dura nº3 de
# AGENTS.md. `ejemplo-clasificados` lo adaptó bien; la plantilla quedó con la lista corta y
# el encabezado no la marca como ADAPTAR.
INTOCABLES='(^|/)(test_[^/]*\.py|[^/]*_test\.py|[^/]*\.(test|spec)\.[jt]sx?)$|^scripts/|(^|/)tests/'
if [ -n "${TAREA:-}" ]; then
  echo "── 0. Integridad"
  # --relative: git informa rutas desde la raíz del repo, y acá razonamos en rutas del
  # proyecto. Sin esto el chequeo daba VERDE con un test modificado.
  TOCADO="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null | grep -E "$INTOCABLES" || true)"
  N_DIFF="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null | grep -c . || true)"
  if [ -n "$TOCADO" ]; then rojo "tocó archivos intocables (tests o el propio gate):"; echo "$TOCADO" | sed 's/^/     /'
  else
    verde "tests y scripts intactos"
    testigo "${N_DIFF:-0} ruta(s) del diff contra el patrón $INTOCABLES"
  fi
fi

# ── Cadena de herramientas. Un corredor ausente no puede verse como "no hay tests".
#
# Esto lo detecta `scripts/correr-suite.sh`, que emite FALTA_CORREDOR, y lo consumen cuatro
# puntos de este gate. Acá había una función `herramienta_falta()` de la versión anterior,
# definida y JAMÁS llamada: quedó cuando la responsabilidad se movió al corredor. Se fue el
# 2026-10-25 al barrer funciones muertas en todo el método — era la única, y estaba justo en
# la pieza que todo proyecto nuevo copia. Los dos ejemplos ya la habían eliminado, así que la
# plantilla estaba ATRASADA respecto de ellos, no al revés.

echo "── 1. Tests"
# Antes de juzgar la suite, CALIBRAR el instrumento con el que se la juzga: que el corredor
# de este proyecto distinga «no corrí ningún test» de «los tests pasan». El contrato de
# códigos lo dice, y lo cumple el corredor de cada proyecto, que se escribe a mano: medido
# el 2026-10-26, adaptarlo a `node --test` lo rompió por las dos puntas y el gate emitió un
# diagnóstico falso y rotundo sobre un test que nunca corrió. El chequeo lo provee el método.
CORREDOR_AUX="$(aux_del_metodo _corredor.sh)"
if [ -z "$CORREDOR_AUX" ]; then
  rojo "falta scripts/_corredor.sh: nadie verificó el contrato del corredor"
  echo "     Lo provee el método en scripts/_corredor.sh. Esto es del método, no del código juzgado."
else
  SAL_CORR="$(bash "$CORREDOR_AUX" 2>&1)"; RC_CORR=$?
  case "$RC_CORR" in
    0) ;;
    1) printf '%s\n' "$SAL_CORR"; FALLOS=$((FALLOS+1)) ;;
    *) printf '%s\n' "$SAL_CORR"; VACIOS=$((VACIOS+1)) ;;
  esac
fi
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
# antes el paso 1 la leía con un patrón y el paso 4 con otro, y el del paso 4 anclaba en
# `tests/`. Medido: de 50 archivos de tarea, el patrón del paso 4 matcheaba 3 y el del paso 1
# matcheaba 33 — en clasificados, cuyas rutas son `backend/tests/` y `frontend/tests/`, el
# paso 4 acotaba en 0 de 31 y se conformaba con «la suite entera falla».
#
# La declaración canónica, en el marcador de fase del archivo de tarea:
#     Archivo: `<ruta>`, clase `<Clase>`.
# Devuelve «ruta clase», o vacío si la tarea no la declara.
# Los archivos que la tarea declara. UN solo lector para UNA sola declaración, igual que
# `test_de_la_tarea`: el paso 2 y el paso 4 leían la misma línea del archivo de tarea con dos
# parsers distintos, y el del paso 4 era una lista de extensiones que envejeció.
archivos_de_la_tarea() {
  sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/${TAREA:-}"-*.md 2>/dev/null \
    | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+(\.[A-Za-z0-9]+|/)' | sort -u
}

# ¿Este archivo está dentro de lo que la tarea declara? Mismo criterio que el paso 2: un
# directorio cubre lo de abajo, un archivo es exacto.
declarado_por_la_tarea() {
  local archivo="$1" permitido
  while read -r permitido; do
    [ -n "$permitido" ] || continue
    case "$permitido" in
      */) case "$archivo" in "$permitido"*) return 0 ;; esac ;;
      *) [ "$archivo" = "$permitido" ] && return 0 ;;
    esac
  done <<< "$(archivos_de_la_tarea)"
  return 1
}

test_de_la_tarea() {
  # Sin anclar en «Archivo:»: la declaración aparece en dos formas en el repo,
  #     Archivo: `backend/tests/test_errores.py`, clase `TestErrores`.
  #     (`tests/test_juego.py`, clase `TestFruta`)
  # y lo que la identifica es la ruta y la clase juntas, no el prefijo. Anclar en «Archivo:»
  # perdía T16; anclar en `tests/` perdía las 31 de clasificados, cuyas rutas son
  # `backend/tests/` y `frontend/tests/`. Con esto: 34 de 50 tareas acotables, contra 3.
  sed -n 's/.*`\([^`]*\)`, *clase `\([A-Za-z0-9_]*\)`.*/\1 \2/p' \
    "tareas/${TAREA:-}"-*.md 2>/dev/null | head -1
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

  esperado="$(test_de_la_tarea)"
  ruta_t="$(echo "$esperado" | cut -d' ' -f1)"
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
    #
    # El motivo sale de una corrida que SÓLO incluye a esta tarea, no de la salida completa.
    # Grepeando todo, el primer match puede ser de OTRO archivo: el tronco está rojo por
    # diseño mientras una etapa está en vuelo, así que siempre hay errores ajenos arriba.
    #
    # Medido el 2026-10-25 en T20 de clasificados: su test fallaba por `KeyError:
    # 'otro_usuario_id'` y el gate informó «ModuleNotFoundError: No module named
    # 'backend.app.servicios.messages'», que es de T21 —otra tarea pendiente—. El reintento
    # habría ido a buscar un módulo que no le toca escribir. Es el defecto del día entero
    # —el veredicto nombra al sujeto equivocado— y acá lo hace citando a un vecino.
    SALIDA_MIA="$SALIDA"
    ESPERADO_PE="$(test_de_la_tarea)"
    if [ -n "$ESPERADO_PE" ]; then
      RUTA_PE="$(echo "$ESPERADO_PE" | cut -d' ' -f1)"
      CLASE_PE="$(echo "$ESPERADO_PE" | cut -d' ' -f2)"
      SALIDA_MIA="$(bash scripts/correr-suite.sh "$RUTA_PE::$CLASE_PE" 2>&1)"
    fi
    # Cualquier `*Error` o `*Exception`, no una lista de siete. La lista enumeraba
    # Import|Module|Attribute|Type|Name|Assertion|Value y dejaba afuera KeyError, IndexError,
    # KeyboardInterrupt, OSError y todos los propios del proyecto. Medido el 2026-10-25: el
    # test de T20 fallaba por `KeyError: 'otro_usuario_id'`, que no matcheaba, y el motivo
    # quedaba para el primer error que SÍ matcheara — el de un vecino. Enumerar lo que puede
    # fallar es una lista que siempre está incompleta.
    PRIMER_ERROR="$(printf '%s\n' "$SALIDA_MIA" \
      | grep -m2 -E '^E +|[A-Za-z_]+(Error|Exception)\b|^ *>? *assert ' \
      | sed 's/^ *//' | tr '\n' ' ' | cut -c1-200)"
    [ -n "$PRIMER_ERROR" ] && echo "     por qué falla: $PRIMER_ERROR"
    return
  fi
  if [ -n "$nuevas" ]; then
    # ¿Fallan por el ENTORNO o por el cambio? Esta rama acusaba sin distinguirlo, y la
    # diferencia entre dos muestras de la suite no es causal: todos los worktrees comparten
    # un MySQL, así que la base que la etapa de tests vio poblada la etapa de tareas la puede
    # ver sin tablas, y la tarea carga con esa diferencia.
    #
    # Cadáver del 2026-10-21: T05a tocó UN archivo nuevo —`backend/app/datos/ads.py`, datos
    # de avisos— y el gate la acusó de romper `test_register_backend.py::
    # test_crear_usuario_hash_correcto`. Sacando ese archivo del worktree fallaban los
    # mismos dos tests, y la causa era `(1146, "Table 'clasificados.users' doesn't exist")`.
    # Dos intentos, punto muerto y el plan detenido, por una falla que la tarea no podía
    # causar: no toca registro ni hasheo.
    #
    # Es el mismo principio que esta función ya aplica a `FALTA_CORREDOR` —«es del método y
    # no del código»— extendido a las firmas de infraestructura. Y no ablanda nada: no
    # declara verde, detiene igual. Lo único que cambia es a QUIÉN se le cobra, que es
    # exactamente lo que estuvo mal en nueve de los doce defectos de estos días.
    # La lista reconocía fallas de CONEXIÓN y de esquema ausente, y le faltaba la más común
    # de una base compartida: el ESTADO QUE QUEDÓ. Medido el 2026-10-24: un test insertó
    # `test@example.com`, y desde entonces toda corrida choca con el UNIQUE de
    # `usuarios.email` — «Duplicate entry», que esta lista no veía, así que el veredicto salía
    # como «rompiste tests que andaban antes de esta tarea». El sujeto equivocado otra vez, y
    # sobre el mismo MySQL del que este bloque ya habla dos líneas más abajo.
    if printf '%s\n' "$SALIDA" | grep -qiE "Table '[^']*' doesn't exist|Unknown database|Can't connect to( local)? MySQL|CR_CONN_HOST_ERROR|Access denied for user|Connection refused|ECONNREFUSED|\(200[36]|2013,|Duplicate entry|IntegrityError|\b1062,|UNIQUE constraint failed"; then
      rojo "el entorno se movió: estas fallas no son de la tarea"
      printf '%s\n' "$nuevas" | head -5 | sed 's/^/     /'
      printf '%s\n' "$SALIDA" | grep -ioE "Table '[^']*' doesn't exist|Unknown database[^\"]*|Can't connect to( local)? MySQL[^\"]*|CR_CONN_HOST_ERROR|Access denied for user[^\"]*|Connection refused" \
        | head -2 | sed 's/^/     causa: /'
      echo "     ENTORNO_MOVIDO — la base de datos del proyecto no está en el estado que la"
      echo "     línea base vio. Todos los worktrees comparten el MySQL de 127.0.0.1:33306:"
      echo "     lo que una etapa deja, la siguiente lo encuentra. Es del entorno y no del"
      echo "     código, así que no se le cobra a la tarea ni se reintenta contra ella."
      return
    fi
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
                | grep -oE '^[0-9]+ (passed|failed)[^,]*|^Ran [0-9]+ tests?[^,]*|Tests +[0-9]+ passed|^# (pass|fail) [0-9]+' \
                | sed 's/  */ /g' | tr '\n' ';' | sed 's/;/ · /g; s/ · $//')"
     # Sin resumen legible NO sale un ✓ pelado. «✓ » a secas es lo que imprimía con
     # `node --test` —que informa TAP, `# pass 2`— porque los patrones eran de unittest,
     # pytest y vitest. Un ✓ sin su número no dice si corrieron 300 tests o ninguno, y
     # «ninguno» tiene código propio en el contrato justamente porque importa.
     RESUMEN="${RESUMEN:-$(echo "$SALIDA" | grep -E '^Ran |^OK' | tail -1)}"
     verde "${RESUMEN:-la suite pasa, y su corredor no informa cuántos tests corrió}"
     testigo "scripts/correr-suite.sh, el mismo comando que valida los tests" ;;
  2) rojo "la suite no corrió ningún test: sin tests no hay gate"
     echo "$SALIDA" | tail -5 | sed 's/^/     /' ;;
  3) # `-n`, no `-z`: la rama de línea base sólo tiene sentido EN modo tarea —imprime «los
     # tests de $TAREA» y lee `.tests-base`, que vive en el worktree—. La plantilla tenía la
     # condición dada vuelta, y diez líneas más abajo el caso `*)` del mismo `case` usa `-n`.
     # Nació bien y la invirtió un commit sobre otra cosa; los dos proyectos la tienen bien.
     # Con `-z`, en un proyecto nuevo cada tarea de la etapa —incluidas las que no tocaron la
     # mitad sin corredor— recibe «falta el corredor de tests» y agota sus reintentos contra
     # un rojo que ninguna puede arreglar.
     if [ -n "${TAREA:-}" ] && [ -f .tests-base ] && grep -q FALTA_CORREDOR .tests-base; then
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
       # Las FALLAS, no las últimas 15 líneas. `tail -15` supone que las fallas están al
       # final, y con una suite de dos mitades la que falla puede ser la primera: medido el
       # 2026-10-20, el backend falló 3 tests y el frontend pasó 27, el tail cayó entero
       # dentro del frontend, y el agente leyó «la suite está en rojo» seguido de
       # «Tests 27 passed (27)» sin una sola falla a la vista. Iteró 1200 s contra un
       # veredicto que su propia evidencia contradecía.
       #
       # `--fallas` es el mismo comando que usan la línea base y `integrar.sh`: una falla por
       # línea, sin depender de dónde las imprimió el corredor. Cuesta una corrida de suite
       # extra, y sólo en el caso rojo.
       FALLAS_SUITE="$(bash scripts/correr-suite.sh --fallas 2>/dev/null | grep . || true)"
       if [ -n "$FALLAS_SUITE" ]; then
         printf '%s\n' "$FALLAS_SUITE" | head -15 | sed 's/^/     /'
       else
         echo "     ⊘ la suite salió en rojo y «--fallas» no listó ninguna: el corredor y"
         echo "       este gate no acuerdan en cómo se nombra una falla. Salida cruda:"
         echo "$SALIDA" | tail -15 | sed 's/^/       /'
       fi
     fi ;;
esac
fi

echo "── 2. Alcance${TAREA:+ (tarea $TAREA)}"
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
  # El alcance sale del archivo de la tarea, no de reglas escritas acá: una regla a mano
  # queda vieja en cuanto el plan crece.
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
      # Por ruta y no por nombre: permitir 'cosa.py' no habilita 'tests/cosa.py'.
      ok=""
      while read -r permitido; do
        [ -n "$permitido" ] || continue
        case "$permitido" in
          */) case "$archivo" in "$permitido"*) ok=1 ;; esac ;;   # un directorio cubre lo de abajo
          *) { [ "$archivo" = "$permitido" ] || [ "$archivo" = "$CODIGO/$permitido" ]; } && ok=1 ;;
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
    else verde "todo dentro del alcance declarado"; fi
  fi
fi

echo "── 3. Higiene"
# Lo mismo del lado de Python. Lo dejé sin hacer un rato porque pensé que pedía mantener a
# mano la lista de módulos de la stdlib; `sys.stdlib_module_names` la trae, así que el
# chequeo que parecía caro costaba una línea. Lo habría atrapado al toque: el agente de T04
# importó `mysql.connector` donde el proyecto declara `pymysql`, y el síntoma fue un
# ModuleNotFoundError dentro del test que el método informó como "el test está mal".
if [ -z "$(aux_del_metodo _imports.py)" ]; then
  # Con `else` y con `rojo`, como su hermano `_suprimidas.py`. Era el único eslabón de la
  # cadena nueva que fallaba ABIERTO: un `if` sin rama negativa, así que el paso no imprimía
  # nada, no sumaba a FALLOS ni a VACIOS, y el veredicto salía «GATE VERDE» limpio — ni
  # siquiera «con N chequeos que no pudieron correr». El mensaje del commit que movió los
  # chequeos al método afirmaba lo contrario; era cierto para uno de los dos. Cualquier
  # invocación del gate sin $AGENTES exportada (CI, cron, una shell nueva) perdía el chequeo
  # de imports en silencio, y el proyecto que se llevó el método aparte ya no tiene copia local.
  rojo "falta scripts/_imports.py: el gate no puede revisar los imports"
  echo "     Lo provee el método en scripts/_imports.py. Esto es del método, no del código juzgado."
else
  if [ -n "${TAREA:-}" ]; then
    PY_IMPORT="$(echo "$CAMBIADOS" | grep -E '\.py$' | tr '\n' ' ')"
  else
    PY_IMPORT="--todo $CODIGO"
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
# ADAPTAR: lo generado por tu stack y las dependencias que no querés ver aparecer.
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$|node_modules/|dist/'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
# ADAPTAR (si tu stack lo permite): **importar algo que no se declara**. No falla al
# escribirlo; falla cuando alguien corre los tests, con un "no encuentro el paquete" que no
# se parece a la causa. En JS/TS se verifica de un lado —los import contra package.json, y
# está hecho en ejemplo-clasificados/scripts/gate.sh—. En Python hace falta la lista de
# módulos de la stdlib, que es larga y cambia por versión: o la traés, o este chequeo no va.
# Mejor no tenerlo que tenerlo a medias y en verde.

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
  # La base se pasa SÓLO en modo tarea, y es la mitad que faltaba del acote. En modo
  # integración no hay tarea de quien acotar: `BASE_REF` es el merge-base con main, o sea
  # HEAD, el árbol está limpio y el diff sale vacío — así que `tocadas` era el conjunto
  # VACÍO (que no es None) y se filtraban TODOS los hallazgos. El chequeo quedaba
  # decorativo justo en el modo que revisa el tronco entero, y el comentario de acá arriba
  # decía «en modo tarea» mientras el código lo pasaba en los dos.
  if [ -n "${TAREA:-}" ]; then
    ARG_SUP="$(echo "$CAMBIADOS" | grep -E '\.(py|ts|tsx|js|jsx)$' | tr '\n' ' ')"
    BASE_SUP="${BASE_REF:-}"
  else
    ARG_SUP=""$CODIGO""
    BASE_SUP=""
  fi
  # Con BASE, `_suprimidas.py` acota al diff: una señal que ya estaba en el archivo
  # no es de esta tarea. Sin esto le cobraba a cualquier tarea las tres de curses
  # que viven en el pacman desde siempre.
  SAL_SUP="$(BASE="$BASE_SUP" "${PY_PROYECTO:-python3}" "$(aux_del_metodo _suprimidas.py)" ${ARG_SUP} 2>&1)"; RC_SUP=$?
  echo "$SAL_SUP"
  case "$RC_SUP" in 1) FALLOS=$((FALLOS+1)) ;; 2) VACIOS=$((VACIOS+1)) ;; esac
fi
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
  ARG_TODO=""$CODIGO""
fi
if [ -z "$ARG_TODO" ]; then
  vacuo "esta tarea no cambió archivos donde buscar TODO"
# OJO: el `grep` usa $ARG_TODO. La primera versión de este acote calculaba la variable y
# después greppeaba los directorios igual, así que el arreglo que el comentario de arriba
# describe NO EXISTÍA: el chequeo seguía barriendo el árbol entero. Y mi test no lo vio
# porque verificaba que la variable EXISTIERA, no que el grep la usara — nombrar la cosa no
# alcanza, esta vez aplicado al test. Lo encontró una auditoría, no una corrida.
elif grep -rnE "\bTODO\b" ${ARG_TODO} --exclude-dir=__pycache__ 2>/dev/null | grep -q .; then rojo "quedaron TODO sueltos"; else verde "sin TODO sueltos"; fi

# ── 4. ¿Los tests distinguen? (sólo en modo tarea)
# Revierte la implementación y exige que la suite FALLE. Un test que pasa con el código
# viejo no prueba nada, y no hay otra forma de que el gate lo detecte.
if [ -n "${TAREA:-}" ]; then
  echo "── 4. ¿Los tests distinguen?"
  # El alcance que la tarea DECLARA, no un patrón de rutas. El patrón dejaba `IMPL` vacío
  # para toda tarea cuya implementación no cayera en él —un `.scss`, un `.sql`, un
  # manifiesto, un archivo fuera del directorio de código— y entonces el paso imprimía
  # «⊘ no hay implementación que revertir» y el gate cerraba: el único chequeo de que los
  # tests DISTINGUEN no corría. El arreglo existía en un ejemplo de tres; la plantilla, que
  # es la que copia todo proyecto nuevo, seguía con el patrón.
  IMPL=""
  while read -r f; do
    [ -n "$f" ] || continue
    [ "$f" = "${RUTA_DECLARADA:-}" ] && continue
    declarado_por_la_tarea "$f" && IMPL="$IMPL
$f"
  done <<< "$CAMBIADOS"
  IMPL="$(printf '%s' "$IMPL" | grep . || true)"
  TMP="$(mktemp -d)"; REVERTIDOS=""
  PREFIJO="$(git rev-parse --show-prefix)"   # vacío si el proyecto es la raíz del repo
  for f in $IMPL; do
    # `git cat-file` resuelve rutas desde la raíz del repo: sin el prefijo, todo archivo
    # parecía "nuevo" y este paso daba VERDE sin revertir nada.
    if git cat-file -e "HEAD:${PREFIJO}$f" 2>/dev/null; then
      cp "$f" "$TMP/$(echo "$f" | tr / _)"
      git checkout HEAD -- "$f" && REVERTIDOS="$REVERTIDOS $f"
    fi
  done
  if [ -z "$IMPL" ]; then vacuo "no hay implementación que revertir"
  elif [ -z "$REVERTIDOS" ]; then vacuo "archivos nuevos (no existían en HEAD): nada que revertir"
  else
    # Qué tests tienen que fallar, no sólo que "algo" falle. La tarea nombra su archivo y
    # su clase; medido, la tasa agregada casi no se mueve ante una regresión mientras las
    # métricas por porción caen 25 a 91 puntos. "La suite falla" puede ser otro test.
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
      # Sin la declaración NO se afirma nada: «la suite entera falla» no distingue, porque el
      # tronco está rojo por diseño mientras una etapa está en vuelo (tests-first). Afirmarlo
      # era un falso verde, no un ⊘.
      vacuo "la tarea no declara «Archivo: \`ruta\`, clase \`Clase\`»: no puedo saber si SUS tests distinguen"
    fi
    for f in $REVERTIDOS; do cp "$TMP/$(echo "$f" | tr / _)" "$f"; done
  fi
  rm -rf "$TMP"
fi

# ── 4b. ¿Los tests distinguen ESTA implementación? (sólo en modo tarea)
#
# El paso 4 revierte la implementación ENTERA y exige que la suite falle. Eso distingue
# «con código» de «sin código», que no es lo mismo que «este código» de «este código con un
# bug»: el nombre del paso prometía más de lo que medía.
#
# `escribir-tests.sh` SÍ muta, pero contra la implementación de REFERENCIA que escribió el
# agente de tests — y la implementación final la escribe otro agente, en otra etapa. Un
# mutante que muere contra la referencia puede sobrevivir contra la final, y entre las dos no
# había nadie.
#
# Medido el 2026-10-25 en T20 de clasificados, con gate VERDE al primer intento: dos mutantes
# sobreviven, y uno es un bug latente. La línea
#
#     row["de_usuario_id"] if row["de_usuario_id"] != user_id else row["a_usuario_id"]
#
# es «el otro usuario de la conversación»; invirtiendo el `!=` devuelve el PROPIO usuario y
# el test no lo nota. Ese verde no se ganó, y sin este paso se integraba.
if [ -n "${TAREA:-}" ] && [ "${FALLOS:-0}" = "0" ]; then
  echo "── 4b. ¿Los tests distinguen ESTA implementación?"
  MUT="$(aux_del_metodo mutar.py || true)"
  ESPERADO_M="$(test_de_la_tarea)"
  PY_MUT="$(printf '%s\n' "${IMPL:-}" | grep -E '\.py$' || true)"
  if [ -z "$MUT" ]; then
    # ROJO y no ⊘: `mutar.py` lo provee el MÉTODO, igual que `_imports.py`, así que su
    # ausencia es un problema de instalación y no una propiedad del proyecto juzgado. El gate
    # ya trata así a sus otros auxiliares, y un ⊘ acá dejaría el único chequeo de que el test
    # distingue ESTA implementación apagado sin que nadie lo decida.
    rojo "falta scripts/mutar.py: no se puede verificar que el test distinga el cambio"
    echo "     Lo provee el método en scripts/mutar.py. Esto es del método, no del código juzgado."
  elif [ -z "$PY_MUT" ]; then
    vacuo "la implementación de esta tarea no tiene archivos .py que mutar"
  elif [ -z "$ESPERADO_M" ]; then
    vacuo "la tarea no declara su test: no sé qué suite correr contra los mutantes"
  else
    RUTA_M="$(echo "$ESPERADO_M" | cut -d' ' -f1)"
    CLASE_M="$(echo "$ESPERADO_M" | cut -d' ' -f2)"
    CODIGO_M="$(for f in $PY_MUT; do dirname "$f"; done | sort -u | paste -sd, -)"
    # `ARCHIVOS` y no sólo `CODIGO`: una tarea que CREA su implementación deja el archivo
    # sin trackear, y `git diff` no lo lista. Nombrarlos es lo único que hace que un archivo
    # nuevo se mute, y crear el archivo es el caso más común.
    SAL_M="$(BASE=HEAD CODIGO="$CODIGO_M" ARCHIVOS="$(printf '%s ' $PY_MUT)" \
             SUITE="bash scripts/correr-suite.sh \"$RUTA_M::$CLASE_M\"" \
             "${PY_PROYECTO:-python3}" "$MUT" 2>&1)"; RC_M=$?
    case "$RC_M" in
      0) verde "los mutantes de esta implementación mueren: $CLASE_M distingue el cambio" ;;
      2) vacuo "no hubo nada que mutar con provecho bajo «${CODIGO_M}»"
         printf '%s\n' "$SAL_M" | sed 's/^/     /' ;;
      3) rojo "hay líneas de la implementación que $CLASE_M NO EJECUTA"
         printf '%s\n' "$SAL_M" | grep '→' | sed 's/^/     /'
         echo "     Si mockeás lo que esta tarea define, estás reemplazando lo que vino a probar." ;;
      1) rojo "sobreviven mutantes: $CLASE_M cubre esas líneas y no verifica su comportamiento"
         printf '%s\n' "$SAL_M" | grep '→' | sed 's/^/     /' ;;
      *) vacuo "mutar.py no pudo correr (código $RC_M)"
         printf '%s\n' "$SAL_M" | sed 's/^/     /' ;;
    esac
  fi
fi

# ── 5. Coherencia (sólo en modo integración)
# Los pasos 0 a 4 miran UNA tarea. Ninguno puede ver que diez diffs correctos por separado
# dejaron la arquitectura peor: eso sólo se ve mirando el conjunto. Copiá
# plantillas/_arquitectura.py y declará tus capas.
if [ -z "${TAREA:-}" ]; then
  echo "── 5. Coherencia"
  if [ -f scripts/_arquitectura.py ]; then
    if OUT="$("$PY_PROYECTO" scripts/_arquitectura.py 2>&1)"; then echo "$OUT"
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
    if OUT="$(PYTHONPATH="$PWD" "$PY_PROYECTO" -m unittest discover -s "$RESERVADOS" -t "$RESERVADOS" -q 2>&1)"; then
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
