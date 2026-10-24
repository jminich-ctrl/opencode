#!/usr/bin/env python3
"""Pide una corrección de enunciado SIN el arnés de opencode: ni memoria, ni sesión, ni
herramientas. Sólo un POST a /chat/completions y la respuesta de texto.

La razón: siete corridas del arnés murieron con `memory_session_expired` a los 7-8 minutos
para corregir UNA palabra en un archivo. Para eso no hace falta una sesión con memoria."""
import json, os, sys, urllib.request

base = os.environ["COLABHIVE_BASE_URL"]
clave = os.environ["COLABHIVE_API_KEY"]
modelo, prompt = sys.argv[1], sys.stdin.read()
# TEMPERATURA 0 por omisión, y por qué importa más de lo que parece.
#
# Medido el 2026-10-24 contra el ejecutor: sin mandar `temperature`, cinco llamadas al MISMO
# prompt dieron dos respuestas distintas —`cantidad_de_avisos` tres veces y
# `cantidad_avisos` dos—. Con `temperature: 0`, las cinco idénticas. O sea que la plataforma
# no usa greedy por omisión y veníamos corriendo con un valor que nadie eligió.
#
# Lo que eso rompe no es sólo el acierto —Udgam Labs midió que pasar de greedy a 0,7 le bajó
# el acierto de llamadas a herramientas de 60% a 46%— sino EL BRAZO DE CONTROL, que es el
# instrumento con el que este método decide si un resultado se le puede atribuir a un modelo.
# `comparar-modelos.sh` dice «el control no se movió: salidas idénticas carácter por carácter
# en dos tandas separadas por horas». Con temperatura no nula, eso era suerte.
#
# Se deja como perilla y no clavada porque hay un caso donde la diversidad es el punto: el
# best-of-N con verificador. Lilavati, de 95M, pasa de 54,7% en un intento a 72,3% con 48
# intentos y un verificador ponderando los votos, y 48 intentos a temperatura 0 son el mismo
# intento 48 veces. Determinismo para medir, diversidad para buscar — y nunca sin saber cuál
# de los dos se está usando.
TEMPERATURA = float(os.environ.get("TEMPERATURA", "0"))
cuerpo = json.dumps({"model": modelo, "max_tokens": 400,
                     "temperature": TEMPERATURA,
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
