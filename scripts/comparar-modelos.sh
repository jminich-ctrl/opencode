#!/usr/bin/env bash
# Corre LA MISMA tarea con varios modelos y compara el resultado.
#
#   PROYECTO=ejemplo-pacman bash scripts/comparar-modelos.sh T03 \
#       colabhive/f5d76140-... colabhive/d7750d6c-...
#
# Es la única forma honesta de elegir modelo para un rol: los benchmarks públicos
# no miden si un modelo llama a las herramientas o se queda deliberando.
#
# Por cada modelo informa: gate (verde/rojo), tiempo, herramientas usadas,
# líneas de deliberación y archivos tocados.
set -uo pipefail

PROYECTO="${PROYECTO:-.}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$RAIZ/$PROYECTO"
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
[ $# -ge 2 ] || { echo "uso: $0 TNN modelo1 [modelo2 ...]" >&2; exit 1; }

TAREA="$1"; shift
archivo="$(ls "$BASE/tareas/${TAREA}"-*.md 2>/dev/null | head -1)"
[ -n "$archivo" ] || { echo "✗ no existe tareas/${TAREA}-*.md" >&2; exit 1; }
archivo="tareas/$(basename "$archivo")"

n=0
for modelo in "$@"; do
  n=$((n+1))
  etiqueta="$(echo "$modelo" | tr '/' '-' | cut -c1-24)"
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
      opencode run --model "$modelo" "Implementá la tarea descrita en $archivo. Leela completa antes de empezar. Respetá los archivos permitidos y prohibidos. Al terminar corré 'bash scripts/gate.sh' y mostrá su salida real." 2>&1
      echo "=== gate ==="; bash scripts/gate.sh 2>&1
    } > "$wt/.tarea.log" 2>&1
    echo "$(( $(date +%s) - inicio ))" > "$wt/.segundos"
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
  gate="?"; grep -q "GATE VERDE" "$log" 2>/dev/null && gate="✓ verde" || gate="✗ rojo"
  grep -qiE 'inference timed out|database is locked' "$log" 2>/dev/null && gate="✗ error"
  segs="$(cat "$wt/.segundos" 2>/dev/null || echo '?')"
  tools="$(grep -cE '^\[0m(→|\$|✱)' "$log" 2>/dev/null || echo 0)"
  delib="$(sed -n '1,/=== gate ===/p' "$log" 2>/dev/null | wc -l | xargs)"
  archivos="$(git -C "$wt/$PROYECTO" status --short 2>/dev/null | grep -vc '\.opencode-data\|\.tarea.log' | xargs)"
  printf '%-3s %-26s %-8s %6s %6s %6s %s\n' "$n" "$(echo "$modelo" | cut -c1-26)" "$gate" "$segs" "$tools" "$delib" "$archivos"
done
echo
echo "TOOLS alto y DELIB bajo = el modelo actúa. Al revés = delibera y no produce."
echo "Diffs en ../comparar-$TAREA-N/  ·  borralos con: git worktree prune"
