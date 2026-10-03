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
CODIGO="${CODIGO:-src}"

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

  wt="$RAIZ/../tests-$id"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "tests/$id" 2>/dev/null
  git -C "$RAIZ" worktree add -q -b "tests/$id" "$wt" || { echo "✗ $id: no pude crear el worktree"; continue; }

  log="$wt/.tests.log"
  echo "▶ $id · $AGENTE escribe $ruta::$clase"
  (
    cd "$wt/$PROYECTO" || exit 1
    export XDG_DATA_HOME="$wt/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    opencode run --agent "$AGENTE" \
      "Leé tareas/$(basename "$archivo"). Tu trabajo es escribir SUS TESTS, no la implementación definitiva.

Escribí exactamente dos archivos, con la herramienta write:

1. '$ruta', con una clase '$clase', que verifique el criterio de terminado de la tarea. Cada test tiene que fallar si la implementación no hace lo que dice el alcance, y tiene que distinguir: un assert que pasaría igual con el código viejo no sirve de nada. Nada de 'assertTrue(len(x) > 0)'.
2. '$CODIGO/_referencia_$id.py', una implementación MÍNIMA que haga pasar esos tests. Es descartable: se usa sólo para comprobar que los tests son correctos y después se borra. No la importes desde el test: el test tiene que importar del módulo real que la tarea va a escribir.

No toques ningún otro archivo." 2>&1
  ) > "$log" 2>&1

  cd "$wt/$PROYECTO" || continue
  fallos=0
  if [ ! -f "$ruta" ] || ! grep -q "class $clase" "$ruta" 2>/dev/null; then
    echo "  ✗ no escribió $ruta con la clase $clase"; fallos=1
  else
    # 1. El test tiene que fallar sin implementación.
    if python3 -m unittest "$(echo "${ruta%.py}" | tr / .).$clase" >/dev/null 2>&1; then
      echo "  ✗ el test PASA sin implementación: no prueba nada"; fallos=1
    else
      echo "  ✓ falla sin implementación"
    fi
    # 2. Con la referencia tiene que pasar. Si no, el test está mal escrito.
    ref="$(ls "$CODIGO"/_referencia_"$id".py 2>/dev/null | head -1)"
    if [ -z "$ref" ]; then
      echo "  ✗ no escribió la implementación de referencia: no se puede validar el test"; fallos=1
    else
      # La referencia se pone donde la tarea dice que va a vivir el módulo real.
      destino="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/$(basename "$archivo")" \
                 | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+\.py' | head -1)"
      if [ -n "$destino" ]; then
        [ -f "$destino" ] && cp "$destino" "$destino.previo"
        cp "$ref" "$destino"
        if python3 -m unittest "$(echo "${ruta%.py}" | tr / .).$clase" >/dev/null 2>&1; then
          echo "  ✓ pasa con la implementación de referencia"
          # 3. Y los mutantes de la referencia tienen que morir.
          git add -A >/dev/null 2>&1; git commit -q -m "ref $id" >/dev/null 2>&1
          if BASE=HEAD~1 CODIGO="$CODIGO" SUITE="python3 -m unittest $(echo "${ruta%.py}" | tr / .).$clase" \
               python3 "$AQUI/mutar.py" >/dev/null 2>&1; then
            echo "  ✓ los mutantes de la referencia mueren: el test distingue"
          else
            echo "  ✗ sobreviven mutantes: el test cubre la línea pero no verifica su comportamiento"; fallos=1
          fi
          git reset -q --hard HEAD~1 >/dev/null 2>&1
        else
          echo "  ✗ el test NO pasa con una implementación que debería hacerlo pasar: el test está mal"; fallos=1
        fi
        [ -f "$destino.previo" ] && mv "$destino.previo" "$destino" || rm -f "$destino"
      fi
    fi
  fi

  if [ "$fallos" -eq 0 ]; then
    # Al tronco llega SÓLO el test. La referencia se queda en el worktree, que se tira.
    mkdir -p "$(dirname "$BASE/$ruta")"
    cp "$ruta" "$BASE/$ruta"
    echo "  ✓ $id: $ruta aceptado y copiado al tronco (la referencia se descarta)"
  else
    echo "  ✗ $id: los tests no se aceptan. Log: $log"
  fi
  cd "$RAIZ" || true
done

echo
echo "Los tests aceptados están en el tronco sin commitear. Revisalos y commiteá:"
echo "  git -C $RAIZ diff --stat && git -C $RAIZ add -A && git -C $RAIZ commit -m 'tests de <tareas>'"
echo "Los worktrees de validación se pueden tirar: git worktree remove ../tests-TNN"
