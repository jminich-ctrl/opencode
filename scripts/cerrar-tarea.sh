#!/usr/bin/env bash
# Cierra una tarea hecha a mano: corre el gate, anota el intento y commitea si da verde.
#
#   bash scripts/cerrar-tarea.sh T03
#
# Existe para que el método funcione sin IA: una persona hace la tarea en el worktree y
# el veredicto lo sigue dando el gate, no la persona. El juez es el mismo para todos.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
ID="${1:-}"
[ -n "$ID" ] || { echo "uso: $0 TNN" >&2; exit 1; }

WT="$RAIZ/../trabajo-$ID"
[ -d "$WT/$PROYECTO" ] || { echo "✗ No existe $WT/$PROYECTO — ¿corriste correr-tarea.sh $ID?" >&2; exit 1; }

LOG="$WT/.tarea.log"
[ -f "$LOG" ] || printf '=== %s · hecha a mano · %s\n' "$ID" "$(date -u +'%Y-%m-%d %H:%M:%S UTC')" > "$LOG"

cd "$WT/$PROYECTO" || exit 1
export TAREA="$ID"
cerrar_con_gate "$LOG" "$ID"
rc=$?
anotar_intento "$ID" "$(veredicto "$LOG")" 0 humano "$LOG"

if [ "$rc" -eq 0 ]; then
  echo "✓ $ID gate VERDE — commiteada en la rama tarea/$ID"
  # Las abstenciones del gate, acá abajo. Éste es el camino que corre una PERSONA para
  # cerrar una tarea a mano, así que es el peor lugar donde esconderlas: el gate sale 0
  # habiéndose abstenido en chequeos y esta línea decía VERDE a secas. Van en líneas
  # aparte y no dentro de la línea del ✓ porque acá nadie lee en paralelo.
  NO_JUZGADO="$(no_juzgado_por_el_gate "$LOG")"
  [ -n "$NO_JUZGADO" ] && printf '%s\n' "$NO_JUZGADO" | sed 's/^/  ⊘ no juzgado: /'
else
  echo "✗ $ID gate ROJO — mirá el detalle arriba; la tarea no está terminada"
fi
exit "$rc"
