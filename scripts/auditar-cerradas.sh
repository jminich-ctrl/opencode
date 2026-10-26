#!/usr/bin/env bash
# ¿Las tareas YA CERRADAS pasarían el gate de hoy? Pasa lo viejo por los instrumentos nuevos.
#
#   bash scripts/auditar-cerradas.sh            # todas las ✅ hechas
#   bash scripts/auditar-cerradas.sh T04 T14    # sólo ésas
#
# POR QUÉ EXISTE. El método mejora sus instrumentos y los instrumentos nuevos encuentran
# cosas en lo ya cerrado — pero nada vuelve a pasar el material viejo por el instrumento
# nuevo. El gate corre cuando la tarea se cierra, y después nadie vuelve.
#
# Medido el 2026-10-25. Ese día se agregaron cuatro chequeos, y pasando a mano los nueve
# pares test↔implementación que el plan de clasificados permite preguntar aparecieron DOS
# verdes falsos entre 19 tareas cerradas:
#
#   · T04 — `backend/app/datos/users.py` no implementa nada: una función que devuelve None
#     y lo dice en su propio comentario («Por ahora retornamos None como placeholder»). Sus
#     tres tests la mockean. Con ese stub ningún usuario puede loguearse;
#   · T04b — su test fue reemplazado al arreglar el brazo nulo y el nuevo quedó ROJO en el
#     tronco desde entonces, sin que nadie se lo atribuyera. El arreglo del instrumento ya
#     había cobrado una pieza y nadie la recogió.
#
# No inventa instrumentos: corre los que el validador ya usa, sobre el material viejo.
# Tampoco toca nada — ni estados, ni código, ni plan. Informa, y reabrir es otra decisión y
# otro comando, con sus jueces.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto

PEDIDAS="$*"
hallazgos=0
mirados=0
saltadas=""
ARCH_MUT=""

# El test de cada tarea sale de la TABLA DE TESTS del plan, y se exige que el campo parezca
# una ruta: la tabla de tareas también tiene tres columnas y viene primero, así que un grep
# por la fila devuelve el título y la dependencia. Tercera vez que un extractor de este
# método lee la tabla de al lado.
# Y si el plan no tiene esa tabla, del ARCHIVO de la tarea, que es donde `reabrir.sh` ya lo
# busca para su paso 3. `ejemplo-pacman` no tiene tabla de tests: declara el test en cada
# tarea. Mirando sólo el plan, el auditor no servía en la mitad de los ejemplos — el mismo
# «el método sabe de clasificados y supone que todo es clasificados» que ya apareció tres
# veces en este repo.
test_de() {
  local t="$1" tf="$2" r=""
  r="$(awk -F'|' -v t="$t" '
    $2 ~ "^ *"t" *$" { gsub(/ |`/, "", $3); if ($3 ~ /\// && $3 ~ /\.[a-z]+$/) { print $3; exit } }
  ' "$BASE/PLAN.md" 2>/dev/null)"
  [ -n "$r" ] || r="$(sed -n 's/.*Archivo: `\([^`]*\)`.*/\1/p' "$tf" | head -1)"
  printf '%s' "$r"
}

for tf in "$BASE"/tareas/T*.md; do
  id="$(basename "$tf" | sed -E 's/^(T[0-9]+[a-z]?)-.*/\1/')"
  [ -z "$PEDIDAS" ] || echo " $PEDIDAS " | grep -q " $id " || continue
  grep -qE '^\*\*Estado:\*\* *(✅|hecha)' "$tf" || continue

  su_test="$(test_de "$id" "$tf")"
  impl="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "$tf" | tr ',' '\n' \
          | sed 's/^ *//; s/ *$//' | grep '\.py$' || true)"
  # Se acumulan ACÁ, antes de saber si la tarea es auditable: el paso de mutación de abajo
  # no necesita el par test↔implementación, y entonces alcanza a las tareas que los pasos 1
  # a 3 tienen que saltear. En `ejemplo-pacman` eso es la diferencia entre 2 y 19.
  for f in $impl; do
    [ -f "$BASE/$f" ] || continue
    case " $ARCH_MUT " in *" $f "*) ;; *) ARCH_MUT="${ARCH_MUT}${ARCH_MUT:+ }$f" ;; esac
  done
  if [ -z "$su_test" ] || [ ! -f "$BASE/$su_test" ]; then
    # NO se adivina por el nombre del archivo. `tareas/T01-laberinto.md` y
    # `tests/test_laberinto.py` se corresponden en pacman, y deducirlo sería inferir lo que
    # el plan no dice. Se informa el hueco con su sujeto y se sigue: 17 de las 19 tareas
    # cerradas de `ejemplo-pacman` no declaran su test en ninguna parte, así que ninguna es
    # auditable, y eso es un dato del plan y no una falla de esta herramienta.
    saltadas="${saltadas}${saltadas:+, }$id (ni el plan ni su archivo declaran su test)"
    continue
  fi
  if [ -z "$impl" ]; then
    saltadas="${saltadas}${saltadas:+, }$id (sin archivos .py declarados)"; continue
  fi

  rojo_de_esta=""
  vacios_de_esta=""
  # ── 1. ¿Su test pasa HOY? Un test aceptado que quedó rojo es un verde que nadie recogió.
  #
  # El rojo puede ser de la tarea o de una dependencia que todavía está pendiente, y el
  # mensaje no los confunde: lo que se afirma es que su verde NO SE SOSTIENE en este árbol,
  # que es verdad en los dos casos, y se nombra la causa cuando se puede distinguir. Lo que
  # no se hace es llamarlo defecto propio sin haberlo separado.
  if [ -f "$BASE/scripts/correr-suite.sh" ]; then
    if ! (cd "$BASE" && bash scripts/correr-suite.sh "$su_test" >/dev/null 2>&1); then
      deps="$(sed -n 's/^\*\*Depende de:\*\* *//p' "$tf" | head -1 | tr ',' ' ')"
      pend=""
      for d in $deps; do
        d="$(printf '%s' "$d" | tr -d ' `—')"
        [ -n "$d" ] || continue
        df="$(ls "$BASE/tareas/${d}"-*.md 2>/dev/null | head -1)"
        [ -n "$df" ] && ! grep -qE '^\*\*Estado:\*\* *(✅|hecha)' "$df" \
          && pend="${pend}${pend:+ }$d"
      done
      if [ -n "$pend" ]; then
        rojo_de_esta="${rojo_de_esta}
     ✗ su test $su_test está ROJO y la tarea está cerrada. Depende de $pend, que
       está pendiente: puede ser de ahí. No se sostiene su verde en este árbol."
      else
        rojo_de_esta="${rojo_de_esta}
     ✗ su test $su_test está ROJO en el tronco y la tarea está cerrada, sin
       ninguna dependencia pendiente que lo explique."
      fi
    fi
  fi
  # ── 2. ¿Tiene aserciones que no pueden fallar con ninguna implementación?
  if [ -f "$AQUI/_aserciones.py" ]; then
    sal="$(python3 "$AQUI/_aserciones.py" "$BASE/$su_test" 2>&1)"; rc_a=$?
    # El 2 —«no pude mirar»— se informa, no se descarta. Mirando sólo el 1, un test que no
    # parsea pasaba por auditado: el chequeo devolvía 2 y acá no lo leía nadie.
    case "$rc_a" in
      1) rojo_de_esta="${rojo_de_esta}
$(printf '%s' "$sal" | sed 's/^  /     /')" ;;
      2) vacios_de_esta="${vacios_de_esta}
