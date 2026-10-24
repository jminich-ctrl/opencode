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
[ $# -ge 1 ] || { echo "uso: $0 TNN [motivo]" >&2; exit 1; }
ID="$1"; MOTIVO="${2:-su gate dio un veredicto falso}"

archivo="$(ls "$BASE/tareas/${ID}"-*.md 2>/dev/null | head -1)"
[ -n "$archivo" ] || { echo "✗ $ID: no existe tareas/${ID}-*.md" >&2; exit 1; }

# Los rojos de ANTES, para poder comparar: lo que importa no es que queden rojos —el que
# motivó la reapertura puede seguir ahí hasta que la tarea corra— sino que no aparezcan
# NUEVOS por culpa de lo que escribimos acá.
rojos_antes="$( (cd "$BASE" && PROYECTO=. python3 "$AQUI/coherencia.py" 2>&1 | grep -c '✗') || true)"

RESPALDO="$RAIZ/../reabrir-$ID-previo"
rm -rf "$RESPALDO"; mkdir -p "$RESPALDO"
cp "$archivo" "$RESPALDO/$(basename "$archivo")"
[ -f "$BASE/PLAN.md" ] && cp "$BASE/PLAN.md" "$RESPALDO/PLAN.md"

echo "▶ reabriendo $ID: $MOTIVO"

# ── 1 y 2: el estado, en los DOS lados.
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
declarados="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "$archivo" \
              | tr ',' '\n' | sed 's/^ *//; s/ *$//' | grep . || true)"
test_tarea="$(sed -n 's/.*Archivo: `\([^`]*\)`.*/\1/p' "$archivo" | head -1)"
sacados=0
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
printf '\n## Reabierta\n\n%s\n\nSe reabrió con scripts/reabrir.sh el %s. Su código anterior\nse sacó del tronco (copia en %s): esta tarea vuelve a pasar por tests-first,\nasí que el test tiene que fallar antes de que exista la implementación.\n' \
  "$(printf '%s' "$MOTIVO" | tr -d '`')" "$(date -u +'%Y-%m-%d %H:%M UTC')" \
  "../reabrir-$ID-previo" >> "$archivo"

# ── Los jueces.
mal=""
(cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" >/dev/null 2>&1) \
  || mal="el plan dejó de validar"
rojos_despues="$( (cd "$BASE" && PROYECTO=. python3 "$AQUI/coherencia.py" 2>&1 | grep -c '✗') || true)"
if [ "${rojos_despues:-0}" -gt "${rojos_antes:-0}" ]; then
  mal="${mal:+$mal; }la reapertura AGREGÓ contradicciones: $rojos_antes → $rojos_despues"
fi

if [ -n "$mal" ]; then
  echo "  ✗ se revierte: $mal"
  cp "$RESPALDO/$(basename "$archivo")" "$archivo"
  [ -f "$RESPALDO/PLAN.md" ] && cp "$RESPALDO/PLAN.md" "$BASE/PLAN.md"
  if [ -d "$RESPALDO/codigo" ]; then
    (cd "$RESPALDO/codigo" && find . -type f | while read -r f; do
       mkdir -p "$BASE/$(dirname "$f")"; cp "$f" "$BASE/$f"; done)
  fi
  git -C "$RAIZ" add -A "$BASE" >/dev/null 2>&1
  exit 1
fi
echo "  ✓ $ID queda pendiente, su código está fuera del tronco y el plan valida"
echo "    (rojos del preflight: $rojos_antes → $rojos_despues; los que quedan los cierra la tarea al correr)"
