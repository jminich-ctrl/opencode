#!/usr/bin/env python3
"""Verifica lo que de un plan se puede verificar con un comando.

G0 lo firma una persona, pero **la mitad de lo que hay que mirar es mecánico** y una
persona leyendo rápido lo pasa por alto. Todo lo de acá salió de un defecto real del plan
de clasificados: filas duplicadas, archivos de tarea huérfanos, plantillas sin completar,
tareas sin alcance declarado.

Lo que NO verifica, y por eso G0 sigue siendo humano:
  · si el plan cubre todo el encargo (una funcionalidad que falta no está en ningún lado),
  · si las tareas están bien dimensionadas de verdad,
  · si inventó APIs que no existen.

  PLAN=PLAN.md python3 scripts/validar-plan.py
  PLAN=PLAN.md python3 scripts/validar-plan.py --arreglar   # y corrige lo mecánico

Con --arreglar hace lo que no requiere criterio: saca las filas repetidas de la tabla y
borra las líneas de etapa que no están en el formato exacto (mezclarlas es peor que no
tenerlas: las que no matchean desaparecen y sus tareas no se ejecutan). Los archivos
huérfanos los informa y no los borra: borrar es del humano.

Nace de haber hecho esas dos cosas a mano. Un método con mínima interacción humana no
puede pedirle a una persona que deduplique filas de una tabla.
"""
import os
import pathlib
import re
import sys

RAIZ = pathlib.Path(os.environ.get("PLAN", "PLAN.md")).resolve().parent
PLAN = pathlib.Path(os.environ.get("PLAN", "PLAN.md"))
if not PLAN.exists():
    print(f"✗ no existe {PLAN}")
    sys.exit(1)

ARREGLAR = "--arreglar" in sys.argv
texto = PLAN.read_text()
errores, avisos = [], []

if ARREGLAR:
    original = texto
    vistas, salida, quitadas = set(), [], 0
    for linea in texto.split("\n"):
        m = re.match(r"^\|\s*(T\d+)\s*\|.*\|\s*\S+\s*\|\s*$", linea)
        if m and len(linea.strip("|").split("|")) >= 4:
            if m.group(1) in vistas:
                quitadas += 1
                continue
            vistas.add(m.group(1))
        salida.append(linea)
    texto = "\n".join(salida)

    # Etapas que no están en el formato exacto: se borran todas, porque mezclar canónicas
    # con prosa hace desaparecer en silencio las que no matchean. Deducidas salen mejor.
    lineas_etapa = [l for l in texto.split("\n") if re.match(r"^ *\*{0,2}etapa +[0-9]", l, re.I)]
    canonicas = [l for l in lineas_etapa
                 if re.match(r"^ *\*{0,2}ETAPA +[0-9]+\*{0,2}:\*{0,2} *[T0-9 ]+ *$", l)]
    borradas = 0
    if lineas_etapa and len(canonicas) < len(lineas_etapa):
        texto = "\n".join(l for l in texto.split("\n") if l not in lineas_etapa)
        borradas = len(lineas_etapa)

    if texto != original:
        PLAN.write_text(texto)
        if quitadas:
            print(f"  · arreglado: {quitadas} fila(s) repetida(s) quitada(s) de la tabla")
        if borradas:
            print(f"  · arreglado: {borradas} línea(s) de etapa en formato incorrecto "
                  f"borradas; se deducen de la tabla")

# ── La tabla de tareas: la primera tabla cuyas filas tienen 5 columnas.
filas = []
for linea in re.findall(r"^\|\s*(T\d+)\s*\|(.*)$", texto, re.M):
    celdas = [c.strip() for c in linea[1].strip("|").split("|")]
    if len(celdas) >= 4:
        filas.append((linea[0], celdas))

if not filas:
    print("✗ el plan no tiene tabla de tareas con columnas | # | Tarea | Depende de | Archivos | Estado |")
    sys.exit(1)

tareas, duplicadas = {}, []
for tid, celdas in filas:
    if tid in tareas:
        duplicadas.append(tid)
        continue
    tareas[tid] = {"titulo": celdas[0], "deps": set(re.findall(r"T\d+", celdas[1])) - {tid},
                   "archivos": celdas[2]}
if duplicadas:
    errores.append(f"filas repetidas en la tabla: {' '.join(sorted(set(duplicadas)))}")

# ── Dependencias que apuntan a tareas que no existen
for tid, t in tareas.items():
    faltan = t["deps"] - set(tareas)
    if faltan:
        errores.append(f"{tid} depende de tareas que no están en la tabla: {' '.join(sorted(faltan))}")

# ── Plan y archivos de tarea tienen que coincidir en los dos sentidos
dir_tareas = RAIZ / "tareas"
en_disco = {}
if dir_tareas.is_dir():
    for f in sorted(dir_tareas.glob("T*.md")):
        m = re.match(r"(T\d+)", f.name)
        if m:
            en_disco.setdefault(m.group(1), []).append(f)

sin_archivo = sorted(set(tareas) - set(en_disco))
if sin_archivo:
    errores.append(f"en la tabla pero sin archivo en tareas/: {' '.join(sin_archivo)}")
huerfanos = sorted(set(en_disco) - set(tareas))
if huerfanos:
    errores.append(f"archivos en tareas/ que la tabla no menciona: {' '.join(huerfanos)}"
                   " (o sobran, o falta la fila)")
