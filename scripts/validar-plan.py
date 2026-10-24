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
import subprocess
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
        m = re.match(r"^\|\s*(T\d+[a-z]?)\s*\|.*\|\s*\S+\s*\|\s*$", linea)
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
for linea in re.findall(r"^\|\s*(T\d+[a-z]?)\s*\|(.*)$", texto, re.M):
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
    tareas[tid] = {"titulo": celdas[0], "deps": set(re.findall(r"T\d+[a-z]?", celdas[1])) - {tid},
                   "archivos": celdas[2], "hecha": "✅" in celdas[-1]}
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
        m = re.match(r"(T\d+[a-z]?)", f.name)
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

# El nombre pelado es la abreviatura de la ruta: la tabla del pacman dice `laberinto.py`
# donde la tarea dice `src/pacman/laberinto.py`, y es el mismo archivo. Lo que esta
# comparación sigue atrapando es el nombre con OTRA extensión —la tabla decía `Login.jsx`
# y la tarea `Login.vue`, en un proyecto React— y el archivo que está en una lista y no en
# la otra.
def cubierto(ruta, otros):
    base = ruta.rsplit("/", 1)[-1]
    return any(ruta == o or o.rsplit("/", 1)[-1] == base for o in otros)


# ── Cada archivo de tarea: las cabeceras que el gate y el runner leen de verdad
vacios = []
CABECERAS = ["**Estado:**", "**Depende de:**", "**Archivos que podés tocar:**"]
# El campo que el gate LEE no debería quedar en blanco: un vacío no dice lo mismo que
# «Ninguno». Pero es AVISO y no error, y el número es la razón.
#
# Medido en clasificados: 25 de 34 tareas tienen «**Prohibido tocar:**» vacío, 9 con valor, y
# 4 de esas 9 dicen literalmente «Ninguno». En pacman todas tienen valor. O sea que en este
# proyecto el vacío se viene usando como sinónimo de «Ninguno»: no es un campo mutilado, es
# una convención inconsistente.
#
# Mi primera versión lo puso como ERROR y dejó 25 enunciados en rojo, deteniendo el plan para
# pedir que alguien escriba «Ninguno» 25 veces. Eso es sobre-corrección —el mismo defecto que
# cometí hoy reponiendo prefijos de markdown— y en el chequeo que decide si el plan arranca
# cuesta una corrida entera.
VACIOS_AVISAN = ["**Prohibido tocar:**"]
HUECO = re.compile(r"^[ \t0-9.)*#>_-]*HUECO\b(.*)$", re.M)
for tid in sorted(set(tareas) & set(en_disco)):
    f = en_disco[tid][0]
    cuerpo = f.read_text()
    for c in CABECERAS:
        if c not in cuerpo:
            errores.append(f"{f.name} no tiene la línea {c}")
    for c in VACIOS_AVISAN:
        m_v = re.search(r"^" + re.escape(c) + r" *(.*)$", cuerpo, re.M)
        if m_v and not m_v.group(1).strip():
            vacios.append(f.name)
    # ── Un enunciado que declara un HUECO no es un enunciado.
    #
    # `HUECO` es la palabra que el método reserva para «esto lo necesita la tarea y ninguna
    # tarea del plan lo entrega». Los dos replanificadores la buscan en el TRANSCRIPT del
    # arquitecto para frenar y llamar a una persona. Nadie la buscaba en el enunciado que SALE.
    #
    # El 2026-10-24, T05c de clasificados tenía en su línea 55:
    #   - **HUECO**: No existe función para listar todos los anuncios en la capa de servicios
    # Lo escribió la replanificación de `51f5c3f`. El arquitecto obedeció la instrucción (3)
    # del prompt —«si la tarea necesita algo que ninguna tarea del plan entrega, decilo con la
    # palabra HUECO»— y la escribió donde se le pidió escribir: en el cuerpo de la tarea. El
    # arnés mira el log, el log no la tenía, los cuatro jueces del relevo la aprobaron, y yo
    # la commiteé con el mensaje «el enunciado no decía que las rutas exigen autenticación».
    #
    # Después el ejecutor chocó con el hueco: entregó un `GET /ads` que devuelve «501 No
    # implementado» y escribió en dos archivos que no eran suyos buscando la función que no
    # existe. Yo diagnostiqué tres veces —el enunciado, el alcance, el modelo— mientras la
    # respuesta estaba escrita en el archivo que estaba leyendo.
    #
    # Es un chequeo de una línea sobre un artefacto que ya existía, y es el defecto que este
    # método persigue en todas sus formas: el dato estaba, nadie lo miraba.
    for m_h in HUECO.finditer(cuerpo):
        falta = m_h.group(1).strip(" *:\u2014-\t") or "no dice qué"
        errores.append(
            f"{f.name} declara un HUECO en su propio enunciado: «{falta[:140]}». Una tarea no "
            f"puede pedir algo que ninguna tarea del plan entrega: eso lo decide quien "
            f"planifica, agregando lo que falta a la tarea que corresponda o sacándolo del "
            f"alcance. Mientras esté escrito, el agente va a chocar con el hueco.")
    # La cabecera del archivo contra la fila de la tabla. Son dos declaraciones de lo mismo
    # y nada las cruzaba: si el plan dice que T13 depende de T31 y su archivo dice T30, el
    # runner usa la tabla para ordenar las etapas y el agente lee el archivo. Lo creamos
    # nosotros editando a mano, que es cómo pasa siempre.
    # El estado, en los dos lados. El deductor de etapas lee la columna de la tabla y
    # `estado.sh` lee esta línea: si sólo una dice «hecha», una tarea ya integrada se
    # vuelve a lanzar (pasó con T01 de clasificados) o una pendiente no se lanza nunca.
    m_est = re.search(r"^\*\*Estado:\*\* *(.*)$", cuerpo, re.M)
    if m_est:
        # La línea trae una ayuda después de «←» que menciona el propio «✅ hecha»:
        # el valor es lo de antes de la flecha.
        hecha_archivo = "✅" in m_est.group(1).split("←")[0]
        if hecha_archivo != tareas[tid]["hecha"]:
            quien = "el archivo" if hecha_archivo else "la tabla"
            errores.append(f"{f.name}: {quien} la da por hecha y el otro no. El deductor de "
                           f"etapas lee la tabla y estado.sh lee el archivo: así una tarea "
                           f"integrada se vuelve a lanzar, o una pendiente no se lanza nunca")

    m_dep = re.search(r"^\*\*Depende de:\*\* *(.*)$", cuerpo, re.M)
    if m_dep:
        del_archivo = set(re.findall(r"T\d+[a-z]?", m_dep.group(1)))
        if del_archivo != tareas[tid]["deps"]:
            errores.append(
                f"{f.name} declara «Depende de: {' '.join(sorted(del_archivo)) or '—'}» y la "
                f"tabla dice «{' '.join(sorted(tareas[tid]['deps'])) or '—'}»")

    # El alcance del archivo contra la columna «Archivos» de la tabla. Son dos
    # declaraciones de lo mismo que leen dos lectores: el deductor de etapas usa la tabla
    # para encontrar choques de archivo y paralelizar, y el gate usa el archivo de tarea
    # para juzgar el alcance. Divergían en todo el frontend de clasificados —la tabla decía
    # `Login.jsx` y la tarea `Login.vue`, en un proyecto React— así que el deductor
    # paralelizaba tareas que sí chocan y el gate juzgaba otro alcance que el planificado.
    m_alc = re.search(r"^\*\*Archivos que podés tocar:\*\* *(.*)$", cuerpo, re.M)
    if m_alc:
        def rutas(txt):
            return {a.strip().strip("`") for a in re.split(r"[,\s]+", txt)
                    if a.strip().strip("`") and ("." in a or a.strip().endswith("/"))}
        del_archivo = rutas(m_alc.group(1))
        de_la_tabla = rutas(tareas[tid]["archivos"])

        if de_la_tabla:
            falta = sorted(r for r in de_la_tabla if not cubierto(r, del_archivo))
            sobra = sorted(r for r in del_archivo if not cubierto(r, de_la_tabla))
        else:
            falta = sobra = []
        if falta or sobra:
            detalle = []
            if falta:
                detalle.append("la tabla declara y la tarea no: " + ", ".join(falta))
            if sobra:
                detalle.append("la tarea declara y la tabla no: " + ", ".join(sobra))
            errores.append(f"{f.name} y la tabla no declaran los mismos archivos — "
                           + "; ".join(detalle))

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

