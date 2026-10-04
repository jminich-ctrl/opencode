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
INTOCABLES='^(tests/|scripts/)'
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
herramienta_falta() {
  echo "  ✗ hay tests en $1 y falta su corredor ($2)"
  echo "     Instalalo antes de correr el gate; si no, el gate no verifica nada y lo diría en verde."
  FALLOS=$((FALLOS+1))
}

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
veredicto_con_linea_base() {
  local base_f ahora mios nuevas esperado ruta_t
  ahora="$(bash scripts/correr-suite.sh --fallas 2>/dev/null | sort -u)"
  base_f="$(sort -u .tests-base 2>/dev/null)"
  nuevas="$(comm -13 <(printf '%s\n' "$base_f") <(printf '%s\n' "$ahora") | grep . || true)"

  esperado="$(sed -n 's/.*Archivo: `\([^`]*\)`.*/\1/p' "tareas/${TAREA}"-*.md 2>/dev/null | head -1)"
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

  if [ -n "$mios" ]; then
    rojo "los tests de $TAREA siguen fallando:"
    printf '%s\n' "$mios" | head -5 | sed 's/^/     /'
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
    else verde "todo dentro del alcance declarado"; fi
  fi
fi

echo "── 3. Higiene"
# Lo mismo del lado de Python. Lo dejé sin hacer un rato porque pensé que pedía mantener a
# mano la lista de módulos de la stdlib; `sys.stdlib_module_names` la trae, así que el
# chequeo que parecía caro costaba una línea. Lo habría atrapado al toque: el agente de T04
# importó `mysql.connector` donde el proyecto declara `pymysql`, y el síntoma fue un
# ModuleNotFoundError dentro del test que el método informó como "el test está mal".
if [ -f scripts/_imports.py ]; then
  if [ -n "${TAREA:-}" ]; then
    PY_IMPORT="$(echo "$CAMBIADOS" | grep -E '\.py$' | tr '\n' ' ')"
  else
    PY_IMPORT="--todo $CODIGO"
  fi
  SAL_IMP="$("${PY_PROYECTO:-python3}" scripts/_imports.py ${PY_IMPORT} 2>&1)"; RC_IMP=$?
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
SUP="$(grep -rnEi '# *(noqa|type: *ignore)|except[^:]*: *pass|@ *unittest\.skip|\.skip\(|\|\| *true|eslint-disable' "$CODIGO" 2>/dev/null || true)"
if [ -n "$SUP" ]; then rojo "hay señales suprimidas:"; echo "$SUP" | head -3 | sed 's/^/     /'; else verde "sin señales suprimidas"; fi
if grep -rnE "\bTODO\b" "$CODIGO" --exclude-dir=__pycache__ 2>/dev/null | grep -q .; then rojo "quedaron TODO sueltos en $CODIGO/"; else verde "sin TODO sueltos"; fi

# ── 4. ¿Los tests distinguen? (sólo en modo tarea)
# Revierte la implementación y exige que la suite FALLE. Un test que pasa con el código
# viejo no prueba nada, y no hay otra forma de que el gate lo detecte.
if [ -n "${TAREA:-}" ]; then
  echo "── 4. ¿Los tests distinguen?"
  IMPL="$(echo "$CAMBIADOS" | grep -E "^$CODIGO/" || true)"
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
    ESPERADO="$(sed -n 's/.*`\(tests\/[A-Za-z0-9_.]*\)`.*clase `\([A-Za-z0-9_]*\)`.*/\1 \2/p' \
                 "tareas/${TAREA}"-*.md 2>/dev/null | head -1)"
    if bash scripts/correr-suite.sh >/dev/null 2>&1; then
      rojo "los tests PASAN con la implementación vieja: no verifican el cambio"
      echo "     revertí:$REVERTIDOS y la suite siguió verde"
    elif [ -n "$ESPERADO" ]; then
      RUTA_T="$(echo "$ESPERADO" | cut -d' ' -f1)"
      CLASE="$(echo "$ESPERADO" | cut -d' ' -f2)"
      if bash scripts/correr-suite.sh "$RUTA_T::$CLASE" >/dev/null 2>&1; then
        rojo "la suite falla, pero NO por los tests de esta tarea ($CLASE pasa con el código viejo)"
        echo "     o los tests de $TAREA no verifican el cambio, o rompiste otra cosa"
      else
        verde "fallan los tests de la tarea ($CLASE) al revertir$REVERTIDOS"
        testigo "$RUTA_T::$CLASE, revirtiendo$REVERTIDOS"
      fi
    else
      vacuo "la tarea no nombra archivo y clase de test: sólo se pudo verificar la suite entera"
    fi
    for f in $REVERTIDOS; do cp "$TMP/$(echo "$f" | tr / _)" "$f"; done
  fi
  rm -rf "$TMP"
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
