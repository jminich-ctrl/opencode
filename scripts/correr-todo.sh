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
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
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

# Y la plataforma tiene que responder. Arrancar diez etapas contra una API caída gasta
# horas de reintentos y produce diagnósticos que señalan al agente.
if [ "$SOLO_VER" != "1" ]; then
  plataforma_responde || exit 1
fi

# Y los contextos declarados tienen que ser los reales. Declarar `limit.context` más
# grande que el `max_model_len` del servido hace que CADA tarea muera con un 400 que no se
# parece a su causa: el método lo informaba como «el agente no escribió el test». Pasó con
# un modelo servido con 5312 tokens cuya ficha nominal dice 128000 — la ficha del modelo no
# es el contrato del endpoint.
#
# `sync_limits.py` existía desde hacía semanas y hasta estaba nombrado en INFRAESTRUCTURA.md
# como la respuesta exacta a ese 400, pero era un paso manual de un runbook. Una cura que
# depende de que alguien se acuerde no es parte del método: es documentación.
if [ "$SOLO_VER" != "1" ] && [ -f "$AQUI/../colabhive/scripts/sync_limits.py" ]; then
  DRIFT="$(python3 "$AQUI/../colabhive/scripts/sync_limits.py" 2>/dev/null | grep -E '^  →' || true)"
  if [ -n "$DRIFT" ]; then
    echo "✗ los contextos declarados no son los que sirve la plataforma:" >&2
    echo "$DRIFT" | head -6 | sed 's/^/  /' >&2
    echo "  Cada tarea moriría con un 400 que no se parece a su causa. Corregilo con:" >&2
    echo "    python3 $AQUI/../colabhive/scripts/sync_limits.py --write" >&2
    exit 1
  fi
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
# Y el cruce ENTRE tareas, que `validar-plan.py` no hace: mira una tarea a la vez.
# Los dos defectos más caros del 2026-10-19 eran de a dos tareas — una exigía autorización sin
# dar el medio, otra pedía un hash que el login no puede verificar— y las dos pasaban sus
# propios tests. Cuesta un segundo acá y costó una hora de agente no tenerlo.
if [ -f "$AQUI/coherencia.py" ]; then
  if ! PROYECTO="$BASE" python3 "$AQUI/coherencia.py"; then
    echo
    echo "✗ el plan se contradice entre tareas. Una tarea que importa algo que nadie provee no"
    echo "  es ejecutable: el agente lo va a inventar, y después va a iterar contra su propio"
    echo "  ImportError hasta agotar el tiempo. Eso lo decide quien planifica, no el agente."
    exit 1
  fi
fi

(cd "$BASE" && ENCARGO="${ENCARGO:-OBJETIVO.md}" PLAN=PLAN.md python3 "$AQUI/cobertura.py") || {
  echo "✗ El plan no cubre el encargo. Eso se decide arriba, no acá." >&2; exit 1; }

ETAPAS_TXT="$(SOLO_ETAPAS=1 bash "$AQUI/correr-plan.sh" 2>/dev/null | sed -n 's/^  ETAPA [0-9]*: //p')"
[ -n "$ETAPAS_TXT" ] || { echo "✗ No pude deducir las etapas del plan" >&2; exit 1; }

ETAPAS=()
while IFS= read -r l; do [ -n "$l" ] && ETAPAS+=("$l"); done <<< "$ETAPAS_TXT"
echo "══ ${#ETAPAS[@]} etapa(s); empezando en la $DESDE"

# Una sola corrida a la vez. Dos sobre los mismos worktrees se pisan —cada tarea borra y
# recrea el suyo—, y mientras una corre nadie puede editar los scripts: bash lee el archivo
# por posición mientras ejecuta, así que insertar líneas en un script en curso le hace
# ejecutar basura. Está escrito en METODO.md «Tres cosas que muerden» y lo incumplí igual,
# con la regla a la vista. Una regla que vive sólo en un documento es una regla que se
# incumple.
OTRA="$(pgrep -f "correr-todo\.sh" | grep -v "^$$\$" | head -1 || true)"
if [ -n "$OTRA" ] && [ "$SOLO_VER" != "1" ]; then
  echo "✗ Ya hay una corrida activa (pid $OTRA)." >&2
  echo "  Dos corridas se pisan: cada tarea borra y recrea su worktree. Y mientras una" >&2
  echo "  corre, editar un script le hace ejecutar basura —bash lo lee por posición—." >&2
  echo "  Esperá a que termine, o cortala: kill $OTRA" >&2
  exit 1
fi

