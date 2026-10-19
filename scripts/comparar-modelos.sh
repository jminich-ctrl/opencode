#!/usr/bin/env bash
# Corre LA MISMA tarea con varios modelos —o con varios agentes— y compara el resultado.
#
#   bash $AGENTES/scripts/comparar-modelos.sh T03 \
#       colabhive/f5d76140-... colabhive/1af07b1f-...
#
#   bash $AGENTES/scripts/comparar-modelos.sh T03 @build @ejecutor
#       un argumento que empieza con @ es un AGENTE, no un modelo: sirve para medir
#       qué cambia el harness (cuántas herramientas, qué prompt) con el modelo fijo.
#   (el ejemplo, desde la raíz de este repo: PROYECTO=ejemplo-pacman bash scripts/comparar-modelos.sh ...)
#
# Es la única forma honesta de elegir modelo para un rol: los benchmarks públicos
# no miden si un modelo llama a las herramientas o se queda deliberando.
#
# Por cada modelo informa: gate (verde/rojo), tiempo, herramientas usadas,
# líneas de deliberación y archivos tocados. Cada agente corre con límite de tiempo
# (LIMITE_AGENTE, 1200s por omisión) porque un candidato roto es el caso normal acá.
set -uo pipefail
# SERIE=1 por omisión: UN brazo a la vez. La columna de segundos de brazos paralelos no
# describe al modelo, describe la ocupación de la plataforma en ese minuto: el mismo MoE A3B
# mide 16,3 tok/s con un usuario y 122 con ocho. Con SERIE=0 los brazos corren en paralelo
# —más rápido, y GATE/TOOLS/DELIB/ARCHIVOS siguen válidos— pero SEGS se imprime como «—».
: "${SERIE:=1}"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE: ver _comun.sh
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
[ $# -ge 2 ] || { echo "uso: $0 TNN {modelo|@agente} {modelo|@agente} [...]" >&2; exit 1; }

TAREA="$1"; shift

# ── El brazo de control, obligatorio ────────────────────────────────────────────────
# Sin control, un resultado no se puede atribuir: si todos los brazos dan cero, el cero
# puede ser del arnés y no de los modelos. Nos pasó: cinco fallas limpias y reproducibles
# del modelo de un partner iban a salir como veredicto sobre el modelo, y lo que lo evitó
# fue que el control no se había movido —salidas idénticas carácter por carácter en dos
# tandas separadas por horas—.
#
# MEDICION.md §7 afirmaba que «el runner se niega a arrancar si el brazo de control no está
# declarado». Era falso: no había un solo brazo de control en ningún script. Esto lo vuelve
# cierto. El control corre SIEMPRE, como un brazo más de la misma tanda — no como una sesión
# de validación aparte, que es la que no se hace nunca.
if [ -z "${CONTROL:-}" ]; then
  echo "✗ declará el brazo de control: CONTROL=<modelo|@agente> $0 ..." >&2
  echo "  Un número sin control no se cita. El control es el modelo del que ya sabés qué" >&2
  echo "  tiene que dar; si se mueve, se movió el arnés y la tanda entera se descarta." >&2
  echo "  Para saltearlo a propósito: CONTROL=ninguno (queda escrito en la tabla)." >&2
  exit 1
fi
if [ "$CONTROL" != "ninguno" ]; then
  set -- "$@" "$CONTROL"   # último brazo, siempre presente
fi

archivo="$(ls "$BASE/tareas/${TAREA}"-*.md 2>/dev/null | head -1)"
[ -n "$archivo" ] || { echo "✗ no existe tareas/${TAREA}-*.md" >&2; exit 1; }
archivo="tareas/$(basename "$archivo")"
# El gate aplica sus reglas de tarea (sin cambios = rojo, alcance) sólo si sabe cuál es.
export TAREA

n=0
for modelo in "$@"; do
  n=$((n+1))
  wt="$RAIZ/../comparar-$TAREA-$n"
  # El transcript del intento anterior, ANTES de borrar el worktree. Es el único lugar
  # donde está escrito por qué falló. Lo agregué primero a escribir-tests.sh y no acá, y
  # volví a perder un log en este camino: arreglar un lado y no el otro es el patrón que
  # este repo repite.
  conservar_intento "$wt" "${TAREA:-comparar}-$n"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "comparar/$TAREA-$n" 2>/dev/null
  git -C "$RAIZ" worktree add -q -b "comparar/$TAREA-$n" "$wt" || continue
  # @nombre = agente; cualquier otra cosa = modelo. Con el modelo fijo y el agente
  # variable se mide el harness; al revés, el modelo.
  case "$modelo" in
    @*) COMO=(--agent "${modelo#@}") ;;
    *)  COMO=(--model "$modelo") ;;
  esac
  echo "▶ $n: $modelo"
  (
    cd "$wt/$PROYECTO" || exit 1
    # Un worktree recién creado no tiene .venv ni node_modules, así que la suite no puede
    # correr y el gate reprueba por «falta el corredor de tests» — a TODOS los modelos, por
    # igual, por un motivo que no los distingue. La primera comparación válida de GLM,
    # Devstral y el 27B se perdió así: midió el entorno, no los modelos.
    # `correr-tarea.sh` ya lo hacía; acá faltaba.
    bash "$AQUI/preparar-entorno.sh" "$wt/$PROYECTO" >/dev/null 2>&1
    export XDG_DATA_HOME="$wt/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    inicio=$(date +%s)
    # CON límite. Lo primero que uno le pide a un modelo candidato es que capaz esté roto,
    # y un modelo roto se cuelga: sin límite, la comparación que vino a detectarlo se queda
    # corriendo para siempre y no informa nada. Un instrumento que no sobrevive al defecto
    # que vino a medir no mide ese defecto.
    export LOG_VIGILADO="$wt/.tarea.log"
    {
      echo "=== $TAREA · $modelo"
      con_limite "${LIMITE_AGENTE:-1200}" opencode run "${COMO[@]}" "Implementá la tarea descrita en $archivo. Leela completa antes de empezar. Respetá los archivos permitidos y prohibidos. Al terminar corré 'bash scripts/gate.sh' y mostrá su salida real." 2>&1
      rc=$?
      # Por qué se cortó, si se cortó: «✗ error» sin motivo no distingue un modelo lento
      # de uno roto, que es exactamente lo que se está midiendo.
      [ "$rc" = 142 ] && echo "el agente no respondió: $(motivo_del_corte "$wt/.tarea.log")"
    } > "$wt/.tarea.log" 2>&1
    duracion=$(( $(date +%s) - inicio ))
    # Veredicto por código de salida del gate, corrido cuando el agente ya terminó.
    # .segundos se escribe DESPUÉS: el gate vería un archivo nuevo fuera del alcance.
    cerrar_con_gate "$wt/.tarea.log" "$TAREA"
    echo "$duracion" > "$wt/.segundos"
  ) &
  # Serializado: esperar a este brazo antes de lanzar el siguiente. Es lo que hace que la
  # columna de segundos signifique algo.
  [ "$SERIE" = 1 ] && wait
