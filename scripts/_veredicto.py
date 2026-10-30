#!/usr/bin/env python3
"""Escribe UN veredicto de test como línea JSON. Lo llama `escribir-tests.sh` al concluir cada
intento, con las dimensiones por stdin (`nombre=marca`, una por línea).

Por qué existe: el juicio de este gate —dimensión por dimensión, con el motivo del rechazo— es
lo que no tiene ningún dataset público de software. Exportarlo parseando los logs funciona para
los aceptados y deja huecos: el 2026-10-29, 30 de 499 registros quedaron con la dimensión de
mutación en «sin dato» porque el bloque del intento se partía en el log. El dato existe en el
momento en que el paso decide; acá se escribe ahí.

Nunca falla la corrida: si no puede escribir, no escribe. Un registro perdido es un dato menos;
una corrida caída por el registro es una medición perdida.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import sys


def main():
    ap = argparse.ArgumentParser()
    for a in ("destino", "tarea", "test", "clase", "veredicto", "motivo", "raiz", "desde"):
        ap.add_argument(f"--{a}", default="")
    args = ap.parse_args()
    if not args.destino or not args.tarea:
        return 0

    dims = {}
    for linea in sys.stdin.read().splitlines():
        if "=" in linea:
            k, v = linea.split("=", 1)
            dims[k.strip()] = v.strip()

    raiz = pathlib.Path(args.raiz) if args.raiz else None

    def leer_de(base, ruta):
        """El test RECHAZADO vive en el worktree, no en el tronco: al tronco llegan sólo los
        aceptados. Y es la mitad del dataset que más vale para un juez — un registro que dice
        «rechazado porque el patch apunta al módulo equivocado» sin el texto del test no
        entrena nada."""
        if not base or not ruta:
            return None
        try:
            return (pathlib.Path(base) / ruta).read_text()
        except OSError:
            return None

    def leer(ruta):
        try:
            return (raiz / ruta).read_text() if raiz else None
        except OSError:
            return None

    enunciados = sorted((raiz / "tareas").glob(f"{args.tarea}-*.md")) if raiz and (raiz / "tareas").is_dir() else []
    borr = (raiz / ".metricas" / "borrador-aceptado" / args.tarea) if raiz else None
    borrador = None
    if borr and borr.is_dir():
        partes = [f"# {p.relative_to(borr)}\n{p.read_text()}" for p in sorted(borr.rglob("*.py"))]
        borrador = "\n\n".join(partes) or None

    cuando = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registro = {
        "id": hashlib.sha256(f"{args.tarea}|{args.test}|{cuando}".encode()).hexdigest()[:16],
        "cuando": cuando,
        "tarea": args.tarea,
        "archivo_de_test": args.test,
        "clase": args.clase,
        "veredicto": args.veredicto,
        "motivo": args.motivo or None,
        "dimensiones": dims,
        "enunciado": enunciados[0].read_text() if enunciados else None,
        "test": leer_de(args.desde, args.test) or leer(args.test),
        "borrador_descartado": borrador,
    }
    try:
        destino = pathlib.Path(args.destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("a") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
