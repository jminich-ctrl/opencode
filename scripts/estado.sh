#!/usr/bin/env bash
# Resumen de en qué anda cada tarea.
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROYECTO="${PROYECTO:-ejemplo-pacman}"
BASE="$RAIZ/$PROYECTO"

printf '%-6s %-38s %-10s %s\n' TAREA TÍTULO ESTADO DETALLE
printf '%.0s─' {1..90}; echo
for f in "$BASE"/tareas/T*.md; do
  [ -e "$f" ] || continue
  id="$(basename "$f" | cut -d- -f1)"
  titulo="$(head -1 "$f" | sed 's/^# T[0-9]* — //' | cut -c1-36)"
  wt="$RAIZ/../trabajo-$id"
  if [ ! -d "$wt" ]; then
    estado="pendiente"; detalle=""
  elif grep -q "GATE VERDE" "$wt/.tarea.log" 2>/dev/null; then
    estado="✓ verde"; detalle="$(git -C "$wt" diff --stat HEAD 2>/dev/null | tail -1 | xargs)"
  elif grep -q "=== fin" "$wt/.tarea.log" 2>/dev/null; then
    estado="✗ rojo"; detalle="$(grep -m1 -E 'FAIL|ERROR|✗' "$wt/.tarea.log" | cut -c1-40)"
  else
    estado="… corriendo"; detalle="$(wc -l < "$wt/.tarea.log" 2>/dev/null | xargs) líneas de log"
  fi
  printf '%-6s %-38s %-10s %s\n' "$id" "$titulo" "$estado" "$detalle"
done
