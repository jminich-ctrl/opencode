#!/usr/bin/env bash
# Resumen de en qué anda cada tarea.
#   bash $AGENTES/scripts/estado.sh                     desde tu proyecto
#   PROYECTO=ejemplo-pacman bash scripts/estado.sh      el ejemplo, desde la raíz de este repo
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE: ver _comun.sh

printf '%-6s %-38s %-10s %s\n' TAREA TÍTULO ESTADO DETALLE
printf '%.0s─' {1..90}; echo
for f in "$BASE"/tareas/T*.md; do
  [ -e "$f" ] || continue
  id="$(basename "$f" | cut -d- -f1)"
  titulo="$(head -1 "$f" | sed 's/^# T[0-9]* — //' | cut -c1-36)"
  wt="$RAIZ/../trabajo-$id"
  log="$wt/.tarea.log"
  if grep -q '^\*\*Estado:\*\* ✅' "$f" 2>/dev/null && [ ! -d "$wt" ]; then
    estado="✅ hecha"; detalle="mergeada"
  elif [ ! -d "$wt" ]; then
    estado="pendiente"; detalle=""
  else
    # El veredicto es el código de salida del gate que corrió el runner (ver _comun.sh),
    # nunca lo que el agente escribió.
    v="$(veredicto "$log")"
    error="$( [ -f "$log" ] && error_del_agente "$log")"
    if [ -z "$v" ]; then
      estado="… corriendo"; detalle="$(wc -l < "$log" 2>/dev/null | xargs) líneas de log"
    elif [ -n "$error" ]; then
      estado="✗ error"; detalle="$(echo "$error" | cut -c1-50)"
    elif [ "$v" = "VERDE" ]; then
      estado="✓ verde"; detalle="$(git -C "$wt" status --short -- "$PROYECTO" 2>/dev/null | grep -vc '\.tarea\.log\|\.opencode-data' | xargs) archivos cambiados"
    else
      estado="✗ rojo"; detalle="$(awk '$0 == "=== gate ===" { s = ""; next } { s = s $0 "\n" } END { printf "%s", s }' "$log" | grep -m1 '✗' | sed 's/^ *//' | cut -c1-50)"
    fi
  fi
  printf '%-6s %-38s %-10s %s\n' "$id" "$titulo" "$estado" "$detalle"
done
