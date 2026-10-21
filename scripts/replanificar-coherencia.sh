#!/usr/bin/env bash
# Cuando el PREFLIGHT encuentra que el plan se contradice, lo arregla el arquitecto — no vos.
#
#   bash $AGENTES/scripts/replanificar-coherencia.sh
#
# Por qué existe. `coherencia.py` terminaba sus rojos con «Lo decide quien planifica» y
# `correr-todo.sh` hacía `exit 1`: o sea, el método producía un veredicto correcto y después
# **paraba a esperar a una persona**. Es palabra por palabra el defecto que `replanificar.sh`
# vino a corregir del lado de las tareas —«el método decía "se repiensa la tarea" y paraba»—
# reaparecido en el chequeo más nuevo. Y en este repo la persona que iba a inferir era yo,
# que es exactamente lo que no tiene que pasar: el objetivo es que los modelos locales hagan
# todo, y el plan tiene un agente `arquitecto` que para esto no se usaba.
#
# El cadáver: el enunciado de T26 pedía la tabla `users`, la migración creaba `usuarios`, y
# el preflight —correctísimo— dejó el plan detenido sin ningún camino que lo levantara.
#
# Lo que el arquitecto NO puede hacer, y este script verifica:
#   1. Dejar el preflight en rojo. El juez es el MISMO chequeo que encontró el problema.
#   2. Achicar los criterios de terminado del plan. Replanificar no es bajar la vara.
#   3. Cambiar los archivos o las clases de test: los declara el plan y los lee todo el mundo.
#   4. Dejar el plan sin validar (`validar-plan.py`, un comando, igual que siempre).
# Cualquiera que falle descarta el cambio ENTERO y deja las tareas como estaban.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"

# ── El motivo, del chequeo y no de mi lectura del chequeo.
ROJOS="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" 2>&1 | grep '✗' || true)"
if [ -z "$ROJOS" ]; then
  echo "✓ el preflight no tiene rojos: no hay nada que replanificar"
  exit 0
fi
echo "▶ el arquitecto replanifica el plan. Lo que el preflight encontró:"
printf '%s\n' "$ROJOS" | sed 's/^/     /'

# Lo que no se toca, medido ANTES, para poder verificarlo después.
CRIT_ANTES="$(cat "$BASE"/tareas/*.md 2>/dev/null | grep -c '^- \[ \]' || true)"
TESTS_ANTES="$(grep -ohE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`[^|]*clase `[A-Za-z0-9_]+`' \
               "$BASE"/tareas/*.md 2>/dev/null | sort || true)"
PREVIO="$BASE/.tareas-previo"
rm -rf "$PREVIO"; cp -R "$BASE/tareas" "$PREVIO"
restaurar() { rm -rf "$BASE/tareas"; mv "$PREVIO" "$BASE/tareas"; }

export LOG_VIGILADO="$BASE/.replan-coherencia.log"
(
  cd "$BASE" || exit 1
  export XDG_DATA_HOME="$BASE/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
  if [ -n "${MODELO:-}" ]; then COMO=(--model "colabhive/$MODELO"); else COMO=(--agent arquitecto); fi
  con_limite "${LIMITE_AGENTE:-1800}" opencode run "${COMO[@]}" \
    "Mirá SOLO los archivos de tareas/, PLAN.md y las migraciones que se nombren. NO explores .venv, node_modules ni .git: hay decenas de miles de archivos ahí y no tienen nada que ver. El preflight del plan encontró esto, y es una contradicción del PLAN, no de ningún agente: $ROJOS. Cada rojo dice qué tarea lo origina. Corregí con la herramienta write SOLO los archivos de tareas/ que haga falta, de modo que la contradicción desaparezca. Para cada tabla tenés exactamente dos salidas y elegís vos: (a) que el enunciado use el nombre que la migración YA crea, o (b) que alguna tarea prometa CREAR esa tabla en una migración, diciéndolo con las palabras 'crear la tabla'. Reglas que no podés romper: (1) no saques ni ablandes ningún criterio de terminado —si hace falta, agregá—; (2) no cambies ningún archivo de test ni el nombre de su clase, los declara el plan; (3) no toques código ni migraciones, sólo tareas/; (4) si la contradicción no se puede resolver sin inventar una decisión de producto, decilo con la palabra HUECO y explicá qué falta, en vez de elegir por tu cuenta." 2>&1
) > "$LOG_VIGILADO" 2>&1
RC=$?

