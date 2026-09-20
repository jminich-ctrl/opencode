#!/usr/bin/env bash
# Lanza una o varias tareas, cada una en su propio worktree de git.
#
#   bash scripts/correr-tarea.sh T03              una tarea
#   bash scripts/correr-tarea.sh T03 T04 T05      varias en paralelo
#   PROYECTO=ejemplo-pacman bash scripts/correr-tarea.sh T02
#
# Cada tarea corre en ../trabajo-TNN sobre la rama tarea/TNN, con contexto limpio.
# Al terminar deja el log en ../trabajo-TNN/.tarea.log y corre el gate.
set -uo pipefail

PROYECTO="${PROYECTO:-.}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$RAIZ/$PROYECTO"
[ -d "$BASE/tareas" ] || { echo "✗ No encuentro $BASE/tareas (¿falta PROYECTO=?)" >&2; exit 1; }
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
[ $# -gt 0 ] || { echo "uso: $0 T01 [T02 ...]" >&2; exit 1; }

lanzar() {
  local id="$1"
  local archivo
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  [ -n "$archivo" ] || { echo "✗ $id: no existe tareas/${id}-*.md"; return 1; }

  local wt="$RAIZ/../trabajo-$id"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "tarea/$id" 2>/dev/null
  git -C "$RAIZ" worktree add -q -b "tarea/$id" "$wt" || { echo "✗ $id: no pude crear el worktree"; return 1; }

  local dir="$wt/$PROYECTO"
  echo "▶ $id lanzada en $dir"
  (
    cd "$dir" || exit 1
    {
      echo "=== $id · $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
      opencode run "Implementá la tarea descrita en $archivo. Leela completa antes de empezar. Respetá los archivos permitidos y prohibidos. Al terminar corré 'bash scripts/gate.sh' y mostrá su salida real." 2>&1
      echo "=== gate ==="
      bash scripts/gate.sh 2>&1
      echo "=== fin $id · $(date -u +'%H:%M:%S UTC')"
    } > "$wt/.tarea.log" 2>&1
    if grep -q "GATE VERDE" "$wt/.tarea.log"; then echo "✓ $id gate VERDE"; else echo "✗ $id gate ROJO"; fi
  ) &
}

for id in "$@"; do lanzar "$id"; done
wait
echo
echo "Logs en ../trabajo-TNN/.tarea.log · resumen: bash scripts/estado.sh"
