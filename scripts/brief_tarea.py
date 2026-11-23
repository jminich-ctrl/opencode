#!/usr/bin/env python3
"""El brief de UNA tarea: su texto, lo que entregan sus dependencias, y los invariantes del
plan. Nada más.

    python3 scripts/brief_tarea.py tareas/T16-backend-rutas-favoritos.md [--destino X.md]

Por qué existe, medido el 2026-11-22 replanificando T16. El prompt decía «Leé la tarea, leé
PLAN.md», y `PLAN.md` son 12.523 bytes de los cuales 8.025 son dos secciones que el
arquitecto no necesita —la tabla completa de 34 tareas y la lista completa de tests—. El
arquitecto (Qwen3.8-27B, 5,9 tok/s medidos) hizo TRECE lecturas para juntar lo que
necesitaba: la tarea, PLAN.md, cuatro fuentes, las tareas T14 y T15, dos archivos de test.
Produjo 23.692 bytes de deliberación, llegó al diagnóstico CORRECTO —«HUECO: T15 was
supposed to provide a list function in the service, but it only provided
`toggle_favorite_service`»— y el pedido se cortó antes de que llamara a `write`. El
diagnóstico quedó vivo sólo en un log.

La palanca no es que escriba menos: lo que tiene que escribir son 2 KB. Es que tiene que
LEER menos para decidir, y sobre todo que no pague trece viajes de ida y vuelta para armar
a mano un contexto que un comando arma en milisegundos.

Lo toma de superpowers (MIT, Jesse Vincent), `skills/subagent-driven-development`, que lo
dice en una línea: «Never make a subagent read the whole plan file». Ellos lo resuelven con
`scripts/task-brief PLAN_FILE N`.

QUÉ ENTRA, y cada cosa está acá porque el arquitecto de T16 la usó:

  · la tarea completa, textual
  · el `## Contrato` de cada tarea que la suya declara en «Depende de» — es lo que contesta
    «¿alguien entrega esto?», o sea el dato con el que se decide un HUECO
  · las secciones de invariante del plan (arquitectura, decisiones cerradas): el arquitecto
    citó «the architecture requires rutas → servicios» para fundamentar su diagnóstico
  · las filas de la tabla de tareas que corresponden a ésta y a sus dependencias

QUÉ NO ENTRA: la tabla entera, la lista entera de tests, y el resto del plan.

UNA COSA QUE NO HACE, a propósito: callarse. Si una sección declarada no existe, o una
dependencia no tiene `## Contrato`, el brief lo DICE en su lugar. Un brief que omite en
silencio es peor que PLAN.md entero: el que lo lee no puede distinguir «no está en el plan»
de «no te lo pasé». Es el defecto que este repo tiene escrito como «nombrar la cosa no
alcanza», en su forma más barata de cometer.
"""
import argparse
import os
import pathlib
import re
import sys

# Las secciones del plan que son INVARIANTES del proyecto, no inventario. Se llevan textuales
# porque una tarea mal escrita suele estar mal contra una de éstas, y el que la reescribe no
# puede inferirlas. No se adivinan por tamaño ni por orden: se nombran, y si una no está, el
# brief lo dice.
SECCIONES_INVARIANTE = ("Arquitectura", "Decisiones cerradas en G0", "Decisiones tomadas")


def secciones(texto):
    """{título: cuerpo} para los `## título` de un markdown."""
    partes = re.split(r"^## +(.+?) *$", texto, flags=re.M)
    return {partes[i].strip(): partes[i + 1] for i in range(1, len(partes), 2)}


def dependencias(texto_tarea):
    """Los ids de «**Depende de:** T15, T06c». Vacío si dice «—» o no está."""
    m = re.search(r"^\*\*Depende de:\*\* *(.*)$", texto_tarea, re.M)
    if not m:
        return []
    return [x.strip() for x in re.split(r"[,;]", m.group(1))
            if re.fullmatch(r"T[0-9]+[a-z]*", x.strip())]


def archivo_de_tarea(dir_tareas, tid):
    """`tareas/T15-*.md`. El id es exacto: `T1` no puede traer `T15`."""
    for f in sorted(dir_tareas.glob(f"{tid}-*.md")):
        return f
    return None


def filas_de_la_tabla(cuerpo_tareas, ids):
    """Las filas `| T16 | … |` de los ids pedidos, con el encabezado de la tabla."""
    lineas = cuerpo_tareas.splitlines()
    cab = [l for l in lineas if re.match(r"^\| *# *\|", l) or re.match(r"^\|[-| ]+\|$", l)]
    filas = []
    for tid in ids:
        for l in lineas:
            if re.match(rf"^\| *{re.escape(tid)} *\|", l):
                filas.append(l)
                break
    return (cab + filas) if filas else []


