#!/usr/bin/env python3
"""¿Hay alguna implementación con la que este test falle? Si no, no es un test.

Los cinco pasos con que el método valida un test preguntan si distingue: sin la
implementación, con ella, mutada, y con los cuerpos vacíos. Los cuatro comparan el test
contra **versiones del producto**, y por eso ninguno ve el test que no mira el producto en
absoluto. Medido el 2026-10-25 en T26 de clasificados, aceptado como uno de los tres tests
de la tarea:

    password = "mi_password_segura"
    expected_hash = hashlib.sha256(password.encode()).hexdigest()
    assert expected_hash == hashlib.sha256(password.encode()).hexdigest()

Los dos lados son la misma expresión. No hay implementación —ninguna, nunca— con la que
eso falle. Pasó «falla sin la implementación» porque sus compañeros de archivo importan el
módulo y el import es lo que revienta; pasó el brazo nulo por lo mismo. Y se llamaba
`test_insert_user_hashea_con_sha256`, afirmando justo lo contrario de lo que la
implementación documenta —que el hasheo es del servicio y no de la capa de datos—, así que
leerlo por encima tranquilizaba.

La regla es exacta y no hace falta correr nada:

    un `assert` cuyos dos lados son el MISMO árbol —resueltas las variables locales que no
    pudieron cambiar en el medio— y que no menciona nada importado del propio repo, no
    puede fallar bajo ninguna implementación.

Las dos condiciones son necesarias. Sin la primera no hay tautología. Sin la segunda se
marcarían los tests legítimos de idempotencia —`assert f(x) == f(x)` sobre una función del
producto es una afirmación de verdad sobre el producto—, y un chequeo que muerde al test
honesto se apaga a la semana.

La resolución de variables exige que entre la asignación y el `assert` no haya ninguna
llamada: `antes = contar()` … `borrar()` … `assert contar() == antes` es un test legítimo
de que algo NO cambió, y los dos lados son el mismo árbol. Lo que lo distingue es que en el
medio pasó algo.

  python3 scripts/_aserciones.py tests/test_x.py        # sale 1 si hay alguna vacua
"""
import ast
import pathlib
import sys

# `assertX(a, b)` de unittest que afirman una relación entre sus dos primeros argumentos.
DE_DOS = {"assertEqual", "assertEquals", "assertNotEqual", "assertIs", "assertIsNot",
          "assertAlmostEqual", "assertListEqual", "assertDictEqual", "assertSetEqual",
          "assertCountEqual", "assertTupleEqual", "assertMultiLineEqual", "assertGreater",
          "assertLess", "assertGreaterEqual", "assertLessEqual", "assertIn", "assertNotIn"}


def raiz_del_repo(desde):
    d = pathlib.Path(desde).resolve()
    for p in [d] + list(d.parents):
        if (p / ".git").exists():
            return p
    return d.parent


def nombres_del_producto(arbol, raiz):
    """Los nombres que el test trajo de un módulo que vive en este repo.

    Un `import hashlib` no está en el repo; un `from backend.app.servicios.register import
    crear_usuario` sí. La distinción es lo único que separa la tautología del test de
    idempotencia, y se resuelve mirando el disco en vez de adivinar por el nombre.
    """
    propios = set()

    def es_del_repo(mod):
        if not mod:
            return False
        base = mod.replace(".", "/")
        return (raiz / (base + ".py")).exists() or (raiz / base / "__init__.py").exists()

    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            for a in n.names:
                if es_del_repo(a.name):
                    propios.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            if es_del_repo(n.module):
                for a in n.names:
                    propios.add(a.asname or a.name)
                if n.module:
                    propios.add(n.module.split(".")[0])
    return propios


def menciona(nodo, nombres):
    return any(isinstance(x, ast.Name) and x.id in nombres for x in ast.walk(nodo))


def neutral(nodo, propios):
    """¿La expresión no toca nada escrito a propósito?

    `hashlib.sha256(x)` repetido a los dos lados es una tautología. `self.huella(d)`
    repetido a los dos lados NO lo es: es la afirmación «la huella es estable», y la suite
    del método tiene dos tests que dicen exactamente eso. La diferencia es si la expresión
    llama a algo que alguien escribió —el producto, un ayudante del propio archivo de test,
    un método de `self`— o sólo a la biblioteca.

    Sin esta distinción el chequeo muerde al test honesto, y un chequeo que muerde al test
    honesto se apaga a la semana. Lo midieron los 2 falsos positivos de `pruebas/`.
    """
    return not menciona(nodo, propios | {"self", "cls"})


def resolver(nodo, asignadas):
    """Un `Name` local se reemplaza por la expresión que lo definió, si la hay."""
    if isinstance(nodo, ast.Name) and nodo.id in asignadas:
        return asignadas[nodo.id]
    return nodo


