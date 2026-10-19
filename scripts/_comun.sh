# Funciones compartidas por correr-tarea.sh, estado.sh y comparar-modelos.sh.
# Se carga con `.`; no se ejecuta sola. Compatible con el bash 3.2 de macOS.

# Las perillas del vigilante, declaradas acá y en ningún otro lado. Estaban enterradas en
# una expansión adentro de con_limite (`${INACTIVIDAD:-45}`), que es un valor que nadie
# puede leer ni testear sin leer el cuerpo de la función: un test que quería comprobar el
# valor por omisión terminó escribiéndolo él también, y entonces no comprobaba nada.
#
#   INACTIVIDAD  segundos de silencio que se toleran. Tiene que ser MAYOR que lo que tarda
#                la herramienta vigilada en informar su propio error —medido: la plataforma
#                tarda 68,4s en decir «upstream stream ended»—, o el vigilante tapa la
#                causa del cuelgue que vino a detectar.
#   ARRANQUE     igual, mientras el log no pase de UMBRAL_ARRANQUE. Se deja como perilla,
#                pero por omisión NO es más corta: un log de 61 bytes no distingue
#                «colgado al arrancar» de «el stream ya murió y todavía no lo informaron».
: "${INACTIVIDAD:=90}"
: "${ARRANQUE:=90}"
: "${UMBRAL_ARRANQUE:=1024}"

# Ubica el proyecto: el repo git del directorio actual (no el de estos scripts), así el
# mismo runner sirve para tu proyecto y para ejemplo-pacman. Deja RAIZ, PROYECTO y BASE.
#   RAIZ      el worktree principal del repo: correr esto desde adentro de un
#             ../trabajo-TNN no lo toma como repo (lo borraría al relanzar)
#   PROYECTO  la carpeta con tareas/, relativa a RAIZ. Si no viene en el entorno, la
#             más cercana hacia arriba desde donde estás parado
#   BASE      $RAIZ/$PROYECTO
# El sujeto del experimento es el ENUNCIADO. Si cambia entre intentos, los cortes y los
# reintentos gastados contra el anterior no cuentan contra éste: son dos experimentos
# distintos conflados en un número. Pasó con T26: arreglé el contrato a mitad de la etapa y
# el presupuesto de cortes ya estaba en 2 de 2, gastado contra el enunciado roto, así que lo
# que iba a frenar la etapa era el contador y no la tarea.
#
# La huella se saca del archivo que el agente VA A LEER —el del worktree, que sale del árbol
# commiteado— y no del que yo tengo abierto: lo que cuenta es lo que recibe el lector.
huella_enunciado() {
  [ -f "$1" ] || { echo ""; return 0; }
  git hash-object "$1" 2>/dev/null || echo ""
}

# rc=0 (hay que reiniciar) sólo si había una huella anterior y es distinta. Sin huella
# anterior es el primer intento: no hay nada que reiniciar, y tratarlo como cambio haría que
# el reinicio no distinga nada.
el_enunciado_cambio() {
  [ -n "${2:-}" ] && [ -n "${1:-}" ] && [ "$1" != "$2" ]
}

