#!/usr/bin/env bash
# Ejecuta un plan entero: etapa por etapa, en paralelo dentro de cada etapa.
#
#   bash scripts/correr-plan.sh              # de la primera etapa a la última
#   bash scripts/correr-plan.sh 3            # desde la etapa 3
#   REINTENTOS=2 bash scripts/correr-plan.sh # cuántas veces relanzar una tarea roja
#   SOLO_UNA=1 bash scripts/correr-plan.sh 3  # la etapa 3 y nada más (lo usa correr-todo.sh)
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
# Los argumentos son un ÍNDICE de etapa (uso humano) o la LISTA DE TAREAS (uso de
# correr-todo.sh). Lo segundo existe porque pasar un índice era un defecto: correr-todo.sh
# le pasaba su `$n` y este script **re-deduce** las etapas por su cuenta, así que el mismo
# número nombraba grupos distintos en cada lado.
#
# Pasó el 2026-10-19: la fase de tests corrió «ETAPA 2/8: T05» y la fase de tareas,
# re-deduciendo con T04b y T26 ya hechas, tomó SU etapa 2 —T14 T20 T11 T28— y salteó T05,
# que quedó con su test rojo en el tronco y sin implementación. Nadie se enteró hasta que
# alguien miró dos líneas del log que decían 8 etapas y 7.
#
# Este mismo archivo ya documenta que los números de etapa no son estables entre corridas, y
# correr-todo.sh tiene un guardia para el `--desde` que da el humano. El arreglo estaba de un
# lado y no del otro: la forma que este repo repite. La declaración tiene que LLEVAR lo que
# significa, no un puntero a una lista que el lector reconstruye.
TAREAS_PEDIDAS=()
for a in "$@"; do
  case "$a" in T[0-9]*) TAREAS_PEDIDAS+=("$a") ;; esac
done
if [ "${#TAREAS_PEDIDAS[@]}" -gt 0 ]; then
  if [ "${#TAREAS_PEDIDAS[@]}" -ne "$#" ]; then
    echo "✗ o un índice de etapa, o una lista de tareas — no las dos cosas: $*" >&2
    exit 1
  fi
  DESDE=1
else
  DESDE="${1:-1}"
fi
REINTENTOS="${REINTENTOS:-2}"

PLAN="$BASE/PLAN.md"
[ -f "$PLAN" ] || { echo "✗ No encuentro $PLAN (el plan es el gate G0: sin plan no se ejecuta)" >&2; exit 1; }

# Etapas declaradas explícitamente, o deducidas de la tabla del plan.
# Sin `mapfile`: es de bash 4 y macOS trae 3.2. Este script no corría por eso.
ETAPAS=()
# Si el llamador NOMBRÓ las tareas, ésa es la etapa y no se deduce nada: así el índice no
# puede significar una cosa acá y otra allá.
if [ "${#TAREAS_PEDIDAS[@]}" -gt 0 ]; then
  ETAPAS=("${TAREAS_PEDIDAS[*]}")
fi
# Formato canónico: `**ETAPA 1:** T02 T03`, sólo identificadores. El cierre de negrita de
# markdown va después de los dos puntos, y se acepta con o sin asteriscos.
CANONICAS=0; PARECIDAS=0
if [ "${#ETAPAS[@]}" -eq 0 ]; then
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
fi

if [ "${#ETAPAS[@]}" -eq 0 ]; then
  echo "· el plan no declara etapas; deduciendo de la tabla de tareas"
  SALIDA_ETAPAS="$(PLAN="$PLAN" python3 "$AQUI/_etapas.py")"; rc_etapas=$?
  if [ "$rc_etapas" -eq 2 ]; then
    echo "✗ $PLAN no tiene tabla de tareas: no hay nada que ejecutar." >&2
    echo "  El plan lo escribe el arquitecto y lo aprueba una persona (gate G0)." >&2
    exit 1
  fi
  # Código 1 = `_etapas.py` NO pudo ordenar el plan (un ciclo, o una dependencia a una tarea
  # que no está en la tabla). Se miraba sólo el 2, así que el 1 seguía de largo con la salida
  # vacía —todo el diagnóstico de `_etapas.py` va a stderr— y veinte líneas más abajo el
  # `${#ETAPAS[@]}` -eq 0 lo informaba como «✓ Todas las tareas están marcadas como hechas:
  # no hay nada que lanzar», con código 0.
  #
  # Era un VEREDICTO FALSO en una de las cinco puertas: cero tareas ejecutadas, reportadas
  # como plan terminado. Y alcanzable de verdad, porque `validar-plan.py` tampoco detectaba
  # los ciclos (se arregló junto con esto): el plan cíclico pasaba G0 entero.
  #
  # «Etapas vacías» y «el plan no se pudo ordenar» son estados distintos y el único que los
  # distingue es el código de salida: con todo ✅, `_etapas.py` también sale con stdout vacío,
  # pero con 0.
  if [ "$rc_etapas" -ne 0 ]; then
    echo "✗ no pude calcular el orden de las tareas de $PLAN: el plan no es ejecutable." >&2
    echo "  El motivo está arriba, y lo arregla quien planifica — no es una tarea terminada." >&2
    exit 1
  fi
  while IFS= read -r linea; do
    [ -n "$linea" ] && ETAPAS+=("$linea")
  done <<< "$SALIDA_ETAPAS"
