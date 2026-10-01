# Funciones compartidas por correr-tarea.sh, estado.sh y comparar-modelos.sh.
# Se carga con `.`; no se ejecuta sola. Compatible con el bash 3.2 de macOS.

# Ubica el proyecto: el repo git del directorio actual (no el de estos scripts), así el
# mismo runner sirve para tu proyecto y para ejemplo-pacman. Deja RAIZ, PROYECTO y BASE.
#   RAIZ      el worktree principal del repo: correr esto desde adentro de un
#             ../trabajo-TNN no lo toma como repo (lo borraría al relanzar)
#   PROYECTO  la carpeta con tareas/, relativa a RAIZ. Si no viene en el entorno, la
#             más cercana hacia arriba desde donde estás parado
#   BASE      $RAIZ/$PROYECTO
ubicar_proyecto() {
  git rev-parse --show-toplevel >/dev/null 2>&1 \
    || { echo "✗ Corré esto desde adentro del repo git de tu proyecto" >&2; exit 1; }
  RAIZ="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
  if [ -z "${PROYECTO:-}" ]; then
    local rel
    rel="$(git rev-parse --show-prefix)"
    rel="${rel%/}"
    while [ -n "$rel" ] && [ ! -d "$RAIZ/$rel/tareas" ]; do
      case "$rel" in */*) rel="${rel%/*}" ;; *) rel="" ;; esac
    done
    PROYECTO="${rel:-.}"
    # Si desde acá no se ve ningún tareas/ hacia arriba, mirá hacia abajo: cuando hay
    # exactamente un proyecto en el repo, no tiene sentido exigir PROYECTO= a mano.
    if [ ! -d "$RAIZ/$PROYECTO/tareas" ]; then
      local candidatos n
      candidatos="$(cd "$RAIZ" && find . -maxdepth 2 -type d -name tareas -not -path '*/.git/*' \
                    | sed 's|^\./||; s|/tareas$||')"
      n="$(echo "$candidatos" | grep -c . || true)"
      if [ "$n" = "1" ]; then
        PROYECTO="$candidatos"
        echo "· proyecto detectado: $PROYECTO" >&2
      elif [ "${n:-0}" -gt 1 ]; then
        echo "✗ Hay varios proyectos en el repo; elegí uno con PROYECTO=<carpeta>:" >&2
        echo "$candidatos" | sed 's/^/    /' >&2
        exit 1
      fi
    fi
  fi
  BASE="$RAIZ/$PROYECTO"
  [ -d "$BASE/tareas" ] \
    || { echo "✗ No encuentro $BASE/tareas (¿falta PROYECTO=<carpeta con tareas/>?)" >&2; exit 1; }
}

# El log de una tarea tiene dos partes: lo que escribió el agente y, al final, lo que
# agrega el runner cuando el agente ya terminó:
#
#   === gate ===
#   <salida del gate>
#   === rc=<código de salida del gate>
#   === fin TNN · <hora>
#
# El veredicto sale del CÓDIGO DE SALIDA del gate, nunca del texto: el agente escribe
# "GATE VERDE" en su prosa aunque el gate esté rojo (pasó de verdad, ver BITACORA.md).

# Corre el gate en el directorio actual, agrega su salida al log y devuelve su código.
cerrar_con_gate() {
  local log="$1" id="$2" salida rc
  salida="$(bash scripts/gate.sh 2>&1)"
  rc=$?
  # El agente nunca commitea: deja todo sin trackear y `git merge tarea/TNN` no trae nada.
  # Si el gate dio verde, commiteamos nosotros para que la rama sea mergeable.
  if [ "$rc" = "0" ]; then
    git add -A >/dev/null 2>&1
    git -c user.name="agente" -c user.email="agente@local" \
        commit -q -m "$id: gate verde" >/dev/null 2>&1 \
      && printf '\n=== commiteado en la rama tarea/%s\n' "$id" >> "$log"
  fi
  printf '\n=== gate ===\n%s\n=== rc=%s\n=== fin %s · %s\n' \
    "$salida" "$rc" "$id" "$(date -u +'%H:%M:%S UTC')" >> "$log"
  return "$rc"
}

# La parte del agente: todo lo anterior a la ÚLTIMA marca "=== gate ===" (el agente
# podría imprimir una igual; la del runner siempre es la última).
parte_del_agente() {
  awk '{ l[NR] = $0; if ($0 == "=== gate ===") g = NR }
       END { n = g ? g - 1 : NR; for (i = 1; i <= n; i++) print l[i] }' "$1"
}

# Un error de OpenCode manda aunque el gate dé verde: si el agente no llegó a trabajar,
# el gate solo ve el repo intacto. Se busca sólo en la parte del agente, no en los tests.
error_del_agente() {
  parte_del_agente "$1" | grep -m1 -oE '^Error: .*|inference timed out[^"]*|database is locked'
}

# Registro de intentos: una línea por corrida, para que las métricas lean datos y no
# adivinen del texto de las tareas. Vive fuera del árbol versionado del proyecto.
anotar_intento() {
  local id="$1" ver="$2" segs="$3" modelo="${4:-}"
  local reg="$RAIZ/.metricas/intentos.csv"
  mkdir -p "$(dirname "$reg")"
  [ -f "$reg" ] || echo "fecha,proyecto,tarea,veredicto,segundos,modelo" > "$reg"
  echo "$(date -u +%FT%TZ),${PROYECTO:-.},$id,$ver,$segs,$modelo" >> "$reg"
}

# VERDE / ROJO / IMPOSIBLE si el runner ya cerró el log; vacío si la tarea sigue corriendo.
#
# IMPOSIBLE es un veredicto de primera clase, no un rojo: el agente declaró que la tarea no
# se puede hacer. Medido en dos estudios independientes: darle esa salida baja el reward
# hacking de 54% a 9% y de 23,6% a 5,3%. Sin ella, un modelo al que se le pide lo imposible
# hace pasar el test de alguna forma. Y NO se reintenta: reintentar lo imposible es
# exactamente la presión que produce la trampa.
veredicto() {
  local log="$1" rc
  [ -f "$log" ] || return 0
  tail -n 1 "$log" | grep -q '^=== fin ' || return 0
  # El orden importa y es P2: si el gate pudo decidir, decide el gate. IMPOSIBLE sólo
  # manda cuando el comando no dio verde — un agente que declara imposible y además deja
  # la suite en verde hizo el trabajo, y el trabajo verificado gana.
  rc="$(grep -E '^=== rc=[0-9]+$' "$log" | tail -n 1 | sed 's/^=== rc=//')"
  if [ "$rc" = "0" ]; then echo VERDE; return 0; fi
  if parte_del_agente "$log" | grep -qE '^ *IMPOSIBLE:'; then echo IMPOSIBLE; return 0; fi
  echo ROJO
}

# El motivo que declaró el agente, para que el humano lo lea sin abrir el log.
motivo_imposible() {
  parte_del_agente "$1" | grep -m1 -oE 'IMPOSIBLE:.*' | cut -c1-120
}

# Huella de la falla: qué rompió, en forma comparable entre intentos. Sale del primer ✗ del
# gate que corrió el runner, o del error de OpenCode si el agente no llegó a trabajar.
#
# Para qué: dos intentos que fallan por LO MISMO no son lo mismo que dos que fallan por
# cosas distintas. Lo primero es un problema de especificación y reintentar no lo arregla;
# lo segundo puede ser una tarea grande de más. El runner corta en el primer caso, y la
# distinción es la que el humano necesita para decidir (HUMANO.md §4).
huella_de_falla() {
  local log="$1" err
  [ -f "$log" ] || return 0
  err="$(error_del_agente "$log")"
  if [ -n "$err" ]; then echo "agente: $err" | cut -c1-90; return 0; fi
  awk '{ l[NR] = $0; if ($0 == "=== gate ===") g = NR }
       END { for (i = g + 1; i <= NR; i++) print l[i] }' "$log" \
    | grep -m1 '✗' | sed 's/^ *//; s/[0-9]\{2,\}/N/g' | cut -c1-90
}

