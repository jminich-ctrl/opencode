#!/usr/bin/env bash
# G2→G3: mergea al tronco las tareas que dieron verde, de a una, con el gate de por medio.
#
#   SOLO_VER=1 bash scripts/integrar.sh          # qué haría, sin tocar nada
#   bash scripts/integrar.sh                     # todas las que estén en verde
#   bash scripts/integrar.sh T15 T16             # sólo esas
#
# Por qué existe: era el eslabón que faltaba. El runner corría el gate y commiteaba la
# rama, y ahí se terminaba todo — nadie mergeaba. El ejemplo de Pacman quedó semanas con
# el tronco en rojo mientras la tarea T17 figuraba VERDE: el agente la había arreglado
# bien, el gate lo confirmó, y el commit se quedó en la rama.
#
# Mergea DE A UNA y corre el gate del tronco después de cada merge. Si el tronco se pone
# rojo, deshace ese merge y para: así se sabe cuál tarea lo rompió, que es lo que no se
# puede saber mergeando todo junto.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto
SOLO_VER="${SOLO_VER:-0}"

TRONCO="$(git -C "$RAIZ" symbolic-ref --short HEAD 2>/dev/null)"
[ -n "$TRONCO" ] || { echo "✗ el repo no está en una rama" >&2; exit 1; }
if [ -n "$(git -C "$RAIZ" status --porcelain)" ] && [ "$SOLO_VER" != "1" ]; then
  echo "✗ el tronco tiene cambios sin commitear: mergear encima mezcla tu trabajo con el del agente" >&2
  exit 1
fi

# Línea base. Es una corrección de corrección, no una comodidad: sin ella, cada rama se
# valida contra su propia suite y el merge contra la del tronco, así que cualquier falla que
# ya estaba —o un test flaky— se le atribuye al merge. Está medido: con esa asimetría, "casi
# toda la interferencia aparente desaparece" al corregirla. Lo que antes era "el tronco está
# rojo" ahora es "ESTE merge lo puso rojo", que es lo único que justifica deshacerlo.
# La línea base no es "el tronco está verde": es QUÉ falla. Con los tests escritos antes,
# el tronco está rojo por diseño mientras una etapa está en vuelo —sus tests están
# commiteados y su implementación no—, así que exigir verde haría el método incompatible
# consigo mismo. Lo que importa es que el merge no agregue fallas NUEVAS.
# Las fallas del tronco, UNA POR UNA.
#
# Las dos capturas salían de `gate.sh | grep '✗'`, y en modo integración el paso 1 del gate
# colapsa toda la suite en UNA línea constante: «✗ la suite está en rojo». Así que el
# `comm -13` entre antes y después comparaba dos listas idénticas de un elemento y siempre
# salía vacío: «no agregó fallas nuevas» era un veredicto que no podía fallar. Un merge que
# rompiera veinte tests —incluido un ImportError que aborta la colección entera— pasaba, se
# marcaba ✅ hecha y se borraba la rama. Así entraron T14, T20 y T28 el 2026-10-19.
#
# `correr-suite.sh --fallas` es el MISMO comando que el runner usa para la línea base de cada
# tarea, y lista las fallas de a una. Cuesta una corrida de suite extra por captura; el
# veredicto que reemplaza no costaba nada y no medía nada.
# El `sort -u` envuelve a la función ENTERA y no a cada bloque. `comm` exige orden GLOBAL en
# sus dos entradas, y dos bloques ordenados por separado y concatenados no lo están: con los
# bloques desordenados `comm -13` sobre-reporta y devuelve como «nueva» una falla que ya
# estaba en la línea base — o sea `reset --hard HEAD~1` culpando a una tarea correcta. Hoy no
# se dispara por ACCIDENTE: el `✗` que sobrevive al `sed` ordena después del ASCII en este
# locale, así que la concatenación sale ordenada. Una garantía incidental no es una garantía.
fallas_del_tronco() {
  {
    ( cd "$BASE" && bash scripts/correr-suite.sh --fallas 2>/dev/null | grep . )
    # Y los chequeos del gate que NO son la suite: ésos sí son una línea por falla. Se saca
    # la línea resumen de la suite para no mezclar granularidades.
    ( cd "$BASE" && TAREA= bash scripts/gate.sh 2>&1 ) \
      | grep '✗' | grep -v 'la suite está en rojo' | sed 's/^ *//'
  } | sort -u
}
# Sin `LC_ALL=C` a propósito: `comm` compara en el orden de colación del locale ACTUAL y
# avisa si su entrada no está ordenada así. Ordenar con un locale y comparar con otro es la
# forma de que el aviso aparezca —o peor, no aparezca— según la máquina.

FALLAS_BASE=""
if [ "$SOLO_VER" != "1" ]; then
  echo "── línea base del tronco"
  FALLAS_BASE="$(fallas_del_tronco || true)"
  if [ -z "$FALLAS_BASE" ]; then
    echo "  ✓ el tronco está verde: lo que rompa de acá en más es del merge"
  else
    echo "  · el tronco arranca con $(echo "$FALLAS_BASE" | grep -c .) falla(s) ya presentes:"
    echo "$FALLAS_BASE" | sed 's/^/     /'
    echo "    Se toman como línea base. Sólo se culpa al merge por fallas NUEVAS."
    echo "    (Es lo normal si hay tests escritos de una etapa que todavía no aterrizó.)"
  fi
fi

