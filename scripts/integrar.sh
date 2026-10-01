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
if [ "$SOLO_VER" != "1" ]; then
  echo "── línea base del tronco"
  if ( cd "$BASE" && TAREA= bash scripts/gate.sh >/dev/null 2>&1 ); then
    verde_base=1; echo "  ✓ el tronco está verde: lo que rompa de acá en más es del merge"
  else
    echo "  ✗ el tronco YA está rojo antes de mergear nada. No se integra encima de eso:" >&2
    ( cd "$BASE" && TAREA= bash scripts/gate.sh 2>&1 ) | grep '✗' | sed 's/^/     /' >&2
    echo "  Arreglá el tronco primero. Si no, el próximo merge se va a llevar la culpa." >&2
    exit 1
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
  if ( cd "$BASE" && TAREA= bash scripts/gate.sh >/dev/null 2>&1 ); then
    echo "  ✓ tronco verde después de $id"
    marcar_hecha_y_limpiar "$id" "$rama"
    integradas+=("$id")
  else
    # Una sola repetición, y no para "darle otra chance": para distinguir una falla real de
    # un test inestable. Medido en Google: el 84% de las transiciones pasa→falla son flaky.
    # Si las dos corridas no coinciden, el problema es el test y lo decide una persona:
    # aceptar el verde del segundo intento es exactamente cómo la inestabilidad tapa fallas.
    if ( cd "$BASE" && TAREA= bash scripts/gate.sh >/dev/null 2>&1 ); then
      echo "  ⚠ $id: el tronco dio rojo y después verde con el mismo código. Hay un test inestable."
      echo "     No se acepta ni se descarta: arreglá el test. El merge queda hecho y se para acá."
      echo "     Para deshacerlo: git -C $RAIZ reset --hard HEAD~1"
      exit 1
    fi
    git -C "$RAIZ" reset --hard HEAD~1 >/dev/null 2>&1
    echo "  ✗ $id puso el tronco en ROJO dos veces seguidas. Merge deshecho."
    ( cd "$BASE" && TAREA= bash scripts/gate.sh 2>&1 ) | grep '✗' | sed 's/^/     /'
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
