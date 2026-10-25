#!/usr/bin/env bash
# Reabre una tarea cuyo gate dio un veredicto FALSO.
#
#   bash scripts/reabrir.sh T20 "su código consulta columnas que la migración no crea"
#
# POR QUÉ EXISTE. `coherencia.py` termina sus rojos más graves con «Su gate dio un veredicto
# falso: ese código no puede funcionar. Hay que REABRIR TNN, no parchear a mano» — y el
# método no tenía con qué. O sea que ordenaba una operación y dejaba su ejecución a mano,
# que es de donde este repo dice, en varios comentarios, que vienen sus defectos: «Lo creamos
# nosotros editando a mano, que es cómo pasa siempre».
#
# Reabrir son CUATRO cosas y hacer tres está peor que no hacer ninguna:
#
#   1. el estado en el ARCHIVO de la tarea;
#   2. el estado en la TABLA del plan. `validar-plan.py` cruza las dos y el deductor de
#      etapas lee la tabla: marcar sólo una deja la tarea invisible para uno de los dos
#      lectores. Ya pasó al revés —T01 se integró, quedó verde, y la etapa 1 la relanzaba—;
#   3. SACAR el código que la tarea produjo. La fase que escribe los tests valida que el test
#      FALLE antes de que exista la implementación; con el código viejo en su lugar el test
#      pasa de entrada y el gate concluye «el test no prueba nada», que es el diagnóstico
#      equivocado. Se saca lo que la tarea DECLARA y nada más;
#   4. dejar escrito POR QUÉ, para que el agente que la retome no tenga que adivinar.
#
# Y un juez al final: si el plan deja de validar, o si la nota de reapertura AGREGA
# contradicciones nuevas, se revierte todo. Eso último no es teórico: una nota de reapertura
# que nombraba la tabla equivocada entre backticks fue leída por el propio chequeo de
# coherencia como un enunciado que promete usarla.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
[ $# -ge 1 ] || { echo "uso: $0 TNN[,TMM,...] [motivo]" >&2; exit 1; }
# VARIAS tareas, separadas por coma. Dos tareas pueden compartir un archivo —T04 y T04b
# comparten `backend/app/servicios/auth.py`, la segunda extiende lo que escribió la
# primera— y entonces reabrir una sola es imposible: el tercer juez la frena, con razón,
# porque dejaría a la otra con su verde cobrado y su código afuera. La cascada no es una
# comodidad, es la única forma de reabrir en ese caso, y el juez ya dice con nombre propio
# cuáles van juntas.
#
# Separadas por coma y no por espacios para que el motivo no se confunda con un id.
IDS="$(printf '%s' "$1" | tr ',' ' ')"
MOTIVO="${2:-su gate dio un veredicto falso}"

ARCHIVOS_TAREA=""
for ID in $IDS; do
  a="$(ls "$BASE/tareas/${ID}"-*.md 2>/dev/null | head -1)"
  [ -n "$a" ] || { echo "✗ $ID: no existe tareas/${ID}-*.md" >&2; exit 1; }
  ARCHIVOS_TAREA="$ARCHIVOS_TAREA $a"
done

# Los rojos de ANTES, para poder comparar: lo que importa no es que queden rojos —el que
# motivó la reapertura puede seguir ahí hasta que la tarea corra— sino que no aparezcan
# NUEVOS por culpa de lo que escribimos acá.
rojos_antes="$( (cd "$BASE" && PROYECTO=. python3 "$AQUI/coherencia.py" 2>&1 | grep -c '✗') || true)"

# Para el tercer juez: qué tareas CERRADAS declaran alguno de los archivos que vamos a
# sacar. Reabrir rompe el test de la tarea que reabre —eso es tests-first y es el punto—,
# pero no puede romper el de una tarea que sigue marcada como hecha: ésa queda con su verde
# cobrado y su código afuera, y el rojo se lo va a cobrar la próxima tarea que corra.
#
# Medido el 2026-10-25 reabriendo T04: dejó 4 tests en error, uno de ellos `test_sesion.py`,
# que es de T04b — una tarea ✅ hecha que declara el mismo `backend/app/servicios/auth.py`.
# Los dos jueces que había miraban el plan y las contradicciones, y ninguno el árbol.
#
# NO se rasca la salida de la suite, y esa fue la primera versión: buscaba `FAILED ruta::test`
# y `ERROR ruta`, que es el formato de pytest. La plantilla `correr-suite.sh` de un proyecto
# con unittest imprime `FAILED (errors=2)`, así que el grep matcheaba eso como si fuera un
# nombre de test y el juez quedaba comparando basura — fallando ABIERTO en todo proyecto
# unittest, que es la mitad de los ejemplos. Quinta vez que el que raspa busca una forma que
# el productor no emite.
#
# Lo único que se usa es el CÓDIGO DE SALIDA de `correr-suite.sh`, que es el contrato que el
# gate ya usa para juzgar, y se corre sólo el test de las tareas candidatas: las cerradas que
# declaran un archivo que estamos sacando. Son una o dos, no toda la suite.

RESPALDO="$RAIZ/../reabrir-$(printf '%s' "$IDS" | tr ' ' '+')-previo"
rm -rf "$RESPALDO"; mkdir -p "$RESPALDO"
for archivo in $ARCHIVOS_TAREA; do cp "$archivo" "$RESPALDO/$(basename "$archivo")"; done
[ -f "$BASE/PLAN.md" ] && cp "$BASE/PLAN.md" "$RESPALDO/PLAN.md"

echo "▶ reabriendo $(printf '%s' "$IDS" | tr ' ' ',')$([ "$(echo $IDS | wc -w)" -gt 1 ] && echo " (en cascada: comparten archivos)"): $MOTIVO"

declarados=""
sacados=0

# ── 1 a 4, para cada tarea de la cascada. El estado en los dos lados, el código afuera y
# la nota de por qué; los jueces corren UNA vez al final, sobre el conjunto, porque lo que
# hay que juzgar es el árbol que queda.
for ID in $IDS; do
archivo="$(ls "$BASE/tareas/${ID}"-*.md 2>/dev/null | head -1)"
sed -i '' 's/^\*\*Estado:\*\*.*/**Estado:** pendiente/' "$archivo" 2>/dev/null \
  || sed -i 's/^\*\*Estado:\*\*.*/**Estado:** pendiente/' "$archivo"
if [ -f "$BASE/PLAN.md" ] && grep -qE "^\| *$ID *\|" "$BASE/PLAN.md"; then
  python3 - "$BASE/PLAN.md" "$ID" <<'PYPLAN'
import re, sys
plan, tid = sys.argv[1], sys.argv[2]
texto = open(plan).read()
def marcar(m):
    celdas = m.group(0).rstrip("\n").strip("|").split("|")
    if len(celdas) < 5:
        return m.group(0)
    celdas[-1] = " pendiente "
    return "|" + "|".join(celdas) + "|\n"
nuevo = re.sub(rf"^\| *{re.escape(tid)} *\|.*\|\s*$\n?", marcar, texto, count=1, flags=re.M)
if nuevo != texto:
    open(plan, "w").write(nuevo)
PYPLAN
fi

# ── 3: sacar lo que la tarea DECLARA, y nada más.
#
# El archivo de test incluido: si sus tests codifican el error —mockean la consulta
# equivocada— conservarlos obliga al agente a reproducir el bug para que pasen.
declarados="$declarados $(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "$archivo" \
              | tr ',' '\n' | sed 's/^ *//; s/ *$//' | grep . || true)"
test_tarea="$(sed -n 's/.*Archivo: `\([^`]*\)`.*/\1/p' "$archivo" | head -1)"
for ruta in $declarados $test_tarea; do
  [ -n "$ruta" ] || continue
  [ -e "$BASE/$ruta" ] || continue
  mkdir -p "$RESPALDO/codigo/$(dirname "$ruta")"
  cp -R "$BASE/$ruta" "$RESPALDO/codigo/$ruta" 2>/dev/null
  if git -C "$RAIZ" ls-files --error-unmatch "$BASE/$ruta" >/dev/null 2>&1; then
    git -C "$RAIZ" rm -q -r --cached "$BASE/$ruta" >/dev/null 2>&1
  fi
  rm -rf "$BASE/$ruta"
  echo "  · sacado $ruta"
  sacados=$((sacados+1))
done
[ "$sacados" = 0 ] && echo "  · no había código declarado para sacar"

# ── 4: por qué. SIN backticks alrededor de identificadores, porque los chequeos leen los
# identificadores entre backticks de un enunciado como un compromiso de usarlos: una nota de
# reapertura que nombraba así la tabla equivocada hizo que el chequeo de coherencia la tomara
# por una promesa del enunciado y el rojo se duplicó.
# ARRIBA, antes de la primera sección, y no al final con `>>`.
#
# La nota lleva el dato que corrige a la tarea, y al final llegaba después de todo lo que
# corrige. Medido el 2026-10-25 en T26: su nota de reapertura dice «su codigo inserta la
# columna password_hash y la tabla usuarios tiene clave_hash», y estaba en la línea 104 de
# 110 — después de cien líneas donde el enunciado nombra `password_hash` cuatro veces,
# incluida la firma `def insert_user(email, password_hash)` que le pide escribir. El agente
# escribió `password_hash` y MySQL lo rechazó con «Unknown column».
#
# Un enunciado se lee de arriba hacia abajo: la corrección tiene que llegar antes que lo
# corregido. Va después del encabezado —estado, dependencias, alcance— porque esos campos los
# leen los scripts por posición, y antes de la primera `## `.
NOTA="$(printf '## Reabierta\n\n%s\n\nSe reabrió con scripts/reabrir.sh el %s. Su código anterior\nse sacó del tronco (copia en %s): esta tarea vuelve a pasar por tests-first,\nasí que el test tiene que fallar antes de que exista la implementación.\n\n' \
  "$(printf '%s' "$MOTIVO" | tr -d '`')" "$(date -u +'%Y-%m-%d %H:%M UTC')" \
  "$(basename "$RESPALDO")")"
python3 - "$archivo" <<PYNOTA
import sys
ruta = sys.argv[1]
nota = """$NOTA"""
lineas = open(ruta).read().split("\n")
# La primera sección. Si la tarea no tiene ninguna, la nota va al final: es el único lugar
# que queda, y quedarse sin escribirla sería perder el motivo.
corte = next((i for i, l in enumerate(lineas) if l.startswith("## ")), len(lineas))
# Una nota anterior se reemplaza, no se acumula: dos bloques «## Reabierta» y el lector no
# sabe cuál rige. Se saca DONDE ESTÉ y no sólo si cae en el corte: una nota escrita por la
# versión anterior de este script está al final, y mirando sólo la primera sección sobrevivía.
# Lo midió T26, que quedó con dos — la de abajo diciendo password_hash y la de arriba
# diciendo clave_hash, que es peor que no haber movido nada.
def sin_notas(ls):
    out, i = [], 0
    while i < len(ls):
        if ls[i].startswith("## Reabierta"):
            i += 1
            while i < len(ls) and not ls[i].startswith("## "):
                i += 1
            continue
        out.append(ls[i]); i += 1
    return out

lineas = sin_notas(lineas)
corte = next((i for i, l in enumerate(lineas) if l.startswith("## ")), len(lineas))
open(ruta, "w").write("\n".join(lineas[:corte] + nota.split("\n") + lineas[corte:]))
PYNOTA
done

# ── Los jueces, sobre el conjunto.
mal=""
(cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" >/dev/null 2>&1) \
  || mal="el plan dejó de validar"
rojos_despues="$( (cd "$BASE" && PROYECTO=. python3 "$AQUI/coherencia.py" 2>&1 | grep -c '✗') || true)"
if [ "${rojos_despues:-0}" -gt "${rojos_antes:-0}" ]; then
  mal="${mal:+$mal; }la reapertura AGREGÓ contradicciones: $rojos_antes → $rojos_despues"
fi

# ── El tercer juez: ¿rompimos el test de alguna tarea que sigue marcada como hecha?
#
# Las dos autoridades están a mano: el alcance de cada tarea dice qué archivos produjo, y la
# tabla de tests del plan dice cuál es su test. Con eso el aviso viene con nombre propio y
# quien decida la cascada no tiene que adivinar cuál.
ajenos=""
for tf in "$BASE"/tareas/T*.md; do
  otro="$(basename "$tf" | sed -E 's/^(T[0-9]+[a-z]?)-.*/\1/')"
  # Todas las de la cascada quedan fuera del juicio: sus tests TIENEN que romperse.
  #
  # Hoy esto es redundante —el paso 1 ya las dejó en `pendiente`, así que el filtro de
  # estado de la línea de abajo las saltea— y lo digo en vez de fingir que lo verifica un
  # test: quitarlo no pone roja la suite. Queda porque no depende de que el paso 1 haya
  # funcionado, y un juez que se apoya en el éxito del paso que viene a juzgar no es un juez.
  echo " $IDS " | grep -q " $otro " && continue
  grep -qE '^\*\*Estado:\*\* *(✅|hecha)' "$tf" || continue
  # ¿Declara alguno de los archivos que sacamos?
  suyos="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "$tf" | tr ',' '\n' \
           | sed 's/^ *//; s/ *$//' | grep . || true)"
  comparte=""
  for ruta in $declarados; do
    printf '%s\n' "$suyos" | grep -qxF "$ruta" && comparte="$ruta"
  done
  [ -n "$comparte" ] || continue
  # Confirmado por medición, no por deducción: se corre SU test y se mira el rc.
  # De la tabla de TESTS, no de la de tareas. Las dos tienen tres columnas y la de tareas
  # viene primero —`| T04b | Verificar sesión | T04 |`—, así que un grep por la fila de la
  # tarea devuelve el título y la dependencia. Se exige que el campo PAREZCA una ruta de
  # archivo, que es lo que distingue una tabla de la otra sin depender de su orden. Tercera
  # vez hoy que un extractor de este método lee la tabla de al lado.
  su_test="$(awk -F'|' -v t="$otro" '
    $2 ~ "^ *"t" *$" { gsub(/ |`/, "", $3); if ($3 ~ /\//  && $3 ~ /\.[a-z]+$/) { print $3; exit } }
  ' "$BASE/PLAN.md" 2>/dev/null)"
  if [ -n "$su_test" ] && [ -f "$BASE/$su_test" ] && [ -f "$BASE/scripts/correr-suite.sh" ]; then
    if ! (cd "$BASE" && bash scripts/correr-suite.sh "$su_test" >/dev/null 2>&1); then
      ajenos="${ajenos}${ajenos:+, }$otro (su test $su_test, por $comparte)"
    fi
  else
    # Sin test que correr no se puede medir, y el alcance compartido ya es motivo: se avisa
    # en vez de callar. Un chequeo que no pudo correr no es un chequeo que pasó.
    ajenos="${ajenos}${ajenos:+, }$otro (declara $comparte; no pude correr su test)"
  fi
done
if [ -n "$ajenos" ]; then
  mal="${mal:+$mal; }rompe tarea(s) que siguen marcadas como hechas: $ajenos"
fi

if [ -n "$mal" ]; then
  echo "  ✗ se revierte: $mal"
  for a in $ARCHIVOS_TAREA; do
    [ -f "$RESPALDO/$(basename "$a")" ] && cp "$RESPALDO/$(basename "$a")" "$a"
  done
  [ -f "$RESPALDO/PLAN.md" ] && cp "$RESPALDO/PLAN.md" "$BASE/PLAN.md"
  if [ -d "$RESPALDO/codigo" ]; then
    (cd "$RESPALDO/codigo" && find . -type f | while read -r f; do
       mkdir -p "$BASE/$(dirname "$f")"; cp "$f" "$BASE/$f"; done)
  fi
  git -C "$RAIZ" add -A "$BASE" >/dev/null 2>&1
  exit 1
fi
echo "  ✓ $(printf '%s' "$IDS" | tr ' ' ',') queda(n) pendiente(s), su código está fuera del tronco y el plan valida"
echo "    (rojos del preflight: $rojos_antes → $rojos_despues; los que quedan los cierra la tarea al correr)"
