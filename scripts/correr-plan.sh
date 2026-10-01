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
# Sin `mapfile`: es de bash 4 y macOS trae 3.2. Este script no corría por eso.
ETAPAS=()
# Formato canónico: `**ETAPA 1:** T02 T03`, sólo identificadores. El cierre de negrita de
# markdown va después de los dos puntos, y se acepta con o sin asteriscos.
CANONICAS="$(grep -cE '^ *\*{0,2}ETAPA +[0-9]+\*{0,2}:\*{0,2} *[T0-9 ]+ *$' "$PLAN" || true)"
PARECIDAS="$(grep -icE '^ *\*{0,2}etapa +[0-9]' "$PLAN" || true)"

if [ "${PARECIDAS:-0}" -gt "${CANONICAS:-0}" ]; then
  # Mezclar líneas canónicas con líneas en prosa es peor que no leer ninguna: las que no
  # matchean DESAPARECEN, y sus tareas no se ejecutan sin que nadie se entere. Descartamos
  # todas y deducimos, que además respeta los choques de archivo.
  echo "⚠ $PLAN declara etapas en un formato que el runner no lee entero:" >&2
  grep -inE '^ *\*{0,2}etapa +[0-9]' "$PLAN" \
    | grep -vE ':\*{0,2} *ETAPA +[0-9]+\*{0,2}:\*{0,2} *[T0-9 ]+ *$' | head -4 | sed 's/^/    /' >&2
  echo "    El formato exacto es: **ETAPA 1:** T02 T03   (sólo identificadores, sin prosa)" >&2
  echo "    Se ignoran TODAS las etapas declaradas y se deducen de la tabla." >&2
elif [ "${CANONICAS:-0}" -gt 0 ]; then
  while IFS= read -r linea; do
    [ -n "$linea" ] && ETAPAS+=("$linea")
  done < <(grep -oE '^ *\*{0,2}ETAPA +[0-9]+\*{0,2}:\*{0,2} *[T0-9 ]+ *$' "$PLAN" \
           | sed 's/^[^:]*://; s/^\*\*//; s/^ *//; s/ *$//')
fi

if [ "${#ETAPAS[@]}" -eq 0 ]; then
  echo "· el plan no declara etapas; deduciendo de la tabla de tareas"
  SALIDA_ETAPAS="$(PLAN="$PLAN" python3 "$AQUI/_etapas.py")"; rc_etapas=$?
  if [ "$rc_etapas" -eq 2 ]; then
    echo "✗ $PLAN no tiene tabla de tareas: no hay nada que ejecutar." >&2
    echo "  El plan lo escribe el arquitecto y lo aprueba una persona (gate G0)." >&2
    exit 1
  fi
  while IFS= read -r linea; do
    [ -n "$linea" ] && ETAPAS+=("$linea")
  done <<< "$SALIDA_ETAPAS"
fi

# Distinto de "no pude leer el plan": el plan está bien y no queda nada pendiente.
if [ "${#ETAPAS[@]}" -eq 0 ]; then
  echo "✓ Todas las tareas de $PLAN están marcadas como hechas: no hay nada que lanzar."
  exit 0
fi

if [ "${SOLO_ETAPAS:-0}" = "1" ]; then
  echo "Plan con ${#ETAPAS[@]} etapa(s):"
  n=0; for etapa in "${ETAPAS[@]}"; do n=$((n+1)); echo "  ETAPA $n: $etapa"; done
  exit 0
fi

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
  HUELLAS="$(mktemp -d)"    # una huella de falla por tarea (bash 3.2 no tiene arrays asociativos)
  MUERTAS=()                # las que fallaron dos veces por lo mismo
  IMPOSIBLES=()             # las que el agente declaró imposibles
  while [ "${#pendientes[@]}" -gt 0 ] && [ "$intento" -le "$REINTENTOS" ]; do
    [ "$intento" -gt 1 ] && echo "── reintento $intento de: ${pendientes[*]}"
    bash "$AQUI/correr-tarea.sh" "${pendientes[@]}"

    # Quedan pendientes las que no dieron verde. El veredicto sale del gate, nunca del log
    # del agente (ver METODO.md P2).
    nuevas=()
    for t in "${pendientes[@]}"; do
      log="$RAIZ/../trabajo-$t/.tarea.log"
      v="$(veredicto "$log" 2>/dev/null)"
      [ "$v" = "VERDE" ] && continue

      # Reintentar una tarea que el agente declaró imposible es la presión que produce la
      # trampa. Se corta acá y decide una persona.
      if [ "$v" = "IMPOSIBLE" ]; then
        echo "  ⃠ $t: el agente la declaró imposible"
        echo "      $(motivo_imposible "$log")"
        IMPOSIBLES+=("$t")
        continue
      fi

      # Reintentar a ciegas gasta tiempo en la falla que no se va a ir sola. Si la huella
      # repite, es la misma falla y no hay nada nuevo que intentar: se detiene acá y decide
      # un humano. Si cambió, el reintento tiene sentido.
      h="$(huella_de_falla "$log")"
      anterior="$(cat "$HUELLAS/$t" 2>/dev/null || true)"
      if [ -n "$h" ] && [ "$h" = "$anterior" ]; then
        echo "  ✗ $t: punto muerto — falló dos veces por lo mismo:"
        echo "      $h"
        MUERTAS+=("$t")
      else
        [ -n "$anterior" ] && echo "  · $t: falló por otra cosa, reintentando"
        printf '%s' "$h" > "$HUELLAS/$t"
        nuevas+=("$t")
      fi
    done
    pendientes=("${nuevas[@]+"${nuevas[@]}"}")
    intento=$((intento+1))
  done
  rm -rf "$HUELLAS"

  if [ "${#pendientes[@]}" -gt 0 ] || [ "${#MUERTAS[@]}" -gt 0 ] || [ "${#IMPOSIBLES[@]}" -gt 0 ]; then
    echo
    echo "✗ La etapa $n se detuvo: ${pendientes[*]+${pendientes[*]}} ${MUERTAS[*]+${MUERTAS[*]}} ${IMPOSIBLES[*]+${IMPOSIBLES[*]}}"
    [ "${#MUERTAS[@]}" -gt 0 ] && echo "  En punto muerto (misma falla dos veces): ${MUERTAS[*]}"
    [ "${#IMPOSIBLES[@]}" -gt 0 ] && echo "  Declaradas imposibles por el agente: ${IMPOSIBLES[*]} — leé el motivo, suele ser cierto"
    echo "  Decide un humano (ver HUMANO.md §4):"
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
echo "Lo que sigue:"
echo "  1. G2 — leer los diffs (bash $AQUI/estado.sh te dice qué ramas hay)"
echo "  2. integrar: bash $AQUI/integrar.sh   — de a una, con el gate del tronco por merge"
echo "  3. G3 — USAR la cosa (las preguntas están en PLAN.md)"
echo "  4. G4 — bash $PROYECTO/scripts/pre-deploy.sh"
echo "  5. G5 — bash $PROYECTO/scripts/deploy.sh staging"
bash "$AQUI/metricas.sh" 2>/dev/null || true
