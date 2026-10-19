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
        if any(x in s for x in ("/tests/", "/_env", "/.venv", "__pycache__", "/node_modules/")):
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
    for mod, detalle in avisos:
        print(f"  ⚠ {detalle}")
        print(f"     Puede ser legítimo. Si tienen que coincidir, el enunciado no debe nombrar"
              f" el algoritmo sino EL ARCHIVO donde vive el que ya se usa.")
    if not rojos and not avisos:
        print(f"  ✓ {len(textos)} tareas cruzadas: ningún import huérfano, ningún módulo en disputa")
    elif not rojos:
        print(f"  ✓ {len(textos)} tareas cruzadas: ningún import huérfano "
              f"({len(avisos)} aviso/s para revisar)")
    return 1 if rojos else 0


if __name__ == "__main__":
    sys.exit(main())
