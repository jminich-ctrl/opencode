#!/usr/bin/env bash
# Ejecuta un plan entero: etapa por etapa, en paralelo dentro de cada etapa.
#
#   bash scripts/correr-plan.sh              # de la primera etapa a la última
#   bash scripts/correr-plan.sh 3            # desde la etapa 3
#   REINTENTOS=2 bash scripts/correr-plan.sh # cuántas veces relanzar una tarea roja
#
# Las etapas se leen de PLAN.md. Formato esperado (una línea por etapa):
#
#   ETAPA 1: T02 T03 T04
#   ETAPA 2: T05
#
# Si el plan no las declara así, se deducen de la tabla de tareas y sus dependencias.
#
# Se detiene cuando una tarea agota sus reintentos: ahí decide un humano (HUMANO.md §4).
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
DESDE="${1:-1}"
REINTENTOS="${REINTENTOS:-2}"

PLAN="$BASE/PLAN.md"
[ -f "$PLAN" ] || { echo "✗ No encuentro $PLAN (el plan es el gate G0: sin plan no se ejecuta)" >&2; exit 1; }

# Etapas declaradas explícitamente, o deducidas de la tabla del plan.
mapfile -t ETAPAS < <(grep -oE '^ *\*{0,2}ETAPA [0-9]+\*{0,2}:.*' "$PLAN" | sed 's/^[^:]*: *//' || true)
if [ "${#ETAPAS[@]}" -eq 0 ]; then
  echo "· el plan no declara etapas; deduciendo de la tabla de tareas"
  mapfile -t ETAPAS < <(PLAN="$PLAN" python3 "$AQUI/_etapas.py")
fi
[ "${#ETAPAS[@]}" -gt 0 ] || { echo "✗ No pude determinar las etapas del plan" >&2; exit 1; }

echo "Plan con ${#ETAPAS[@]} etapa(s). Empezando en la $DESDE."
echo

n=0
for etapa in "${ETAPAS[@]}"; do
  n=$((n+1))
  [ "$n" -ge "$DESDE" ] || continue
  read -r -a tareas <<< "$etapa"
  [ "${#tareas[@]}" -gt 0 ] || continue

  echo "══ ETAPA $n: ${tareas[*]}"
  intento=1
  pendientes=("${tareas[@]}")
  while [ "${#pendientes[@]}" -gt 0 ] && [ "$intento" -le "$REINTENTOS" ]; do
    [ "$intento" -gt 1 ] && echo "── reintento $intento de: ${pendientes[*]}"
    bash "$AQUI/correr-tarea.sh" "${pendientes[@]}"

    # Quedan pendientes las que no dieron verde. El veredicto sale del gate, nunca del log
    # del agente (ver METODO.md P2).
    nuevas=()
    for t in "${pendientes[@]}"; do
      log="$RAIZ/../trabajo-$t/.tarea.log"
      [ "$(veredicto "$log" 2>/dev/null)" = "VERDE" ] || nuevas+=("$t")
    done
    pendientes=("${nuevas[@]+"${nuevas[@]}"}")
    intento=$((intento+1))
  done

  if [ "${#pendientes[@]}" -gt 0 ]; then
    echo
    echo "✗ La etapa $n se detuvo con tareas en rojo: ${pendientes[*]}"
    echo "  Agotaron $REINTENTOS intentos. Decide un humano (ver HUMANO.md §4):"
    echo "    · relanzar con el error pegado en la tarea,"
    echo "    · partir la tarea en dos,"
    echo "    · o hacerla a mano."
    echo "  Logs: $RAIZ/../trabajo-TNN/.tarea.log"
    exit 1
  fi

  echo "✓ etapa $n completa"
  echo
done

echo "══ Todas las etapas en verde."
echo "Lo que sigue lo hace un humano:"
echo "  1. G3 — integrar y USAR la cosa (las preguntas están en PLAN.md)"
echo "  2. G4 — bash $PROYECTO/scripts/pre-deploy.sh"
echo "  3. G5 — bash $PROYECTO/scripts/deploy.sh staging"
bash "$AQUI/metricas.sh" 2>/dev/null || true