def rutas_de_los_campos(texto_tarea):
    """Los paths que la tarea nombra en sus campos de archivos, en orden y sin repetir."""
    salida = []
    for campo in ("Archivos que podés tocar", "Prohibido tocar"):
        m = re.search(rf"^\*\*{campo}:\*\* *(.*)$", texto_tarea, re.M)
        if not m:
            continue
        for x in re.split(r"[,;\s]+", m.group(1).strip()):
            x = x.strip().strip("`")
            if x and x not in ("—", "-", "N/A") and x not in salida:
                salida.append(x)
    return salida


def nombres_de_arriba(ruta):
    """Los `def` y `class` de nivel superior de un .py, que es el «import exacto».

    Sin `ast`: un archivo a medio escribir no parsea, y justamente los archivos que una
    tarea trabada tiene a mano son los que están a medio escribir. Una regex sobre la
    columna cero da la respuesta en el único caso que importa.
    """
    try:
        texto = ruta.read_text()
    except OSError:
        return []
    return re.findall(r"^(?:async +)?(?:def|class) +([A-Za-z_][A-Za-z0-9_]*)", texto, re.M)


def donde_vive(raiz, rutas, tope=40):
    """Cada ruta contra el DISCO, y el contenido real del directorio de cada una.

    Por qué existe, medido el 2026-11-23 en el diagnóstico de T16. El prompt le pide al
    arquitecto, textual: «para cada cosa que la tarea nombra, DÓNDE vive: archivo exacto e
    import exacto». Eso es una pregunta sobre el disco, y el arquitecto no tenía el disco:
    tenía que adivinar. Adivinó dos veces y las dos fallaron —`tareas/T15-backend-servici
    o-favoritos.md` cuando el archivo real dice `servicios` en plural, y `backend/app/rutas/
    ads.py`, que no existe todavía—. A 5,9 tok/s medidos, cada adivinanza fallada es un
    viaje de ida y vuelta, y se murió contra el muro del gateway con el diagnóstico correcto
    ya escrito en su propio log.

    Un modelo reconstruye un path por patrón; `ls` lo sabe. Es el reparto de siempre: el
    dato lo pone el comando, el juicio lo pone el modelo.
    """
    out = []
    dirs = []
    for r in rutas:
        f = raiz / r
        if f.exists():
            nombres = nombres_de_arriba(f) if f.suffix == ".py" else []
            extra = f" — define: {', '.join(nombres)}" if nombres else ""
            out.append(f"- `{r}` **existe**{extra}")
        else:
            out.append(f"- `{r}` ⊘ **no existe todavía** (si tu tarea lo crea, está bien; "
                       f"si esperabas encontrarlo, no lo inventes: no está)")
        d = (raiz / r).parent
        if d not in dirs:
            dirs.append(d)
    for d in dirs:
        rel = d.relative_to(raiz) if d.is_relative_to(raiz) else d
        if not d.is_dir():
            out += ["", f"`{rel}/` ⊘ **el directorio no existe.**"]
            continue
        hijos = sorted(x.name + ("/" if x.is_dir() else "")
                       for x in d.iterdir() if not x.name.startswith((".", "__")))
        if len(hijos) > tope:
            hijos = hijos[:tope] + [f"(+{len(hijos) - tope} más)"]
        out += ["", f"`{rel}/` contiene, hoy: " + (", ".join(f"`{h}`" for h in hijos)
                                                   or "**nada**")]
    return out


