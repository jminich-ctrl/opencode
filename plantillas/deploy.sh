#!/usr/bin/env bash
# G5 — deploy. Copiala a tu proyecto como scripts/deploy.sh y adaptá lo marcado ADAPTAR.
#
#   bash scripts/deploy.sh staging      ← esto lo puede correr el agente
#   bash scripts/deploy.sh produccion   ← esto lo corre una persona, a mano
#
# El orden no es negociable: un solo artefacto, staging primero, humano en el medio,
# y la reversa lista antes de tocar producción.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
DESTINO="${1:-}"
ARTEFACTO="${ARTEFACTO:-.artefactos/$(git rev-parse --short HEAD).tar.gz}"

case "$DESTINO" in
  staging|produccion) ;;
  *) echo "uso: $0 staging|produccion" >&2; exit 1;;
esac

# ── 0. Nadie despliega sin G4 verde
if ! bash scripts/pre-deploy.sh >/dev/null 2>&1; then
  echo "✗ el pre-deploy (G4) está en rojo. Corré 'bash scripts/pre-deploy.sh' y arreglá eso primero."
  exit 1
fi
echo "✓ G4 verde"

# ── 1. Un solo artefacto: lo que se prueba en staging es lo que va a producción
if [ ! -f "$ARTEFACTO" ]; then
  echo "▶ construyendo $ARTEFACTO"
  mkdir -p "$(dirname "$ARTEFACTO")"
  # ADAPTAR: tu build real (docker build, npm run build, python -m build…)
  git archive --format=tar.gz -o "$ARTEFACTO" HEAD
fi
echo "✓ artefacto $(basename "$ARTEFACTO") ($(git rev-parse --short HEAD))"

# ── 2. La reversa, ANTES de desplegar
# ADAPTAR: cómo se vuelve atrás en tu stack (la versión anterior, el tag previo, el
# artefacto que está corriendo hoy). Si no podés contestar esto, no despliegues.
ANTERIOR="$(git rev-parse --short HEAD~1)"
echo "✓ reversa: volver a $ANTERIOR  ·  'bash scripts/deploy.sh $DESTINO' con ARTEFACTO del commit anterior"

if [ "$DESTINO" = "produccion" ]; then
  echo
  echo "── Esto va a PRODUCCIÓN. Antes de seguir, respondé:"
  echo "   · ¿qué cambia para el usuario?"
  echo "   · ¿qué puede romper, y cómo te darías cuenta?"
  echo "   · ¿la reversa está probada, o solo escrita?"
  echo "   · ¿hay migraciones? ¿el código viejo sigue andando con el esquema nuevo?"
  echo
  # Nunca automático: G5 es el único gate que exige una persona. Todo lo anterior
  # es reversible; esto toca usuarios y datos.
  read -r -p "Escribí 'desplegar' para continuar: " RESPUESTA
  [ "$RESPUESTA" = "desplegar" ] || { echo "cancelado"; exit 1; }
fi

# ── 3. Desplegar
# ADAPTAR: el comando que despliega de verdad —rsync + systemctl, docker compose up,
# kubectl apply, lo que uses—. Tiene que ser IDEMPOTENTE: correrlo dos veces no puede romper
# nada. `$DESTINO` vale `staging` o `produccion`.
#
# Vacío a propósito, y por eso este script NO puede decir que desplegó: tal como venía, el
# paso 3 eran dos comentarios y el final imprimía «✓ desplegado en staging» sin haber
# desplegado nada. Es el defecto que este método persigue desde la primera línea —un paso que
# no hizo nada informando éxito— y estaba en el único gate que toca usuarios y datos.
COMANDO_DEPLOY=""

echo "▶ desplegando a $DESTINO"
if [ -z "$COMANDO_DEPLOY" ]; then
  echo "✗ no hay comando de deploy configurado (COMANDO_DEPLOY en scripts/deploy.sh):"
  echo "   no desplegué nada, y no puedo decir que sí. Adaptá el paso 3."
  exit 1
fi
if ! "$SHELL" -c "$COMANDO_DEPLOY"; then
  echo "✗ el comando de deploy falló — revertí ya: volver a $ANTERIOR"
  exit 1
fi

# ── 4. Verificar que quedó arriba
echo "▶ verificando"
# ADAPTAR: el smoke contra el destino, no contra tu máquina.
# Los códigos del smoke son contrato y los leen DOS: G4 y esto. El 3 —«el proyecto declara
# que no tiene nada que levantar», con su motivo— no es una falla: mandar a revertir por un
# vacío declarado enseña a desconfiar del paso que verifica. Medido el 2026-10-26: le agregué
# el 3 al contrato, actualicé G4 y no esto, y el deploy de una librería terminaba en «✗
# staging NO responde — revertí ya» sobre un deploy que había ido bien.
SAL_SMOKE_G5="$(bash scripts/smoke.sh 2>&1)"; RC_SMOKE_G5=$?
printf '%s\n' "$SAL_SMOKE_G5" | grep . | sed 's/^/  /'
case "$RC_SMOKE_G5" in
  0) echo "✓ $DESTINO responde" ;;
  3) echo "⊘ no verifiqué que $DESTINO responda: el proyecto declara que no hay nada que levantar" ;;
  *) echo "✗ $DESTINO NO responde — revertí ya: volver a $ANTERIOR"
     exit 1 ;;
esac

echo
echo "✓ desplegado en $DESTINO"
[ "$DESTINO" = "staging" ] && echo "  probalo a mano antes de ir a producción."
echo "  qué mirar ahora: <ADAPTAR: errores, latencia, la métrica que importe>"
echo "  si algo va mal: volver a $ANTERIOR"