$(printf '%s' "$sal" | sed 's/^  /     /')" ;;
    esac
  fi
  # ── 2b. ¿El test obliga un contrato que el enunciado no declara? El chequeo es nuevo del
  # 2026-10-25 y encontró DOS tests ya aceptados que lo hacen —T20 y T21—, así que es
  # exactamente el material que esta herramienta existe para revisar.
  if [ -f "$AQUI/_contrato.py" ]; then
    sal_c="$( (cd "$BASE" && python3 "$AQUI/_contrato.py" "$su_test" "${tf#$BASE/}" .) 2>&1 )"
    [ $? -eq 1 ] && rojo_de_esta="${rojo_de_esta}
$(printf '%s' "$sal_c" | sed 's/^  /     /')"
  fi
  # ── 3. El brazo nulo, archivo por archivo: ¿el test nota que cada archivo quedó sin cuerpo?
  for f in $impl; do
    [ -f "$BASE/$f" ] || continue
    sal_v="$( (cd "$BASE" && python3 "$AQUI/vaciar.py" "$f") 2>&1 )"; rc_v=$?
    if [ "$rc_v" = "3" ]; then
      rojo_de_esta="${rojo_de_esta}
$(printf '%s' "$sal_v" | sed 's/^  /     /')"
    elif [ "$rc_v" = "0" ] && [ -f "$BASE/scripts/correr-suite.sh" ]; then
      if (cd "$BASE" && bash scripts/correr-suite.sh "$su_test" >/dev/null 2>&1); then
        rojo_de_esta="${rojo_de_esta}
     ✗ el test pasa con los cuerpos de $f VACÍOS: no prueba ese archivo."
      fi
    fi
    (cd "$BASE" && python3 "$AQUI/vaciar.py" --restaurar >/dev/null 2>&1)
  done

  mirados=$((mirados+1))
  if [ -n "$rojo_de_esta" ]; then
    hallazgos=$((hallazgos+1))
    echo "✗ $id — cerrada, y no pasaría el gate de hoy:$rojo_de_esta$vacios_de_esta"
  elif [ -n "$vacios_de_esta" ]; then
    # Ni ✗ ni ·: hubo chequeos que no pudieron correr, y eso no es «pasa».
    echo "⊘ $id — auditada a medias:$vacios_de_esta"
  else
    echo "· $id — pasa los chequeos de hoy"
  fi
done

# ── 4. Mutación por ARCHIVO, el único paso que NO necesita el par test↔implementación.
#
# Por qué existe. El paso 4b del gate —mutar el diff de la tarea— es del 2026-10-25, así que
# ninguna tarea cerrada antes pasó por él; y los pasos 1 a 3 de arriba necesitan saber cuál
# es el test de cada tarea, que 17 de las 19 cerradas de `ejemplo-pacman` no declaran. Los
# ARCHIVOS los declaran las 19. Mutar no pide más que eso y la suite.
#
# Medido la primera vez que corrió, sobre ejemplo-pacman: 98 mutantes, 9 sobrevivientes, con
# 103 tests verdes y 19 de 19 tareas cerradas. Dos de los cuatro estilos de fantasma tenían
# su estrategia probada como función suelta y su USO sin probar: borrar la línea que la
# llama no rompía un solo test. Y `test_caduca_a_los_cincuenta_turnos` pasa igual si la
# fruta dura UN turno: afirma el estado final y no la duración que su nombre promete.
echo
echo "── mutación de los archivos declarados (no necesita saber cuál es el test)"
if [ -n "${SIN_MUTAR:-}" ]; then
  echo "  ⊘ salteada por SIN_MUTAR=1 — no pudo verificarse"
  echo "     No es un pase: nadie verificó que la suite distinga."
elif [ -z "$ARCH_MUT" ]; then
  echo "  ⊘ ninguna tarea cerrada declara un archivo .py que exista — no pudo verificarse"
  echo "     No es un pase: nadie verificó que la suite distinga."
elif [ ! -f "$BASE/scripts/correr-suite.sh" ]; then
  echo "  ⊘ el proyecto no declara cómo se corre su suite (scripts/correr-suite.sh)"
  echo "     No es un pase: nadie verificó que la suite distinga."
else
  # El árbol VACÍO como base, y no el primer commit: así cada archivo cuenta como nuevo y se
  # mutan todas sus líneas, que es lo que se quiere auditar. Con el primer commit, un
  # proyecto que se subió de una sola vez tendría cero líneas «cambiadas» y el paso saldría
  # ⊘ sin que nadie entienda por qué. `-w` escribe un objeto de árbol vacío, que es inerte.
  REF0="$(cd "$BASE" && git hash-object -w -t tree /dev/null)"
  CODIGO_MUT="$(for f in $ARCH_MUT; do dirname "$f"; done | sort -u | paste -sd, -)"
  sal_m="$( (cd "$BASE" && BASE="$REF0" CODIGO="$CODIGO_MUT" ARCHIVOS="$ARCH_MUT" \
             LIMITE="${LIMITE:-400}" SUITE="bash scripts/correr-suite.sh" \
             DETALLE="${DETALLE:-todos}" \
             python3 "$AQUI/mutar.py") 2>&1 )"; rc_m=$?
  printf '%s\n' "$sal_m"
  case "$rc_m" in
    0) ;;
    2) ;;   # ⊘: mutar.py ya imprime "No es un pase" con su motivo
    *) hallazgos=$((hallazgos+1)) ;;
  esac
fi

echo
echo "$mirados tarea(s) cerrada(s) auditada(s)"
[ -n "$saltadas" ] && echo "  ⊘ sin material para preguntar: $saltadas"
if [ "$hallazgos" -gt 0 ]; then
  echo "✗ $hallazgos con hallazgos. Reabrir es otra decisión: scripts/reabrir.sh TNN[,TMM] \"motivo\""
  exit 1
fi
# CERO auditadas no es un ✓, y mi primera versión lo informaba así: «✓ ninguna tarea cerrada
# falla los chequeos de hoy» después de preguntar por ninguna. Es el defecto que este método
# viene combatiendo todo el día —un chequeo que no pudo correr diciendo que pasó— y lo
# introduje en la herramienta que vine a escribir para encontrarlo. Lo encontró la primera
# corrida sobre `ejemplo-pacman`, donde no pudo leer un solo test.
if [ "$mirados" -eq 0 ]; then
  echo "⊘ no se auditó NINGUNA tarea: esto no es un pase, es que no se pudo preguntar."
  echo "   Revisá que el plan reparta los tests, o que las tareas los declaren."
  exit 2
fi
echo "✓ las $mirados tarea(s) cerrada(s) auditada(s) pasan los chequeos de hoy"
