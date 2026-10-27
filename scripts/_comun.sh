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
# ARRANQUE_FRIO: cuánto se le concede a un modelo DESALOJADO para levantarse. Medido el
# 2026-10-20 con `oc --warm`: 91, 97 y 106 s según el modelo, y un POST de sonda contra el
# ejecutor desalojado contestó 200 a los 41,5 s después de que pedidos anteriores lo
# arrancaran. El número vive acá y lo usan los dos que lo necesitan —la sonda de plataforma y
# el presupuesto del calentador—, porque tenerlo dos veces es tenerlo mal una vez.
: "${ARRANQUE_FRIO:=240}"

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

# La raíz del MÉTODO, deducida de dónde vive este archivo. Hasta ahora `$AGENTES` aparecía
# 31 veces en los mensajes del método y no existía como variable en ninguna parte: una ruta
# que el método le pedía al humano tener en la cabeza. Es la misma forma que este repo viene
# encontrando —una regla que vive sólo en un documento— aplicada a su propia ubicación.
#
# Se exporta para que los hijos la reciban, incluido el gate del proyecto, que necesita
# encontrar los chequeos que el método provee y que estaban copiados en cada proyecto.
AGENTES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
export AGENTES

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
  # Sin los colores, y UNA sola vez para los tres chequeos. El log guarda la salida de
  # opencode con escapes ANSI: la línea real es `\e[91m\e[1mError: \e[0m{"message":…}`, así
  # que `^Error:` no ancla nunca. Lo descubrí verificando contra una copia del log que yo
  # mismo había limpiado para poder leerla — el camino que no ejercita el defecto.
  local limpio
  limpio="$(parte_del_agente "$1" | sed "s/$(printf '\033')\[[0-9;]*m//g")"

  # El SOBRE, no el texto. La plataforma devuelve siempre
  # `Error: {"message":"…","type":"api_error"}`, y esta función enumeraba MENSAJES: reconocía
  # «Failed to start inference server» y «upstream stream ended» porque están en la lista de
  # abajo, y dejaba pasar `memory_delivery_unavailable`, que el 2026-10-19 mató T11 y T20 en
  # la misma etapa. Los dos intentos quedaron anotados como «no hay ningún cambio: la tarea
  # no se hizo», o sea contra el modelo.
  #
  # Una lista de mensajes envejece con cada error nuevo de la plataforma, y lo que envejece
  # CALLA: el error nuevo no se parece a un error, se parece a un modelo que no pudo. El
  # sobre es el contrato del endpoint y no cambia. La enumeración queda para los que llegan
  # sin sobre.
  local sobre
  sobre="$(printf '%s\n' "$limpio" \
           | sed -n 's/^Error: {"message":"\(.*\)","type":"api_error"}.*/\1/p' | head -1)"
  if [ -n "$sobre" ]; then
    printf '%s\n' "$sobre" | cut -c1-200
    return 0
  fi

  # Una llamada a herramienta emitida como TEXTO. El modelo escribe `<tool_call>` en el
  # contenido en vez de pedirla por el canal de herramientas: nadie la ejecuta, el modelo no
  # recibe resultado y la corrida muere sin tocar un archivo. El gate entonces dice «no hay
  # ningún cambio: la tarea no se hizo», que es cierto y **no se parece a su causa** — es un
  # fallo de PROTOCOLO entre el modelo y el harness, no del enunciado ni del tamaño.
  #
  # Pasó con T26 el 2026-10-19 y el ejecutor `f5d76140`, después de que el mismo modelo
  # escribiera bien el test de esa misma tarea. Va acá adentro y no en un chequeo aparte
  # para que lo hereden los tres que ya leen esta función: la huella del reintento, el
  # veredicto del runner y la columna de `comparar-modelos.sh`. El tercero es el que
  # importa: sin esto, una falla de protocolo se cuenta como falla de LA TAREA y corrompe la
  # comparación entre modelos — un inválido contado como reprobado.
  #
  # Anclado a principio de línea: con una coincidencia en cualquier lugar del texto, un
  # agente que MENCIONE `<tool_call>` quedaría marcado como error, y un detector que marca a
  # todos no distingue a ninguno.
  if printf '%s\n' "$limpio" | grep -qE '^[[:space:]]*<(tool_call>|function[/ ])'; then
    echo "el modelo emitió una llamada a herramienta como TEXTO (<tool_call>): fallo de protocolo, no de la tarea"
    return 0
  fi

  printf '%s\n' "$limpio" \
    | grep -m1 -oE 'inference timed out[^"]*|database is locked|el agente no respondió[^"]*|upstream stream ended[^"]*|maximum context length is [0-9]*[^\"]*|Failed to allocate GPU|Failed to start inference server[^\"]*|Bad Gateway|Service Unavailable|Internal Server Error|50[0234] '
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
# El entorno de la plataforma, en UN solo lado y sin pisar a quien llama.
#
#   cargar_entorno_colabhive
#
# Siete scripts tenían `[ -f ~/.config/colabhive/env ] && . ~/.config/colabhive/env` copiado,
# y corría DESPUÉS de recibir el entorno, así que pisaba el `COLABHIVE_BASE_URL` que le pasó
# quien los llama. Ninguno de los siete se podía apuntar a otra plataforma —ni medir—, y lo
# intestable es lo que se rompe sin que nadie se entere: el canal sin memoria estuvo meses
# sin un test por esto, y su primer test le pegó a la plataforma REAL con un id de juguete y
# recibió un 404.
#
# Lo que ya viene seteado GANA; el archivo sólo rellena lo que falte. Y vive acá porque es una
# regla con siete lectores, y una regla copiada en siete lados es una regla que va a divergir
# —la forma que este repo repite, y que hoy ya costó tres defectos—.
cargar_entorno_colabhive() {
  [ -f "$HOME/.config/colabhive/env" ] || return 0
  local url="${COLABHIVE_BASE_URL:-}" clave="${COLABHIVE_API_KEY:-}"
  . "$HOME/.config/colabhive/env"
  [ -n "$url" ] && COLABHIVE_BASE_URL="$url"
  [ -n "$clave" ] && COLABHIVE_API_KEY="$clave"
  export COLABHIVE_BASE_URL COLABHIVE_API_KEY
  # `return 0` explícito. Hoy no hace falta —el `export` de arriba ya devuelve 0— y lo mido
  # así: quitándolo, los tests siguen verdes. Queda como red para el día en que alguien
  # agregue un `[ -n ... ] &&` al final, porque entonces la función devolvería 1 por no haber
  # tenido nada que rellenar, y un cargador de entorno que informa falla por haber hecho su
  # trabajo rompe a todo el que lo llame con `&&`.
  #
  # Lo escribo así porque la primera versión de este comentario decía que sin el `return` la
  # función YA devolvía 1, y era falso: el `export` está en medio. Un comentario que afirma un
  # mecanismo que no ocurre es la misma clase de problema que un chequeo que no mide.
  return 0
}

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

# ¿El cuerpo que contestó la plataforma ES una respuesta de chat, o sólo un 200?
#
# Defecto 19, abierto desde el 2026-10-20: la sonda miraba el CÓDIGO y nada más. El método ya
# movió esta sonda una vez por lo mismo —`/models` devolvía 200 mientras los pedidos reales
# daban 502— y el agujero se reprodujo un nivel más adentro: un 200 cuyo cuerpo es
# `{"error": "model not loaded"}` contaba como plataforma sana.
cuerpo_es_respuesta() {
  command -v python3 >/dev/null 2>&1 || return 0   # sin python3 no opinamos
  python3 -I - "$1" <<'PYCUERPO' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    m = d["choices"][0]["message"]
    sys.exit(0 if isinstance(m, dict) and ("content" in m or "tool_calls" in m) else 1)
except Exception:
    sys.exit(1)
PYCUERPO
}

# El pedido de TAMAÑO REAL: 20 KB de prompt con definiciones de herramientas, que es la forma
# que tiene un pedido de agente. Se construye con python3 y no con un heredoc de bash porque
# el JSON armado a mano en esta función ya nos costó un «HTTP 000000».
payload_de_tamano_real() {
  MODELO_SONDA_PL="$1" python3 -I - "$2" <<'PYPAYLOAD' 2>/dev/null
import json, os, sys
relleno = ("Contexto de una tarea del metodo, con su plan y su diff. " * 400)[:20000]
herramientas = [
    {"type": "function", "function": {
        "name": n, "description": f"sonda {n}",
        "parameters": {"type": "object",
                       "properties": {"p": {"type": "string"}, "q": {"type": "string"}},
                       "required": ["p"]}}}
    for n in ("read", "write", "edit", "bash", "grep", "glob")
]
json.dump({"model": os.environ["MODELO_SONDA_PL"], "max_tokens": 4,
           "messages": [{"role": "user", "content": relleno}],
           "tools": herramientas}, open(sys.argv[1], "w"))
PYPAYLOAD
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
  # La paciencia es ARRANQUE_FRIO y no 45 s. Con 45, la sonda no sobrevive al arranque de un
  # modelo desalojado —medido: 91 a 106 s— así que devolvía «HTTP 000» y el runner abortaba
  # el plan entero con «la plataforma de modelos no responde», que es falso: la plataforma
  # contestaba 200 a otros modelos en 13 s. Nos bloqueó tres lanzamientos el 2026-10-20 y me
  # llevó a culpar primero al `nohup` y después al segundo plano, las dos veces mal.
  #
  # Es la misma regla que el vigilante de inactividad: **un vigilante tiene que perder la
  # carrera contra el error que la herramienta vigilada sabe informar.** Si corta antes, no
  # observa el sistema, lo fabrica. Y de paso la sonda CALIENTA: el POST es lo que arranca la
  # réplica, así que esperarla es más útil que no esperarla.
  # TRES muestras, no una. La plataforma es intermitente —está anotado y medido— y una
  # muestra puntual de un servicio intermitente no alcanza para declararlo caído: el
  # 2026-10-21 un 502 abortó un plan de 7 etapas y dos minutos después el mismo pedido, con
  # y sin herramientas, contestaba 200. El costo de reintentar son segundos; el de un aborto
  # falso es un lanzamiento entero y un diagnóstico que apunta a la plataforma.
  #
  # No tapa una caída real: si las tres fallan, el veredicto es el mismo que antes, y la
  # SECUENCIA de códigos se informa siempre. «502 200» y «502 502 502» dicen cosas
  # distintas, y el que decide necesita esa diferencia.
  local intentos=3 i=1 codigos="" cuerpo_tmp pl_tmp codigo_grande
  cuerpo_tmp="$(mktemp)"
  while [ "$i" -le "$intentos" ]; do
    codigo="$(curl -s -m "$ARRANQUE_FRIO" -o "$cuerpo_tmp" -w '%{http_code}' \
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
    codigos="${codigos:+$codigos }$codigo"
    if [ "$codigo" = "200" ]; then
      if ! cuerpo_es_respuesta "$cuerpo_tmp"; then
        echo "✗ la plataforma contestó 200 pero el CUERPO no es una respuesta de chat" >&2
        echo "  (sin choices[0].message). «Contestó» y «contestó algo que sirve» no son lo" >&2
        echo "  mismo: el modelo puede estar sin cargar detrás de un 200." >&2
        head -c 200 "$cuerpo_tmp" | sed 's/^/     /' >&2
        rm -f "$cuerpo_tmp"
        return 1
      fi
      [ "$i" -gt 1 ] && echo "  ⚠ la plataforma contestó al intento $i de $intentos (códigos: $codigos): está intermitente, los tiempos de esta corrida no son comparables" >&2
      # ── Y ahora el pedido que se parece al que hace una corrida. Un 200 de 4 tokens no
      # autoriza nada: el incidente que mudó esta sonda a /chat/completions fue justamente
      # que 20 KB con herramientas devolvían 502 mientras lo chico pasaba.
      pl_tmp="$(mktemp)"
      if payload_de_tamano_real "$modelo" "$pl_tmp"; then
        codigo_grande="$(curl -s -m "$ARRANQUE_FRIO" -o "$cuerpo_tmp" -w '%{http_code}' \
                        "$COLABHIVE_BASE_URL/chat/completions" \
                        -H "Authorization: Bearer ${COLABHIVE_API_KEY:-}" \
                        -H "Content-Type: application/json" \
                        -d @"$pl_tmp" 2>/dev/null)"
        codigo_grande="${codigo_grande:-000}"
        if [ "$codigo_grande" != "200" ] || ! cuerpo_es_respuesta "$cuerpo_tmp"; then
          echo "✗ la plataforma atiende pedidos chicos (HTTP $codigos) y NO uno de tamaño" >&2
          echo "  real: 20 KB de prompt con 6 herramientas → HTTP $codigo_grande. Eso es la" >&2
          echo "  forma que tiene cada pedido de una corrida, así que esto no autoriza una." >&2
          rm -f "$cuerpo_tmp" "$pl_tmp"
          return 1
        fi
        echo "  · verificado: 200 con choices[0].message en el pedido chico y en uno de" >&2
        echo "    20 KB con 6 herramientas, que es la forma de un pedido de agente" >&2
      else
        echo "  ⊘ no pude armar el pedido de tamaño real: verifiqué sólo el chico" >&2
      fi
      rm -f "$cuerpo_tmp" "$pl_tmp"
      return 0
    fi
    i=$((i+1))
  done
  rm -f "$cuerpo_tmp"
  echo "✗ la plataforma de modelos no responde: HTTP $codigos ($intentos intentos) en $COLABHIVE_BASE_URL/chat/completions" >&2
  [ "$codigo" = "000" ] && echo "  (000 = ni contestó en ${ARRANQUE_FRIO}s. Si el modelo estaba desalojado, este mismo pedido lo arrancó: reintentá una vez.)" >&2
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
# Deja la base del árbol vacía y con el esquema puesto, antes de una pasada de la suite.
#
#   limpiar_base_del_arbol <ruta del worktree>
#
# El validador de tests corre el MISMO test dos veces —una sin la implementación y otra con
# ella— y el test inserta sus datos en la preparación, haya implementación o no. Así que la
# segunda pasada choca con la fila que dejó la primera SOBRE LA MISMA BASE, por nueva que sea.
# Medido el 2026-10-25: con la base propia ya creada y anunciada, T26 seguía dando
# `Duplicate entry 'test@example.com' for key 'usuarios.email'`.
#
# O sea que aislar por worktree era NECESARIO y NO SUFICIENTE. Lo que el aislamiento habilita
# es esto: vaciar la base no le rompe nada a ninguna tarea hermana, porque es de un solo
# árbol. Era la única objeción que esta salida tenía.
#
# Vacía el PROYECTO y no el método, igual que el DROP: el método no sabe qué tablas hay.
limpiar_base_del_arbol() {
  local wt="$1" ent db
  [ -n "$wt" ] && [ -d "$wt" ] || return 0
  [ -x "$BASE/scripts/entorno.sh" ] || return 0
  ent="$wt/${PROYECTO:-.}/.entorno"
  # Un ENLACE es el `.entorno` del tronco: ésa es la base del proyecto y no se vacía.
  [ -f "$ent" ] && [ ! -L "$ent" ] || return 0
  db="$(sed -n 's/^export MYSQL_DB=//p' "$ent" | head -1 | tr -d "\"'")"
  [ -n "$db" ] || return 0
  # Devuelve si LIMPIÓ, y eso es lo que permite medir a quién cobrarle un choque de UNIQUE.
  # Antes terminaba en `|| true` y devolvía 0 siempre, así que quien la llamaba no podía
  # distinguir «la base quedó vacía» de «no pude». Con eso, el ⊘ del `Duplicate entry`
  # afirmaba «lo causa el MÉTODO» sin haberlo medido — y el 2026-10-25 esa afirmación era
  # falsa tres corridas seguidas: la base SÍ se limpiaba entre pasadas, y el estado venía del
  # intento anterior porque su base no se tiraba al rehacer el worktree.
  ( cd "$BASE" && MYSQL_DB="$db" bash scripts/entorno.sh --limpiar ) >/dev/null 2>&1
}

# La base de un worktree se va CON el worktree.
#
#   tirar_base_del_worktree <ruta del worktree>
#
# Desde el 2026-10-25 cada worktree tiene su propia base —antes todos escribían en la misma,
# nadie la limpiaba, y el validador de tests, que corre el mismo test DOS VECES, chocaba en la
# segunda con la fila que insertó la primera: `Duplicate entry ... for key 'usuarios.email'`,
# y el veredicto se lo cobraba al test—. Si nadie la tira, el servidor se llena de bases
# muertas, que es cambiar una fuga por otra.
#
# El DROP lo hace el PROYECTO, no el método: `scripts/entorno.sh --tirar` del proyecto sabe
# dónde está su cliente y cómo se llama su base, y el método no. Es la misma división que ese
# archivo declara en su encabezado. Si el proyecto no tiene ese script, acá no hay nada que
# hacer y no se inventa nada.
#
# Se llama ANTES de `git worktree remove`: después el `.entorno` con el nombre de la base ya
# no está, y nadie sabría qué tirar.
tirar_base_del_worktree() {
  local wt="$1" proy ent db
  [ -n "$wt" ] || return 0
  # Un worktree que ya no está en el disco no es «nada que hacer»: es que alguien llamó a
  # esto DESPUÉS de borrarlo, y entonces la base queda viva y nadie se entera. Fue
  # exactamente lo que pasó en `escribir-tests.sh`, donde la llamada estaba después de un
  # `rm -rf`. El aviso es el que convierte un silencio en un dato.
  if [ ! -d "$wt" ]; then
    # ¿Nunca existió, o lo borraron antes de tiempo? Lo dice GIT: si conoce el worktree, el
    # directorio estuvo y alguien se lo llevó —y entonces su base quedó viva—. Si no lo
    # conoce, es la limpieza PREVENTIVA de la primera corrida y no hay nada que avisar.
    #
    # Sin la distinción el aviso salía en TODA corrida de tarea, que es la forma más rápida
    # de que alguien aprenda a ignorarlo. Lo midió `correr-tarea.sh` al lanzar T15 y T20.
    if git -C "$RAIZ" worktree list --porcelain 2>/dev/null \
         | grep -qxF "worktree $(cd "$(dirname "$wt")" 2>/dev/null && pwd)/$(basename "$wt")"
    then
      echo "     ⚠ $wt ya no está: no pude saber qué base tirar. Si era un worktree con base" >&2
      echo "        propia, quedó viva en el servidor. Hay que tirarla ANTES de borrar el" >&2
      echo "        directorio, porque su nombre vive en su .entorno." >&2
    fi
    return 0
  fi
  proy="$wt/${PROYECTO:-.}"
  [ -x "$BASE/scripts/entorno.sh" ] || return 0
  ent="$proy/.entorno"
  # Un ENLACE es el `.entorno` del tronco: ahí la base es la del proyecto y no se toca.
  [ -f "$ent" ] && [ ! -L "$ent" ] || return 0
  db="$(sed -n 's/^export MYSQL_DB=//p' "$ent" | head -1 | tr -d "\"'")"
  [ -n "$db" ] || return 0
  ( cd "$BASE" && MYSQL_DB="$db" bash scripts/entorno.sh --tirar ) 2>/dev/null \
    || echo "     ⚠ quedó la base $db en el servidor: tirala con MYSQL_DB=$db bash scripts/entorno.sh --tirar"
}

