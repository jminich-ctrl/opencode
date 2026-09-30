#!/usr/bin/env bash
# G0: el arquitecto convierte un OBJETIVO.md en PLAN.md y los archivos de tareas.
#
#   bash $AGENTES/scripts/planificar.sh                  # lee OBJETIVO.md del proyecto
#   bash $AGENTES/scripts/planificar.sh mi-encargo.md    # otro archivo de encargo
#   AGENTE=plan bash $AGENTES/scripts/planificar.sh      # con otro agente
#
# Era el único gate sin script: se corría a mano y por eso arrastramos meses un
# `--agent arquitecto` que en realidad respondía `build` (OPENCODE.md §3).
#
# El plan que sale NO está aprobado. G0 lo firma una persona: ver HUMANO.md §1.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE: ver _comun.sh
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"

AGENTE="${AGENTE:-arquitecto}"
ENCARGO="${1:-OBJETIVO.md}"
[ -f "$BASE/$ENCARGO" ] || { echo "✗ No encuentro $BASE/$ENCARGO" >&2
  echo "  El encargo lo escribe una persona, en sus palabras (HUMANO.md §1)." >&2; exit 1; }

command -v opencode >/dev/null 2>&1 || { echo "✗ No hay opencode." >&2
  echo "  El método no depende de una IA: escribí el plan a mano con plantillas/PLAN.md" >&2
  echo "  y seguí con 'bash scripts/correr-plan.sh'." >&2; exit 1; }

# Un agente que no está registrado responde como el agente por defecto y no avisa.
# Verificarlo cuesta un segundo y nos habría ahorrado semanas.
if ! opencode agent list 2>/dev/null | grep -qE "^$AGENTE \((primary|subagent)\)"; then
  echo "✗ OpenCode no reconoce el agente '$AGENTE'." >&2
  echo "  Suele ser que le falta \"mode\": \"primary\" en opencode.json (OPENCODE.md §3)." >&2
  echo "  Registrados: $(opencode agent list 2>/dev/null | grep -oE '^[a-z]+ \(primary\)' | cut -d' ' -f1 | tr '\n' ' ')" >&2
  exit 1
fi
if opencode agent list 2>/dev/null | grep -qE "^$AGENTE \(subagent\)"; then
  echo "✗ '$AGENTE' es un subagente: desde la CLI cae al agente por defecto sin avisar." >&2
  exit 1
fi

[ -f "$BASE/PLAN.md" ] && { echo "· ya existe $BASE/PLAN.md; se respalda en PLAN.md.previo"
                            cp "$BASE/PLAN.md" "$BASE/PLAN.md.previo"; }

log="$BASE/.plan.log"
echo "▶ $AGENTE sobre $ENCARGO  (log: $log)"
inicio=$(date +%s)
(
  cd "$BASE" || exit 1
  opencode run --agent "$AGENTE" \
    "Leé $ENCARGO. Es el encargo. Escribí PLAN.md y los archivos de tareas en tareas/, siguiendo el método del repo ($AQUI/../METODO.md, $AQUI/../DESCOMPOSICION.md, plantillas en $AQUI/../plantillas/). Cuando termines, decime qué decisiones te quedaron abiertas." 2>&1
) > "$log" 2>&1
duracion=$(( $(date +%s) - inicio ))

# El veredicto de G0 no es lo que el agente diga: es si el plan existe y es ejecutable.
# El mismo principio que P2, aplicado al planificador.
echo
fallos=0
if [ -s "$BASE/PLAN.md" ]; then echo "  ✓ PLAN.md escrito ($(wc -l < "$BASE/PLAN.md" | xargs) líneas)"
else echo "  ✗ no escribió PLAN.md"; fallos=$((fallos+1)); fi

n_tareas="$(ls "$BASE"/tareas/T*.md 2>/dev/null | wc -l | xargs)"
if [ "${n_tareas:-0}" -gt 0 ]; then echo "  ✓ $n_tareas archivo(s) de tarea"
else echo "  ✗ no escribió ninguna tarea en tareas/"; fallos=$((fallos+1)); fi

if [ "$fallos" -eq 0 ] && SOLO_ETAPAS=1 bash "$AQUI/correr-plan.sh" >/dev/null 2>&1; then
  echo "  ✓ el plan se puede ejecutar:"
  SOLO_ETAPAS=1 bash "$AQUI/correr-plan.sh" 2>/dev/null | sed 's/^/     /'
elif [ "$fallos" -eq 0 ]; then
  echo "  ✗ el plan existe pero no se le pueden deducir las etapas"; fallos=$((fallos+1))
fi

err="$(error_del_agente "$log")"
[ -n "$err" ] && { echo "  ✗ el agente cortó por un error: $err"; fallos=$((fallos+1)); }

echo
if [ "$fallos" -gt 0 ]; then
  echo "G0 ROJO en ${duracion}s — revisá $log"
  exit 1
fi
echo "G0: el plan está escrito, en ${duracion}s. NO está aprobado."
echo "Lo que sigue lo hace una persona (HUMANO.md §1):"
echo "  1. ¿Las tareas están dimensionadas? (cuántas funciones tiene que escribir, no cuántos archivos)"
echo "  2. ¿Marcó los choques de archivo?"
echo "  3. ¿Inventó APIs que no existen?"
echo "  4. ¿Se dio permisos de más en «archivos que podés tocar»?"
echo "  5. ¿Dejó decisiones abiertas, o eligió solo?"
echo
echo "Cerrá lo abierto y después: bash $AQUI/correr-plan.sh"
