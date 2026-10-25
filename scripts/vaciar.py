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


def vaciar_fuente(texto: str) -> tuple[str, int, list]:
    """Devuelve (fuente con los cuerpos vaciados, cuántas se vaciaron, cuáles YA eran stub).

    La tercera es el hallazgo, y el método la tiraba. Esta función siempre supo reconocer el
    stub —el comentario decía «ya era un stub: no cuenta»— y de ese reconocimiento sacaba la
    conclusión opuesta a la correcta: lo descartaba del conteo. Una función que ya devuelve
    None sin hacer nada no es una implementación que el brazo nulo no pueda juzgar; es el
    veredicto.

    Medido el 2026-10-25 en T04 de clasificados, cerrada como ✅ hecha:

        def read_user_by_email(email: str) -> dict | None:
            '''El usuario como dict con al menos `id`, `email` y `password_hash`, o None.'''
            # Esta implementación sería con una conexión a base de datos real
            # Por ahora retornamos None como placeholder
            return None

    Vaciar ese archivo no cambia nada —`vaciar.py` decía «no había funciones que vaciar»— y
    el brazo nulo igual daba verde, porque vaciaba los TRES archivos de la tarea juntos y
    los otros dos sí rompían el test. Con ese stub el login de clasificados no puede
    funcionar para ningún usuario, y la tarea está cerrada.
    """
    arbol = ast.parse(texto)
    n = 0
    stubs = []

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
                stubs.append(nodo.name)   # ya era un stub: ESO es el hallazgo
                return nodo
            nodo.body = nuevo
            n += 1
            return nodo

        visit_FunctionDef = _vaciar
        visit_AsyncFunctionDef = _vaciar

    arbol = Vaciador().visit(arbol)
    ast.fix_missing_locations(arbol)
    return ast.unparse(arbol) + "\n", n, stubs


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
    stubs_vistos = []
    for ruta in args:
        p = pathlib.Path(ruta)
        if not p.is_file() or p.suffix != ".py":
            continue
        texto = p.read_text()
        try:
            vaciado, n, stubs = vaciar_fuente(texto)
        except SyntaxError as e:
            print(f"  ⊘ {ruta}: no parsea ({e.msg}); no lo vacío", file=sys.stderr)
            continue
        if stubs and not n:
            # ROJO sólo cuando el archivo no tiene NINGUNA función con cuerpo: entonces no es
            # «tiene un stub», es «no implementa nada». Medido el 2026-10-25 sobre los dos
            # proyectos ejemplo: un solo archivo así, el `users.py` de T04, y es el defecto.
            #
            # La distinción no es un ablande. Vaciando también el `.venv` de clasificados
            # aparecen 16 archivos con funciones que devuelven None y las 16 son legítimas
            # —clases base que la subclase sobreescribe, shims de compatibilidad— y las 16
            # viven rodeadas de decenas de funciones con cuerpo. Sin esta condición el
            # chequeo marcaría la primera clase base que una tarea escriba.
            #
            # No es degradar un rojo por su compañía, que es un defecto que este método ya
            # cerró: el sujeto es otro. «Este archivo no implementa nada» y «esta función de
            # diez está vacía» son dos afirmaciones distintas, y la segunda la contesta el
            # brazo nulo archivo por archivo, que ahora sí corre.
            stubs_vistos.append((ruta, stubs))
            print(f"  ✗ {ruta}: NO implementa nada. Sus {len(stubs)} función/es devuelven"
                  f" None sin hacer nada: {', '.join(stubs)}")
        elif stubs:
            print(f"  ⚠ {ruta}: {len(stubs)} función/es devuelven None sin hacer nada"
                  f" ({', '.join(stubs)}), pero el archivo tiene {n} con cuerpo."
                  f" Lo decide el brazo nulo de este archivo.")
        if not n:
            continue
        shutil.copy(str(p), str(p) + SUFIJO)
        p.write_text(vaciado)
        total += n
        print(f"  · {ruta}: {n} función/es vaciada/s")
    # Un stub entre los archivos que la tarea declara es un veredicto, no un detalle: el
    # brazo nulo no puede distinguir «vacío» de «vacío», y antes esto se iba por el ⊘.
    # El código es 3 para que el llamador no lo confunda con «no se pudo preguntar».
    if stubs_vistos:
        return 3
    # Sin funciones que vaciar no hay brazo nulo posible: que el llamador lo sepa.
    if not total:
        print("  ⊘ no había funciones que vaciar", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