conservar_intento() {
  # $3 = prefijo del archivo, `intento` por defecto y `exito` cuando el gate dio VERDE. El
  # dataset necesita distinguir el positivo del negativo, y el directorio se llama
  # `fallidos-<id>`: sin el prefijo, un éxito guardado ahí queda indistinguible de una falla.
  # (El nombre del directorio quedó: renombrarlo toca cuatro scripts, los documentos y los
  # `fallidos-*` que ya existen en disco en los proyectos. Anotado, no hecho.)
  local wt="$1" id="${2:-tarea}" pre="${3:-intento}" dest log
  [ -d "$wt" ] || return 0
  dest="$RAIZ/../fallidos-$id"
  # El log se llama distinto según el camino: .tarea.log en el runner, .tests.log al
  # escribir tests, .log en los arneses de experimento.
  for log in "$wt/.tarea.log" "$wt/.tests.log" "$wt/.log"; do
    [ -f "$log" ] || continue
    mkdir -p "$dest"
    # En UTC, igual que el encabezado que el runner escribe adentro del log. Estaba en hora
    # local, y hoy leí «16:38 UTC» adentro de un archivo llamado `intento-133855` y concluí
    # que el transcript se había perdido: comparé dos relojes distintos y por un rato creí
    # que el método destruía su propia evidencia. Con la fecha, además, dos corridas del
    # mismo minuto de días distintos no se pisan.
    cp "$log" "$dest/$pre-$(date -u +%Y%m%dT%H%M%SZ).log" 2>/dev/null
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
    } > "$dest/parche-$(date -u +%Y%m%dT%H%M%SZ).diff"
    echo "     (intento conservado en $dest: transcript y parche de $(echo "$sucios" | grep -c .) archivo/s)"
  fi
}

