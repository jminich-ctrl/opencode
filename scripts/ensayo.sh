#!/usr/bin/env bash
# Un ENSAYO del pipeline completo: determinista, repetible y sin gastar un token de modelo.
#
#   GRUPOS=7 bash $AGENTES/scripts/ensayo.sh                        21 tareas en 3 etapas de 7
#   GRUPOS=1 COMPORTAMIENTO=miente bash $AGENTES/scripts/ensayo.sh  ¿el gate lo atrapa?
#
# Por qué existe: lo más largo que el pipeline había ejecutado de verdad eran CINCO tareas, y
# un plan de veinte estaba afirmado y no medido. Medirlo con modelos cuesta horas, gasta
# plataforma y no es repetible —un modelo contesta distinto cada vez—, así que la orquestación
# nunca se podía separar del modelo. Acá el agente es determinista: lo que falle es del método.
#
# Lo encontró en su PRIMERA corrida: el gate le cobraba a la tarea un `.opencode-data` vacío
# que crea el propio runner, y eso dispara justo cuando el agente no escribió nada —o sea que
# tapaba la causa real con un rojo de higiene—. Ver el commit «el gate le cobraba a la tarea un
# directorio vacío que crea el propio runner».
#
# Lo que esto mide es la ORQUESTACIÓN: etapas, worktrees, escribir-tests, gate, cierre, merge.
# Lo que NO mide es si un modelo chico puede hacer la tarea; eso es el banco (`congelar-banco.sh`).
#
# El veredicto es el código de salida de ESTE script, y depende del comportamiento pedido:
#   · `cumple`           se espera que TODAS las tareas cierren y la suite del proyecto quede verde
#   · cualquier otro      se espera que el pipeline SE DETENGA y que ninguna tarea cierre
# Un ensayo que no sabe qué esperar no es un ensayo: es una corrida.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRUPOS="${GRUPOS:-1}"
COMPORTAMIENTO="${COMPORTAMIENTO:-cumple}"
DONDE="${1:-$(mktemp -d)}"
mkdir -p "$DONDE" || { echo "✗ no puedo escribir en $DONDE" >&2; exit 1; }
PROY="$DONDE/proy"; CLAVES="$DONDE/claves"; LOG="$DONDE/ensayo.log"
mkdir -p "$PROY" "$CLAVES"

python3 "$AQUI/_ensayo_generar.py" "$GRUPOS" "$PROY" "$CLAVES" || exit 1

# El agente, con el nombre que el runner busca. Un enlace y no una copia: si el agente del
# ensayo cambia, el ensayo que corre es el nuevo.
BIN="$DONDE/bin"; mkdir -p "$BIN"
ln -sf "$AQUI/_ensayo_agente.sh" "$BIN/opencode"

echo "══ ensayo: $((GRUPOS * 3)) tarea(s), comportamiento «${COMPORTAMIENTO}»"
echo "   proyecto: $PROY"
(
  cd "$PROY" || exit 1
  AGENTES="$(cd "$AQUI/.." && pwd)" PATH="$BIN:$PATH" \
  ENSAYO_CLAVES="$CLAVES" ENSAYO_COMPORTAMIENTO="$COMPORTAMIENTO" \
  ARRANQUE_FRIO="${ARRANQUE_FRIO:-5}" bash "$AQUI/correr-todo.sh"
) > "$LOG" 2>&1
RC_PIPELINE=$?

# `|| true`, NO `|| echo 0`: `grep -c` imprime el conteo Y sale 1 cuando es cero, así que
# `|| echo 0` agrega un segundo cero y la variable queda «0\n0» — después `[ "$CERRADAS" -ne 0 ]`
# muere con «integer expression expected» y el `if` se evalúa como falso. O sea que la guarda
# que detecta un VERDE FALSO no corría. Es el mismo defecto que ya se arregló en el stack JS de
# este repo («`grep -c . || echo 0` daba "0\n0"») y lo volví a escribir acá.
# `[a-z]?` y no `[abc]`: el id con sufijo de letra es parte del método —partir una tarea
# grande es la respuesta correcta a un defecto del plan— y un patrón que no lo acepta parte
# las subtareas. Hay un test de la suite que barre los scripts buscando justo esto, y me lo
# marcó: el generador del ensayo usa a/b/c, pero el patrón es del método, no del generador.
CERRADAS="$(grep -cE '^\| T[0-9]+[a-z]? \|.*✅' "$PROY/PLAN.md" 2>/dev/null || true)"
TOTAL=$((GRUPOS * 3))
VERDES="$(grep -cE 'gate VERDE' "$LOG" 2>/dev/null || true)"
CERRADAS="${CERRADAS:-0}"; VERDES="${VERDES:-0}"
echo "   pipeline: código $RC_PIPELINE · $CERRADAS/$TOTAL tarea(s) cerradas · $VERDES gate(s) verde(s)"
echo "   log: $LOG"

if [ "$COMPORTAMIENTO" = "cumple" ]; then
  if [ "$RC_PIPELINE" -ne 0 ] || [ "$CERRADAS" -ne "$TOTAL" ]; then
    echo "✗ con un agente que cumple, el pipeline tiene que cerrar las $TOTAL"
    grep -E '^ *✗ ' "$LOG" | sort -u | head -6 | sed 's/^/     /'
    exit 1
  fi
  SUITE="$(cd "$PROY" && bash scripts/correr-suite.sh 2>&1 | tail -3)"
  if ! echo "$SUITE" | grep -q '^OK'; then
    echo "✗ las $TOTAL cerraron pero la suite del proyecto NO está verde:"
    echo "$SUITE" | sed 's/^/     /'
    exit 1
  fi
  echo "✓ $TOTAL/$TOTAL cerradas y la suite del proyecto en verde"
else
  # El ensayo de un comportamiento malo pasa cuando el método NO lo deja pasar.
  if [ "$RC_PIPELINE" -eq 0 ] || [ "$CERRADAS" -ne 0 ]; then
    echo "✗ «${COMPORTAMIENTO}» cerró $CERRADAS tarea(s) con código $RC_PIPELINE: es un VERDE FALSO"
    exit 1
  fi
  echo "✓ «${COMPORTAMIENTO}» no pasó. El gate dijo:"
  grep -E '^ *✗ ' "$LOG" | grep -vE 'punto muerto|se detuvo|quedaron en rojo|gate ROJO' \
    | sort -u | head -3 | sed 's/^/     /'
fi
