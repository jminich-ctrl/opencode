#!/usr/bin/env bash
# Resumen de en qué anda cada tarea.
#   bash $AGENTES/scripts/estado.sh                     desde tu proyecto
#   PROYECTO=ejemplo-pacman bash scripts/estado.sh      el ejemplo, desde la raíz de este repo
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE: ver _comun.sh

printf '%-6s %-38s %-10s %s\n' TAREA TÍTULO ESTADO DETALLE
printf '%.0s─' {1..90}; echo
for f in "$BASE"/tareas/T*.md; do
  [ -e "$f" ] || continue
  id="$(basename "$f" | cut -d- -f1)"
  # `T[0-9]*` no cubre los sufijos: con T04b y T06a el título salía como «# T04b — …» y la
  # columna quedaba ilegible justo en las tareas partidas, que son las que más se miran.
  titulo="$(head -1 "$f" | sed 's/^# *T[0-9]*[a-z]* *— *//' | cut -c1-36)"
  wt="$RAIZ/../trabajo-$id"
  log="$wt/.tarea.log"
  if grep -q '^\*\*Estado:\*\* ✅' "$f" 2>/dev/null && [ ! -d "$wt" ]; then
    estado="✅ hecha"; detalle="mergeada"
  elif [ ! -d "$wt" ]; then
    estado="pendiente"; detalle=""
  else
    # El veredicto es el código de salida del gate que corrió el runner (ver _comun.sh),
    # nunca lo que el agente escribió.
    v="$(veredicto "$log")"
    error="$( [ -f "$log" ] && error_del_agente "$log")"
    if [ -z "$v" ]; then
      estado="… corriendo"; detalle="$(wc -l < "$log" 2>/dev/null | xargs) líneas de log"
    elif [ -n "$error" ]; then
      estado="✗ error"; detalle="$(echo "$error" | cut -c1-50)"
    elif [ "$v" = "IMPOSIBLE" ]; then
      estado="⃠ imposible"; detalle="$(motivo_imposible "$log" | cut -c1-50)"
    elif [ "$v" = "VERDE" ]; then
      estado="✓ verde"; detalle="$(git -C "$wt" status --short -- "$PROYECTO" 2>/dev/null | grep -vc '\.tarea\.log\|\.opencode-data' | xargs) archivos cambiados"
    else
      estado="✗ rojo"; detalle="$(awk '$0 == "=== gate ===" { s = ""; next } { s = s $0 "\n" } END { printf "%s", s }' "$log" | grep -m1 '✗' | sed 's/^ *//' | cut -c1-50)"
    fi
  fi
  printf '%-6s %-38s %-10s %s\n' "$id" "$titulo" "$estado" "$detalle"
done