# ── El tronco no es un worktree: lo que un agente escribe de más, se mide y se saca.
#
# `replanificar.sh` y `replanificar-relevo.sh` corren `cd "$BASE"` sobre el proyecto REAL,
# no sobre una copia: sus agentes tienen permiso de escritura sobre el tronco. El prompt se
# lo prohíbe —«NO modifiques ningún archivo del plan ni de las tareas. NO escribas ningún
# archivo: tu respuesta ES el entregable»— y nadie lo verificaba. Un prompt no es un permiso.
#
# Medido el 2026-10-24: el relevo de T05c corrió de 10:16:44 a 10:27:07 y el que tenía que
# reescribir el enunciado IMPLEMENTÓ la tarea. Dejó `backend/app/rutas/ads.py` —89 líneas,
# sin seguimiento— en el tronco a las 10:26:51, y la corrida terminó con `exit=0` diciendo
# sólo «✗ no escribió el cuerpo nuevo»: cierto en la letra y callado en lo grave.
#
# Lo que estaba en juego no era el archivo de más sino la corrida siguiente: ese código iba
# a quedar ahí para que el próximo intento de tests-first de T05c lo encontrara ya hecho
# —justo lo que `validar-plan.py` prohíbe— y para que el paso 0 del gate viera «implementó
# la feature, el test pasa» y concluyera «el test no prueba nada», que es el diagnóstico
# equivocado. Dos corridas distintas unidas por un archivo que nadie puso en ninguna foto.
#
# La foto de `escribir-tests.sh` no alcanza: mide el worktree del ejecutor, y esto pasa
# fuera de todo worktree. Vive acá y no copiado en los dos replanificadores porque es UNA
# regla con DOS lectores, y una regla copiada en dos lados es una regla que va a divergir.