# ── La tabla de tests contra la tabla de tareas y contra los archivos de tarea.
# Tres declaraciones de lo mismo que leen tres lectores distintos: `escribir-tests.sh` usa
# la tabla del plan para saber qué archivo pedir, el agente lee la ruta del archivo de
# tarea, y el gate juzga el archivo que quedó en el disco. En clasificados las tres
# divergían: la tabla decía `backend/tests/test_auth_backend.py` y 23 de 27 archivos de
# tarea decían otra cosa (`tests/...`, `tests/backend/...`). El agente busca el test donde
# le dicen, no lo encuentra, y la tarea se cae por una razón que no es la suya.
FILA_TEST = re.compile(r"^\|\s*(T\d+[a-z]?)\s*\|\s*`?([^|`]+?)`?\s*\|\s*`?([A-Za-z_][\w]*)`?\s*\|\s*$", re.M)
tests_plan = {}
for tid, ruta, clase in FILA_TEST.findall(texto):
    # La tabla de tareas tiene 5 columnas y no matchea este patrón de 3; igual chequeamos
    # que no estemos leyendo una fila de ahí.
    if tid in tests_plan:
        errores.append(f"la tabla de tests declara {tid} dos veces")
        continue
    tests_plan[tid] = (ruta.strip(), clase.strip())

