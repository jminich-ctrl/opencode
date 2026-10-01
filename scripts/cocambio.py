#!/usr/bin/env python3
"""Archivos que cambian juntos y que la arquitectura dice que son independientes.

Es la deriva que el chequeo de capas deja pasar **en verde**: dos módulos que la
arquitectura declara separados y que en la práctica no se pueden tocar por separado. Nadie
lo ve en un diff, porque cada diff es correcto; se ve en la historia.

  python3 scripts/cocambio.py                 # sobre todo el repo
  VENTANA=200 python3 scripts/cocambio.py     # últimos 200 commits

El diseño es el publicado, con sus umbrales, no inventado:

- **Confianza asimétrica más piso de soporte absoluto.** "De las veces que cambió A, en
  qué fracción cambió B". La confianza sola es catastrófica con poco soporte: un archivo
  que cambió una vez junto a B tiene confianza 1,0. La configuración medida con confianza
  0,9 y soporte 3 dio precisión >50% y recall ~4%; la de confianza 0,1 dio precisión 26%.
  Los defaults de acá son los de la herramienta de campo más usada: soporte 5, confianza 30%.
- **Se descartan los commits grandes.** El trabajo original descartó los de más de 30
  archivos, y es también el mecanismo publicado para los merges. Un commit de licencia o de
  formato acopla todo con todo.
- **Y el número que calibra las expectativas**: en una inspección manual de 408 cambios
  conjuntos, sólo el **16,2%** correspondía a dependencias estructurales. El 40,4% eran
  concerns transversales —aplicar una licencia, cambiar cabeceras—. **La mayoría de lo que
  salga acá no va a ser un problema de diseño**, y por eso esto informa y no corta.

El tamaño típico de commit no es portable entre proyectos (se midió 13,78 contra 5,38
archivos por revisión en dos repos), así que si los resultados son ruidosos, calibrá
MAX_ARCHIVOS para el tuyo.
"""
import collections
import itertools
import os
import pathlib
import re
import subprocess
import sys

VENTANA = os.environ.get("VENTANA", "")          # cuántos commits mirar; vacío = todos
MAX_ARCHIVOS = int(os.environ.get("MAX_ARCHIVOS", "30"))
SOPORTE = int(os.environ.get("SOPORTE", "5"))     # mínimo de cambios compartidos
CONFIANZA = float(os.environ.get("CONFIANZA", "30"))  # % mínimo
EXTENSIONES = tuple(os.environ.get("EXTENSIONES", ".py,.ts,.tsx,.js,.jsx,.scss").split(","))

# Pares que se espera que cambien juntos: test con su unidad, y lo que declares acá.
# La herramienta de campo publicada trae esta exclusión como una característica propia.
ESPERADOS = [(r"tests?/", r""), (r"", r"tests?/")]


def modulo(ruta):
    """A qué módulo pertenece un archivo. ADAPTAR si tu estructura es otra."""
    partes = pathlib.Path(ruta).parts
    return partes[1] if len(partes) > 2 else (partes[0] if partes else "")


def commits():
    cmd = ["git", "log", "--no-merges", "--name-only", "--pretty=format:%H"]
    if VENTANA:
        cmd.insert(2, f"-n{VENTANA}")
    salida = subprocess.run(cmd, capture_output=True, text=True).stdout
    grupo = []
    for linea in salida.split("\n"):
        if re.fullmatch(r"[0-9a-f]{40}", linea.strip()):
            if grupo:
                yield grupo
            grupo = []
        elif linea.strip():
            grupo.append(linea.strip())
    if grupo:
        yield grupo


def main():
    cambios = collections.Counter()
    juntos = collections.Counter()
    descartados = 0
    for archivos in commits():
        archivos = [a for a in archivos if a.endswith(EXTENSIONES)]
        if not archivos:
            continue
        if len(archivos) > MAX_ARCHIVOS:
            # Un commit de licencia, formato o renombre masivo acopla todo con todo.
            descartados += 1
            continue
        for a in archivos:
            cambios[a] += 1
        for a, b in itertools.combinations(sorted(set(archivos)), 2):
            juntos[(a, b)] += 1

    if not cambios:
        print("  · no hay historia suficiente para medir co-cambio")
        return 0

    hallazgos = []
    for (a, b), compartidos in juntos.items():
        if compartidos < SOPORTE:
            continue
        if modulo(a) == modulo(b):
            continue          # mismo módulo: que cambien juntos es lo esperado
        if any(re.search(pa, a) and (not pb or re.search(pb, b)) for pa, pb in ESPERADOS):
            continue
        # Confianza asimétrica en los dos sentidos; se informa la más alta.
        c_ab = 100.0 * compartidos / cambios[a]
        c_ba = 100.0 * compartidos / cambios[b]
        if max(c_ab, c_ba) >= CONFIANZA:
            hallazgos.append((max(c_ab, c_ba), compartidos, a, b, modulo(a), modulo(b)))

    hallazgos.sort(reverse=True)
    print(f"  {len(cambios)} archivos, {len(juntos)} pares con historia compartida"
          + (f", {descartados} commit(s) de más de {MAX_ARCHIVOS} archivos descartados"
             if descartados else ""))
    if not hallazgos:
        print(f"  ✓ ningún par de módulos distintos cambia junto por encima de "
              f"{CONFIANZA:.0f}% con soporte {SOPORTE}")
        return 0
    print(f"  · {len(hallazgos)} par(es) de módulos distintos que cambian juntos:")
    for conf, n, a, b, ma, mb in hallazgos[:12]:
        print(f"     {conf:5.0f}%  {n:>3} veces   {ma}/{mb}   {a}  ↔  {b}")
    print("    No es un veredicto: en una inspección manual publicada, sólo el 16,2% de los")
    print("    cambios conjuntos correspondía a dependencias estructurales. Lo que decide es")
    print("    si estos dos módulos deberían poder tocarse por separado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
