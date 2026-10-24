#!/usr/bin/env bash
# El enjambre: la MISMA pregunta a varios modelos, y el acuerdo es el dato.
#
#   bash scripts/enjambre.sh <archivo-con-el-prompt> <id>:<nombre> [<id>:<nombre> ...]
#
# Se guarda la salida CRUDA de cada uno en su archivo y la extracción se hace DESPUÉS, sobre
# el archivo. La primera versión extraía con `sed/tail` en la tubería y se trajo el
# razonamiento del modelo en vez de su respuesta —el mismo defecto que el `grep '→'` de
# mutar.py: un extractor que no acuerda con el formato de su fuente, y que encima descartaba
# la evidencia que permitiría notarlo.
#
# La extracción la hace `limpiar.py`. Estaba copiada acá adentro como python incrustado, y
# esa copia tomaba la última línea del texto CRUDO: para una respuesta en cercas devolvía
# «```» y la tabla mostraba eso como la respuesta del modelo.
set -u
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SALIDA="${SALIDA:-$(cd "$AQUI/.." && pwd)/../sin-memoria}"
mkdir -p "$SALIDA"
PROMPT="$1"; shift
[ -s "$PROMPT" ] || { echo "✗ el prompt está vacío o no existe: $PROMPT" >&2; exit 1; }
for m in "$@"; do
  id="${m%%:*}"; nom="${m##*:}"; t0=$(date +%s)
  python3 "$AQUI/pedir.py" "$id" < "$PROMPT" > "$SALIDA/enj-$nom.out" 2> "$SALIDA/enj-$nom.err"
  rc=$?; dt=$(( $(date +%s) - t0 ))
  if [ "$rc" != 0 ]; then
    printf '%-16s %4ds  ✗ %s\n' "$nom" "$dt" "$(tr '\n' ' ' < "$SALIDA/enj-$nom.err" | cut -c1-90)"
    continue
  fi
  resp="$(python3 "$AQUI/limpiar.py" --ultima-linea "$SALIDA/enj-$nom.out")"
  printf '%-16s %4ds  %s\n' "$nom" "$dt" "$(printf '%s' "$resp" | cut -c1-120)"
done
echo "(salidas crudas en $SALIDA)"