if tests_plan:
    sin_test = sorted(set(tareas) - set(tests_plan))
    if sin_test:
        errores.append(f"tareas sin test declarado en la tabla de tests: {' '.join(sin_test)}"
                       " (escribir-tests.sh no sabe qué archivo pedir y las saltea)")
    sobran = sorted(set(tests_plan) - set(tareas))
    if sobran:
        errores.append(f"la tabla de tests nombra tareas que no están en la tabla de tareas:"
                       f" {' '.join(sobran)}")

    # Dos tareas con el mismo archivo de test se pisan: la segunda sobrescribe el test de
    # la primera, y el gate de la primera pasa a juzgar otra cosa.
    por_ruta = {}
    for tid, (ruta, _) in tests_plan.items():
        por_ruta.setdefault(ruta, []).append(tid)
    for ruta, ids in sorted(por_ruta.items()):
        if len(ids) > 1:
            errores.append(f"{' y '.join(sorted(ids))} declaran el mismo archivo de test "
                           f"«{ruta}»: el segundo pisa al primero")

    # Y la ruta que el archivo de tarea le muestra al agente.
    LINEA_TEST = re.compile(r"^(.*Archivo: )`([^`]+)`(, clase )`?([A-Za-z_]\w*)`?(\..*)$", re.M)
    for tid in sorted(set(tareas) & set(en_disco) & set(tests_plan)):
        arch = en_disco[tid][0]
        cuerpo = arch.read_text()
        m = LINEA_TEST.search(cuerpo)
        ruta_plan, clase_plan = tests_plan[tid]
        if not m:
            avisos.append(f"{arch.name} no nombra su archivo de test: el agente no sabe "
                          f"dónde está (el plan dice {ruta_plan})")
            continue
        if (m.group(2), m.group(4)) == (ruta_plan, clase_plan):
            continue
        if ARREGLAR:
            nueva = f"{m.group(1)}`{ruta_plan}`{m.group(3)}`{clase_plan}`{m.group(5)}"
            arch.write_text(cuerpo[:m.start()] + nueva + cuerpo[m.end():])
            print(f"  · arreglado: {arch.name} apuntaba a «{m.group(2)}», ahora a «{ruta_plan}»")
        else:
            errores.append(f"{arch.name} dice que su test es «{m.group(2)}::{m.group(4)}» y "
                           f"el plan dice «{ruta_plan}::{clase_plan}»")