# Cierra una tarea integrada: la marca hecha en su archivo (es lo que lee estado.sh),
# saca el worktree y borra la rama. Sin esto la tarea figura "verde" para siempre y nadie
# se entera de que está mergeada — o peor, de que no lo está.
marcar_hecha_y_limpiar() {
  local id="$1" rama="$2" archivo
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  if [ -n "$archivo" ]; then
    if grep -q '^\*\*Estado:\*\*' "$archivo"; then
      sed -i '' 's/^\*\*Estado:\*\*.*/**Estado:** ✅ hecha/' "$archivo" 2>/dev/null \
        || sed -i 's/^\*\*Estado:\*\*.*/**Estado:** ✅ hecha/' "$archivo"
    else
      # estado.sh lee esta línea; si falta, la tarea figura pendiente para siempre.
      sed -i '' '2i\
\
**Estado:** ✅ hecha
' "$archivo" 2>/dev/null || true
    fi
    git -C "$RAIZ" add "$archivo" >/dev/null 2>&1
    git -C "$RAIZ" commit -q -m "$id: hecha" >/dev/null 2>&1 || true
  fi
  git -C "$RAIZ" worktree remove --force "$RAIZ/../trabajo-$id" 2>/dev/null
  git -C "$RAIZ" branch -D "$rama" >/dev/null 2>&1
}
