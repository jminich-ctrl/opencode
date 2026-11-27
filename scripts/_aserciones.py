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


# ── ¿Alguna aserción FIJA UN VALOR? ──────────────────────────────────────────────────────
#
# Segundo modo, `--exige-valor`, y existe por una medición: el 2026-10-29, midiendo la FPR del
# validador con verdad de terreno, el test degradado «flojo» —`assertIsNotNone(responder1())`,
# una sola aserción de existencia— FUE ACEPTADO en T01c. Los cinco pasos lo dejaron pasar así:
#
#     ✓ falla sin la implementación      (el import revienta)
#     ✓ pasa con la implementación
#     ⊘ no hubo nada que mutar bajo «src/rutas»
#     ✓ el brazo nulo falla              (cuerpo vacío devuelve None, y None ES None)
#
# O sea: cuando `mutar.py` no tiene operadores que mutar —`return {"valor": calcular1()}` no
# tiene aritmética ni comparaciones— el gate pierde su ÚNICA defensa contra una aserción floja,
# y el brazo nulo no lo cubre porque la no-nulidad distingue «algo» de «nada» de verdad.
#
# La regla es exacta y no hace falta correr nada: una aserción fija un valor si compara contra
# algo —la familia `assertEqual`, un `assert` con un `Compare`, un `assertRaises` con su
# excepción—. Si TODAS las aserciones del test son de existencia —`assertIsNotNone`,
# `assertTrue(f())`, `assertIsInstance`— el test no dice qué tiene que devolver el producto.
#
# No se usa por omisión: muerde sólo donde el paso que discrimina no pudo correr. Un test
# legítimo puede tener una aserción de existencia entre varias, y rechazarlo ahí sería el
# chequeo que muerde al honesto y se apaga a la semana.
EXISTENCIA = {"assertIsNotNone", "assertIsNone", "assertTrue", "assertFalse",
              "assertIsInstance", "assertNotIsInstance"}


def fija_valor(funcion):
    """¿Hay al menos una aserción que compare contra algo?"""
    for x in ast.walk(funcion):
        if isinstance(x, ast.Assert):
            if any(isinstance(y, ast.Compare) for y in ast.walk(x.test)):
                return True
        if isinstance(x, ast.Call):
            nombre = getattr(x.func, "attr", "")
            if nombre in DE_DOS:
                return True
            if nombre in ("assertRaises", "assertRaisesRegex", "assertWarns") and x.args:
                return True
            # `assertTrue(f() == 5)` sí fija un valor: lo que no fija es `assertTrue(f())`.
            if nombre in EXISTENCIA and any(
                    isinstance(y, ast.Compare) for a in x.args for y in ast.walk(a)):
                return True
    return False


def sin_valor_en(arbol):
    """Los tests del archivo cuyas aserciones son todas de existencia."""
    flojos = []
    for n in ast.walk(arbol):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
            tiene = any(isinstance(x, ast.Assert)
                        or (isinstance(x, ast.Call) and getattr(x.func, "attr", "").startswith("assert"))
                        for x in ast.walk(n))
            if tiene and not fija_valor(n):
                flojos.append((n.lineno, n.name))
    return flojos


def exigir_valor(archivos):
    """Códigos: 0 fija un valor, 1 todas de existencia, 2 no pude mirar, 3 no aplica."""
    if not archivos:
        print("  ⊘ no me pasaron ningún archivo: no inspeccioné nada.")
        print("     No es un pase: nadie verificó si alguna aserción fija un valor.")
        return 2
    flojos, mirados, ajenos_v = [], 0, []
    for a in archivos:
        p = pathlib.Path(a)
        if p.exists() and p.suffix != ".py":
            ajenos_v.append(f"{a}: {p.suffix or 'sin extensión'}, no es Python")
            continue
        if not p.exists():
            print(f"  ⊘ {a}: no existe — no pudo verificarse")
            continue
        try:
            arbol = ast.parse(p.read_text())
        except SyntaxError as e:
            print(f"  ⊘ {a}: no pude leer el árbol sintáctico ({e.msg} en la línea {e.lineno})")
            continue
        mirados += 1
        flojos += [(p, linea, fn) for linea, fn in sin_valor_en(arbol)]
    if mirados == 0 and ajenos_v:
        print("  ⊘ este chequeo lee Python y no le pasaron ningún archivo Python:")
        for m in ajenos_v:
            print(f"     → {m}")
        print("     NO APLICA. La fuerza de esas aserciones sigue sin verificar.")
        return 3
    if mirados == 0:
        print("     No es un pase: «no pude leer el test» y «el test está bien» no son lo mismo.")
        return 2
    if not flojos:
        print("  ✓ alguna aserción fija un valor, no sólo la existencia del resultado")
        return 0
    print("  ✗ el test sólo afirma que el resultado EXISTE, y el paso que discrimina no pudo correr:")
    for p, linea, fn in flojos[:6]:
        print(f"     → {p}:{linea}  en {fn}()")
    print("     Sin mutantes que matar, una aserción de existencia da verde contra cualquier")
    print("     implementación que devuelva algo. Afirmá QUÉ tiene que devolver:")
    print("     `assertEqual(responder1(), {\"valor\": 50})` en vez de `assertIsNotNone(...)`.")
    return 1


