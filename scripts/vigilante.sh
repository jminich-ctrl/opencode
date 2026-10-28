#!/usr/bin/env bash
# El vigilante de que NO SE FRENE. Pedido literal: «no frenes por nada, poné un watchdog que
# haga que no frenes».
#
# Qué hace: cada ciclo mira si hay trabajo vivo —suite o corridas de agente—. Si no hay nada
# y la cola tiene algo pendiente, lanza lo que sigue. Si la cola está vacía, lo DICE, porque
# una cola vacía es la única forma legítima de que no haya nada corriendo y hay que verla.
#
# Lo que NO hace: inventar trabajo. Ejecuta la cola que se le llena a mano
# (`watchdog-cola.txt`, un comando por línea). Un vigilante que elige qué correr decide por
# su cuenta y gasta plataforma sin que nadie lo haya pedido.
#
# Guardias, en este orden:
#   · disco por debajo de 2 Gi  → para y lo escribe (acuerdo con Jose)
#   · `watchdog.stop` presente  → para
#   · más de MAX_POR_HORA lanzamientos en la última hora → espera
set -uo pipefail
# El directorio de trabajo lo pasa quien llama: un vigilante con una ruta de sesión clavada
# sólo sirve en esa sesión.
#
#   DONDE=<dir> bash scripts/vigilante.sh
#
# En <dir> espera `cola.txt`, una entrada por línea con el formato `<id>|<comando>`.
S="${DONDE:?falta DONDE=<directorio con cola.txt>}"
mkdir -p "$S"
COLA="$S/cola.txt"
HECHO="$S/hechos.txt"
LOG="$S/vigilante.log"
CICLO="${CICLO:-120}"
MAX_POR_HORA="${MAX_POR_HORA:-6}"
touch "$COLA" "$HECHO"

decir() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*" >> "$LOG"; }

hay_trabajo_vivo() {
  pgrep -f "unittest pruebas.test_metodo" >/dev/null 2>&1 && return 0
  pgrep -f "scripts/correr-todo.sh" >/dev/null 2>&1 && return 0
  pgrep -f "opencode run" >/dev/null 2>&1 && return 0
  return 1
}

lanzamientos_ultima_hora() {
  local ahora corte n=0 ts
  ahora=$(date +%s); corte=$((ahora - 3600))
  while read -r ts _; do
    case "$ts" in ''|*[!0-9]*) continue ;; esac
    [ "$ts" -ge "$corte" ] && n=$((n+1))
  done < "$HECHO"
  echo "$n"
}

decir "▶ vigilante arriba · ciclo ${CICLO}s · tope ${MAX_POR_HORA}/hora"
while :; do
  if [ -f "$S/parar" ]; then decir "■ parado por el archivo «parar»"; exit 0; fi

  libre=$(df -g /System/Volumes/Data 2>/dev/null | awk 'NR==2{print $4}')
  case "$libre" in ''|*[!0-9]*) libre=99 ;; esac
  if [ "$libre" -lt 2 ]; then
    decir "■ disco en ${libre}Gi, por debajo del acuerdo de 2Gi: NO lanzo nada más"
    sleep "$CICLO"; continue
  fi

  if hay_trabajo_vivo; then
    sleep "$CICLO"; continue
  fi

  # Nada vivo. ¿Hay cola?
  #
  # La entrada se identifica por un ID ESTABLE que va en la propia línea, no por su texto ni
  # por su posición. Las dos formas anteriores fallaron el 2026-10-28, cada una a su modo:
  #
  #   · por texto (`grep -vxFf`): tres líneas idénticas se consumían de una, y el watchdog
  #     informaba «cola vacía» con dos pendientes.
  #   · por número de línea: al REEMPLAZAR la cola, los números se reusan, así que entradas
  #     nuevas nacían marcadas como hechas —y otra vez «cola vacía» con trabajo pendiente—.
  #
  # Las dos veces el síntoma salió por el mensaje que existe para avisar que NO hay trabajo,
  # así que un aviso correcto afirmaba algo falso. El id lo escribe quien llena la cola, con
  # el formato `<id>|<comando>`; una línea sin id se informa y se saltea, porque adivinarle
  # un id es volver al problema.
  id_pend=""; pendiente=""
  while IFS= read -r linea; do
    case "$linea" in ''|[[:space:]]*'#'*|'#'*) continue ;; esac
    [ -n "$(printf '%s' "$linea" | tr -d '[:space:]')" ] || continue
    case "$linea" in
      *'|'*) ;;
      *) decir "⊘ entrada sin id, la salteo: ${linea%% *}…"; continue ;;
    esac
    i="${linea%%|*}"; cmd="${linea#*|}"
    grep -qF "|$i|" "$HECHO" 2>/dev/null && continue
    id_pend="$i"; pendiente="$cmd"; break
  done < "$COLA"
  if [ -z "$pendiente" ]; then
    decir "⊘ nada vivo y la cola está VACÍA — hay que llenarla: $COLA"
    sleep "$CICLO"; continue
  fi

  n=$(lanzamientos_ultima_hora)
  if [ "$n" -ge "$MAX_POR_HORA" ]; then
    decir "· tope: $n lanzamiento(s) en la última hora, espero"
    sleep "$CICLO"; continue
  fi

  decir "▶ lanzo [$id_pend]: $pendiente"
  printf '%s |%s| %s\n' "$(date +%s)" "$id_pend" "$pendiente" >> "$HECHO"
  nohup bash -c "$pendiente" >> "$S/salidas.log" 2>&1 &
  sleep "$CICLO"
done
