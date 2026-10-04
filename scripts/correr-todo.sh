#!/usr/bin/env bash
# El plan entero, etapa por etapa, sin intervención: tests → tareas → integrar → siguiente.
#
#   bash $AGENTES/scripts/correr-todo.sh            # desde la etapa 1
#   bash $AGENTES/scripts/correr-todo.sh 3          # retomar desde la 3
#   SOLO_VER=1 bash $AGENTES/scripts/correr-todo.sh # qué haría, sin tocar nada
#
# Es el encadenado que faltaba. Antes cada paso era un comando y el humano los unía; eso no
# es mínima interacción, es un humano de utilería. Acá el humano hace tres cosas y ninguna
# es trabajo mecánico: firmar el plan, usar la cosa (G3) y desplegar (G5).
#
# **Se detiene y explica** en cada caso en que haga falta una decisión:
#   · los tests de una tarea no pasan su propia validación dos veces
#   · una tarea agota sus reintentos o queda en punto muerto
#   · el agente declaró una tarea IMPOSIBLE
#   · un merge agrega fallas nuevas al tronco
#   · el gate del tronco queda rojo al cerrar una etapa
#
# Lo que NO hace, a propósito: no aprueba el plan, no decide trade-offs, no se saltea G3.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
DESDE="${1:-1}"
SOLO_VER="${SOLO_VER:-0}"
PLAN="$BASE/PLAN.md"

[ -f "$PLAN" ] || { echo "✗ No hay $PLAN. El plan es G0: sin plan no se ejecuta." >&2; exit 1; }

# G0 tiene que estar firmado. Es la única puerta que el runner no abre solo.
if grep -qE '^\*\*Estado del gate G0:\*\*.*borrador' "$PLAN"; then
  echo "✗ El plan sigue marcado como «borrador»." >&2
  echo "  G0 lo firma una persona: es lo único que no se automatiza (HUMANO.md §1)." >&2
  echo "  Cuando lo hayas revisado, cambiá esa línea por: aprobado por <quién> el <fecha>" >&2
  exit 1
fi

# El tronco tiene que estar limpio ANTES de arrancar, no al integrar. `integrar.sh` ya lo
# exige —mergear encima mezcla el trabajo de quien edita con el del agente— pero lo
# descubría al final: la etapa 1 de clasificados gastó 13 minutos y cuatro intentos, llegó
# a VERDE, y se detuvo ahí porque quien mira la corrida había editado un archivo mientras
# corría. Lo que se puede saber antes, se dice antes.
SUCIO="$(git -C "$RAIZ" status --porcelain | grep -v '^?? ' || true)"
if [ -n "$SUCIO" ] && [ "$SOLO_VER" != "1" ]; then
  echo "✗ El tronco tiene cambios sin commitear:" >&2
  echo "$SUCIO" | head -10 | sed 's/^/    /' >&2
  echo "  Commitealos o descartalos antes de arrancar: el worktree de cada tarea se crea" >&2
  echo "  de HEAD, así que lo que no está commiteado no viaja, y al integrar se mezclaría" >&2
  echo "  con el trabajo del agente." >&2
  exit 1
fi

# Y la forma del plan, antes de gastar una sola llamada al modelo.
echo "══ verificando el plan antes de arrancar"
(cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py") || {
  echo "✗ El plan no valida. Arreglalo antes de lanzar 27 tareas sobre él." >&2; exit 1; }
(cd "$BASE" && ENCARGO="${ENCARGO:-OBJETIVO.md}" PLAN=PLAN.md python3 "$AQUI/cobertura.py") || {
  echo "✗ El plan no cubre el encargo. Eso se decide arriba, no acá." >&2; exit 1; }

ETAPAS_TXT="$(SOLO_ETAPAS=1 bash "$AQUI/correr-plan.sh" 2>/dev/null | sed -n 's/^  ETAPA [0-9]*: //p')"
[ -n "$ETAPAS_TXT" ] || { echo "✗ No pude deducir las etapas del plan" >&2; exit 1; }

ETAPAS=()
while IFS= read -r l; do [ -n "$l" ] && ETAPAS+=("$l"); done <<< "$ETAPAS_TXT"
echo "══ ${#ETAPAS[@]} etapa(s); empezando en la $DESDE"

