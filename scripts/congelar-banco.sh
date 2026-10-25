#!/usr/bin/env bash
# Congela el banco de ítems de evaluación como ARTEFACTO, en vez de reconstruirlo desde la
# historia cada vez.
#
#   bash scripts/congelar-banco.sh                 # todos los candidatos del proyecto
#   bash scripts/congelar-banco.sh T40 T41         # sólo esos
#   PROYECTO=ejemplo-pacman bash scripts/congelar-banco.sh
#
# Por qué existe: el banco se armaba revirtiendo el commit verde de cada tarea cerrada, y eso
# se podre. Medido: de 21 candidatos, 7 tenían un parche inverso que ya NO APLICA porque una
# tarea posterior tocó las mismas líneas, 3 daban `rc=2` (que por contrato no es rojo) y 2
# daban rojo por el motivo equivocado (un ImportError que se lleva 21 tests ajenos). Y una
# tarea tenía CUATRO commits «gate verde»: revertir uno deja la implementación de los otros.
#
# Un ítem congelado es una rama `item/<proyecto>-<TNN>` con dos commits:
#   base     — el estado ROJO verificado: los tests de la tarea existen y FALLAN
#   testigo  — la implementación que los pone en verde
# y un `.precondicion` con los dos SHAs, el selector y la salida literal de la corrida sobre
# `base`. Congelado así, la precondición no depende de que el tronco no se mueva.
#
# La precondición se VERIFICA CORRIENDO los tests, no deduciéndola de que el parche aplicó.
# Declaramos un ítem inadmisible mirando su `diff --stat` —tres archivos vacíos, 0 inserciones—
# y al correrlo resultó viable: git no versiona directorios vacíos y el test verificaba que el
# directorio existiera. Ver MEDICION.md §1, pregunta 4.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto   # RAIZ, PROYECTO, BASE

SOLO=("$@")
WT_BASE="$RAIZ/../banco-wt"
RAMA_ACTUAL="$(git -C "$RAIZ" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"

# Los commits «gate verde» de una tarea, ACOTADOS a este proyecto: `--grep` solo mezcla los
# dos ejemplos, que tienen tareas con el mismo número.
commits_verdes() {
  local id="$1" s
  for s in $(git -C "$RAIZ" log --all --format='%h' --grep="^${id}: gate verde" 2>/dev/null); do
    git -C "$RAIZ" show --name-only --format= "$s" | grep -q "^$PROYECTO/" && echo "$s"
  done
}

# Qué declara la tarea: «ruta clase». Mismo lector que el gate.
declaracion() {
  sed -n 's/.*`\([^`]*\)`, *clase `\([A-Za-z0-9_]*\)`.*/\1 \2/p' \
    "$BASE/tareas/${1}"-*.md 2>/dev/null | head -1
}

# Los archivos de IMPLEMENTACIÓN que toca un commit: ni tests ni scripts.
impl_del_commit() {
  git -C "$RAIZ" show --name-only --format= "$1" \
    | grep "^$PROYECTO/" \
    | grep -vE "^$PROYECTO/(tests/|scripts/|.*/tests/)" \
    | grep -vE '\.md$' || true
}

printf '%-7s %-9s %-46s %s\n' TAREA ESTADO SELECTOR MOTIVO
printf '%.0s─' {1..110}; echo