# La foto de ANTES. Igual que `.sucio-antes` del chequeo de alcance: lo que ya estaba no lo
# escribió el agente. El archivo de destino aparece en su propia foto —la redirección lo
# crea antes de que corra el `git`— y por eso se resta solo.
foto_proyecto() {
  local destino="$1"
  ( cd "$BASE" 2>/dev/null || exit 1
    { git diff --name-only --relative HEAD 2>/dev/null
      git ls-files --others --exclude-standard 2>/dev/null; } | sort -u ) > "$destino" \
    || : > "$destino"
}

# Lo que apareció después de la foto y no estaba permitido, por stdout y relativo a $BASE.
#
# Sin foto NO dice «limpio»: avisa que no pudo medir. Un chequeo que informa verde cuando le
# falta el instrumento es el defecto que este archivo entero persigue.
escrituras_de_mas() {
  local foto="$1" permitido="$2"
  if [ ! -f "$foto" ]; then
    echo "  ⚠ sin foto del tronco ($foto): no se puede medir qué escribió el agente" >&2
    return 0
  fi
  ( cd "$BASE" 2>/dev/null || exit 0
    { git diff --name-only --relative HEAD 2>/dev/null
      git ls-files --others --exclude-standard 2>/dev/null; } | sort -u \
      | comm -23 - "$foto" | grep -vE "$permitido" | grep . ) || true
}

# Saca del tronco lo que el agente escribió sin permiso y lo deja aparte. NO lo borra: el
# 2026-10-24 ese archivo de más era la prueba de un HUECO del plan. Tenía un `GET /ads` que
# devolvía `501 No implementado` con el comentario «esta funcionalidad no está implementada
# en el servicio de ads según el alcance de la tarea T05c», escrito por el propio modelo
# antes de que nadie se lo preguntara, y coincidía con el diagnóstico del 27B. Borrarlo
# habría borrado la evidencia del defecto, que es lo único que este método produce.
sacar_escrituras_de_mas() {
  local id="$1"; shift
  local dest="$RAIZ/../relevo-escribio-$id" f
  for f in "$@"; do
    mkdir -p "$dest/$(dirname "$f")"
    if git -C "$BASE" ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      cp "$BASE/$f" "$dest/$f" 2>/dev/null && git -C "$BASE" checkout -- "$f" 2>/dev/null
    else
      mv "$BASE/$f" "$dest/$f" 2>/dev/null
    fi
  done
  echo "$dest"
}

# El guardia entero, para que cada replanificador llame UNA línea:
#
#   revisar_escrituras_de_mas <foto> <id> <quién> [patrón extra permitido]
#
# Permitido siempre: el andamio que el arnés mismo escribe dentro del proyecto. El `[^/]*`
# del log y la barra del directorio están para que el permiso no tape un archivo del agente
# que apenas empiece parecido. Devuelve 1 si hubo algo de más.
revisar_escrituras_de_mas() {
  local foto="$1" id="$2" quien="$3" extra="${4:-}" demas
  local permitido="^(\\.relevo-[^/]*\\.log|\\.replan-[^/]*\\.log|\\.opencode-data/|\\.oc/${extra:+|$extra})"
  demas="$(escrituras_de_mas "$foto" "$permitido")"
  [ -n "$demas" ] || return 0
  echo "  ✗ $quien escribió en el tronco $(echo "$demas" | grep -c .) archivo/s y tenía PROHIBIDO escribir:"
  echo "$demas" | sed 's/^/       /'
  echo "     sacados del tronco, guardados en $(sacar_escrituras_de_mas "$id" $demas)"
  return 1
}

# ¿Los archivos de esta tarea están commiteados?
#
#   tarea_sin_commitear <id>     0 = limpio, 1 = sucio (y lo imprime)
#
# El worktree sale del árbol COMMITEADO. Un arreglo del contrato o del test que esté sin
# commitear NO llega al agente y no se entera nadie: trabaja contra la versión vieja, el gate
# lo juzga contra la vieja, y el rojo que sale no habla de lo que arreglaste.
#
# Vive acá y no copiado en los dos runners porque es UNA declaración con DOS lectores, y una
# regla copiada en dos lados es una regla que va a divergir — la forma que este repo repite.
# Estaba sólo en `correr-tarea.sh`, y en `escribir-tests.sh` la consecuencia era peor: ahí no
# se pierde una corrida, se ACEPTA el artefacto equivocado. El validador compara el test del
# agente contra la implementación de referencia del propio agente, las dos escritas contra el
# enunciado viejo, así que los tres pasos pasan y el test del contrato viejo se copia al
# tronco. Lo encontró una auditoría, no una corrida: el defecto estaba latente.
tarea_sin_commitear() {
  local id="$1" sucios
  sucios="$(cd "$RAIZ" && { git diff --name-only HEAD -- "$PROYECTO/tareas/${id}"-*.md 2>/dev/null
      # Y el archivo de test que la tarea declara: el agente no lo toca, pero el gate lo usa.
      local decl
      decl="$(sed -n 's/.*`\([^`]*\)`, *clase `[A-Za-z0-9_]*`.*/\1/p' \
              "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
      [ -n "$decl" ] && git diff --name-only HEAD -- "$PROYECTO/$decl" 2>/dev/null
    } | grep . | sort -u || true)"
  [ -n "$sucios" ] || return 0
  echo "✗ $id: estos archivos de la tarea tienen cambios SIN COMMITEAR, y el worktree sale"
  echo "  del árbol commiteado: el agente trabajaría contra la versión vieja."
  printf '     %s\n' $sucios
  echo "  Commiteá el contrato y el test antes de lanzar, o el rojo que salga no va a hablar"
  echo "  de lo que arreglaste."
  return 1
}

