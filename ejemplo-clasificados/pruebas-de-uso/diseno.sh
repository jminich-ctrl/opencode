#!/usr/bin/env bash
# `diseno` — sistema de diseño propio en SCSS. OBJETIVO.md: «queremos que se vea bien».
# No alcanza con que los .scss existan: tienen que LLEGAR a la página servida.
set -uo pipefail
PROY="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROY" || exit 1
SALIDA="$(npm --prefix frontend run build 2>&1)" || {
  echo "el frontend no se puede construir, así que no hay página que mirar:"
  printf '%s\n' "$SALIDA" | grep -iE "error|could not" | head -3
  exit 1
}
HTML="$(ls frontend/dist/index.html 2>/dev/null)"
[ -n "$HTML" ] || { echo "el build no dejó frontend/dist/index.html"; exit 1; }
if grep -qE '<link[^>]+rel="stylesheet"' "$HTML"; then
  echo "la página construida trae su hoja de estilo"; exit 0
fi
echo "la página construida NO referencia ninguna hoja de estilo: el SCSS no llega al build"
exit 1