VIABLES=0; CAIDOS=0
for f in "$BASE"/tareas/*.md; do
  id="$(basename "$f" | sed 's/-.*//')"
  if [ "${#SOLO[@]}" -gt 0 ]; then
    printf '%s\n' "${SOLO[@]}" | grep -qxF "$id" || continue
  fi

  SHAS="$(commits_verdes "$id")"
  [ -n "$SHAS" ] || continue
  N_SHAS="$(printf '%s\n' "$SHAS" | grep -c .)"
  TESTIGO_SHA="$(printf '%s\n' "$SHAS" | head -1)"   # el más nuevo: git log va de nuevo a viejo

  DECL="$(declaracion "$id")"
  if [ -z "$DECL" ]; then
    printf '%-7s %-9s %-46s %s\n' "$id" "⊘" "—" "la tarea no declara archivo y clase de test"
    CAIDOS=$((CAIDOS+1)); continue
  fi
  RUTA="$(echo "$DECL" | cut -d' ' -f1)"; CLASE="$(echo "$DECL" | cut -d' ' -f2)"
  SEL="$RUTA::$CLASE"

  IMPL="$(impl_del_commit "$TESTIGO_SHA")"
  if [ -z "$IMPL" ]; then
    printf '%-7s %-9s %-46s %s\n' "$id" "⊘" "$SEL" "el commit verde no toca implementación"
    CAIDOS=$((CAIDOS+1)); continue
  fi

  RAMA="item/$PROYECTO-$id"
  WT="$WT_BASE-$id"
  # conservar_intento: no-aplica — es un worktree de CONSTRUCCIÓN del banco, no la
  # corrida de un agente: no hay intento que conservar. Lo que vale queda en la rama
  # item/… y en su .precondicion, que se commitean antes de esto.
  tirar_base_del_worktree "$WT"; rm -rf "$WT"
  git -C "$RAIZ" worktree remove --force "$WT" 2>/dev/null
  git -C "$RAIZ" branch -D "$RAMA" 2>/dev/null
  git -C "$RAIZ" worktree add -q -b "$RAMA" "$WT" "$TESTIGO_SHA" 2>/dev/null || {
    printf '%-7s %-9s %-46s %s\n' "$id" "⊘" "$SEL" "no pude crear el worktree en $TESTIGO_SHA"
    CAIDOS=$((CAIDOS+1)); continue
  }

  # El ítem congela el SUJETO (tests + implementación), no el INSTRUMENTO (los scripts).
  # El commit testigo de varias tareas es anterior a `scripts/correr-suite.sh`, así que el
  # selector salía con código 127 —falta el corredor— y el ítem caía por un defecto del
  # instrumento viejo. Y congelar el instrumento de entonces dentro del ítem garantizaría el
  # punto 7 de la regla de parada: «cambiaste el instrumento entre dos corridas, no son
  # comparables». Los scripts son INTOCABLES para el agente, así que traer los de hoy es lo
  # correcto y es lo que hace el gate.
  # Del ÁRBOL DE TRABAJO, no del commit: `git checkout <rama> -- ruta` trae la versión
  # commiteada, y un arreglo del corredor sin commitear no llegaba al ítem. Congelé el banco
  # con el corredor viejo y nueve ítems cayeron por un defecto que ya estaba arreglado en
  # disco. Es «medí el artefacto que corre, no el árbol», al revés: acá el artefacto que corre
  # es el del árbol de trabajo. El recibo anota cuál se usó.
  rm -rf "$WT/$PROYECTO/scripts"
  cp -R "$BASE/scripts" "$WT/$PROYECTO/scripts"

  # Y el ARCHIVO DE TEST declarado, también de hoy, por la misma razón: los tests de una tarea
  # son INTOCABLES para el agente que implementa (los escribe otra corrida), así que son
  # instrumento, no sujeto. Un ítem cosechado de la historia hereda los defectos que el tronco
  # ya arregló: el test de una tarea tenía clavada la ruta absoluta del worktree donde se
  # escribió —`/Users/jose/tests-T03/...`, que no existe más—, el tronco lo arregló con una
  # constante relativa, y el ítem seguía trayendo la versión vieja. Falla en todos lados menos
  # en un directorio que ya no existe.
  #
  # Traerlo de hoy es seguro porque el congelado VERIFICA el testigo: si los tests de hoy no
  # pasan contra la implementación histórica, el ítem cae con «testigo: los tests NO pasan».
  if [ -f "$BASE/$RUTA" ]; then
    mkdir -p "$(dirname "$WT/$PROYECTO/$RUTA")"
    cp "$BASE/$RUTA" "$WT/$PROYECTO/$RUTA"
  fi

  # base: la implementación vuelve al estado del padre del testigo. Los tests quedan.
  FALLO=""
  for a in $IMPL; do
    if git -C "$WT" cat-file -e "$TESTIGO_SHA^:$a" 2>/dev/null; then
      git -C "$WT" checkout "$TESTIGO_SHA^" -- "$a" 2>/dev/null || FALLO="no pude revertir $a"
    else
      # No existía en el padre: es nuevo, se borra. Y hay que PODAR los directorios que queden
      # vacíos, porque git no versiona directorios vacíos: en el padre esos directorios no
      # existían, así que dejarlos vacíos construye un estado base que nunca existió.
      #
      # Importa de verdad: la «implementación» de una tarea eran tres `__init__.py` vacíos, y
      # su test verifica que los DIRECTORIOS existan. Con `rm -f` solo, el directorio quedaba y
      # el test pasaba sin implementación → el ítem se descartaba como «no distingue». Con la
      # poda, falla, y el ítem es viable. Dos formas de revertir dieron dos veredictos
      # opuestos sobre el mismo ítem, y la que vale es la que reproduce el árbol del padre.
      git -C "$WT" rm -q --cached "$a" 2>/dev/null; rm -f "$WT/$a"
      d="$(dirname "$a")"
      while [ "$d" != "." ] && [ "$d" != "/" ]; do
        git -C "$WT" cat-file -e "$TESTIGO_SHA^:$d" 2>/dev/null && break
        rmdir "$WT/$d" 2>/dev/null || break
        d="$(dirname "$d")"
      done
    fi
  done
  if [ -n "$FALLO" ]; then
    printf '%-7s %-9s %-46s %s\n' "$id" "⊘" "$SEL" "$FALLO"
    # conservar_intento: no-aplica — es un worktree de CONSTRUCCIÓN del banco, no la
    # corrida de un agente: no hay intento que conservar. Lo que vale queda en la rama
    # item/… y en su .precondicion, que se commitean antes de esto.
    tirar_base_del_worktree "$WT"
    git -C "$RAIZ" worktree remove --force "$WT" 2>/dev/null; git -C "$RAIZ" branch -D "$RAMA" 2>/dev/null
    CAIDOS=$((CAIDOS+1)); continue
  fi
  git -C "$WT" add -A >/dev/null 2>&1
  git -C "$WT" -c user.email=banco@metodo -c user.name=banco commit -qm "base: $id sin implementación — los tests de la tarea tienen que fallar" >/dev/null 2>&1
  SHA_BASE="$(git -C "$WT" rev-parse --short HEAD)"

  bash "$AQUI/preparar-entorno.sh" "$WT/$PROYECTO" >/dev/null 2>&1
  SALIDA_BASE="$(cd "$WT/$PROYECTO" && bash scripts/correr-suite.sh "$SEL" 2>&1)"; RC_BASE=$?

  # testigo: la implementación del commit verde.
  git -C "$WT" checkout "$TESTIGO_SHA" -- $IMPL 2>/dev/null
  git -C "$WT" add -A >/dev/null 2>&1
  git -C "$WT" -c user.email=banco@metodo -c user.name=banco commit -qm "testigo: $id con la implementación que cierra verde" >/dev/null 2>&1
  SHA_TEST="$(git -C "$WT" rev-parse --short HEAD)"
  SALIDA_TEST="$(cd "$WT/$PROYECTO" && bash scripts/correr-suite.sh "$SEL" 2>&1)"; RC_TEST=$?

  # El contrato: 1 = falla (lo que queremos en base), 0 = pasa (lo que queremos en testigo).
  # 2 = no corrió ningún test, 3 = del método, 127 = falta el corredor. Ninguno es «falla».
  MOTIVO=""
  case "$RC_BASE" in
    1) ;;
    0) MOTIVO="los tests PASAN sin la implementación: no distinguen" ;;
    2) MOTIVO="base: $CLASE no corrió ningún test" ;;
    3) MOTIVO="base: el corredor falló por el entorno" ;;
    *) MOTIVO="base: no pude correr el selector (código $RC_BASE)" ;;
  esac
  [ -z "$MOTIVO" ] && [ "$RC_TEST" != "0" ] && MOTIVO="testigo: los tests NO pasan con la implementación (código $RC_TEST)"
  # Rojo ATRIBUIBLE a la tarea, no daño colateral. Ver MEDICION.md §1, pregunta 4.
  #
  # `AttributeError: 'Juego' object has no attribute 'alternar_pausa'` SÍ cuenta: el test
  # llama al método que la implementación tiene que proveer, así que el rojo es exactamente
  # la señal que buscamos. `ImportError`/`ModuleNotFoundError` NO: se llevan tests ajenos y
  # abortan la colección —medido, uno bajó la suite de 103 a 82 tests corridos—, con lo que
  # el rojo no distingue esta tarea de ninguna otra.
  if [ -z "$MOTIVO" ] && printf '%s' "$SALIDA_BASE" | grep -qE "ImportError|ModuleNotFoundError|Failed to resolve import|Interrupted: .* error"; then
    # Un error de import con selector ACOTADO puede ser la señal o puede ser ruido, y lo que
    # los separa es QUÉ módulo falta: si es la implementación que acabamos de revertir, es
    # exactamente «la implementación no está» y es atribuible. Si falta otra cosa —`pymysql`,
    # una dependencia del entorno— el rojo no dice nada de esta tarea.
    #
    # Rechazarlos todos descartaba los ítems cuya implementación es un archivo NUEVO, que es
    # el caso normal en un proyecto greenfield.
    ATRIBUIBLE=""
    for a in $IMPL; do
      # `backend/app/datos/conexion.py` → busco `conexion` y `app.datos.conexion` y la ruta.
      mod="$(basename "$a" | sed 's/\.[^.]*$//')"
      rel="${a#$PROYECTO/}"
      if printf '%s' "$SALIDA_BASE" | grep -qF "$mod" || printf '%s' "$SALIDA_BASE" | grep -qF "$rel"; then
        ATRIBUIBLE="$a"; break
      fi
    done
    if [ -z "$ATRIBUIBLE" ]; then
      MOTIVO="base: rojo por un import que no es de esta tarea, no atribuible"
    fi
  fi

  if [ -n "$MOTIVO" ]; then
    printf '%-7s %-9s %-46s %s\n' "$id" "✗" "$SEL" "$MOTIVO"
    # conservar_intento: no-aplica — es un worktree de CONSTRUCCIÓN del banco, no la
    # corrida de un agente: no hay intento que conservar. Lo que vale queda en la rama
    # item/… y en su .precondicion, que se commitean antes de esto.
    tirar_base_del_worktree "$WT"
    git -C "$RAIZ" worktree remove --force "$WT" 2>/dev/null
    git -C "$RAIZ" branch -D "$RAMA" 2>/dev/null
    CAIDOS=$((CAIDOS+1)); continue
  fi

  # El recibo del ítem: los dos SHAs, el selector y la SALIDA LITERAL sobre base.
  {
    echo "# Ítem congelado: $PROYECTO $id"
    echo "proyecto: $PROYECTO"
    echo "tarea: $id"
    echo "selector: $SEL"
    echo "base: $SHA_BASE      # rc=$RC_BASE (1 = los tests de la tarea fallan)"
    echo "testigo: $SHA_TEST   # rc=$RC_TEST (0 = pasan con la implementación)"
    echo "commit_original: $TESTIGO_SHA"
    [ "$N_SHAS" -gt 1 ] && echo "aviso: la tarea tiene $N_SHAS commits «gate verde»; se usó el más nuevo"
    echo "implementación: $(echo $IMPL | tr '\n' ' ')"
    echo "congelado: $(date -u +%FT%TZ)"
    # `instrumento-proyecto` y no `instrumento`: el registro usa ese nombre para
    # `HEAD:scripts` (los scripts del MÉTODO) y acá se sella `HEAD:$PROYECTO/scripts` (el
    # corredor de suite del PROYECTO). Son dos árboles distintos; con el mismo nombre las
    # dos columnas parecían unibles y no lo son.
    echo "instrumento-proyecto: $(git -C "$RAIZ" rev-parse --short HEAD:$PROYECTO/scripts 2>/dev/null || echo '?')$(git -C "$RAIZ" diff --quiet HEAD -- "$PROYECTO/scripts" 2>/dev/null || echo ' +sin-commitear')"
    echo
    echo "## salida sobre base (tiene que ser rojo atribuible a la tarea)"
    # Sin la ruta absoluta del worktree de congelado, que no existe después y es justo el
    # defecto que el método tiene un test para evitar: una ruta clavada que pasó cuando se
    # escribió y falla en todos lados desde entonces.
    printf '%s\n' "$SALIDA_BASE" | tail -20 | sed "s|$WT/||g"
  } > "$WT/.precondicion"
  git -C "$WT" add -f .precondicion >/dev/null 2>&1
  git -C "$WT" -c user.email=banco@metodo -c user.name=banco commit -qm "recibo: la precondición de $id, verificada corriendo sus tests" >/dev/null 2>&1

  printf '%-7s %-9s %-46s %s\n' "$id" "✓" "$SEL" "$RAMA (base $SHA_BASE → testigo $SHA_TEST)"
  VIABLES=$((VIABLES+1))
  # conservar_intento: no-aplica — es un worktree de CONSTRUCCIÓN del banco, no la
  # corrida de un agente: no hay intento que conservar. Lo que vale queda en la rama
  # item/… y en su .precondicion, que se commitean antes de esto.
  tirar_base_del_worktree "$WT"
  git -C "$RAIZ" worktree remove --force "$WT" 2>/dev/null
done

echo
echo "Viables: $VIABLES   ·   caídos: $CAIDOS"
if [ "$VIABLES" -gt 0 ]; then
  echo "Cada viable quedó en su rama item/$PROYECTO-TNN, con .precondicion commiteado."
  echo "El recibo lleva la salida literal sobre base: si mañana no reproduce, se ve."
else
  echo "Ningún ítem quedó congelado. Los motivos de arriba son del BANCO, no de los modelos:"
  echo "un ítem que no puede establecer su estado rojo no mide nada de nadie."
fi
