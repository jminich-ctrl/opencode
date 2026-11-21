#!/usr/bin/env bash
# Trae al repo el material crudo que el método produce AFUERA, para que deje de perderse.
#
#   bash scripts/cosechar.sh            # cosecha y muestra qué entró
#   bash scripts/cosechar.sh --seco     # sólo dice qué entraría
#
# Por qué existe. El método genera tres cosas que no vive ninguna en el repo:
#
#   - `../fallidos-TNN/` — transcripts, parches y veredictos de cada intento que el gate
#     reprobó. Los escribe `conservar_intento` y `conservar_veredicto` (`_comun.sh`), y van
#     AFUERA del worktree a propósito, porque el worktree se destruye.
#   - `~/rechazados/` — los 16 intentos con código real que son el banco de los dos
#     experimentos bloqueados. Su propio `PROCEDENCIA.md` dice que son «un rescate accidental
#     de worktrees que estaban por borrarse» y «la única copia que existe».
#
# «La única copia que existe» es una frase que ya nos costó caro. El 2026-11-10 escribí
# `gate_publico.py` —la réplica pública del gate sobre TestEval— en el scratchpad de /tmp
# junto con el banco de 210 ítems y su venv. El sistema limpió /tmp y se fueron los tres. El
# script lo pude reescribir porque estaba en una transcripción; el banco y el venv hubo que
# volver a armarlos. Material de investigación que vive en un directorio que alguien más
# administra no está guardado: está prestado.
#
# Lo que este script NO hace: borrar los originales. El runner sigue escribiendo donde
# escribía, y `replanificar.sh` sigue leyendo el veredicto de ahí. Esto es una copia, y es
# idempotente: correrlo dos veces no duplica nada.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(cd "$AQUI/.." && pwd)"
DESTINO="$RAIZ/experimentos/crudo"
SECO=0
[ "${1:-}" = "--seco" ] && SECO=1

copiados=0; ya=0; dirs=0

