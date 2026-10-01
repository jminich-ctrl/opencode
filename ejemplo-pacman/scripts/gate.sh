#!/usr/bin/env bash
# Gate G1: decide si una tarea está terminada. No opina, ejecuta.
#   1) tests   2) alcance   3) higiene
# Verde => imprime "GATE VERDE". Cualquier rojo => sale con código 1.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
FALLOS=0
rojo() { echo "  ✗ $1"; FALLOS=$((FALLOS+1)); }
verde() { echo "  ✓ $1"; }

# Punto de partida del diff. Lo escribe el runner al crear el worktree, ANTES de que el
# agente toque nada: si lo dedujéramos acá, el primer commit del agente movería la base y
# los pasos 0 y 2 dejarían de ver sus propios cambios.
RAIZ_WT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -f "$RAIZ_WT/.base-ref" ]; then
  BASE_REF="$(cat "$RAIZ_WT/.base-ref")"
else
  BASE_REF="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD)"
fi

# ── 0. Integridad (solo en modo tarea)
# El gate y los tests viven dentro del worktree del agente, así que son editables.
# Esta lista NO sale del archivo de tarea: un agente que puede ampliarse el alcance
# deja de estar limitado por él. Medido en la literatura y acá: pedirlo por prompt no
# alcanza, el límite tiene que ser un comando que corre alguien más.
INTOCABLES='^(tests/|scripts/)'
if [ -n "${TAREA:-}" ]; then
  echo "── 0. Integridad"
  TOCADO="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null | grep -E "$INTOCABLES" || true)"
  if [ -n "$TOCADO" ]; then
    rojo "tocó archivos intocables (tests o el propio gate):"; echo "$TOCADO" | sed 's/^/     /'
  else
    verde "tests y scripts intactos"
  fi
fi

echo "── 1. Tests"
SALIDA="$(python3 -m unittest discover -s tests -t . -q 2>&1)"
if echo "$SALIDA" | grep -qE '^Ran 0 tests'; then
  # Una suite vacía pasa siempre. Que "no pude verificar" se parezca a "verifiqué y está
  # bien" es la trampa recurrente de este archivo: acá, explícito y en rojo.
  rojo "la suite no corrió ningún test"
elif echo "$SALIDA" | grep -qE '^OK'; then
  verde "$(echo "$SALIDA" | grep -E '^Ran ' | head -1)"
else
  rojo "tests en rojo"; echo "$SALIDA" | tail -15 | sed 's/^/     /'
fi

echo "── 2. Alcance${TAREA:+ (tarea $TAREA)}"
# archivos modificados respecto del punto de partida de la rama
# La infraestructura del runner no es parte del trabajo de la tarea: se filtra ACÁ y no en
# el .gitignore de cada proyecto, porque olvidarse de una línea del .gitignore ponía en rojo
# toda tarea (`.base-ref` es un archivo que escribe el propio runner).
INFRA='^(\.base-ref|\.tarea\.log|\.segundos|\.plan\.log|\.opencode-data/|\.metricas/)'
CAMBIADOS="$( { git diff --name-only --relative "$BASE_REF" 2>/dev/null; git ls-files --others --exclude-standard; } | grep -vE "$INFRA" || true)"
if [ -z "$CAMBIADOS" ] && [ -n "${TAREA:-}" ]; then
  rojo "no hay ningún cambio: la tarea no se hizo"
elif [ -z "$CAMBIADOS" ]; then
  verde "árbol limpio (modo integración)"
else
  echo "$CAMBIADOS" | sed 's/^/     /' | sort -u
  # El alcance sale del archivo de la tarea, no de reglas hardcodeadas acá: una regla
  # escrita a mano queda vieja en cuanto el plan crece (nos pasó con render.py y T12).
  PERMITIDOS="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/${TAREA:-}"-*.md 2>/dev/null \
                | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+\.(py|txt|md)' | sort -u)"
  if [ -n "${TAREA:-}" ] && [ -z "$PERMITIDOS" ]; then
    rojo "la tarea $TAREA no declara \"Archivos que podés tocar\": sin alcance no hay gate"
  elif [ -z "${TAREA:-}" ]; then
    verde "sin límite de alcance declarado (modo integración)"
  else
    FUERA=""
    while read -r archivo; do
      [ -n "$archivo" ] || continue
      # por ruta y no por basename: 'entidades.py' permitido no habilita 'tests/entidades.py'
      ok=""
      while read -r permitido; do
        [ -n "$permitido" ] || continue
        [ "$archivo" = "$permitido" ] || [ "$archivo" = "src/$permitido" ] && ok=1
      done <<< "$PERMITIDOS"
      [ -n "$ok" ] || FUERA="$FUERA $archivo"
    done <<< "$CAMBIADOS"
    if [ -n "$FUERA" ]; then
      rojo "archivos fuera del alcance de $TAREA:$FUERA"
      echo "     permitidos: $(echo "$PERMITIDOS" | tr '\n' ' ')"
    else
      verde "todo dentro del alcance declarado en tareas/$TAREA-*.md"
    fi
  fi
