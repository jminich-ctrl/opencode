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

# ── El worktree, PRIMERO. El venv, node_modules y .entorno están gitignorados, así que
# no viajan. En vez de copiarlos, los enlazamos al tronco: es instantáneo y no se
# desincroniza.
#
# Va antes de instalar y no después: el sello que evita reinstalar vive DENTRO de
# node_modules, así que con el orden invertido cada worktree hacía su propio `npm
# install` desde cero. Un minuto por tarea, y el plan de clasificados tiene 28.
if [ "$DESTINO" != "$BASE" ]; then
  # El enlace de dependencias es CONDICIONAL: sólo si el worktree declara lo mismo que el
  # tronco. Una tarea como T30 cambia el manifiesto —agrega vitest—, y con el enlace puesto
  # su `npm install` escribiría dentro del node_modules del tronco, con el manifiesto del
  # worktree: la instalación de una tarea se filtra a un tronco que todavía no la integró,
  # y dos tareas de frontend de la misma etapa instalan a la vez en el mismo directorio.
  mismo_manifiesto() {
    local dir="$1" nombre="$2"
    local a="$BASE/$dir/$nombre" b="$DESTINO/$dir/$nombre"
    [ -f "$a" ] && [ -f "$b" ] || return 1
    [ "$(cksum < "$a")" = "$(cksum < "$b")" ]
  }
  for d in .venv .entorno backend/node_modules frontend/node_modules node_modules; do
    origen="$BASE/$d"
    [ -e "$origen" ] || continue
    destino="$DESTINO/$d"
    case "$d" in
      *node_modules)
        dir_m="$(dirname "$d")"; [ "$dir_m" = "." ] && dir_m=""
        if ! mismo_manifiesto "$dir_m" package.json; then
          # Y si el enlace YA estaba puesto, se deshace: la condición se evalúa en la
          # primera pasada, antes de que el agente escriba su package.json, así que el
          # manifiesto diverge después. Sin deshacerlo, el `npm install` de la segunda
          # pasada escribe a través del enlace en el node_modules del tronco, que todavía
          # no integró nada. Borrar un enlace no toca su destino.
          if [ -L "$destino" ]; then
            rm -f "$destino"
            echo "· $d se desenlaza: el worktree ya declara otras dependencias"
            HIZO=1
          else
            echo "· $d NO se enlaza: el worktree declara otras dependencias que el tronco"
          fi
          continue
        fi ;;
    esac
    [ -e "$destino" ] && continue
    mkdir -p "$(dirname "$destino")"
    ln -s "$origen" "$destino" && { echo "· enlazado $d al tronco"; HIZO=1; }
  done
fi


# ── Servicios del proyecto (base de datos, colas, lo que sea). El método no sabe qué
# necesita cada proyecto: si hay `scripts/entorno.sh`, lo corre y confía en su código de
# salida. Un servicio que no se puede levantar NO se disimula: para la etapa con un motivo
# accionable, porque un test de base de datos que pasa sin base no verifica nada.
if [ -x "$BASE/scripts/entorno.sh" ]; then
  ( cd "$BASE" && bash scripts/entorno.sh ) || {
    echo "✗ los servicios del proyecto no están listos. El gate iba a reprobar por eso."; exit 1; }
  HIZO=1
fi

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

[ "$HIZO" = "1" ] || echo "· entorno al día"