parar() {
  echo
  echo "⏸  Se detuvo en la etapa $1: $2"
  echo "   Decide una persona (HUMANO.md §4). Para retomar después de arreglarlo:"
  echo "     bash $AQUI/correr-todo.sh $1"
  exit 1
}

n=0
for etapa in "${ETAPAS[@]}"; do
  n=$((n+1)); [ "$n" -ge "$DESDE" ] || continue
  read -r -a tareas <<< "$etapa"
  echo
  echo "══════ ETAPA $n/${#ETAPAS[@]}: ${tareas[*]}"

  if [ "$SOLO_VER" = "1" ]; then
    echo "   escribiría los tests, correría las tareas y las integraría"
    continue
  fi

  # 0. El entorno, antes de gastar una llamada al modelo. La etapa anterior pudo agregar
  # dependencias, y el gate —con razón— pone ROJO si falta el corredor de tests. Ese rojo
  # no sería del agente: sería nuestro.
  bash "$AQUI/preparar-entorno.sh" || parar "$n" "no pude preparar el entorno. El gate iba a reprobar por falta de herramientas, no por el código."

  # 1. Los tests, con su validación mecánica. Lo que no pase no se lanza.
  echo "── 1/3 tests"
  bash "$AQUI/escribir-tests.sh" "${tareas[@]}" || true
  sin_tests=()
  for t in "${tareas[@]}"; do
    archivo="$(ls "$BASE/tareas/${t}"-*.md 2>/dev/null | head -1)"
    ruta="$(sed -n "s/^| *$t *| *\`\{0,1\}\([^ |\`]*\)\`\{0,1\} *|.*/\1/p" "$PLAN" | head -1)"
    [ -n "$ruta" ] && [ -f "$BASE/$ruta" ] || sin_tests+=("$t")
  done
  if [ "${#sin_tests[@]}" -gt 0 ]; then
    parar "$n" "los tests de ${sin_tests[*]} no pasaron su propia validación. Los escribe una persona o se repiensa la tarea."
  fi
  git -C "$RAIZ" add -A >/dev/null 2>&1
  git -C "$RAIZ" commit -q -m "tests de la etapa $n: ${tareas[*]}" >/dev/null 2>&1 || true

  # 2. Las tareas. El runner reintenta y corta en punto muerto por su cuenta.
  #
  # UNA sola invocación. Antes esto lanzaba correr-plan.sh en segundo plano Y correr-tarea.sh
  # en primer plano sobre las mismas tareas: dos agentes compitiendo por el mismo worktree,
  # que cada `correr-tarea.sh` borra y recrea (`rm -rf "$wt"`). Se pisaban. El síntoma era
  # una tarea roja sin causa visible en su log, y la cuenta de intentos duplicada en el
  # registro. correr-plan.sh ya llama a correr-tarea.sh: es el motor de reintentos.
  echo "── 2/3 tareas"
  SOLO_UNA=1 bash "$AQUI/correr-plan.sh" "$n" || true

  rojas=(); imposibles=()
  for t in "${tareas[@]}"; do
    v="$(veredicto "$RAIZ/../trabajo-$t/.tarea.log" 2>/dev/null)"
    case "$v" in
      VERDE) ;;
      IMPOSIBLE) imposibles+=("$t") ;;
      *) rojas+=("$t") ;;
    esac
  done
  if [ "${#imposibles[@]}" -gt 0 ]; then
    for t in "${imposibles[@]}"; do
      echo "   ⃠ $t: $(motivo_imposible "$RAIZ/../trabajo-$t/.tarea.log")"
    done
    parar "$n" "el agente declaró imposible(s): ${imposibles[*]}. Leé el motivo: suele ser cierto."
  fi
  [ "${#rojas[@]}" -eq 0 ] || parar "$n" "quedaron en rojo: ${rojas[*]}"

  # 3. Integrar, de a una, con el gate del tronco de por medio.
  echo "── 3/3 integrar"
  bash "$AQUI/integrar.sh" "${tareas[@]}" || parar "$n" "la integración no cerró"
  echo "✓ etapa $n completa"
done

echo
echo "══ Todas las etapas en verde."
echo "Lo que sigue lo hace una persona:"
echo "  1. G3 — USÁ la cosa. Las preguntas están en PLAN.md."
echo "  2. G4 — bash $BASE/scripts/pre-deploy.sh"
echo "  3. G5 — bash $BASE/scripts/deploy.sh staging"
bash "$AQUI/metricas.sh" 2>/dev/null || true
