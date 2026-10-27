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
cargar_entorno_colabhive
[ $# -ge 1 ] || { echo "uso: $0 TNN [TNN ...]" >&2; exit 1; }

AGENTE="${AGENTE:-tester}"
# Cuántas veces se reintenta la escritura de un test que no pasa su validación. Sin
# esto, una generación inconsistente —el test del agente contra la implementación del
# agente— paraba la corrida y pedía una persona.
REINTENTOS_TESTS="${REINTENTOS_TESTS:-2}"
# Los cortes por cuelgue de la herramienta llevan cuenta aparte, y más generosa. No es lo
# mismo que una falla de contenido: ésa no se va a ir sola y reintentarla gasta modelo, pero
# un cuelgue intermitente sí se va —el mismo prompt anduvo seis de seis veces aislado—, así
# que reintentar es la respuesta correcta y no un gasto. Con los dos en la misma cuenta,
# dos cuelgues seguidos agotaban el presupuesto de una tarea que nunca llegó a fallar.
# Doce, no cinco. Con el cuelgue de arranque cortado a los 20s, doce cortes son cuatro
# minutos de sobrecarga en el peor caso —barato comparado con una corrida detenida— y el
# cuelgue es de la herramienta, no de la tarea: insistir es la respuesta correcta. T06 se
# quedó sin presupuesto con cinco y nunca llegó a producir un test.
CORTES_MAX="${CORTES_MAX:-12}"

# Y los cortes por LÍMITE TOTAL llevan su propia cuenta, mucho más corta.
#
# El presupuesto de arriba está justificado con esta cuenta, textual: «con el cuelgue de
# arranque cortado a los 20s, doce cortes son cuatro minutos de sobrecarga en el peor caso».
# Eso vale para el corte por INACTIVIDAD, que es el cuelgue transitorio de la herramienta:
# opencode inicializa y nunca le pide nada al modelo, y reintentar es la respuesta correcta.
#
# Un corte por límite total es otra cosa: el agente TRABAJÓ los 1200s y no terminó. Doce de
# esos no son cuatro minutos, son cuatro horas — y no dicen nada de la herramienta: dicen
# algo de la TAREA. Medido el 2026-10-19 en T05: tres cortes seguidos por límite total, cero
# por inactividad, y el tercer transcript mostraba al agente iterando contra un `ImportError`
# de una función que él mismo había inventado porque la tarea le exigía autorización sin
# decirle con qué. Con el presupuesto mezclado, el método se iba a quedar cuatro horas sin
# decir una palabra sobre un defecto del plan.
#
# `motivo_del_corte` ya distinguía los dos casos; lo que faltaba era usar la distinción.
CORTES_TOTAL_MAX="${CORTES_TOTAL_MAX:-2}"

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

  # Cómo se declara el agrupador depende del lenguaje, igual que más abajo. Con la forma
  # Python hardcodeada acá, un `.test.ts` que YA estaba bien en el tronco se reescribía en
  # cada corrida — contra la regla del propio método, «reescribir lo que pasa lo empeora»—.
  case "$ruta" in
    *.py)                                      YA="class $clase" ;;
    *.test.ts|*.test.tsx|*.test.js|*.test.jsx) YA="describe" ;;
    *)                                         YA="$clase" ;;
  esac
  if [ -f "$BASE/$ruta" ] && grep -q "$YA" "$BASE/$ruta" 2>/dev/null \
     && grep -q "$clase" "$BASE/$ruta" 2>/dev/null; then
    echo "· $id: $ruta ya declara $clase — no se toca (reescribir lo que pasa lo empeora)"
    continue
  fi

  intento=1; cortes=0; cortes_total=0; MOTIVO_TESTS=""; HUELLA_ANTERIOR=""
  ENUNCIADO_ANTERIOR=""   # por tarea: sin esto la tarea hereda la huella de la anterior
  while :; do
  wt="$RAIZ/../tests-$id"
  # El transcript del intento anterior, ANTES de borrar el worktree. Es el único lugar
  # donde está escrito por qué falló, y recrear el worktree lo borraba: hoy lo perdí cuatro
  # veces y cada vez tuve que reproducir la corrida a mano, veinte minutos por vez, para
  # leer una línea. Cuando por fin leí una, la causa estaba ahí entera.
  #
  # Es el mismo defecto que un vigilante que corta antes del error, con otro mecanismo: el
  # método destruyendo la evidencia de sus propias fallas.
  if [ -f "$wt/.tests.log" ]; then
    FALLIDOS="$RAIZ/../fallidos-$id"; mkdir -p "$FALLIDOS"
    cp "$wt/.tests.log" "$FALLIDOS/intento-$(date -u +%Y%m%dT%H%M%SZ).log" 2>/dev/null \
      && echo "     (transcript del intento guardado en $FALLIDOS)"
  fi
  # ANTES del `rm -rf`, no después. Estaba al revés, y `conservar_intento` arranca con
  # `[ -d "$wt" ] || return 0`: era código muerto. El transcript sobrevivía de casualidad por
  # el `cp` manual de arriba —el arreglo viejo y parcial—, pero el PARCHE se perdía siempre.
  # Evidencia al descubrirlo: `fallidos-T26` tenía 9 transcripts y 0 parches, mientras
  # `fallidos-T05`, que pasa por correr-tarea.sh (el hermano que lo hace bien), tenía 3.
  # O sea que la fábrica de dataset no recogía NADA del camino de tests, que es justo donde
  # el método mide que el agente falla más: 4 de 15 escribiendo tests, 0 implementando.
  conservar_intento "$wt" "${id:-${TAREA:-tests}}"
  # La base se tira ANTES del `rm -rf`, no después. `tirar_base_del_worktree` necesita leer
  # el `.entorno` del worktree para saber CÓMO SE LLAMA la base, y el `rm -rf` se lo lleva:
  # la llamada quedaba antes de `worktree remove` —que es lo que pide el encabezado de la
  # función— y después del `rm -rf`, así que salía por su guarda sin tirar nada.
  #
  # Medido el 2026-10-25 en los tres intentos de T26: la base de un worktree NUNCA se tiraba
  # entre intentos. El intento siguiente la encontraba con lo que dejó el anterior —el log lo
  # delata, porque no vuelve a decir «aplicando migración»— y el validador chocaba con
  # `Duplicate entry 'test@example.com'` en su segunda pasada. Eso se informaba como un ⊘
  # cuya explicación decía «hay que limpiar la base entre pasadas o aislarla por corrida»:
  # las dos cosas ya estaban hechas, y lo que faltaba era esto.
  tirar_base_del_worktree "$wt"
  rm -rf "$wt"
  git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
  git -C "$RAIZ" branch -D "tests/$id" 2>/dev/null
  # El mismo guardia que correr-tarea.sh, y por la misma razón: el worktree sale de HEAD.
  # Acá la consecuencia es PEOR —allá se pierde una corrida, acá se acepta y se copia al
  # tronco el test del enunciado viejo—, porque la validación compara el test del agente
  # contra la implementación de referencia del propio agente, las dos escritas contra el
  # enunciado que el agente vio. Los tres pasos pasan y el artefacto equivocado aterriza.
  tarea_sin_commitear "$id" || break
  git -C "$RAIZ" worktree add -q -b "tests/$id" "$wt" || { echo "✗ $id: no pude crear el worktree"; break; }
  # El enunciado que el agente va a leer es el de ESTE worktree, recién salido de HEAD. Si
  # cambió desde el intento anterior, el sujeto es otro y los contadores arrancan de cero:
  # ver `huella_enunciado` en _comun.sh. MOTIVO_TESTS y HUELLA_ANTERIOR también, porque
  # «un intento anterior falló así, no repitas ese camino» se le inyecta en el pedido y ese
  # camino lo había causado el enunciado viejo.
  ENUNCIADO="$(huella_enunciado "$wt/$PROYECTO/tareas/$(basename "$archivo")")"
  if el_enunciado_cambio "$ENUNCIADO" "${ENUNCIADO_ANTERIOR:-}"; then
    echo "  · $id: el enunciado cambió — intentos y cortes vuelven a cero (sujeto nuevo)"
    intento=1; cortes=0; cortes_total=0; MOTIVO_TESTS=""; HUELLA_ANTERIOR=""
  fi
  ENUNCIADO_ANTERIOR="$ENUNCIADO"
  # El worktree es nuevo: no tiene venv ni node_modules. Sin esto, una tarea de frontend
  # se rechaza por falta de corredor, que es un defecto del método y no del test.
  bash "$AQUI/preparar-entorno.sh" "$wt/$PROYECTO" 2>&1 | sed 's/^/  /'

  # La base del diff y la LÍNEA BASE DE TESTS, antes de que el agente toque nada —igual que
  # hace `correr-tarea.sh` para la etapa de implementación, y por el mismo motivo, que su
  # propio comentario explica: «el método es tests-first, al empezar la etapa el tronco tiene
  # los tests de todas sus tareas y la implementación de ninguna, así que la suite no puede
  # estar verde; sin esta lista el gate de cada tarea la vería roja por los tests de sus
  # hermanas y ninguna podría cerrar».
  #
  # Esta etapa no las escribía, y el efecto lo medimos el 2026-10-20 con T05a: `AGENTS.md`
  # manda correr el gate, el gate del worktree de tests no tenía línea base, las 3 fallas
  # preexistentes del tronco (de T26 y T04b, ya mergeadas, por `CR_CONN_HOST_ERROR`) se le
  # cobraban a la tarea, y el veredicto quedaba INSATISFACIBLE. El agente escribía su test y
  # su implementación, el gate le decía «la suite está en rojo», e iteraba hasta agotar los
  # 1200 s. Tres corridas, seis intentos, tres puntos muertos, todos informados como «habla
  # de la TAREA». No hablaban de la tarea.
  #
  # Quinta vez en el día que el arreglo vive en un hermano y no en el otro.
  git -C "$wt" rev-parse HEAD > "$wt/.base-ref"
  if [ -f "$wt/$PROYECTO/scripts/correr-suite.sh" ]; then
    ( cd "$wt/$PROYECTO" && bash scripts/correr-suite.sh --fallas > .tests-base 2>/dev/null ) || true
    # Sexta vez que el arreglo vivía en el hermano y no acá, y las dos mitades son del
    # hermano: `correr-tarea.sh` las tiene desde el 2026-10-26 con su comentario, y este
    # script seguía con el `|| echo 0` —que da «0\n0», porque `grep -c` IMPRIME 0 y ADEMÁS
    # sale 1— y sin la guarda. Lo delató el log de una corrida real: «· línea base: 0» y
    # «0 test(s) ya fallando» en dos líneas.
    N_BASE="$(grep -c . "$wt/$PROYECTO/.tests-base" 2>/dev/null)"; N_BASE="${N_BASE:-0}"
    echo "  · línea base: ${N_BASE} test(s) ya fallando"
    # Y la otra mitad: con la línea base vacía y la suite roja, el gate le cobra a esta tarea
    # las fallas de sus hermanas, que es justo lo que la línea base existe para evitar. Este
    # script lanza una corrida de agente igual que `correr-tarea.sh`, así que frenar antes
    # vale lo mismo acá: el gate juzga al CERRAR, cuando ya se gastó.
    ( cd "$wt/$PROYECTO" && bash scripts/correr-suite.sh >/dev/null 2>&1 ); RC_SUITE_BASE=$?
    if [ "$RC_SUITE_BASE" = "1" ] && [ "$N_BASE" = "0" ]; then
      echo "✗ la suite está en ROJO y la línea base salió VACÍA." >&2
      echo "  La función «fallas» de scripts/correr-suite.sh no entiende la salida de este" >&2
      echo "  corredor: es un EXTRACTOR y sabe del stack, igual que «correr_suite». Con la" >&2
      echo "  lista vacía el gate le va a cobrar a $id las fallas de sus hermanas." >&2
      echo "  Arreglá el patrón de «fallas» y volvé a lanzar." >&2
      continue
    fi
  fi
  # El venv del tronco, igual que en correr-tarea.sh: el del worktree es un enlace, pero
  # si el enlace no está, el validador correría con el intérprete del sistema y no vería
  # las dependencias — y el diagnóstico que saldría es "el test está mal".
  if [ -x "$BASE/.venv/bin/python" ]; then export PY_PROYECTO="$BASE/.venv/bin/python"; fi


  # LA FOTO DEL WORKTREE SUCIO, antes de que el agente toque nada.
  #
  # El chequeo de alcance compara contra HEAD, así que le cobra a la tarea TODO lo que
  # difiera del commit — incluido lo que el propio runner dejó en el worktree antes de
  # lanzar al agente: `.tests-base`, los enlaces a .venv y .entorno, lo que venga.
  #
  # Cadáver del 2026-10-23: T05c fue rechazada con «tocó archivos que no le corresponden:
  # backend/app/datos/ads.py backend/app/servicios/ads.py». Su transcript tiene DOS Write y
  # los dos son legítimos —su test y su único archivo declarado—; de datos/ads.py no hay ni
  # una mención en todo el log. Esos dos archivos los había commiteado T05b veinticinco
  # minutos antes, en `b06a1cd T05b: gate verde`.
  #
  # O sea: la tarea escribió sólo lo suyo y el método la acusó por el trabajo de su hermana.
  # Es la segunda vez que este mismo gate atribuye a una tarea los cambios de otra: la
  # primera fue el «rompiste tests que andaban antes» del 21 de octubre, que tampoco era
  # causal. Y es el defecto central de esta investigación —un veredicto que nombra al sujeto
  # equivocado— en el chequeo que decide si el trabajo del agente entra al tronco.
  #
  # Restar la foto hace el chequeo correcto por construcción, sin depender de saber QUÉ
  # ensució el worktree: lo que ya estaba antes no lo hizo el agente.
  ( cd "$wt/$PROYECTO" 2>/dev/null || cd "$wt"
    { git diff --name-only --relative HEAD 2>/dev/null; git ls-files --others --exclude-standard; } \
      | sort -u > "$wt/.sucio-antes" ) || : > "$wt/.sucio-antes"
  # `grep -c .` imprime 0 Y SALE CON 1 cuando no hay líneas, así que el `|| echo 0` disparaba
  # TAMBIÉN y la variable quedaba con «0\n0». El `[ -gt ]` reventaba con
  # «[: 0 0: integer expression expected», y justo en el caso más común —el worktree limpio—:
  # el aviso no podía imprimirse nunca y en su lugar salía un error de bash en el log de la
  # corrida. Una medición que no mide y encima ensucia la evidencia que uno lee después.
  # Lo destapó la corrida real de T05c, no la suite: ningún test miraba esta línea.
  heredados="$(grep -c . "$wt/.sucio-antes" 2>/dev/null)"; heredados="${heredados:-0}"
  [ "$heredados" -gt 0 ] 2>/dev/null && echo "  · el worktree ya traía $heredados archivo(s) cambiado(s): no se le cobran a la tarea"

  log="$wt/.tests.log"
  # El reloj que detecta el cuelgue es el de inactividad sobre este log: el agente que
  # trabaja escribe todo el tiempo, el colgado no escribe nada.
  # El valor de INACTIVIDAD lo declara _comun.sh en un solo lugar. Acá decía 45,
  # que era el valor viejo: una tercera copia del mismo número, de las que quedan
  # viejas sin que nadie se entere.
  export LOG_VIGILADO="$log"
  # Antes de gastar un intento: ¿sigue siendo el mismo instrumento? Editar un script con
  # una corrida en vuelo le hace ejecutar basura a bash, y el guardia de borde de etapa se
  # enteraba cuarenta minutos después. Ver `instrumento_se_movio` en _comun.sh.
  # `break 2`: sale del bucle de intentos Y del de tareas. Con un `break` simple pasaría a
  # la tarea siguiente, que es lo contrario de lo que dice el mensaje — y lo que viniera
  # después se juzgaría con el instrumento nuevo, que es el defecto que esto ataja.
  if instrumento_se_movio; then
    echo "     No se lanza este intento. Relanzá la corrida desde cero." >&2
    break 2
  fi
  # La ruta del enunciado va ABSOLUTA Y DENTRO DEL WORKTREE. Las dos otras formas fallan,
  # cada una por su lado:
  #   · absoluta del repo ORIGINAL -> OpenCode la ve como `external_directory` y la rechaza
  #     por permisos (está escrito en correr-tarea.sh y hoy se vio en el log:
  #     «permission requested: external_directory (/Users/jose/*); auto-rejecting»);
  #   · relativa (`tareas/X.md`) -> OpenCode la resuelve contra la RAÍZ DEL WORKTREE y no
  #     contra el `cd` de este bloque, y ahí no hay `tareas/`: el proyecto vive en
  #     `$wt/$PROYECTO`. El 2026-10-21 el intento murió con
  #     «Read /Users/jose/tests-T05a/tareas/T05a-avisos-datos.md failed: File not found»
  #     mientras el archivo estaba en `/Users/jose/tests-T05a/ejemplo-clasificados/tareas/`.
  #
  # Que la absoluta del worktree SÍ se puede leer lo prueba ese mismo log: falló con «File
  # not found» y no con un rechazo de permisos. Y no depender de cómo OpenCode resuelve una
  # ruta relativa es lo correcto además por otra razón: el 2026-10-21 el mismo prompt anduvo
  # en un intento y falló en el siguiente, así que esa resolución no es estable.
  echo "▶ $id · $AGENTE escribe $ruta::$clase"
  (
    cd "$wt/$PROYECTO" || exit 1
    export XDG_DATA_HOME="$wt/.opencode-data"; mkdir -p "$XDG_DATA_HOME"
    con_limite "${LIMITE_AGENTE:-1200}" opencode run --agent "$AGENTE" \
      "${MOTIVO_TESTS:+Un intento anterior falló así: $MOTIVO_TESTS. No repitas ese camino. }Leé $wt/$PROYECTO/tareas/$(basename \"$archivo\"). Ojo: esta corrida es la que CREA los tests, así que todavía no existen, los estás creando vos. Hacé la tarea completa: la implementación Y sus tests, las dos cosas con la herramienta write. El archivo de test es '$ruta' y su agrupador se llama '$clase'. Las reglas de cómo escribir tests están en AGENTS.md: leelas. Al terminar corré 'bash scripts/correr-suite.sh $ruta::$clase' y mostrá su salida real." 2>&1
  ) > "$log" 2>&1
  RC_AGENTE=$?

  cd "$wt/$PROYECTO" || break
  fallos=0
  # 142 = SIGALRM: el agente no respondió en el límite. Es un intento fallido con motivo
  # propio y reintentable, no un test malo: pasó que `opencode run` se quedó 31 minutos con
  # el log en 0 bytes mientras la API del modelo respondía en 3 segundos.
  if [ "${RC_AGENTE:-0}" = "142" ]; then
    malo "el agente no respondió: $(motivo_del_corte "$log")"
  fi
  # Y los errores de PLATAFORMA, con el mismo detector que usa `correr-tarea.sh`. Esta etapa
  # no lo llamaba —`error_del_agente` aparecía 2 veces en su hermana y 0 acá—, así que un
  # `{"message":"memory_session_expired","type":"api_error"}` se informaba como
  # «✗ no escribió backend/tests/X.py declarando TestX»: cierto en la letra y falso en el
  # sujeto. La tarea gastaba un reintento por una falla que no era suya, y el registro
  # anotaba un rojo del modelo.
  #
  # Medido el 2026-10-21 en T05a: el agente venía leyendo archivos con normalidad y la API
  # le cortó la sesión. Es la misma familia que mató T11 y T20 el 2026-10-19 con
  # `memory_delivery_unavailable`, y el detector ya reconoce el sobre `api_error` completo
  # —no una lista de mensajes— justo por eso. Séptima vez en el día que el arreglo vive en
  # un hermano y no en el otro.
  ERROR_PLAT="$(error_del_agente "$log")"
  if [ -n "$ERROR_PLAT" ] && [ "$fallos" = "0" ]; then
    malo "la plataforma cortó el intento: $ERROR_PLAT"
    PLATAFORMA_CORTO=1
  fi
  # Otra vez, porque el agente pudo CREAR el manifiesto: T30 escribe el package.json con
  # vitest, y recién ahora se sabe que hace falta instalarlo.
  bash "$AQUI/preparar-entorno.sh" "$wt/$PROYECTO" >> "$log" 2>&1

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
  # Lo que el agente tocó = lo que difiere ahora MENOS lo que ya difería antes de que corra.
  TOCADOS="$( { git diff --name-only --relative HEAD 2>/dev/null; git ls-files --others --exclude-standard; } \
              | sort -u | comm -23 - "$wt/.sucio-antes" 2>/dev/null \
              || { git diff --name-only --relative HEAD 2>/dev/null; git ls-files --others --exclude-standard; } )"
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

  # Cómo se declara "la clase" depende del lenguaje. Esto exigía `class X` siempre, así que
  # ningún test de vitest podía pasar: en TypeScript el agrupador es `describe('X', ...)`.
  # Es la tercera vez hoy que aparece la misma forma —el método sabe de Python y supone que
  # todo es Python—, así que la condición se declara por extensión y no se adivina.
  case "$ruta" in
    *.py)                                 DECLARA="class $clase" ;;
    *.test.ts|*.test.tsx|*.test.js|*.test.jsx) DECLARA="describe" ;;
    *)                                    DECLARA="$clase" ;;
  esac
  # Los imports, antes de correr nada. Un paquete que el proyecto no declara se tiene que
  # diagnosticar como eso: el agente de T04 usó `passlib` donde el plan cerró `hashlib.scrypt`
  # y el método lo informó como «el test no pasa ni con la implementación del propio agente»,
  # que manda a mirar el test en vez del contrato.
  if [ "$fallos" -eq 0 ] && [ -f "$AQUI/_imports.py" ]; then
    PY_TOCADOS="$(echo "$TOCADOS" | grep -E '\.py$' | tr '\n' ' ')"
    if [ -n "$PY_TOCADOS" ]; then
      SAL_I="$("${PY_PROYECTO:-python3}" "$AQUI/_imports.py" ${PY_TOCADOS} 2>&1)"; RC_I=$?
      if [ "$RC_I" -eq 1 ]; then
        malo "$(echo "$SAL_I" | sed -n 's/^  ✗ //p' | head -1)"
      elif [ "$RC_I" -eq 2 ]; then
        # El 2 de `_imports.py` es «no hay archivos .py que cruzar — no pudo verificarse», y
        # acá se iba en SILENCIO: el cruce no corría y nadie se enteraba. Pasa cuando los
        # archivos que el agente tocó ya no están en disco (renombrados, borrados) o quedaron
        # bajo `.venv`. Lo encontró el test de la costura, aplicando la pregunta 4 del skill
        # `auditar-el-juez` a las piezas que la sesión anterior no había auditado.
        echo "$SAL_I" | sed 's/^/     /'
        echo "     · el cruce de imports no se verificó (ver arriba): no es del test"
      elif [ "$RC_I" -eq 3 ]; then
        # Callado era lo peor de las tres opciones: el cruce no corría y nadie se enteraba.
        # Y `malo` tampoco va: un intérprete viejo no mejora reintentando, así que gastaría
        # los intentos del agente por algo que no es del agente ni del test.
        echo "$SAL_I" | sed 's/^/     /'
        echo "     · el cruce de imports no se verificó (ver arriba): no es del test"
      fi
    fi
  fi

  # La aserción que no puede fallar con NINGUNA implementación. Los cinco pasos de abajo
  # comparan el test contra versiones del producto —sin la implementación, con ella, mutada,
  # vaciada— y por eso ninguno ve el test que no mira el producto en absoluto. Medido el
  # 2026-10-25: T26 tenía aceptado un `assert expected_hash ==
  # hashlib.sha256(password.encode()).hexdigest()` donde la línea de arriba definía
  # `expected_hash` con esa misma expresión. Pasó «falla sin la implementación» porque sus
  # compañeros de archivo importan el módulo y el import es lo que revienta. Es estático y
  # va antes de correr nada: no hace falta gastar tres pasadas de suite para saberlo.
  #
  # Falla CERRADO, y es a propósito. El fixture de la suite aprendió esto a los golpes: una
  # guarda `[ -f auxiliar ]` que saltea el chequeo cuando el auxiliar no está hace que el
  # paso no corra nunca y nadie se entere. Pasó con `_imports.py`, que quedó sin resolver en
  # todo proyecto de juguete de la historia; al hacerlo fallar cerrado se pusieron rojos 22
  # tests de golpe. Un chequeo que no pudo correr no es un chequeo que pasó.
  # El CONTRATO que el test obliga tiene que estar declarado en el enunciado. El chequeo de
  # columnas pregunta si el enunciado pide algo que el esquema no tiene; éste es el mismo
  # cruce en la otra dirección, y hace falta porque el test se acepta PRIMERO y después juzga
  # a toda implementación: lo que invente queda obligado para siempre.
  #
  # Medido el 2026-10-25 sobre los tests ya aceptados de clasificados: T20 obliga seis claves
  # que su enunciado no nombra y que no son columna de ninguna tabla —`other_user_id`,
  # `ultimo_mensaje`, `last_message`…— y T21 obliga `message_id` con un contrato que dice
  # sólo `-> dict`. Dos corridas de implementación de T20 fallaron adivinando ese mapeo.
  # El archivo de tarea es `$archivo`, que este script ya resolvió al empezar la tarea. Mi
  # primera versión usó una variable `ARCHIVO_TAREA` que no existe, y con la guarda `-n` el
  # chequeo no habría corrido NUNCA: falla abierto, que es el defecto que este método viene
  # cerrando todo el día. Si falta el auxiliar es rojo, por el mismo motivo que `_imports.py`.
  if [ "$fallos" -eq 0 ] && [ -f "$ruta" ] && [ -f "$archivo" ]; then
    if [ ! -f "$AQUI/_contrato.py" ]; then
      malo "falta $AQUI/_contrato.py: no se puede cruzar el contrato del test con el enunciado"
    else
    SAL_C="$("${PY_PROYECTO:-python3}" "$AQUI/_contrato.py" "$ruta" "$archivo" . 2>&1)"
    RC_C=$?
    if [ "$RC_C" = "1" ]; then
      malo "el test obliga un contrato que el enunciado no declara"
      printf '%s\n' "$SAL_C" | sed 's/^  /     /'
    elif [ "$RC_C" = "2" ]; then
      echo "  ⊘ no pude cruzar el contrato del test contra el enunciado y el esquema"
      printf '%s\n' "$SAL_C" | sed 's/^  /     /'
    fi
    fi
  fi

  if [ "$fallos" -eq 0 ] && [ -f "$ruta" ]; then
    if [ ! -f "$AQUI/_aserciones.py" ]; then
      malo "falta $AQUI/_aserciones.py: no se puede revisar si las aserciones pueden fallar"
      echo "     Lo provee el método. Un chequeo que no pudo correr no es un chequeo que pasó."
    else
      SAL_A="$("${PY_PROYECTO:-python3}" "$AQUI/_aserciones.py" "$ruta" 2>&1)"; RC_A=$?
      if [ "$RC_A" = "1" ]; then
        malo "el test tiene aserciones que no pueden fallar con ninguna implementación"
        printf '%s\n' "$SAL_A" | sed 's/^  /     /'
      elif [ "$RC_A" != "0" ]; then
        malo "_aserciones.py no pudo correr (rc=$RC_A): el chequeo no se puede saltear"
        printf '%s\n' "$SAL_A" | sed 's/^/     /'
      fi
    fi
  fi

  # ¿El test parchea donde el patch va a pegar? Medido el 2026-10-27 con modelos de verdad:
  # los siete tests de una etapa parchearon el módulo donde el nombre se DEFINE, y el
  # enunciado pedía traerlo con `from`, que es justo lo que vuelve el patch inefectivo. Tres
  # de siete quedaron en punto muerto acusando al implementador, con la implementación
  # palabra por palabra igual al contrato; las otras cuatro pasaron DESOBEDECIENDO el
  # contrato. El veredicto quedó correlacionado al revés de lo correcto. Detalle y los tres
  # casos en que el patch sí pega: scripts/_mocks.py.
  case "$ruta" in *.py) MIRA_MOCKS=1 ;; *) MIRA_MOCKS=0 ;; esac
  if [ "$fallos" -eq 0 ] && [ "$MIRA_MOCKS" = "1" ] && [ -f "$ruta" ]; then
    if [ ! -f "$AQUI/_mocks.py" ]; then
      malo "falta $AQUI/_mocks.py: no se puede revisar si los patch del test tienen efecto"
      echo "     Lo provee el método. Un chequeo que no pudo correr no es un chequeo que pasó."
    else
      # `--segun-enunciado`: la implementación que hay en el worktree AHORA es el borrador
      # del mismo agente que escribió el test —el método la descarta—, así que mirarla es
      # preguntarle al acusado. Está medido: así se colaba el test defectuoso. El único
      # compromiso sobre la implementación futura es el contrato.
      SAL_K="$("${PY_PROYECTO:-python3}" "$AQUI/_mocks.py" --segun-enunciado \
               "$ruta" "$archivo" . 2>&1)"; RC_K=$?
      if [ "$RC_K" = "1" ]; then
        malo "el test parchea un lugar donde el patch no va a tener efecto"
        printf '%s\n' "$SAL_K" | sed 's/^  /     /'
      elif [ "$RC_K" = "2" ]; then
        echo "  ⊘ no pude determinar si los patch del test tienen efecto"
        printf '%s\n' "$SAL_K" | sed 's/^  /     /'
        echo "     Si el enunciado no declara con qué import la implementación trae el nombre,"
        echo "     el test está apostando a una de tres formas. Eso lo decide quien planifica."
      elif [ "$RC_K" != "0" ]; then
        malo "_mocks.py no pudo correr (rc=$RC_K): el chequeo no se puede saltear"
        printf '%s\n' "$SAL_K" | sed 's/^/     /'
      else
        # El testigo también en verde, y no es cosmética: este chequeo dio verde durante una
        # corrida entera mirando la implementación equivocada, y lo que lo hacía invisible
        # era justamente no decir qué había mirado.
        echo "  ✓ los patch del test apuntan donde el patch pega"
        printf '%s\n' "$SAL_K" | sed 's/^  /     · /'
      fi
    fi
  fi

  if [ "$fallos" -eq 0 ] && { [ ! -f "$ruta" ] \
       || ! grep -q "$DECLARA" "$ruta" 2>/dev/null \
       || ! grep -q "$clase" "$ruta" 2>/dev/null; }; then
    malo "no escribió $ruta declarando $clase"
    echo "     En .py se espera «class ${clase}»; en .test.ts, un describe con ese nombre."
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
      # Cada pasada arranca con la base vacía. Sin esto, la segunda choca con lo que
      # insertó la primera y el veredicto se lo cobra al test: ver `limpiar_base_del_arbol`.
      limpiar_base_del_arbol "$wt"
      if eval "$prueba" >/dev/null 2>&1; then
        malo "el test PASA con el código de antes: no prueba nada"
      else
        echo "  ✓ falla sin la implementación"
      fi
      for f in $impl; do cp "$tmp/$(echo "$f" | tr / _)" "$f"; done
      rm -rf "$tmp"
      # Si esto limpió, la base arrancó VACÍA esta pasada, y entonces un choque de UNIQUE no
      # lo puede haber puesto otra corrida: lo puso el propio test. Es el dato que convierte
      # el ⊘ de abajo en un veredicto medido en vez de una atribución.
      limpiar_base_del_arbol "$wt" && BASE_VACIA_AL_EMPEZAR=1 || BASE_VACIA_AL_EMPEZAR=0
      if eval "$prueba" >/dev/null 2>&1; then
        echo "  ✓ pasa con la implementación"
        git add -A >/dev/null 2>&1
        git commit -q -m "impl+tests $id (worktree desechable)" >/dev/null 2>&1
        if [ "$MUTABLE" != "1" ]; then
          echo "  ⊘ no hay mutador para «${ruta}»: el test pasa los dos primeros pasos y el"
          echo "     tercero (¿distingue?) no pudo verificarse. No es un pase."
        else
        # El CODIGO sale de lo que ESTA tarea declara, no de un default. Valía `src` y nadie
        # lo seteaba nunca: en un proyecto cuyo código vive en `backend/app` y `frontend/src`
        # el filtro de mutar.py no matcheaba un solo archivo, devolvía 0, y esto imprimía
        # «✓ los mutantes mueren» con la salida silenciada. Todo clasificados, siempre.
        CODIGO_TAREA="$(for f in $impl; do dirname "$f"; done | sort -u | paste -sd, -)"
        # UNA sola corrida de mutar.py, y su salida se usa para todo. Antes corría DOS veces
        # —una muda para el veredicto y otra para capturar el detalle— y la segunda quedó con
        # el `CODIGO` viejo cuando arreglé la primera: el detalle salía VACÍO. El reintento
        # recibía «sobreviven mutantes» sin un solo dato, dos veces, y T05a llegó a punto
        # muerto por eso. Dos invocaciones del mismo comando son dos cosas que pueden
        # divergir, y divergieron en el mismo bloque y en el mismo arreglo.
        #
        # Y mutar.py muta archivos del árbol y los restaura: correrlo una vez también es más
        # seguro que correrlo dos.
        SALIDA_MUT="$(BASE=HEAD~1 CODIGO="${CODIGO_TAREA:-$CODIGO}" SUITE="$prueba" \
                      python3 "$AQUI/mutar.py" 2>&1)"
        RC_MUT=$?
        if [ "$RC_MUT" = "0" ]; then
          echo "  ✓ los mutantes mueren: el test distingue"
        elif [ "$RC_MUT" = "2" ]; then
          echo "  ⊘ no hubo nada que mutar bajo «${CODIGO_TAREA:-$CODIGO}»: el test pasa los dos"
          echo "     primeros pasos y el tercero (¿distingue?) no pudo verificarse. No es un pase."
          printf '%s\n' "$SALIDA_MUT" | sed 's/^/     /'
        else
          # El detalle sale de la MISMA corrida, así que no puede desaparecer ni contradecirla.
          SOBREVIVEN="$(printf '%s\n' "$SALIDA_MUT" | grep '→' | head -3 | tr '\n' ' ' | cut -c1-400)"
          # El veredicto no es uno, son dos opuestos, y acá se afirmaba siempre el primero:
          # «cubre las líneas y no verifica su comportamiento» manda a mejorar aserciones.
          # Cuando el test NO EJECUTA la línea —un mock del propio archivo de la tarea— ese
          # consejo apunta al lado contrario, y el agente no tiene cómo darse cuenta. Medido
          # el 2026-10-25: T26 de clasificados mockeaba `users_register.insert_user`, que es
          # la función que la tarea pide escribir, y quedó trabada dos corridas recibiendo
          # «cubre las líneas» sobre tres líneas que nunca corrieron. `mutar.py` lo distingue
          # con un centinela y lo dice con el código 3.
          if [ "$RC_MUT" = "3" ]; then
            malo "el test NO EJECUTA las líneas de la implementación: no las está probando.${SOBREVIVEN:+ Sobrevivió: $SOBREVIVEN}"
            echo "     Si mockeás un símbolo que vive en un archivo de ESTA tarea, estás"
            echo "     reemplazando lo que viniste a probar. Mockeá lo de ABAJO, no la tarea."
          else
            malo "sobreviven mutantes: el test cubre las líneas y no verifica su comportamiento.${SOBREVIVEN:+ Sobrevivió: $SOBREVIVEN}"
          fi
          # La salida COMPLETA al log, igual que en la rama del ⊘ doce líneas más arriba.
          # Acá no se imprimía, así que cuando la extracción fallaba la evidencia no quedaba
          # en ninguna parte: ni el agente ni la persona podían saber qué mutante sobrevivió,
          # y el aviso mandaba a mirar un log donde no estaba. Un chequeo que descarta su
          # propia evidencia no se puede auditar.
          printf '%s\n' "$SALIDA_MUT" | sed 's/^/     /'
          [ -n "$SOBREVIVEN" ] || echo "     ⚠ mutar.py no listó sobrevivientes con «→»: revisá que el formato de mutar.py y este extractor sigan acordando"
        fi
        fi
        # 4. El BRAZO NULO: con los cuerpos vaciados, el test tiene que FALLAR.
        #
        # Los tres pasos de arriba preguntan «¿este test distingue ESTE cambio?». Falta el
        # anterior: **¿distingue algo de nada?** El test aceptado de T04b tenía cinco pruebas
        # y las cinco negativas —token inválido, vacío, nulo, mal formado, id inexistente— y
        # ninguna verificaba que un token válido devolviera el id, que era el criterio de la
        # tarea. Pasó los tres pasos, y `def usuario_desde_token(token): return None` pasaba
        # los cinco. El método se enteraba sólo si alguien lo leía.
        #
        # `experimentos/README.md` ya exige un brazo nulo para los experimentos por este
        # mismo motivo. Es el mismo control, en el lugar donde más barato sale.
        #
        # ARCHIVO POR ARCHIVO, y es el arreglo. Vaciaba los archivos de la tarea TODOS
        # JUNTOS y una sola pasada decidía, así que bastaba que UNO fuera necesario para dar
        # verde y los demás no se preguntaban nunca. Medido el 2026-10-25 en T04 de
        # clasificados, cerrada como ✅ hecha: declara tres archivos, el test mockea
        # `datos/users.py`, y ese archivo es un stub que lo dice en su propio comentario
        # —«Por ahora retornamos None como placeholder»—. Vaciar los tres rompía el test por
        # los otros dos; vaciar sólo `users.py` no cambia nada. Con ese stub el login no
        # puede funcionar para ningún usuario, y la tarea está cerrada.
        #
        # Las tres tareas de clasificados con más de un archivo .py son T04, T26 y T28, y
        # son las tres que fallaron. No es casualidad: es el molde ruta+servicio+datos, donde
        # el test mockea la capa de datos y el brazo nulo conjunto no lo nota.
        if [ "$fallos" = "0" ]; then
          PREGUNTADOS=0
          for f in $impl; do
            case "$f" in *.py) ;; *) continue ;; esac
            SAL_V="$(python3 "$AQUI/vaciar.py" "$f" 2>&1)"; RC_V=$?
            if [ "$RC_V" = "3" ]; then
              # `vaciar.py` reconoció un stub. Siempre supo reconocerlo —su comentario decía
              # «ya era un stub: no cuenta»— y la conclusión que sacaba era descartarlo.
              malo "un archivo de la implementación YA es un stub: no hay nada que probar"
              printf '%s\n' "$SAL_V" | sed 's/^  /     /'
              echo "     Una función que devuelve None sin hacer nada no es una implementación."
              python3 "$AQUI/vaciar.py" --restaurar >/dev/null 2>&1
              break
            elif [ "$RC_V" != "0" ]; then
              echo "  ⊘ $f: no había funciones que vaciar, así que no se le puede preguntar"
              continue
            fi
            # Cada pasada arranca con la base vacía, igual que las tres de arriba.
            limpiar_base_del_arbol "$wt"
            PREGUNTADOS=$((PREGUNTADOS + 1))
            if eval "$prueba" >/dev/null 2>&1; then
              malo "el test pasa con los cuerpos de $f VACÍOS: no prueba ese archivo"
              echo "     Un stub que devuelve None lo satisface. Dos causas posibles: falta el"
              echo "     caso positivo —un test de puros negativos no cubre un criterio que"
              echo "     afirma algo—, o estás mockeando lo que $f define, que es la tarea."
              python3 "$AQUI/vaciar.py" --restaurar >/dev/null 2>&1
              break
            fi
            python3 "$AQUI/vaciar.py" --restaurar >/dev/null 2>&1
          done
          if [ "$fallos" = "0" ]; then
            if [ "$PREGUNTADOS" -gt 0 ]; then
              echo "  ✓ el brazo nulo falla en los $PREGUNTADOS archivo(s): el test distingue algo de nada"
            else
              echo "  ⊘ no pude armar el brazo nulo: no había funciones que vaciar"
            fi
          fi
        fi
      else
        # El motivo lleva el fallo real, no su categoría: el nombre del test que falla y el
        # mensaje del assert. Sin eso el reintento no tiene nada nuevo con lo que trabajar,
        # y se vio: T02 falló dos veces por lo mismo recibiendo sólo "el test está mal".
        # Los dos formatos: pytest escribe `E  AssertionError` y `FAILED ruta::test`;
        # vitest escribe ` FAIL  tests/x.test.ts > TestX > caso` y el error sin prefijo.
        # Con el patrón de uno solo, el motivo salía vacío en todo el frontend.
        DETALLE="$(eval "$prueba" 2>&1 \
                   | grep -E '^E +|^(FAILED|FAIL:) |^ *(FAIL|×) |(Assertion|Type|Reference|Syntax)Error|Cannot find|^Error: ' \
                   | head -4 | tr '\n' ' ' | tr -s ' ' | cut -c1-400)"
        # ESTADO QUE QUEDÓ, no un test malo. Y el método se lo cobraba al test.
        #
        # Medido el 2026-10-24 en T26: el validador corre el MISMO test DOS VECES —una sin la
        # implementación, para comprobar que falla, y otra con ella— contra una base con
        # estado. La primera pasada insertó `test@example.com`, la segunda chocó con el UNIQUE
        # de `usuarios.email`, y el veredicto que salió fue «el test no pasa ni con la
        # implementación del propio agente»: le cobró al test lo que dejó su propia primera
        # pasada. Dos intentos del ejecutor gastados en eso.
        #
        # El gate ya tiene este concepto escrito para su lado —ENTORNO_MOVIDO: «todos los
        # worktrees comparten el MySQL de 127.0.0.1:33306, lo que una etapa deja la siguiente
        # lo encuentra; es del entorno y no del código, así que no se le cobra a la tarea»—
        # pero su lista de firmas reconoce «Table doesn't exist», «Access denied» y
        # «Can't connect», no un choque de UNIQUE. Acá faltaba entero.
        #
        # No se reintenta: la segunda pasada va a encontrar la misma fila. Y no se ablanda
        # nada —el test no se acepta igual—; lo único que cambia es A QUIÉN se le cobra, que es
        # lo que estuvo mal en la mayoría de los defectos de estos días.
        if printf '%s' "$DETALLE" | grep -qiE "IntegrityError|Duplicate entry|\b1062,|UNIQUE constraint failed"; then
          # A QUIÉN se le cobra se MIDE, no se atribuye. Si la limpieza de esta pasada
          # funcionó, la base arrancó vacía y las filas que chocan las insertó este test en
          # esta corrida: es del test. Si no se pudo limpiar, el estado puede venir de
          # cualquier parte y no se le cobra a la tarea.
          #
          # El mensaje viejo afirmaba «lo causa el MÉTODO» siempre, y recomendaba «limpiar la
          # base entre pasadas o aislarla por corrida». El 2026-10-25 las dos cosas ya
          # estaban hechas y medidas, y la afirmación fue falsa tres corridas seguidas: me
          # mandó a lo ya arreglado mientras el defecto real era que la base no se tiraba al
          # rehacer el worktree. Un veredicto que nombra la causa equivocada cuesta más que
          # uno que dice «no sé».
          if [ "${BASE_VACIA_AL_EMPEZAR:-0}" = "1" ]; then
            # `IntegrityError` es una FAMILIA, no un error. Con la base vacía, un duplicado
            # (1062) y una clave foránea fallida (1452) piden arreglos casi opuestos, y mi
            # primera versión afirmaba «inserta la misma fila dos veces» para los dos.
            #
            # Medido el 2026-10-25 en T16: su test inserta favoritos para un usuario que no
            # existe —la limpieza dejó la base vacía— y recibió «inserta la misma fila dos
            # veces», que no describe nada de lo que pasó. Un veredicto que nombra la causa
            # equivocada cuesta más que uno que dice «no sé»: es la tercera vez hoy.
            if printf '%s' "$DETALLE" | grep -qiE "\b1452,|foreign key|FOREIGN KEY"; then
              malo "el test referencia filas que no existen: la base arranca VACÍA cada pasada."
              echo "     $DETALLE"
              echo "     No es estado de otra corrida: la limpieza corrió y funcionó. El test"
              echo "     da por sentados datos semilla —un usuario, un anuncio— que nadie creó."
              echo "     Tiene que crear lo que referencia, en su propio setUp."
            elif printf '%s' "$DETALLE" | grep -qiE "\b1048,|cannot be null|NOT NULL"; then
              malo "el test deja sin valor una columna que no admite nulos."
              echo "     $DETALLE"
              echo "     La migración la declara NOT NULL sin default: hay que darle un valor"
              echo "     o el enunciado está pidiendo una fila que el esquema no acepta."
            else
              malo "el test choca con datos que insertó ÉL MISMO: la base arrancó vacía esta pasada."
              echo "     $DETALLE"
              echo "     La limpieza corrió y funcionó, así que no hay estado de otra corrida."
              echo "     El test inserta la misma fila dos veces —o la inserta y no la limpia"
              echo "     entre sus propios casos—. Eso lo arregla el test, no el entorno."
            fi
          else
            echo "  ⊘ $id: el test choca con datos que YA estaban en la base, no con su lógica."
            echo "     $DETALLE"
            echo "     Y no pude limpiar la base antes de esta pasada, así que ese estado"
            echo "     puede venir de cualquier corrida: no se le cobra a la tarea. Revisá"
            echo "     que el worktree tenga su propia base y que se tire al rehacerlo —su"
            echo "     nombre vive en su .entorno, así que hay que tirarla ANTES de borrar el"
            echo "     directorio—. No se reintenta: la próxima pasada va a encontrar la"
            echo "     misma fila. Log: $log"
            cd "$RAIZ" || true
            conservar_intento "$wt" "${id:-${TAREA:-tests}}"
            break
          fi
        fi
        malo "el test no pasa ni con la implementación del propio agente.${DETALLE:+ Falla así: $DETALLE}"
      fi
    fi
  fi

  # ── 5. El test contra el ESQUEMA, antes de aceptarlo.
  #
  # Un test completamente mockeado puede clavar una consulta imposible y pasar los cuatro
  # chequeos anteriores. Medido el 2026-10-24: el test que el gate ACEPTÓ para T28 fijaba
  #
  #   mock_cursor.execute.assert_called_once_with(
  #     "SELECT id, usuario_id, titulo, categoria, precio FROM anuncios WHERE 1=1 ...")
  #
  # y ni `categoria` ni `precio` existen —son `categoria_id` y `precio_centavos`—. Pasó porque
  # la base nunca se toca: el mock acepta cualquier cadena. Y los mutantes MUEREN, porque
  # `assert_called_once_with` fija la cadena exacta: el chequeo de mutación lo satisface un
  # test que clava una consulta equivocada.
  #
  # Eso no es un test que deja pasar el bug: es un test que lo OBLIGA. La implementación que
  # lo haga pasar va a escribir esa consulta, y MySQL la va a rechazar en la primera corrida
  # real — con el veredicto apuntando a la tarea que la escribió.
  #
  # El chequeo existía y corría DESPUÉS: el preflight de la corrida siguiente lo marcaba, con
  # el test ya copiado al tronco. La información estaba en el momento equivocado, que es la
  # forma que este repo persigue desde el primer día. El juez es el mismo `coherencia.py` que
  # lo encontró; acá se le pregunta por el archivo que está a punto de entrar.
  if [ "$fallos" -eq 0 ] && [ -f "$AQUI/coherencia.py" ]; then
    # Cualquier renglón de esquema que NOMBRE este test, no sólo los `✗`. El 2026-10-25
    # este chequeo no disparó y el test entró al tronco igual: el rojo de la columna se
    # agrupaba por (tabla, columna) y se atribuía al primer archivo, así que con la
    # implementación nombrando la misma columna el veredicto salió como `⚠` —el dueño de ESE
    # archivo estaba pendiente— y el test quedó dentro de «y 1 más». Eso se arregló en
    # `coherencia.py`, que ahora informa por archivo; esto deja de depender del símbolo.
    #
    # Un test que clava una consulta imposible no se acepta ni si alguien «se hace cargo» del
    # archivo: el test obliga la consulta, y la obliga para siempre.
    ESQ="$( (cd "$wt/$PROYECTO" && PROYECTO=. python3 "$AQUI/coherencia.py" 2>&1 \
             | grep -E '✗|⚠ esquema' | grep -F "$ruta") || true)"
    if [ -n "$ESQ" ]; then
      malo "el test clava una consulta que el esquema no acepta: $(printf '%s' "$ESQ" | head -2 | tr '\n' ' ' | cut -c1-320)"
    fi
  fi

  if [ "$fallos" -eq 0 ]; then
    # Al tronco llega SÓLO el test. La referencia se queda en el worktree, que se tira.
    mkdir -p "$(dirname "$BASE/$ruta")"
    cp "$ruta" "$BASE/$ruta"
    echo "  ✓ $id: $ruta aceptado y copiado al tronco (la implementación se descarta)"
    cd "$RAIZ" || true
    # El worktree de validación ya no hace falta: el test está en el tronco y la
    # implementación de referencia se descarta a propósito. Se queda sólo cuando FALLA, que
    # es cuando alguien va a querer mirarlo.
    #
    # Dejarlos todos acumulados no es gratis: una corrida de un día dejó doce worktrees
    # registrados y doce ramas, y cada herramienta que recorre el repo los recorre.
    # `exito`: el transcript del test que SÍ pasó los cinco pasos es la mitad positiva del
    # dataset, y acá además viene con la implementación de referencia que el método descarta
    # —el único registro que queda de contra qué se validó el test—. Sin el prefijo cae en
    # `fallidos-<id>` indistinguible de una falla. Séptima vez que el arreglo vivía en el
    # hermano: `correr-tarea.sh` lo pasa desde hoy y acá seguía por omisión.
    conservar_intento "$wt" "${id:-${TAREA:-tests}}" exito
    tirar_base_del_worktree "$wt"
    git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null
    git -C "$RAIZ" branch -D "tests/$id" >/dev/null 2>&1
    break
  fi

  [ -n "$MOTIVO_TESTS" ] || MOTIVO_TESTS="la validación del test no pasó"
  cd "$RAIZ" || true

  # Misma regla de corte que correr-plan.sh: reintentar a ciegas gasta tiempo en la falla
  # que no se va a ir sola. Si el motivo repite, es la misma falla.
  #
  # Con una excepción: **un corte por tiempo no es una falla que repite.** El cuelgue de
  # opencode es intermitente —inicializa y no llega a pedirle nada al modelo— y el mismo
  # prompt anduvo seis veces de seis en reproducciones aisladas. Tratarlo como punto muerto
  # convierte un problema transitorio de la herramienta en una parada del método.
  # Un corte de PLATAFORMA tampoco es una falla que repite, y no es de la tarea. Va con el
  # presupuesto generoso de los cortes de herramienta —no con el de «límite total», que es
  # el único que habla de la tarea— y la huella se limpia para que el reintento no reciba
  # «un intento anterior falló así» con un motivo que el enunciado no puede arreglar.
  if [ "${PLATAFORMA_CORTO:-0}" = "1" ]; then
    PLATAFORMA_CORTO=0
    HUELLA_ANTERIOR=""; MOTIVO_TESTS=""
    cortes=$((cortes+1))
    if [ "$cortes" -gt "$CORTES_MAX" ]; then
      echo "  ✗ $id: $cortes cortes seguidos y el último fue de plataforma."
      echo "     No es la tarea ni el modelo. Cuando la plataforma se estabilice, retomá:"
      echo "     no hay nada que arreglar en el plan. Log: $log"
      break
    fi
    echo "     (corte de plataforma $cortes de $CORTES_MAX; no cuenta contra la tarea)"
    continue
  fi
  if [ "${RC_AGENTE:-0}" = "142" ]; then
    HUELLA_ANTERIOR=""
    # ¿Trabajó y no terminó, o nunca arrancó? Son dos fallas distintas con dos presupuestos.
    case "$MOTIVO_TESTS" in
      *"límite total"*)
        cortes_total=$((cortes_total+1))
        if [ "$cortes_total" -gt "$CORTES_TOTAL_MAX" ]; then
          echo "  ✗ $id: $cortes_total cortes por LÍMITE TOTAL (${LIMITE_AGENTE:-1200}s cada uno)."
          echo "     El agente trabajó todo el tiempo y no terminó, las $cortes_total veces."
          echo "     Eso no es la herramienta colgándose: es la TAREA. Mirá el transcript y"
          echo "     preguntate si el enunciado le pide algo sin darle el medio, o si hay que"
          echo "     partirla. Log: $log"
          break
        fi
        echo "     (corte por límite total $cortes_total de $CORTES_TOTAL_MAX; el agente trabajó y no terminó)"
        continue ;;
    esac
    cortes=$((cortes+1))
    if [ "$cortes" -gt "$CORTES_MAX" ]; then
      # Antes de culpar a la herramienta, preguntarle a la red. Hoy perdimos horas: la
      # conexión se cortaba de a ratos y el método informaba «es la herramienta» —y yo
      # detrás, buscando la causa en opencode, en la plataforma, en la cuantización del
      # modelo y en el tamaño del prompt—. Una tanda de cuelgues y una conexión caída se
      # ven exactamente igual desde acá, así que hay que mirar.
      if ! plataforma_responde 2>/dev/null; then
        echo "  ✗ $id: $cortes cortes seguidos Y la plataforma no responde ahora mismo."
        echo "     Esto es conexión o plataforma, no la tarea ni la herramienta. Cuando"
        echo "     vuelva, retomá: no hay nada que arreglar en el plan."
      else
        echo "  ✗ $id: $cortes cortes por cuelgue seguidos, con la plataforma respondiendo."
        echo "     Eso sí apunta a la herramienta. Log: $log"
      fi
      break
    fi
    echo "     (corte por inactividad $cortes de $CORTES_MAX; la herramienta no llegó a pedir nada)"
    continue
  elif [ "$MOTIVO_TESTS" = "$HUELLA_ANTERIOR" ]; then
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
# Sólo si hay algo que commitear. Se imprimía SIEMPRE, incluso cuando las dos tareas se
# saltearon por «ya declara la clase — no se toca»: lo leí hoy con el tronco limpio y me hizo
# dudar del estado del repo justo cuando estaba diagnosticando por qué la integración no
# cerraba. Y lo que sugería era `git add -A`, que barre cualquier cosa ajena —el trabajo a
# medio hacer del humano— a un commit llamado «tests de …».
SUCIO="$(git -C "$RAIZ" status --porcelain 2>/dev/null | grep . || true)"
if [ -n "$SUCIO" ]; then
  echo "Los tests aceptados están en el tronco sin commitear. Revisalos y commiteá:"
  printf '%s\n' "$SUCIO" | sed 's/^/    /'
  echo "  git -C $RAIZ add -- <los de arriba> && git -C $RAIZ commit -m 'tests de <tareas>'"
fi
echo "Los worktrees de los tests ACEPTADOS ya se tiraron. Quedan los que fallaron,"
echo "que es donde hay algo que mirar: git worktree list"