done
wait

echo
printf '%-3s %-26s %-8s %6s %6s %6s %s\n' '#' 'MODELO / @AGENTE' GATE SEGS TOOLS DELIB ARCHIVOS
printf '%.0s─' {1..88}; echo
n=0
for modelo in "$@"; do
  n=$((n+1))
  wt="$RAIZ/../comparar-$TAREA-$n"
  log="$wt/.tarea.log"
  if [ -n "$(error_del_agente "$log" 2>/dev/null)" ]; then gate="✗ error"
  elif [ "$(veredicto "$log")" = "VERDE" ]; then gate="✓ verde"
  else gate="✗ rojo"; fi
  # Un instrumento que no puede medir el tiempo no muestra un número de tiempo.
  if [ "$SERIE" = 1 ]; then segs="$(cat "$wt/.segundos" 2>/dev/null || echo '?')"
  else segs='—'; fi
  # Herramientas: contamos las marcas que OpenCode imprime al invocarlas. El patrón
  # anterior dependía de los códigos de escape exactos y contaba 0 siempre.
  tools="$(parte_del_agente "$log" 2>/dev/null \
           | grep -cE '(Read|Write|Edit|Glob|Grep|Bash|List) ' )"
  delib="$(parte_del_agente "$log" 2>/dev/null | wc -l | xargs)"
  # Archivos: del commit que deja el runner al dar verde. Contar los sin commitear da 0
  # desde que el runner commitea (una mejora en un lado rompió la medición en el otro).
  # Los archivos QUE EL AGENTE tocó, sin la infraestructura que prepara el método. Antes
  # miraba HEAD~1..HEAD, que incluye el commit de preparación del entorno: informaba 11
  # archivos para los tres modelos cuando ninguno había escrito uno solo. Una columna que
  # da el mismo número para quien trabajó y para quien no, no mide nada.
  INFRA_CMP='\.opencode-data|\.tarea\.log|\.segundos|\.base-ref|\.tests-base|\.venv|\.entorno|node_modules|package-lock\.json|\.mysql'
  archivos="$( { git -C "$wt" diff --name-only HEAD -- "$PROYECTO" 2>/dev/null; \
                 git -C "$wt" ls-files --others --exclude-standard -- "$PROYECTO" 2>/dev/null; } \
               | grep -vE "$INFRA_CMP" | sort -u | grep -c . | xargs)"
  printf '%-3s %-26s %-8s %6s %6s %6s %s\n' "$n" "$(echo "$modelo" | cut -c1-26)" "$gate" "$segs" "${tools:-0}" "$delib" "$archivos"
