#!/usr/bin/env bash
# Replanifica en DOS pasos, con un modelo distinto en cada uno.
#
#   DIAGNOSTICA=<id> ESCRIBE=<id> bash scripts/replanificar-relevo.sh T04
#
# Por qué partirlo: los perfiles medidos son complementarios, no mejores o peores.
#   Qwen3.8-27B     razonamiento 6/6 · replanificando NO llamó a write
#   openhands-32b   razonamiento 3/6 · 3 herramientas en 1088 líneas
#   Qwen3-Coder-30B razonamiento 2/6 · gate verde, 8 herramientas
#
# Unos diagnostican y otros ejecutan. Con un solo agente, el diagnóstico correcto del
# arquitecto de T04 —«falló la fase que escribe los tests, los módulos que el test necesita
# no existen todavía»— se perdió porque el mismo modelo tenía que además escribir.
#
# Lo que se relevan es TEXTO, no estado oculto: el diagnóstico. Es lo que tiene valor y lo
# único que sobrevive al relevo.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"
[ $# -ge 1 ] || { echo "uso: DIAGNOSTICA=<id> ESCRIBE=<id> $0 TNN" >&2; exit 1; }
: "${DIAGNOSTICA:?falta DIAGNOSTICA=<id de modelo>}"
: "${ESCRIBE:?falta ESCRIBE=<id de modelo>}"

for id in "$@"; do
  archivo="$(ls "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  [ -n "$archivo" ] || { echo "✗ $id: no existe tareas/${id}-*.md" >&2; continue; }
  FALLIDOS="$RAIZ/../fallidos-$id"
  ULTIMO="$(ls -t "$FALLIDOS"/*.log 2>/dev/null | head -1)"
  TEST_TAREA="$(sed -n 's/.*Archivo: `\([^`]*\)`.*/\1/p' "$archivo" 2>/dev/null | head -1)"
  if [ -n "$TEST_TAREA" ] && [ ! -f "$BASE/$TEST_TAREA" ]; then
    FASE="Falló la fase que ESCRIBE los tests: '$TEST_TAREA' todavía no existe. El enunciado dice que ya está en el repo porque está escrito para la fase siguiente; ignorá esa frase."
  else
    FASE="El test '$TEST_TAREA' existe y falló la IMPLEMENTACIÓN contra él."
  fi
  MOTIVO="$FASE  Lo que falló: $(sed 's/\x1b\[[0-9;]*m//g' "${ULTIMO:-/dev/null}" 2>/dev/null \
            | grep -E '✗|por qué falla' | head -6 | sort -u | tr '\n' ' ' | cut -c1-500)"

  # ── 1. DIAGNOSTICAR. No toca ningún archivo del plan: sólo escribe su análisis.
  DIAG="$BASE/.diagnostico-$id.md"; rm -f "$DIAG"
  echo "▶ $id · paso 1: diagnostica $DIAGNOSTICA"
  export LOG_VIGILADO="$BASE/.relevo-$id-diag.log"
  ( cd "$BASE" || exit 1
    export XDG_DATA_HOME="$BASE/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    con_limite "${LIMITE_AGENTE:-1800}" opencode run --model "colabhive/$DIAGNOSTICA" \
      "Mirá SOLO el archivo de la tarea, PLAN.md y, si hace falta, los archivos que la tarea nombra. NO explores .venv, node_modules, .git ni ningún directorio de dependencias: no tienen nada que ver con el enunciado y hay decenas de miles de archivos ahí. La tarea tareas/$(basename \"$archivo\") falló, y el motivo es cómo está escrita, no el agente que la intentó. $MOTIVO. Leé la tarea y PLAN.md. NO modifiques ningún archivo del plan ni de las tareas. NO escribas ningún archivo: tu respuesta ES el entregable. Decí: (1) qué le falta o le sobra al enunciado para que el defecto no pueda repetirse, (2) para cada cosa que la tarea nombra, DÓNDE vive: archivo exacto e import exacto, (3) si falta algo que ninguna tarea del plan entrega, escribí la palabra HUECO y qué falta. Sé concreto y breve." 2>&1
  ) > "$LOG_VIGILADO" 2>&1
  E="$(error_del_agente "$LOG_VIGILADO" 2>/dev/null)"
  [ -n "$E" ] && { echo "  ✗ el diagnóstico no se pudo hacer: $E"; continue; }
  # El diagnóstico se LEVANTA del transcript, no se le pide que lo escriba. Medido tres
  # veces con dos modelos: el que razona mejor no llama a `write` —el 27B produjo 19 KB de
  # análisis correcto y cero archivos—. Pedirle que escriba es pedirle lo que no hace.
  # Su respuesta ya es el entregable; el arnés la levanta y se la pasa al que sí escribe.
  # Eso es relevar el stream: lo que viaja es texto, y el texto ya estaba.
  sed 's/\x1b\[[0-9;]*m//g' "$LOG_VIGILADO" | grep -vE '^(→|✱|\$) ' | grep -v '^\s*$' > "$DIAG"
  [ -s "$DIAG" ] || { echo "  ✗ $DIAGNOSTICA no dijo nada. Log: $LOG_VIGILADO"; continue; }
  echo "  ✓ diagnóstico de $(wc -c < "$DIAG" | tr -d ' ') bytes"
  # El patrón acepta marcas de markdown INTERCALADAS, y también la lista numerada. El
  # 2026-10-24 el diagnóstico de T05c dijo «- **HUECO**: No existe función para listar todos
  # los anuncios» y el regex viejo —`[*#>-]*` UNA sola vez antes de los espacios— no
  # matcheaba «- **HUECO»: guión, espacio, asteriscos. El hueco del plan se perdió, el relevo
  # siguió al paso 2 y gastó otro agente de 16 minutos en una tarea que requería una decisión
  # de producto. Mismo defecto de extractor frágil que el `grep '→'` de mutar.py y el motivo
  # que era una categoría.
  #
  # Las dos apariciones llevan el MISMO patrón. En `replanificar.sh` arreglé el `grep -q` que
  # detecta y dejé el `grep -A3` que imprime con el viejo: el aviso se disparaba y no mostraba
  # el hueco. Un arreglo a medias dentro del mismo `if`, que es la forma que este repo repite.
  if grep -qE '^[0-9.)[:space:]*#>_-]*HUECO' "$DIAG" 2>/dev/null; then
    echo "  ⃠ dice que falta algo que ninguna tarea entrega — lo decide una persona:"
    grep -A2 -E '^[0-9.)[:space:]*#>_-]*HUECO' "$DIAG" | head -4 | sed 's/^/     /'
    continue
  fi

  # ── 2. ESCRIBIR, con el diagnóstico ya hecho. El que escribe no tiene que diagnosticar.
  CRIT_ANTES="$(grep -c '^- \[ \]' "$archivo" || true)"
  TEST_ANTES="$(grep -oE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`.*clase `[A-Za-z0-9_]+`' "$archivo" | head -1)"
  cp "$archivo" "$archivo.previo"
  # El que escribe NO reescribe el archivo entero: produce SÓLO las secciones que puede
  # cambiar, y el arnés reensambla conservando lo intocable textual. Cuatro intentos, cuatro
  # pérdidas distintas —los criterios, el archivo de test, el encabezado— porque pedirle
  # «reescribí todo sin perder nada» es pedirle que recuerde no borrar. Es el mismo
  # principio que el paso 0 del gate: lo intocable no lo decide quien escribe.
  CAMBIABLE="$BASE/.replan-$id-cuerpo.md"; rm -f "$CAMBIABLE"
  echo "▶ $id · paso 2: reescribe $ESCRIBE"
  export LOG_VIGILADO="$BASE/.relevo-$id-esc.log"
  ( cd "$BASE" || exit 1
    export XDG_DATA_HOME="$BASE/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    con_limite "${LIMITE_AGENTE:-1800}" opencode run --model "colabhive/$ESCRIBE" \
      "Mirá SOLO tareas/$(basename "$archivo") y .diagnostico-$id.md. NO explores .venv, node_modules ni .git. Otro agente ya diagnosticó por qué esta tarea falló; su diagnóstico está en .diagnostico-$id.md. Tu trabajo es UNO SOLO: escribí con la herramienta write el archivo '.replan-$id-cuerpo.md' con las secciones del MEDIO de la tarea ya corregidas —desde '## Objetivo' hasta justo antes de '## Tests'— aplicando ese diagnóstico. No vuelvas a diagnosticar. NO escribas el encabezado, ni la sección Tests, ni los criterios de terminado: ésos los conserva el sistema y no te corresponden. Lo más útil que podés hacer es decir DÓNDE vive cada cosa que la tarea nombra: archivo exacto e import exacto." 2>&1
  ) > "$LOG_VIGILADO" 2>&1
  E="$(error_del_agente "$LOG_VIGILADO" 2>/dev/null)"
  if [ -n "$E" ]; then echo "  ✗ la reescritura no se pudo hacer: $E"; mv "$archivo.previo" "$archivo"; continue; fi
  if [ ! -s "$CAMBIABLE" ]; then echo "  ✗ $ESCRIBE no escribió el cuerpo nuevo"; mv "$archivo.previo" "$archivo"; continue; fi

  # Reensamblado: encabezado original + cuerpo nuevo + Tests y criterios originales.
  python3 - "$archivo.previo" "$CAMBIABLE" "$archivo" <<'PYR'
import sys, pathlib
orig = pathlib.Path(sys.argv[1]).read_text()
cuerpo = pathlib.Path(sys.argv[2]).read_text().strip() + "\n"
i = orig.index("## Objetivo")
j = orig.index("## Tests")
pathlib.Path(sys.argv[3]).write_text(orig[:i] + cuerpo + "\n" + orig[j:])
PYR

  mal=""
  cmp -s "$archivo" "$archivo.previo" && mal="no reescribió nada"
  # UNA TAREA, UN DOCUMENTO. El enunciado tiene que seguir siendo UN enunciado.
  #
  # El 2026-10-23 el relevo "replanificó" T28 agregando una versión nueva COMPLETA al final
  # en vez de reemplazar la vieja: el archivo pasó de 59 a 96 líneas con dos `# T28`, dos
  # `**Estado:**` y dos `## Tests`. Y los cuatro jueces lo aprobaron —validar-plan.py dijo
  # que el plan validaba, los criterios habían AUMENTADO y la declaración de test duplicada
  # coincidía con la original—, porque todos miran propiedades del contenido y ninguno
  # pregunta si el documento sigue siendo uno.
  #
  # Es el mismo agujero que un bullet comido unas horas antes, en escala mayor: 37 líneas
  # duplicadas en vez de un guion de menos. Lo que faltaba no era otro chequeo de contenido
  # sino uno de INTEGRIDAD.
  for enc in '^# T[0-9]' '^\*\*Estado:' '^## Tests'; do
    n="$(grep -c "$enc" "$archivo" || true)"
    # Sin «» alrededor de la variable: el patrón lleva `[`, `*` y `#`, y pegado a un
    # multibyte el mensaje sale cortado («duplicado: 2 veces «?»). Es el mismo defecto de
    # portabilidad que TestPortabilidadBash32 vigila y que ya cometí hoy con «$tid».
    [ "${n:-0}" -le 1 ] || mal="${mal:+$mal; }el enunciado quedó duplicado: $n veces el patron $enc"
  done
  CRIT_DESPUES="$(grep -c '^- \[ \]' "$archivo" || true)"
  [ "${CRIT_DESPUES:-0}" -lt "${CRIT_ANTES:-0}" ] && mal="${mal:+$mal; }achicó los criterios: $CRIT_ANTES → $CRIT_DESPUES"
  TEST_DESPUES="$(grep -oE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`.*clase `[A-Za-z0-9_]+`' "$archivo" | head -1)"
  [ -n "$TEST_ANTES" ] && [ "$TEST_ANTES" != "$TEST_DESPUES" ] && mal="${mal:+$mal; }cambió el archivo o la clase de test"
  (cd "$BASE" && PLAN=PLAN.md python3 "$AQUI/validar-plan.py" >/dev/null 2>&1) || mal="${mal:+$mal; }el plan dejó de validar"

  if [ -n "$mal" ]; then
    echo "  ✗ se descarta: $mal"; mv "$archivo.previo" "$archivo"
  else
    echo "  ✓ $id replanificada por relevo ($DIAGNOSTICA → $ESCRIBE) y el plan valida"
    diff -u "$archivo.previo" "$archivo" | grep -E '^[+][^+]' | head -10 | sed 's/^/     /'
    rm -f "$archivo.previo"
  fi
done
