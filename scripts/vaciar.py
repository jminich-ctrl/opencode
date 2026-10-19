#!/usr/bin/env python3
"""El brazo nulo del validador de tests: vacía los cuerpos y exige que el test FALLE.

Los tres pasos del validador preguntan «¿este test distingue ESTE cambio?»: falla sin la
implementación, pasa con ella, y los mutantes mueren. Ninguno pregunta lo anterior:
**¿distingue algo de nada?**

Pasó, y es lo que motivó esto. El test aceptado de T04b tenía cinco pruebas y las cinco
negativas —token inválido, vacío, nulo, mal formado, id inexistente— y ninguna verificaba que
un token válido devolviera el id, que era el criterio de la tarea. Pasó los tres pasos: falla
sin la implementación (por `ImportError`), pasa con la del agente, y los mutantes mueren sobre
la lógica de ésa. Pero `def usuario_desde_token(token): return None` pasa los cinco.

Un test que un stub satisface no verifica nada, y el método se enteraba sólo si alguien lo
leía. `experimentos/README.md` ya exige un brazo nulo para los experimentos —el sujeto
reemplazado por un no-op, rojo obligatorio— por exactamente este motivo. Esto es el mismo
control, en el lugar donde más barato sale.

Uso:
    python3 scripts/vaciar.py archivo.py [archivo2.py ...]      # vacía en el lugar
    python3 scripts/vaciar.py --restaurar                        # devuelve los originales

Vacía SÓLO los cuerpos de funciones y métodos: deja imports, firmas, clases y constantes de
módulo, para que el test siga pudiendo importar. Si lo que rompe es el import, el rojo no
distingue nada —es el mismo rojo del paso 1— y el chequeo no serviría.
"""
import ast
import pathlib
import shutil
import sys

SUFIJO = ".vaciar-original"


def vaciar_fuente(texto: str) -> tuple[str, int]:
    """Devuelve (fuente con los cuerpos vaciados, cuántas funciones se vaciaron)."""
    arbol = ast.parse(texto)
    n = 0

    class Vaciador(ast.NodeTransformer):
        def _vaciar(self, nodo):
            self.generic_visit(nodo)
            nonlocal n
            # El docstring se conserva: vaciar no es borrar la intención.
            doc = None
            if (nodo.body and isinstance(nodo.body[0], ast.Expr)
                    and isinstance(nodo.body[0].value, ast.Constant)
                    and isinstance(nodo.body[0].value.value, str)):
                doc = nodo.body[0]
            nuevo = ([doc] if doc else []) + [ast.Return(value=ast.Constant(value=None))]
            if len(nodo.body) == len(nuevo) and isinstance(nodo.body[-1], ast.Return) \
                    and isinstance(getattr(nodo.body[-1], "value", None), ast.Constant) \
                    and nodo.body[-1].value.value is None:
                return nodo          # ya era un stub: no cuenta
            nodo.body = nuevo
            n += 1
            return nodo

        visit_FunctionDef = _vaciar
        visit_AsyncFunctionDef = _vaciar

    arbol = Vaciador().visit(arbol)
    ast.fix_missing_locations(arbol)
    return ast.unparse(arbol) + "\n", n


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    if args[0] == "--restaurar":
        n = 0
        for orig in pathlib.Path(".").rglob(f"*{SUFIJO}"):
            destino = orig.with_suffix("")
            # `with_suffix("")` saca sólo el último sufijo: reconstruyo el nombre a mano.
            destino = pathlib.Path(str(orig)[: -len(SUFIJO)])
            shutil.move(str(orig), str(destino))
            n += 1
        print(f"restaurados: {n}")
        return 0

    total = 0
    for ruta in args:
        p = pathlib.Path(ruta)
        if not p.is_file() or p.suffix != ".py":
            continue
        texto = p.read_text()
        try:
            vaciado, n = vaciar_fuente(texto)
        except SyntaxError as e:
            print(f"  ⊘ {ruta}: no parsea ({e.msg}); no lo vacío", file=sys.stderr)
            continue
        if not n:
            continue
        shutil.copy(str(p), str(p) + SUFIJO)
        p.write_text(vaciado)
        total += n
        print(f"  · {ruta}: {n} función/es vaciada/s")
    # Sin funciones que vaciar no hay brazo nulo posible: que el llamador lo sepa.
    if not total:
        print("  ⊘ no había funciones que vaciar", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
