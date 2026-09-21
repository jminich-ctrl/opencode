#!/usr/bin/env bash
# Lanza una o varias tareas, cada una en su propio worktree de git.
#
# Se corre desde adentro del repo de tu proyecto (el que tiene tareas/):
#   bash $AGENTES/scripts/correr-tarea.sh T03              una tarea
#   bash $AGENTES/scripts/correr-tarea.sh T03 T04 T05      varias en paralelo
#   PARALELAS=4 bash $AGENTES/scripts/correr-tarea.sh T02 T03 T04    baja el tope
# El ejemplo de este repo, desde su raíz:
#   PROYECTO=ejemplo-pacman bash scripts/correr-tarea.sh T02
#
# Corren hasta PARALELAS a la vez (8 por defecto). Medido el 2026-09-21: una réplica
# admite 8 pedidos a la vez y el resto espera turno, así que pasado 8 el throughput ya
# no sube. Con la misma key, además, todas comparten su tope de pedidos por minuto.
# Ver INFRAESTRUCTURA.md.
#
# Cada tarea corre en ../trabajo-TNN sobre la rama tarea/TNN, con contexto limpio.
# Cuando el agente termina, el runner corre el gate y deja todo en ../trabajo-TNN/.tarea.log.
set -uo pipefail

PARALELAS="${PARALELAS:-8}"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE: ver _comun.sh
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
    # El gate endurece sus reglas cuando sabe que corre dentro de una tarea:
    # exige que haya cambios y aplica los límites de alcance.
    export TAREA="$id"
    export XDG_DATA_HOME="$wt/.opencode-data"
    mkdir -p "$XDG_DATA_HOME"
    local log="$wt/.tarea.log"
    {
      echo "=== $id · $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
      opencode run "Implementá la tarea descrita en $archivo. Leela completa antes de empezar. Respetá los archivos permitidos y prohibidos. Al terminar corré 'bash scripts/gate.sh' y mostrá su salida real." 2>&1
    } > "$log" 2>&1
    # El agente ya terminó. Recién ahora corre el gate, y el veredicto es su código de
    # salida: nunca lo que el agente escribió. Pasó de verdad: el modelo afirmó
    # "El gate.sh indica GATE VERDE" después de ver fallar el gate tres veces.
    local error
    error="$(error_del_agente "$log")"
    cerrar_con_gate "$log" "$id"
    local rc=$?
    if [ -n "$error" ]; then echo "✗ $id ERROR del agente: $error"
    elif [ "$rc" -eq 0 ]; then echo "✓ $id gate VERDE"
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
PREF=""; [ "$PROYECTO" != "." ] && PREF="PROYECTO=$PROYECTO "
echo "Logs en $RAIZ/../trabajo-TNN/.tarea.log · resumen: ${PREF}bash $AQUI/estado.sh"