if [ "$RC" = 142 ]; then
  echo "  ✗ el arquitecto no respondió: $(motivo_del_corte "$LOG_VIGILADO")"
  restaurar; exit 1
fi
ERR_PLAT="$(error_del_agente "$LOG_VIGILADO" 2>/dev/null)"
if [ -n "$ERR_PLAT" ]; then
  echo "  ✗ no se pudo replanificar: $ERR_PLAT"
  echo "     Es de la plataforma o la herramienta, no del arquitecto. Reintentá."
  restaurar; exit 1
fi
if grep -qE '^[ \t]*[*#>-]*[ \t]*HUECO\b' "$LOG_VIGILADO" 2>/dev/null; then
  echo "  ⃠ el arquitecto dice que falta una decisión que no es suya:"
  grep -A3 -E '^[ \t]*[*#>-]*[ \t]*HUECO\b' "$LOG_VIGILADO" | head -6 | sed 's/^/     /'
  echo "     Eso lo decide una persona: es del encargo, no del plan."
  restaurar; exit 1
fi
if diff -rq "$PREVIO" "$BASE/tareas" >/dev/null 2>&1; then
  echo "  ✗ el arquitecto no cambió nada: leyó el plan y no lo reescribió."
  echo "     No es una replanificación fallida, es una que no ocurrió. Log: $LOG_VIGILADO"
  restaurar; exit 1
fi

# ── Los cuatro jueces.
mal=""
CRIT_DESPUES="$(cat "$BASE"/tareas/*.md 2>/dev/null | grep -c '^- \[ \]' || true)"
[ "${CRIT_DESPUES:-0}" -lt "${CRIT_ANTES:-0}" ] \
  && mal="achicó los criterios de terminado del plan: de $CRIT_ANTES a $CRIT_DESPUES"
TESTS_DESPUES="$(grep -ohE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`[^|]*clase `[A-Za-z0-9_]+`' \
                 "$BASE"/tareas/*.md 2>/dev/null | sort || true)"
[ "$TESTS_ANTES" != "$TESTS_DESPUES" ] \
  && mal="${mal:+$mal; }cambió los archivos o las clases de test, que los declara el plan"
# EL juez: el mismo chequeo que encontró el problema es el que acepta el arreglo. Si el
# arquitecto tapa un rojo y abre otro, el preflight sigue rojo y esto sigue siendo un no.
if ! PROYECTO="$BASE" python3 "$AQUI/coherencia.py" >/dev/null 2>&1; then
  mal="${mal:+$mal; }el preflight sigue en rojo: $(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" 2>&1 | grep '✗' | head -2 | tr '\n' ' ')"
fi
if ! (cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" >/dev/null 2>&1); then
  mal="${mal:+$mal; }el plan dejó de validar"
fi

if [ -n "$mal" ]; then
  echo "  ✗ se descarta la replanificación: $mal"
  restaurar; exit 1
fi
echo "  ✓ el plan ya no se contradice y sigue validando"
diff -ru "$PREVIO" "$BASE/tareas" | grep -E '^[+-][^+-]' | head -16 | sed 's/^/     /'
rm -rf "$PREVIO"
echo
echo "Lo replanificado NO está commiteado. Miralo y commiteá, o descartalo:"
echo "  git -C $RAIZ diff -- $PROYECTO/tareas"
