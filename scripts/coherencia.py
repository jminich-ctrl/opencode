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


# ── Columnas: un nivel más abajo que las tablas, y el que faltaba ─────────────────────
#
# Cadáver del 2026-10-24. La tabla `anuncios` se crea con `categoria_id`, y
# `backend/app/datos/search_ads.py` —de T28, marcada ✅ hecha— hace:
#
#     SELECT id, usuario_id, titulo, categoria FROM anuncios WHERE 1=1
#     ...  condiciones.append("categoria = %s")
#
# Esa columna no existe: el código NO PUEDE correr. Su gate dio verde porque sus tests
# simulan la base y nadie compara la consulta contra el esquema. El chequeo de tablas no lo
# ve —la tabla `anuncios` sí existe— y lo encontró, de casualidad, el ejecutor de otra tarea
# al que el guardia de alcance frenó por tocar un archivo ajeno: el método tenía el dato
# dentro de un rechazo.
#
# Se juzgan SÓLO superficies explícitas, por la misma razón que el chequeo de tablas mira
# sólo literales que parecen SQL: un rojo en el preflight detiene el plan, y un falso rojo
# cuesta una corrida entera.
#   · la lista de un `SELECT ... FROM <una tabla>`, sin `*`, sin JOIN, sin funciones, sin
#     nombres calificados y sin alias;
#   · las columnas declaradas de un `INSERT INTO <t> (...)`.
# El `WHERE` queda afuera a propósito: sacarlo de ahí pide parsear expresiones, y preferí un
# chequeo que ve menos a uno que inventa. El caso de T28 cae igual por la lista del SELECT.

# Palabras que abren una restricción y no son una columna.
NO_SON_COLUMNAS = {"primary", "foreign", "unique", "key", "index", "constraint", "check",
                   "fulltext", "spatial", "period"}