fi

echo "── 3. Higiene"
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
if grep -rqE '^\s*(import|from)\s+(pygame|numpy|pytest)' src/ 2>/dev/null; then rojo "dependencia externa en src/"; else verde "solo biblioteca estándar"; fi
if grep -rn "TODO" src/ 2>/dev/null | grep -qv '^\s*$'; then rojo "quedaron TODO en src/: $(grep -rn 'TODO' src/ | head -2 | tr '\n' ' ')"; else verde "sin TODO sueltos"; fi
if ! python3 -m compileall -q src/ >/dev/null 2>&1; then rojo "src/ no compila"; else verde "src/ compila"; fi
# Apagar una señal es más barato que arreglar la causa, y no deja rastro en los tests.
SUPRESIONES="$(grep -rnE '# *(noqa|type: *ignore)|except[^:]*: *pass|@unittest\.skip|\|\| *true' src/ 2>/dev/null || true)"
if [ -n "$SUPRESIONES" ]; then
  rojo "hay señales suprimidas en src/:"; echo "$SUPRESIONES" | head -3 | sed 's/^/     /'
else verde "sin señales suprimidas"; fi

# ── 4. ¿Los tests distinguen? (solo en modo tarea)
# Revierte la implementación y exige que la suite FALLE. Un test que pasa con el
# código viejo no prueba nada, y el gate no lo detecta de ninguna otra forma:
# nos pasó en T13, con dos tests cuyo assert era "len(posiciones) > 0".
if [ -n "${TAREA:-}" ]; then
  echo "── 4. ¿Los tests distinguen?"
  IMPL="$(echo "$CAMBIADOS" | grep -E 'src/.*\.py$' || true)"   # rutas relativas a la raíz del repo
  TMP="$(mktemp -d)"; REVERTIDOS=""
  PREFIJO="$(git rev-parse --show-prefix)"   # vacío si el proyecto es la raíz del repo
  for f in $IMPL; do
    if git cat-file -e "HEAD:${PREFIJO}$f" 2>/dev/null; then
      cp "$f" "$TMP/$(echo "$f" | tr / _)"
      git checkout HEAD -- "$f" && REVERTIDOS="$REVERTIDOS $f"
    fi
  done
  if [ -z "$IMPL" ]; then
    verde "no hay implementación nueva que revertir"
  elif [ -z "$REVERTIDOS" ]; then
    verde "archivos nuevos (no existían en HEAD): nada que revertir"
  else
    # Qué tests tienen que fallar, no sólo que "algo" falle: medido, la tasa agregada casi
    # no se mueve ante una regresión mientras las métricas por porción caen 25 a 91 puntos.
    ESPERADO="$(sed -n 's/.*`\(tests\/[A-Za-z0-9_.]*\)`.*clase `\([A-Za-z0-9_]*\)`.*/\1 \2/p' \
                 "tareas/${TAREA}"-*.md 2>/dev/null | head -1)"
    if python3 -m unittest discover -s tests -t . -q >/dev/null 2>&1; then
      rojo "los tests PASAN con la implementación vieja: no verifican el cambio"
      echo "     revertí:$REVERTIDOS y la suite siguió verde"
    elif [ -n "$ESPERADO" ]; then
      MOD="$(echo "$ESPERADO" | cut -d' ' -f1 | sed 's|/|.|g; s|\.py$||')"
      CLASE="$(echo "$ESPERADO" | cut -d' ' -f2)"
      if python3 -m unittest "$MOD.$CLASE" >/dev/null 2>&1; then
        rojo "la suite falla, pero NO por los tests de esta tarea ($CLASE pasa con el código viejo)"
        echo "     o los tests de $TAREA no verifican el cambio, o rompiste otra cosa"
      else
        verde "fallan los tests de la tarea ($CLASE) al revertir$REVERTIDOS"
      fi
    else
      verde "la suite falla al revertir$REVERTIDOS (la tarea no nombra sus tests)"
    fi
    for f in $REVERTIDOS; do cp "$TMP/$(echo "$f" | tr / _)" "$f"; done
  fi
  rm -rf "$TMP"
fi

# ── 5. Coherencia (sólo en modo integración)
# Los pasos 0-4 miran UNA tarea. Ninguno puede ver que diez diffs correctos por separado
# dejaron la arquitectura peor: esa deriva sólo se ve mirando el conjunto, y por eso este
# paso corre sobre el tronco y no dentro del worktree de una tarea.
if [ -z "${TAREA:-}" ] && [ -f scripts/_arquitectura.py ]; then
  echo "── 5. Coherencia"
  if OUT="$(python3 scripts/_arquitectura.py 2>&1)"; then echo "$OUT"
  else echo "$OUT"; FALLOS=$((FALLOS+1)); fi
fi

echo
if [ "$FALLOS" -eq 0 ]; then echo "GATE VERDE"; exit 0; else echo "GATE ROJO ($FALLOS fallo/s)"; exit 1; fi
