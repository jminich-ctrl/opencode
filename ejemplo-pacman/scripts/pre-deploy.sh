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
# El pathspec va en TODOS los `git diff` de este script, no sólo en el de dependencias. Sin
# él el diff barre el repo ENTERO: corriendo G4 del pacman entraban los archivos del método,
# y sus fixtures de test están llenos de la palabra «password» a propósito.
BASE="${1:-origin/main}"
git rev-parse --verify -q "$BASE" >/dev/null || BASE="$(git rev-parse HEAD~1 2>/dev/null || echo HEAD)"

FALLOS=0
VACIOS_G4=0
rojo()  { echo "  ✗ $1"; FALLOS=$((FALLOS+1)); }
verde() { echo "  ✓ $1"; }
aviso() { echo "  · $1"; }
# Lo que miró, con nombre: sin esto «pasó» y «no miré» se imprimen igual.
testigo_g4() { echo "     · inspeccionó: $1"; }

# Las herramientas que PROVEE el método no son código del proyecto, y G4 las estaba leyendo
# como si lo fueran. Medido el 2026-10-26: copiar `pre-deploy.sh` al proyecto y correrlo
# informaba «✗ variables usadas y no documentadas: MYSQL_PASSWORD» —la variable está en un
# COMENTARIO de este mismo archivo, el que explica por qué `os.environ.get('MYSQL_PASSWORD')`
# NO es un secreto— y el paso de secretos citaba sus propios párrafos. G4 leyéndose a sí
# mismo, y bloqueando el deploy de un proyecto que no tiene base de datos.
#
# Se excluyen por nombre y se DICE cuáles: un archivo que no se inspecciona y no se nombra es
# un agujero. Lo que el proyecto escribe —incluido `smoke.sh`— se sigue inspeccionando.
DEL_METODO='^(scripts/(gate|pre-deploy|deploy|correr-suite)\.sh|scripts/_[a-z_]+\.(py|sh))$'
# Y el mismo criterio para los diffs que leen CONTENIDO (secretos, variables de entorno): sin
# esto, los pasos 1 y 4 seguían citando los comentarios de este archivo aunque la lista de
# nombres ya estuviera filtrada. Un pathspec negativo de git, uno por herramienta del método.
EXCLUIR_METODO=(":(exclude)*/scripts/gate.sh" ":(exclude)scripts/gate.sh"
                ":(exclude)*/scripts/pre-deploy.sh" ":(exclude)scripts/pre-deploy.sh"
                ":(exclude)*/scripts/deploy.sh" ":(exclude)scripts/deploy.sh"
                ":(exclude)*/scripts/correr-suite.sh" ":(exclude)scripts/correr-suite.sh"
                ":(exclude)*/scripts/_*.py" ":(exclude)scripts/_*.py"
                ":(exclude)*/scripts/_*.sh" ":(exclude)scripts/_*.sh")
DIFF_CRUDO="$(git diff --name-only "$BASE"...HEAD ${PREFIJO:+-- "$RAIZ/$PREFIJO"} 2>/dev/null)"
DIFF="$(printf '%s\n' "$DIFF_CRUDO" | grep -vE "$DEL_METODO" || true)"
SALTEADAS_G4="$(printf '%s\n' "$DIFF_CRUDO" | grep -E "$DEL_METODO" | tr '\n' ' ' || true)"
[ -n "${SALTEADAS_G4// /}" ] && aviso "no se inspeccionan (las provee el método): $SALTEADAS_G4"
[ -n "$DIFF" ] || aviso "sin cambios contra $BASE"

