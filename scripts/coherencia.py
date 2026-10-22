#!/usr/bin/env python3
"""Cruza las tareas entre sí: lo que una declara contra lo que las otras proveen.

El gate mira UNA tarea. El paso 5 mira la arquitectura. Nadie miraba si dos tareas se
contradicen — y los dos defectos más caros del 2026-10-19 fueron exactamente eso: tareas que
pasaban sus propios tests y juntas rompían el sistema.

**Cadáver 1 — T05.** Decía «respetando la autorización del usuario», no declaraba con qué
obtener el usuario, y sus archivos permitidos no incluían `servicios/auth.py`. El agente
inventó `obtener_usuario_id_desde_token`, cableó tres archivos a ella, y se quedó una hora
contra su propio `ImportError`. Nadie cruzaba «lo que el contrato importa» contra «lo que
alguna tarea provee».

**Cadáver 2 — T26.** Decía «hash de la contraseña con `hashlib.scrypt`» mientras
`servicios/auth.py` —de T04, ya integrada— compara con `hashlib.sha256`. Registro habría
guardado scrypt y login comparado sha256: ningún usuario registrado podría entrar, y las DOS
tareas pasarían sus tests, porque ninguna prueba cruza registro con login.

Dos chequeos, y la diferencia entre ellos es a propósito:

  ROJO  — un import del contrato que nadie provee. Es mecánico y no admite interpretación:
          o el símbolo existe en el tronco, o alguna tarea lo declara, o la tarea es
          inejecutable.
  AVISO — dos tareas que nombran el mismo módulo con funciones distintas. Puede ser legítimo
          (`json.dumps` y `json.loads`), así que no reprueba: lo pone adelante para que lo
          juzgue quien planifica.

Uso:
    PROYECTO=ejemplo-clasificados python3 scripts/coherencia.py
    python3 scripts/coherencia.py        # desde la raíz del proyecto

Códigos: 0 sin rojos · 1 hay rojos · 2 no pude leer el plan (⊘, no es un pase)
"""
import ast
import difflib
import os
import pathlib
import re
import sys

# `from X import a, b` y `import X` dentro del bloque ## Contrato de cada tarea.
RE_BLOQUE = re.compile(r"^## Contrato\s*$(.*?)(?=^## |\Z)", re.M | re.S)
RE_MOD_FUNC = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]{2,})\b")
# Módulos donde mezclar funciones distintas entre tareas sí es un defecto y no una variante.
# No es una lista de «módulos peligrosos»: es dónde ya nos costó, que es el único criterio
# que este repo acepta para agregar una verificación.
# Los módulos donde dos tareas que no coinciden es un DEFECTO, no una variante.
#
# La primera versión miraba cualquier `x.y` del texto, y sobre el plan ya arreglado emitía
# siete avisos: `f.unlink` donde `f` es una variable, `importlib.util` que es un submódulo.
# Sin resolver imports no se puede distinguir un módulo de una variable, y un chequeo que
# emite siete falsos positivos en un plan limpio se ignora — y uno que se ignora es peor que
# ninguno (MEDICION.md §7: «si crece, se poda»).
#
# Así que la lista es corta y la regla para agregarle algo es la del método: **para entrar,
# una verificación necesita un cadáver con nombre y fecha.**
#
#   hashlib — 2026-10-19, T26: pedía `hashlib.scrypt` mientras `servicios/auth.py` compara
#             `hashlib.sha256`. Registro habría guardado un hash que login no puede verificar;
#             las dos tareas pasaban sus tests y juntas rompían el login.
MODULOS_QUE_TIENEN_QUE_COINCIDIR = {"hashlib", "hmac", "bcrypt", "scrypt", "jwt", "base64"}
RE_RUIDO = re.compile(r"^(self|cls|np|pd|request|response|app|router)$")
# Terceros que el proyecto declara en sus manifiestos: tampoco los provee una tarea.
TERCEROS = {"fastapi", "pydantic", "starlette", "pytest", "pymysql", "vitest", "react"}
# `main.scss` y `main.tsx` matchean `módulo.función` y no lo son: la regex leía el nombre y
# no la cosa. Lo que separa un módulo de un archivo es la extensión.
EXTENSIONES = {"py", "ts", "tsx", "js", "jsx", "scss", "css", "md", "json", "sql", "html",
               "txt", "yml", "yaml", "lock", "sh", "env", "toml", "cfg", "ini"}


