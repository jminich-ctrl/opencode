#!/usr/bin/env bash
# Gate G1 del sitio de clasificados. Adaptado de ejemplo-pacman/scripts/gate.sh:
# mismo esqueleto, distinta suite (pytest atrás, vitest adelante) y distintas capas.
#   0) integridad  1) tests  2) alcance  3) higiene  4) ¿distinguen?  5) coherencia
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
FALLOS=0
rojo() { echo "  ✗ $1"; FALLOS=$((FALLOS+1)); }
verde() { echo "  ✓ $1"; }

# La base del diff la fija el runner al crear el worktree, antes de que el agente toque nada.
RAIZ_WT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -f "$RAIZ_WT/.base-ref" ]; then BASE_REF="$(cat "$RAIZ_WT/.base-ref")"
else BASE_REF="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD)"; fi

# ── 0. Integridad
# Los tests y el propio gate viven dentro del worktree del agente. La lista es fija acá y
# el archivo de tarea NO puede ampliarla.
INTOCABLES='^(backend/tests/|frontend/tests/|scripts/)'
if [ -n "${TAREA:-}" ]; then
  echo "── 0. Integridad"
  TOCADO="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null | grep -E "$INTOCABLES" || true)"
  if [ -n "$TOCADO" ]; then rojo "tocó archivos intocables (tests o el propio gate):"; echo "$TOCADO" | sed 's/^/     /'
  else verde "tests y scripts intactos"; fi
fi

echo "── 1. Tests"
CORRIO=0
if [ -d backend/tests ] && ls backend/tests/test_*.py >/dev/null 2>&1; then
  SALIDA="$(cd backend && python3 -m pytest -q 2>&1)"
  if echo "$SALIDA" | grep -qE 'no tests ran|collected 0 items'; then
    rojo "backend: la suite no corrió ningún test"
  elif echo "$SALIDA" | grep -qE '[0-9]+ passed' && ! echo "$SALIDA" | grep -qE '[0-9]+ (failed|error)'; then
    verde "backend: $(echo "$SALIDA" | grep -oE '[0-9]+ passed[^ ]*' | head -1)"; CORRIO=1
  else
    rojo "backend en rojo"; echo "$SALIDA" | tail -15 | sed 's/^/     /'
  fi
fi
if [ -f frontend/package.json ] && grep -q '"vitest"' frontend/package.json 2>/dev/null; then
  SALIDA="$(cd frontend && npx --no-install vitest run --reporter=basic 2>&1)"
  if echo "$SALIDA" | grep -qE 'No test files found'; then
    rojo "frontend: la suite no corrió ningún test"
  elif echo "$SALIDA" | grep -qE 'FAIL|failed'; then
    rojo "frontend en rojo"; echo "$SALIDA" | tail -15 | sed 's/^/     /'
  else verde "frontend: tests en verde"; CORRIO=1; fi
fi
[ "$CORRIO" = "0" ] && rojo "no se ejecutó ninguna suite: sin tests no hay gate"

echo "── 2. Alcance${TAREA:+ (tarea $TAREA)}"
CAMBIADOS="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null; git ls-files --others --exclude-standard)"
if [ -z "$CAMBIADOS" ] && [ -n "${TAREA:-}" ]; then
  rojo "no hay ningún cambio: la tarea no se hizo"
elif [ -z "$CAMBIADOS" ]; then
  verde "árbol limpio (modo integración)"
else
  echo "$CAMBIADOS" | sed 's/^/     /' | sort -u
  PERMITIDOS="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/${TAREA:-}"-*.md 2>/dev/null \
                | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+\.(py|ts|tsx|js|jsx|scss|sql|json|md)' | sort -u)"
  if [ -n "${TAREA:-}" ] && [ -z "$PERMITIDOS" ]; then
    rojo "la tarea $TAREA no declara \"Archivos que podés tocar\": sin alcance no hay gate"
  elif [ -z "${TAREA:-}" ]; then
    verde "sin límite de alcance declarado (modo integración)"
  else
    FUERA=""
    while read -r archivo; do
      [ -n "$archivo" ] || continue
      ok=""
      while read -r permitido; do
        [ -n "$permitido" ] || continue
        [ "$archivo" = "$permitido" ] && ok=1
      done <<< "$PERMITIDOS"
      [ -n "$ok" ] || FUERA="$FUERA $archivo"
    done <<< "$CAMBIADOS"
    if [ -n "$FUERA" ]; then
      rojo "archivos fuera del alcance de $TAREA:$FUERA"
      echo "     permitidos: $(echo "$PERMITIDOS" | tr '\n' ' ')"
    else verde "todo dentro del alcance declarado"; fi
  fi
fi

echo "── 3. Higiene"
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$|node_modules/|dist/'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
if grep -rqE 'tailwind' frontend/ --include=*.json --include=*.js --include=*.ts 2>/dev/null; then rojo "apareció Tailwind: el diseño es propio"; else verde "sin librerías de diseño"; fi
SUP="$(grep -rnE '# *(noqa|type: *ignore)|except[^:]*: *pass|@ *unittest\.skip|\.skip\(|\|\| *true|eslint-disable' backend/app frontend/src 2>/dev/null || true)"
if [ -n "$SUP" ]; then rojo "hay señales suprimidas:"; echo "$SUP" | head -3 | sed 's/^/     /'; else verde "sin señales suprimidas"; fi
if grep -rn "TODO" backend/app frontend/src 2>/dev/null | grep -q .; then rojo "quedaron TODO sueltos"; else verde "sin TODO sueltos"; fi

# ── 4. ¿Los tests distinguen? (sólo en modo tarea)
if [ -n "${TAREA:-}" ]; then
  echo "── 4. ¿Los tests distinguen?"
  IMPL="$(echo "$CAMBIADOS" | grep -E '^(backend/app|frontend/src)/.*\.(py|ts|tsx|jsx)$' || true)"
  TMP="$(mktemp -d)"; REVERTIDOS=""
  PREFIJO="$(git rev-parse --show-prefix)"   # vacío si el proyecto es la raíz del repo
  for f in $IMPL; do
    if git cat-file -e "HEAD:${PREFIJO}$f" 2>/dev/null; then
      cp "$f" "$TMP/$(echo "$f" | tr / _)"
      git checkout HEAD -- "$f" && REVERTIDOS="$REVERTIDOS $f"
    fi
  done
  if [ -z "$IMPL" ]; then verde "no hay implementación nueva que revertir"
  elif [ -z "$REVERTIDOS" ]; then verde "archivos nuevos (no existían en HEAD): nada que revertir"
  else
    if ( cd backend && python3 -m pytest -q >/dev/null 2>&1 ); then
      rojo "los tests PASAN con la implementación vieja: no verifican el cambio"
      echo "     revertí:$REVERTIDOS y la suite siguió verde"
    else verde "la suite falla al revertir$REVERTIDOS"; fi
    for f in $REVERTIDOS; do cp "$TMP/$(echo "$f" | tr / _)" "$f"; done
  fi
  rm -rf "$TMP"
fi

# ── 5. Coherencia (sólo en modo integración): lo único que mira a través de las tareas.
if [ -z "${TAREA:-}" ] && [ -f scripts/_arquitectura.py ]; then
  echo "── 5. Coherencia"
  if OUT="$(python3 scripts/_arquitectura.py 2>&1)"; then echo "$OUT"
  else echo "$OUT"; FALLOS=$((FALLOS+1)); fi
fi

echo
if [ "$FALLOS" -eq 0 ]; then echo "GATE VERDE"; exit 0; else echo "GATE ROJO ($FALLOS fallo/s)"; exit 1; fi
