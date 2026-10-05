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

# Una falla de la HERRAMIENTA, que es distinta de un error que el agente haya impreso al
# correr un comando. El patrón decía `^Error: .*` y atrapaba la salida de npm o de vite:
# T07 quedó informada como «ERROR del agente» con el gate en VERDE, que es exactamente lo
# contrario de lo que el método dice que hay que hacer.
#
# Y no manda sobre el gate: si el gate pudo decidir, decide el gate (P2). Esto sirve para
# explicar un rojo, o para distinguir «el agente no llegó a trabajar» de «trabajó mal»
# —aunque eso el gate ya lo dice con «no hay ningún cambio: la tarea no se hizo»—.
error_del_agente() {
  parte_del_agente "$1" \
    | grep -m1 -oE 'inference timed out[^"]*|database is locked|el agente no respondió[^"]*|Bad Gateway|Service Unavailable|Internal Server Error|50[0234] '
}

# ¿Responde la plataforma? Un 502 de nginx no es una falla de la tarea ni del agente, y
# reintentar contra una plataforma caída gasta el presupuesto de todas las tareas sin
# aprender nada. Pasó: la API pasó de responder en 3s a devolver 502 en TODO —incluido
# `/models`— y el método lo informaba como «el test no pasa ni con la implementación del
# propio agente», que es el diagnóstico más lejano posible de la causa.
plataforma_responde() {
  [ -n "${COLABHIVE_BASE_URL:-}" ] || return 0      # sin configurar, no opinamos
  local codigo
  # Contra `/chat/completions` CON herramientas, no contra `/models`. Listar modelos pasa
  # por otro camino: lo vimos devolver 200 mientras las peticiones reales de un agente
  # —20 KB de prompt y definiciones de herramientas— devolvían 502. Un chequeo que pasa
  # mientras el camino que importa falla es un falso verde, y éste iba a dejar arrancar una
  # corrida de nueve etapas contra una plataforma que no podía atenderla.
  codigo="$(curl -s -m 45 -o /dev/null -w '%{http_code}' \
            "$COLABHIVE_BASE_URL/chat/completions" \
            -H "Authorization: Bearer ${COLABHIVE_API_KEY:-}" \
            -H "Content-Type: application/json" \
            -d '{"model":"'"${MODELO_SONDA:-f5d76140-5b4d-41c0-88da-dad6d11f341a}"'",
                 "max_tokens":4,"messages":[{"role":"user","content":"OK"}],
                 "tools":[{"type":"function","function":{"name":"read",
                   "description":"sonda","parameters":{"type":"object",
                   "properties":{"p":{"type":"string"}}}}}]}' 2>/dev/null)"
  # Sin `|| echo 000`: cuando curl no conecta ya imprime «000» y además sale distinto de
  # cero, así que el `||` agregaba otro y el mensaje decía «HTTP 000000». Un mensaje con un
  # valor inventado es justo lo que vengo arreglando todo el día.
  codigo="${codigo:-000}"
  [ "$codigo" = "200" ] && return 0
  echo "✗ la plataforma de modelos no responde: HTTP $codigo en $COLABHIVE_BASE_URL/chat/completions" >&2
  echo "  No es la tarea ni el agente. Reintentar contra una plataforma caída gasta el" >&2
  echo "  presupuesto de todas las tareas sin aprender nada." >&2
  return 1
}

