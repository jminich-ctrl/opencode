#!/usr/bin/env bash
# G0: de un encargo a PLAN.md y las tareas, con el arquitecto corrigiéndose solo.
#
#   bash $AGENTES/scripts/planificar.sh                  # lee OBJETIVO.md del proyecto
#   bash $AGENTES/scripts/planificar.sh mi-encargo.md    # otro archivo de encargo
#   INTENTOS=5 bash $AGENTES/scripts/planificar.sh        # cuántas vueltas de corrección
#   INSTRUCCION="..." bash $AGENTES/scripts/planificar.sh # un pedido acotado, sin rehacer
#
# El bucle: el arquitecto escribe → se valida la forma y la cobertura del encargo → lo que
# esté mal se le devuelve como UN pedido concreto → repite. Se detiene cuando está limpio,
# cuando se agotan los intentos, o cuando falla dos veces por lo mismo (punto muerto).
#
# Por qué el bucle y no una persona en el medio: la primera vez hicimos siete
# intervenciones a mano en este gate, y cuatro eran trabajo de máquina —deduplicar filas,
# borrar etapas mal declaradas, cruzar requisitos contra el plan. Un método con mínima
# interacción humana no puede pedir eso.
#
# Lo que sigue siendo humano, y no se automatiza: cerrar las decisiones con trade-off, y
# firmar. El plan que sale de acá NO está aprobado (HUMANO.md §1).
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE: ver _comun.sh
cargar_entorno_colabhive

AGENTE="${AGENTE:-arquitecto}"
ENCARGO="${1:-OBJETIVO.md}"
# Si el que llama lo fijó, manda él. Si no, lo decide la cantidad de defectos del plan: ver
# el ajuste después del primer `revisar`.
INTENTOS_EXPLICITO="${INTENTOS:+1}"
INTENTOS="${INTENTOS:-3}"
INSTRUCCION="${INSTRUCCION:-}"

[ -f "$BASE/$ENCARGO" ] || { echo "✗ No encuentro $BASE/$ENCARGO" >&2
  echo "  El encargo lo escribe una persona, en sus palabras (HUMANO.md §1)." >&2; exit 1; }

command -v opencode >/dev/null 2>&1 || { echo "✗ No hay opencode." >&2
  echo "  El método no depende de una IA: escribí el plan a mano con plantillas/PLAN.md" >&2
  echo "  y seguí con 'bash scripts/correr-plan.sh'." >&2; exit 1; }

# Un agente que no está registrado responde como el agente por defecto y no avisa.
if ! opencode agent list 2>/dev/null | grep -qE "^$AGENTE \(primary\)"; then
  echo "✗ OpenCode no reconoce '$AGENTE' como agente primario." >&2
  echo "  Suele faltarle \"mode\": \"primary\" en opencode.json (OPENCODE.md §3)." >&2
  echo "  Primarios: $(opencode agent list 2>/dev/null | grep -oE '^[a-z0-9_]+ \(primary\)' | cut -d' ' -f1 | tr '\n' ' ')" >&2
  exit 1
fi

# ¿Está arriba el modelo que este agente usa? La sonda existía y estaba cableada sólo en
# `correr-todo.sh`. Acá importa especialmente: el 2026-10-24 el 27B —arquitecto, plan,
# reviewer— estuvo TRES HORAS caído mientras el ejecutor contestaba 200, así que un preflight
# que mira el ejecutor autoriza a planificar contra un modelo que no está. Y el 2026-10-26 a
# las 08:46 el monitoreo lo volvió a medir en `actuales=0`.
if ! MODELO_SONDA="$(modelo_del_agente "$AGENTE")" plataforma_responde; then
  echo "✗ no se planifica: el modelo de $AGENTE no responde." >&2
  echo "  No es el encargo ni el plan. Esperá que la réplica vuelva y reintentá." >&2
  exit 1
fi