# Qué tareas: las pedidas, o todas las que tengan rama y veredicto VERDE.
CANDIDATAS=()
if [ $# -gt 0 ]; then CANDIDATAS=("$@")
else
  while IFS= read -r b; do CANDIDATAS+=("${b#tarea/}"); done \
    < <(git -C "$RAIZ" branch --format='%(refname:short)' | grep '^tarea/' || true)
fi
[ "${#CANDIDATAS[@]}" -gt 0 ] || { echo "· no hay ramas tarea/* para integrar"; exit 0; }

integradas=(); saltadas=()
for id in "${CANDIDATAS[@]}"; do
  rama="tarea/$id"
  git -C "$RAIZ" rev-parse --verify "$rama" >/dev/null 2>&1 || { saltadas+=("$id:sin rama"); continue; }

  # El veredicto sale del gate que corrió el runner, nunca del log del agente (METODO.md P2).
  log="$RAIZ/../trabajo-$id/.tarea.log"
  v="$(veredicto "$log" 2>/dev/null)"
  if [ "$v" != "VERDE" ]; then saltadas+=("$id:veredicto=${v:-sin correr}"); continue; fi

  # Y el test que la tarea declara tiene que EXISTIR. El mismo agujero que el paso 1 del
  # gate, un nivel más arriba: acá el veredicto se mide por «no agregó fallas nuevas sobre la
  # línea base», y una tarea sin tests no agrega ninguna. El 2026-10-19 integré T14, T20 y
  # T28 así —invocando este script a mano después de un salteo de etapa que dejó a las tres
  # sin tests— y el código de T14 ni se podía importar. Hubo que revertir las tres.
  #
  # Se lee del archivo de tarea, que es la declaración canónica, igual que en el gate.
  t_decl="$(sed -n 's/.*`\([^`]*\)`, *clase `[A-Za-z0-9_]*`.*/\1/p' \
            "$BASE/tareas/${id}"-*.md 2>/dev/null | head -1)"
  if [ -n "$t_decl" ] && [ ! -f "$BASE/$t_decl" ]; then
    saltadas+=("$id:declara $t_decl y no está en el árbol")
    continue
  fi

  pendientes="$(git -C "$RAIZ" log --oneline "$TRONCO..$rama" | wc -l | xargs)"
  if [ "$pendientes" = "0" ]; then
    echo "· $id: ya está en el tronco"
    [ "$SOLO_VER" = "1" ] || marcar_hecha_y_limpiar "$id" "$rama"
    integradas+=("$id"); continue
  fi

  if [ "$SOLO_VER" = "1" ]; then
    echo "· $id: mergearía $pendientes commit(s) y correría el gate del tronco"
    continue
  fi

  echo "── integrando $id ($pendientes commit/s)"
  if ! git -C "$RAIZ" merge --no-edit --no-ff -m "Integrar $id" "$rama" >/dev/null 2>&1; then
    git -C "$RAIZ" merge --abort 2>/dev/null
    echo "  ✗ conflicto al mergear $rama. Resolvelo a mano:"
    echo "      git merge $rama"
    echo "  Y si el trabajo ya está en el tronco por otra vía, descartá la rama:"
    echo "      git branch -D $rama"
    exit 1
  fi

  # El gate del tronco, después de cada merge. Diez merges juntos y un tronco rojo no
  # dicen cuál lo rompió.
  FALLAS_AHORA="$(fallas_del_tronco || true)"
  NUEVAS_FALLAS="$(comm -13 <(echo "$FALLAS_BASE") <(echo "$FALLAS_AHORA") | grep . || true)"
  if [ -z "$NUEVAS_FALLAS" ]; then
    if [ -z "$FALLAS_AHORA" ]; then echo "  ✓ tronco verde después de $id"
    else echo "  ✓ $id no agregó fallas nuevas (las de la línea base siguen)"; fi
    marcar_hecha_y_limpiar "$id" "$rama"
    integradas+=("$id")
  else
    # Una sola repetición, y no para "darle otra chance": para distinguir una falla real de
    # un test inestable. Medido en Google: el 84% de las transiciones pasa→falla son flaky.
    # Si las dos corridas no coinciden, el problema es el test y lo decide una persona:
    # aceptar el verde del segundo intento es exactamente cómo la inestabilidad tapa fallas.
    FALLAS_REPETIR="$(fallas_del_tronco || true)"
    if [ -z "$(comm -13 <(echo "$FALLAS_BASE") <(echo "$FALLAS_REPETIR") | grep . || true)" ]; then
      echo "  ⚠ $id: la segunda corrida no repite las fallas de la primera. Hay un test inestable."
      echo "     No se acepta ni se descarta: arreglá el test. El merge queda hecho y se para acá."
      echo "     Para deshacerlo: git -C $RAIZ reset --hard HEAD~1"
      exit 1
    fi
    git -C "$RAIZ" reset --hard HEAD~1 >/dev/null 2>&1
    echo "  ✗ $id agregó fallas NUEVAS al tronco, dos veces seguidas. Merge deshecho."
    echo "$NUEVAS_FALLAS" | sed 's/^/     /'
    exit 1
  fi
done

echo
[ "${#integradas[@]}" -gt 0 ] && echo "✓ integradas: ${integradas[*]}"
[ "${#saltadas[@]}" -gt 0 ] && { echo "· saltadas:"; for s in "${saltadas[@]}"; do echo "    ${s%%:*} — ${s#*:}"; done; }
if [ "$SOLO_VER" != "1" ] && [ "${#integradas[@]}" -gt 0 ]; then
  echo
  echo "Lo que sigue es G3, y lo hace una persona: usar la cosa."
  echo "  bash $AQUI/estado.sh"
fi