ubicar_proyecto() {
  git rev-parse --show-toplevel >/dev/null 2>&1 \
    || { echo "✗ Corré esto desde adentro del repo git de tu proyecto" >&2; exit 1; }
  # RAIZ es el repo DEL PROYECTO, y es el worktree en el que estás parado: `--show-toplevel`.
  # Decía `git worktree list | head -1`, que devuelve el worktree PRINCIPAL. Correr el plan
  # desde un worktree de desarrollo leía las tareas del tronco, y lo que medías no era el
  # árbol que estabas editando. Me pasó hoy probando el cableado de coherencia.py: dije «el
  # import huérfano no se detecta» cuando sí se detectaba — había medido el otro árbol.
  #
  # No es `dirname $BASH_SOURCE`: los scripts del método se corren contra el repo del
  # proyecto, que puede no ser el repo donde viven los scripts. Eso lo probé y rompió tres
  # tests de métricas, que corren metricas.sh contra un repo temporal.
  RAIZ="$(git rev-parse --show-toplevel)"
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
  # Y se EXPORTA, para que los hijos no tengan que volver a adivinarlo.
  #
  # Estaba como variable de shell nomás, así que cada script hijo llamaba a `ubicar_proyecto`
  # de nuevo y lo re-detectaba del cwd. Normalmente sale bien, porque el cwd está adentro del
  # proyecto. Pero cuando el cwd ya no existe —justo después de borrar un worktree— la
  # detección cae en «buscá un tareas/ hacia abajo», encuentra los DOS ejemplos de este repo y
  # muere con «Hay varios proyectos». Pasó en la etapa 1 de clasificados: un error impreso que
  # no correspondía a ninguna decisión, y que podía tapar uno real.
  #
  # Es la misma forma de falla que el repo repite: una declaración que el lector no recibe.
  # Acá el que declara es el padre y el que no recibe es el hijo.
  export PROYECTO RAIZ BASE
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
    | grep -m1 -oE 'inference timed out[^"]*|database is locked|el agente no respondió[^"]*|upstream stream ended[^"]*|maximum context length is [0-9]*[^\\"]*|Failed to allocate GPU|Failed to start inference server[^\\"]*|Bad Gateway|Service Unavailable|Internal Server Error|50[0234] '
}

# ¿Responde la plataforma? Un 502 de nginx no es una falla de la tarea ni del agente, y
# reintentar contra una plataforma caída gasta el presupuesto de todas las tareas sin
# aprender nada. Pasó: la API pasó de responder en 3s a devolver 502 en TODO —incluido
# `/models`— y el método lo informaba como «el test no pasa ni con la implementación del
# propio agente», que es el diagnóstico más lejano posible de la causa.
# Qué modelo usa un agente, según la config de OpenCode. Existe porque el id del modelo
# estaba clavado en tres scripts a la vez —la sonda de acá, warm.sh y anclar.sh— y los tres
# quedaron apuntando al modelo viejo el día que los agentes cambiaron. El de la sonda fue
# el caro: consultaba un modelo que ningún agente usaba, que encima estaba frío y roto, se
# comía el timeout, y la corrida entera se negaba a arrancar diciendo «la plataforma no
# responde» con la plataforma perfectamente arriba.
modelo_del_agente() {
  local agente="${1:-ejecutor}" cfg="${CONFIG_OC:-$HOME/.config/opencode/opencode.json}"
  [ -f "$cfg" ] || return 1
  python3 - "$cfg" "$agente" <<'PYMOD' 2>/dev/null
import json, sys
cfg = json.load(open(sys.argv[1]))
m = ((cfg.get("agent") or {}).get(sys.argv[2]) or {}).get("model")
print(m.split("/")[-1] if m else "", end="")
PYMOD
}

# ¿Está DECLARADO este id en la config de OpenCode? Un modelo que no está declarado muere
# en ~2 segundos con un error genérico que parece de plataforma, y lo tomamos tres veces como
# «ese modelo no sirve». La regla que cierra el agujero vive en MEDICION.md: ninguna corrida
# de menos de 10 segundos cuenta como fallo del modelo. Esto la detecta antes de correr.
# Devuelve 0 si está, 1 si no está, 2 si no se pudo averiguar (⊘: no es un no).
modelo_declarado() {
  local id="$1" cfg="${CONFIG_OC:-$HOME/.config/opencode/opencode.json}"
  [ -f "$cfg" ] || return 2
  command -v python3 >/dev/null 2>&1 || return 2
  # El veredicto viaja por stdout, no por el código de salida de python: con `|| return 2`
  # el `sys.exit(1)` de «no está declarado» era indistinguible de un python que se cayó, y
  # el chequeo contestaba ⊘ —«no pude averiguar»— para el único caso que vino a detectar.
  # Un ⊘ tapando un «no» es el mismo defecto que este chequeo existe para evitar.
  local r
  r="$(python3 - "$cfg" "$id" <<'PYDEC' 2>/dev/null
import json, sys
try:
    cfg = json.load(open(sys.argv[1]))
except Exception:
    print("⊘"); sys.exit(0)
buscado = sys.argv[2].split("/")[-1]
for prov in (cfg.get("provider") or {}).values():
    if buscado in (prov.get("models") or {}):
        print("si"); sys.exit(0)
print("no")
PYDEC
)"
  case "$r" in si) return 0 ;; no) return 1 ;; *) return 2 ;; esac
}

