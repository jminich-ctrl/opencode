#!/usr/bin/env python3
"""Normaliza la respuesta de un modelo: saca el bloque de razonamiento y las cercas.

    python3 limpiar.py <archivo>                  → el cuerpo, sin `<think>` ni cercas
    python3 limpiar.py --ultima-linea <archivo>   → la última línea no vacía

Existe porque el 2026-10-23 el ejecutor devolvió un archivo de test correcto envuelto en
```python a pesar de que el prompt decía «sin bloques de markdown», y el chequeo lo informó
como «✗ sintaxis: invalid syntax (line 1)». El contenido estaba bien; el extractor no. Pedir
un formato no garantiza el formato: hay que normalizar lo que llega.

El modo `--ultima-linea` estaba copiado adentro de `enjambre.sh` y de `conversar.sh` como
python incrustado. Vive acá porque es UNA regla —«dónde termina el razonamiento y empieza la
respuesta»— con varios lectores, y una regla copiada en tres lados es una regla que va a
divergir: la forma que este repo repite y que hoy ya costó dos defectos.
"""
import re, sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
ultima = "--ultima-linea" in sys.argv
t = open(args[0]).read() if args else sys.stdin.read()

# El razonamiento, si lo hay. Lo que importa es lo que viene DESPUÉS del cierre: un modelo
# que piensa en voz alta deja su conclusión al final, y tomar el principio es tomar la duda.
if "</think>" in t:
    t = t.split("</think>")[-1]

# Cercas con o sin lenguaje, en cualquier parte del texto.
m = re.search(r"```[a-zA-Z0-9_-]*\n(.*?)```", t, re.S)
if m:
    t = m.group(1)
else:
    t = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*$", "", t, flags=re.M)
t = t.strip()

# La última línea se toma del texto YA normalizado, no del crudo. La copia incrustada en
# `enjambre.sh` lo hacía sobre el crudo, así que para una respuesta en cercas devolvía
# «```» —la cerca de cierre— y la tabla del enjambre mostraba eso como la respuesta del
# modelo. Un extractor que no acuerda con el formato de su fuente, por tercera vez.
if ultima:
    lineas = [l.strip() for l in t.splitlines() if l.strip()]
    sys.stdout.write((lineas[-1] if lineas else "(vacío)") + "\n")
    raise SystemExit(0)

sys.stdout.write(t + "\n")
