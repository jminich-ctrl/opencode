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
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
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
  MOTIVO="$FASE  Lo que falló: $(printf '%s\n%s\n' "$CONCRETO" "$GENERICO" | grep . | tr '\n' ' ' | cut -c1-600)"
  if [ -z "$MOTIVO" ]; then
    echo "✗ $id: no hay transcripts de fallo en $FALLIDOS ni en ../tests-$id."
    echo "   Replanificar sin el motivo es adivinar. Corré la tarea primero."
    continue
  fi

  # Lo que no se toca, para poder verificarlo después.
  CRIT_ANTES="$(grep -c '^- \[ \]' "$archivo" || true)"
  TEST_ANTES="$(grep -oE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`.*clase `[A-Za-z0-9_]+`' "$archivo" | head -1)"
  cp "$archivo" "$archivo.previo"

  echo "▶ $id · el arquitecto replanifica"
  echo "$MOTIVO" | sed 's/^/     /'

  export LOG_VIGILADO="$BASE/.replan-$id.log"
  (
    cd "$BASE" || exit 1
    export XDG_DATA_HOME="$BASE/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    # MODELO= permite comparar candidatos en el papel de arquitecto sin tocar la config.
    # Hace falta: el perfil del planificador —mucha deliberación, pocas herramientas— no se
    # puede evaluar con un banco de seis preguntas, y la única prueba real es si replanifica
    # una tarea que falló de verdad.
    if [ -n "${MODELO:-}" ]; then COMO=(--model "colabhive/$MODELO"); else COMO=(--agent arquitecto); fi
    con_limite "${LIMITE_AGENTE:-1800}" opencode run "${COMO[@]}" \
      "Mirá SOLO el archivo de la tarea, PLAN.md y, si hace falta, los archivos que la tarea nombra. NO explores .venv, node_modules, .git ni ningún directorio de dependencias: no tienen nada que ver con el enunciado y hay decenas de miles de archivos ahí. La tarea tareas/$(basename \"$archivo\") falló al ejecutarse, y el motivo es cómo está escrita, no el agente que la intentó. Esto es lo que falló: $MOTIVO. Leé la tarea, leé PLAN.md, y reescribí SOLO el archivo de tarea con la herramienta write para que el defecto no pueda repetirse. Reglas que no podés romper: (1) no cambies el archivo de test ni el nombre de su clase, los declara el plan; (2) no saques ni ablandes ningún criterio de terminado — si hace falta, agregá; (3) si el problema es que la tarea necesita algo que ninguna tarea del plan entrega, decilo con la palabra HUECO y explicá qué falta, en vez de inventarlo. Lo más útil que podés hacer es decir DÓNDE vive cada cosa que la tarea nombra: archivo exacto, import exacto." 2>&1
  ) > "$LOG_VIGILADO" 2>&1
  RC=$?

  if [ "$RC" = 142 ]; then
    echo "  ✗ el arquitecto no respondió: $(motivo_del_corte "$LOG_VIGILADO")"
    mv "$archivo.previo" "$archivo"; continue
  fi
  if grep -qE '^[ \t]*[*#>-]*[ \t]*HUECO\b' "$LOG_VIGILADO" 2>/dev/null; then
    echo "  ⃠ el arquitecto dice que falta algo que ninguna tarea entrega:"
    grep -A3 -E '^[ \t]*[*#>-]*[ \t]*HUECO\b' "$LOG_VIGILADO" | head -6 | sed 's/^/     /'
    echo "     Eso lo decide una persona: es un hueco del plan, no de la tarea."
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
  # ¿cambió algo? Los tres chequeos de abajo pasan trivialmente sobre un
  # archivo intacto, así que sin esto el script informa «replanificada» cuando el arquitecto
  # leyó, razonó y no escribió. Pasó con T04 y T26: cero líneas de diff, dos verdes.
  # Un chequeo que no puede fallar no es un chequeo — y éste estaba en el script escrito
  # para arreglar el método.
  if cmp -s "$archivo" "$archivo.previo"; then
    echo "  ✗ el arquitecto no cambió nada: leyó la tarea y no la reescribió."
    echo "     No es una replanificación fallida, es una que no ocurrió. Log: $LOG_VIGILADO"
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
    && mal="achicó los criterios de terminado: de $CRIT_ANTES a $CRIT_DESPUES"
  TEST_DESPUES="$(grep -oE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`.*clase `[A-Za-z0-9_]+`' "$archivo" | head -1)"
  [ -n "$TEST_ANTES" ] && [ "$TEST_ANTES" != "$TEST_DESPUES" ] \
    && mal="${mal:+$mal; }cambió el archivo o la clase de test, que los declara el plan"
  if ! (cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" >/dev/null 2>&1); then
    mal="${mal:+$mal; }el plan dejó de validar"
  fi

  if [ -n "$mal" ]; then
    echo "  ✗ se descarta la replanificación: $mal"
    mv "$archivo.previo" "$archivo"
  else
    echo "  ✓ $id replanificada y el plan sigue validando"
    diff -u "$archivo.previo" "$archivo" | grep -E '^[+-][^+-]' | head -12 | sed 's/^/     /'
    rm -f "$archivo.previo"
  fi
done

echo
echo "Lo replanificado NO está commiteado. Miralo y commiteá, o descartalo:"
echo "  git -C $RAIZ diff -- $PROYECTO/tareas"
