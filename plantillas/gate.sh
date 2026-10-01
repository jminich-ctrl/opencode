#!/usr/bin/env bash
# Gate G1: decide si una tarea está terminada. No opina, ejecuta.
#   0) integridad  1) tests  2) alcance  3) higiene  4) ¿distinguen?  5) coherencia
#
# PLANTILLA. Buscá "ADAPTAR" — son cuatro líneas: el comando de tests, la marca de suite
# vacía, los directorios de código, y las reglas de higiene propias de tu stack.
#
# Verde => imprime "GATE VERDE" y sale 0. Cualquier rojo => sale 1.
#
# Dos reglas que no se tocan al adaptarlo, porque cada una salió de un falso verde real:
#   · Un chequeo que no pudo ejecutarse da ROJO, nunca verde.
#   · Lo que el agente no puede tocar lo decide ESTE archivo, no el archivo de tarea.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
FALLOS=0
rojo() { echo "  ✗ $1"; FALLOS=$((FALLOS+1)); }
verde() { echo "  ✓ $1"; }

# ADAPTAR: el comando que corre TODA tu suite, y cómo se ve una suite que no corrió nada.
TESTS="python3 -m unittest discover -s tests -t . -q"
VACIA='^Ran 0 tests'
# ADAPTAR: dónde vive el código de producción (no los tests).
CODIGO="src"

# La base del diff la escribe el runner al crear el worktree, ANTES de que el agente toque
# nada. Si la dedujera este script, el primer commit del agente movería la base y los pasos
# 0 y 2 dejarían de ver sus propios cambios.
RAIZ_WT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -f "$RAIZ_WT/.base-ref" ]; then BASE_REF="$(cat "$RAIZ_WT/.base-ref")"
else BASE_REF="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD)"; fi

# ── 0. Integridad (sólo en modo tarea)
# Los tests y este archivo viven DENTRO del worktree del agente al que juzgan. La lista es
# fija acá y el archivo de tarea no puede ampliarla: un límite que el limitado puede
# reescribir no es un límite. Pedirlo por prompt está medido que no alcanza.
INTOCABLES='^(tests/|scripts/)'
if [ -n "${TAREA:-}" ]; then
  echo "── 0. Integridad"
  # --relative: git informa rutas desde la raíz del repo, y acá razonamos en rutas del
  # proyecto. Sin esto el chequeo daba VERDE con un test modificado.
  TOCADO="$(git diff --name-only --relative "$BASE_REF" 2>/dev/null | grep -E "$INTOCABLES" || true)"
  if [ -n "$TOCADO" ]; then rojo "tocó archivos intocables (tests o el propio gate):"; echo "$TOCADO" | sed 's/^/     /'
  else verde "tests y scripts intactos"; fi
fi

echo "── 1. Tests"
SALIDA="$($TESTS 2>&1)"
if echo "$SALIDA" | grep -qE "$VACIA"; then
  # Una suite vacía pasa siempre. "No pude verificar" no puede parecerse a "verifiqué".
  rojo "la suite no corrió ningún test"
elif echo "$SALIDA" | grep -qE '^OK'; then
  verde "$(echo "$SALIDA" | grep -E '^Ran ' | head -1)"
else
  rojo "tests en rojo"; echo "$SALIDA" | tail -15 | sed 's/^/     /'
fi

echo "── 2. Alcance${TAREA:+ (tarea $TAREA)}"
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
  # El alcance sale del archivo de la tarea, no de reglas escritas acá: una regla a mano
  # queda vieja en cuanto el plan crece.
  PERMITIDOS="$(sed -n 's/^\*\*Archivos que podés tocar:\*\* *//p' "tareas/${TAREA:-}"-*.md 2>/dev/null \
                | tr ',' '\n' | grep -oE '[A-Za-z0-9_./-]+\.[A-Za-z0-9]+' | sort -u)"
  if [ -n "${TAREA:-}" ] && [ -z "$PERMITIDOS" ]; then
    rojo "la tarea $TAREA no declara \"Archivos que podés tocar\": sin alcance no hay gate"
  elif [ -z "${TAREA:-}" ]; then
    verde "sin límite de alcance declarado (modo integración)"
  else
    FUERA=""
    while read -r archivo; do
      [ -n "$archivo" ] || continue
      # Por ruta y no por nombre: permitir 'cosa.py' no habilita 'tests/cosa.py'.
      ok=""
      while read -r permitido; do
        [ -n "$permitido" ] || continue
        { [ "$archivo" = "$permitido" ] || [ "$archivo" = "$CODIGO/$permitido" ]; } && ok=1
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
# ADAPTAR: lo generado por tu stack y las dependencias que no querés ver aparecer.
if echo "$CAMBIADOS" | grep -qE '__pycache__|\.pyc$|node_modules/|dist/'; then rojo "hay archivos generados en el diff"; else verde "sin archivos generados"; fi
# Apagar una señal es más barato que arreglar la causa, y no deja rastro en los tests.
SUP="$(grep -rnE '# *(noqa|type: *ignore)|except[^:]*: *pass|@ *unittest\.skip|\.skip\(|\|\| *true|eslint-disable' "$CODIGO" 2>/dev/null || true)"
if [ -n "$SUP" ]; then rojo "hay señales suprimidas:"; echo "$SUP" | head -3 | sed 's/^/     /'; else verde "sin señales suprimidas"; fi
if grep -rn "TODO" "$CODIGO" 2>/dev/null | grep -q .; then rojo "quedaron TODO sueltos en $CODIGO/"; else verde "sin TODO sueltos"; fi

