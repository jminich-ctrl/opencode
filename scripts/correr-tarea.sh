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
cargar_entorno_colabhive
[ $# -gt 0 ] || { echo "uso: $0 T01 [T02 ...]" >&2; exit 1; }
[ $# -gt "$PARALELAS" ] && echo "· $# tareas, de a $PARALELAS por vez"

lanzar() {
  local id="$1"
  local archivo
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  [ -n "$archivo" ] || { echo "✗ $id: no existe tareas/${id}-*.md"; return 1; }
  # Absoluta DENTRO DEL WORKTREE, que es la única de las tres formas que anda:
  #   · absoluta del repo ORIGINAL -> OpenCode la ve como `external_directory` y la rechaza
  #     por permisos (es lo que decía el comentario que estaba acá, y es cierto);
  #   · relativa (`tareas/X.md`)   -> OpenCode la resuelve contra la RAÍZ DEL WORKTREE y no
  #     contra el `cd` del bloque que lanza al agente, y ahí no hay `tareas/`: el proyecto
  #     vive en `$wt/$PROYECTO`. Mató un intento de T05a el 2026-10-21 con «File not found»
  #     sobre `/Users/jose/tests-T05a/tareas/T05a-avisos-datos.md`, con el archivo presente
  #     en `/Users/jose/tests-T05a/ejemplo-clasificados/tareas/`.
  #   · absoluta del worktree      -> se lee. Lo prueba ese mismo log: falló con «File not
  #     found», no con un rechazo de permisos.
  # Se arma abajo, cuando `$wt` ya existe.
  local nombre_tarea
  nombre_tarea="$(basename "$archivo")"

  # El worktree se crea desde HEAD: los cambios sin commitear (al gate, por ejemplo)
  # NO viajan. Commiteá antes de lanzar.
  local wt="$RAIZ/../trabajo-$id"
  archivo="$wt/$PROYECTO/tareas/$nombre_tarea"
  # El transcript del intento anterior, ANTES de borrar el worktree. Es el único lugar
  # donde está escrito por qué falló. Lo agregué primero a escribir-tests.sh y no acá, y
  # volví a perder un log en este camino: arreglar un lado y no el otro es el patrón que
  # este repo repite.
  # Transcript Y PARCHE. Guardaba sólo el transcript, y el código del intento se iba con el
  # worktree: de un intento que el gate reprobó no quedaba nada ejecutable.
  conservar_intento "$wt" "${id:-${TAREA:-tarea}}"
  # La base ANTES del `rm -rf`: `tirar_base_del_worktree` lee el `.entorno` del worktree para
  # saber cómo se llama la base, y el `rm -rf` se lo lleva. Es el mismo defecto que tenía
  # `escribir-tests.sh`, y el comentario de arriba lo anticipaba: «arreglar un lado y no el
  # otro es el patrón que este repo repite». Lo arreglé de un lado y no del otro el
  # 2026-10-25, y lo cantó el aviso nuevo en su primera corrida real —T15— porque la función
  # dejó de callarse cuando no puede saber qué tirar.
  tirar_base_del_worktree "$wt"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "tarea/$id" 2>/dev/null
  # El worktree sale del árbol COMMITEADO. Un arreglo del contrato o del test que esté sin
  # commitear NO llega al agente, y no se entera nadie: el agente trabaja contra la versión
  # vieja, el gate lo juzga contra la vieja, y el rojo que sale no habla de lo que arreglaste.
  #
  # Pasó con T04: reescribí su contrato y su test —tres contradicciones, una de ellas un test
  # que sólo pasaba con un hash falso— y el agente implementó exactamente el contrato viejo,
  # con razón, porque es el que vio. Una corrida entera por una declaración que el lector no
  # recibe, que es la forma de falla que este repo repite.
  tarea_sin_commitear "$id" || return 1
  git -C "$RAIZ" worktree add -q -b "tarea/$id" "$wt" || { echo "✗ $id: no pude crear el worktree"; return 1; }

  # Base del diff FIJADA antes de que el agente toque nada. Sin esto, cualquier chequeo
  # de diff se vuelve ciego en cuanto el agente commitea: es el defecto más común de los
  # gates publicados. El gate la lee de acá y sólo deduce la base si el archivo no está.
  git -C "$wt" rev-parse HEAD > "$wt/.base-ref"

  local dir="$wt/$PROYECTO"
  # El venv del proyecto no viaja al worktree (está gitignorado), así que el gate correría
  # contra el intérprete del sistema y no vería las dependencias. Se lo pasamos.
  if [ -x "$BASE/.venv/bin/python" ]; then export PY_PROYECTO="$BASE/.venv/bin/python"; fi

  # El entorno es responsabilidad del método, no de la tarea: el gate pone ROJO cuando
  # falta el corredor de tests —y hace bien— pero ese rojo no es del agente. Enlazamos
  # venv y node_modules del tronco antes de que empiece.
  bash "$AQUI/preparar-entorno.sh" "$dir" 2>&1 | sed 's/^/  /'

  # La línea base de tests, ANTES de que el agente toque nada. El método es tests-first: al
  # empezar la etapa el tronco tiene los tests de todas sus tareas y la implementación de
  # ninguna, así que la suite no puede estar verde. Sin esta lista, el gate de cada tarea la
  # vería roja por los tests de sus hermanas y ninguna podría cerrar.
  if [ -f "$dir/scripts/correr-suite.sh" ]; then
    ( cd "$dir" && bash scripts/correr-suite.sh --fallas > .tests-base 2>/dev/null ) || true
    echo "  · línea base: $(grep -c . "$dir/.tests-base" 2>/dev/null || echo 0) test(s) ya fallando"
  fi

  # Modo manual: el método no depende de que haya una IA disponible. Preparamos el
  # worktree, mostramos la tarea, y la hace una persona; el gate decide igual.
  if [ "${MANUAL:-0}" = "1" ] || ! command -v opencode >/dev/null 2>&1; then
    [ "${MANUAL:-0}" = "1" ] || echo "· no encuentro opencode: modo manual"
    echo "▶ $id preparada para hacerla a mano"
    echo "    tarea:     $BASE/tareas/$(basename "$archivo")"
    echo "    trabajá en: $dir"
    echo "    al terminar: bash $AQUI/cerrar-tarea.sh $id"
    return 0
  fi

  echo "▶ $id lanzada en $dir"
  (
    cd "$dir" || exit 1
    # OpenCode guarda su estado en SQLite y dos procesos sobre la misma base
    # chocan con "database is locked": cada tarea necesita el suyo.
    # El gate endurece sus reglas cuando sabe que corre dentro de una tarea:
    # exige que haya cambios y aplica los límites de alcance.
    # Antes de gastar un intento: ¿sigue siendo el mismo instrumento? Editar un script con
    # una corrida en vuelo le hace ejecutar basura a bash, y el guardia de borde de etapa se
    # enteraba cuarenta minutos después. Ver `instrumento_se_movio` en _comun.sh.
    # `exit 1` y no `break`: esto corre dentro de la subshell `( ... ) &` de cada tarea, y
    # un `break` ahí no rompe el bucle de afuera — rompe nada y sigue como si el chequeo
    # hubiera pasado, que es la vacuidad de siempre. El código 1 lo lee el `wait` de abajo.
    if instrumento_se_movio; then
      echo "     No se lanza este intento. Relanzá la corrida desde cero." >&2
      exit 1
    fi
    export TAREA="$id"
    export XDG_DATA_HOME="$wt/.opencode-data"
    mkdir -p "$XDG_DATA_HOME"
    local log="$wt/.tarea.log" inicio
    inicio="$(date +%s)"
    # La concurrencia se mide ACÁ, antes de lanzar al agente, y viaja al registro en una
    # variable. `anotar_intento` la contaba sola, y corre DESPUÉS del agente y del gate: lo
    # que anotaba era «cuántas quedaban vivas cuando yo ya terminé». Medido en la tanda del
    # 2026-10-19: cuatro tareas arrancadas en 12 segundos, solapadas por completo, con
    # valores 1, 2, 2 y 0 que decrecen con el orden de finalización — y la que compitió con
    # tres durante sus 970 s enteros quedó anotada como 0, o sea como la única serializada.
    # La columna que existe para que el tiempo no mida la ocupación de la plataforma estaba
    # midiendo la ocupación de la plataforma.
    CONCURRENCIA_AL_ARRANCAR="$(pgrep -f "opencode run" 2>/dev/null | wc -l | tr -d ' ')"
    export CONCURRENCIA_AL_ARRANCAR
    # Igual que en escribir-tests.sh: lo que distingue un cuelgue de un agente lento es el
    # silencio, no el tiempo total.
    # El valor de INACTIVIDAD lo declara _comun.sh en un solo lugar. Acá decía 45,
  # que era el valor viejo: una tercera copia del mismo número, de las que quedan
  # viejas sin que nadie se entere.
  export LOG_VIGILADO="$log"
    {
      echo "=== $id · $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
      # --agent ejecutor: primario con el harness mínimo (6 herramientas en vez de 10).
      # Medido: el cuerpo del request baja de 39.548 a 17.423 caracteres. Se puede cambiar
      # con AGENTE=build si hace falta delegar en subagentes desde la tarea.
      # La memoria de fallas verificadas sobre los archivos que esta tarea toca. Medido:
      # con memoria correcta 75% contra 25% sin ella, y memoria AJENA compra cero —así que
      # se entregan sólo los registros de tareas que comparten archivos, no todos—.
      MEM="$(memoria_para "$id" 2>/dev/null | head -c 4000)"
      con_limite "${LIMITE_AGENTE:-1200}" opencode run --agent "${AGENTE:-ejecutor}" "${MEM:+Fallas YA verificadas en estos archivos, de corridas anteriores. No las repitas: $MEM }${MOTIVO:+Un intento anterior falló así: $MOTIVO. No repitas ese camino. }Implementá la tarea descrita en $archivo. Leela completa antes de empezar. Respetá los archivos permitidos y prohibidos. Al terminar corré 'bash scripts/gate.sh' y mostrá su salida real." 2>&1
      # 142 = SIGALRM: cortado por tiempo. Se deja escrito en el log con la forma que
      # `error_del_agente` reconoce, así el intento queda como ERROR del agente y no como
      # "la tarea no se hizo", que es el diagnóstico equivocado.
      [ "$?" = "142" ] && echo "Error: el agente no respondió: $(motivo_del_corte "$log")"
    } > "$log" 2>&1
    # El agente ya terminó. Recién ahora corre el gate, y el veredicto es su código de
    # salida: nunca lo que el agente escribió. Pasó de verdad: el modelo afirmó
    # "El gate.sh indica GATE VERDE" después de ver fallar el gate tres veces.
    # Otra vez, ahora que el agente ya escribió: una tarea de scaffolding CREA el
    # manifiesto (requirements.txt, package.json), y sin instalarlo el gate reprueba por
    # falta de corredor a la tarea que acaba de declararlo bien.
    bash "$AQUI/preparar-entorno.sh" "$dir" >> "$log" 2>&1
    local error
    error="$(error_del_agente "$log")"
    cerrar_con_gate "$log" "$id"
    # El código del gate se captura ACÁ, pegado a la llamada. Estaba más abajo y en el medio
    # entró el bloque de memoria: `local rc=$?` pasó a leer el estado del `if`, que vale 0
    # cuando su condición es falsa, así que el runner imprimía «gate VERDE» SIEMPRE. El
    # método existe porque un agente dijo «GATE VERDE» con el gate rojo; esto era el arnés
    # haciendo lo mismo. Cualquier cosa que se inserte entre estas dos líneas lo repite.
    local rc=$?
    # Si llegó a verde DESPUÉS de haber fallado, el par (qué falló, qué lo arregló) es
    # memoria verificada: el veredicto lo dio un comando que puede reprobar. Es lo único
    # que el experimento A/B/C muestra que sirve, y lo estábamos tirando al log.
    if [ "$rc" -eq 0 ] && [ -n "${MOTIVO:-}" ]; then
      recordar_falla "$id" "$MOTIVO" \
        "$(git -C "$wt" diff --name-only HEAD~1 HEAD -- "$PROYECTO" 2>/dev/null \
           | grep -v '^$' | tr '\n' ' ' | cut -c1-200)"
    fi
    # Una línea por intento en el registro: las métricas leen datos, no adivinan del texto.
    #
    # El gate primero, SIEMPRE, también acá. El arreglo de abajo —«el ruido del log es una
    # nota, no un veredicto»— entró en el mensaje de consola y NO en el valor que se
    # escribe, así que el registro siguió contradiciendo al gate. Medido: T07, T27 y T06 del
    # 2026-10-04 tienen su commit `gate verde` al segundo exacto de una fila `ERROR`
    # —`cerrar_con_gate` commitea sólo con rc 0, así que el commit prueba el verde—, y
    # `metricas.sh` las informaba como «nunca llegaron a verde» y además las descontaba como
    # pérdida de plataforma. Un ⊘ tapando un sí, contra el modelo y contra la tarea a la vez.
    anotar_intento "$id" "$(veredicto_registrado "$rc" "$error" "$log")" \
                   "$(( $(date +%s) - inicio ))" \
                   "$(grep -m1 -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}' "$log" | cut -c1-8)" \
                   "$log"
    # El gate primero, siempre. Antes esto miraba el error del agente ANTES del código del
    # gate, así que una tarea verde e integrada se informaba como «ERROR del agente» —y el
    # método predica que el juez es el comando—. El ruido del log es una nota, no un
    # veredicto.
    if [ "$rc" -eq 0 ]; then
      echo "✓ $id gate VERDE"
      [ -n "$error" ] && echo "   (nota: la herramienta informó «${error}», y el gate pasó igual)"
    elif [ -n "$error" ]; then
      echo "✗ $id gate ROJO, y la herramienta falló: $error"
    else
      echo "✗ $id gate ROJO"
    fi
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
