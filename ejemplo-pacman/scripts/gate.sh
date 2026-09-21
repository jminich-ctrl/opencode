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

echo "── 2. Alcance"
# archivos modificados respecto del punto de partida de la rama
BASE_REF="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD)"
CAMBIADOS="$(git diff --name-only "$BASE_REF" 2>/dev/null; git ls-files --others --exclude-standard)"
if [ -z "$CAMBIADOS" ]; then
  rojo "no hay ningún cambio: la tarea no se hizo"
else
  echo "$CAMBIADOS" | sed 's/^/     /' | sort -u
  # render.py solo puede tocarse en la tarea T07
  # Regla de alcance por tarea. En integración (sin TAREA) no aplica: el tronco
  # junta el trabajo de todas las tareas.
  if [ -n "${TAREA:-}" ] && [ "$TAREA" != "T07" ] && echo "$CAMBIADOS" | grep -q 'render.py'; then
    rojo "render.py solo se toca en T07 (la lógica de juego no va ahí)"
  else
    verde "sin archivos fuera de lugar"
  fi
fi

echo "── 3. Higiene"
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
if grep -rqE '^\s*(import|from)\s+(pygame|numpy|pytest)' src/ 2>/dev/null; then rojo "dependencia externa en src/"; else verde "solo biblioteca estándar"; fi
if grep -rn "TODO" src/ 2>/dev/null | grep -qv '^\s*$'; then rojo "quedaron TODO en src/: $(grep -rn 'TODO' src/ | head -2 | tr '\n' ' ')"; else verde "sin TODO sueltos"; fi
if ! python3 -m compileall -q src/ >/dev/null 2>&1; then rojo "src/ no compila"; else verde "src/ compila"; fi

echo
if [ "$FALLOS" -eq 0 ]; then echo "GATE VERDE"; exit 0; else echo "GATE ROJO ($FALLOS fallo/s)"; exit 1; fi