def brief(ruta_tarea, ruta_plan):
    tarea = ruta_tarea.read_text()
    tid = ruta_tarea.name.split("-")[0]
    dir_tareas = ruta_tarea.parent
    out = [f"# Brief de {tid} — armado por scripts/brief_tarea.py",
           "",
           "Esto es TODO lo que necesitás del plan. NO leas PLAN.md: lo que te sirve de ahí",
           "ya está abajo, y lo que no está abajo es porque no está en el plan.",
           "",
           f"## La tarea ({ruta_tarea.name}), textual",
           "", tarea.rstrip(), ""]

    deps = dependencias(tarea)
    out += ["## Lo que entregan las tareas de las que ésta depende", ""]
    if not deps:
        out += ["(no declara dependencias)", ""]
    for tid_dep in deps:
        f = archivo_de_tarea(dir_tareas, tid_dep)
        if f is None:
            # No es un detalle: una dependencia declarada que no existe como tarea ES un
            # hueco del plan, y el que lee tiene que verlo acá y no deducirlo de un glob
            # que no encontró nada.
            out += [f"### {tid_dep}", "",
                    f"⊘ **NO existe `tareas/{tid_dep}-*.md`.** La tarea declara depender de algo "
                    f"que el plan no tiene como tarea. Eso es un HUECO del plan.", ""]
            continue
        secs = secciones(f.read_text())
        toca = re.search(r"^\*\*Archivos que podés tocar:\*\* *(.*)$", f.read_text(), re.M)
        out += [f"### {tid_dep} ({f.name})", ""]
        if toca:
            out += [f"Archivos que entrega: {toca.group(1).strip() or '(ninguno declarado)'}", ""]
        if "Contrato" in secs:
            out += ["Su contrato:", "", secs["Contrato"].strip(), ""]
        else:
            out += [f"⊘ **{tid_dep} no tiene sección `## Contrato`**: el plan no declara QUÉ "
                    f"entrega. No se puede saber desde acá si entrega lo que esta tarea "
                    f"necesita; si tu tarea lo necesita y nadie lo declara, eso es un HUECO.",
                    ""]

    # El disco, antes de los invariantes del plan: lo que el plan DECLARA y lo que el
    # disco TIENE es la comparación con la que se decide un HUECO, y hasta hoy el brief
    # traía sólo la mitad declarada.
    raiz_proy = ruta_tarea.parent.parent
    rutas = rutas_de_los_campos(tarea)
    for tid_dep in deps:
        f = archivo_de_tarea(dir_tareas, tid_dep)
        if f is None:
            continue
        m = re.search(r"^\*\*Archivos que podés tocar:\*\* *(.*)$", f.read_text(), re.M)
        if m:
            for x in re.split(r"[,;\s]+", m.group(1).strip()):
                x = x.strip().strip("`")
                if x and x not in ("—", "-", "N/A") and x not in rutas:
                    rutas.append(x)
    out += ["## Dónde vive cada cosa, verificado contra el disco", ""]
    if rutas:
        out += donde_vive(raiz_proy, rutas) + [""]
    else:
        out += ["⊘ la tarea no nombra ningún archivo en sus campos «Archivos que podés "
                "tocar» / «Prohibido tocar». Eso ya es un defecto del enunciado.", ""]
    out += ["Los archivos de tarea del plan, con su nombre EXACTO:", "",
            ", ".join(f"`{f.name}`" for f in sorted(dir_tareas.glob("T*.md"))) or "⊘ ninguno",
            ""]

    if ruta_plan is not None and ruta_plan.exists():
        plan = ruta_plan.read_text()
        secs_plan = secciones(plan)
        out += [f"## Invariantes del plan ({ruta_plan.name})", ""]
        for nombre in SECCIONES_INVARIANTE:
            if nombre in secs_plan:
                out += [f"### {nombre}", "", secs_plan[nombre].strip(), ""]
            else:
                out += [f"### {nombre}", "",
                        f"⊘ `{ruta_plan.name}` no tiene sección `## {nombre}`.", ""]
        if "Tareas" in secs_plan:
            filas = filas_de_la_tabla(secs_plan["Tareas"], [tid] + deps)
            if filas:
                out += ["### Las filas de la tabla de tareas que te tocan", ""] + filas + [""]
    else:
        out += ["## Invariantes del plan", "",
                f"⊘ no encontré el plan ({ruta_plan}): el brief va SIN arquitectura ni "
                f"decisiones cerradas. No lo supongas: pedilo.", ""]
    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tarea", help="ruta al archivo tareas/TNN-*.md")
    p.add_argument("--plan", default=None, help="ruta a PLAN.md (por omisión, junto a tareas/)")
    p.add_argument("--destino", default=None, help="dónde escribirlo (por omisión, a stdout)")
    a = p.parse_args()
    ruta = pathlib.Path(a.tarea)
    if not ruta.exists():
        print(f"✗ no existe {ruta}", file=sys.stderr)
        return 2
    plan = pathlib.Path(a.plan) if a.plan else ruta.parent.parent / "PLAN.md"
    texto = brief(ruta, plan)
    if a.destino:
        d = pathlib.Path(a.destino)
        d.write_text(texto)
        # La RUTA por stdout y el contenido al archivo: quien llama necesita la ruta para
        # ponerla en el prompt, y meter 5 KB en el stdout de un script de shell es cómo se
        # llena un log de cosas que nadie va a leer.
        print(os.fspath(d))
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
