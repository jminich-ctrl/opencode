#!/usr/bin/env python3
"""¿La reescritura de un enunciado se llevó algo que no podía llevarse?

  python3 scripts/preservar_criterios.py <antes.md> <despues.md>

Sale 0 si todo lo que estaba sigue estando, 1 si se perdió algo, y dice qué.

## Por qué existe

El prompt del arquitecto dice «no saques ni ablandes ningún criterio de terminado — si hace
falta, agregá». Hasta hoy el único juez de eso era **contar** viñetas `- [ ]` de todo el
archivo (`replanificar.sh`), y un replay midió el agujero: de 15 reescrituras mutantes, **11
salían ✓** —borrar `## Contrato`, borrar el campo `Prohibido tocar:`, canjear tres criterios
reales por tres triviales, invertir la prohibición del hash que es el defecto más caro del
2026-10-19—. El 2026-11-22 pasó de verdad: una reescritura borró una prohibición con toda su
explicación y el arnés dijo ✓.

## La taxonomía, que no es la que yo tenía en la cabeza

`arXiv 2608.24569` («When "Must" Becomes "Maybe"») mide que una restricción se debilita de
**cuatro** formas, no de una: **borrada**, **generalizada**, **degradada de prioridad** y
**reescrita ambigua**. Yo iba a chequear sólo la primera. Las cuatro, acá:

| forma | cómo se detecta |
|---|---|
| borrada | el texto del criterio ya no está, ni igual ni normalizado |
| degradada | el criterio salió de `## Criterio de terminado`, o `**Prohibido tocar:**` dejó de existir |
| generalizada | el criterio quedó, pero perdió lo que lo hacía verificable: un nombre de archivo, de símbolo o un número |
| reescrita ambigua | el criterio quedó, pero le apareció una palabra de escape («si aplica», «preferible», «idealmente») |

Y una quinta que no está en el paper y es la que de verdad nos pasó: **la directiva en
negrita borrada**. La primera versión de este archivo chequeaba secciones, criterios `- [ ]`
y el campo `**Prohibido tocar:**`, y **daba ✓ sobre la reescritura que motivó escribirlo** —
conservó las nueve secciones, los tres criterios idénticos y el campo intacto, y se llevó dos
líneas de prosa en negrita. Ver `directivas()`.

Lo que NO hace, declarado: no juzga si el enunciado nuevo es bueno. Sólo si perdió algo. Un
enunciado puede pasar esto y seguir siendo malo, y para eso están `validar-plan.py` y
`coherencia.py`.

## Y el baseline es HEAD, no el disco

`replanificar.sh` comparaba contra el archivo **como estaba en el árbol de trabajo**, y nada
compara nunca contra lo commiteado. Dos pasadas sin commitear en el medio degradan el
enunciado al hueso y las dos dicen ✓, porque la segunda toma la reescritura de la primera como
piso. Quien use esto tiene que pasarle `git show HEAD:<archivo>`.
"""
import pathlib
import re
import sys

# Secciones cuya desaparición es pérdida. No es «las que el formato exige» —eso lo valida
# otro— sino «las que estaban y se fueron»: la regla es conservar, no cumplir una plantilla.
ESCAPES = ("si aplica", "preferible", "idealmente", "en lo posible", "deseable",
           "si es posible", "opcional", "se recomienda", "debería")


def secciones(texto):
    return [l.strip() for l in texto.splitlines() if l.startswith("## ")]


def criterios(texto):
    """Las viñetas `- [ ]` de la sección «Criterio de terminado», en orden.

    De esa sección y no de todo el archivo: contar sobre el archivo entero deja que una
    viñeta agregada en `## Tests` compense una borrada del criterio, que es uno de los
    agujeros medidos."""
    dentro, salida = False, []
    for l in texto.splitlines():
        if l.startswith("## "):
            dentro = "criterio de terminado" in l.lower()
            continue
        if dentro and l.strip().startswith("- [ ]"):
            salida.append(l.strip()[5:].strip())
    return salida


def norma(s):
    """Para comparar sin castigar un reformato. Minúsculas, sin backticks, sin puntuación
    de borde, espacios colapsados. Deliberadamente NO saca palabras: si cambió una palabra,
    es otro criterio."""
    s = s.lower().replace("`", "").replace("**", "")
    s = re.sub(r"\s+", " ", s).strip(" .;:—-")
    return s


def anclas(s):
    """Lo que hace verificable a un criterio: rutas, símbolos con punto o guion bajo, y
    números. Si el criterio sobrevive pero perdió sus anclas, se generalizó."""
    return set(re.findall(r"[\w/.-]+\.(?:py|ts|tsx|sql|md|json)|[a-z_]+\.[a-z_]+|\b\d+\b", s))


