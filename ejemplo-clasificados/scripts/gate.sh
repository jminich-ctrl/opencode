#!/usr/bin/env bash
# Gate G1 del sitio de clasificados. Adaptado de ejemplo-pacman/scripts/gate.sh:
# mismo esqueleto, distinta suite (pytest atrás, vitest adelante) y distintas capas.
#   0) integridad  1) tests  2) alcance  3) higiene  4) ¿distinguen?  5) coherencia
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

# La base del diff la fija el runner al crear el worktree, antes de que el agente toque nada.
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

# ── 0. Integridad
# Los tests y el propio gate viven dentro del worktree del agente. La lista es fija acá y
# el archivo de tarea NO puede ampliarla.
INTOCABLES='^(backend/tests/|frontend/tests/|scripts/)'
if [ -n "${TAREA:-}" ]; then
  echo "── 0. Integridad"
  TOCADO="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null | grep -E "$INTOCABLES" || true)"
  if [ -n "$TOCADO" ]; then rojo "tocó archivos intocables (tests o el propio gate):"; echo "$TOCADO" | sed 's/^/     /'
  else verde "tests y scripts intactos"; fi
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
case "$RC" in
  0) RESUMEN="$(echo "$SALIDA" | grep -oE '[0-9]+ (passed|tests?)[^ ]*' | tail -1)"
     verde "${RESUMEN:-$(echo "$SALIDA" | grep -E '^Ran |^OK' | tail -1)}"
     testigo "scripts/correr-suite.sh, el mismo comando que valida los tests" ;;
  2) rojo "la suite no corrió ningún test: sin tests no hay gate"
     echo "$SALIDA" | tail -5 | sed 's/^/     /' ;;
  3) rojo "falta el corredor de tests — esto es del método, no del código que se juzga"
     echo "$SALIDA" | tail -5 | sed 's/^/     /'
     echo "     bash \$AGENTES/scripts/preparar-entorno.sh" ;;
  127) rojo "no existe scripts/correr-suite.sh: el proyecto no declara cómo se corre su suite"
     echo "     Copiala de plantillas/correr-suite.sh y adaptala. Sin ella, quien valida los"
     echo "     tests y quien los juzga vuelven a inventar cada uno su comando." ;;
  *) rojo "la suite está en rojo"
     echo "$SALIDA" | tail -15 | sed 's/^/     /' ;;
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
INFRA='^(\.base-ref|\.tarea\.log|\.segundos|\.plan\.log|\.opencode-data/|\.metricas/|\.venv(/|$)|\.entorno$|\.mysql(/|$)|([A-Za-z0-9_-]+/)?node_modules(/|$))'
CAMBIADOS="$( { git diff --name-only --relative "$BASE_REF" 2>/dev/null; git ls-files --others --exclude-standard; } | grep -vE "$INFRA" || true)"
if [ -z "$CAMBIADOS" ] && [ -n "${TAREA:-}" ]; then
  rojo "no hay ningún cambio: la tarea no se hizo"
elif [ -z "$CAMBIADOS" ]; then
  verde "árbol limpio (modo integración)"
else
  echo "$CAMBIADOS" | sed 's/^/     /' | sort -u
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
      ok=""
      while read -r permitido; do
        [ -n "$permitido" ] || continue
        case "$permitido" in
          */) case "$archivo" in "$permitido"*) ok=1 ;; esac ;;   # un directorio cubre lo de abajo
          *) [ "$archivo" = "$permitido" ] && ok=1 ;;
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
  fi
fi
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$|node_modules/|dist/'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
if grep -rqE 'tailwind' frontend/ --include=*.json --include=*.js --include=*.ts 2>/dev/null; then rojo "apareció Tailwind: el diseño es propio"; else verde "sin librerías de diseño"; fi
SUP="$(grep -rnEi '# *(noqa|type: *ignore)|except[^:]*: *pass|@ *unittest\.skip|\.skip\(|\|\| *true|eslint-disable' backend/app frontend/src 2>/dev/null || true)"
if [ -n "$SUP" ]; then rojo "hay señales suprimidas:"; echo "$SUP" | head -3 | sed 's/^/     /'; else verde "sin señales suprimidas"; fi
if grep -rnE "\bTODO\b" backend/app frontend/src --exclude-dir=__pycache__ 2>/dev/null | grep -q .; then rojo "quedaron TODO sueltos"; else verde "sin TODO sueltos"; fi

# ── 4. ¿Los tests distinguen? (sólo en modo tarea)
if [ -n "${TAREA:-}" ]; then
  echo "── 4. ¿Los tests distinguen?"
  IMPL="$(echo "$CAMBIADOS" | grep -E '^(backend/app|frontend/src)/.*\.(py|ts|tsx|jsx)$' || true)"
  TMP="$(mktemp -d)"; REVERTIDOS=""
  PREFIJO="$(git rev-parse --show-prefix)"   # vacío si el proyecto es la raíz del repo
  for f in $IMPL; do
    if git cat-file -e "HEAD:${PREFIJO}$f" 2>/dev/null; then
      cp "$f" "$TMP/$(echo "$f" | tr / _)"
      git checkout HEAD -- "$f" && REVERTIDOS="$REVERTIDOS $f"
    fi
  done
  if [ -z "$IMPL" ]; then vacuo "no hay implementación que revertir"
  elif [ -z "$REVERTIDOS" ]; then vacuo "archivos nuevos (no existían en HEAD): nada que revertir"
  else
    if bash scripts/correr-suite.sh >/dev/null 2>&1; then
      rojo "los tests PASAN con la implementación vieja: no verifican el cambio"
      echo "     revertí:$REVERTIDOS y la suite siguió verde"
    else verde "la suite falla al revertir$REVERTIDOS"; fi
    for f in $REVERTIDOS; do cp "$TMP/$(echo "$f" | tr / _)" "$f"; done
  fi
  rm -rf "$TMP"
fi

# ── 5. Coherencia (sólo en modo integración): lo único que mira a través de las tareas.
if [ -z "${TAREA:-}" ] && [ -f scripts/_arquitectura.py ]; then
  echo "── 5. Coherencia"
  if OUT="$("$PY_PROYECTO" scripts/_arquitectura.py 2>&1)"; then echo "$OUT"
  else echo "$OUT"; FALLOS=$((FALLOS+1)); fi
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
  if [ -d "$RESERVADOS" ] && ls "$RESERVADOS"/test_*.py >/dev/null 2>&1; then
    if OUT="$(PYTHONPATH="$PWD/backend" "$PY_PROYECTO" -m pytest -q "$RESERVADOS" 2>&1)"; then
      verde "$(echo "$OUT" | grep -E '^Ran ' | head -1) de composición"
    else
      rojo "la suite reservada falla: pasa los tests de las tareas y no hace lo que tiene que hacer"
      echo "$OUT" | tail -15 | sed 's/^/     /'
    fi
  else
    echo "  · no hay suite reservada en $RESERVADOS"
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