# Qué significa un punto muerto, cuando se puede decir.
#
#   explicar_punto_muerto <huella>
#
# Dos cortes por LÍMITE TOTAL no son «el agente falla igual»: son «trabajó todo el
# presupuesto y no terminó», dos veces, y eso habla de la TAREA. `escribir-tests.sh` ya lo
# explicaba en su propio camino y `correr-plan.sh` sólo decía «punto muerto»: el arreglo
# estaba de un lado y no del hermano, que es la forma que este repo repite.
#
# Pasó con T05 el 2026-10-19: dos cortes de 1200s, y el transcript mostraba al agente
# escribiendo los tres archivos que la tarea pide y quedándose sin tiempo iterando. No era
# el enunciado —ése ya se había arreglado— ni el modelo: era el presupuesto.
#
# No lleva números escritos a mano. Un número en un mensaje envejece y después miente; lo
# que lleva es el comando que lo calcula, que es la regla P2 del método.
explicar_punto_muerto() {
  case "${1:-}" in
    *"límite total"*)
      echo "      Eso no es el agente fallando igual: trabajó TODO el presupuesto y no"
      echo "      terminó, las dos veces. Habla de la TAREA, no del modelo."
      echo "      Mirá el transcript y decidí con eso:"
      echo "        · si escribió todo lo que la tarea pide y se cortó iterando, es"
      echo "          presupuesto. Relanzala sola con más:"
      echo "            LIMITE_AGENTE=2400 bash \$AGENTES/scripts/correr-plan.sh ${2:-TNN}"
      echo "        · si iteró contra algo que no existe, es el enunciado: le falta el medio."
      echo "        · si escribió de más, fuera de su alcance, la tarea es demasiado grande."
      # «el éxito más lento» y no «el máximo»: el máximo que `metricas.sh` imprimía era un
      # ROJO de 1855 s —más largo que el propio límite, porque el número incluye el gate— y
      # el éxito más lento medía 970. Calibrar un presupuesto con el techo del vigilante es
      # medirse con la propia regla. El lector ahora imprime la línea que este mensaje pide.
      echo "      Cuánto margen hay entre este presupuesto y el éxito más lento, medido"
      echo "      en la línea «éxito más lento» de:"
      echo "        bash \$AGENTES/scripts/metricas.sh" ;;
  esac
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
  case "$tools" in ''|*[!0-9]*) tools=0 ;; esac
  if [ -z "$prev" ]; then
    # La línea base se escribía sin validar NADA, y un control que ya estaba roto cuando se
    # la escribió se AUTO-VALIDA para siempre: con `tools=0` la primera mitad del criterio
    # queda apagada —pide `t_prev > 0`— y con un veredicto estable la segunda nunca dispara.
    # Es justo el modo de falla para el que esta función existe («el modelo de un partner daba
    # 0 de 6 llamadas por un defecto del arnés») y no podía verlo. Lo encontró una auditoría
    # ejercitando la función con `tools=0`, no una corrida: los cinco casos pineados en los
    # tests usaban 6, 5 y 2 llamadas y veredicto VERDE.
    if [ "$tools" -le 0 ] || [ "$gate" = "?" ]; then
      echo "el control no sirve como línea base: $tools llamada(s) a herramientas, veredicto «${gate}». Un control que no actúa no puede señalar que el arnés se movió."
      return 1
    fi
    echo "$clave|$tools|$gate|$(date -u +%FT%TZ)" >> "$base"
    return 2
  fi
  t_prev="$(echo "$prev" | cut -d'|' -f3)"; g_prev="$(echo "$prev" | cut -d'|' -f4)"
  # Herramientas a la mitad o menos: dejó de actuar. Es el modo de falla medido — el modelo de
  # un partner daba 0 de 6 llamadas por un defecto del arnés, no del modelo.
  case "$t_prev" in ''|*[!0-9]*) t_prev=0 ;; esac
  # Y una línea base degenerada que quedó escrita ANTES de este chequeo tampoco sirve: hay
  # que decirlo en vez de dar la tanda por válida.
  if [ "$t_prev" -le 0 ] || [ "$g_prev" = "?" ]; then
    echo "la línea base del control está degenerada ($t_prev herramientas, veredicto «${g_prev}»): no puede detectar nada. Borrá su línea de $base y volvé a medirla con el arnés sano."
    return 1
  fi
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
  # Quien lanza la corrida la mide al ARRANCAR y la pasa en `CONCURRENCIA_AL_ARRANCAR`.
  # Contarla acá es contarla al cerrar, que es otra cosa y es la que no sirve (ver
  # `correr-tarea.sh`). El respaldo queda para los llamadores que no la pasan
  # —`cerrar-tarea.sh`, que es trabajo humano y no compite con nada—.
  local concurrencia="${CONCURRENCIA_AL_ARRANCAR:-}"
  [ -n "$concurrencia" ] || concurrencia="$(pgrep -f "opencode run" 2>/dev/null | wc -l | tr -d ' ')"
  [ -n "$concurrencia" ] || concurrencia=0
  # `instrumento`: la huella de los scripts que produjeron la fila. Dos filas con huellas
  # distintas no se comparan — es el punto 7 de la regla de parada de MEDICION.md, que decía
  # «cambiaste el instrumento entre dos corridas: no son comparables» y no tenía cómo saberlo.
  local instrumento
  instrumento="$(git -C "$RAIZ" rev-parse --short HEAD:scripts 2>/dev/null || echo "?")"
  # Si el árbol de trabajo tiene cambios en scripts/, la huella del COMMIT miente: lo que
  # corrió no es lo commiteado, y dos corridas con scripts distintos comparten huella — que
  # es justo el estado contra el que avisa el guardia de `correr-todo.sh`. `congelar-banco.sh`
  # ya lo marcaba así y esto no: el arreglo estaba de un lado y no del otro.
  # Con HEAD: `git diff --quiet -- <ruta>` compara árbol↔ÍNDICE, así que un `git add scripts/`
  # —el reflejo de cualquiera que quiera mirar su propio diff antes de lanzar— apagaba la
  # marca y la fila quedaba con la huella del commit viejo y sin aviso. Justo el estado que
  # esta línea existe para delatar. El modelo que cité al escribirla (`congelar-banco.sh`)
  # tenía el mismo defecto, así que el arreglo copió el agujero.
  git -C "$RAIZ" diff --quiet HEAD -- scripts 2>/dev/null || instrumento="${instrumento}+sin-commitear"
  # Y los contextos declarados, que también son el instrumento. Las filas viejas quedan con
  # el campo VACÍO, que es lo honesto: no dice «el mismo contexto», dice «no se registró».
  local contextos
  contextos="$(huella_contextos)"
  local ENCABEZADO="fecha,proyecto,tarea,veredicto,segundos,modelo,motivo,concurrencia,instrumento,contextos"
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
  echo "$(date -u +%FT%TZ),${PROYECTO:-.},$id,$ver,$segs,$modelo,$motivo,$concurrencia,$instrumento,$contextos" >> "$reg"
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