# ── El tronco
# Entre "el worktree de la tarea da verde" y "main da verde" hay un paso que no tenía
# comando, y nos costó tener el repo de ejemplo publicado en rojo (BITACORA §13).
# Los gates corren por tarea; esto corre sobre lo que está mergeado.
if [ -x "$BASE/scripts/gate.sh" ]; then
  echo
  # Una sola corrida: estaba corriendo el gate DOS veces —una muda para el if y otra para
  # mostrar el error—, así que la suite del tronco se pagaba dos veces en cada estado.sh.
  salida="$( cd "$BASE" && TAREA= bash scripts/gate.sh 2>&1 )"
  rc=$?   # pegado a la asignación: cualquier cosa en el medio y esto lee el estado de ESO
  if [ "$rc" -eq 0 ]; then
    echo "tronco: ✓ verde"
  else
    # Durante una etapa tests-first el tronco está rojo POR DISEÑO: los tests de la etapa se
    # aceptan y commitean antes de que exista la implementación. Decir «ROJO» a secas es un
    # veredicto que no puede dar verde mientras eso dure, y un número que no puede fallar no
    # mide nada (MEDICION.md). Casi leí este rojo como una rotura real.
    en_vuelo=""
    for f in "$BASE"/tareas/T*.md; do
      [ -e "$f" ] || continue
      grep -q '^\*\*Estado:\*\* *✅' "$f" 2>/dev/null && continue
      # Mismo extractor que el paso 4 del gate: «Archivo: `x`, clase `Y`».
      t_decl="$(sed -n 's/.*`\([^`]*\)`, *clase `[A-Za-z0-9_]*`.*/\1/p' "$f" | head -1)"
      [ -n "$t_decl" ] && [ -f "$BASE/$t_decl" ] \
        && en_vuelo="$en_vuelo    $t_decl ← $(basename "$f" | cut -d- -f1), pendiente"$'\n'
    done
    # Las fallas se imprimen SIEMPRE, y «por diseño» se VERIFICA en vez de afirmarse. La
    # versión anterior se conformaba con que existiera algún test en vuelo y el `grep '✗'`
    # vivía sólo en el `else`, así que un tronco realmente roto no mostraba una sola falla.
    # Es el estado exacto de clasificados el 2026-10-19: etapa en vuelo Y T14 integrada con
    # un `from .conexion import get_db_connection` que abortaba la colección entera. El
    # informe decía «por diseño» y el ImportError quedaba invisible. Cambiar un rojo que no
    # medía por un rojo que se explica sin comprobar la explicación es la misma vacuidad.
    #
    # Granular, igual que `fallas_del_tronco` de `integrar.sh`: en modo integración el paso 1
    # del gate colapsa la suite entera en una línea constante, que no nombra ningún archivo.
    # ¿Está instalado lo que el proyecto declara? Por manifiesto, igual que
    # `preparar-entorno.sh`: con `requirements*.txt` hace falta el venv, con `package.json`
    # el node_modules de al lado.
    sin_entorno=""
    # Con `find` y no con `ls <glob> <glob>`: `ls` sale distinto de cero si CUALQUIERA de
    # sus argumentos no existe, así que con el manifiesto en `backend/` y nada en la raíz el
    # chequeo entero daba falso y el `.venv` faltante no se informaba. Lo vi corriendo esto.
    if [ -n "$(cd "$BASE" && find . -maxdepth 2 -name 'requirements*.txt' \
                 -not -path '*/.venv/*' 2>/dev/null)" ] \
       && [ ! -d "$BASE/.venv" ] && [ ! -d "$RAIZ/.venv" ]; then
      sin_entorno="$sin_entorno .venv"
    fi
    while IFS= read -r m; do
      [ -n "$m" ] || continue
      if [ ! -d "$(dirname "$m")/node_modules" ]; then
        sin_entorno="$sin_entorno $(dirname "$m")/node_modules"
      fi
    done <<EOF_M