def directivas(texto):
    """Las frases en NEGRITA del enunciado, normalizadas.

    Es dónde vive de verdad el conocimiento caro de este formato, y me costó una versión
    entera darme cuenta. La primera versión de este archivo chequeaba secciones, viñetas
    `- [ ]` y el campo `**Prohibido tocar:**`, y **daba ✓ sobre la reescritura de T26 que
    motivó escribirlo**: esa reescritura conservó las nueve secciones, los tres criterios
    idénticos y el campo intacto, y se llevó dos líneas de prosa:

        - **Cambiar el esquema de hash.** El del ejemplo es un `sha256` sin sal…
        **No mockees la conexión.** El escritor de tests inventó…

    O sea: el chequeo pasaba el caso que lo motivó. Lo vi corriéndolo, no diseñándolo.

    En este formato la negrita marca lo que carga peso —prohibiciones, advertencias, el
    contrato— porque el formato no tiene un campo para eso: `**Prohibido tocar:**` lleva
    rutas de archivo («Ninguno», en T26), no reglas. Mientras el conocimiento caro viva en
    prosa, lo único que se puede vigilar es la prosa."""
    # Dos palabras y 12 caracteres como mínimo: la negrita también se usa para enfatizar
    # una palabra suelta («antes», «Entra») y eso no es una directiva. Sin el filtro, T26
    # salía con 9 pérdidas de las que una era la palabra «antes»: un guardia que marca
    # ruido se apaga, y apagado es peor que ninguno.
    return {norma(m) for m in re.findall(r"\*\*(.+?)\*\*", texto)
            if len(m.strip()) >= 12 and len(m.strip().split()) >= 2}


def prohibido(texto):
    m = re.search(r"^\*\*Prohibido tocar:\*\*(.*)$", texto, re.M)
    return None if m is None else m.group(1).strip()


def revisar(antes, despues):
    perdidas = []

    # 1. BORRADA / 2. DEGRADADA fuera de la sección
    c_antes, c_despues = criterios(antes), criterios(despues)
    norm_despues = {norma(c) for c in c_despues}
    texto_despues = norma(despues)
    for c in c_antes:
        if norma(c) in norm_despues:
            continue
        if norma(c) in texto_despues:
            perdidas.append(("degradado", c, "sigue en el archivo pero ya no es un criterio "
                                             "de terminado: de bloqueante a prosa"))
        else:
            perdidas.append(("borrado", c, "no está en ninguna forma"))

    # 3. GENERALIZADA: está, pero perdió lo que lo hacía verificable
    for c in c_antes:
        igual = [d for d in c_despues if norma(d) == norma(c)]
        if igual:
            continue
        parecidos = [d for d in c_despues if norma(c)[:18] and norma(c)[:18] in norma(d)]
        for d in parecidos:
            faltan = anclas(c) - anclas(d)
            if faltan:
                perdidas.append(("generalizado", c,
                                 "quedó sin lo que lo hacía verificable: " + ", ".join(sorted(faltan))))

    # 4. AMBIGUA: apareció una palabra de escape donde antes no había
    for d in c_despues:
        nuevas = [e for e in ESCAPES if e in norma(d) and not any(
            e in norma(c) for c in c_antes if norma(c)[:18] and norma(c)[:18] in norma(d))]
        if nuevas:
            perdidas.append(("ablandado", d, "le apareció: " + ", ".join(nuevas)))

    # DIRECTIVAS en negrita que estaban y se fueron. Es la clase que de verdad pasó.
    d_antes, d_despues = directivas(antes), directivas(despues)
    for d in sorted(d_antes - d_despues):
        # Si la frase sigue en el archivo sin la negrita, es degradación: de regla a prosa.
        if d in norma(despues):
            perdidas.append(("directiva degradada", d,
                             "sigue escrita pero perdió el énfasis que la marcaba como regla"))
        else:
            perdidas.append(("directiva borrada", d,
                             "era una frase en negrita del enunciado: en este formato ahí "
                             "vive lo que carga peso, porque no hay campo para reglas"))

    # Secciones que estaban y se fueron
    faltan_sec = [s for s in secciones(antes) if s not in secciones(despues)]
    for s in faltan_sec:
        perdidas.append(("sección borrada", s, "estaba en el enunciado anterior"))

    # El campo de prohibiciones. Que esté VACÍO es otra cosa —el validador ya avisa— pero
    # que DESAPAREZCA no lo avisa nadie, y es la degradación de «bloqueante» a «no existe».
    p_antes, p_despues = prohibido(antes), prohibido(despues)
    if p_antes is not None and p_despues is None:
        perdidas.append(("campo borrado", "**Prohibido tocar:**",
                         f"existía con «{p_antes[:40]}» y ya no está. Lo que no se puede "
                         f"tocar va en el campo, no en prosa"))
    return perdidas


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip().splitlines()[2])
        return 2
    antes = pathlib.Path(sys.argv[1]).read_text()
    despues = pathlib.Path(sys.argv[2]).read_text()
    perdidas = revisar(antes, despues)
    if not perdidas:
        print(f"  ✓ no se perdió ningún criterio ni sección "
              f"({len(criterios(antes))} criterio(s) conservado(s))")
        return 0
    print(f"  ✗ la reescritura se llevó {len(perdidas)} cosa(s) que no podía llevarse:")
    for forma, que, por_que in perdidas:
        print(f"     [{forma}] {que[:88]}")
        print(f"        {por_que}")
    print("     El prompt dice «no saques ni ablandes ningún criterio — si hace falta,")
    print("     agregá». Las cuatro formas de ablandar salen de arXiv 2608.24569.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