fi

# Las etapas DECLARADAS se filtran por estado igual que las deducidas. `_etapas.py` ya
# filtraba las hechas; la rama que lee `**ETAPA n:**` las tomaba al pie de la letra, y la
# plantilla de PLAN.md enseña a declararlas — así que el camino documentado perdía el filtro.
#
# Medido el 2026-10-26 en un proyecto JS con tres tareas hechas y dos pendientes: relanzó la
# ETAPA 1 COMPLETA. Tres corridas de agente gastadas, el gate contestando «no hay ningún
# cambio: la tarea no se hizo» —cierto y engañoso, porque no había nada que hacer—, dos tareas
# en «punto muerto» por fallar dos veces por lo mismo, y el plan detenido SIN llegar a la etapa
# pendiente. Se nota en la SEGUNDA corrida del plan, que es la normal: la primera algo falla y
# se vuelve a lanzar.
#
# Si el llamador NOMBRÓ las tareas, no se filtra: pedir T01 a mano es pedirla, hecha o no.
if [ "${#ETAPAS[@]}" -gt 0 ] && [ "${#TAREAS_PEDIDAS[@]}" -eq 0 ]; then
  SIN_HECHAS=(); YA_HECHAS=""
  for etapa in "${ETAPAS[@]}"; do
    queda=""
    for t in $etapa; do
      tf="$(ls "$BASE/tareas/${t}"-*.md 2>/dev/null | head -1)"
      if [ -n "$tf" ] && grep -qE '^\*\*Estado:\*\* *(✅|hecha)' "$tf"; then
        YA_HECHAS="${YA_HECHAS}${YA_HECHAS:+ }$t"
      else
        queda="${queda}${queda:+ }$t"
      fi
    done
    [ -n "$queda" ] && SIN_HECHAS+=("$queda")
  done
  [ -n "$YA_HECHAS" ] && echo "· ya hechas, no se relanzan: $YA_HECHAS"
  ETAPAS=(${SIN_HECHAS[@]+"${SIN_HECHAS[@]}"})
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