$(cd "$BASE" && find . -maxdepth 2 -name package.json -not -path '*/node_modules/*' 2>/dev/null)
EOF_M

    # UNA falla por línea, para contar y para atribuir.
    fallas="$( ( cd "$BASE" && bash scripts/correr-suite.sh --fallas 2>/dev/null | grep . )
               printf '%s\n' "$salida" | grep '✗' \
                 | grep -v 'la suite está en rojo' | sed 's/^ *//' )"
    # Y el detalle, aparte: varios chequeos informan «✗ hay señales suprimidas:» y ponen el
    # DÓNDE en las líneas indentadas de abajo, así que quedarse con el ✗ solo deja un informe
    # que nombra la falla y no alcanza para actuar. Va aparte y no mezclado porque la primera
    # versión de esto contaba las líneas de detalle —y hasta la que sugiere el comando para
    # arreglarlo— como fallas: «14 falla(s)» donde había 8. Un contador que cuenta pistas es
    # un número que no mide lo que su nombre dice.
    detalle="$(printf '%s\n' "$salida" \
                 | awk '/✗/ {p=1} p && !/✗/ && !/^ {4,}/ {p=0} p' \
                 | grep -v 'la suite está en rojo' | sed 's/^ *//')"
    n_fallas="$(printf '%s\n' "$fallas" | grep -c .)"
    echo "tronco: ✗ rojo — $n_fallas falla(s):"
    printf '%s\n' "$fallas" | grep . | sed 's/^/    /'
    if [ "$(printf '%s\n' "$detalle" | grep -c .)" -gt "$n_fallas" ]; then
      echo "  detalle de los chequeos que no son la suite:"
      printf '%s\n' "$detalle" | grep . | sed 's/^/      /'
    fi
    if [ -n "$en_vuelo" ]; then
      echo "  tests de tareas pendientes ya commiteados:"
      printf '%s' "$en_vuelo"
      # ¿Cada falla la explica un test en vuelo? La que no, es del tronco y hay que verla.
      ajenas=""
      while IFS= read -r l; do
        [ -n "$l" ] || continue
        explicada=0
        while IFS= read -r t; do
          [ -n "$t" ] || continue
          # Las dos notaciones del mismo archivo. Los corredores nombran la falla como
          # MÓDULO —`tests.test_cosa`— y la tarea lo declara como RUTA —`tests/test_cosa.py`—,
          # así que comparar la ruta cruda marcaba como «no explicada» justo al test en vuelo
          # que la explica: un aviso que grita en cada etapa tests-first, o sea exactamente
          # cuando hay que poder creerle.
          mod="${t%.py}"; mod="$(printf '%s' "$mod" | tr / .)"
          case "$l" in *"$t"*|*"$mod"*) explicada=1 ;; esac
        done <<EOF_T
$(printf '%s' "$en_vuelo" | awk '{print $1}')
EOF_T
        [ "$explicada" -eq 0 ] && ajenas="$ajenas    $l"$'\n'
      done <<EOF_F
$(printf '%s\n' "$fallas" | grep .)
EOF_F
      if [ -z "$ajenas" ]; then
        echo "  Todas las fallas las nombra un test en vuelo: el rojo es POR DISEÑO y no"
        echo "  mide el tronco. Lo que mide es el gate de cada tarea, que descuenta la base."
      else
        echo "  ⚠ pero estas fallas NO las explica ningún test en vuelo:"
        printf '%s' "$ajenas"
        echo "  Ésas son del tronco: «por diseño» no las cubre."
      fi
    elif [ -n "$sin_entorno" ]; then
      # Ni del merge ni del modelo: este worktree no tiene instalado lo que su propio
      # manifiesto declara, así que la suite no corrió — no corrió y dio mal. Es la
      # distinción que `correr-suite.sh` codifica en su código 3 y que este informe estaba
      # perdiendo: imprimía ocho fallas de colección por `ModuleNotFoundError: pymysql` y
      # las atribuía a «lo mergeado sin pasar su propio gate». Acusar al merge por un
      # worktree sin entorno es nombrar mal al sujeto, que es la forma de la que habla
      # MEDICION.md §4.
      echo "  ⊘ este worktree no tiene entorno:$sin_entorno"
      echo "  Las fallas de arriba son de eso, no de lo mergeado. Este informe no mide el"
      echo "  tronco hasta que el entorno esté:"
      echo "    bash \$AGENTES/scripts/preparar-entorno.sh"
    else
      # «✗ ROJO» en mayúsculas, que es el veredicto: las fallas se imprimen siempre y
      # arriba, pero el rojo REAL tiene que distinguirse de un golpe de vista del rojo por
      # diseño. Al mover la lista de fallas antes de la decisión, el titular dejó de poder
      # distinguirlos —todavía no se sabe—, así que la distinción va en la línea final.
      echo "  tronco: ✗ ROJO — no hay tests de etapas en vuelo: esto es lo mergeado sin"
      echo "  pasar su propio gate."
    fi
  fi
fi
