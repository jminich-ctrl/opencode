#!/usr/bin/env bash
# Corre LA MISMA tarea con varios modelos y compara el resultado.
#
#   bash $AGENTES/scripts/comparar-modelos.sh T03 \
#       colabhive/f5d76140-... colabhive/1af07b1f-...
#   (el ejemplo, desde la raíz de este repo: PROYECTO=ejemplo-pacman bash scripts/comparar-modelos.sh ...)
#
# Es la única forma honesta de elegir modelo para un rol: los benchmarks públicos
# no miden si un modelo llama a las herramientas o se queda deliberando.
#
# Por cada modelo informa: gate (verde/rojo), tiempo, herramientas usadas,
# líneas de deliberación y archivos tocados.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE: ver _comun.sh
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
[ $# -ge 2 ] || { echo "uso: $0 TNN modelo1 [modelo2 ...]" >&2; exit 1; }

TAREA="$1"; shift
archivo="$(ls "$BASE/tareas/${TAREA}"-*.md 2>/dev/null | head -1)"
[ -n "$archivo" ] || { echo "✗ no existe tareas/${TAREA}-*.md" >&2; exit 1; }
archivo="tareas/$(basename "$archivo")"
# El gate aplica sus reglas de tarea (sin cambios = rojo, alcance) sólo si sabe cuál es.
export TAREA

n=0
for modelo in "$@"; do
  n=$((n+1))
  wt="$RAIZ/../comparar-$TAREA-$n"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "comparar/$TAREA-$n" 2>/dev/null
  git -C "$RAIZ" worktree add -q -b "comparar/$TAREA-$n" "$wt" || continue
  echo "▶ $n: $modelo"
  (
    cd "$wt/$PROYECTO" || exit 1
    export XDG_DATA_HOME="$wt/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    inicio=$(date +%s)
    {
      echo "=== $TAREA · $modelo"
      opencode run --model "$modelo" "Implementá la tarea descrita en $archivo. Leela completa antes de empezar. Respetá los archivos permitidos y prohibidos. Al terminar corré 'bash scripts/gate.sh' y mostrá su salida real." 2>&1
    } > "$wt/.tarea.log" 2>&1
    duracion=$(( $(date +%s) - inicio ))
    # Veredicto por código de salida del gate, corrido cuando el agente ya terminó.
    # .segundos se escribe DESPUÉS: el gate vería un archivo nuevo fuera del alcance.
    cerrar_con_gate "$wt/.tarea.log" "$TAREA"
    echo "$duracion" > "$wt/.segundos"
  ) &
done
wait

echo
printf '%-3s %-26s %-8s %6s %6s %6s %s\n' '#' MODELO GATE SEGS TOOLS DELIB ARCHIVOS
printf '%.0s─' {1..88}; echo
n=0
for modelo in "$@"; do
  n=$((n+1))
  wt="$RAIZ/../comparar-$TAREA-$n"
  log="$wt/.tarea.log"
  if [ -n "$(error_del_agente "$log" 2>/dev/null)" ]; then gate="✗ error"
  elif [ "$(veredicto "$log")" = "VERDE" ]; then gate="✓ verde"
  else gate="✗ rojo"; fi
  segs="$(cat "$wt/.segundos" 2>/dev/null || echo '?')"
  tools="$(parte_del_agente "$log" 2>/dev/null | grep -cE '^\[0m(→|\$|✱)')"
  delib="$(parte_del_agente "$log" 2>/dev/null | wc -l | xargs)"
  archivos="$(git -C "$wt" status --short -- "$PROYECTO" 2>/dev/null \
              | grep -vc '\.opencode-data\|\.tarea\.log\|\.segundos' | xargs)"
  printf '%-3s %-26s %-8s %6s %6s %6s %s\n' "$n" "$(echo "$modelo" | cut -c1-26)" "$gate" "$segs" "${tools:-0}" "$delib" "$archivos"
done
echo
echo "TOOLS alto y DELIB bajo = el modelo actúa. Al revés = delibera y no produce."
echo "Diffs en $RAIZ/../comparar-$TAREA-N/  ·  borralos con: git worktree remove <carpeta>"