# Revisa el plan y deja en PROBLEMAS lo que el arquitecto tiene que arreglar.
# Los arreglos mecánicos se aplican primero: no gastan una vuelta del modelo.
revisar() {
  PROBLEMAS=""
  [ -s "$BASE/PLAN.md" ] || { PROBLEMAS="No escribiste PLAN.md."; return; }
  local n_tareas
  n_tareas="$(ls "$BASE"/tareas/T*.md 2>/dev/null | wc -l | xargs)"
  [ "${n_tareas:-0}" -gt 0 ] || { PROBLEMAS="No escribiste ningún archivo de tarea en tareas/."; return; }

  local forma cobertura etapas cruce
  forma="$(cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" --arreglar 2>&1)"
  cobertura="$(cd "$BASE" && ENCARGO="$ENCARGO" PLAN=PLAN.md python3 "$AQUI/cobertura.py" 2>&1)"
  etapas="$(SOLO_ETAPAS=1 bash "$AQUI/correr-plan.sh" 2>&1 >/dev/null)"
  # EL CRUCE ENTRE TAREAS, que es el que faltaba y explica una rueda entera.
  #
  # `correr-todo.sh` corre `coherencia.py` en G0 y FRENA si da rojo. El arquitecto —el único
  # que puede arreglar el plan— veía la forma, la cobertura y las etapas, y nunca veía esto.
  # O sea: el planificador declaraba el plan terminado, el lanzador se negaba a arrancar, y
  # nadie le decía al planificador por qué. Dos componentes del método con criterios
  # distintos sobre el mismo plan y sin un canal entre ellos.
  #
  # Es el mismo defecto que ya nombramos dos veces con otras caras: «el arreglo vive en un
  # hermano y no en el otro». Acá el que juzga y el que corrige leían listas distintas.
  cruce=""
  [ -f "$AQUI/coherencia.py" ] && cruce="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" 2>&1)"

  echo "$forma" | sed 's/^/  /'
  echo "$cobertura" | sed 's/^/  /'
  [ -n "$etapas" ] && echo "$etapas" | sed 's/^/  /'
  [ -n "$cruce" ] && echo "$cruce" | sed 's/^/  /'

  # Sólo los ✗ son problemas: los avisos los resuelve quien revisa, no el arquitecto. Y el
  # «no se pudo verificar» de `coherencia.py` (código 3) no imprime ✗ a propósito: no es un
  # defecto del plan y no se le pide al arquitecto que lo arregle.
  PROBLEMAS="$( { echo "$forma"; echo "$cobertura"; echo "$etapas"; echo "$cruce"; } \
                | grep '✗' | sed 's/^ *✗ *//' || true)"
}

# ── HABLÓ Y NO ESCRIBIÓ
#
# UN solo lector del criterio, y por eso es función: el rojo final de G0 también lo consulta.
#
# POR QUÉ NO MIRA EL TEXTO. Mi primera versión contaba «líneas de deliberación» con
# `grep -cE "^(Hmm|Wait|Let me|Actually|OK|So )"` y las escrituras con `grep '→ Write'`. Las
# dos cosas estaban mal por el mismo motivo: **atan el método a un idioma y a un formato**.
# Los marcadores son ingleses, así que un modelo que razone en español deja el detector
# callado — y callado se lee igual que «no rumió», que es un guardia incapaz de disparar—; y
# `→ Write` es la forma del transcripto de OpenCode, así que el día que cambie el detector
# pasa a disparar siempre o nunca sin que nadie lo note.
#
# La pregunta no necesita leer el texto: **¿cambiaron los archivos?** Eso es verdad de
# terreno —la huella que el propio script ya calcula para el veredicto final—, no depende del
# idioma del modelo, ni de qué herramienta usó, ni de cómo se imprime. `$1` es la huella de
# antes de la vuelta y `$2` el byte donde empieza su tramo de log; `SALIDA_N` queda con
# cuántos bytes habló, para informarlo.
hablo_sin_escribir() {
  local huella_antes="${1:-}" desde="${2:-0}" ahora
  # `SALIDA_N` se define ANTES de cualquier salida temprana: quien llama la informa en su
  # mensaje, y con `set -u` una variable sin definir mata al que la lee. Lo encontró el
  # brazo nulo de su propio test —el caso en que el agente SÍ escribió—, que es para lo que
  # está el brazo nulo.
  SALIDA_N=0
  if [ -f "$log" ]; then
    SALIDA_N="$(tail -c "+$((desde + 1))" "$log" 2>/dev/null | wc -c | xargs)"
  fi
  ahora="$(huella_del_plan)"
  [ "$ahora" = "$huella_antes" ] || return 1          # escribió: no hay nada que partir
  # Que haya hablado. Si no produjo NADA, el problema no es el pedido: es que no contestó, y
  # ese camino ya lo cubre `error_del_agente`. Partir un pedido que nunca llegó al modelo
  # gasta otra corrida contra el mismo silencio.
  [ "${SALIDA_N:-0}" -gt 500 ]
}