# ── Las rutas que el cuerpo de la tarea nombra, contra su propio alcance.
# T03 declaraba `001_initial.sql` y su contrato le pedía además escribir
# `001_inicial_down.sql`: dos archivos, uno permitido, y encima escrito de dos maneras
# (`initial` / `inicial`), así que no había respuesta que cerrara. El agente hizo lo
# correcto —escribir la reversa que le pedían— y el chequeo de alcance lo reprobó por eso.
# Misma clase que «la tarea declara un intocable»: el plan pide lo que el gate prohíbe.
# Qué cuenta como ruta en el texto. `127.0.0.1` no lo es (la extensión empieza con
# dígito) y `Juego.fruta` tampoco (es un atributo). La lista de extensiones es cerrada a
# propósito: acá fallar abierto —no marcar— es el lado seguro, porque marcar de más
# convierte el chequeo en ruido y el ruido se ignora.
RUTA_EN_TEXTO = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z][A-Za-z0-9]{0,4})`")
EXT_DE_ARCHIVO = {"py", "ts", "tsx", "js", "jsx", "sql", "md", "json", "scss", "css",
                  "html", "txt", "yml", "yaml", "sh", "toml", "cfg", "ini", "lock", "env"}
DEL_METODO = ("scripts/", "PLAN.md", "OBJETIVO.md", "AGENTS.md", "METODO.md", "HUMANO.md",
              "BITACORA.md", "DESCOMPOSICION.md", "OPENCODE.md", "PRUEBAS.md")
for tid in sorted(set(tareas) & set(en_disco)):
    arch = en_disco[tid][0]
    cuerpo = arch.read_text()
    mm = re.search(r"^\*\*Archivos que podés tocar:\*\* *(.*)$", cuerpo, re.M)
    if not mm:
        continue
    alcance = [a.strip().strip("`") for a in re.split(r"[,\s]+", mm.group(1)) if a.strip()]
    if not alcance:
        continue
    del_plan = tests_plan.get(tid, ("", ""))[0]

    def en_alcance(r, alcance=alcance, del_plan=del_plan):
        if r == del_plan or r.startswith(DEL_METODO):
            return True
        # El nombre pelado es la abreviatura natural de una ruta del alcance: si algo
        # permitido termina en `/<nombre>`, el cuerpo lo está nombrando corto. Lo que esto
        # SÍ sigue atrapando es el nombre pelado con otra extensión —T07 pedía `Login.vue`
        # en un proyecto React cuyo alcance declara `Login.jsx`—, que es el caso real.
        if "/" not in r and any(a.endswith("/" + r) for a in alcance):
            return True
        return any(r == a or (a.endswith("/") and r.startswith(a)) for a in alcance)

    # Sólo las secciones que le PIDEN escribir algo. El objetivo y las notas pueden
    # nombrar archivos ajenos para dar contexto.
    pedido = "\n".join(re.findall(
        r"^## (?:Contrato|Criterio de terminado|Alcance)\s*\n(.*?)(?=^## |\Z)",
        cuerpo, re.M | re.S))
    def parece_archivo(r):
        return "/" in r or r.rsplit(".", 1)[-1].lower() in EXT_DE_ARCHIVO

    for r in sorted({r for r in RUTA_EN_TEXTO.findall(pedido)
                     if parece_archivo(r) and not en_alcance(r)}):
        # Si el archivo es de OTRA tarea, nombrarlo es una referencia legítima: así se
        # describe una interfaz. Lo que no puede pasar es que el cuerpo pida un archivo que
        # **ninguna tarea tiene asignado**: ése no lo va a escribir nadie, y si lo escribe
        # quien lo lee, el chequeo de alcance lo reprueba. Era el caso de T03.
        asignados = {a.strip().strip("`") for otro in tareas.values()
                     for a in re.split(r"[,\s]+", otro["archivos"]) if a.strip().strip("`")}
        if cubierto(r, asignados):
            continue
        # Y un archivo que YA EXISTE no es un archivo que alguien tenga que escribir. El
        # chequeo usa la sección como aproximación a «te pido que lo escribas», que es
        # razonable pero no distingue «escribí esto» de «leé esto». La existencia sí: T26
        # tiene que nombrar `backend/tests/test_auth_backend.py` para decir «el patch se hace
        # así», y ese test está en el repo desde T04. El alcance lo sigue cuidando el paso 2
        # del gate, que reprueba tocar lo que no es tuyo.
        if (RAIZ / r).exists():
            continue
        errores.append(f"{arch.name} le pide escribir «{r}», y no está en su alcance ni en "
                       f"el de ninguna otra tarea: nadie lo va a escribir")

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

