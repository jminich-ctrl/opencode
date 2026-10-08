#!/usr/bin/env bash
# G4 — pre-deploy: lo que rompe en producción y no en local.
#
# Copiala a tu proyecto como scripts/pre-deploy.sh y adaptá las partes marcadas
# con ADAPTAR. Corre sobre el tronco, después de G3.
#
#   bash scripts/pre-deploy.sh [rama-base]     (por defecto: origin/main)
#
# Verde => sale 0. Cualquier rojo => sale 1 y el deploy no arranca.
set -uo pipefail
# El proyecto es el directorio de este script, no la raíz del repo: un repo puede
# tener varios proyectos (nos pasó, y el smoke quedó sin correr sin que nadie lo notara).
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
RAIZ="$(git rev-parse --show-toplevel)"
PREFIJO="${PWD#$RAIZ/}"; [ "$PREFIJO" = "$PWD" ] && PREFIJO=""
BASE="${1:-origin/main}"
git rev-parse --verify -q "$BASE" >/dev/null || BASE="$(git rev-parse HEAD~1 2>/dev/null || echo HEAD)"

FALLOS=0
rojo()  { echo "  ✗ $1"; FALLOS=$((FALLOS+1)); }
verde() { echo "  ✓ $1"; }
aviso() { echo "  · $1"; }

DIFF="$(git diff --name-only "$BASE"...HEAD ${PREFIJO:+-- "$RAIZ/$PREFIJO"} 2>/dev/null)"
[ -n "$DIFF" ] || aviso "sin cambios contra $BASE"

echo "── 1. Secretos"
# Un secreto commiteado ya está filtrado aunque lo borres en el commit siguiente:
# hay que rotarlo. Por eso esto es rojo, no aviso.
PATRON='(api[_-]?key|secret|password|passwd|token|BEGIN [A-Z ]*PRIVATE KEY)[^a-z]{0,3}[:=][^=]'
if git diff "$BASE"...HEAD -U0 2>/dev/null | grep -iE '^\+' | grep -iEq "$PATRON"; then
  rojo "hay algo que parece un secreto en el diff"
  git diff "$BASE"...HEAD -U0 | grep -iE '^\+' | grep -iE "$PATRON" | head -3 | sed 's/^/     /'
  echo "     si es real: rotalo, no alcanza con borrarlo del próximo commit"
else
  verde "sin secretos evidentes en el diff"
fi
if echo "$DIFF" | grep -qE '(^|/)\.env$'; then rojo ".env en el diff"; fi

echo "── 2. Dependencias nuevas"
# ADAPTAR: el archivo de dependencias de tu stack
DEPS="requirements.txt"          # o package.json, pyproject.toml, go.mod…
if echo "$DIFF" | grep -q "$DEPS"; then
  NUEVAS="$(git diff "$BASE"...HEAD -- "$DEPS" | grep -E '^\+[^+]' | sed 's/^+/     /')"
  [ -n "$NUEVAS" ] && { aviso "dependencias agregadas — justificalas o sacalas:"; echo "$NUEVAS"; }
else
  verde "sin dependencias nuevas"
fi

echo "── 3. Migraciones"
# ADAPTAR: dónde viven y cómo se aplican/revierten
MIGRACIONES="migrations"
if [ -d "$MIGRACIONES" ] && echo "$DIFF" | grep -q "^$MIGRACIONES/"; then
  for m in $(echo "$DIFF" | grep "^$MIGRACIONES/"); do
    if grep -qiE '\bdown\b|\bdowngrade\b|-- *revers' "$m" 2>/dev/null; then
      verde "$(basename "$m") tiene reversa"
    else
      rojo "$(basename "$m") NO tiene reversa: un deploy sin vuelta atrás es una apuesta"
    fi
  done
else
  verde "sin migraciones en este cambio"
fi

echo "── 4. Variables de entorno"
# Las que el código nuevo lee y no están declaradas en el ejemplo del repo
USADAS="$(git diff "$BASE"...HEAD -U0 | grep -E '^\+' \
  | grep -oE "(os\.environ(\.get)?\(['\"][A-Z_]+|process\.env\.[A-Z_]+|getenv\(['\"][A-Z_]+)" \
  | grep -oE '[A-Z_]{3,}' | sort -u)"
if [ -n "$USADAS" ]; then
  FALTAN=""
  for v in $USADAS; do
    grep -qE "^$v=" .env.example 2>/dev/null || grep -rqE "\b$v\b" README.md 2>/dev/null || FALTAN="$FALTAN $v"
  done
  [ -n "$FALTAN" ] && rojo "variables usadas y no documentadas:$FALTAN" || verde "las variables nuevas están documentadas"
else
  verde "sin variables de entorno nuevas"
fi

echo "── 5. Build"
# ADAPTAR: el build real de producción, no los tests
if ! python3 -m compileall -q . >/dev/null 2>&1; then rojo "el código no compila"; else verde "compila"; fi

echo "── 6. Smoke de arranque"
# El chequeo que más rinde: que la aplicación ARRANQUE. Los tests unitarios no lo ven,
# porque el bug vive en el arranque, el cableado y la configuración. Nuestro Pacman
# crasheaba al arrancar con 70 tests en verde.
# ADAPTAR: el comando que levanta tu app, y cuántos segundos esperar.
if [ -x scripts/smoke.sh ]; then
  if bash scripts/smoke.sh; then verde "la aplicación arranca"; else rojo "la aplicación NO arranca"; fi
else
  # Rojo, no aviso: un G4 que da verde salteándose el chequeo que más atrapa es
  # exactamente la trampa que veníamos arreglando en el gate de tareas.
  rojo "no hay scripts/smoke.sh — sin smoke de arranque, G4 no puede dar verde"
  echo "     escribilo: que levante la app de verdad y verifique que responde"
fi

echo "── 7. La suite sobre un checkout limpio"
# Todo lo anterior corre sobre el árbol de trabajo, donde puede haber archivos sin
# commitear que hacen pasar los tests. Lo que se despliega es lo COMMITEADO, así que la
# última verificación se hace sobre un clon limpio de HEAD. Es la forma en que
# SWE-Bench Pro V2 atrapó contenidos de archivo falsificados.
LIMPIO="$(mktemp -d)"
if git clone -q --no-hardlinks --depth 1 "file://$RAIZ" "$LIMPIO/repo" 2>/dev/null; then
  if ( cd "$LIMPIO/repo/${PREFIJO:-.}" && python3 -m unittest discover -s tests -t . -q ) >"$LIMPIO/salida" 2>&1; then
    verde "la suite pasa sobre lo commiteado ($(grep -E '^Ran ' "$LIMPIO/salida" | head -1))"
  else
    rojo "la suite FALLA sobre un checkout limpio: hay algo sin commitear que la sostiene"
    tail -12 "$LIMPIO/salida" | sed 's/^/     /'
  fi
else
  rojo "no pude clonar el repo para verificar sobre lo commiteado"
fi
rm -rf "$LIMPIO"

echo
if [ "$FALLOS" -eq 0 ]; then echo "PRE-DEPLOY VERDE"; exit 0
else echo "PRE-DEPLOY ROJO ($FALLOS fallo/s) — el deploy no arranca"; exit 1; fi