for tid, fs in en_disco.items():
    if len(fs) > 1:
        errores.append(f"{tid} tiene más de un archivo: {', '.join(f.name for f in fs)}")

# ── Cada archivo de tarea: las cabeceras que el gate y el runner leen de verdad
CABECERAS = ["**Estado:**", "**Depende de:**", "**Archivos que podés tocar:**"]
for tid in sorted(set(tareas) & set(en_disco)):
    f = en_disco[tid][0]
    cuerpo = f.read_text()
    for c in CABECERAS:
        if c not in cuerpo:
            errores.append(f"{f.name} no tiene la línea {c}")
    # La cabecera del archivo contra la fila de la tabla. Son dos declaraciones de lo mismo
    # y nada las cruzaba: si el plan dice que T13 depende de T31 y su archivo dice T30, el
    # runner usa la tabla para ordenar las etapas y el agente lee el archivo. Lo creamos
    # nosotros editando a mano, que es cómo pasa siempre.
    m_dep = re.search(r"^\*\*Depende de:\*\* *(.*)$", cuerpo, re.M)
    if m_dep:
        del_archivo = set(re.findall(r"T\d+", m_dep.group(1)))
        if del_archivo != tareas[tid]["deps"]:
            errores.append(
                f"{f.name} declara «Depende de: {' '.join(sorted(del_archivo)) or '—'}» y la "
                f"tabla dice «{' '.join(sorted(tareas[tid]['deps'])) or '—'}»")

    m = re.search(r"^\*\*Archivos que podés tocar:\*\* *(.*)$", cuerpo, re.M)
    if m and not m.group(1).strip():
        # Sin alcance el gate da rojo, así que la tarea es inejecutable desde el principio.
        errores.append(f"{f.name} declara «Archivos que podés tocar» vacío: el gate la rechaza")
    if not re.search(r"^## Objetivo", cuerpo, re.M):
        avisos.append(f"{f.name} no tiene sección «## Objetivo»")
    n_archivos = len([a for a in re.split(r"[,\s]+", tareas[tid]["archivos"]) if "." in a])
    if n_archivos > 3:
        avisos.append(f"{tid} toca {n_archivos} archivos: candidata a partirse "
                      f"(ver DESCOMPOSICION.md §4)")

# ── Ninguna tarea puede declarar un archivo que el gate considera intocable.
# Es un cruce entre dos componentes que nadie hacía, y produce tareas INSATISFACIBLES: el
# plan permite lo que el gate prohíbe, así que ningún agente puede cerrarlas. Nos pasó con
# dos tareas de 28, y una era peor que un problema de alcance — le pedía al agente escribir
# `scripts/_arquitectura.py`, es decir el verificador que lo juzga. Eso viola el corolario
# de P2: el comando tiene que ser inmodificable por quien es juzgado.
gate = RAIZ / "scripts" / "gate.sh"
if gate.exists():
    m = re.search(r"^INTOCABLES='([^']+)'", gate.read_text(), re.M)
    if m:
        patron = re.compile(m.group(1))
        for tid in sorted(set(tareas) & set(en_disco)):
            f = en_disco[tid][0]
            mm = re.search(r"^\*\*Archivos que podés tocar:\*\* *(.*)$", f.read_text(), re.M)
            if not mm:
                continue
            for a in re.split(r"[,\s]+", mm.group(1)):
                a = a.strip("`")
                if a and patron.match(a):
                    errores.append(f"{f.name} declara «{a}», que el gate considera intocable: "
                                   f"la tarea es insatisfacible")

# ── Plantillas sin completar, en el plan y en las tareas
def placeholders(cuerpo):
    # Fuera los bloques de código y el código en línea: `Promise<void>` y `<any>` son
    # genéricos de TypeScript, no plantillas sin completar.
    limpio = re.sub(r"```.*?```", "", cuerpo, flags=re.S)
    limpio = re.sub(r"`[^`\n]*`", "", limpio)
    return set(re.findall(r"<[a-záéíóúñ][^<>\n]{2,40}>", limpio))

# La línea de firma de G0 tiene <quién> y <fecha> a propósito: los completa la persona
# que aprueba, no el planificador. Su ausencia ya la cubre el aviso de «borrador».
texto_sin_firma = re.sub(r"^\*\*Estado del gate G0:\*\*.*$", "", texto, flags=re.M)
p = placeholders(texto_sin_firma)
if p:
    errores.append(f"{PLAN.name} tiene plantillas sin completar: {', '.join(sorted(p))}")
for tid in sorted(set(tareas) & set(en_disco)):
    f = en_disco[tid][0]
    p = placeholders(f.read_text())
    if p:
        errores.append(f"{f.name} tiene plantillas sin completar: {', '.join(sorted(p))}")

# ── El estado del gate G0 tiene que estar firmado por alguien, no por el agente
if re.search(r"\*\*Estado del gate G0:\*\*.*borrador", texto):
    avisos.append("el plan sigue marcado como «borrador»: G0 lo firma una persona")

for e in errores:
    print(f"  ✗ {e}")
for a in avisos:
    print(f"  · aviso: {a}")
if not errores and not avisos:
    print(f"  ✓ {len(tareas)} tareas, sin errores de forma")
elif not errores:
    print(f"  ✓ {len(tareas)} tareas, sin errores de forma ({len(avisos)} aviso/s)")

sys.exit(1 if errores else 0)
