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

# El nombre de la base para el árbol que se prepara. Vacío si es el tronco: el tronco usa la
# del proyecto, que es la que una persona mira entre corridas.
#
# El prefijo sale del `.entorno` del TRONCO porque el método no sabe cómo se llama la base de
# un proyecto —lo decide su `entorno.sh`— y el sufijo del nombre del worktree, que es la
# unidad de aislamiento que el método ya tiene. Se sanea a lo que MySQL acepta como
# identificador y se corta a 64, que es el límite.
base_de_datos_del_arbol() {
  [ "$DESTINO" != "$BASE" ] || return 0
  local prefijo="" raiz slug
  if [ -f "$BASE/.entorno" ]; then
    prefijo="$(sed -n 's/^export MYSQL_DB=//p' "$BASE/.entorno" | head -1 | tr -d "\"'")"
  fi
  raiz="$(git -C "$DESTINO" rev-parse --show-toplevel 2>/dev/null)"
  # `printf '%s'` y no `basename` directo: el salto de línea que agrega `basename` también es
  # un carácter fuera del juego, así que `tr` lo convertía en un `_` y la base quedaba
  # `clasificados_tests_T26_`. Funcionaba, pero un nombre con basura es un nombre que alguien
  # va a leer y no va a entender.
  slug="$(printf '%s' "$(basename "${raiz:-$DESTINO}")" | tr -c 'A-Za-z0-9' '_')"
  printf '%s' "${prefijo:-proyecto}_${slug}" | cut -c1-64
}

