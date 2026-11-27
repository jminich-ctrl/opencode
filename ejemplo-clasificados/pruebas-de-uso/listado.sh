#!/usr/bin/env bash
# `listado` — la lista de avisos. Lo que pide OBJETIVO.md: «un listado donde buscar».
. "$(dirname "$0")/_api.sh"
CODIGO="$(curl -s -o /tmp/listado.$$.out -w '%{http_code}' -m 5 "$URL/ads")"
CUERPO="$(cat /tmp/listado.$$.out 2>/dev/null)"; rm -f /tmp/listado.$$.out
if [ "$CODIGO" != "200" ]; then
  echo "GET /ads devolvió $CODIGO: la app está arriba y el listado no responde"
  echo "rutas que sí publica: $(curl -s -m 3 "$URL/openapi.json" | python3 -c 'import json,sys; print(" ".join(sorted(json.load(sys.stdin)["paths"])))' 2>/dev/null)"
  exit 1
fi
case "$CUERPO" in
  \[*) echo "GET /ads → 200 y devolvió una lista"; exit 0 ;;
  *) echo "GET /ads → 200 pero el cuerpo no es una lista: ${CUERPO:0:60}"; exit 1 ;;
esac
