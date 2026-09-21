#!/usr/bin/env bash
# Guarda la API key de ColabHive en ~/.config/colabhive/env (chmod 600),
# la carga automáticamente en bash/zsh y valida contra la API.
#
# Uso (desde la raíz del repo):  bash colabhive/scripts/set-api-key.sh
# Correr en una terminal propia (no pegar la key en el chat).
set -euo pipefail

ENV_DIR="$HOME/.config/colabhive"
ENV_FILE="$ENV_DIR/env"
BASE_URL="https://api.colabhive.com/v1"
SOURCE_LINE='[ -f "$HOME/.config/colabhive/env" ] && . "$HOME/.config/colabhive/env"'

printf "Pegá tu API key de ColabHive (no se muestra): "
IFS= read -r -s KEY
echo
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"

if [ -z "$KEY" ]; then
  echo "✗ Key vacía, no se guardó nada." >&2
  exit 1
fi
case "$KEY" in
  hive_*) ;;
  *) echo "⚠ La key no empieza con 'hive_'. Se guarda igual, revisá si es la correcta." ;;
esac

# Validar antes de guardar (la key va por stdin, no queda en la lista de procesos)
echo "→ Validando contra $BASE_URL/models ..."
BODY="$(mktemp)"
trap 'rm -f "$BODY"' EXIT
HTTP_CODE="$(printf 'Authorization: Bearer %s\n' "$KEY" \
  | curl -sS -m 30 -o "$BODY" -w '%{http_code}' -H @- "$BASE_URL/models" || echo "000")"

case "$HTTP_CODE" in
  200)
    COUNT="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d.get("data", [])))' "$BODY" 2>/dev/null || echo "?")"
    echo "✓ Key válida. Modelos de chat visibles: $COUNT"
    ;;
  401|403)
    echo "✗ La API rechazó la key (HTTP $HTTP_CODE). No se guardó." >&2
    exit 1
    ;;
  *)
    echo "⚠ No se pudo validar (HTTP $HTTP_CODE). Se guarda igual; revisá conexión/VPN y volvé a correr el script." ;;
esac

# Guardar con permisos restrictivos
mkdir -p "$ENV_DIR"
chmod 700 "$ENV_DIR"
umask 077
cat > "$ENV_FILE" <<EOF
# ColabHive — generado por set-api-key.sh ($(date +%Y-%m-%d))
export COLABHIVE_API_KEY='$KEY'
export COLABHIVE_BASE_URL='$BASE_URL'
export COLABHIVE_BUILDER_URL='https://api.colabhive.com/api/builder/v1'
EOF
chmod 600 "$ENV_FILE"
echo "✓ Guardada en $ENV_FILE (chmod 600)"

# Cargar automáticamente en shells nuevos
for RC in "$HOME/.bash_profile" "$HOME/.zshrc"; do
  [ -f "$RC" ] || continue
  if ! grep -qF '.config/colabhive/env' "$RC"; then
    printf '\n# ColabHive API key\n%s\n' "$SOURCE_LINE" >> "$RC"
    echo "✓ Agregado a $(basename "$RC")"
  else
    echo "• $(basename "$RC") ya la cargaba"
  fi
done

echo
echo "Listo. Para usarla en esta terminal:  source $ENV_FILE"