# `${ETAPAS[@]+...}` y no `"${ETAPAS[@]}"`: en bash 3.2 —el que trae macOS—
# expandir un array VACÍO con `set -u` no imprime mal, ABORTA el script. Hoy un
# `exit 0` anterior lo intercepta, pero esa garantía la rompe mover una línea.
rechazar_salteo "$DESDE" "bash $AQUI/correr-plan.sh" ${ETAPAS[@]+"${ETAPAS[@]}"}
# Antes de la primera etapa: ¿están arriba TODOS los modelos que la corrida va a usar? Esta
# sonda existe desde que el 27B estuvo tres horas caído con el ejecutor contestando 200 —el
# preflight daba verde y la corrida moría en la primera replanificación, informando que falló
# la tarea— y estaba cableada sólo en `correr-todo.sh`. Esta puerta es la que enseña la
# plantilla de PLAN.md. En modo manual no se pide: ahí no hay agente que dependa de ellos.
if [ "${MANUAL:-0}" != "1" ] && command -v opencode >/dev/null 2>&1; then
  if ! plataforma_responde_la_corrida; then
    echo "✗ no se lanza el plan: hay modelos de esta corrida que no responden." >&2
    exit 1
  fi
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
  ENTORNO=()                # las que fallaron por el entorno: no son de la tarea
  while [ "${#pendientes[@]}" -gt 0 ] && [ "$intento" -le "$REINTENTOS" ]; do
    [ "$intento" -gt 1 ] && echo "── reintento $intento de: ${pendientes[*]}"
    # El reintento lleva una DESCRIPCIÓN de lo que falló, no la salida cruda. Medido: tener
    # la forma literal de una llamada fallida en el contexto sube la probabilidad de
    # repetirla de 0,06 a 0,54, y el 83% de ese daño es la forma; una descripción quita el
    # 76%. Y el 79% de las fallas tras refinar eran por falta de información, no por el
    # modelo. Se pasa de a una tarea para que cada una reciba su propio motivo.
    if [ "$intento" -gt 1 ]; then
      for t in "${pendientes[@]}"; do
        MOTIVO="$(cat "$HUELLAS/$t" 2>/dev/null || true)" \
          bash "$AQUI/correr-tarea.sh" "$t"
      done
    else
      bash "$AQUI/correr-tarea.sh" "${pendientes[@]}"
    fi

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
      # Un veredicto de ENTORNO no es una falla de la tarea, así que no entra en el juego
      # de huellas: reintentar no la arregla y declararla en punto muerto le cobra a la
      # tarea una diferencia del entorno. Es la misma regla que ya rige para los cortes de
      # plataforma en `escribir-tests.sh`, y el gate la emite con `ENTORNO_MOVIDO`.
      #
      # Cadáver del 2026-10-21: T05a, que toca un solo archivo de datos de avisos, quedó en
      # punto muerto acusada de romper el hasheo de contraseñas. La causa era
      # `Table 'clasificados.users' doesn't exist` en el MySQL que comparten todos los
      # worktrees. Dos intentos y el plan detenido por algo que la tarea no podía causar.
      if grep -q 'ENTORNO_MOVIDO' "$log" 2>/dev/null; then
        echo "  ⊘ $t: el entorno se movió, no es la tarea. No se reintenta contra ella."
        grep -m2 '     causa: ' "$log" 2>/dev/null | sed 's/^ */      /'
        echo "      El MySQL del proyecto lo comparten todos los worktrees: lo que una"
        echo "      etapa deja, la siguiente lo encuentra. Log: $log"
        ENTORNO+=("$t")
        continue
      fi

      h="$(huella_de_falla "$log")"
      anterior="$(cat "$HUELLAS/$t" 2>/dev/null || true)"
      if [ -n "$h" ] && [ "$h" = "$anterior" ]; then
        echo "  ✗ $t: punto muerto — falló dos veces por lo mismo:"
        echo "      $h"
        # Y qué significa, cuando se puede decir: ver `explicar_punto_muerto` en _comun.sh.
        explicar_punto_muerto "$h" "$t"
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

  if [ "${#ENTORNO[@]}" -gt 0 ]; then
    echo "  ⊘ el entorno se movió en: ${ENTORNO[*]}"
    echo "     No es la tarea ni el modelo. La base de datos del proyecto no estaba en el"
    echo "     estado que la línea base vio. Arreglá el entorno y relanzá: no hay nada que"
    echo "     cambiarle al plan ni al enunciado."
  fi
  if [ "${#pendientes[@]}" -gt 0 ] || [ "${#MUERTAS[@]}" -gt 0 ] || [ "${#IMPOSIBLES[@]}" -gt 0 ] || [ "${#ENTORNO[@]}" -gt 0 ]; then
    echo
    echo "✗ La etapa $n se detuvo: ${pendientes[*]+${pendientes[*]}} ${MUERTAS[*]+${MUERTAS[*]}} ${IMPOSIBLES[*]+${IMPOSIBLES[*]}}"
    [ "${#MUERTAS[@]}" -gt 0 ] && echo "  En punto muerto (misma falla dos veces): ${MUERTAS[*]}"
    [ "${#IMPOSIBLES[@]}" -gt 0 ] && echo "  Declaradas imposibles por el agente: ${IMPOSIBLES[*]} — leé el motivo, suele ser cierto"
    echo "  Decide un humano (ver HUMANO.md §4):"
    echo "    · si el rojo es del TEST —arriba se dice cuando se puede afirmar—, arreglá el test:"
    echo "      las otras tres salidas no lo arreglan,"
    echo "    · relanzar con el error pegado en la tarea,"
    echo "    · partir la tarea en dos,"
    echo "    · o hacerla a mano."
    echo "  Logs: $RAIZ/../trabajo-TNN/.tarea.log"
    exit 1
  fi

  echo "✓ etapa $n completa"
  echo
  # correr-todo.sh intercala la integración entre etapas, así que necesita pedir una sola.
  [ "${SOLO_UNA:-0}" = "1" ] && break
done

echo "══ Todas las etapas en verde."
echo "Lo que sigue:"
echo "  1. G2 — leer los diffs (bash $AQUI/estado.sh te dice qué ramas hay)"
echo "  2. integrar: bash $AQUI/integrar.sh   — de a una, con el gate del tronco por merge"
echo "  3. G3 — USAR la cosa. Las preguntas, del plan:"
preguntas_de_g3 "$PLAN" || true
echo "  4. G4 — bash $PROYECTO/scripts/pre-deploy.sh"
echo "  5. G5 — bash $PROYECTO/scripts/deploy.sh staging"
bash "$AQUI/metricas.sh" 2>/dev/null || true