# Registro de intentos: una línea por corrida, para que las métricas lean datos y no
# adivinen del texto de las tareas. Vive fuera del árbol versionado del proyecto.
anotar_intento() {
  local id="$1" ver="$2" segs="$3" modelo="${4:-}" log="${5:-}"
  local reg="$RAIZ/.metricas/intentos.csv" motivo=""
  # El motivo va al registro porque "falló" no se puede analizar y "falló por esto" sí. Es
  # la misma huella que usa el runner para decidir si reintentar: una sola fuente.
  [ -n "$log" ] && motivo="$(huella_de_falla "$log" 2>/dev/null | tr ',;"' '   ' | cut -c1-80)"
  mkdir -p "$(dirname "$reg")"
  [ -f "$reg" ] || echo "fecha,proyecto,tarea,veredicto,segundos,modelo,motivo" > "$reg"
  echo "$(date -u +%FT%TZ),${PROYECTO:-.},$id,$ver,$segs,$modelo,$motivo" >> "$reg"
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

# Corre un comando con límite de tiempo. macOS no trae `timeout`, y perl sí está siempre.
#
# Existe porque pasó: `opencode run` se quedó 31 minutos con el log en 0 bytes mientras la
# API del modelo respondía en 3 segundos. Sin límite, **un agente colgado detiene la corrida
# para siempre**, y para un método que se vende como autónomo eso es peor que un error: un
# error se reintenta, un cuelgue no se nota.
#
#   con_limite 900 opencode run --agent ejecutor "..."
#
# Sale 142 si cortó por tiempo (SIGALRM), y eso se trata como un intento fallido con motivo
# propio: es reintentable, porque la próxima vez puede andar.
# Mata el GRUPO de procesos, no sólo el líder: `opencode` arranca hijos (node, servidores
# de lenguaje) y una señal al líder los deja huérfanos corriendo. En una sesión larga eso se
# acumula y la máquina se degrada sin que nadie relacione una cosa con la otra.
con_limite() {
  local segundos="$1"; shift
  local pid guardian rc
  set -m                      # cada hijo arranca en su propio grupo de procesos
  "$@" &
  pid=$!
  set +m
  ( # Dos relojes, y el que importa es el segundo.
    #
    # El límite total ($segundos) es la red de seguridad. El que detecta de verdad es el de
    # INACTIVIDAD sobre el log: el cuelgue de opencode no es lentitud, es silencio —su
    # propio log termina en `init` y no escribe nada más—, mientras que un agente que
    # trabaja escribe todo el tiempo. Con un solo reloj total hay que elegir entre cortar
    # rápido y no cortar a quien está trabajando; con el de inactividad no hay que elegir.
    #
    # Medido: el tiempo al primer byte del modelo con un prompt real es de 0,7s y opencode
    # imprime su encabezado en ~1s, así que 45s de silencio TOTAL ya es patológico —y como
    # la salida se transmite token por token, también lo es a mitad de camino—. Con 45 en
    # vez de 90, cada cuelgue cuesta la mitad y un agente que escribe no se toca.
    local t=0 quieto=0 tam_anterior=-1 tam
    while [ "$t" -lt "$segundos" ]; do
      sleep 15; t=$((t+15))
      kill -0 "$pid" 2>/dev/null || exit 0
      if [ -n "${LOG_VIGILADO:-}" ]; then
        tam="$(wc -c < "$LOG_VIGILADO" 2>/dev/null || echo 0)"
        # Ventana más corta mientras la salida siga siendo sólo el encabezado. Todos los
        # cuelgues observados son de ARRANQUE: el proxy mostró que opencode no manda ni una
        # petición de completado —sólo el GET /models— y el log se queda entre 61 y 272
        # bytes. Como el primer token del modelo llega en 0,6s y la salida se transmite
        # token por token, un proceso con menos de 1 KB y veinte segundos sin escribir una
        # letra está colgado, no pensando. Cada cuelgue cuesta 20s en vez de 45.
        local limite_quieto="${INACTIVIDAD:-45}"
        [ "${tam:-0}" -lt "${UMBRAL_ARRANQUE:-1024}" ] && limite_quieto="${ARRANQUE:-20}"
        if [ "$tam" = "$tam_anterior" ]; then
          quieto=$((quieto+15))
          if [ "$quieto" -ge "$limite_quieto" ]; then
            # Qué reloj cortó: el mensaje de un corte tiene que decirlo, o se informa "no
            # respondió en 1200s" cuando en realidad se lo cortó a los 90 por silencio, y
            # el próximo que lo lea va a buscar un problema de lentitud que no existe.
            [ -n "${LOG_VIGILADO:-}" ] && echo "inactividad ${limite_quieto}s$([ "${tam:-0}" -lt "${UMBRAL_ARRANQUE:-1024}" ] && echo ' (sin pasar del encabezado: cuelgue de arranque)')" > "$LOG_VIGILADO.corte"
            break
          fi
        else
          quieto=0; tam_anterior="$tam"
        fi
      fi
    done
    [ -n "${LOG_VIGILADO:-}" ] && [ ! -f "$LOG_VIGILADO.corte" ] \
      && echo "límite total ${segundos}s" > "$LOG_VIGILADO.corte"
    kill -TERM -"$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    sleep 5
    kill -KILL -"$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  # El guardián NO hereda stdout: si lo hereda, su `sleep` mantiene la tubería abierta y
  # quien capture la salida espera el límite entero aunque el comando ya haya terminado.
  # Medido: tres casos de test tardaban 66s en vez de 3.
  guardian=$!
  wait "$pid"; rc=$?
  kill "$guardian" 2>/dev/null
  wait "$guardian" 2>/dev/null
  # 143 = SIGTERM, 137 = SIGKILL: los dos son "lo cortamos nosotros". Se normalizan a 142
  # para que quien lo llama tenga un solo código que mirar.
  case "$rc" in 143|137) return 142 ;; *) return "$rc" ;; esac
}

# Por qué se cortó el último `con_limite`: "inactividad 90s" o "límite total 1200s".
# Lo escribe el guardián y se consume una sola vez.
motivo_del_corte() {
  local f="${1:-${LOG_VIGILADO:-}}.corte"
  [ -f "$f" ] || { echo "cortado por tiempo"; return; }
  cat "$f"; rm -f "$f"
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
  fi
  # Y la columna Estado de la tabla del plan, que es la que lee el deductor de etapas.
  # Marcar sólo el archivo dejaba la tarea "pendiente" para el deductor: T01 de
  # clasificados se integró, quedó verde en el tronco, y la etapa 1 la volvía a lanzar.
  # Dos declaraciones de lo mismo que leen dos lectores distintos; otra vez.
  if [ -f "$BASE/PLAN.md" ] && grep -qE "^\| *$id *\|" "$BASE/PLAN.md"; then
    "${PY_METODO:-python3}" - "$BASE/PLAN.md" "$id" <<'PYFIN'
import re, sys
plan, tid = sys.argv[1], sys.argv[2]
with open(plan) as fh:
    texto = fh.read()
# Sólo la fila de la tabla de tareas (5 columnas), y sólo su última celda.
def marcar(m):
    celdas = m.group(0).rstrip("\n").strip("|").split("|")
    if len(celdas) < 5 or "✅" in celdas[-1]:
        return m.group(0)
    celdas[-1] = " ✅ hecha "
    return "|" + "|".join(celdas) + "|\n"
nuevo = re.sub(rf"^\| *{re.escape(tid)} *\|.*\|\s*$\n?", marcar, texto, count=1, flags=re.M)
if nuevo != texto:
    with open(plan, "w") as fh:
        fh.write(nuevo)
PYFIN
    git -C "$RAIZ" add "$BASE/PLAN.md" >/dev/null 2>&1
  fi
  git -C "$RAIZ" commit -q -m "$id: hecha" >/dev/null 2>&1 || true
  git -C "$RAIZ" worktree remove --force "$RAIZ/../trabajo-$id" 2>/dev/null
  git -C "$RAIZ" branch -D "$rama" >/dev/null 2>&1
}