huella_scripts() {
  # TODOS los archivos del directorio, no los `*.sh`. El instrumento incluye los diez `.py`
  # que viven acá: `_imports.py` y `_suprimidas.py` son lo que el gate ejecuta, `mutar.py` y
  # `vaciar.py` deciden si un test se acepta, `coherencia.py` y `_etapas.py` deciden si el
  # plan arranca y cómo se cortan las etapas. Editar uno con el plan en vuelo —que es
  # literalmente lo que pasó cuatro veces el 2026-10-20— pasaba el guardia de borde de etapa
  # en silencio: la etapa 1 se juzgaba con un chequeo y la etapa 5 con otro, y el guardia
  # decía que era la misma corrida. Sin lista de extensiones a propósito: una enumeración
  # envejece callando, y cada `.py` nuevo que se mueva acá quedaba afuera sin que nada avise.
  # Se saltean los que empiezan con punto (`.DS_Store`, swaps del editor): no son el método.
  # El directorio es un ARGUMENTO con valor por omisión: sin eso la función sólo puede
  # hablar del método instalado y no hay forma de apuntarla a un árbol de prueba, así que su
  # conducta no se puede verificar — sólo su texto. Lo descubrí rompiendo el test que la
  # verificaba: al mudarla acá quedó inverificable, que es peor que estar en el lugar
  # equivocado.
  local dir="${1:-$AGENTES/scripts}"
  find "$dir" -maxdepth 1 -type f ! -name '.*' 2>/dev/null | LC_ALL=C sort \
    | tr '\n' '\0' | xargs -0 cat 2>/dev/null | git hash-object --stdin 2>/dev/null || echo "?"
}

# ¿Cambió el instrumento desde que arrancó esto? Se compara contra `HUELLA_INSTRUMENTO`, que
# fija el primero que pregunte y heredan los hijos.
#
# Se verifica ANTES DE CADA INTENTO y no sólo en el borde de etapa, que es donde estaba. El
# guardia de borde de etapa mira en el único momento en que ya es tarde: entre dos bordes
# pueden pasar cuarenta minutos y seis intentos, y cualquier edición en esa ventana queda
# fuera de su alcance. Lo demostré rompiéndolo: el 2026-10-21 edité `escribir-tests.sh` dos
# veces con un intento en curso —con la regla a la vista y después de citarla cuatro veces—
# y el guardia no se enteró. Es el mismo problema que `huella_enunciado` ya resuelve bien, en
# el mismo archivo: comparar la huella del sujeto antes de cada intento, no por tanda.
# La huella de los CONTEXTOS DECLARADOS, que son parte del instrumento y no vivían en
# ninguna huella. `huella_scripts` cubre `scripts/`; el `limit.context` de cada modelo vive
# en la config de opencode, afuera del repo, así que cambiarlo no movía ninguna huella y las
# filas de antes y después quedaban comparables sin serlo.
#
# Medido el 2026-10-21: el ejecutor venía declarado con 32000 cuando la plataforma le sirve
# 241000 —ocho veces menos— y al corregirlo NADA dijo que las filas anteriores dejaban de
# ser comparables. Un cambio de contexto cambia lo que el sujeto puede hacer; es la misma
# clase de cosa que cambiar un script, y el registro no la veía.
#
# Se hashea SÓLO `{id: limit.context}` y no el archivo entero: la config lleva tema, atajos
# y claves, y un cambio de tema no vuelve incomparables dos corridas. Una huella que se
# mueve por cosas que no afectan al sujeto es una huella que nadie va a poder usar.
huella_contextos() {
  local cfg="${CONFIG_OC:-$HOME/.config/opencode/opencode.json}"
  [ -f "$cfg" ] || { echo "?"; return 0; }
  python3 -I - "$cfg" 2>/dev/null <<'PYCTX' || echo "?"
import hashlib, json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("?"); raise SystemExit
pares = []
for pv in (d.get("provider") or {}).values():
    for mid, m in ((pv.get("models") or {}).items()):
        ctx = (m.get("limit") or {}).get("context")
        if ctx:
            pares.append("%s=%s" % (mid, ctx))
print(hashlib.sha1("\n".join(sorted(pares)).encode()).hexdigest()[:7] if pares else "?")
PYCTX
}

instrumento_se_movio() {
  local ahora; ahora="$(huella_scripts)"
  if [ -z "${HUELLA_INSTRUMENTO:-}" ]; then
    HUELLA_INSTRUMENTO="$ahora"; export HUELLA_INSTRUMENTO; return 1
  fi
  [ "$ahora" = "$HUELLA_INSTRUMENTO" ] && return 1
  echo "  ✗ los scripts del método CAMBIARON con la corrida en curso" >&2
  echo "     (instrumento al arrancar: $HUELLA_INSTRUMENTO · ahora: $ahora)" >&2
  echo "     bash lee los scripts por posición mientras ejecuta: lo que siga no es" >&2
  echo "     confiable, y lo ya hecho tampoco, porque el bucle pudo saltar pedazos." >&2
  return 0
}

# Empezar en la etapa N saltea las anteriores. El argumento existe para retomar después de
# arreglar algo, y eso es legítimo; lo que no puede es saltar trabajo callado.
#
#   rechazar_salteo <desde> <comando para relanzar> <etapa>...
#
# UNA copia, en el método, y los dos runners la llaman. La guardia nació del salteo de T05 y
# se escribió sólo en `correr-todo.sh`: `correr-plan.sh` siguió tomando el índice sin guardia,
# o sea que el arreglo dejó abierto el script hermano del defecto que venía a cerrar. Es la
# cuarta vez en un día que un arreglo se aplica a una copia y no a su hermana, así que esta
# vez no hay copia que desincronizar.
rechazar_salteo() {
  local desde="$1" relanzar="$2"; shift 2
  [ "$desde" -gt 1 ] 2>/dev/null || return 0
  local salteadas="" i=0 etapa
  for etapa in "$@"; do
    i=$((i+1)); [ "$i" -lt "$desde" ] || break
    salteadas="$salteadas $etapa"
  done
  [ -n "$(echo "$salteadas" | tr -d ' ')" ] || return 0
  echo "✗ Al empezar en la etapa $desde se saltean tareas que siguen pendientes:$salteadas" >&2
  echo "  Los números de etapa se recalculan en cada corrida: al cerrar una etapa, las" >&2
  echo "  que siguen se corren un lugar. El número que anotaste ya no significa lo mismo." >&2
  echo "  Corré sin argumento —arranca en la primera etapa con trabajo pendiente—:" >&2
  echo "    $relanzar" >&2
  exit 1
}