mismo_manifiesto() {
  local dir="$1" nombre="$2"
  local a="$BASE/$dir/$nombre" b="$DESTINO/$dir/$nombre"
  [ -f "$a" ] && [ -f "$b" ] || return 1
  [ "$(cksum < "$a")" = "$(cksum < "$b")" ]
}

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
  for d in .venv .entorno backend/node_modules frontend/node_modules node_modules; do
    origen="$BASE/$d"
    [ -e "$origen" ] || continue
    destino="$DESTINO/$d"
    case "$d" in
      .entorno)
        # NO se enlaza si el proyecto sabe regenerarlo. `.entorno` lleva el NOMBRE DE LA
        # BASE, así que compartirlo es compartir la base — y hasta el 2026-10-25 eso era
        # exactamente lo que pasaba: todos los worktrees escribían en la misma, nadie la
        # limpiaba, y el validador —que corre el mismo test dos veces— chocaba en la segunda
        # con la fila que insertó la primera. El veredicto se lo cobraba al test.
        # Si el proyecto NO tiene `entorno.sh`, se enlaza como antes: sin quién lo regenere,
        # quitarlo dejaría al worktree sin credenciales.
        if [ -x "$BASE/scripts/entorno.sh" ]; then
          # Y si el enlace YA estaba de una corrida anterior, se DESHACE. Es imprescindible,
          # no cosmético: `entorno.sh` escribe con `cat >`, y escribir a través de un enlace
          # escribe en su DESTINO — o sea que generar el `.entorno` del worktree pisaría el
          # del tronco con el nombre de la base del worktree, y el tronco entero pasaría a
          # apuntar a la base de una tarea. Borrar un enlace no toca su destino.
          if [ -L "$destino" ]; then
            rm -f "$destino"
            echo "· .entorno se desenlaza: cada worktree tiene su propia base"
            HIZO=1
          fi
          continue
        fi ;;
      *node_modules)
        dir_m="$(dirname "$d")"; [ "$dir_m" = "." ] && dir_m=""
        # Si NINGUNO de los dos lados tiene manifiesto, no hay nada que comparar y el
        # node_modules es basura de alguna corrida anterior: no se enlaza y no se explica
        # con un motivo que no es el verdadero.
        if [ ! -f "$BASE/${dir_m:+$dir_m/}package.json" ] \
           && [ ! -f "$DESTINO/${dir_m:+$dir_m/}package.json" ]; then
          continue
        fi
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
  # Corre el script DEL TRONCO incluso para un worktree, a propósito: el worktree no tiene
  # `.mysql/` —está gitignorado y no se enlaza— así que desde ahí el script no encontraría ni
  # el cliente ni el datadir, y podría intentar levantar un SEGUNDO servidor. El servidor es
  # uno; lo que se aísla es la base.
  DB_ARBOL="$(base_de_datos_del_arbol)"
  if [ -n "$DB_ARBOL" ]; then
    echo "· base de datos de este worktree: $DB_ARBOL"
  fi
  ( cd "$BASE" \
    && MYSQL_DB="${DB_ARBOL:-${MYSQL_DB:-}}" \
       ENTORNO_DESTINO="$DESTINO" MIGRACIONES_DESDE="$DESTINO" \
       bash scripts/entorno.sh ) || {
    echo "✗ los servicios del proyecto no están listos. El gate iba a reprobar por eso."; exit 1; }
  # ── Lo que informamos tiene que ser lo que quedó escrito.
  #
  # El `.entorno` es la ÚNICA fuente de la base para todo lo que viene después: el test la
  # lee de ahí, y `limpiar_base_del_arbol` también. Si el nombre que derivamos y el que quedó
  # escrito no son el mismo, el método informa una base, limpia otra y el test usa una
  # tercera — y el choque reaparece como `Duplicate entry` con el veredicto cobrado al test,
  # que es el defecto que se cerró el 2026-10-25 y volvió a aparecer ese mismo día.
  #
  # Medido ese día en la corrida de T26: el método informó `clasificados_tests_T26`, el
  # `.entorno` quedó diciendo `clasificados_tests_T26_tests_T26` —el sufijo dos veces— y las
  # DOS bases existen en el servidor, con una fila cada una. `limpiar_base_del_arbol` vació
  # la del `.entorno` y dejó la otra intacta.
  #
  # No pude reproducir cómo se duplica: tres pasadas seguidas de este script dan el mismo
  # nombre, y `entorno.sh` no deriva nada —escribe el `MYSQL_DB` que recibe—. Así que esto no
  # es el arreglo de la causa, es el chequeo que la va a atrapar con los dos nombres a la
  # vista la próxima vez que pase. Un desacuerdo acá no se puede dejar pasar en silencio: es
  # barato de ver y caro de diagnosticar después.
  if [ -n "$DB_ARBOL" ] && [ -f "$DESTINO/.entorno" ]; then
    DB_ESCRITA="$(sed -n 's/^export MYSQL_DB=//p' "$DESTINO/.entorno" | head -1 | tr -d "\"'")"
    if [ "$DB_ESCRITA" != "$DB_ARBOL" ]; then
      echo "✗ el nombre de la base no coincide con el que quedó escrito:"
      echo "     derivado por el método: $DB_ARBOL"
      echo "     escrito en $DESTINO/.entorno: ${DB_ESCRITA:-(vacío)}"
      echo "   El .entorno es la única fuente para el test y para la limpieza. Con dos"
      echo "   nombres, se limpia una base y se usa otra, y el choque vuelve como"
      echo "   «Duplicate entry» cobrado al test."
      exit 1
    fi
  fi
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
  # Y las dependencias que existen SÓLO para correr los tests, si el proyecto las declara
  # aparte. No se despliegan, así que no van en requirements.txt; y el corredor de tests es
  # del método, así que instalarlas es nuestro. Sin esto pasó con `httpx` —el cliente de
  # tests de FastAPI—: el test de T04 lo importaba, estaba permitido en AGENTS.md, y ninguna
  # tarea lo tenía asignado, así que el diagnóstico que salía era «el test está mal».
  DEV="$(ls "$DESTINO"/requirements-dev.txt "$DESTINO"/*/requirements-dev.txt 2>/dev/null | head -1)"
  if [ -n "$DEV" ]; then
    SELLO_DEV="$VENV/.sello-requirements-dev"
    AHORA_DEV="$(cksum < "$DEV" | awk '{print $1}')"
    if [ "$(cat "$SELLO_DEV" 2>/dev/null)" != "$AHORA_DEV" ]; then
      echo "· instalando $(basename "$(dirname "$DEV")")/requirements-dev.txt"
      if "$VENV/bin/pip" install -q -r "$DEV" 2>&1 | tail -5; then
        echo "$AHORA_DEV" > "$SELLO_DEV"; HIZO=1
      else
        echo "✗ pip falló con las dependencias de test. El gate va a reprobar por eso." >&2
        exit 1
      fi
    fi
  fi

  # pytest no siempre está declarado y sin él el gate no verifica nada. Lo exigimos acá
  # para que no aparezca como falla de la tarea.
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
      # Si el manifiesto del worktree NO es el del tronco, el lock commiteado es de otro
      # manifiesto: `npm ci` se niega, y `npm install` sobre un lock viejo deja el árbol a
      # medias por el bug de dependencias opcionales de npm —el agente de T30 se topó con
      # «Cannot find native binding», que es rollup sin su binario de plataforma—. En ese
      # caso se instala desde el package.json y sin escribir lock: el lock es del proyecto,
      # no de un worktree de validación.
      # Instalación LIMPIA siempre que el manifiesto cambió: `npm install` sobre un
      # node_modules viejo deja el árbol a medias por el bug de dependencias opcionales de
      # npm, y el síntoma es «Cannot find native binding» —rollup sin su binario de
      # plataforma— a mitad de una tarea que no tiene nada que ver. Nos pasó dos veces, y la
      # segunda el node_modules roto estaba en el TRONCO, así que se lo heredaban todas.
      # La documentación de npm para ese bug dice exactamente esto: borrar node_modules y el
      # lock antes de reinstalar.
      if [ "$DESTINO" != "$BASE" ] && ! mismo_manifiesto "${DIR#$DESTINO/}" package.json; then
        echo "  · manifiesto propio del worktree: instalación limpia, sin tocar el lock"
        rm -rf "$DIR/node_modules"
        ( cd "$DIR" && npm install --silent --no-package-lock )
      elif [ -f "$DIR/package-lock.json" ] && ( cd "$DIR" && npm ci --silent ); then
        :
      else
        echo "  · instalación limpia (el lock no estaba en sincronía con el manifiesto)"
        rm -rf "$DIR/node_modules" "$DIR/package-lock.json"
        ( cd "$DIR" && npm install --silent )
      fi
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