plataforma_responde() {
  [ -n "${COLABHIVE_BASE_URL:-}" ] || return 0      # sin configurar, no opinamos
  local codigo modelo
  modelo="${MODELO_SONDA:-$(modelo_del_agente ejecutor)}"
  if [ -z "$modelo" ]; then
    echo "  ⊘ no pude saber qué modelo usa el ejecutor: la sonda de plataforma no corre" >&2
    return 0   # no sabemos: no es excusa para frenar, pero queda dicho
  fi
  # Antes de preguntarle a la plataforma, preguntarle a nuestra config. Si el id no está
  # declarado, el 2 segundos que viene después NO es un dato sobre el modelo: es un defecto
  # nuestro, y hay que decirlo con ese nombre.
  modelo_declarado "$modelo"
  case $? in
    1) echo "✗ el modelo «${modelo}» no está declarado en provider.*.models de ${CONFIG_OC:-$HOME/.config/opencode/opencode.json}" >&2
       echo "  Es un defecto de configuración, no del modelo: sin declarar, el pedido muere en" >&2
       echo "  ~2 segundos con un error genérico que parece de plataforma." >&2
       return 1 ;;
    2) echo "  ⊘ no pude leer la config de OpenCode: no verifico si «${modelo}» está declarado" >&2 ;;
  esac
  # Contra `/chat/completions` CON herramientas, no contra `/models`. Listar modelos pasa
  # por otro camino: lo vimos devolver 200 mientras las peticiones reales de un agente
  # —20 KB de prompt y definiciones de herramientas— devolvían 502. Un chequeo que pasa
  # mientras el camino que importa falla es un falso verde, y éste iba a dejar arrancar una
  # corrida de nueve etapas contra una plataforma que no podía atenderla.
  codigo="$(curl -s -m 45 -o /dev/null -w '%{http_code}' \
            "$COLABHIVE_BASE_URL/chat/completions" \
            -H "Authorization: Bearer ${COLABHIVE_API_KEY:-}" \
            -H "Content-Type: application/json" \
            -d '{"model":"'$modelo'",
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

# Conserva lo que se puede aprender de un intento ANTES de destruir su worktree.
#
# Guardaba sólo el transcript, en tres de los cinco lugares que destruyen worktrees. Lo que
# faltaba es el CÓDIGO: `recordar_falla` sólo escribe un registro cuando el veredicto es
# VERDE, así que de un intento que el gate reprobó el método no guardaba nada ejecutable —
# y el parche de un intento rechazado es exactamente el material que necesita la condición
# central del experimento de memoria (ver experimentos/memoria-verificada.md §2).
#
# Los 16 rechazados que tenemos hoy son un rescate accidental de worktrees de experimento
# que estaban por borrarse. Sin esto, cada corrida sigue destruyendo material.
#
#   conservar_intento <worktree> <id>
conservar_intento() {
  local wt="$1" id="${2:-tarea}" dest log
  [ -d "$wt" ] || return 0
  dest="$RAIZ/../fallidos-$id"
  # El log se llama distinto según el camino: .tarea.log en el runner, .tests.log al
  # escribir tests, .log en los arneses de experimento.
  for log in "$wt/.tarea.log" "$wt/.tests.log" "$wt/.log"; do
    [ -f "$log" ] || continue
    mkdir -p "$dest"
    cp "$log" "$dest/intento-$(date +%H%M%S).log" 2>/dev/null
    break
  done
  # El parche: lo que el agente escribió, aplicable con `git apply`. Sin los archivos de
  # infraestructura que prepara el método, que no son trabajo del agente.
  local infra='\.opencode-data|\.tarea\.log|\.tests\.log|\.log|\.corte|\.base-ref|\.tests-base|\.venv|_env/|\.entorno|node_modules|package-lock\.json|__pycache__|\.oc/'
  local sucios
  sucios="$( { git -C "$wt" diff --name-only HEAD 2>/dev/null; \
               git -C "$wt" ls-files --others --exclude-standard 2>/dev/null; } \
             | grep -vE "$infra" | sort -u | grep . || true)"
  if [ -n "$sucios" ]; then
    mkdir -p "$dest"
    { git -C "$wt" diff HEAD -- $sucios 2>/dev/null
      # Los archivos nuevos no salen en `diff HEAD`: van con /dev/null como origen.
      for f in $sucios; do
        git -C "$wt" ls-files --error-unmatch "$f" >/dev/null 2>&1 && continue
        [ -f "$wt/$f" ] || continue
        git -C "$wt" diff --no-index -- /dev/null "$f" 2>/dev/null
      done
    } > "$dest/parche-$(date +%H%M%S).diff"
    echo "     (intento conservado en $dest: transcript y parche de $(echo "$sucios" | grep -c .) archivo/s)"
  fi
}