# Qué veredicto se ESCRIBE en el registro: el del gate primero, siempre.
#
#   veredicto_registrado <rc del gate> <error de la herramienta> <log>
#
# Vive acá, como función, y no inline en el llamador, porque inline sólo se podía verificar
# leyéndolo — y ahí fue donde el arreglo se perdió. `correr-tarea.sh` decidía con
# `[ -n "$error" ] && echo ERROR || veredicto "$log"`, o sea el ruido de la herramienta ANTES
# del código del gate, mientras doce líneas más abajo un comentario declaraba lo contrario
# para el mensaje de consola. Medido: T07, T27 y T06 del 2026-10-04 tienen su commit
# `TNN: gate verde` al segundo exacto de una fila ERROR —y `cerrar_con_gate` commitea sólo
# con rc 0, así que el commit prueba el verde—; `metricas.sh` las informaba como «nunca
# llegaron a verde» Y las descontaba como pérdida de plataforma. Es P2: el juez es un
# comando, y si el comando dio verde, el log no lo desmiente.
veredicto_registrado() {
  local rc="${1:-1}" error="${2:-}" log="${3:-}"
  if [ "$rc" -eq 0 ]; then echo VERDE; return 0; fi
  if [ -n "$error" ]; then echo ERROR; return 0; fi
  # `veredicto` no imprime nada si el log está incompleto (sin la línea `=== fin`), y una
  # columna vacía es una fila que ningún lector puede clasificar. El gate ya dijo que no es
  # verde, así que el respaldo es ROJO: lo único que `veredicto` agrega sobre el rc es
  # distinguir IMPOSIBLE, y para eso necesita el log.
  local v; v="$(veredicto "$log")"
  echo "${v:-ROJO}"
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
            conex="$(conexiones_vivas "$pid")"
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
# Los modelos que la corrida va a usar DE VERDAD, uno por línea: «<id> <papel>,<papel>».
#
# TODOS los agentes declarados, no una lista escrita acá a mano. Los scripts piden
# `arquitecto` y `ejecutor`, pero OpenCode usa por su cuenta `title`, `summary` y
# `compaction` para la maquinaria de la sesión: si ésos están caídos, la sesión del agente se
# cae igual y el veredicto va a decir que falló la tarea. Una lista a mano envejece con el
# primer papel nuevo, que es la forma que este repo repite.
modelos_de_la_corrida() {
  local cfg="${CONFIG_OC:-$HOME/.config/opencode/opencode.json}"
  [ -f "$cfg" ] || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - "$cfg" <<'PYCORR' 2>/dev/null
import json, sys
try:
    cfg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
por_modelo = {}
orden = []
for nombre, a in sorted((cfg.get("agent") or {}).items()):
    m = ((a or {}).get("model") or "").split("/")[-1]
    if not m:
        continue
    if m not in por_modelo:
        por_modelo[m] = []; orden.append(m)
    por_modelo[m].append(nombre)
for m in orden:
    print(m, ",".join(por_modelo[m]))
PYCORR
}

# La sonda del PREFLIGHT: todos los modelos que la corrida va a usar, no uno.
#
# `plataforma_responde` mide `modelo_del_agente ejecutor` y nada más. Una corrida usa varios
# —en la config de hoy, 13 papeles declarados sobre 3 modelos distintos— y las réplicas se
# caen de a una: el 2026-10-24 el monitoreo midió réplicas ancladas con `min=1` que quedaron
# en `actuales=0`, y el 27B estuvo TRES HORAS caído mientras el ejecutor contestaba 200. Con
# esa sonda el preflight daba verde y la corrida moría en la primera replanificación,
# informando que falló la tarea.
#
# Un chequeo que mide un sujeto y autoriza a otro es el defecto central de este método, y
# acá estaba en la puerta: es lo único que separa «no arrancar» de nueve etapas de agentes.
#
# El mensaje nombra los PAPELES y no sólo el id. «1af07b1f-5832 no responde» no le sirve a
# nadie; «el modelo de arquitecto, plan, reviewer, seguridad no responde» se puede actuar.
#
# El que sigue mirando un solo modelo es `escribir-tests.sh`, y está bien: ahí la pregunta es
# otra —«¿la plataforma está viva AHORA, o el cuelgue es de la herramienta?»— y se hace en
# medio de un bucle de reintentos, donde sondear tres modelos cuesta minutos por intento.
plataforma_responde_la_corrida() {
  [ -n "${COLABHIVE_BASE_URL:-}" ] || return 0      # sin configurar, no opinamos
  local lista m papeles caidos=0 probados=0
  lista="$(modelos_de_la_corrida)"
  if [ -z "$lista" ]; then
    echo "  ⊘ no pude leer qué modelos usa la corrida: sondeo sólo el del ejecutor" >&2
    plataforma_responde
    return $?
  fi
  # Here-string y no tubería: el `while` de un pipe corre en un subshell y los contadores no
  # sobreviven. Es el defecto que este repo ya tuvo tres veces, con guardas detrás de una
  # tubería que no podían disparar.
  while read -r m papeles; do
    [ -n "$m" ] || continue
    probados=$((probados+1))
    if MODELO_SONDA="$m" plataforma_responde; then
      echo "  ✓ responde el modelo de $(echo "$papeles" | tr ',' ' ')"
    else
      echo "✗ NO responde el modelo de $(echo "$papeles" | tr ',' ' ') ($m)" >&2
      caidos=$((caidos+1))
    fi
  done <<<"$lista"
  if [ "$caidos" -gt 0 ]; then
    echo "✗ $caidos de $probados modelos de esta corrida no responden." >&2
    echo "  Arrancar así gasta el presupuesto de cada tarea que toque ese papel, y el rojo" >&2
    echo "  que salga va a nombrar la tarea en vez del modelo caído." >&2
    return 1
  fi
  return 0
}

# Los PIDs del ÁRBOL: el proceso y todos sus descendientes.
#
# Hace falta porque `lsof -g` mira el GRUPO de procesos, y el grupo no es el árbol: basta un
# envoltorio entre `con_limite` y el agente para que la conexión al modelo quede afuera del
# grupo que se consulta. Medido el 2026-10-24 con el arnés real:
#
#   agente como hijo DIRECTO de con_limite  →  150s callado, NO se cortó por silencio
#   el mismo agente dentro de `bash -c`     →  cortado a los 15s, «sin ninguna conexión»
#
# O sea que la protección dependía de un detalle estructural invisible en el call site. Hoy
# ninguno envuelve al agente, así que esto no era un defecto activo: era una trampa puesta
# para el próximo que agregue uno, y nada lo habría avisado —el síntoma es «el agente se
# colgó», con el sujeto equivocado—.
descendientes() {
  local raiz="$1" h
  echo "$raiz"
  for h in $(pgrep -P "$raiz" 2>/dev/null); do
    descendientes "$h"
  done
}

# ¿Tiene el agente alguna conexión abierta? Callado no es lo mismo que colgado: generar un
# archivo largo son minutos sin imprimir una letra, y mientras eso pasa el socket al modelo
# sigue ESTABLISHED.
#
# Devuelve un número (0 = ninguna) o `SIN_LSOF` si el chequeo no se puede hacer. Es una
# pregunta de PRESENCIA, no un conteo: la unión de grupo y árbol puede contar dos veces la
# misma conexión, y al único lector le importa si es mayor que cero.
#
# Se conserva el chequeo del grupo ADEMÁS del árbol porque son dos formas de perder al
# proceso: un hijo que se cambia de grupo sale del primero, y un proceso que se desprende del
# padre sale del segundo. Union, no reemplazo.
conexiones_vivas() {
  local lsof_bin="${LSOF:-lsof}" pids
  command -v "$lsof_bin" >/dev/null 2>&1 || { echo "SIN_LSOF"; return; }
  pids="$(descendientes "$1" | sort -u | tr '\n' ',' | sed 's/,$//')"
  { "$lsof_bin" -nP -g "$1" 2>/dev/null
    [ -n "$pids" ] && "$lsof_bin" -nP -p "$pids" 2>/dev/null
  } | grep -c ESTABLISHED
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
  # Y se commitea EN EL ACTO. Lo escribía y lo dejaba sin trackear, así que `integrar.sh`
  # —que se niega a mergear con el tronco sucio, y tiene razón— frenó la etapa 1 de
  # clasificados con T04b y T26 las DOS en verde. El método bloqueándose con su propia
  # salida: la memoria verificada es la primera cosa que el runner escribe en el tronco y
  # nadie la había puesto en un commit. Y el mensaje que salía —«el tronco tiene cambios sin
  # commitear»— hacía pensar en un descuido del humano.
  #
  # El pathspec al final es a propósito: commitea ESTE archivo y no barre lo que haya sucio.
  # Y reintenta, porque las tareas de una etapa corren en paralelo y pueden pelearse el
  # `index.lock`.
  local i=0
  while [ "$i" -lt 3 ]; do
    git -C "$RAIZ" add "$f" >/dev/null 2>&1 \
      && git -C "$RAIZ" commit -q -m "$id: memoria verificada" -- "$f" >/dev/null 2>&1 \
      && break
    i=$((i+1)); sleep 1
  done
  # Si no se pudo, decirlo acá: el síntoma aparece después, en integrar.sh, y allá no se
  # puede saber de dónde vino.
  [ "$i" -ge 3 ] && echo "  ⚠ no pude commitear memoria/${id}.md — integrar.sh va a frenar por tronco sucio" >&2
  return 0
}

# El registro de enlaces de cobertura (`.cobertura.json`), commiteado EN EL ACTO y por el
# mismo motivo que la memoria de arriba: lo escribe `cobertura.py` cuando `correr-todo.sh`
# verifica la firma de G0 —o sea ANTES de la primera tarea— y si queda sin trackear,
# `integrar.sh` frena la etapa 1 con las tareas en verde, con un mensaje («el tronco tiene
# cambios sin commitear») que hace pensar en un descuido del humano. Ya pasó con `memoria/`.
#
# Y commitearlo no es sólo para desatascar: el valor entero del registro es que una
# re-bendición de un enlace quede en el diff, y un archivo sin trackear no tiene diff.
#
# Pathspec al final, como arriba: commitea ESTE archivo y no barre lo que haya sucio al lado.
# Las preguntas del gate humano G3, leídas del plan e IMPRESAS. No «están en PLAN.md».
#
# Las dos puertas que cierran una corrida —`correr-plan.sh` y `correr-todo.sh`— mandaban a una
# persona a buscarlas a un archivo, y el archivo podía no tenerlas: medido el 2026-10-27, el
# plan de `ejemplo-pacman` no tiene la sección G3, y es justamente el proyecto donde el hueco
# se midió (54 tests verdes, cinco problemas en el primer minuto de juego). Un puntero a algo
# que puede no existir es la misma falla que un extractor que busca una forma que el productor
# no emite, con una persona en el lugar del extractor.
#
# Acá, y no copiado en las dos puertas: es un juicio —qué cuenta como pregunta de G3— y el
# método ya tiene medido lo que cuesta copiar un juicio.
preguntas_de_g3() {
  local plan="${1:-$PLAN}" seccion
  [ -f "$plan" ] || { echo "  ⊘ no encuentro $plan: no puedo mostrarte las preguntas de G3"; return 0; }
  seccion="$(awk '/^#+ *G3[^|]*prueba de uso/{d=1;next} d && /^#+ /{exit} d' "$plan"              | grep -E '^[[:space:]]*[-*] \[[ xX]\]' || true)"
  if [ -z "$seccion" ]; then
    echo "  ✗ $plan NO tiene preguntas de G3, y G3 es el único gate que mide lo que ningún"
    echo "    comando mide. Sin él, esto termina verde y malo. La plantilla las trae:"
    echo "    plantillas/PLAN.md — y el validador del plan ahora lo exige."
    return 1
  fi
  printf '%s\n' "$seccion" | sed 's/^[[:space:]]*/    /'
  return 0
}

commitear_cobertura() {
  local reg="${1:-$BASE/.cobertura.json}"
  # Sólo si está SIN TRACKEAR: si ya está en git, un cambio suyo es una re-bendición y ésa
  # la commitea quien la decidió, no el runner por atrás.
  [ -n "$(git -C "$RAIZ" ls-files --others --exclude-standard -- "$reg" 2>/dev/null)" ] || return 0
  local i=0
  while [ "$i" -lt 3 ]; do
    git -C "$RAIZ" add "$reg" >/dev/null 2>&1 \
      && git -C "$RAIZ" commit -q -m "G0: enlaces de cobertura aprobados" -- "$reg" >/dev/null 2>&1 \
      && break
    i=$((i+1)); sleep 1
  done
  [ "$i" -ge 3 ] && echo "  ⚠ no pude commitear .cobertura.json — integrar.sh va a frenar por tronco sucio" >&2
  return 0
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
  # La base se va con el worktree, también por el camino del VERDE. Este sitio es el quinto
  # que destruye un worktree y era el único que no tiraba su base: una tarea que cierra bien y
  # se integra dejaba su base viva en el servidor. Medido el 2026-10-25 después de integrar
  # T15: su worktree ya no estaba y `clasificados_trabajo_T15` seguía ahí.
  #
  # El test de los cinco sitios declara este como «no-aplica» para `conservar_intento`, y es
  # correcto —no hay intento que conservar cuando la tarea cerró verde y su código vive en un
  # commit—. Pero la base no es el intento: eso sí aplica, y la excepción de un chequeo se
  # leyó como excepción del otro.
  tirar_base_del_worktree "$RAIZ/../trabajo-$id"
  git -C "$RAIZ" worktree remove --force "$RAIZ/../trabajo-$id" 2>/dev/null
  git -C "$RAIZ" branch -D "$rama" >/dev/null 2>&1
}