done
echo
# ── El criterio de validez del control, escrito y aplicado ─────────────────────────
#
# MEDICION.md §7 decía que faltaba esto: el comparador corría el control y lo informaba, y
# QUIÉN decide que se movió demasiado seguía siendo una persona.
#
# Y la banda que el diseño proponía —±2 ítems sobre 12— estaba calculada con p=0,83, que es la
# tasa de TOOL-CALL, no de verde. La tasa de verde del control, medida en `.metricas`, es
# **0,42 por corrida** (22 de 52). Con ésa, ±2 descarta el 29% de los bloques buenos; ±4 da
# 5,6% y ±5 da 1,9%. Un conteo binomial de 12 ítems con una banda de ±5 ya no controla nada:
# la señal de que un conteo así no puede ser un control.
#
# Por eso el criterio es CONTINUO y sobre lo que tiene varianza baja: la tasa de herramientas
# y las líneas de deliberación del control. Si el control deja de llamar herramientas, se
# movió el arnés — y eso se ve con pocas corridas, no con doce.
if [ "$CONTROL" = "ninguno" ]; then
  echo "SIN BRAZO DE CONTROL (CONTROL=ninguno): si todos los brazos dan lo mismo, no podés"
  echo "saber si eso es de los modelos o del arnés. El resultado no se cita sin eso."
else
  WT_C="$RAIZ/../comparar-$TAREA-$n"
  LOG_C="$WT_C/.tarea.log"
  T_C="$(parte_del_agente "$LOG_C" 2>/dev/null | grep -cE '(Read|Write|Edit|Glob|Grep|Bash|List) ')"
  G_C="$(veredicto "$LOG_C" 2>/dev/null)"
  echo "CONTROL = $CONTROL (último brazo): gate=${G_C:-sin veredicto}, herramientas=$T_C"
  SALIDA_C="$(control_se_movio "$CONTROL|$TAREA" "$T_C" "${G_C:-?}")"; RC_C=$?
  case "$RC_C" in
    2) echo "  · primera corrida de este control en $TAREA: queda como línea base."
       echo "    El criterio aplica desde la segunda. Un número de esta tanda no tiene con qué"
       echo "    compararse todavía, y eso hay que decirlo al citarlo." ;;
    0) echo "  · el control no se movió: la tanda es válida." ;;
    1) echo
       echo "✗ EL CONTROL SE MOVIÓ: $SALIDA_C"
       echo "  Se movió el arnés, no los modelos. **La tanda se descarta ENTERA**, incluidos los"
       echo "  brazos que dieron bien: si el instrumento estaba mal, su acierto también es"
       echo "  sospechoso. Arreglá y volvé a correr todo."
       exit 1 ;;
  esac
fi
echo "TOOLS alto y DELIB bajo = el modelo actúa. Al revés = delibera y no produce."
[ "$SERIE" = 1 ] || echo "SEGS = — : los brazos corrieron en paralelo y el tiempo medido sería el de la plataforma, no el del modelo. Para medir tiempo: SERIE=1 (por omisión)."
echo "Diffs en $RAIZ/../comparar-$TAREA-N/  ·  borralos con: git worktree remove <carpeta>"