def tareas(base: pathlib.Path):
    for f in sorted((base / "tareas").glob("*.md")):
        yield f.name.split("-")[0], f


def imports_del_contrato(texto: str):
    """(módulo, símbolo) de cada import dentro del bloque ## Contrato."""
    salida = []
    for bloque in RE_BLOQUE.findall(texto):
        for linea in bloque.splitlines():
            linea = linea.strip()
            if not linea.startswith(("from ", "import ")):
                continue
            # Se parsea con `ast`, no con regex: un import con alias o con paréntesis se
            # lee igual, y un comentario al final no se cuela como símbolo.
            try:
                arbol = ast.parse(linea)
            except SyntaxError:
                continue
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.ImportFrom) and nodo.module:
                    for a in nodo.names:
                        salida.append((nodo.module, a.name))
                elif isinstance(nodo, ast.Import):
                    for a in nodo.names:
                        salida.append((a.name, None))
    return salida


def lo_que_hace(texto: str) -> str:
    """El texto de la tarea SIN el bloque «No entra».

    El chequeo tiene que leer lo que la tarea declara que HACE, no lo que declara que no.
    Y además: en este repo cada arreglo documenta su cadáver, así que una tarea corregida
    CITA el defecto viejo —«acá decía hash con `hashlib.scrypt`»— y un chequeo que lee prosa
    ve la cita como si fuera la declaración. Le pasaría con toda tarea arreglada.
    """
    salida, saltando = [], False
    for linea in texto.splitlines():
        if re.match(r"^\s*No entra\s*:", linea):
            saltando = True
            continue
        if saltando and (linea.startswith("## ") or re.match(r"^\s*Entra\s*:", linea)):
            saltando = False
        if not saltando:
            salida.append(linea)
    return "\n".join(salida)


def simbolos_de(ruta: pathlib.Path):
    """Los nombres de nivel superior que un archivo define."""
    try:
        arbol = ast.parse(ruta.read_text())
    except (OSError, SyntaxError):
        return set()
    out = set()
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out