def main(archivos):
    """Códigos: 0 limpio, 1 hay aserciones vacuas, 2 NO PUDE MIRAR.

    El 2 existe desde el 2026-10-26. Antes este chequeo devolvía 0 y silencio en cuatro
    situaciones: sin argumentos, con un archivo que no existe, con uno que no es `.py` y con
    uno que no parsea —un test a medio escribir—. Las cuatro se leían igual que «lo miré y
    está limpio», porque en el caso limpio tampoco imprimía nada. Sus hermanos del método,
    `_imports.py` y `_suprimidas.py`, imprimen su testigo: éste era el único mudo, y lo
    encontró un barrido que le preguntó a cada chequeo qué informa cuando no tiene material.
    """
    malos, mirados, no_pude, ajenos, aserciones = [], 0, [], [], 0
    for a in archivos:
        p = pathlib.Path(a)
        if not p.exists():
            no_pude.append(f"{a}: no existe")
            continue
        if p.suffix != ".py":
            # NO es «no pude»: este analizador lee Python y el archivo es de otro lenguaje.
            # La diferencia decide el veredicto, y hasta el 2026-11-27 no existía: ver el
            # comentario de `AJENO` abajo.
            ajenos.append(f"{a}: {p.suffix or 'sin extensión'}, no es Python")
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
    # ── «NO APLICA» no es «NO PUDE». El código 3, y lo que costó no tenerlo.
    #
    # Medido el 2026-11-27 en la corrida de clasificados: las tres tareas de frontend —T32,
    # T33, T34— murieron en punto muerto con este rojo:
    #
    #   ✗ _aserciones.py no pudo correr (rc=2): el chequeo no se puede saltear
    #      ⊘ frontend/tests/test_index_html_frontend.test.ts: no es un .py
    #
    # Dos intentos cada una, seis corridas de agente, por un motivo que NINGÚN agente puede
    # arreglar: un `.test.ts` no va a ser un `.py` nunca. Y viola la regla que el método se
    # puso: un rojo que no se le puede atribuir al agente es un defecto NUESTRO.
    #
    # Lo que no se toca —y está en EMPEZAR.md como algo que no hay que tocar— es que un
    # chequeo que no pudo ejecutarse dé ROJO: eso salió de un falso verde real. Lo que
    # faltaba es la otra mitad: un chequeo que no APLICA no es un chequeo que falló. Un
    # archivo que no existe o que no parsea es «no pude» y sigue siendo rojo; un archivo de
    # otro lenguaje es «no aplica», se declina y se dice cuál.
    #
    # El 3 no es un número nuevo del método: es el mismo contrato que ya usan `smoke.sh`
    # («este proyecto declara que no tiene nada que levantar») y `correr-suite.sh`. Quien
    # llama lo lee como ⊘ declinado, no como pase.
    if ajenos and mirados == 0 and not no_pude:
        print("  ⊘ este chequeo lee Python y no le pasaron ningún archivo Python:")
        for m in ajenos:
            print(f"     → {m}")
        print("     NO APLICA, que no es lo mismo que «no pude»: no hay nada que este")
        print("     analizador pueda decir sobre un test de otro lenguaje. Lo que ese test")
        print("     afirma sigue SIN verificar — hace falta un analizador para su lenguaje.")
        return 3
    if (no_pude or ajenos) and mirados == 0:
        print("  ⊘ no pude mirar ninguno de los archivos que me pasaron:")
        for m in no_pude + ajenos:
            print(f"     → {m}")
        print("     No es un pase: «no pude leer el test» y «el test está bien» no son lo mismo.")
        return 2
    for m in no_pude + ajenos:
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
    if sys.argv[1:2] == ["--exige-valor"]:
        sys.exit(exigir_valor(sys.argv[2:]))
    sys.exit(main(sys.argv[1:]))
