#!/usr/bin/env bash
# ¿El corredor de ESTE proyecto cumple el contrato de códigos de `scripts/correr-suite.sh`?
#
#   bash _corredor.sh        # desde la raíz del proyecto
#   0 cumple · 1 no cumple, y dice en qué · 2 no pude probar
#
# POR QUÉ EXISTE. `correr-suite.sh` es el cimiento de todos los veredictos por tarea: el
# paso 1 lo usa para juzgar la suite y el paso 4 para preguntar si los tests DE LA TAREA
# distinguen. El contrato de códigos es el que separa «verifiqué y pasó» de «no corrí
# ningún test». Y es la pieza que cada proyecto escribe a mano: la plantilla lo cumple para
# `unittest`, y cualquier otro stack la reimplementa.
#
# Medido el 2026-10-26, armando un proyecto JS de cero para ver si el método es replicable a
# otro stack. Adaptando la única función que el documento manda adaptar, la escribí mal de
# dos maneras, con el contrato delante:
#
#   · `node --test --test-name-pattern X` con un patrón que no casa ningún test devuelve 0 e
#     informa `# pass 0 / # skipped 2`. El corredor lo pasó como VERDE, y el paso 4 del gate
#     concluyó «la suite falla, pero NO por los tests de esta tarea (saldo pasa con el código
#     viejo)»: un diagnóstico falso, seguro y rotundo, sobre un test que nunca corrió;
#   · con un selector que no existe devolvió 1 —«los tests fallan»— donde el contrato pide 2.
#
# La sonda es la de MEDICION.md §1: una corrida de control cuyo resultado esperado se conoce
# y es distinto del nulo. Acá el control es un selector que NO PUEDE existir en ningún stack.
set -uo pipefail

[ -f scripts/correr-suite.sh ] || {
  echo "  ⊘ no hay scripts/correr-suite.sh: no puedo probar el contrato del corredor"
  exit 2
}

IMPOSIBLE="tests/__corredor_no_existe_$$__::__NadaQueExista__"
bash scripts/correr-suite.sh "$IMPOSIBLE" >/dev/null 2>&1; RC=$?

case "$RC" in
  2|3) exit 0 ;;   # 2 "no corrió ningún test", 3 "falta el corredor": las dos son honestas
  0)
    echo "  ✗ el corredor de este proyecto informa VERDE (0) un selector que no existe."
    echo "     Entonces «no corrí ningún test» y «los tests pasan» salen iguales, y el paso 4"
    echo "     del gate afirma que los tests de la tarea no distinguen cuando nunca corrieron."
    echo "     Arreglá \`correr_suite\` en scripts/correr-suite.sh: devolver 9 cuando no corre"
    echo "     ninguno. Probado con: $IMPOSIBLE"
    exit 1 ;;
  1)
    echo "  ✗ el corredor de este proyecto informa ROJO (1) un selector que no existe."
    echo "     Eso pinta de defecto del código algo que es «no pude preguntar», y manda a"
    echo "     buscar un bug que no está. El contrato pide 2. Probado con: $IMPOSIBLE"
    exit 1 ;;
  *)
    echo "  ⊘ el corredor devolvió $RC ante un selector inexistente, que no está en el"
    echo "     contrato (0,1,2,3). No pudo verificarse. Probado con: $IMPOSIBLE"
    exit 2 ;;
esac
