#!/usr/bin/env bash
# Lanza una o varias tareas, cada una en su propio worktree de git.
#
#   bash scripts/correr-tarea.sh T03              una tarea
#   bash scripts/correr-tarea.sh T03 T04 T05      varias en paralelo
#   PROYECTO=ejemplo-pacman bash scripts/correr-tarea.sh T02
#   PARALELAS=8 bash scripts/correr-tarea.sh T02 T03 T04    baja el tope
#
# Corren hasta PARALELAS a la vez (16 por defecto). Medido sobre Qwen3-8B: hasta 16
# el costo de sumar tareas es casi cero; con 24 empieza a formarse cola (la peor
# request salta de 3 s a 12,6 s) y el throughput ya no sube. Ver INFRAESTRUCTURA.md.
#
# Cada tarea corre en ../trabajo-TNN sobre la rama tarea/TNN, con contexto limpio.
# Al terminar deja el log en ../trabajo-TNN/.tarea.log y corre el gate.
set -uo pipefail

PROYECTO="${PROYECTO:-.}"
PARALELAS="${PARALELAS:-16}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$RAIZ/$PROYECTO"
[ -d "$BASE/tareas" ] || { echo "✗ No encuentro $BASE/tareas (¿falta PROYECTO=?)" >&2; exit 1; }
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
[ $# -gt 0 ] || { echo "uso: $0 T01 [T02 ...]" >&2; exit 1; }
[ $# -gt "$PARALELAS" ] && echo "· $# tareas, de a $PARALELAS por vez"

lanzar() {
  local id="$1"
  local archivo
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  [ -n "$archivo" ] || { echo "✗ $id: no existe tareas/${id}-*.md"; return 1; }
  # Ruta RELATIVA al worktree: si le pasamos la absoluta del repo original, OpenCode
  # la ve como external_directory y rechaza leerla por permisos.
  archivo="tareas/$(basename "$archivo")"

  # El worktree se crea desde HEAD: los cambios sin commitear (al gate, por ejemplo)
  # NO viajan. Commiteá antes de lanzar.
  local wt="$RAIZ/../trabajo-$id"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "tarea/$id" 2>/dev/null
  git -C "$RAIZ" worktree add -q -b "tarea/$id" "$wt" || { echo "✗ $id: no pude crear el worktree"; return 1; }

  local dir="$wt/$PROYECTO"
  echo "▶ $id lanzada en $dir"
  (
    cd "$dir" || exit 1
    # OpenCode guarda su estado en SQLite y dos procesos sobre la misma base
    # chocan con "database is locked": cada tarea necesita el suyo.
    export XDG_DATA_HOME="$wt/.opencode-data"
    mkdir -p "$XDG_DATA_HOME"
    {
      echo "=== $id · $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
      opencode run "Implementá la tarea descrita en $archivo. Leela completa antes de empezar. Respetá los archivos permitidos y prohibidos. Al terminar corré 'bash scripts/gate.sh' y mostrá su salida real." 2>&1
      echo "=== gate ==="
      bash scripts/gate.sh 2>&1
      echo "=== fin $id · $(date -u +'%H:%M:%S UTC')"
    } > "$wt/.tarea.log" 2>&1
    # Un error de OpenCode manda, aunque el gate diga verde: si el agente no llegó a
    # trabajar, el gate solo está viendo el repo intacto.
    # Leer SOLO el gate que corrimos nosotros (después de "=== gate ==="), nunca el
    # log entero: el agente escribe "GATE VERDE" en su prosa aunque el gate esté rojo.
    # Pasó de verdad: el modelo afirmó "El gate.sh indica GATE VERDE" con 2 tests fallando.
    veredicto="$(sed -n '/^=== gate ===$/,$p' "$wt/.tarea.log" | grep -m1 -oE 'GATE (VERDE|ROJO)')"
    if grep -qE 'inference timed out|database is locked' "$wt/.tarea.log"; then
      echo "✗ $id ERROR del agente: $(grep -m1 -oE 'inference timed out[^\"]*|database is locked' "$wt/.tarea.log")"
    elif [ "$veredicto" = "GATE VERDE" ]; then echo "✓ $id gate VERDE"
    else echo "✗ $id gate ROJO"; fi
  ) &
}

for id in "$@"; do
  # esperar a que se libere un lugar antes de lanzar la próxima
  while [ "$(jobs -rp | wc -l)" -ge "$PARALELAS" ]; do wait -n 2>/dev/null || sleep 1; done
  lanzar "$id"
done
wait
echo
echo "Logs en ../trabajo-TNN/.tarea.log · resumen: bash scripts/estado.sh"
