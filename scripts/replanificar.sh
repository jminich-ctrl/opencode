#!/usr/bin/env bash
# Cuando una tarea falla por cómo está ESCRITA, la replanifica el arquitecto — no vos.
#
#   bash $AGENTES/scripts/replanificar.sh T04
#   bash $AGENTES/scripts/replanificar.sh T04 T26
#
# Por qué existe: el método decía «se repiensa la tarea» y paraba esperando a una persona.
# Esa persona terminaba reescribiendo el enunciado hasta que el agente pudiera, y entonces
# el número de autonomía no mide el método: mide cuánto lo empujaron. El método tiene un
# agente `arquitecto` para planificar y no tenía ningún camino que lo usara.
#
# Las tres cosas que NO puede hacer el arquitecto, y que este script verifica:
#   1. Cambiar el archivo de test o su clase: los declara el plan y los lee todo el mundo.
#   2. Achicar los criterios de terminado. Replanificar no es bajar la vara.
#   3. Dejar el plan sin validar. El juez es `validar-plan.py`, un comando, igual que
#      siempre (P2): si no valida, el cambio se descarta entero.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
cargar_entorno_colabhive

# El tope de salida del arquitecto tiene que entrar en el tiempo que le damos. Un chequeo y
# no un comentario: el 2026-11-21 el arquitecto se cortaba a mitad del razonamiento con el
# tope en 4096, y subirlo sin tocar el límite habría movido la falla de «cortado por tokens»
# a «matado por el reloj» — diagnóstico nuevo, mismo resultado. Ver `presupuesto_coherente`.
presupuesto_coherente "${AGENTE_REPLAN:-arquitecto}" "${LIMITE_AGENTE:-3600}" || {
  echo "✗ no arranco con el presupuesto en contradicción: lo que saldría de acá sería una" >&2
  echo "  medición de nuestro reloj, no del arquitecto." >&2
  exit 1
}
[ $# -ge 1 ] || { echo "uso: $0 TNN [TNN ...]" >&2; exit 1; }

for id in "$@"; do
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  [ -n "$archivo" ] || { echo "✗ $id: no existe tareas/${id}-*.md" >&2; continue; }

  # El motivo real, de los transcripts conservados. Sin esto el arquitecto replanifica a
  # ciegas, que es el mismo error que cometíamos con los reintentos.
  FALLIDOS="$RAIZ/../fallidos-$id"
  # SÓLO el último transcript, y SÓLO de la fase que falló. La primera versión juntaba
  # todos los ✗ de todos los logs conservados, incluidos los de hace horas y los que ya no
  # aplicaban: el arquitecto se enganchó con un «ruta absoluta clavada» obsoleto y derivó
  # a una conclusión falsa. Es el mismo defecto que le encontré al gate —la categoría en
  # vez del dato— cometido en el script que escribí para arreglarlo.
  ULTIMO="$(ls -t "$FALLIDOS"/*.log 2>/dev/null | head -1)"
  TEST_TAREA="$(sed -n 's/.*Archivo: `\([^`]*\)`.*/\1/p' "$archivo" 2>/dev/null | head -1)"
  # Y en qué fase se cayó, porque el estado del mundo es distinto en cada una: si falló la
  # escritura del test, el archivo de test NO existe — y el enunciado dice que sí. Sin
  # decirlo, el arquitecto lo lee como un hueco del plan, que es lo que pasó con T04 y T26.
  if [ -n "$TEST_TAREA" ] && [ ! -f "$BASE/$TEST_TAREA" ]; then
    FASE="Falló la fase que ESCRIBE los tests, así que '$TEST_TAREA' todavía NO existe —el
enunciado dice que ya está en el repo porque está escrito para la fase siguiente, ignorá
esa frase—. Tu trabajo es que esa tarea se pueda ESCRIBIR como test."
  else
    FASE="El test '$TEST_TAREA' existe y falló la IMPLEMENTACIÓN contra él."
  fi
  # EL ERROR CONCRETO PRIMERO, la categoría sólo si no hay nada mejor.
  #
  # Este extractor buscaba `✗|por qué falla` y nada más. El 2026-10-23 el único `✗` del
  # transcript de T28 era la línea genérica «✗ la suite está en rojo», así que el arquitecto
  # recibió eso —una categoría— sobre una tarea cuyo test todavía no existe, y no cambió
  # nada: con esa información no hay nada que arreglar. Ocho minutos de agente para nada.
  #
  # El dato estaba en el mismo archivo, en la línea 137:
  #   E  AssertionError: Expected 'execute' to be called once. Called 0 times.
  #
  # Es LA MISMA lección que este script ya tiene escrita doce líneas más arriba —«es el
  # mismo defecto que le encontré al gate: la categoría en vez del dato»— y volvió porque el
  # arreglo anterior acotó CUÁNTO se pasaba (un transcript, la fase que falló) y no QUÉ. El
  # patrón de búsqueda es el que el gate ya usa para su «por qué falla».
  CONCRETO="$(sed 's/\x1b\[[0-9;]*m//g' "${ULTIMO:-/dev/null}" 2>/dev/null \
    | grep -E '^E +|(Import|Module|Attribute|Type|Name|Assertion|Value)Error|^ *>? *assert ' \
    | sed 's/^ *//' | sort -u | head -6)"
  GENERICO="$( { sed 's/\x1b\[[0-9;]*m//g' "${ULTIMO:-/dev/null}" 2>/dev/null \
                 | grep -E '✗|por qué falla' | head -6
               sed 's/\x1b\[[0-9;]*m//g' "$RAIZ/../tests-$id/.tests.log" 2>/dev/null \
                 | grep -E '^  ✗' | head -4; } | sort -u)"
  # EL VEREDICTO DEL ARNÉS PRIMERO, antes que cualquier grep del transcript.
  #
  # Todo lo de arriba lee lo que el AGENTE imprimió. El 2026-11-10, en los cuatro rechazos de
  # la etapa 1 de clasificados, eso daba «✗ la suite está en rojo» —una categoría— mientras el
  # motivo real del arnés era «el test parchea un lugar donde el patch no va a tener efecto»,
  # con la ruta exacta que había que poner. El arquitecto recibió la categoría y no cambió
  # nada. Es la tercera vez que este script replanifica con el dato equivocado, y las dos
  # anteriores se arreglaron acotando el grep en vez de cambiar la FUENTE.
  #
  # `escribir-tests.sh` ahora escribe su veredicto en `fallidos-<id>/veredicto-*.txt`
  # (`conservar_veredicto` en _comun.sh). Si está, manda; el grep queda de respaldo para los
  # fallidos viejos, que no lo tienen.
  VEREDICTO="$(cat "$(ls -t "$FALLIDOS"/veredicto-*.txt 2>/dev/null | head -1)" 2>/dev/null \
    | sed 's/\x1b\[[0-9;]*m//g' | grep . | head -14)"
  LO_QUE_FALLO="$(printf '%s\n%s\n%s\n' "$VEREDICTO" "$CONCRETO" "$GENERICO" | grep . | tr '\n' ' ' | cut -c1-600)"
  [ -n "$VEREDICTO" ] || echo "     ⊘ sin veredicto del arnés para $id: el motivo sale de grepear el transcript del agente, que da la categoría y no el dato. Lo tendrá en la próxima corrida."
  MOTIVO="$FASE  Lo que falló: $LO_QUE_FALLO"
  # La guarda mira LO QUE FALLÓ, no la oración armada. Miraba `$MOTIVO`, que arranca con
  # `$FASE` y por lo tanto NUNCA está vacío: no podía dispararse jamás. El script replanificaba
  # con «Lo que falló:» y nada detrás, o sea adivinando, que es exactamente lo que su propio
  # mensaje dice que no hay que hacer. Y el arquitecto que recibe un motivo vacío no se queda
  # quieto: inventa una causa, que es cómo T05c acumuló tres replanificaciones.
  #
  # Cuarta guarda que encuentro incapaz de dispararse —las otras tres estaban detrás de una
  # tubería que ya había consumido el estado— y la cuarta vez que el defecto es el mismo: el
  # chequeo mira una variable derivada en vez del dato.
  if [ -z "$LO_QUE_FALLO" ]; then
    echo "✗ $id: no hay transcripts de fallo en $FALLIDOS ni en ../tests-$id."
    echo "   Replanificar sin el motivo es adivinar: el arquitecto va a inventar una causa."
    echo "   Corré la tarea primero."
    continue
  fi

  # EL TOPE DE RONDAS. Va acá: después de la guarda que puede abortar gratis y ANTES de la
  # sonda, que cuesta un pedido. Es la regla de orden que este script ya tiene escrita.
  #
  # Si el enunciado se reescribió TOPE_REPLAN veces y la tarea sigue sin pasar, el defecto
  # dejó de ser del enunciado. Reescribirlo una cuarta vez es gastar un agente en la hipótesis
  # que ya se refutó tres veces, y el método tiene medido que el arquitecto no se queda
  # quieto: inventa una causa. Así acumuló T05c sus tres replanificaciones.
  RONDAS="$(replanificaciones_de "$id")"
  if [ "${RONDAS:-0}" -ge "$TOPE_REPLAN" ]; then
    echo "⃠ $id: $RONDAS reescrituras del enunciado y sigue sin pasar."
    echo "   A esta altura el defecto NO es del enunciado: es del PLAN. Las rondas:"
    motivos_de_replanificacion "$id"
    echo "   Lo decide una persona, igual que un HUECO: o el plan parte la tarea, o entrega"
    echo "   lo que le falta, o la tarea no es la que el plan creía. Para el caso de"
    echo "   incoherencias entre tareas está \`replanificar-coherencia.sh\`."
    echo "   Si igual querés otra ronda: TOPE_REPLAN=$((RONDAS + 1)) bash \$AGENTES/scripts/replanificar.sh $id"
    continue
  fi

  # Acá, y no antes del bucle: la sonda cuesta un pedido a la plataforma y no tiene sentido
  # gastarlo si la guarda de arriba —«no hay transcripts de fallo»— iba a frenar igual. Es la
  # misma regla de orden que el método ya tiene para el vigilante: lo caro va después de lo
  # que puede abortar gratis. Mi primera versión la puso antes del bucle y rompió dos tests
  # que miden exactamente esa guarda.
  #
  # Una sola vez, aunque se pidan varias tareas. Esta sonda se escribió por el incidente del
  # 27B tres horas caído con el ejecutor en 200 —la corrida murió «en la primera
  # replanificación», informando que falló la tarea— y estaba cableada sólo en
  # `correr-todo.sh`. Replanificar ES el papel del 27B: acá su caída se paga más caro.
  if [ "${SONDA_HECHA:-0}" = "0" ] && command -v opencode >/dev/null 2>&1; then
    SONDA_HECHA=1
    if ! MODELO_SONDA="${MODELO:-$(modelo_del_agente arquitecto)}" plataforma_responde; then
      echo "✗ no se replanifica: el modelo del arquitecto no responde." >&2
      echo "  No es la tarea ni el enunciado. Esperá que la réplica vuelva y reintentá." >&2
      exit 1
    fi
  fi

  # Lo que no se toca, para poder verificarlo después.
  CRIT_ANTES="$(grep -c '^- \[ \]' "$archivo" || true)"
  TEST_ANTES="$(grep -oE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`.*clase `[A-Za-z0-9_]+`' "$archivo" | head -1)"
  cp "$archivo" "$archivo.previo"

  # EL BRIEF, y no PLAN.md. Medido el 2026-11-22 replanificando T16: el prompt decía «Leé la
  # tarea, leé PLAN.md», PLAN.md son 12.523 bytes de los que 8.025 son dos secciones que el
  # arquitecto no usa, y el arquitecto hizo TRECE lecturas para juntar a mano lo que
  # necesitaba —la tarea, el plan, cuatro fuentes, las tareas T14 y T15, dos tests—. Llegó al
  # diagnóstico correcto a los 23.692 bytes de deliberación y el pedido se cortó antes de que
  # llamara a `write`.
  #
  # El brief trae la tarea, el `## Contrato` de cada dependencia declarada y los invariantes
  # del plan: para T16 son 5.984 bytes y el hueco queda a la vista en UNA lectura —su
  # contrato pide una lista de objetos con `id, ad_id, favorited, status` y T15, su
  # dependencia, entrega sólo `toggle_favorite_service`—. La idea es de superpowers (MIT):
  # «Never make a subagent read the whole plan file».
  BRIEF="$BASE/.brief-$id.md"
  if ! python3 "$AQUI/brief_tarea.py" "$archivo" --destino "$BRIEF" >/dev/null 2>&1; then
    # Y si no se pudo armar, se DICE y se vuelve al plan entero. Un respaldo callado es el
    # defecto que este repo tiene escrito nueve veces: el que lee no puede distinguir «el
    # brief no traía eso» de «no hubo brief».
    echo "     ⊘ no pude armar el brief de $id: el prompt va con PLAN.md entero, que es"
    echo "        lo que hizo que el arquitecto gastara el pedido leyendo. No es un pase."
    BRIEF=""
  fi
  if [ -n "$BRIEF" ]; then
    QUE_LEER="Leé el brief $BRIEF: trae la tarea completa, el contrato de cada tarea de la que ésta depende, los invariantes del plan, y —verificado contra el disco— qué archivos existen hoy, qué define cada uno y el nombre EXACTO de cada archivo de tarea. NO leas PLAN.md ni los archivos de tarea de tus dependencias: lo que te sirve de ahí ya está en el brief, y lo que no está en el brief es porque no está. NO ADIVINES NINGÚN PATH: si no figura en el brief, no existe. Medido el 2026-11-23: el arquitecto de T16 adivinó dos veces un nombre de archivo, falló las dos, y a 5,9 tok/s cada adivinanza es un viaje que se le descuenta del reloj."
  else
    QUE_LEER="Leé la tarea y PLAN.md."
  fi

  echo "▶ $id · el arquitecto replanifica"
  echo "$MOTIVO" | sed 's/^/     /'

  export LOG_VIGILADO="$BASE/.replan-$id.log"
  # El arquitecto corre sobre el proyecto REAL, no sobre un worktree. Acá sí tiene que
  # escribir —el archivo de tarea es su entregable— y nada más que eso.
  # Ver `revisar_escrituras_de_mas` en _comun.sh.
  FOTO="$BASE/.replan-$id-antes.log"; foto_proyecto "$FOTO"
  (
    cd "$BASE" || exit 1
    export XDG_DATA_HOME="$BASE/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    # MODELO= permite comparar candidatos en el papel de arquitecto sin tocar la config.
    # Hace falta: el perfil del planificador —mucha deliberación, pocas herramientas— no se
    # puede evaluar con un banco de seis preguntas, y la única prueba real es si replanifica
    # una tarea que falló de verdad.
    # `--agent` SIEMPRE, y `--model` encima cuando se pide un candidato. Antes era un
    # `if/else`: con `MODELO=` puesto se caía `--agent arquitecto` y opencode corría con su
    # agente por omisión, `build`, cuyo prompt de sistema dice textual «Escribí primero,
    # deliberá después. No razones en la respuesta: usá las herramientas».
    #
    # O sea que la variable que existe para «comparar candidatos en el papel de arquitecto
    # sin tocar la config» cambiaba el PAPEL además del modelo, y de paso el tope de salida,
    # las herramientas, la temperatura, los `steps` y el bloque de permisos. El 2026-11-22
    # eso convirtió un experimento de una variable en uno de cuatro, y la cuarta era un
    # prompt que ORDENA la conducta que el experimento estaba midiendo: conclusión inválida.
    COMO=(--agent "${AGENTE_REPLAN:-arquitecto}")
    [ -n "${MODELO:-}" ] && COMO+=(--model "colabhive/$MODELO")
    con_limite "${LIMITE_AGENTE:-3600}" opencode run "${COMO[@]}" \
      "Mirá SOLO el brief de la tarea y, si hace falta, los archivos que la tarea nombra. NO explores .venv, node_modules, .git ni ningún directorio de dependencias: no tienen nada que ver con el enunciado y hay decenas de miles de archivos ahí. La tarea tareas/$(basename \"$archivo\") falló al ejecutarse, y el motivo es cómo está escrita, no el agente que la intentó. Esto es lo que falló: $MOTIVO. $QUE_LEER Reescribí SOLO el archivo de tarea con la herramienta write para que el defecto no pueda repetirse. Reglas que no podés romper: (1) no cambies el archivo de test ni el nombre de su clase, los declara el plan; (2) no saques ni ablandes ningún criterio de terminado — si hace falta, agregá; (3) si el problema es que la tarea necesita algo que ninguna tarea del plan entrega, decilo con la palabra HUECO y explicá qué falta, en vez de inventarlo. Lo que la tarea NO puede tocar va en el campo «Prohibido tocar», no en prosa, y NO expliques cómo hacer lo que prohibís: medido, el ejecutor hace lo que la receta dice aunque dos líneas antes diga que no le corresponde. Nombrar un archivo ajeno está bien para decir DÓNDE VIVE algo que la tarea importa, y mal si viene con instrucciones de cómo modificarlo. Lo más útil que podés hacer es decir DÓNDE vive cada cosa que la tarea nombra: archivo exacto, import exacto." 2>&1
  ) > "$LOG_VIGILADO" 2>&1
  RC=$?

  if [ "$RC" = 142 ]; then
    echo "  ✗ el arquitecto no respondió: $(motivo_del_corte "$LOG_VIGILADO")"
    mv "$archivo.previo" "$archivo"; continue
  fi
  # Sin `|| true`: la guarda devuelve 1 cuando el arquitecto escribió fuera de su alcance, y
  # el `|| true` lo descartaba. Una corrida podía imprimir «✗ escribió en el tronco 2
  # archivo/s y tenía PROHIBIDO escribir» y DESPUÉS «✓ replanificada»: el veredicto que el
  # operador lee es el último.
  revisar_escrituras_de_mas "$FOTO" "$id" "el arquitecto" \
    "tareas/$(basename "$archivo")\$" || FUERA_DE_ALCANCE=1
  # El patrón acepta marcas de markdown INTERCALADAS, y también la lista numerada. El
  # 2026-10-24 el diagnóstico de T05c dijo «- **HUECO**: No existe función para listar todos
  # los anuncios» y el regex viejo —`[*#>-]*` UNA sola vez antes de los espacios— no
  # matcheaba «- **HUECO»: guión, espacio, asteriscos. El hueco del plan se perdió, el relevo
  # siguió al paso 2 y gastó otro agente de 16 minutos en una tarea que requería una decisión
  # de producto. Mismo defecto de extractor frágil que el `grep '→'` de mutar.py y el motivo
  # que era una categoría.
  #
  # Las dos apariciones llevan el MISMO patrón. En `replanificar.sh` arreglé el `grep -q` que
  # detecta y dejé el `grep -A3` que imprime con el viejo: el aviso se disparaba y no mostraba
  # el hueco. Un arreglo a medias dentro del mismo `if`, que es la forma que este repo repite.
  if grep -qE '^[0-9.)[:space:]*#>_-]*HUECO' "$LOG_VIGILADO" 2>/dev/null; then
    echo "  ⃠ el arquitecto dice que falta algo que ninguna tarea entrega:"
    grep -A3 -E '^[0-9.)[:space:]*#>_-]*HUECO' "$LOG_VIGILADO" | head -6 | sed 's/^/     /'
    echo "     Eso lo decide una persona: es un hueco del plan, no de la tarea."
    # Cuenta como ronda, y no es un castigo al arquitecto: un hueco declarado y NO resuelto
    # es justamente el caso en que seguir reescribiendo el enunciado no puede servir.
    anotar_replanificacion "$id" "$LO_QUE_FALLO" hueco
    mv "$archivo.previo" "$archivo"; continue
  fi

  # ── Los tres chequeos. Cualquiera que falle descarta el cambio entero.
  # ANTES del no-op: ¿falló la herramienta o la plataforma? Un stream cortado a mitad deja
  # el archivo intacto, y sin este chequeo se informa «el arquitecto no cambió nada» —que
  # acusa al modelo de no querer escribir cuando lo mataron mientras trabajaba—. Pasó con
  # el 32B: leyó la tarea, leyó el plan, y lo cortó un «upstream stream ended».
  ERR_PLAT="$(error_del_agente "$LOG_VIGILADO" 2>/dev/null)"
  if [ -n "$ERR_PLAT" ]; then
    echo "  ✗ no se pudo replanificar: $ERR_PLAT"
    echo "     Es de la plataforma o la herramienta, no del arquitecto. Reintentá."
    mv "$archivo.previo" "$archivo"
    continue
  fi

  mal=""
  # La guarda de escrituras corre más arriba, antes de este `mal=""`, así que su resultado
  # viaja en una bandera: asignarle `mal` allá lo borraba acá. Es el defecto que esta línea
  # produce por existir, y por eso la bandera se limpia al final de cada tarea.
  [ "${FUERA_DE_ALCANCE:-0}" = "1" ] && mal="escribió fuera de su alcance"
  FUERA_DE_ALCANCE=0
  # ¿cambió algo? Los tres chequeos de abajo pasan trivialmente sobre un
  # archivo intacto, así que sin esto el script informa «replanificada» cuando el arquitecto
  # leyó, razonó y no escribió. Pasó con T04 y T26: cero líneas de diff, dos verdes.
  # Un chequeo que no puede fallar no es un chequeo — y éste estaba en el script escrito
  # para arreglar el método.
  if cmp -s "$archivo" "$archivo.previo"; then
    echo "  ✗ el arquitecto no cambió nada: leyó la tarea y no la reescribió."
    echo "     No es una replanificación fallida, es una que no ocurrió. Log: $LOG_VIGILADO"
    anotar_replanificacion "$id" "$LO_QUE_FALLO" "sin-cambios"
    mv "$archivo.previo" "$archivo"
    continue
  fi
  # UNA TAREA, UN DOCUMENTO. El enunciado tiene que seguir siendo UN enunciado.
  #
  # El 2026-10-23 el relevo "replanificó" T28 agregando una versión nueva COMPLETA al final
  # en vez de reemplazar la vieja: el archivo pasó de 59 a 96 líneas con dos `# T28`, dos
  # `**Estado:**` y dos `## Tests`. Y los cuatro jueces lo aprobaron —validar-plan.py dijo
  # que el plan validaba, los criterios habían AUMENTADO y la declaración de test duplicada
  # coincidía con la original—, porque todos miran propiedades del contenido y ninguno
  # pregunta si el documento sigue siendo uno.
  #
  # Es el mismo agujero que un bullet comido unas horas antes, en escala mayor: 37 líneas
  # duplicadas en vez de un guion de menos. Lo que faltaba no era otro chequeo de contenido
  # sino uno de INTEGRIDAD.
  for enc in '^# T[0-9]' '^\*\*Estado:' '^## Tests'; do
    n="$(grep -c "$enc" "$archivo" || true)"
    # Sin «» alrededor de la variable: el patrón lleva `[`, `*` y `#`, y pegado a un
    # multibyte el mensaje sale cortado («duplicado: 2 veces «?»). Es el mismo defecto de
    # portabilidad que TestPortabilidadBash32 vigila y que ya cometí hoy con «$tid».
    [ "${n:-0}" -le 1 ] || mal="${mal:+$mal; }el enunciado quedó duplicado: $n veces el patron $enc"
  done
  CRIT_DESPUES="$(grep -c '^- \[ \]' "$archivo" || true)"
  [ "${CRIT_DESPUES:-0}" -lt "${CRIT_ANTES:-0}" ] \
    && mal="${mal:+$mal; }achicó los criterios de terminado: de $CRIT_ANTES a $CRIT_DESPUES"
  TEST_DESPUES="$(grep -oE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`.*clase `[A-Za-z0-9_]+`' "$archivo" | head -1)"
  [ -n "$TEST_ANTES" ] && [ "$TEST_ANTES" != "$TEST_DESPUES" ] \
    && mal="${mal:+$mal; }cambió el archivo o la clase de test, que los declara el plan"
  # Lo que la reescritura NO puede llevarse. El juez de esto era contar viñetas `- [ ]` de
  # todo el archivo, y un replay midió el agujero: de 15 reescrituras mutantes, 11 salían ✓.
  # El baseline es HEAD y no el `.previo`: comparar contra el árbol de trabajo deja que dos
  # pasadas sin commitear degraden el enunciado al hueso, con las dos diciendo ✓.
  if git -C "$BASE" show "HEAD:./tareas/$(basename "$archivo")" > "$BASE/.head-tarea.md" 2>/dev/null; then
    if ! SALIDA_PRES="$(python3 "$AQUI/preservar_criterios.py" "$BASE/.head-tarea.md" "$archivo" 2>&1)"; then
      printf '%s\n' "$SALIDA_PRES"
      mal="${mal:+$mal; }se llevó criterios o directivas que no podía llevarse"
    fi
    rm -f "$BASE/.head-tarea.md"
  else
    echo "     ⊘ la tarea no está en HEAD: no pude comparar qué se perdió. NO es un pase."
    mal="${mal:+$mal; }no pude verificar qué se perdió (la tarea no está commiteada)"
  fi
  # Y la coherencia ENTRE tareas, que es el juez que atrapó el daño real del 2026-11-22 —un
  # import cruzado T26→T04 que la reescritura inventó— y que este camino no corría, mientras
  # su hermano `replanificar-coherencia.sh` sí. El arreglo vivía en un hermano, otra vez.
  # Desde la RAÍZ con PROYECTO, que es como `correr-todo.sh` lo corre. Corriéndolo desde
  # `$BASE` devuelve 2 —«no pude»— y un 2 leído como rojo acusa al arquitecto de algo que no
  # se midió; leído como pase, deja pasar la contradicción. Ninguna de las dos sirve.
  if ! SALIDA_COH="$(cd "$RAIZ" && PROYECTO="$(basename "$BASE")" python3 "$AQUI/coherencia.py" 2>&1)"; then
    printf '%s\n' "$SALIDA_COH" | grep '✗' | head -3
    mal="${mal:+$mal; }el plan se contradice entre tareas"
  fi
  # La salida de `validar-plan.py` se IMPRIME: iba a /dev/null y con ella se perdían sus
  # avisos. Hoy mismo uno decía «T26 no nombra su archivo de test: el agente no sabe dónde
  # está» y nadie lo vio, porque el consumidor sólo leía el código de salida.
  if ! (cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" 2>&1 | grep -E '✗|aviso' | head -6; exit "${PIPESTATUS[0]}"); then
    mal="${mal:+$mal; }el plan dejó de validar"
  fi

  if [ -n "$mal" ]; then
    echo "  ✗ se descarta la replanificación: $mal"
    # La ronda se gastó igual: lo que el tope cuenta son rondas, no éxitos.
    anotar_replanificacion "$id" "$LO_QUE_FALLO" descartada
    mv "$archivo.previo" "$archivo"
  else
    anotar_replanificacion "$id" "$LO_QUE_FALLO" reescrita
    echo "  ✓ $id replanificada y el plan sigue validando"
    diff -u "$archivo.previo" "$archivo" | grep -E '^[+-][^+-]' | head -12 | sed 's/^/     /'
    rm -f "$archivo.previo"
  fi
done

echo
echo "Lo replanificado NO está commiteado. Miralo y commiteá, o descartalo:"
echo "  git -C $RAIZ diff -- $PROYECTO/tareas"