echo "── 1. Secretos"
# Un secreto commiteado ya está filtrado aunque lo borres en el commit siguiente:
# hay que rotarlo. Por eso esto es rojo, no aviso.
# Dos niveles, y el rojo pide un LITERAL. `[^a-z]{0,3}[:=]` aceptaba cero caracteres antes
# del `:`, así que `password: str` matcheaba: medido, 21 líneas del proyecto de ejemplo, todas
# anotaciones de tipo, campos de Pydantic, un `useState` y hasta
# `'password': os.environ.get('MYSQL_PASSWORD', '')`, que es lo CONTRARIO de un secreto
# commiteado. El commit que integra el auth del ejemplo ponía G4 en rojo y el deploy no
# arrancaba. Un chequeo que reprueba el código que anda se aprende a esquivar.
#
# NOMBRE + separador + literal entre comillas de 6 o más = rojo. Y las líneas que leen del
# entorno quedan afuera por nombre: son la forma correcta, no la sospechosa.
NOMBRE='(api[_-]?key|secret|password|passwd|token)'
PATRON="${NOMBRE}[^a-z]{0,3}[:=] *['\"][^'\"]{6,}['\"]|BEGIN [A-Z ]*PRIVATE KEY"
DEL_ENTORNO='environ|getenv|process\.env|import\.meta\.env'
# Y el literal que CONTIENE el nombre del campo es un fixture de test, no un secreto:
# `'password': 'password'`, `'wrongpassword'`, `"mocked-token-for-user-"`. Eran los últimos
# cinco falsos positivos de los 17 que el patrón viejo daba sobre el código del ejemplo.
# El compromiso, dicho: un secreto cuyo valor lleve la palabra adentro se escapa del rojo y
# cae en el aviso de abajo. No es un agujero callado, es un caso que queda a la vista.
TRIVIAL="${NOMBRE}[^a-z]{0,3}[:=] *['\"][^'\"]*${NOMBRE}"
# El patrón flojo no desaparece: lo que antes era rojo ahora es AVISO, así que un secreto sin
# comillas se sigue viendo y nadie lo descubre tarde por un acote nuestro.
PATRON_FLOJO="${NOMBRE}[^a-z]{0,3}[:=][^=]"
AGREGADAS="$(git diff "$BASE"...HEAD -U0 ${PREFIJO:+-- "$RAIZ/$PREFIJO"} "${EXCLUIR_METODO[@]}" 2>/dev/null | grep -iE '^\+' | grep -viE "$DEL_ENTORNO" || true)"
SOSPECHOSAS="$(printf '%s\n' "$AGREGADAS" | grep -iE "$PATRON" | grep -viE "$TRIVIAL" || true)"
if [ -n "$SOSPECHOSAS" ]; then
  rojo "hay algo que parece un secreto en el diff"
  printf '%s\n' "$SOSPECHOSAS" | head -3 | sed 's/^/     /'
  echo "     si es real: rotalo, no alcanza con borrarlo del próximo commit"