def _cuerpos_create_table(txt: str):
    """`[(tabla, cuerpo)]`, delimitando con un CONTADOR de paréntesis y no con un regex.

    `VARCHAR(255)` y `FOREIGN KEY (x) REFERENCES y(id)` anidan paréntesis: un regex perezoso
    corta el cuerpo en el primer `)` —el del VARCHAR— y pierde la mitad de las columnas. Y un
    chequeo de columnas que no ve todas las columnas no informa de menos: INVENTA rojos.
    """
    for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
                         r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\(", txt, re.I):
        i, nivel = m.end(), 1
        while i < len(txt) and nivel:
            if txt[i] == "(":
                nivel += 1
            elif txt[i] == ")":
                nivel -= 1
            i += 1
        yield m.group(1).lower(), txt[m.end():i - 1]


def _partir_en_el_primer_nivel(cuerpo: str):
    """Las comas de ARRIBA, no las de adentro de `DECIMAL(10,2)`."""
    partes, nivel, actual = [], 0, []
    for ch in cuerpo:
        if ch == "(":
            nivel += 1
        elif ch == ")":
            nivel -= 1
        if ch == "," and nivel == 0:
            partes.append("".join(actual)); actual = []
        else:
            actual.append(ch)
    partes.append("".join(actual))
    return partes


def columnas_que_crean_las_migraciones(base: pathlib.Path):
    """`{tabla: {columna, ...}}`. Las `_down.sql` no cuentan: son la reversa."""
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
        for tabla, cuerpo in _cuerpos_create_table(txt):
            cols = creadas.setdefault(tabla, set())
            for item in _partir_en_el_primer_nivel(cuerpo):
                item = item.strip()
                if not item:
                    continue
                primera = re.split(r"[\s(]+", item, 1)[0].strip("`").lower()
                if primera in NO_SON_COLUMNAS:
                    continue
                if re.fullmatch(r"[a-z_][a-z0-9_]*", primera):
                    cols.add(primera)
        # `ALTER TABLE t ADD COLUMN c` también crea columna: sin esto, una migración posterior
        # que agrega un campo deja al chequeo acusando al código que lo usa.
        for m in re.finditer(r"ALTER\s+TABLE\s+`?([a-z_][a-z0-9_]*)`?\s+ADD\s+"
                             r"(?:COLUMN\s+)?`?([a-z_][a-z0-9_]*)`?", txt, re.I):
            creadas.setdefault(m.group(1).lower(), set()).add(m.group(2).lower())
    return creadas


RE_SELECT_DE_UNA_TABLA = re.compile(
    r"\bSELECT\s+(.+?)\s+FROM\s+`?([a-z_][a-z0-9_]*)`?(?![a-z0-9_])", re.I | re.S)
RE_INSERT_CON_COLUMNAS = re.compile(
    r"\bINSERT\s+INTO\s+`?([a-z_][a-z0-9_]*)`?\s*\(([^)]*)\)", re.I)


def _columnas_de_una_lista(lista: str):
    """Los nombres de columna de una lista explícita, o `None` si no se puede afirmar.

    Devuelve `None` —y el chequeo se calla— en cuanto aparece algo que no es un nombre pelado:
    `*`, una función, un nombre calificado, un alias. Preferir callarse es la regla: el rojo
    de este chequeo detiene el plan.
    """
    lista = re.sub(r"^\s*(?:DISTINCT|ALL)\s+", "", lista, flags=re.I)
    cols = set()
    for item in _partir_en_el_primer_nivel(lista):
        item = item.strip().strip("`")
        if not item or "*" in item or "(" in item or "." in item:
            return None
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", item, re.I):
            return None
        cols.add(item.lower())
    return cols or None


def columnas_que_consulta_el_codigo(base: pathlib.Path):
    """`{(tabla, columna): [archivo:línea, ...]}` desde literales que parecen SQL."""
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
            donde = (f"{f.relative_to(base) if f.is_relative_to(base) else f}"
                     f":{nodo.lineno}")
            # Con un JOIN una columna puede venir de cualquiera de las tablas: no se puede
            # afirmar de cuál, así que no se afirma nada.
            if not re.search(r"\bJOIN\b", txt, re.I):
                for m in RE_SELECT_DE_UNA_TABLA.finditer(txt):
                    cols = _columnas_de_una_lista(m.group(1))
                    if not cols:
                        continue
                    for c in cols:
                        usadas.setdefault((m.group(2).lower(), c), []).append(donde)
            for m in RE_INSERT_CON_COLUMNAS.finditer(txt):
                cols = _columnas_de_una_lista(m.group(2))
                if not cols:
                    continue
                for c in cols:
                    usadas.setdefault((m.group(1).lower(), c), []).append(donde)
    return usadas


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


# ¿De qué tarea es este archivo, y esa tarea ya corrió?
#
# Sin esto el preflight se trababa a sí mismo. El código de `users_register.py` contradice el
# esquema, la tarea que lo arregla (T26) declara ese archivo entre los que puede tocar, y el
# preflight hacía `exit 1` ANTES de dejarla correr: el chequeo impedía arreglar el defecto que
# el chequeo señalaba. Y no es un caso raro: en un método tests-first el código siempre está
# peor que el plan, porque el plan se corrige en segundos y el código necesita una corrida.
#
# La distinción que importa no es «hay una tarea» sino SI YA CORRIÓ:
#   · tarea pendiente → aviso. Va a correr y su gate la va a juzgar.
#   · tarea hecha     → ROJO, y el sujeto es el veredicto: figura hecha y su código no puede
#                       funcionar, así que su gate dio un verde falso y hay que reabrirla.
# Eso es lo contrario de ablandar: convierte un bloqueo mudo en la acusación correcta.
RE_ESTADO = re.compile(r"^\*\*Estado:\*\*\s*(.+)$", re.M)
RE_TOCAR = re.compile(r"^\*\*Archivos que podés tocar:\*\*\s*(.+)$", re.M)


def duenio_del_archivo(textos: dict, ruta: str):
    """`(TNN, hecha)` de la tarea que declara este archivo, o `(None, False)`."""
    ruta = ruta.split(":")[0].lstrip("./")
    for tid, texto in sorted(textos.items()):
        m = RE_TOCAR.search(texto)
        if not m:
            continue
        declarados = [a.strip().lstrip("./") for a in m.group(1).split(",")]
        if not any(ruta == d or ruta.endswith("/" + d) or d.endswith("/" + ruta) for d in declarados):
            continue
        e = RE_ESTADO.search(texto)
        estado = (e.group(1) if e else "").lower()
        return tid, ("hecha" in estado or "✅" in estado)
    return None, False


def duenios_del_archivo(textos: dict, ruta: str):
    """`[(TNN, hecha), ...]` de TODAS las tareas que declaran este archivo.

    `duenio_del_archivo` devuelve sólo la primera, y para decidir si un rojo detiene el plan
    hace falta saber si queda alguna PENDIENTE: `datos/messages.py` lo declaran tres tareas
    —una hecha y dos pendientes— y con la primera sola el veredicto sería «reabrir» sobre una
    tarea cuyo arreglo ya está planificado.
    """
    ruta = ruta.split(":")[0].lstrip("./")
    encontrados = []
    for tid, texto in sorted(textos.items()):
        m = RE_TOCAR.search(texto)
        if not m:
            continue
        declarados = [a.strip().lstrip("./") for a in m.group(1).split(",")]
        if not any(ruta == d or ruta.endswith("/" + d) or d.endswith("/" + ruta)
                   for d in declarados):
            continue
        e = RE_ESTADO.search(texto)
        estado = (e.group(1) if e else "").lower()
        encontrados.append((tid, "hecha" in estado or "✅" in estado))
    return encontrados


def main():
    base = pathlib.Path(os.environ.get("PROYECTO", "."))
    # `--tablas` imprime lo que las migraciones CREAN, una por línea, y sale.
    #
    # Es para el prompt de replanificar-coherencia.sh, y la razón es medida: sin ese dato el
    # arquitecto se iba a buscarlo solo. Con el prompt que decía «elegís vos entre (a) y (b)»
    # y sin la lista, la corrida de T26 leyó el enunciado, la migración, `auth.py`,
    # `datos/users.py` y el test antes de que la memoria la cortara; la de T28, dos archivos.
    # La única corrida que llegó a escribir —4:09— tenía el nombre de la tabla existente en el
    # prompt. El dato no decide nada: cuál de las dos salidas tomar sigue siendo del que
    # planifica. Lo que ahorra es la búsqueda, que es lo que no entra en el techo.
    if "--tablas" in sys.argv:
        if not (base / "tareas").is_dir():
            base = pathlib.Path(".")
        for t, sql in sorted(tablas_que_crean_las_migraciones(base).items()):
            print(f"{t} (la crea {sql})")
        return 0
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
    creadas_cols = columnas_que_crean_las_migraciones(base)
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
                tid_d, hecha = duenio_del_archivo(textos, lugares[0])
                if tid_d and not hecha:
                    cubiertos.append(
                        f"el código consulta la tabla `{tabla}` y ninguna migración la crea "
                        f"({donde}).{pista} {tid_d} declara ese archivo y está PENDIENTE: va a "
                        f"correr y su gate la va a juzgar. El plan puede arrancar.")
                elif tid_d and hecha:
                    rojos.append(("esquema",
                                  f"{tid_d} figura HECHA y su código consulta la tabla "
                                  f"`{tabla}`, que ninguna migración crea — {donde}."
                                  f"{pista} Su gate dio un veredicto falso: ese código no "
                                  f"puede funcionar. Hay que REABRIR {tid_d}, no parchear a "
                                  f"mano."))
                else:
                    rojos.append(("esquema",
                                  f"el código consulta la tabla `{tabla}` y ninguna migración la "
                                  f"crea — {donde}."
                                  f"{pista} Ninguna tarea declara ese archivo: lo decide quien "
                                  f"planifica, o la migración la crea, o el código usa la que existe."))

    # ── ROJO: una COLUMNA que el código consulta y ninguna migración crea ──────────
    #
    # Un nivel más abajo que el chequeo de tablas, y es el que faltaba. Medido el 2026-10-24
    # contra ejemplo-clasificados: SEIS columnas inventadas en tres archivos, y los tres de
    # tareas con gate VERDE.
    #
    #   anuncios.categoria          la tabla tiene `categoria_id`      (T28, hecha)
    #   usuarios.password_hash      la tabla tiene `clave_hash`        (T26, hecha)
    #   mensajes.remitente_id       la tabla tiene `de_usuario_id`     (T20, hecha hoy)
    #   mensajes.destinatario_id    la tabla tiene `a_usuario_id`
    #   mensajes.contenido          la tabla tiene `cuerpo`
    #   mensajes.fecha_envio        la tabla tiene `creado_en`
    #
    # Ninguno de esos códigos puede correr, y los tres pasaron su gate porque sus tests
    # simulan la base: nadie comparaba la consulta contra el esquema. El de T20 se cerró HOY.
    #
    # Lo encontró el ejecutor de OTRA tarea, al que el guardia de alcance frenó por tocar un
    # archivo ajeno —estaba corrigiendo `categoria` por `categoria_id`—. O sea que el método
    # tenía el dato adentro de un rechazo y no lo leía: el rechazo era correcto, y la
    # información que traía se tiraba.
    if creadas_cols:
        for (tabla, col), lugares in sorted(columnas_que_consulta_el_codigo(base).items()):
            if tabla not in creadas_cols or col in creadas_cols[tabla]:
                continue
            # Sin adivinanza por parecido, A DIFERENCIA del chequeo de tablas. Medido: para
            # `destinatario_id` sugería `de_usuario_id` y para `remitente_id` sugería
            # `a_usuario_id` —las dos INVERTIDAS— y para `contenido` sugería `creado_en`. Una
            # pista equivocada dentro de un veredicto es peor que ninguna: es la familia del
            # sujeto equivocado, y acá el nombre correcto no se puede deducir de la ortografía
            # porque el esquema está en castellano y el código en otra convención.
            #
            # Lo que sí sirve es el DATO: las columnas que la tabla tiene. Son pocas y están
            # a mano.
            pista = f" La tabla tiene: {', '.join('`%s`' % c for c in sorted(creadas_cols[tabla]))}."
            donde = f"{lugares[0]}{' y ' + str(len(lugares) - 1) + ' más' if len(lugares) > 1 else ''}"
            # TODOS los que declaran el archivo, no el primero. Con `messages.py` son tres
            # —T20 hecha, T21 y T22 pendientes— y la diferencia decide el veredicto: si alguna
            # está PENDIENTE va a correr y su gate la va a juzgar, así que el plan puede
            # arrancar. Tomar sólo el primero convertiría eso en un rojo que detiene el plan
            # para pedir que se reabra una tarea cuyo arreglo ya está planificado.
            duenios = duenios_del_archivo(textos, lugares[0])
            pendientes = [tid for tid, hecha in duenios if not hecha]
            cerradas = [tid for tid, hecha in duenios if hecha]
            if pendientes:
                cubiertos.append(
                    f"el código consulta `{tabla}.{col}` y la migración no crea esa columna "
                    f"({donde}).{pista} {', '.join(pendientes)} declara ese archivo y está "
                    f"PENDIENTE: va a correr y su gate la va a juzgar. El plan puede arrancar.")
            elif cerradas:
                rojos.append(("esquema",
                              f"{', '.join(cerradas)} figura HECHA y su código consulta "
                              f"`{tabla}.{col}`, que ninguna migración crea — {donde}."
                              f"{pista} Su gate dio un veredicto falso: esa consulta no puede "
                              f"correr. Hay que REABRIR {', '.join(cerradas)}, no parchear a "
                              f"mano desde otra tarea."))
            else:
                rojos.append(("esquema",
                              f"el código consulta `{tabla}.{col}` y ninguna migración crea esa "
                              f"columna — {donde}.{pista} Ninguna tarea declara ese archivo: lo "
                              f"decide quien planifica."))

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
