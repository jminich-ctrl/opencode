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
echo "▶ desplegando a $DESTINO"
# ADAPTAR: rsync + systemctl, docker compose up, kubectl apply, lo que uses.
# Tiene que ser idempotente: correrlo dos veces no puede romper nada.

# ── 4. Verificar que quedó arriba
echo "▶ verificando"
# ADAPTAR: el smoke contra el destino, no contra tu máquina.
if bash scripts/smoke.sh; then
  echo "✓ $DESTINO responde"
else
  echo "✗ $DESTINO NO responde — revertí ya: volver a $ANTERIOR"
  exit 1
fi

echo
echo "✓ desplegado en $DESTINO"
[ "$DESTINO" = "staging" ] && echo "  probalo a mano antes de ir a producción."
echo "  qué mirar ahora: <ADAPTAR: errores, latencia, la métrica que importe>"
echo "  si algo va mal: volver a $ANTERIOR"
