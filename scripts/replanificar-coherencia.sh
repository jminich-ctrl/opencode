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
cargar_entorno_colabhive

# ── El motivo, del chequeo y no de mi lectura del chequeo.
ROJOS="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" 2>&1 | grep '✗' || true)"
if [ -z "$ROJOS" ]; then
  echo "✓ el preflight no tiene rojos: no hay nada que replanificar"
  exit 0
fi
# Las tablas que YA existen, para ponerlas en el prompt. Sin esto el agente se las va a
# buscar, y buscar es justo lo que no entra en el techo de la sesión: medido, la corrida de
# T26 leyó cinco archivos —el enunciado, la migración, `auth.py`, `datos/users.py` y el
# test— antes de que la memoria la cortara. No decide por él: cuál de las dos salidas tomar
# sigue siendo del que planifica.
TABLAS="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" --tablas 2>/dev/null | tr '\n' '; ')"
echo "▶ el arquitecto replanifica el plan. Lo que el preflight encontró:"
printf '%s\n' "$ROJOS" | sed 's/^/     /'

# Lo que no se toca, medido ANTES, para poder verificarlo después.
CRIT_ANTES="$(cat "$BASE"/tareas/*.md 2>/dev/null | grep -c '^- \[ \]' || true)"
TESTS_ANTES="$(grep -ohE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`[^|]*clase `[A-Za-z0-9_]+`' \
               "$BASE"/tareas/*.md 2>/dev/null | sort || true)"
PREVIO="$BASE/.tareas-previo"
rm -rf "$PREVIO"; cp -R "$BASE/tareas" "$PREVIO"
restaurar() { rm -rf "$BASE/tareas"; mv "$PREVIO" "$BASE/tareas"; }

# UNA CORRIDA POR ROJO, y no una sola con todos.
#
# Medido el 2026-10-21, porque las primeras cuatro corridas de este script murieron con
# `memory_delivery_unavailable` y yo se lo cobré a la plataforma tres veces. La tabla
# completa, con el mismo agente y el mismo prompt variando sólo el techo de tiempo:
#
#   240s directo, 300s directo, 240s con con_limite  → cortadas por alarma, TRABAJANDO
#   1800s por este script, cuatro veces              → memory_* a los 8-13 min
#   900s directo, sin script                         → memory_session_expired a los 7:03
#   420s directo, UN rojo, prompt de 541 caracteres  → ✓ hecho en 4:09
#
# Ninguna murió antes de los 5 minutos; ninguna sobrevivió más de 13. O sea: la sesión de
# memoria de ColabHive tiene un techo de unos pocos minutos, y el pedido que no entra ahí no
# falla por su contenido sino por su tamaño. Partirlo es la única palanca del método.
#
# Y NO se baja `LIMITE_AGENTE`: el principio que este repo ya tiene escrito es que un
# vigilante tiene que perder la carrera contra el error que la herramienta vigilada sabe
# informar. La plataforma informa su corte con un mensaje claro; si el límite del método
# cortara antes, taparía ese mensaje con un cuelgue sin causa. Lo que se achica es el
# TRABAJO por corrida, no la paciencia.
export LOG_VIGILADO="$BASE/.replan-coherencia.log"
: > "$LOG_VIGILADO"
n=0; fallo=""
# El bucle lee de un heredoc y NO de una tubería: `printf | while` corre el cuerpo en un
# subshell, así que `fallo` y `n` volverían vacíos al terminar y el script informaría que
# todos los rojos se trataron bien cuando ninguno lo hizo.
while IFS= read -r rojo; do
  [ -n "$rojo" ] || continue
  n=$((n+1))
  # De qué tarea es, para nombrarle el archivo exacto: con la ruta en el prompt, la corrida
  # que anduvo tardó 4:09; sin ella, el agente gasta el techo buscando.
  tid="$(printf '%s\n' "$rojo" | grep -oE '\bT[0-9]+[a-z]?\b' | head -1)"
  arch="$(cd "$BASE" && ls tareas/${tid}-*.md 2>/dev/null | head -1)"
  if [ -z "$arch" ]; then
    echo "  ⊘ rojo $n: no pude ubicar el archivo de «${tid}», lo salteo"
    fallo="${fallo:+$fallo; }$tid sin archivo"
    continue
  fi
  echo "  · rojo $n/$(printf '%s\n' "$ROJOS" | grep -c .): $tid → $arch"
  (
    cd "$BASE" || exit 1
    export XDG_DATA_HOME="$BASE/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    if [ -n "${MODELO:-}" ]; then COMO=(--model "colabhive/$MODELO"); else COMO=(--agent arquitecto); fi
    con_limite "${LIMITE_AGENTE:-1800}" opencode run "${COMO[@]}" \
      "Editá UN SOLO archivo: $arch. El preflight del plan encontró esto: $rojo. Las tablas que las migraciones YA crean son: ${TABLAS:-ninguna}. Abrí $arch con read y corregilo con write. NO leas código ni tests: la decisión está entre ese enunciado y esa lista, y nada más. Tenés dos salidas y elegís vos: (a) que el enunciado use una tabla de la lista, o (b) que el enunciado prometa CREAR la tabla que nombra, con las palabras 'crear la tabla'. No cambies nada más del archivo: ni los criterios de terminado, ni el archivo de test, ni el nombre de su clase. Si no se puede resolver sin inventar una decisión de producto, no edites y decilo con la palabra HUECO." 2>&1
  ) >> "$LOG_VIGILADO" 2>&1
  rc=$?
  if [ "$rc" = 142 ]; then
    fallo="${fallo:+$fallo; }$tid: $(motivo_del_corte "$LOG_VIGILADO")"
  else
    err="$(error_del_agente "$LOG_VIGILADO" 2>/dev/null)"
    [ -n "$err" ] && fallo="${fallo:+$fallo; }$tid: $err"
  fi
done <<ROJOS_FIN
$ROJOS
ROJOS_FIN
[ -n "$fallo" ] && echo "  ⚠ no todos los rojos se pudieron tratar: $fallo"

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
