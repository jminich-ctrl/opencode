#!/usr/bin/env bash
# Escribe los tests de una tarea, y los valida mecánicamente antes de aceptarlos.
#
#   bash $AGENTES/scripts/escribir-tests.sh T03
#   bash $AGENTES/scripts/escribir-tests.sh T03 T04 T05
#
# Por qué existe: escribir los tests era lo último del método que seguía siendo trabajo
# manual, y con un plan de 28 tareas eso son 28 archivos a mano. Es también lo que el
# método declara no delegable, porque lo medimos: en 15 tareas el agente nunca falló
# implementando algo especificado y falló CUATRO VECES escribiendo tests que probaran algo
# —asserts como `assertTrue(len(x) > 0)` que pasan igual con el código viejo—.
#
# **La salida no es delegarlo igual: es delegarlo detrás de un gate que ataque esa falla.**
# El agente escribe el test Y una implementación de referencia que después se tira, y los
# tests se aceptan sólo si pasan estas cuatro:
#
#   1. El test FALLA contra el código actual. Si pasa, no prueba nada.
#   2. Con la implementación de referencia, PASA. Si no, el test está mal escrito —y es la
#      regla que nos costó dos corridas de A/B aprender a mano.
#   3. Los mutantes de la referencia MUEREN (scripts/mutar.py). Si sobreviven, el test
#      cubre la línea y no verifica su comportamiento: es el test vacuo, medido.
#   4. El archivo y la clase son exactamente los que declara el plan.
#
# La referencia se descarta siempre: al tronco sólo llega el archivo de test. El worktree
# es desechable, así que el tronco nunca ve la implementación de referencia.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
[ $# -ge 1 ] || { echo "uso: $0 TNN [TNN ...]" >&2; exit 1; }

AGENTE="${AGENTE:-tester}"
# Cuántas veces se reintenta la escritura de un test que no pasa su validación. Sin
# esto, una generación inconsistente —el test del agente contra la implementación del
# agente— paraba la corrida y pedía una persona.
REINTENTOS_TESTS="${REINTENTOS_TESTS:-2}"

# Diagnostica y deja el motivo anotado para el reintento.
malo() { echo "  ✗ $1"; MOTIVO_TESTS="$1"; fallos=1; }
# Uno o varios directorios de código, separados por coma. El Pacman tiene uno (`src`); un
# proyecto con back y front tiene dos. Asumir uno era un supuesto que se colaba de calibrar
# contra un solo proyecto.
CODIGO="${CODIGO:-src}"
PATRON_CODIGO="^($(echo "$CODIGO" | tr ',' '|'))/"

# El tester es subagente y desde la CLI cae al agente por defecto sin avisar (OPENCODE.md §3).
# Para escribir archivos hace falta un primario; `ejecutor` es el que tiene el harness flaco.
opencode agent list 2>/dev/null | grep -qE "^$AGENTE \(primary\)" || AGENTE="ejecutor"

for id in "$@"; do
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  [ -n "$archivo" ] || { echo "✗ $id: no existe tareas/${id}-*.md"; continue; }

  # Qué test pide el plan para esta tarea: archivo y clase, de su propia tabla.
  esperado="$(sed -n "s/^| *$id *| *\`\{0,1\}\([^ |\`]*\)\`\{0,1\} *| *\`\{0,1\}\([A-Za-z0-9_]*\)\`\{0,1\} *|.*/\1 \2/p" \
              "$BASE/PLAN.md" | head -1)"
  if [ -z "$esperado" ]; then
    esperado="$(sed -n 's/.*`\(tests\/[A-Za-z0-9_./]*\)`.*clase `\([A-Za-z0-9_]*\)`.*/\1 \2/p' "$archivo" | head -1)"
  fi
  ruta="$(echo "$esperado" | cut -d' ' -f1)"; clase="$(echo "$esperado" | cut -d' ' -f2)"
  if [ -z "$ruta" ] || [ -z "$clase" ]; then
    echo "✗ $id: ni el plan ni la tarea declaran archivo y clase de test. Eso lo decide quien planifica."
    continue
  fi

  if [ -f "$BASE/$ruta" ] && grep -q "class $clase" "$BASE/$ruta" 2>/dev/null; then
    echo "· $id: $ruta ya tiene $clase — no se toca (reescribir lo que pasa lo empeora)"
    continue
  fi

  intento=1; MOTIVO_TESTS=""; HUELLA_ANTERIOR=""
  while :; do
  wt="$RAIZ/../tests-$id"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "tests/$id" 2>/dev/null
  git -C "$RAIZ" worktree add -q -b "tests/$id" "$wt" || { echo "✗ $id: no pude crear el worktree"; break; }
  # El worktree es nuevo: no tiene venv ni node_modules. Sin esto, una tarea de frontend
  # se rechaza por falta de corredor, que es un defecto del método y no del test.
  bash "$AQUI/preparar-entorno.sh" "$wt/$PROYECTO" 2>&1 | sed 's/^/  /'
  # El venv del tronco, igual que en correr-tarea.sh: el del worktree es un enlace, pero
  # si el enlace no está, el validador correría con el intérprete del sistema y no vería
  # las dependencias — y el diagnóstico que saldría es "el test está mal".
  if [ -x "$BASE/.venv/bin/python" ]; then export PY_PROYECTO="$BASE/.venv/bin/python"; fi


  log="$wt/.tests.log"
  echo "▶ $id · $AGENTE escribe $ruta::$clase"
  (
    cd "$wt/$PROYECTO" || exit 1
    export XDG_DATA_HOME="$wt/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    opencode run --agent "$AGENTE" \
      "${MOTIVO_TESTS:+Un intento anterior falló así: $MOTIVO_TESTS. No repitas ese camino. }Leé tareas/$(basename \"$archivo\"). Hacé la tarea completa: la implementación Y sus tests.

Dos cosas, las dos con la herramienta write:

1. La implementación, en los archivos que la tarea declara en 'Archivos que podés tocar'.
2. '$ruta', con una clase '$clase', que verifique el criterio de terminado. Cada test tiene que fallar si la implementación no hace lo que dice el alcance, y tiene que DISTINGUIR: un assert que pasaría igual con el código de antes no sirve de nada. Nada de 'assertTrue(len(x) > 0)'.

De tu trabajo nos vamos a quedar SÓLO con los tests: la implementación la va a escribir otro agente desde cero. Así que los tests son el entregable, y tienen que ser buenos.

Antes de decir que terminaste, corré 'bash scripts/correr-suite.sh $ruta::$clase' y mostrá su salida real. Tienen que pasar: si tu test no pasa contra tu propia implementación, uno de los dos está mal y lo tenés que arreglar vos, no nosotros. Ese es el comando con el que te vamos a juzgar, así que no uses otro.

No toques ningún otro archivo." 2>&1
  ) > "$log" 2>&1

  cd "$wt/$PROYECTO" || break
  # Otra vez, porque el agente pudo CREAR el manifiesto: T30 escribe el package.json con
  # vitest, y recién ahora se sabe que hace falta instalarlo.
  bash "$AQUI/preparar-entorno.sh" "$wt/$PROYECTO" >> "$log" 2>&1
  fallos=0

  # 0. Alcance. Va PRIMERO porque sin esto el chequeo 1 miente: si el agente implementó la
  # feature en el archivo real, el test pasa y el gate concluye "el test no prueba nada",
  # que es el diagnóstico equivocado. Nos pasó en la primera corrida.
  # Los permitidos salen del archivo de tarea, igual que en el gate: una lista escrita acá
  # a mano queda vieja en cuanto el plan crece.
  # Las rutas declaradas, tal cual: archivos y directorios. El patrón es genérico porque
  # una lista de extensiones escrita a mano envejece con el primer stack nuevo.
  RUTAS_OK="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/$(basename "$archivo")" \
              | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+(\.[A-Za-z0-9]+|/)' | sort -u)"
  PERMITIDOS="$(echo "$RUTAS_OK" | sed 's#/$#/.*#; s#^#^#; s#$#$#' | tr '\n' '|' | sed 's/|$//')"
  TOCADOS="$(git diff --name-only --relative HEAD 2>/dev/null; git ls-files --others --exclude-standard)"
  # Ojo: `$$` en bash es el PID, no un `$` literal. Armar el patrón en una variable aparte
  # evita esa clase de error, que en un grep no falla: deja de matchear y todo queda "fuera".
  # El lock lo escribe nuestro `npm install` al preparar el entorno, no el agente.
  PATRON_OK="^($ruta|\.tests\.log|\.opencode-data/.*|([A-Za-z0-9_-]+/)?package-lock\.json)\$"
  [ -n "$PERMITIDOS" ] && PATRON_OK="$PATRON_OK|$PERMITIDOS"
  FUERA="$(echo "$TOCADOS" | grep -vE "$PATRON_OK" | grep . || true)"
  if [ -n "$FUERA" ]; then
    malo "tocó archivos que no le corresponden a esta etapa:$(echo " $FUERA" | tr '\n' ' ')"
    echo "     Puede tocar los archivos de la tarea y su archivo de test. Nada más."
  else
    echo "  ✓ sólo tocó el test y los archivos de la tarea"
  fi

  if [ "$fallos" -eq 0 ] && { [ ! -f "$ruta" ] || ! grep -q "class $clase" "$ruta" 2>/dev/null; }; then
    malo "no escribió $ruta con la clase $clase"
  fi

  # La validación del test, en tres pasos. Los archivos que la tarea declara son la
  # implementación: se revierten para comprobar que el test falla, se restauran para
  # comprobar que pasa, y se mutan para comprobar que el test distingue. La implementación
  # no se queda: el entregable es el test.
  if [ "$fallos" -eq 0 ]; then
    # La implementación es lo que la tarea declara, no lo que matchea $CODIGO. T03
    # entrega dos `.sql` en `backend/migraciones/`, que no está en CODIGO: el validador
    # no veía implementación y rechazaba el test del agente por algo que el agente hizo
    # bien. La autoridad es el archivo de tarea, igual que para el alcance.
    impl="$(echo "$TOCADOS" | grep -E "$PERMITIDOS" | grep -v "^$ruta$" || true)"
    # El comando es el del proyecto, no uno que armemos acá: `scripts/correr-suite.sh`
    # es el mismo que usa el gate para juzgar. Mientras cada uno tenía el suyo, diferían en
    # el cwd, el PYTHONPATH, el corredor y sus flags, y cada diferencia producía un test
    # imposible de pasar que esto informaba como "el test está mal".
    if [ ! -f scripts/correr-suite.sh ]; then
      echo "  ✗ $id: el proyecto no tiene scripts/correr-suite.sh, así que no hay una sola"
      echo "     forma de correr la suite. Copiala de plantillas/correr-suite.sh y adaptala."
      fallos=1
    fi
    prueba="bash scripts/correr-suite.sh \"$ruta::$clase\""
    # mutar.py muta Python. Para TypeScript no hay mutador: el paso se marca ⊘ y no cuenta
    # como pase (METODO.md P3).
    case "$ruta" in *.py) MUTABLE=1 ;; *) MUTABLE=0 ;; esac

    if [ "$fallos" -ne 0 ]; then :
    elif [ -z "$impl" ]; then
      malo "no escribió implementación: sin ella no se puede validar el test"
    else
      tmp="$(mktemp -d)"
      for f in $impl; do
        cp "$f" "$tmp/$(echo "$f" | tr / _)"
        git checkout HEAD -- "$f" 2>/dev/null || rm -f "$f"
      done
      if eval "$prueba" >/dev/null 2>&1; then
        malo "el test PASA con el código de antes: no prueba nada"
      else
        echo "  ✓ falla sin la implementación"
      fi
      for f in $impl; do cp "$tmp/$(echo "$f" | tr / _)" "$f"; done
      rm -rf "$tmp"
      if eval "$prueba" >/dev/null 2>&1; then
        echo "  ✓ pasa con la implementación"
        git add -A >/dev/null 2>&1
        git commit -q -m "impl+tests $id (worktree desechable)" >/dev/null 2>&1
        if [ "$MUTABLE" != "1" ]; then
          echo "  ⊘ no hay mutador para «$ruta»: el test pasa los dos primeros pasos y el"
          echo "     tercero (¿distingue?) no pudo verificarse. No es un pase."
        elif BASE=HEAD~1 CODIGO="$CODIGO" SUITE="$prueba" python3 "$AQUI/mutar.py" >/dev/null 2>&1; then
          echo "  ✓ los mutantes mueren: el test distingue"
        else
          SOBREVIVEN="$(BASE=HEAD~1 CODIGO="$CODIGO" SUITE="$prueba" python3 "$AQUI/mutar.py" 2>&1 \
                         | grep '→' | head -3 | tr '\n' ' ' | cut -c1-400)"
          malo "sobreviven mutantes: el test cubre las líneas y no verifica su comportamiento.${SOBREVIVEN:+ Sobrevivió: $SOBREVIVEN}"
          echo "$SOBREVIVEN" | tr ';' '\n' | sed 's/^/     /'
        fi
      else
        # El motivo lleva el fallo real, no su categoría: el nombre del test que falla y el
        # mensaje del assert. Sin eso el reintento no tiene nada nuevo con lo que trabajar,
        # y se vio: T02 falló dos veces por lo mismo recibiendo sólo "el test está mal".
        DETALLE="$(eval "$prueba" 2>&1 \
                   | grep -E '^E +[A-Za-z_.]*(Error|Exception|AssertionError)|^(FAILED|FAIL:) ' \
                   | head -3 | tr '\n' ' ' | cut -c1-400)"
        malo "el test no pasa ni con la implementación del propio agente.${DETALLE:+ Falla así: $DETALLE}"
      fi
    fi
  fi

  if [ "$fallos" -eq 0 ]; then
    # Al tronco llega SÓLO el test. La referencia se queda en el worktree, que se tira.
    mkdir -p "$(dirname "$BASE/$ruta")"
    cp "$ruta" "$BASE/$ruta"
    echo "  ✓ $id: $ruta aceptado y copiado al tronco (la implementación se descarta)"
    cd "$RAIZ" || true
    break
  fi

  [ -n "$MOTIVO_TESTS" ] || MOTIVO_TESTS="la validación del test no pasó"
  cd "$RAIZ" || true

  # Misma regla de corte que correr-plan.sh: reintentar a ciegas gasta tiempo en la falla
  # que no se va a ir sola. Si el motivo repite, es la misma falla.
  if [ "$MOTIVO_TESTS" = "$HUELLA_ANTERIOR" ]; then
    echo "  ✗ $id: punto muerto — falló dos veces por lo mismo: $MOTIVO_TESTS"
    echo "     Log: $log"
    break
  fi
  HUELLA_ANTERIOR="$MOTIVO_TESTS"
  intento=$((intento+1))
  if [ "$intento" -gt "$REINTENTOS_TESTS" ]; then
    echo "  ✗ $id: los tests no se aceptan después de $REINTENTOS_TESTS intento(s). Log: $log"
    break
  fi
  echo "  · $id: reintento $intento — $MOTIVO_TESTS"
  done
done

echo
echo "Los tests aceptados están en el tronco sin commitear. Revisalos y commiteá:"
echo "  git -C $RAIZ diff --stat && git -C $RAIZ add -A && git -C $RAIZ commit -m 'tests de <tareas>'"
echo "Los worktrees de validación se pueden tirar: git worktree remove ../tests-TNN"