# ── Una tarea PENDIENTE cuyo código ya está commiteado no puede cerrar
# El método es tests-first y su validador exige que el test FALLE al revertir la
# implementación del agente. Si la implementación ya está en HEAD, el agente no toca nada,
# no hay nada que revertir, y el paso no se puede evaluar. Pasó con backend/app/main.py:
# una corrida vieja lo integró con gate verde, la tarea se reabrió y se partió en tres, y
# el archivo quedó. El agente de turno leyó el archivo, vio la tarea hecha, y declaró haber
# escrito un test que nunca escribió.
#
# Es barato detectarlo acá: es la tabla del plan contra `git ls-files`. Lo caro es que lo
# descubra un agente a los veinte minutos y lo informe mal.
try:
    _trackeados = set(subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=str(RAIZ),
        timeout=30).stdout.split())
except Exception:
    _trackeados = None
if _trackeados is None:
    avisos.append("⊘ no pude listar los archivos de git: no se pudo comprobar si alguna "
                  "tarea pendiente ya tiene su código commiteado")
else:
    # Un archivo que una tarea YA TERMINADA declara está explicado: la que viene lo
    # modifica, que es el caso normal. Sin esta exención el chequeo acusaba a las tres
    # tareas que tocan AdsList.jsx después de que T08 lo creara — un falso rojo que habría
    # frenado el plan entero, justo la clase de defecto que este chequeo vino a evitar.
    _de_tareas_hechas = set()
    for _t, _d in tareas.items():
        if _d.get("hecha"):
            _de_tareas_hechas.update(a.strip() for a in str(_d.get("archivos", "")).split(","))
    for tid, datos in sorted(tareas.items()):
        if datos.get("hecha"):
            continue
        ya = [a.strip() for a in str(datos.get("archivos", "")).split(",")
              if a.strip() and a.strip() in _trackeados
              and a.strip() not in _de_tareas_hechas]
        if ya:
            errores.append(
                f"{tid} está pendiente pero su código ya está commiteado: "
                f"{', '.join(ya)}. Tests-first no puede cerrar así —no hay implementación "
                f"que revertir—. O se borra el archivo y se reconstruye, o la tarea se "
                f"marca hecha")

# ── El estado del gate G0 tiene que estar firmado por alguien, no por el agente
if re.search(r"\*\*Estado del gate G0:\*\*.*borrador", texto):
    avisos.append("el plan sigue marcado como «borrador»: G0 lo firma una persona")

if vacios:
    avisos.append(f"{len(vacios)} tarea(s) con **Prohibido tocar:** en blanco "
                  f"({', '.join(sorted(vacios)[:3])}{'...' if len(vacios) > 3 else ''}): el "
                  f"gate lee ese campo, conviene que diga «Ninguno» en vez de quedar vacío")

for e in errores:
    print(f"  ✗ {e}")
for a in avisos:
    print(f"  · aviso: {a}")
if not errores and not avisos:
    print(f"  ✓ {len(tareas)} tareas, sin errores de forma")
elif not errores:
    print(f"  ✓ {len(tareas)} tareas, sin errores de forma ({len(avisos)} aviso/s)")

sys.exit(1 if errores else 0)