# ¿Se movió el brazo de control respecto de su línea base?
#
#   control_se_movio <clave> <herramientas_ahora> <veredicto_ahora>
#     0 = no se movió, la tanda es válida
#     1 = se movió: se movió el arnés, la tanda se descarta ENTERA
#     2 = primera corrida: queda como línea base, el criterio aplica desde la segunda
#
# Está acá y no dentro del comparador por el mismo motivo que la regla de mayoría del banco:
# **una regla que decide el resultado tiene que poder ejercitarse sin correr la campaña.**
#
# El criterio es CONTINUO y sobre lo que tiene varianza baja (llamadas a herramientas), no un
# conteo binomial de gate sobre doce ítems. La banda de ±2 ítems que proponía el diseño estaba
# calculada con p=0,83, que es la tasa de tool-call; la tasa de VERDE del control, medida, es
# 0,42 por corrida, y con ésa ±2 descarta el 29% de los bloques buenos. Un conteo de 12 con
# banda ±5 ya no controla nada: ésa es la señal de que no puede ser el control.
control_se_movio() {
  local clave="$1" tools="$2" gate="${3:-?}" base prev t_prev g_prev movio=""
  base="$RAIZ/.metricas/control-base.csv"
  mkdir -p "$(dirname "$base")"
  prev="$(grep -F "$clave|" "$base" 2>/dev/null | tail -1)"
  if [ -z "$prev" ]; then
    echo "$clave|$tools|$gate|$(date -u +%FT%TZ)" >> "$base"
    return 2
  fi
  t_prev="$(echo "$prev" | cut -d'|' -f3)"; g_prev="$(echo "$prev" | cut -d'|' -f4)"
  # Herramientas a la mitad o menos: dejó de actuar. Es el modo de falla medido — el modelo de
  # un partner daba 0 de 6 llamadas por un defecto del arnés, no del modelo.
  case "$t_prev" in ''|*[!0-9]*) t_prev=0 ;; esac
  case "$tools" in ''|*[!0-9]*) tools=0 ;; esac
  [ "$t_prev" -gt 0 ] && [ "$((tools * 2))" -lt "$t_prev" ] \
    && movio="las llamadas a herramientas cayeron de $t_prev a $tools"
  [ "$g_prev" != "?" ] && [ "$gate" != "?" ] && [ "$gate" != "$g_prev" ] \
    && movio="${movio:+$movio; }el veredicto del control pasó de $g_prev a $gate"
  if [ -n "$movio" ]; then echo "$movio"; return 1; fi
  echo "$clave|$tools|$gate|$(date -u +%FT%TZ)" >> "$base"
  return 0
}