# La huella del plan y las tareas: un dato declarado, un solo lector. El veredicto final de
# G0 la usaba inline en dos lugares con el mismo `cksum`.
huella_del_plan() {
  (cat "$BASE/PLAN.md" 2>/dev/null; ls "$BASE"/tareas/ 2>/dev/null; \
   cat "$BASE"/tareas/*.md 2>/dev/null) | cksum
}

# ── EL PROTOCOLO DE DOS FASES: decidir en texto, transcribir después.
#
# Medido el 2026-11-26, cinco corridas del arquitecto (Qwen3.8-27B, 6.7 tok/s de mediana)
# sobre el mismo pedido —agregarle al plan las tareas que faltaban—:
#
#   decidir Y escribir, en español              1342s   CERO archivos   58 líneas de delib.
#   decidir Y escribir, en inglés + «write first» 1290s   CERO archivos
#   decidir Y escribir, prompt de sistema inglés   854s   CERO archivos   38 líneas
#   SÓLO decidir, respuesta en 3 líneas            ✓ contestó, una vuelta
#   SÓLO escribir, con la decisión servida         ✓ escribió los dos enunciados
#
# No falla en decidir ni en escribir: falla cuando las dos cosas van en la misma llamada. Y
# el prompt no lo corrige —«WRITE FIRST» como primera línea deliberó 1290s igual—, así que
# lo tiene que cortar el arnés. Repetir el mismo pedido en la vuelta siguiente es gastar
# otros 1200s contra el mismo muro.
#
# El texto hacia el modelo va en inglés: es el idioma en el que este modelo razona de todas
# formas —medido en experimentos/plan-robustez.md— y cuesta 9,2% menos tokens para el mismo
# contenido, lo que importa cuando el reloj del gateway es la restricción que ata. Los
# mensajes para la persona siguen en español: son otra audiencia.
# CUÁNTO HABLÓ, EN LA UNIDAD QUE NO MIENTE.
#
# El arnés decía «habló 0 KB y no cambió ningún archivo». Se contradice solo: el umbral del
# detector son 500 bytes y la división entera a KB los redondea a cero, así que la misma
# línea afirmaba «habló» y «0 KB». El que lee el log concluye que el modelo no dijo nada, que
# es exactamente la atribución equivocada que este guardia existe para evitar. Medido el
# 2026-11-28, en la primera vuelta donde `dos_fases` llegó a disparar.
cuanto_hablo() {
  local n="${SALIDA_N:-0}"
  if [ "$n" -lt 1024 ]; then printf '%s bytes' "$n"; else printf '%s KB' "$((n / 1024))"; fi
}

dos_fases() {
  local pedido_original="$1" bruto decision
  echo "  · habló $(cuanto_hablo) y no cambió ningún archivo: parto el pedido en dos"
  export LOG_VIGILADO="$log"

  # FASE 1 — decidir. Sin archivos, y la respuesta delimitada: capturar la salida cruda de
  # `opencode run` trae trazas de herramientas y color, y pasarle ESO como «tu decisión» es
  # pasarle ruido. Los marcadores son lo que hace recortable la respuesta.
  bruto="$( cd "$BASE" && con_limite "${LIMITE_AGENTE:-1200}" opencode run --agent "$AGENTE" \
    "DECISION ONLY. Do not write or edit any single file: this run has no file output and anything you write will be discarded. State what you decided, nothing else.

$pedido_original

Answer with the decision between these two markers, and put nothing outside them:
---DECISION---
(one line per thing you would write: the file, and what goes in it)
---END---" 2>&1 )"
  printf '%s\n' "$bruto" >> "$log"
  decision="$(printf '%s\n' "$bruto" | sed -n '/---DECISION---/,/---END---/p' \
              | sed '1d;$d' | sed 's/\x1b\[[0-9;]*m//g')"
  if [ -z "${decision//[[:space:]]/}" ]; then
    echo "  ⊘ la fase de decisión no devolvió nada entre los marcadores: no hay qué transcribir"
    return 1
  fi
  echo "  · decidió $(printf '%s\n' "$decision" | grep -c . ) línea(s); ahora sólo las escribe"

  # FASE 2 — transcribir. Su propia decisión servida de vuelta: no es inferirle el plan, es
  # devolverle el que ya escribió en su transcripto.
  ( cd "$BASE" || exit 1
    con_limite "${LIMITE_AGENTE:-1200}" opencode run --agent "$AGENTE" \
      "TRANSCRIPTION JOB. No analysis, no design, no alternatives: the decision below is already yours, made in the previous run. Your first move is the write tool. Write the files exactly as decided and stop.

YOUR DECISION:
$decision

Your only output is files on disk. Your final reply is the list of files you wrote." 2>&1
    [ "$?" = "142" ] && echo "Error: el agente no respondió: $(motivo_del_corte "$log")"
  ) >> "$log" 2>&1
}

[ -f "$BASE/PLAN.md" ] && cp "$BASE/PLAN.md" "$BASE/PLAN.md.previo"
# QUÉ SE LE PIDE AL ARQUITECTO EN CADA VUELTA.
#
# Es función y no un `if` en el medio del bucle para que un test pueda preguntarle qué elige
# sin levantar un modelo —el mismo reparto que `hablo_sin_escribir`— y para que el texto de
# corrección exista UNA vez: lo usan dos ramas y escrito dos veces iba a derivar.
#
# Lee `INSTRUCCION`, `PROBLEMAS`, `$BASE/PLAN.md` y `$ENCARGO`. `$1` es el número de vuelta.
pedido_de_la_vuelta() {
  local vuelta="$1"
  # UN PROBLEMA POR VUELTA, Y ES ARITMÉTICA, NO ESTILO.
  #
  # Hasta el 2026-11-28 acá iba `$PROBLEMAS` entero. Medido ese día sobre clasificados, con
  # cinco rojos en el plan: tres tareas que cruzan capas hay que partirlas en tres cada una,
  # así que arreglar los cinco es ESCRIBIR 9 enunciados nuevos más dos contratos más la
  # tabla. Los enunciados de ese proyecto promedian 2472 caracteres, o sea ~690 tokens: nueve
  # son ~6200 tokens de SALIDA. Y el techo a 6,1 tok/s en 1200 s es 7320 tokens.
  #
  # O sea que la escritura sola se come el 85% del presupuesto y no queda nada para decidir.
  # No es un problema de prompt: es imposible, y por eso el protocolo de dos fases tampoco lo
  # salvó — esa corrida murió 1200 s en la fase de DECISIÓN sin llegar a emitir los
  # marcadores, y el total fueron 1764 s con cero archivos. Cuatro corridas, cero progreso.
  #
  # La lista en sí no era el problema: 2253 caracteres, 626 tokens. Pedirle cinco cosas sí.
  #
  # Y no se le dice cuántas quedan. El propio método tiene medido por qué: un dato
  # irrelevante en el enunciado le baja el acierto a un modelo chico de 54,7% a 20,7%
  # (Udgam Labs, citado en plantillas/TAREA.md). «Hay otros cuatro» no lo ayuda a arreglar
  # este, y compite por la atención con lo que sí.
  local uno
  uno="$(printf '%s\n' "$PROBLEMAS" | grep . | head -1)"
  local corregir="Leé $ENCARGO y el PLAN.md que ya existe. Arreglá EXACTAMENTE esto y nada más:
$uno
No rehagas el resto del plan. No toques las tareas que ya están bien."

  if [ "$vuelta" -eq 1 ] && [ -n "$INSTRUCCION" ]; then
    printf '%s' "Leé $ENCARGO y el PLAN.md que ya existe. $INSTRUCCION No rehagas el resto del plan ni toques las tareas que ya están."
  elif [ "$vuelta" -eq 1 ] && [ -s "$BASE/PLAN.md" ] && [ -n "$PROBLEMAS" ]; then
    # UN PLAN QUE YA EXISTE Y TIENE DEFECTOS SE CORRIGE, NO SE REHACE.
    #
    # Hasta el 2026-11-28 la vuelta 1 sin INSTRUCCION pedía siempre «escribí PLAN.md y un
    # archivo por tarea», y eso sobre un plan de 37 tareas con 19 cerradas es pedirle al
    # arquitecto que tire el trabajo hecho. Peor: `revisar` ya había corrido antes del bucle
    # y YA TENÍA la lista de defectos en la mano — el bucle la ignoraba justo en la única
    # vuelta donde servía y recién la mostraba en la vuelta 2, después de gastar una llamada
    # entera (1342s medidos en este agente) rehaciendo lo que no había que rehacer.
    #
    # Es el defecto que este repo persigue desde el principio: un dato declarado que nadie
    # cruzaba contra otro. Estaba calculado, y el que decidía no lo miraba.
    printf '%s' "$corregir"
  elif [ "$vuelta" -eq 1 ]; then
    printf '%s' "Leé $ENCARGO. Es el encargo. Escribí PLAN.md y un archivo por tarea en tareas/, siguiendo el método del repo ($AQUI/../METODO.md, $AQUI/../DESCOMPOSICION.md, plantillas en $AQUI/../plantillas/). Escribilos aunque te falte información: las decisiones que queden abiertas van en una sección 'Decisiones abiertas' DENTRO de PLAN.md."
  else
    printf '%s' "$corregir"
  fi
}

# Huella del estado antes de empezar. En modo INSTRUCCION hace falta: el plan ya validaba,
# así que los validadores dan verde igual si el arquitecto no hizo nada. Nos pasó: una
# corrida de 761s que razonó la tarea entera, no escribió un archivo, y G0 dijo VERDE.
ANTES="$(huella_del_plan)"
log="$BASE/.plan.log"
inicio=$(date +%s)
huella=""
vuelta=0
limpias=0
# `revisar` la llena, pero puede no haber corrido todavía (modo INSTRUCCION) y abajo se la
# lee para decidir el pedido de la vuelta 1. Sin esto, `set -u` mata el script.
PROBLEMAS=""

# Nunca mandar a refinar algo que ya pasa: medido, HumanEval cae de 96,3% a 66,5% cuando se
# refina código que ya era correcto. Si el plan existe y ya valida, no se toca.
YA_VALIDA=0
if [ -z "$INSTRUCCION" ] && [ -s "$BASE/PLAN.md" ]; then
  revisar
  if [ -z "$PROBLEMAS" ]; then
    echo "· el plan que ya existe valida: no se toca — refinar lo que pasa lo empeora"
    YA_VALIDA=1
  fi
fi

# EL PRESUPUESTO DE VUELTAS ESCALA CON LOS DEFECTOS.
#
# Desde que cada vuelta arregla UN problema, un default fijo de 3 vueltas sobre un plan con 5
# defectos no puede terminar nunca: arreglaría tres y saldría en rojo por los otros dos,
# culpando al arquitecto de un techo que le pusimos nosotros. Es el mismo reparto que el tope
# de reintentos de los tests, que ata a quien avanza.
if [ -z "$INTENTOS_EXPLICITO" ] && [ -n "$PROBLEMAS" ]; then
  n_defectos="$(printf '%s\n' "$PROBLEMAS" | grep -c . || true)"
  if [ "${n_defectos:-0}" -ge "$INTENTOS" ]; then
    INTENTOS=$((n_defectos + 1))
    echo "· $n_defectos defecto(s) en el plan y una vuelta arregla uno: presupuesto $INTENTOS vueltas"
  fi
fi

while [ "$YA_VALIDA" -eq 0 ] && [ "$vuelta" -lt "$INTENTOS" ]; do
  vuelta=$((vuelta+1))
  pedido="$(pedido_de_la_vuelta "$vuelta")"

  echo "── vuelta $vuelta/$INTENTOS · $AGENTE"
  # Byte donde empieza ESTA vuelta: el log se acumula entre vueltas y entre corridas, así
  # que sin la marca el diagnóstico de abajo leería deliberación de ayer.
  DESDE_BYTE="$(wc -c < "$log" 2>/dev/null | xargs || echo 0)"
  HUELLA_VUELTA="$(huella_del_plan)"
  # TECHO PROPIO. Hasta el 2026-11-26 esta era la ÚNICA invocación de agente del método sin
  # `con_limite`: `correr-tarea.sh` y `escribir-tests.sh` ya lo usaban. El arreglo vivía en
  # dos hermanos y no en el tercero, que es el patrón que este repo persigue.
  #
  # Qué pasaba sin techo: el arquitecto deliberaba hasta que el gateway cortaba el stream a
  # los 1200s y la corrida terminaba sin un archivo. Medido ese día, tres veces: 117s, 1342s
  # y 1290s —los dos largos son el muro del gateway más el preflight—. Y el veredicto que
  # salía era «el arquitecto no cambió ni el plan ni las tareas», que acusa al sujeto
  # equivocado: había decidido el plan entero.
  export LOG_VIGILADO="$log"
  ( cd "$BASE" || exit 1
    con_limite "${LIMITE_AGENTE:-1200}" opencode run --agent "$AGENTE" \
      "$pedido Tu única salida son archivos, escritos con la herramienta write: lo que no quedó en un archivo no existe. Antes de terminar verificá con read que cada archivo que dijiste escribir esté ahí. Tu respuesta final es la lista de archivos que escribiste." 2>&1
    # 142 = SIGALRM. Se deja escrito con la forma que `error_del_agente` reconoce, para que
    # el bucle corte con el motivo real en vez de dar otra vuelta contra el mismo muro.
    [ "$?" = "142" ] && echo "Error: el agente no respondió: $(motivo_del_corte "$log")"
  ) >> "$log" 2>&1

  # EL TRAMO DE ESTA VUELTA, no el log entero. `.plan.log` se acumula entre vueltas y entre
  # corridas —208 KB el 2026-11-28, con errores de días anteriores adentro— y
  # `error_del_agente` devuelve el PRIMER error que encuentra. O sea que sin recortar, la
  # vuelta 1 podía cortar acusando un error de anteayer. El detector de rumiado ya recortaba
  # por `DESDE_BYTE` desde el 2026-11-26 y este hermano no: el mismo arreglo en uno y no en
  # el otro, que es el patrón que este repo persigue.
  tail -c "+$((DESDE_BYTE + 1))" "$log" > "$BASE/.plan-vuelta.log" 2>/dev/null || true
  err="$(error_del_agente "$BASE/.plan-vuelta.log")"

  # DELIBERÓ Y NO ESCRIBIÓ: se pregunta ANTES de decidir qué hacer con el error, y el orden
  # es el arreglo.
  #
  # Hasta el 2026-11-28 el corte por techo rompía la vuelta tres líneas más arriba, así que
  # `dos_fases` —construido exactamente para «deliberó 1200s y no escribió un archivo»— era
  # INALCANZABLE en el único caso que lo motiva: el techo es la forma normal en que ese caso
  # termina. Medido ese día sobre clasificados: el arquitecto recibió los cinco rojos, habló
  # 1204s, no escribió nada, y el guardia que tenía que partirle el pedido no corrió. Un
  # guardia incapaz de disparar se lee igual que un guardia que no encontró nada.
  #
  # El discriminante no es el error: es si habló y no escribió. Un corte con 20 bytes de
  # salida es la plataforma —`hablo_sin_escribir` exige 500— y ése sí termina la vuelta.
  if hablo_sin_escribir "$HUELLA_VUELTA" "$DESDE_BYTE"; then
    dos_fases "$pedido"
    # Y si partido TAMPOCO escribió, otra vuelta es otro muro igual: no hay forma de pedirlo
    # que no hayamos probado ya en esta misma vuelta.
    if [ "$(huella_del_plan)" = "$HUELLA_VUELTA" ]; then
      echo "  ✗ partido en dos y tampoco escribió${err:+ · último error: $err}"
      break
    fi
  elif [ -n "$err" ]; then
    echo "  ✗ el agente cortó por un error: $err"; break
  fi

  revisar
  if [ -z "$PROBLEMAS" ]; then
    # Dos pasadas limpias, no una. Pero la segunda es una REVALIDACIÓN, no otra vuelta del
    # arquitecto: volver a refinar algo que ya pasa lo empeora (medido: 96,3% → 66,5%).
    # Lo que se confirma es que el veredicto del validador es estable, no el plan.
    revisar >/dev/null
    if [ -z "$PROBLEMAS" ]; then break; fi
    echo "  · la primera pasada dio limpio y la segunda no: el validador no es estable"
  fi

  if [ "$PROBLEMAS" = "$huella" ]; then
    echo "  ✗ punto muerto: falló dos veces por lo mismo. Decide un humano (HUMANO.md §4)."
    break
  fi
  huella="$PROBLEMAS"
done

duracion=$(( $(date +%s) - inicio ))

# Sin cambios no hay trabajo hecho, y los validadores no lo ven porque miran la forma del
# plan y no si se hizo lo que se pidió.
DESPUES="$(huella_del_plan)"
if [ "$ANTES" = "$DESPUES" ] && [ "$YA_VALIDA" -eq 0 ]; then
  echo
  echo "✗ G0 ROJO en ${duracion}s: el arquitecto no cambió ni el plan ni las tareas."
  # NO SE AFIRMA LO QUE NO SE MIRÓ. Esta línea decía fija «los validadores dan verde porque
  # el plan ya estaba bien», y el 2026-11-28 la imprimió sobre una corrida donde los
  # validadores habían dado CINCO rojos. Un veredicto que afirma algo falso sobre su propio
  # chequeo manda a buscar el problema donde no está: el que lo lee concluye que el plan está
  # bien y el agente no quiso trabajar.
  if [ -n "$PROBLEMAS" ]; then
    echo "  Y los validadores SIGUEN en rojo: $(printf '%s\n' "$PROBLEMAS" | grep -c .) problema(s) sin resolver."
  else
    echo "  Los validadores dan verde porque el plan ya estaba bien, pero no se hizo lo pedido."
  fi
  # QUÉ hizo, en vez de sólo qué no hizo. «No cambió nada» es verdad y acusa al sujeto
  # equivocado: medido el 2026-11-26, dos corridas decidieron el plan completo —qué tareas,
  # sus dependencias, sus archivos, hasta cómo mockear los servicios en los tests— y
  # murieron sin transcribirlo. Un rojo que no distingue «no trabajó» de «deliberó y no
  # escribió» manda a cambiar el modelo cuando lo que hay que cambiar es el pedido.
  if hablo_sin_escribir "${HUELLA_VUELTA:-}" "${DESDE_BYTE:-0}"; then
    {
      echo "  Pero SÍ trabajó: produjo $(cuanto_hablo) de salida sin cambiar un archivo."
      echo "  Eso no es un modelo que no puede, es un pedido que no entra en el reloj: a"
      echo "  ${TOK_S_PISO:-6.1} tok/s, ${LIMITE_AGENTE:-1200}s no alcanzan para decidir Y escribir en la misma"
      echo "  llamada. Partilo: una corrida que decida y conteste en pocas líneas, y otra que"
      echo "  reciba esa decisión y sólo la escriba. Medido: partido, escribió los dos"
      echo "  enunciados; junto, murió deliberando dos veces."
      echo "  El arnés ya lo intenta solo: si pasó igual, mirá $log — puede que la fase de"
      echo "  decisión no haya devuelto nada entre los marcadores."
    }
  fi
  echo "  Mirá $log: si el razonamiento está correcto y no hay llamadas a write, el problema"
  echo "  es del servidor y no del modelo (ver OPENCODE.md §8)."
  exit 1
fi

echo
if [ -n "${PROBLEMAS:-}" ]; then
  echo "G0 ROJO en ${duracion}s, después de $vuelta vuelta(s) — revisá $log"
  exit 1
fi

echo "G0: el plan está escrito y valida, en ${duracion}s y $vuelta vuelta(s). NO está aprobado."
echo
echo "Lo que queda es lo único que no se automatiza (HUMANO.md §1):"
echo "  · ¿Las decisiones abiertas del plan están cerradas? Cerralas vos: no hay respuesta correcta."
echo "  · ¿Las tareas están dimensionadas? (cuántas funciones tiene que escribir, no archivos)"
echo "  · ¿Inventó APIs que no existen?"
echo "  · Firmá la línea «Estado del gate G0»."
echo
echo "La forma del plan, la cobertura del encargo y el corte en etapas ya se verificaron."
echo "Después:  bash $AQUI/correr-plan.sh"