# Los números de etapa NO son estables entre corridas. Las etapas se deducen del grafo de
# dependencias sobre las tareas PENDIENTES, así que en cuanto una cierra, las que siguen se
# corren un lugar. Pasó: la etapa 1 era «T06a T08» y la 2 «T06b T12 T29»; al cerrar la 1, la
# 2 pasó a ser la 1, y retomar con `correr-todo.sh 2` salteó tres tareas sin un solo aviso.
#
# El argumento existe para retomar después de arreglar algo, y eso es legítimo. Lo que no
# puede es saltar trabajo callado.
if [ "$DESDE" -gt 1 ] 2>/dev/null; then
  SALTEADAS=""
  i=0
  for etapa in "${ETAPAS[@]}"; do
    i=$((i+1)); [ "$i" -lt "$DESDE" ] || break
    SALTEADAS="$SALTEADAS $etapa"
  done
  if [ -n "$(echo "$SALTEADAS" | tr -d ' ')" ]; then
    echo "✗ Al empezar en la etapa $DESDE se saltean tareas que siguen pendientes:$SALTEADAS" >&2
    echo "  Los números de etapa se recalculan en cada corrida: al cerrar una etapa, las" >&2
    echo "  que siguen se corren un lugar. El número que anotaste ya no significa lo mismo." >&2
    echo "  Corré sin argumento —arranca en la primera etapa con trabajo pendiente—:" >&2
    echo "    bash $AQUI/correr-todo.sh" >&2
    exit 1
  fi
fi

parar() {
  echo
  echo "⏸  Se detuvo en la etapa $1: $2"
  echo "   Decide una persona (HUMANO.md §4). Para retomar después de arreglarlo:"
  # El tercer argumento es el comando PRECISO, cuando el que para sabe uno mejor.
  # `correr-todo.sh N` re-corre la etapa ENTERA: si lo que falló fue la integración, eso
  # borra los worktrees que ya estaban en VERDE y manda a rehacer las implementaciones. Me
  # pasó hoy: la etapa 1 frenó en 3/3 con T04b y T26 las dos verdes, seguí este mensaje al
  # pie de la letra y tiré las dos. Los commits se recuperan del reflog, pero el mensaje no
  # avisaba de nada.
  if [ -n "${3:-}" ]; then
    echo "     $3"
    echo "   NO uses \`correr-todo.sh $1\`: re-corre la etapa entera y tira los worktrees"
    echo "   que ya están en verde. Los de esta etapa están en: git worktree list"
  else
    echo "     bash $AQUI/correr-todo.sh $1"
  fi
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

  # 0.a Los modelos calientes, antes de medir nada contra ellos. `min_replicas: 1` no es
  # autocurativo —configurado 1, corriendo 0— así que un modelo evacuado tarda ~253s en
  # arrancar y durante ese arranque el agente no imprime NADA. El vigilante de inactividad
  # corta a los 45s, así que sin calentar primero mataríamos arranques legítimos y lo
  # informaríamos como cuelgue. Es la misma trampa de siempre: el umbral sólo es válido si
  # la condición que mide es la que uno cree.
  if command -v oc >/dev/null 2>&1; then
    # Se informa lo que dijo, no se juzga: `oc --warm` avisa «quedaron modelos fríos» cuando
    # alguno del equipo no se pudo levantar, y puede ser uno que esta corrida no usa. Quien
    # sabe si importa es la herramienta del proyecto, no este script.
    SALIDA_WARM="$(con_limite 240 oc --warm 2>&1)"
    echo "$SALIDA_WARM" | grep -E '^ *[●◐○]' | sed 's/^/  /' || true
    echo "$SALIDA_WARM" | grep -q "Quedaron modelos fríos" \
      && echo "  ⊘ quedaron modelos fríos: si la corrida usa uno de ésos, su arranque (~253s" \
      && echo "     sin imprimir nada) se va a ver como un cuelgue y el vigilante lo va a cortar"
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
  # Por NOMBRE, no por índice: correr-plan.sh re-deduce las etapas y el mismo número
  # nombraba grupos distintos en los dos lados. Salteó T05 el 2026-10-19 — ver el comentario
  # largo en correr-plan.sh.
  SOLO_UNA=1 bash "$AQUI/correr-plan.sh" "${tareas[@]}" || true

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
  bash "$AQUI/integrar.sh" "${tareas[@]}" \
    || parar "$n" "la integración no cerró" \
             "bash $AQUI/integrar.sh ${tareas[*]}"
  echo "✓ etapa $n completa"
done

echo
echo "══ Todas las etapas en verde."
echo "Lo que sigue lo hace una persona:"
echo "  1. G3 — USÁ la cosa. Las preguntas están en PLAN.md."
echo "  2. G4 — bash $BASE/scripts/pre-deploy.sh"
echo "  3. G5 — bash $BASE/scripts/deploy.sh staging"
bash "$AQUI/metricas.sh" 2>/dev/null || true
