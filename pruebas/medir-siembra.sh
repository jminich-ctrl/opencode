#!/usr/bin/env bash
# Mide la tasa de captura de la suite del método contra fallas sembradas por un tercero.
#
#   bash pruebas/medir-siembra.sh /tmp/siembra
#
# Por qué: la suite de `pruebas/test_metodo.py` tiene un caso por cada bug que tuvimos, así
# que **todo verde mide el sesgo de la suite, no la corrección del gate.** Está publicado:
# "que una suite encuentre muchas fallas sembradas no significa que vaya a encontrar las
# fallas que importan", y un generador satura "no porque el compilador esté libre de bugs
# sino porque el generador contiene sesgos".
#
# La forma de romper ese sesgo es que las fallas las siembre **alguien sin la lista de bugs**.
# Esto toma esas variantes, pone cada una como el gate de la plantilla, corre la suite, y
# cuenta cuántas atrapa. El número que sale es la **tasa de captura**, y lo que importa no es
# que sea alto: es saberlo.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${1:-/tmp/siembra}"
ORIGINAL="$AQUI/../plantillas/gate.sh"
RESPALDO="$(mktemp)"
cp "$ORIGINAL" "$RESPALDO"
trap 'cp "$RESPALDO" "$ORIGINAL"; rm -f "$RESPALDO"' EXIT

mapfile_ls() { ls "$DIR"/variante-*.sh 2>/dev/null; }
VARIANTES="$(mapfile_ls)"
[ -n "$VARIANTES" ] || { echo "✗ no hay variantes en $DIR" >&2; exit 1; }

atrapadas=0; total=0; escapadas=""
for v in $VARIANTES; do
  total=$((total+1))
  nombre="$(basename "$v" .sh)"
  if ! bash -n "$v" 2>/dev/null; then
    echo "  — $nombre: no es bash válido, se descarta"; total=$((total-1)); continue
  fi
  cp "$v" "$ORIGINAL"
  if python3 "$AQUI/test_metodo.py" >/dev/null 2>&1; then
    printf '  ✗ %s ESCAPÓ — la suite dio verde con la falla puesta\n' "$nombre"
    escapadas="$escapadas $nombre"
  else
    printf '  ✓ %s atrapada\n' "$nombre"
    atrapadas=$((atrapadas+1))
  fi
done
cp "$RESPALDO" "$ORIGINAL"

echo
echo "Tasa de captura: $atrapadas de $total"
if [ -n "$escapadas" ]; then
  echo "Escaparon:$escapadas"
  echo
  echo "Cada una es un caso de test que falta. Miralas con:"
  echo "  diff plantillas/gate.sh $DIR/variante-NN.sh"
  echo "Y la lección publicada: el remedio no es agregar un caso por cada escapada —eso es"
  echo "sobreajustar de nuevo— sino preguntarse qué CLASE de chequeo falta."
else
  echo "Ninguna escapó. Ojo: eso mide estas 12 fallas, no la corrección del gate."
fi