cosechar_dir() {
  # $1 = origen, $2 = subcarpeta de destino
  local origen="$1" sub="$2" dest f base
  [ -d "$origen" ] || return 0
  dest="$DESTINO/$sub"
  dirs=$((dirs+1))
  for f in "$origen"/*; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    if [ -f "$dest/$base" ]; then ya=$((ya+1)); continue; fi
    copiados=$((copiados+1))
    [ "$SECO" = "1" ] && { echo "  + $sub/$base"; continue; }
    mkdir -p "$dest"
    cp -p "$f" "$dest/$base"
  done
}

echo "→ intentos reprobados que el runner dejó en ../fallidos-*"
for d in "$RAIZ"/../fallidos-*; do
  [ -d "$d" ] || continue
  cosechar_dir "$d" "fallidos/$(basename "$d" | sed 's/^fallidos-//')"
done

# Los transcripts del arquitecto cuando replanifica. Son `.log` sueltos dentro del
# proyecto, o sea gitignoreados y a un `git clean` de distancia, y son la ÚNICA evidencia de
# qué hizo el arquitecto con un motivo en la mano. El 2026-11-10 fueron lo que refutó mi
# propia hipótesis: con el veredicto correcto adelante, el arquitecto igual no reescribió
# nada, y por qué sólo se ve ahí adentro.
echo "→ transcripts de replanificación del proyecto de ejemplo"
for p in "$RAIZ"/ejemplo-clasificados "$RAIZ"/../ejemplo-clasificados; do
  [ -d "$p" ] || continue
  dest="$DESTINO/replan"
  for f in "$p"/.replan-*.log; do
    [ -f "$f" ] || continue
    # Sin el punto de adelante: en el proyecto están ocultos a propósito —son temporales
    # del runner— pero acá son material, y un material que `ls` no muestra es un material
    # que nadie va a mirar.
    base="$(basename "$f" | sed 's/^\.//')"
    if [ -f "$dest/$base" ]; then ya=$((ya+1)); continue; fi
    copiados=$((copiados+1))
    [ "$SECO" = "1" ] && { echo "  + replan/$base"; continue; }
    mkdir -p "$dest"; cp -p "$f" "$dest/$base"
  done
  dirs=$((dirs+1))
  break
done

echo "→ el banco de 16 rechazados con código real"
# Recursivo: cada ítem es una carpeta con el worktree adentro, no archivos sueltos.
if [ -d "$HOME/rechazados" ]; then
  dirs=$((dirs+1))
  if [ "$SECO" = "1" ]; then
    echo "  + banco/ ($(find "$HOME/rechazados" -type f | wc -l | tr -d ' ') archivos)"
  else
    mkdir -p "$DESTINO/banco"
    # `-p` conserva la fecha, que es lo único que ata un intento a su corrida.
    (cd "$HOME/rechazados" && tar cf - .) | (cd "$DESTINO/banco" && tar xpf -)
  fi
fi

if [ "$SECO" = "1" ]; then
  echo
  echo "en seco: $copiados archivo(s) nuevos de $dirs origen(es); $ya ya estaban."
  exit 0
fi

# El índice. Se reescribe entero en cada cosecha a propósito: un índice que se APENDA queda
# describiendo un estado que ya no es, y lo que describe mal un material es peor que no
# describirlo —se le cree—.
{
  echo "# Material crudo, cosechado al repo"
  echo
  echo "Generado por \`scripts/cosechar.sh\` el $(date -u +%Y-%m-%d) (UTC). **No se edita a mano.**"
  echo
  echo "Esto es una COPIA. Los originales siguen donde el método los escribe"
  echo "(\`../fallidos-TNN/\`, \`~/rechazados/\`) porque el runner y \`replanificar.sh\` leen de ahí."
  echo "Está acá porque material de investigación que vive sólo afuera del repo no está"
  echo "guardado: el 2026-11-10 se perdió \`gate_publico.py\` con su banco y su venv cuando el"
  echo "sistema limpió /tmp."
  echo
  echo "## Intentos reprobados, por tarea"
  echo
  echo "| tarea | intentos | parches | veredictos del arnés |"
  echo "|---|---|---|---|"
  for d in "$DESTINO"/fallidos/*; do
    [ -d "$d" ] || continue
    printf '| %s | %s | %s | %s |\n' "$(basename "$d")" \
      "$(ls "$d"/intento-* 2>/dev/null | wc -l | tr -d ' ')" \
      "$(ls "$d"/parche-* 2>/dev/null | wc -l | tr -d ' ')" \
      "$(ls "$d"/veredicto-* 2>/dev/null | wc -l | tr -d ' ')"
  done
  echo
  echo "El **veredicto del arnés** es el dato nuevo y es el que vale: hasta el 2026-11-10 el"
  echo "motivo del rechazo sólo existía en stdout y moría con la corrida, así que de los"
  echo "intentos viejos hay transcript y parche pero no veredicto. El transcript NO lo"
  echo "reemplaza: el agente imprime el gate varias veces mientras trabaja y el último que"
  echo "imprime no es el veredicto (ver \`banco/PROCEDENCIA.md\`)."
  echo
  echo "## El banco con código real"
  echo
  echo "\`banco/\` — 22 carpetas, 16 de ellas con veredicto ✗ ROJO y el parche que un modelo"
  echo "escribió de verdad. Su procedencia, modelo por modelo, está en \`banco/PROCEDENCIA.md\`."
  echo
  echo "## Replanificación"
  echo
  echo "\`replan/\` — lo que el arquitecto hizo cuando recibió el motivo del rechazo. Son los"
  echo "transcripts que el 2026-11-10 refutaron la hipótesis de que el arquitecto no actuaba"
  echo "porque recibía la categoría en vez del dato: con el dato adelante tampoco reescribió."
} > "$DESTINO/INDICE.md"

echo
echo "✓ $copiados archivo(s) nuevos · $ya ya estaban · índice en experimentos/crudo/INDICE.md"
echo "  Falta commitearlo: el material sólo está guardado cuando está en un commit."