def pares(nodo):
    """Los dos lados que una aserción compara, o nada."""
    if isinstance(nodo, ast.Assert):
        t = nodo.test
        if isinstance(t, ast.Compare) and len(t.comparators) == 1:
            return t.left, t.comparators[0]
        return None
    if (isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Call)
            and getattr(nodo.value.func, "attr", "") in DE_DOS
            and len(nodo.value.args) >= 2):
        return nodo.value.args[0], nodo.value.args[1]
    return None


def vacuas_en(funcion, propios):
    """Recorre el cuerpo en orden: las asignaciones valen hasta que algo pueda cambiarlas."""
    hallazgos = []
    asignadas = {}
    for sentencia in funcion.body:
        par = pares(sentencia)
        if par:
            izq, der = (resolver(x, asignadas) for x in par)
            if ast.dump(izq) == ast.dump(der) and neutral(izq, propios):
                hallazgos.append((sentencia.lineno, ast.unparse(sentencia)[:110]))
        # Después de juzgar la sentencia, ver qué le deja a las que siguen. El orden es el
        # arreglo: primero se invalida y después se registra. Al revés —`if Assign … elif
        # Call`— una asignación que CONTIENE una llamada entraba por la primera rama y no
        # invalidaba nada, y `salida = correr(...)` es la forma más común que hay. Eran 4 de
        # los 6 falsos positivos sobre `pruebas/`: `antes = f.read_text()` … `correr(...)` …
        # `assertEqual(antes, f.read_text())` es un test legítimo de que algo NO cambió.
        if not par and any(isinstance(x, ast.Call) for x in ast.walk(sentencia)):
            # Algo se llamó: cualquier variable viva pudo cambiar de valor, y entonces los
            # dos lados iguales ya no son el mismo valor.
            asignadas.clear()
        if isinstance(sentencia, ast.Assign) and len(sentencia.targets) == 1 \
                and isinstance(sentencia.targets[0], ast.Name):
            asignadas[sentencia.targets[0].id] = sentencia.value
    return hallazgos


def main(archivos):
    """Códigos: 0 limpio, 1 hay aserciones vacuas, 2 NO PUDE MIRAR.

    El 2 existe desde el 2026-10-26. Antes este chequeo devolvía 0 y silencio en cuatro
    situaciones: sin argumentos, con un archivo que no existe, con uno que no es `.py` y con
    uno que no parsea —un test a medio escribir—. Las cuatro se leían igual que «lo miré y
    está limpio», porque en el caso limpio tampoco imprimía nada. Sus hermanos del método,
    `_imports.py` y `_suprimidas.py`, imprimen su testigo: éste era el único mudo, y lo
    encontró un barrido que le preguntó a cada chequeo qué informa cuando no tiene material.
    """
    malos, mirados, no_pude, aserciones = [], 0, [], 0
    for a in archivos:
        p = pathlib.Path(a)
        if not p.exists():
            no_pude.append(f"{a}: no existe")
            continue
        if p.suffix != ".py":
            no_pude.append(f"{a}: no es un .py")
            continue
        try:
            arbol = ast.parse(p.read_text())
        except SyntaxError as e:
            no_pude.append(f"{a}: no pude leer el árbol sintáctico ({e.msg} en la línea {e.lineno})")
            continue
        mirados += 1
        propios = nombres_del_producto(arbol, raiz_del_repo(p))
        for n in ast.walk(arbol):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and n.name.startswith("test"):
                aserciones += sum(1 for x in ast.walk(n)
                                  if isinstance(x, ast.Assert)
                                  or (isinstance(x, ast.Call)
                                      and getattr(x.func, "attr", "").startswith("assert")))
                for linea, texto in vacuas_en(n, propios):
                    malos.append((p, n.name, linea, texto))
    if not archivos:
        print("  ⊘ no me pasaron ningún archivo: no inspeccioné nada.")
        print("     No es un pase: nadie verificó si las aserciones pueden fallar.")
        return 2
    if no_pude and mirados == 0:
        print("  ⊘ no pude mirar ninguno de los archivos que me pasaron:")
        for m in no_pude:
            print(f"     → {m}")
        print("     No es un pase: «no pude leer el test» y «el test está bien» no son lo mismo.")
        return 2
    for m in no_pude:
        print(f"  ⊘ {m} — no pudo verificarse")
    if not malos:
        print("  ✓ ninguna aserción es vacua por construcción")
        print(f"     · inspeccionó: {mirados} archivo(s), {aserciones} aserción/es")
        return 0
    print("  ✗ hay aserciones que no pueden fallar con NINGUNA implementación:")
    for p, fn, linea, texto in malos[:6]:
        print(f"     → {p}:{linea}  en {fn}()   {texto}")
    print("     Los dos lados son la misma expresión y no nombran nada del producto.")
    print("     Un test así da verde contra cualquier código, incluso contra código ausente.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
