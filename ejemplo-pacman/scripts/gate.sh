#!/usr/bin/env bash
# Gate G1: decide si una tarea está terminada. No opina, ejecuta.
#   1) tests   2) alcance   3) higiene
# Verde => imprime "GATE VERDE". Cualquier rojo => sale con código 1.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
FALLOS=0
rojo() { echo "  ✗ $1"; FALLOS=$((FALLOS+1)); }
verde() { echo "  ✓ $1"; }

echo "── 1. Tests"
SALIDA="$(python3 -m unittest discover -s tests -t . -q 2>&1)"
if echo "$SALIDA" | grep -qE '^(OK|Ran 0 tests)'; then
  verde "$(echo "$SALIDA" | grep -E '^Ran ' | head -1)"
else
  rojo "tests en rojo"; echo "$SALIDA" | tail -15 | sed 's/^/     /'
fi

echo "── 2. Alcance${TAREA:+ (tarea $TAREA)}"
# archivos modificados respecto del punto de partida de la rama
BASE_REF="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD)"
CAMBIADOS="$(git diff --name-only "$BASE_REF" 2>/dev/null; git ls-files --others --exclude-standard)"
if [ -z "$CAMBIADOS" ] && [ -n "${TAREA:-}" ]; then
  rojo "no hay ningún cambio: la tarea no se hizo"
elif [ -z "$CAMBIADOS" ]; then
  verde "árbol limpio (modo integración)"
else
  echo "$CAMBIADOS" | sed 's/^/     /' | sort -u
  # El alcance sale del archivo de la tarea, no de reglas hardcodeadas acá: una regla
  # escrita a mano queda vieja en cuanto el plan crece (nos pasó con render.py y T12).
  PERMITIDOS="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/${TAREA:-}"-*.md 2>/dev/null \
                | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+\.(py|txt|md)' | sort -u)"
  if [ -z "${TAREA:-}" ] || [ -z "$PERMITIDOS" ]; then
    verde "sin límite de alcance declarado"
  else
    FUERA=""
    while read -r archivo; do
      [ -n "$archivo" ] || continue
      echo "$PERMITIDOS" | grep -qF "$(basename "$archivo")" || FUERA="$FUERA $archivo"
    done <<< "$CAMBIADOS"
    if [ -n "$FUERA" ]; then
      rojo "archivos fuera del alcance de $TAREA:$FUERA"
      echo "     permitidos: $(echo "$PERMITIDOS" | tr '\n' ' ')"
    else
      verde "todo dentro del alcance declarado en tareas/$TAREA-*.md"
    fi
  fi
fi

echo "── 3. Higiene"
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
if grep -rqE '^\s*(import|from)\s+(pygame|numpy|pytest)' src/ 2>/dev/null; then rojo "dependencia externa en src/"; else verde "solo biblioteca estándar"; fi
if grep -rn "TODO" src/ 2>/dev/null | grep -qv '^\s*$'; then rojo "quedaron TODO en src/: $(grep -rn 'TODO' src/ | head -2 | tr '\n' ' ')"; else verde "sin TODO sueltos"; fi
if ! python3 -m compileall -q src/ >/dev/null 2>&1; then rojo "src/ no compila"; else verde "src/ compila"; fi

echo
if [ "$FALLOS" -eq 0 ]; then echo "GATE VERDE"; exit 0; else echo "GATE ROJO ($FALLOS fallo/s)"; exit 1; fi
