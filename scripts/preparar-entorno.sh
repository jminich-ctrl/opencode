#!/usr/bin/env bash
# Deja el proyecto en condiciones de que el gate verifique algo. Idempotente.
#
#   bash $AGENTES/scripts/preparar-entorno.sh            # sobre el tronco
#   bash $AGENTES/scripts/preparar-entorno.sh /ruta/wt   # sobre un worktree
#
# Por qué existe: el gate, bien hecho, pone ROJO cuando falta el corredor de tests —
# "un corredor ausente no puede verse como «no hay tests»". Pero ese rojo **no es del
# agente**: es nuestro. Una tarea declara `backend/requirements.txt`, lo escribe bien, y
# el gate la reprueba porque nadie instaló lo que declaró. El runner se detiene, el humano
# instala a mano, y la supuesta autonomía se paga en interrupciones.
#
# La regla que sale de eso: **todo rojo que no pueda atribuirse al agente es un defecto
# del método.** Preparar el entorno es parte del método, no del trabajo de la tarea.
#
# Detecta por manifiesto, no por lista de stacks escrita acá: con `requirements.txt`
# instala Python, con `package.json` instala node. Un stack nuevo se agrega acá, una vez.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto

# Sobre qué árbol trabajamos: el tronco por defecto, o el worktree que nos pasen.
DESTINO="${1:-$BASE}"
[ -d "$DESTINO" ] || { echo "✗ no existe $DESTINO" >&2; exit 1; }
HIZO=0

# ── Python. El venv vive en el tronco y se comparte: crear uno por worktree son 40 MB y
# medio minuto por tarea, y las dependencias son las mismas.
REQ="$(ls "$DESTINO"/requirements.txt "$DESTINO"/*/requirements.txt 2>/dev/null | head -1)"
if [ -n "$REQ" ]; then
  VENV="$BASE/.venv"
  if [ ! -x "$VENV/bin/python" ]; then
    echo "· creando $VENV"
    python3 -m venv "$VENV" || { echo "✗ no pude crear el venv" >&2; exit 1; }
    HIZO=1
  fi
  # Reinstalar sólo si el manifiesto cambió: un `pip install` por tarea son minutos
  # regalados, y el método los paga en cada etapa.
  SELLO="$VENV/.sello-requirements"
  AHORA="$(cksum "$REQ" | awk '{print $1}')"
  if [ "$(cat "$SELLO" 2>/dev/null)" != "$AHORA" ]; then
    echo "· instalando $(basename "$(dirname "$REQ")")/requirements.txt"
    if "$VENV/bin/pip" install -q -r "$REQ" 2>&1 | tail -5; then
      echo "$AHORA" > "$SELLO"; HIZO=1
    else
      echo "✗ pip falló. El entorno queda incompleto y el gate lo va a decir en rojo." >&2
      exit 1
    fi
  fi
  # pytest no suele estar en requirements.txt (es de desarrollo) y sin él el gate no
  # verifica nada. Lo exigimos acá para que no aparezca como falla de la tarea.
  if ! "$VENV/bin/python" -c "import pytest" >/dev/null 2>&1; then
    echo "· instalando pytest (corredor, no dependencia del producto)"
    "$VENV/bin/pip" install -q pytest || exit 1
    HIZO=1
  fi
fi

# ── Node. `npm ci` si hay lock, `npm install` si no; el lock es lo que hace repetible la
# instalación, así que si existe se respeta.
PKG="$(ls "$DESTINO"/package.json "$DESTINO"/*/package.json 2>/dev/null | head -1)"
if [ -n "$PKG" ]; then
  DIR="$(dirname "$PKG")"
  SELLO="$DIR/node_modules/.sello-package"
  AHORA="$(cksum "$PKG" | awk '{print $1}')"
  if [ "$(cat "$SELLO" 2>/dev/null)" != "$AHORA" ]; then
    if command -v npm >/dev/null 2>&1; then
      echo "· instalando $(basename "$DIR")/package.json"
      if [ -f "$DIR/package-lock.json" ]; then ( cd "$DIR" && npm ci --silent ) || ( cd "$DIR" && npm install --silent )
      else ( cd "$DIR" && npm install --silent ); fi
      if [ -d "$DIR/node_modules" ]; then echo "$AHORA" > "$SELLO"; HIZO=1
      else echo "✗ npm no dejó node_modules" >&2; exit 1; fi
    else
      echo "⊘ hay package.json y no hay npm: el gate del frontend va a dar rojo por falta"
      echo "   de corredor. Instalá node y volvé a correr esto."
      exit 1
    fi
  fi
fi

# ── El worktree. El venv y node_modules están gitignorados, así que no viajan. En vez de
# copiarlos, los enlazamos al tronco: es instantáneo y no se desincroniza.
if [ "$DESTINO" != "$BASE" ]; then
  for d in .venv backend/node_modules frontend/node_modules node_modules; do
    origen="$BASE/$d"
    [ -e "$origen" ] || continue
    destino="$DESTINO/$d"
    [ -e "$destino" ] && continue
    mkdir -p "$(dirname "$destino")"
    ln -s "$origen" "$destino" && { echo "· enlazado $d al tronco"; HIZO=1; }
  done
fi

[ "$HIZO" = "1" ] || echo "· entorno al día"