# ── 4. ¿Los tests distinguen? (sólo en modo tarea)
# Revierte la implementación y exige que la suite FALLE. Un test que pasa con el código
# viejo no prueba nada, y no hay otra forma de que el gate lo detecte.
if [ -n "${TAREA:-}" ]; then
  echo "── 4. ¿Los tests distinguen?"
  IMPL="$(echo "$CAMBIADOS" | grep -E "^$CODIGO/" || true)"
  TMP="$(mktemp -d)"; REVERTIDOS=""
  PREFIJO="$(git rev-parse --show-prefix)"   # vacío si el proyecto es la raíz del repo
  for f in $IMPL; do
    # `git cat-file` resuelve rutas desde la raíz del repo: sin el prefijo, todo archivo
    # parecía "nuevo" y este paso daba VERDE sin revertir nada.
    if git cat-file -e "HEAD:${PREFIJO}$f" 2>/dev/null; then
      cp "$f" "$TMP/$(echo "$f" | tr / _)"
      git checkout HEAD -- "$f" && REVERTIDOS="$REVERTIDOS $f"
    fi
  done
  if [ -z "$IMPL" ]; then verde "no hay implementación nueva que revertir"
  elif [ -z "$REVERTIDOS" ]; then verde "archivos nuevos (no existían en HEAD): nada que revertir"
  else
    # Qué tests tienen que fallar, no sólo que "algo" falle. La tarea nombra su archivo y
    # su clase; medido, la tasa agregada casi no se mueve ante una regresión mientras las
    # métricas por porción caen 25 a 91 puntos. "La suite falla" puede ser otro test.
    ESPERADO="$(sed -n 's/.*`\(tests\/[A-Za-z0-9_.]*\)`.*clase `\([A-Za-z0-9_]*\)`.*/\1 \2/p' \
                 "tareas/${TAREA}"-*.md 2>/dev/null | head -1)"
    if $TESTS >/dev/null 2>&1; then
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
# Los pasos 0 a 4 miran UNA tarea. Ninguno puede ver que diez diffs correctos por separado
# dejaron la arquitectura peor: eso sólo se ve mirando el conjunto. Copiá
# plantillas/_arquitectura.py y declará tus capas.
if [ -z "${TAREA:-}" ] && [ -f scripts/_arquitectura.py ]; then
  echo "── 5. Coherencia"
  if OUT="$(python3 scripts/_arquitectura.py 2>&1)"; then echo "$OUT"
  else echo "$OUT"; FALLOS=$((FALLOS+1)); fi
fi

# ── 6. La suite reservada (sólo en modo integración)
# Tests escritos por una persona que NINGÚN agente ve: viven fuera del directorio del
# proyecto, así que OpenCode los rechaza por `external_directory` desde cualquier worktree.
# No se nombran en el plan ni en las tareas.
#
# Por qué: los gates de tarea verifican lo que los tests de la tarea cubren, y el agente
# optimiza contra eso. Medido, la brecha de reward hacking crece ~27 puntos por cada 10× de
# tamaño de código, y los puntajes de validación se saturan mientras los reservados
# divergen — peor en modelos chicos. Es el único gate que mide lo que el agente no pudo
# haber optimizado.
#
# Y medido también: "leer los tests reservados" es el hack MÁS común. Por eso van afuera y
# no sólo sin documentar.
if [ -z "${TAREA:-}" ]; then
  # Fuera del repo, no sólo fuera del proyecto: así no viaja en los worktrees ni se
  # commitea por accidente, y OpenCode la rechaza por external_directory.
  RESERVADOS="${RESERVADOS:-$(cd "$(git rev-parse --show-toplevel)/.." && pwd)/reservados-$(basename "$PWD")}"
  echo "── 6. Suite reservada"
  if [ -d "$RESERVADOS" ] && ls "$RESERVADOS"/test_*.py >/dev/null 2>&1; then
    if OUT="$(PYTHONPATH="$PWD" python3 -m unittest discover -s "$RESERVADOS" -t "$RESERVADOS" -q 2>&1)"; then
      verde "$(echo "$OUT" | grep -E '^Ran ' | head -1) de composición"
    else
      rojo "la suite reservada falla: pasa los tests de las tareas y no hace lo que tiene que hacer"
      echo "$OUT" | tail -15 | sed 's/^/     /'
    fi
  else
    echo "  · no hay suite reservada en $RESERVADOS"
    echo "    Es el gate que mide lo que el agente no pudo optimizar. Escribila: tests de"
    echo "    composición, invariantes de punta a punta, fuera del repo para que no la vea."
  fi
fi

echo
if [ "$FALLOS" -eq 0 ]; then echo "GATE VERDE"; exit 0; else echo "GATE ROJO ($FALLOS fallo/s)"; exit 1; fi
