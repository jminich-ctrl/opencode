#!/usr/bin/env python3
"""¿El plan cubre todo el encargo? La pregunta más cara de G0, como comando.

Es el error que más se repite y el único que no se ve leyendo el plan: una funcionalidad
que falta no está en ninguna línea. En el plan de clasificados faltaba un tercio del
alcance y el plan se leía bien; después de corregirlo faltaba el registro de usuarios, y
eso también se leía bien.

Para que sea mecánico, el encargo declara sus requisitos con una clave:

    ## Requisitos
    - `login` — cuentas con login por cookie de sesión
    - `favoritos` — marcar avisos como favoritos
    - `publicar|crud` — crear un aviso   (varias formas de nombrarlo, separadas por |)

Y esto verifica que cada clave aparezca en la tabla de tareas del plan. Los acentos y la ñ
no importan. La clave la escribe la persona **una vez**, cuando escribe el encargo, que es
algo que iba a escribir igual.

  ENCARGO=OBJETIVO.md PLAN=PLAN.md python3 scripts/cobertura.py
"""
import os
import pathlib
import re
import sys
import unicodedata


def normalizar(t):
    """Sin acentos y en minúsculas: 'búsqueda' y 'busqueda' son la misma palabra, y
    escribir la clave con acento correcto no debería ser parte del trabajo."""
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")

ENCARGO = pathlib.Path(os.environ.get("ENCARGO", "OBJETIVO.md"))
PLAN = pathlib.Path(os.environ.get("PLAN", "PLAN.md"))
for f in (ENCARGO, PLAN):
    if not f.exists():
        print(f"  ✗ no existe {f}")
        sys.exit(1)

encargo = ENCARGO.read_text()
m = re.search(r"^##+ *Requisitos *$(.*?)(?=^##+ |\Z)", encargo, re.M | re.S)
if not m:
    print(f"  · {ENCARGO.name} no tiene sección «## Requisitos» con claves: no se puede")
    print(f"    verificar la cobertura. Es la única parte de G0 que se puede mecanizar;")
    print(f"    sin ella queda entera en manos de quien lea el plan.")
    sys.exit(0)

requisitos = re.findall(r"^\s*[-*] *`([^`]+)`(.*)$", m.group(1), re.M)
if not requisitos:
    print(f"  · la sección «## Requisitos» de {ENCARGO.name} no tiene claves entre backticks")
    sys.exit(0)

# Sólo las filas de la tabla de tareas: título y archivos.
plan = PLAN.read_text()
filas = normalizar("\n".join(re.findall(r"^\|\s*T\d+\s*\|.*$", plan, re.M)))

faltan = []
for clave, texto in requisitos:
    # Raíz, no palabra exacta: 'favorito' matchea 'favoritos' y 'favorites'. Y con `|`
    # se declaran varias formas de nombrar lo mismo: alcanza con que una aparezca.
    if not any(normalizar(a) in filas for a in clave.split("|") if a.strip()):
        faltan.append((clave, texto.strip(" —-")))

print(f"  {len(requisitos)} requisito(s) declarados en {ENCARGO.name}")
if faltan:
    print(f"  ✗ {len(faltan)} sin ninguna tarea que los cubra:")
    for clave, texto in faltan:
        print(f"     {clave}  {texto[:60]}")
    sys.exit(1)
print("  ✓ todos tienen al menos una tarea")