# ── Tablas: lo que el código consulta contra lo que las migraciones crean ─────────────
#
# Mismo chequeo que el de imports, en otra superficie. Cadáver del 2026-10-21:
# `backend/app/datos/users_register.py` hace `INSERT INTO users` y la migración
# `001_initial.sql` crea `usuarios`. Esa tabla NUNCA existió, así que los tests de registro
# no podían pasar — y durante trece corridas el método culpó por eso a tareas que no tocan
# registro. Nadie cruzaba «qué tabla consulta el código» contra «qué tabla crea alguna
# migración».
#
# Se miran SÓLO literales de cadena, con `ast`: un `from backend.app.datos import users` de
# Python tiene la palabra `from` seguida de un nombre, y un regex plano sobre el archivo lo
# leería como SQL. Y la cadena tiene que parecer SQL —llevar SELECT/INSERT/UPDATE/DELETE—
# porque «from» aparece en mil textos que no son consultas.
RE_CREA_TABLA = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z_][A-Za-z0-9_]*)`?",
                           re.I)
# `(?<!ON )`: `actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`
# es una cláusula de COLUMNA, y sin esto el chequeo informaba `current_timestamp` como una
# tabla que falta. Lo encontró el control contra los dos proyectos de ejemplo, que es la
# única razón por la que no quedó un rojo inventado en el chequeo que decide si el plan
# arranca.
RE_USA_TABLA = re.compile(r"(?<!ON )\b(?:FROM|INTO|UPDATE|JOIN)\s+`?([a-z_][a-z0-9_]*)`?", re.I)
# Forma de SENTENCIA, no «aparece la palabra UPDATE». La cadena de arriba lleva `UPDATE` y no
# es una consulta; un ROJO que se apoya en una palabra suelta no es mecánico, es un augurio.
RE_PARECE_SQL = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|REPLACE|WITH)\b"
    r"|\bINSERT\s+INTO\b|\bDELETE\s+FROM\b"
    r"|\bSELECT\b[\s\S]*\bFROM\b|\bUPDATE\b[\s\S]*\bSET\b", re.I)
# Palabras que nunca son una tabla, por si alguna forma nueva se cuela igual.
NUNCA_UNA_TABLA = {"current_timestamp", "now", "set", "select", "values", "table",
                   "duplicate", "key", "null", "default"}
# Tablas del motor, y la que el propio método crea para registrar migraciones.
TABLAS_DEL_SISTEMA = {"information_schema", "mysql", "performance_schema", "sys",
                      "_migraciones", "dual"}


# Directorios que no son el código del proyecto. Se juzga por PARTES del path y no por
# subcadena: el filtro decía `"/.venv" in str(f)`, y con `PROYECTO=.` las rutas salen
# relativas —`.venv/lib/python3.12/...`, sin barra delante— así que no matcheaba y el chequeo
# se comía las dependencias enteras.
#
# Medido el 2026-10-21 contra el mismo proyecto: 2 rojos con `PROYECTO=ejemplo-clasificados`
# o con ruta absoluta, **37** con `PROYECTO=.`, 35 de ellos de `pip/_vendor/distlib`. El
# mismo chequeo y dos veredictos distintos según cómo se nombre el proyecto, y `PROYECTO="."`
# es lo que `ubicar_proyecto` deja cuando se corre desde la raíz del proyecto: el preflight
# habría detenido el plan por tablas de pip. Un chequeo cuyo resultado depende de cómo lo
# invocás no mide el sujeto, mide la invocación.
AJENOS = {".venv", "_env", "__pycache__", "node_modules", ".git", "site-packages"}


def es_del_proyecto(f: pathlib.Path) -> bool:
    return not (AJENOS & set(f.parts))


def tablas_que_crean_las_migraciones(base: pathlib.Path):
    """Las que alguna migración CREA. Las `_down.sql` no cuentan: son la reversa."""
    creadas = {}
    for sql in sorted(base.rglob("*.sql")):
        partes = {x.lower() for x in sql.parts}
        if not ({"migraciones", "migrations"} & partes):
            continue
        if sql.name.endswith("_down.sql"):
            continue
        try:
            txt = sql.read_text()
        except OSError:
            continue
        for t in RE_CREA_TABLA.findall(txt):
            creadas.setdefault(t.lower(), sql.name)
    return creadas


def tablas_que_consulta_el_codigo(base: pathlib.Path):
    """`{tabla: [archivo:línea, ...]}` leyendo sólo cadenas que parecen SQL."""
    usadas = {}
    for f in sorted(base.rglob("*.py")):
        if not es_del_proyecto(f):
            continue
        try:
            arbol = ast.parse(f.read_text())
        except (OSError, SyntaxError):
            continue
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)):
                continue
            txt = nodo.value
            if not RE_PARECE_SQL.search(txt):
                continue
            # Una cadena que CREA la tabla la provee, no la consume.
            propias = {t.lower() for t in RE_CREA_TABLA.findall(txt)}
            for t in RE_USA_TABLA.findall(txt):
                t = t.lower()
                if t in TABLAS_DEL_SISTEMA or t in propias or t in NUNCA_UNA_TABLA:
                    continue
                donde = f"{f.relative_to(base) if f.is_relative_to(base) else f}:{nodo.lineno}"
                usadas.setdefault(t, []).append(donde)
    return usadas


# ¿Qué dicen los ENUNCIADOS sobre esta tabla? Dos cosas muy distintas:
#   · quien promete CREARLA se hace cargo del problema;
#   · quien promete GUARDAR ahí sin que nadie la cree ES el problema, y es la tarea a corregir.
#
# La distinción no es cosmética: la escribí primero sin ella y el chequeo trató a T26 —la
# tarea cuyo enunciado dice «almacene los datos en la tabla `users`», o sea la que ORIGINA
# la contradicción— como si fuera su dueña, y bajó un rojo legítimo a aviso. Un chequeo que
# confunde la causa con el arreglo ablanda exactamente el caso que vino a atrapar.
#
# Exige la tabla EN FORMA DE TABLA y no la palabra suelta: el archivo `users_register.py`
# contiene «users» y nombrarlo no es comprometerse con la tabla `users`.
def _pat(plantilla: str, tabla: str):
    return re.compile(plantilla % re.escape(tabla), re.I)


# Las tablas que los ENUNCIADOS dan por hechas, sin mirar una línea de código.
#
# Este es el cruce que habría ahorrado todo. El de abajo mira el código, así que sólo puede
# hablar DESPUÉS de que un agente lo escribió: para cuando dijo «la tabla `users` no existe»,
# T26 ya había corrido, commiteado «gate verde» y dejado dos tests en rojo permanente que
# tres defectos posteriores intentaron explicar mirando al lugar equivocado. El enunciado y
# las migraciones existen **el día que se planifica**, y contradecirse entre ellos es
# detectable ahí, con cero agentes gastados.
# Dos formas, y las dos tienen que ser inequívocas. La primera versión aceptaba
# `\bFROM\s+(\w+)` a secas y cobró SEIS falsos positivos de siete contra clasificados:
# `fastapi`, `pydantic`, `contextlib`, `backend`, `app`, `ads` — todos de un `from X import`
# de Python citado en el enunciado. Es LITERALMENTE el falso positivo que este archivo ya
# documenta del lado del código («un `from X import` de Python no es un `FROM` de SQL»),
# repetido del lado del enunciado por escribir la regex de memoria en vez de mirar la que
# estaba doce líneas más arriba.
RE_TABLA_BACKTICKS = re.compile(r"tabla\s+`([a-z_][a-z0-9_]*)`", re.I)
RE_TABLA_EN_SQL = re.compile(r"\b(?:FROM|INTO|UPDATE|JOIN)\s+`?([a-z_][a-z0-9_]*)`?", re.I)


def tablas_que_los_enunciados_dan_por_hechas(textos: dict):
    """`{tabla: [TNN, ...]}` — «tabla `x`» con backticks, o un `x` dentro de una línea que
    parece SQL de verdad (el mismo RE_PARECE_SQL que juzga el código)."""
    pedidas = {}
    for tid, texto in sorted(textos.items()):
        encontradas = set(m.group(1).lower() for m in RE_TABLA_BACKTICKS.finditer(texto))
        for linea in texto.splitlines():
            if RE_PARECE_SQL.search(linea):
                encontradas |= {m.group(1).lower() for m in RE_TABLA_EN_SQL.finditer(linea)}
        for t in sorted(encontradas):
            if t in NUNCA_UNA_TABLA or t in TABLAS_DEL_SISTEMA:
                continue
            pedidas.setdefault(t, [])
            if tid not in pedidas[t]:
                pedidas[t].append(tid)
    return pedidas


def tareas_que_crean(textos: dict, tabla: str):
    pats = (_pat(r"create\s+table\s+(?:if\s+not\s+exists\s+)?`?%s`?\b", tabla),
            _pat(r"cre(?:a|ar|e)\s+(?:la\s+)?tabla\s+`?%s`?\b", tabla))
    return sorted(tid for tid, t in textos.items() if any(p.search(t) for p in pats))


# UN solo criterio para «¿el enunciado nombra esta tabla?», y se apoya en la función de
# arriba. Tenía dos, con regexes distintas para la misma pregunta, y uno de los dos ya había
# cobrado los seis falsos positivos: dos definiciones de lo mismo son dos cosas que pueden
# divergir, y en este repo divergieron tres veces (el gate en tres copias, mutar.py corriendo
# dos veces, la huella del instrumento).
def tareas_que_la_dan_por_hecha(textos: dict, tabla: str):
    return list(tablas_que_los_enunciados_dan_por_hechas(textos).get(tabla.lower(), []))


def main():
    base = pathlib.Path(os.environ.get("PROYECTO", "."))
    if not (base / "tareas").is_dir():
        base = pathlib.Path(".")
    if not (base / "tareas").is_dir():
        print("⊘ no encuentro tareas/ — no pude cruzar nada", file=sys.stderr)
        return 2

    textos = {tid: f.read_text() for tid, f in tareas(base)}
    if not textos:
        print("⊘ no hay tareas que cruzar", file=sys.stderr)
        return 2

    # Qué símbolo provee cada tarea, según los imports de LOS DEMÁS contratos no: según lo que
    # su propio contrato define. Un contrato declara `def f(...)`, y eso es lo que promete.
    provee = {}
    for tid, texto in textos.items():
        for bloque in RE_BLOQUE.findall(texto):
            for m in re.finditer(r"^\s*(?:async\s+)?def\s+([a-z_][a-z0-9_]*)", bloque, re.M):
                provee.setdefault(m.group(1), []).append(tid)
            for m in re.finditer(r"^\s*([a-z_][a-z0-9_]*)\s*#.*APIRouter", bloque, re.M):
                provee.setdefault(m.group(1), []).append(tid)

    # Y los MÓDULOS que cada tarea va a CREAR: una tarea que declara
    # `backend/app/datos/ads.py` provee el nombre `ads` para `from backend.app.datos import
    # ads`, que es un submódulo y Python lo resuelve sin que el `__init__.py` lo nombre.
    #
    # Sin esto el chequeo daba un falso rojo justo sobre la forma que el método EXIGE para que
    # el `@patch` del test aplique. Es la TERCERA vez que el mismo caso muerde un chequeo
    # distinto de este repo: ya había pasado con `_imports.py` —donde lo atrapó el control
    # negativo contra los dos proyectos— y con el paso 4 del gate. Un submódulo declarado como
    # archivo es una declaración; que no tenga `def` no la vuelve inexistente.
    for tid, texto in textos.items():
        m = re.search(r"^\*\*Archivos que podés tocar:\*\* *(.*)$", texto, re.M)
        if not m:
            continue
        for ruta in re.findall(r"[A-Za-z0-9_./-]+\.py", m.group(1)):
            provee.setdefault(pathlib.Path(ruta).stem, []).append(tid)

    rojos, avisos = [], []

    # ── ROJO: un import del contrato que nadie provee ────────────────────────────────
    for tid, texto in sorted(textos.items()):
        for modulo, simbolo in imports_del_contrato(texto):
            raiz = modulo.split(".")[0]
            # La biblioteca estándar y los paquetes de terceros no los provee ninguna tarea:
            # la lista blanca a mano tenía tres nombres y `contextlib` salía como huérfano.
            if simbolo is None or raiz in sys.stdlib_module_names or raiz in TERCEROS:
                continue
            # ¿Está en el tronco?
            rel = pathlib.Path(modulo.replace(".", "/") + ".py")
            candidatos = [base / rel, base.parent / rel, pathlib.Path(*rel.parts[1:])]
            en_tronco = any(c.is_file() and simbolo in simbolos_de(c) for c in candidatos)
            if en_tronco or simbolo in provee:
                continue
            rojos.append((tid, f"importa `{simbolo}` de `{modulo}` y no existe en el tronco "
                               f"ni lo declara el contrato de ninguna tarea"))

    # ── ROJO: una tabla que el código consulta y ninguna migración crea ─────────────
    #
    # Sólo se juzga si el proyecto TIENE migraciones: sin ellas no hay con qué comparar, y un
    # chequeo que no puede medir no opina. Es la misma regla que el método aplica a los
    # corredores de tests: un ⊘ no es un pase, pero tampoco un rojo.
    cubiertos = []
    creadas = tablas_que_crean_las_migraciones(base)
    dichas = set()
    if creadas:
        for tabla, quienes in sorted(tablas_que_los_enunciados_dan_por_hechas(textos).items()):
            if tabla in creadas or tareas_que_crean(textos, tabla):
                continue
            parecidas = difflib.get_close_matches(tabla, sorted(creadas), n=1, cutoff=0.5)
            pista = f" ¿Será `{parecidas[0]}`, que crea {creadas[parecidas[0]]}?" if parecidas else ""
            dichas.add(tabla)
            rojos.append(("esquema",
                          f"{', '.join(quienes)} da por hecha la tabla `{tabla}` y ninguna "
                          f"migración ni tarea la crea.{pista} Está en el ENUNCIADO: quien lo "
                          f"ejecute va a escribir esa consulta porque se la pidieron, y va a "
                          f"pasar su propio gate. Se corrige antes de gastar un agente."))
    if creadas:
        for tabla, lugares in sorted(tablas_que_consulta_el_codigo(base).items()):
            if tabla in creadas or tabla in dichas:
                continue
            # La pista con `difflib` y no con prefijos a ojo: `users` vs `usuarios` no
            # comparte los primeros cinco caracteres y era justo el caso que había que
            # nombrar. Quien planifica necesita el candidato, no sólo el problema.
            parecidas = difflib.get_close_matches(tabla, sorted(creadas), n=1, cutoff=0.5)
            pista = f" ¿Será `{parecidas[0]}`, que crea {creadas[parecidas[0]]}?" if parecidas else ""
            donde = f"{lugares[0]}{' y ' + str(len(lugares) - 1) + ' más' if len(lugares) > 1 else ''}"
            cargo = tareas_que_crean(textos, tabla)
            piden = [t for t in tareas_que_la_dan_por_hecha(textos, tabla) if t not in cargo]
            if piden:
                # El sujeto correcto. El mensaje anterior decía «el código consulta» y mandaba
                # a mirar el código: con esto se ve que el agente hizo lo que le pidieron y que
                # lo que hay que corregir es el ENUNCIADO. Es el defecto más caro de estos días
                # —culpar al sujeto equivocado— en el chequeo más nuevo.
                rojos.append(("esquema",
                              f"{', '.join(piden)} promete guardar en la tabla `{tabla}` y "
                              f"ninguna tarea la crea: la migración crea "
                              f"{', '.join('`%s`' % c for c in sorted(creadas))}."
                              f"{pista} El código la consulta porque el enunciado se la pidió "
                              f"({donde}): se corrige el enunciado, no el agente."))
            elif cargo:
                # No es un pase: la contradicción sigue viva hasta que esa tarea corra, y
                # cualquier tarea anterior que toque ese camino va a chocar con la tabla que
                # no existe. Lo que cambia es que el plan tiene dueño para el problema, así
                # que detenerlo acá sería impedir su propio arreglo. El juez sigue siendo el
                # gate de esa tarea.
                cubiertos.append(f"la tabla `{tabla}` no la crea ninguna migración ({donde}), "
                                 f"y {', '.join(cargo)} se hace cargo: el plan puede arrancar, "
                                 f"pero hasta que esa tarea pase, todo lo que consulte `{tabla}` falla.")
            else:
                rojos.append(("esquema",
                              f"el código consulta la tabla `{tabla}` y ninguna migración la "
                              f"crea — {donde}."
                              f"{pista} Lo decide quien planifica: o la migración la crea, o el "
                              f"código usa la que existe."))

    # ── AVISO: un enunciado nombra `mod.func` y el CÓDIGO usa `mod.otra` ─────────────
    #
    # El par importa, y el primero que elegí estaba mal: comparaba texto de tarea contra
    # texto de tarea, y el cadáver era texto contra CÓDIGO. T26 decía «hash con
    # `hashlib.scrypt`» y el `hashlib.sha256` vivía en `servicios/auth.py`, no en el
    # enunciado de T04 — así que con dos enunciados no había par y el chequeo callaba.
    # Probarlo contra el cadáver es lo que lo mostró.
    codigo = {}
    for f in sorted(base.rglob("*.py")):
        s = str(f)
        if "tests" in f.parts or not es_del_proyecto(f):
            continue
        try:
            txt = f.read_text()
        except OSError:
            continue
        for mod, func in RE_MOD_FUNC.findall(txt):
            if mod not in MODULOS_QUE_TIENEN_QUE_COINCIDIR:
                continue
            codigo.setdefault(mod, {}).setdefault(func, set()).add(
                str(f.relative_to(base)) if f.is_relative_to(base) else s)

    for tid, texto in sorted(textos.items()):
        for mod, func in sorted(set(RE_MOD_FUNC.findall(lo_que_hace(texto)))):
            if mod not in MODULOS_QUE_TIENEN_QUE_COINCIDIR or mod not in codigo:
                continue
            otras = {f: ar for f, ar in codigo[mod].items() if f != func}
            if not otras or func in codigo[mod]:
                continue      # el código ya usa la que la tarea nombra: coinciden
            detalle = " · ".join(f"`{mod}.{f}` en {sorted(ar)[0]}" for f, ar in sorted(otras.items()))
            avisos.append((mod, f"{tid} nombra `{mod}.{func}` y el código usa {detalle}"))

    for tid, msg in rojos:
        print(f"  ✗ {tid}: {msg}")
    for detalle in cubiertos:
        print(f"  ⚠ esquema: {detalle}")
    for mod, detalle in avisos:
        print(f"  ⚠ {detalle}")
        print(f"     Puede ser legítimo. Si tienen que coincidir, el enunciado no debe nombrar"
              f" el algoritmo sino EL ARCHIVO donde vive el que ya se usa.")
    avisos_total = len(avisos) + len(cubiertos)
    if not rojos and not avisos_total:
        print(f"  ✓ {len(textos)} tareas cruzadas: ningún import huérfano, ningún módulo en disputa")
    elif not rojos:
        print(f"  ✓ {len(textos)} tareas cruzadas: ningún import huérfano "
              f"({avisos_total} aviso/s para revisar)")
    return 1 if rojos else 0


if __name__ == "__main__":
    sys.exit(main())
