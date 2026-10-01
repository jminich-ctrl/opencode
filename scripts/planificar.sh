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
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"

AGENTE="${AGENTE:-arquitecto}"
ENCARGO="${1:-OBJETIVO.md}"
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
  echo "  Primarios: $(opencode agent list 2>/dev/null | grep -oE '^[a-z]+ \(primary\)' | cut -d' ' -f1 | tr '\n' ' ')" >&2
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

  local forma cobertura etapas
  forma="$(cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" --arreglar 2>&1)"
  cobertura="$(cd "$BASE" && ENCARGO="$ENCARGO" PLAN=PLAN.md python3 "$AQUI/cobertura.py" 2>&1)"
  etapas="$(SOLO_ETAPAS=1 bash "$AQUI/correr-plan.sh" 2>&1 >/dev/null)"

  echo "$forma" | sed 's/^/  /'
  echo "$cobertura" | sed 's/^/  /'
  [ -n "$etapas" ] && echo "$etapas" | sed 's/^/  /'

  # Sólo los ✗ son problemas: los avisos los resuelve quien revisa, no el arquitecto.
  PROBLEMAS="$( { echo "$forma"; echo "$cobertura"; echo "$etapas"; } | grep '✗' | sed 's/^ *✗ *//' || true)"
}

[ -f "$BASE/PLAN.md" ] && cp "$BASE/PLAN.md" "$BASE/PLAN.md.previo"
# Huella del estado antes de empezar. En modo INSTRUCCION hace falta: el plan ya validaba,
# así que los validadores dan verde igual si el arquitecto no hizo nada. Nos pasó: una
# corrida de 761s que razonó la tarea entera, no escribió un archivo, y G0 dijo VERDE.
ANTES="$( (cat "$BASE/PLAN.md" 2>/dev/null; ls "$BASE"/tareas/ 2>/dev/null; \
           cat "$BASE"/tareas/*.md 2>/dev/null) | cksum)"
log="$BASE/.plan.log"
inicio=$(date +%s)
huella=""
vuelta=0
limpias=0

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

while [ "$YA_VALIDA" -eq 0 ] && [ "$vuelta" -lt "$INTENTOS" ]; do
  vuelta=$((vuelta+1))
  if [ "$vuelta" -eq 1 ] && [ -n "$INSTRUCCION" ]; then
    pedido="Leé $ENCARGO y el PLAN.md que ya existe. $INSTRUCCION No rehagas el resto del plan ni toques las tareas que ya están."
  elif [ "$vuelta" -eq 1 ]; then
    pedido="Leé $ENCARGO. Es el encargo. Escribí PLAN.md y un archivo por tarea en tareas/, siguiendo el método del repo ($AQUI/../METODO.md, $AQUI/../DESCOMPOSICION.md, plantillas en $AQUI/../plantillas/). Escribilos aunque te falte información: las decisiones que queden abiertas van en una sección 'Decisiones abiertas' DENTRO de PLAN.md."
  else
    # Un pedido por vuelta: con cinco correcciones juntas arregla las mecánicas y deja las
    # estructurales. Se le devuelve la lista, pero se le dice que arregle eso y nada más.
    pedido="Leé $ENCARGO y el PLAN.md que ya existe. Arreglá EXACTAMENTE esto y nada más:
$PROBLEMAS
No rehagas el resto del plan. No toques las tareas que ya están bien."
  fi

  echo "── vuelta $vuelta/$INTENTOS · $AGENTE"
  ( cd "$BASE" || exit 1
    opencode run --agent "$AGENTE" \
      "$pedido Tu única salida son archivos, escritos con la herramienta write: lo que no quedó en un archivo no existe. Antes de terminar verificá con read que cada archivo que dijiste escribir esté ahí. Tu respuesta final es la lista de archivos que escribiste." 2>&1
  ) >> "$log" 2>&1

  err="$(error_del_agente "$log")"
  [ -n "$err" ] && { echo "  ✗ el agente cortó por un error: $err"; break; }

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
DESPUES="$( (cat "$BASE/PLAN.md" 2>/dev/null; ls "$BASE"/tareas/ 2>/dev/null; \
             cat "$BASE"/tareas/*.md 2>/dev/null) | cksum)"
if [ "$ANTES" = "$DESPUES" ] && [ "$YA_VALIDA" -eq 0 ]; then
  echo
  echo "✗ G0 ROJO en ${duracion}s: el arquitecto no cambió ni el plan ni las tareas."
  echo "  Los validadores dan verde porque el plan ya estaba bien, pero no se hizo lo pedido."
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