# Registro de intentos: una línea por corrida, para que las métricas lean datos y no
# adivinen del texto de las tareas. Vive fuera del árbol versionado del proyecto.
anotar_intento() {
  local id="$1" ver="$2" segs="$3" modelo="${4:-}" log="${5:-}"
  local reg="$RAIZ/.metricas/intentos.csv" motivo=""
  # El motivo va al registro porque "falló" no se puede analizar y "falló por esto" sí. Es
  # la misma huella que usa el runner para decidir si reintentar: una sola fuente.
  # `tr` también sobre saltos de línea y retornos: la huella devolvía varias líneas y cada
  # salto partía la fila en dos, dejando filas huérfanas de un campo. Sanear acá además de
  # arreglar la huella es a propósito: el registro no puede depender de que quien lo
  # alimenta se porte bien.
  [ -n "$log" ] && motivo="$(huella_de_falla "$log" 2>/dev/null | tr ',;"\n\r' '     ' | cut -c1-80)"
  mkdir -p "$(dirname "$reg")"
  # `concurrencia`: corridas de agente vivas al arrancar ésta. Va como COLUMNA y no como nota
  # al pie porque es lo que decide si la fila sirve para medir tiempo: el mismo modelo pasa de
  # 16,3 a 122 tok/s según la ocupación, y `correr-tarea.sh` corre con PARALELAS=8 por omisión.
  # Toda fila con concurrencia > 1 queda fuera del análisis de tiempo POR CONSTRUCCIÓN, no por
  # criterio de quien analiza.
  # Sin `|| echo 1`: `grep -c .` imprime «0» Y sale distinto de cero cuando no hay nada, así
  # que el `||` agregaba otra línea y la variable quedaba con DOS valores («0\n1»). Es el
  # mismo defecto que dejaba el mensaje «HTTP 000000» en la sonda de plataforma. `wc -l` no
  # falla, así que no hace falta el respaldo.
  local concurrencia
  concurrencia="$(pgrep -f "opencode run" 2>/dev/null | wc -l | tr -d ' ')"
  [ -n "$concurrencia" ] || concurrencia=0
  # `instrumento`: la huella de los scripts que produjeron la fila. Dos filas con huellas
  # distintas no se comparan — es el punto 7 de la regla de parada de MEDICION.md, que decía
  # «cambiaste el instrumento entre dos corridas: no son comparables» y no tenía cómo saberlo.
  local instrumento
  instrumento="$(git -C "$RAIZ" rev-parse --short HEAD:scripts 2>/dev/null || echo "?")"
  local ENCABEZADO="fecha,proyecto,tarea,veredicto,segundos,modelo,motivo,concurrencia,instrumento"
  if [ ! -f "$reg" ]; then
    echo "$ENCABEZADO" > "$reg"
  elif [ "$(head -1 "$reg")" != "$ENCABEZADO" ]; then
    # El encabezado se escribía SÓLO si el archivo no existía, así que agregar la columna
    # `motivo` dejó un registro con 6 nombres y filas de 7 campos. `csv.DictReader` manda el
    # séptimo a la clave None y `metricas.sh` leía `motivo` vacío SIEMPRE: el bloque «motivos
    # de rojo que se repiten» nunca imprimió nada, con datos de sobra para imprimirlo.
    # Una columna que nadie puede leer no existe, y el que la escribe no se enteró nunca.
    # Reescribir SÓLO el encabezado dejaba las filas viejas con menos campos que los nombres,
    # y `csv.DictReader` manda los que sobran a la clave None o deja los que faltan en None:
    # las dos formas de una columna ilegible. Así que se rellenan las filas al ancho nuevo.
    local n_cols
    n_cols="$(echo "$ENCABEZADO" | tr ',' '\n' | grep -c .)"
    python3 - "$reg" "$ENCABEZADO" "$n_cols" <<'PYMIG'
import sys
ruta, encabezado, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
lineas = open(ruta).read().rstrip("\n").split("\n")
salida = [encabezado]
for l in lineas[1:]:
    if not l:
        continue
    campos = l.split(",")
    if len(campos) == 1:          # continuación huérfana de un campo con salto de línea
        salida[-1] += " " + l
        continue
    campos += [""] * (n - len(campos))
    salida.append(",".join(campos[:n]))
open(ruta, "w").write("\n".join(salida) + "\n")
PYMIG
    echo "  (registro migrado a $n_cols columnas: el encabezado no nombraba todas las escritas)" >&2
  fi
  echo "$(date -u +%FT%TZ),${PROYECTO:-.},$id,$ver,$segs,$modelo,$motivo,$concurrencia,$instrumento" >> "$reg"
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
  # El primer rojo CON su detalle. El gate imprime la categoría en la línea del ✗ y el dato
  # —qué archivo, qué test, qué import— en las líneas sangradas que siguen. Quedarse con la
  # primera línea daba motivos como «✗ tocó archivos intocables (tests o el propio gate):»,
  # con los dos puntos y nada detrás: el reintento no sabía QUÉ había tocado y repetía.
  # Pasó con T08 y terminó en punto muerto por eso.
  #
  # Y además la huella sirve para decidir si hay punto muerto: sin el dato, tocar dos
  # archivos distintos daba la misma huella y el método lo leía como la misma falla.
  #
  # `escribir-tests.sh` ya tenía esta lección escrita; este camino no la había aprendido.
  awk '{ l[NR] = $0; if ($0 == "=== gate ===") g = NR }
       END { for (i = g + 1; i <= NR; i++) print l[i] }' "$log" \
    | awk '/✗/ && !vi { vi = 1; print; next }
           vi && /^ +[^ ]/ && !/^ *[✗✓⊘·]/ && n < 3 { print; n++; next }
           vi { exit }' \
    | sed -E 's/^ +//' \
    | sed -E 's/(^|[^A-Za-z0-9])[0-9]{2,}/\1N/g' \
    | tr '\n' ' ' | sed 's/  */ /g; s/ *$//' | cut -c1-220
  # Los números sueltos se normalizan para que dos fallas iguales con contadores distintos
  # den la misma huella; «T06c» NO, porque el 06 va pegado a una letra y mutilarlo deja
  # mensajes como «los tests de TNc siguen fallando».
  #
  # El comentario va ACÁ, después del pipe, y no al final de la línea del `sed`. Estaba
  # pegado con `# …` al final de una línea y seguía en las dos siguientes, así que el
  # `| tr '\n' ' ' | cut -c1-220` del final quedó DENTRO del comentario: nunca corrió. La
  # huella devolvía hasta 4 líneas, `anotar_intento` las metía sin comillas en el CSV, y el
  # registro quedó con filas huérfanas de un solo campo. Un comentario que se come el código
  # no se ve leyendo: se ve corriendo la función y contando las líneas.
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
  ( # Dos relojes. El total ($segundos) es la red de seguridad; el de INACTIVIDAD sobre el
    # log es el que detecta, porque un agente que trabaja escribe y uno trabado no.
    #
    # LO QUE COSTÓ UN DÍA ENTERO. Acá decía 45s de silencio, y 20s mientras el log no
    # pasara del encabezado, con el argumento de que «un proceso con menos de 1 KB y veinte
    # segundos sin escribir una letra está colgado, no pensando».
    #
    # Falso, y la medición lo dio vuelta: sin vigilante, lo que pasa de verdad es que la
    # plataforma corta el stream a mitad de la generación y tarda **68,4 segundos** (tres
    # corridas, idéntico) en informarlo con `upstream stream ended without a complete EOS
    # handshake`. Durante todo ese rato el log sigue en 61 bytes —el encabezado—, o sea que
    # las DOS ventanas mataban el proceso antes del diagnóstico: la de arranque por 48
    # segundos, la larga por 23. Ese error no aparece ni una sola vez en ningún log del día.
    #
    # El «cuelgue de arranque» que esas ventanas creían detectar ERA este error, tapado por
    # ellas. Por eso ahora hay una sola ventana y es más larga que el informe de la
    # herramienta: **un vigilante tiene que perder siempre la carrera contra el error que
    # la herramienta vigilada sabe imprimir**. Si corta antes, no observa el sistema: lo
    # fabrica, y deja un cuelgue sin causa que nadie puede diagnosticar.
    #
    # El costo de aflojar es real —cada cuelgue verdadero cuesta 90s en vez de 45— y es
    # barato al lado de un día de diagnóstico contra evidencia que uno mismo borró.
    local t=0 quieto=0 tam_anterior=-1 tam conex=0
    while [ "$t" -lt "$segundos" ]; do
      sleep 15; t=$((t+15))
      kill -0 "$pid" 2>/dev/null || exit 0
      if [ -n "${LOG_VIGILADO:-}" ]; then
        tam="$(wc -c < "$LOG_VIGILADO" 2>/dev/null || echo 0)"
        local limite_quieto="$INACTIVIDAD"
        # La ventana de arranque existe sólo como perilla; por omisión es la misma, porque
        # un log corto no distingue «colgado al arrancar» de «la plataforma todavía no
        # contó que cortó el stream»: medido, en ese caso el log queda en 61 bytes.
        [ "${tam:-0}" -lt "$UMBRAL_ARRANQUE" ] && limite_quieto="$ARRANQUE"
        if [ "$tam" = "$tam_anterior" ]; then
          quieto=$((quieto+15))
          if [ "$quieto" -ge "$limite_quieto" ]; then
            # Callado no es lo mismo que colgado. Antes de matar, se mira si el grupo
            # todavía tiene una conexión abierta: si la tiene, está esperando al modelo
            # —generar un archivo largo son minutos sin imprimir una letra— y se reinicia
            # el reloj del silencio. El límite total sigue siendo el techo, así que esto
            # no puede esperar para siempre.
            conex="$(conexiones_del_grupo "$pid")"
            if [ "$conex" != "SIN_LSOF" ] && [ "${conex:-0}" -gt 0 ]; then
              quieto=0
              continue
            fi
            # Qué reloj cortó: el mensaje de un corte tiene que decirlo, o se informa "no
            # respondió en 1200s" cuando en realidad se lo cortó a los 90 por silencio, y
            # el próximo que lo lea va a buscar un problema de lentitud que no existe.
            [ -n "${LOG_VIGILADO:-}" ] && echo "inactividad ${limite_quieto}s y $([ "$conex" = "SIN_LSOF" ] && echo 'sin poder mirar si había conexión abierta (⊘)' || echo 'sin ninguna conexión abierta') — lo cortamos nosotros: si la herramienta tenía un error que no llegó a imprimir, no lo vamos a ver$([ "${tam:-0}" -lt "$UMBRAL_ARRANQUE" ] && echo ' · el log no pasó del encabezado')" > "$LOG_VIGILADO.corte"
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

# ¿El grupo de procesos tiene alguna conexión TCP abierta? Es la señal de vida que el
# silencio no da: medido, un `opencode` colgado tiene CERO conexiones y el hilo principal
# parado en `kevent64`, mientras uno que trabaja mantiene dos abiertas de punta a punta
# —muestreado cada 5s durante cuatro minutos, a través de silencios de hasta 40s—.
#
# Imprime el número, o SIN_LSOF si no se pudo mirar. Esa distinción importa: un chequeo
# que no pudo correr no dice «está vivo». Si lo dijera, en una máquina sin `lsof` un
# cuelgue no se cortaría nunca, que es peor que el problema que vino a resolver.
#
# Lo que NO cubre, y conviene saberlo: opencode mantiene la conexión viva entre peticiones,
# así que un cuelgue POSTERIOR a conectarse no baja el contador. Para ésos quedan el
# límite total y `error_del_agente`.
conexiones_del_grupo() {
  local lsof_bin="${LSOF:-lsof}"
  command -v "$lsof_bin" >/dev/null 2>&1 || { echo "SIN_LSOF"; return; }
  "$lsof_bin" -nP -g "$1" 2>/dev/null | grep -c ESTABLISHED
}

# Por qué se cortó el último `con_limite`: "inactividad 90s" o "límite total 1200s".
# Lo escribe el guardián y se consume una sola vez.
motivo_del_corte() {
  local f="${1:-${LOG_VIGILADO:-}}.corte"
  [ -f "$f" ] || { echo "cortado por tiempo"; return; }
  cat "$f"; rm -f "$f"
}

# ── MEMORIA DEL MÉTODO ───────────────────────────────────────────────────────────────
# Medido sobre nuestras propias fallas, cuatro modelos, diseño A/B/C:
#     A sin memoria        6/24  (25%)
#     B memoria correcta  18/24  (75%)
#     C memoria de OTRA    6/24  (25%)   ← mismo largo de prompt, compra CERO
# C ≡ A dice que lo que sube es el CONTENIDO, no el texto. Y el dato que cambia la economía
# del método: CodeScout-1.7B pasa de 1/6 a 5/6 con memoria correcta y supera al 30B sin
# memoria. Veníamos eligiendo entre modelos que se mueven de 2 a 3 sobre 6.
#
# La memoria que funciona es la VERIFICADA: la que lleva el veredicto de un comando que
# puede reprobar. El método la produce en cada corrida y la tiraba al log.

# Anota una falla con su arreglo, cuando la tarea pasa a verde después de haber fallado.
# El registro es el trío que el método ya tiene: qué se pidió, qué falló, qué lo arregló.
recordar_falla() {
  local id="$1" motivo="$2" arreglo="$3"
  [ -n "$motivo" ] || return 0
  local dir="$BASE/memoria"; mkdir -p "$dir"
  local f="$dir/${id}.md"
  # Una tarea puede fallar varias veces; cada registro es una entrada, no un reemplazo.
  {
    echo "## $(date -u '+%Y-%m-%d %H:%M UTC') · $id"
    echo
    echo "**Falló así:** $motivo"
    echo
    echo "**Quedó en verde al:** $arreglo"
    echo
  } >> "$f"
  echo "  · registrado en memoria/${id}.md"
}

# Los registros que le sirven a una tarea: los de las tareas que tocaron ALGUNO de sus
# archivos. No todos —un prompt lleno de memoria ajena es el caso C, que compra cero— ni
# sólo los propios, porque la falla suele estar en el archivo compartido.
memoria_para() {
  local id="$1" archivo dir="$BASE/memoria"
  [ -d "$dir" ] || return 0
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  [ -n "$archivo" ] || return 0
  local mios otros_id otros_arch
  mios="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "$archivo" | tr ',' '\n' | sed 's/^ *//; s/ *$//' | grep . || true)"
  [ -n "$mios" ] || return 0
  for f in "$dir"/*.md; do
    [ -f "$f" ] || continue
    otros_id="$(basename "$f" .md)"
    [ "$otros_id" = "$id" ] && { cat "$f"; continue; }
    otros_arch="$(ls "$BASE/tareas/${otros_id}"-*.md 2>/dev/null | head -1)"
    # Un registro cuya tarea ya no existe NO se puede emparejar por archivos, y antes se
    # descartaba callado. Pasa de verdad: T06 se partió en T06a/T06b/T06c y su archivo se
    # borró, así que un `memoria/T06.md` quedaría inalcanzable para siempre sin que nadie se
    # entere. Es la clase de falla de PRUEBAS.md —dejar de mirar en vez de fallar— y acá la
    # consecuencia es una memoria que existe y no llega. Se salta igual (entregar memoria
    # ajena compra cero y gasta contexto: C ≡ A), pero lo dice.
    if [ -z "$otros_arch" ]; then
      # El prefijo `_` es la convención para un registro que NO es de una tarea: lo lee el
      # replanificador (MEM_PLAN en replanificar.sh), no el ejecutor. Ése se salta callado.
      case "$otros_id" in _*) continue ;; esac
      echo "  ⊘ memoria/$otros_id.md: no hay tareas/${otros_id}-*.md, no puedo saber si aplica" >&2
      continue
    fi
    # ¿Comparten algún archivo? Entonces su falla puede repetirse acá.
    if sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "$otros_arch" 2>/dev/null \
       | tr ',' '\n' | sed 's/^ *//; s/ *$//' | grep -qxF -f <(printf '%s\n' "$mios") 2>/dev/null; then
      cat "$f"
    fi
  done
}

# Cierra una tarea integrada: la marca hecha en su archivo (es lo que lee estado.sh),
# saca el worktree y borra la rama. Sin esto la tarea figura "verde" para siempre y nadie
# se entera de que está mergeada — o peor, de que no lo está.
# NO llama a conservar_intento, y es correcto: esto corre cuando la tarea YA cerró verde y
# está integrada, así que su código vive en un commit. Lo que hay que conservar es el intento
# que el gate RECHAZÓ, y de eso se ocupan los otros cuatro sitios.
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
  # conservar_intento: no-aplica — la tarea cerró verde y su código ya está commiteado.
  git -C "$RAIZ" worktree remove --force "$RAIZ/../trabajo-$id" 2>/dev/null
  git -C "$RAIZ" branch -D "$rama" >/dev/null 2>&1
}