else
  verde "sin secretos evidentes en el diff"
  # El patrón flojo, como aviso: acá entra el secreto sin comillas, que el rojo no pide.
  FLOJAS="$(printf '%s\n' "$AGREGADAS" | grep -iE "$PATRON_FLOJO" | head -3 || true)"
  if [ -n "$FLOJAS" ]; then
    echo "     · nombres sospechosos sin literal (anotaciones de tipo, campos, lecturas del"
    echo "       entorno: casi siempre legítimos). Mirá si alguno lleva un valor de verdad:"
    printf '%s\n' "$FLOJAS" | sed 's/^/       /'
  fi
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
USADAS="$(git diff "$BASE"...HEAD -U0 ${PREFIJO:+-- "$RAIZ/$PREFIJO"} "${EXCLUIR_METODO[@]}" | grep -E '^\+' \
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
if [ -x scripts/smoke.sh ] || [ -f scripts/smoke.sh ]; then
  SAL_SMOKE="$(bash scripts/smoke.sh 2>&1)"; RC_SMOKE=$?
  printf '%s\n' "$SAL_SMOKE" | grep . | sed 's/^/  /'
  case "$RC_SMOKE" in
    0) verde "la aplicación arranca" ;;
    # 3 = el proyecto DECLARA que no tiene nada que levantar, con su motivo. No es un pase
    # silencioso: queda impreso, se cuenta como vacío y el veredicto lo dice. Sin esto, una
    # librería no podía pasar G4 de ninguna forma honesta.
    3) VACIOS_G4=$((VACIOS_G4+1)) ;;
    *) rojo "la aplicación NO arranca" ;;
  esac
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
  # Con `scripts/correr-suite.sh` y sus códigos de contrato, no con una invocación propia:
  # tener dos formas de correr la suite produce un diagnóstico falso que se informa como
  # defecto del proyecto. Medido en un proyecto JS el 2026-10-26.
  if [ ! -f "$LIMPIO/repo/${PREFIJO:-.}/scripts/correr-suite.sh" ]; then
    rojo "lo commiteado no incluye scripts/correr-suite.sh: no sé cómo correr la suite"
  else
    # El clon no tiene entorno: `.venv`, `node_modules`, `.mysql` y `.entorno` están
    # gitignorados —y tienen que estarlo—, así que el corredor devuelve 3 («falta el
    # corredor») y este paso queda en ROJO PERMANENTE para todo proyecto con dependencias.
    # Medido el 2026-10-26 la primera vez que clasificados corrió su G4. Así es como un paso
    # imposible termina borrado, y éste es el único que mira lo COMMITEADO.
    #
    # Se ENLAZA, no se instala: es instantáneo, y lo que este paso verifica es el código, no
    # la instalación. Es lo mismo que el runner hace al crear un worktree —«enlazado .venv al
    # tronco»— y por el mismo motivo.
    for dep in .venv .entorno .mysql node_modules backend/node_modules frontend/node_modules; do
      [ -e "$dep" ] || continue
      [ -e "$LIMPIO/repo/${PREFIJO:-.}/$dep" ] && continue
      mkdir -p "$(dirname "$LIMPIO/repo/${PREFIJO:-.}/$dep")" 2>/dev/null
      ln -s "$PWD/$dep" "$LIMPIO/repo/${PREFIJO:-.}/$dep" 2>/dev/null \
        && ENLAZADOS="${ENLAZADOS:-}${ENLAZADOS:+ }$dep"
    done
    [ -n "${ENLAZADOS:-}" ] && testigo_g4 "entorno enlazado al tronco: $ENLAZADOS"
    ( cd "$LIMPIO/repo/${PREFIJO:-.}" && bash scripts/correr-suite.sh ) >"$LIMPIO/salida" 2>&1
    case $? in
      0) verde "la suite pasa sobre lo commiteado ($(grep -E '^Ran |^# pass ' "$LIMPIO/salida" | head -1))"
         testigo_g4 "scripts/correr-suite.sh del checkout limpio" ;;
      2) rojo "sobre lo commiteado la suite no corrió NINGÚN test: sin tests no hay deploy" ;;
      3) rojo "falta el corredor de tests en el checkout limpio — es del método, no del código" ;;
      *) # ¿De quién es el rojo? Si la suite YA está roja en el tronco, el clon falla por lo
         # mismo y «hay algo sin commitear que la sostiene» es un diagnóstico FALSO que manda
         # a buscar un archivo fantasma. Medido el 2026-10-26 en clasificados, cuyo tronco
         # tiene dos tests rojos de tareas escritas y no integradas.
         #
         # La segunda medición sólo se paga cuando hace falta —el clon falló— que es la misma
         # regla que `escribir-tests.sh` ya usa para preguntarle a la plataforma.
         if bash scripts/correr-suite.sh >"$LIMPIO/tronco" 2>&1; then
           rojo "la suite FALLA sobre un checkout limpio: hay algo sin commitear que la sostiene"
           tail -12 "$LIMPIO/salida" | sed 's/^/     /'
         else
           rojo "la suite ya está ROJA en el tronco: esto no mide lo commiteado"
           echo "     No es un archivo sin commitear: el rojo está a la vista en el árbol."
           # Con el extractor del proyecto y no con un `tail`: la salida de una suite de dos
           # mitades TERMINA con la que pasó, así que el tail mostraba el éxito del frontend
           # debajo de un ✗ por el backend. `--fallas` es el único que sabe leer este stack.
           bash scripts/correr-suite.sh --fallas 2>/dev/null | head -6 | sed 's/^/     → /'
         fi ;;
    esac
  fi
else
  rojo "no pude clonar el repo para verificar sobre lo commiteado"
fi
rm -rf "$LIMPIO"

echo
if [ "$FALLOS" -eq 0 ] && [ "$VACIOS_G4" -eq 0 ]; then echo "PRE-DEPLOY VERDE"; exit 0
elif [ "$FALLOS" -eq 0 ]; then
  echo "PRE-DEPLOY VERDE — con $VACIOS_G4 chequeo/s declarados sin material (⊘)"; exit 0
else echo "PRE-DEPLOY ROJO ($FALLOS fallo/s) — el deploy no arranca"; exit 1; fi
