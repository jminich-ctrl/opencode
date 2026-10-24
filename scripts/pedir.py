#!/usr/bin/env python3
"""Pide una corrección de enunciado SIN el arnés de opencode: ni memoria, ni sesión, ni
herramientas. Sólo un POST a /chat/completions y la respuesta de texto.

La razón: siete corridas del arnés murieron con `memory_session_expired` a los 7-8 minutos
para corregir UNA palabra en un archivo. Para eso no hace falta una sesión con memoria."""
import json, os, sys, urllib.request

base = os.environ["COLABHIVE_BASE_URL"]
clave = os.environ["COLABHIVE_API_KEY"]
modelo, prompt = sys.argv[1], sys.stdin.read()
cuerpo = json.dumps({"model": modelo, "max_tokens": 400,
                     "messages": [{"role": "user", "content": prompt}]}).encode()
pedido = urllib.request.Request(base + "/chat/completions", data=cuerpo, headers={
    "Authorization": "Bearer " + clave, "Content-Type": "application/json"})
try:
    # La paciencia por ENV y con 400s por omisión, no 180. El método ya tiene medido que un
    # modelo desalojado tarda 253s en levantarse y que el POST es lo que lo arranca: con 180
    # el pedido muere justo antes de que termine de cargar, y el que lee la tabla concluye
    # "este modelo no responde" cuando lo que pasó es que no lo esperamos. Es el mismo error
    # que la sonda de 45s contra un arranque de 91-106s, que ya nos costó tres lanzamientos.
    with urllib.request.urlopen(pedido, timeout=int(os.environ.get("PACIENCIA", "400"))) as r:
        d = json.load(r)
    print(d["choices"][0]["message"]["content"].strip())
except Exception as e:
    print("ERROR:", e, file=sys.stderr); raise SystemExit(1)
