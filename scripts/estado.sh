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
  # `T[0-9]*` no cubre los sufijos: con T04b y T06a el título salía como «# T04b — …» y la
  # columna quedaba ilegible justo en las tareas partidas, que son las que más se miran.
  titulo="$(head -1 "$f" | sed 's/^# *T[0-9]*[a-z]* *— *//' | cut -c1-36)"
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
    elif [ "$v" = "IMPOSIBLE" ]; then
      estado="⃠ imposible"; detalle="$(motivo_imposible "$log" | cut -c1-50)"
    elif [ "$v" = "VERDE" ]; then
      estado="✓ verde"; detalle="$(git -C "$wt" status --short -- "$PROYECTO" 2>/dev/null | grep -vc '\.tarea\.log\|\.opencode-data' | xargs) archivos cambiados"
    else
      estado="✗ rojo"; detalle="$(awk '$0 == "=== gate ===" { s = ""; next } { s = s $0 "\n" } END { printf "%s", s }' "$log" | grep -m1 '✗' | sed 's/^ *//' | cut -c1-50)"
    fi
  fi
  printf '%-6s %-38s %-10s %s\n' "$id" "$titulo" "$estado" "$detalle"
done

# ── El tronco
# Entre "el worktree de la tarea da verde" y "main da verde" hay un paso que no tenía
# comando, y nos costó tener el repo de ejemplo publicado en rojo (BITACORA §13).
# Los gates corren por tarea; esto corre sobre lo que está mergeado.
if [ -x "$BASE/scripts/gate.sh" ]; then
  echo
  # Una sola corrida: estaba corriendo el gate DOS veces —una muda para el if y otra para
  # mostrar el error—, así que la suite del tronco se pagaba dos veces en cada estado.sh.
  salida="$( cd "$BASE" && TAREA= bash scripts/gate.sh 2>&1 )"
  rc=$?   # pegado a la asignación: cualquier cosa en el medio y esto lee el estado de ESO
  if [ "$rc" -eq 0 ]; then
    echo "tronco: ✓ verde"
  else
    # Durante una etapa tests-first el tronco está rojo POR DISEÑO: los tests de la etapa se
    # aceptan y commitean antes de que exista la implementación. Decir «ROJO» a secas es un
    # veredicto que no puede dar verde mientras eso dure, y un número que no puede fallar no
    # mide nada (MEDICION.md). Casi leí este rojo como una rotura real.
    en_vuelo=""
    for f in "$BASE"/tareas/T*.md; do
      [ -e "$f" ] || continue
      grep -q '^\*\*Estado:\*\* *✅' "$f" 2>/dev/null && continue
      # Mismo extractor que el paso 4 del gate: «Archivo: `x`, clase `Y`».
      t_decl="$(sed -n 's/.*`\([^`]*\)`, *clase `[A-Za-z0-9_]*`.*/\1/p' "$f" | head -1)"
      [ -n "$t_decl" ] && [ -f "$BASE/$t_decl" ] \
        && en_vuelo="$en_vuelo    $t_decl ← $(basename "$f" | cut -d- -f1), pendiente"$'\n'
    done
    if [ -n "$en_vuelo" ]; then
      echo "tronco: ✗ rojo POR DISEÑO — tests de tareas pendientes ya commiteados:"
      printf '%s' "$en_vuelo"
      echo "  Mientras siga así este veredicto no puede dar verde, así que no mide el tronco."
      echo "  Lo que mide es el gate de cada tarea, que descuenta la línea base."
    else
      echo "tronco: ✗ ROJO — lo mergeado no pasa su propio gate:"
      printf '%s\n' "$salida" | grep '✗' | sed 's/^/  /'
    fi
  fi
fi
