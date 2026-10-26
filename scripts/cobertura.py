#!/usr/bin/env python3
"""¿El plan cubre todo el encargo? La pregunta más cara de G0, como comando.

Es el error que más se repite y el único que no se ve leyendo el plan: una funcionalidad
que falta no está en ninguna línea. En el plan de clasificados faltaba un tercio del
alcance y el plan se leía bien; después de corregirlo faltaba el registro de usuarios, y
eso también se leía bien.

Para que sea mecánico, el encargo declara sus requisitos con una clave:

    ## Requisitos
    - `login` — cuentas con login por cookie de sesión
    - `favoritos` — marcar avisos como favoritos
    - `publicar|crud` — crear un aviso   (varias formas de nombrarlo, separadas por |)

Y esto verifica que cada clave aparezca en la tabla de tareas del plan. Los acentos y la ñ
no importan. La clave la escribe la persona **una vez**, cuando escribe el encargo, que es
algo que iba a escribir igual.

  ENCARGO=OBJETIVO.md PLAN=PLAN.md python3 scripts/cobertura.py

## Enlaces con versión: que un requisito no se debilite en silencio

Lo de arriba responde «¿hay alguna tarea que lo nombre?». No responde la pregunta de un
bucle donde el arquitecto REESCRIBE el plan: «¿sigue siendo la misma cobertura que se
aprobó?». Un requisito puede debilitarse sin que falte nada:

  - el encargo decía «login por cookie de sesión» y ahora dice «login». La clave `login`
    sigue estando, alguna tarea la sigue nombrando, y el ✓ de ayer avala un requisito que
    ya no existe.
  - la clave desaparece del encargo entera. Nadie la extraña: este chequeo sólo miraba que
    lo declarado estuviera cubierto, así que borrar la declaración apaga el chequeo.
  - la tarea que lo cubría era T03 y ahora es T07 con otros archivos.

Así que el enlace se GUARDA con la huella de sus dos extremos, en `.cobertura.json`, y en
las corridas siguientes se compara. La idea no es nuestra: la industria la tiene como
*suspect link* —DOORS marca el enlace cuando un extremo cambia—. El corte en dos estados
sí es nuestro, porque las dos mitades piden acciones distintas:

  - `outdated`  — se movió el ENCARGO: el ✓ avala un requisito que ya no dice eso.  ✗ ROJO
  - `borrado`   — la clave ya no está en el encargo y el enlace quedó colgando.     ✗ ROJO
  - `predated`  — se movió el PLAN: lo cubren otras tareas que las aprobadas.       · aviso

**Por qué `predated` es aviso y no rojo**, que es la decisión entera de este diseño:
`planificar.sh` le devuelve al arquitecto las líneas `✗` como problemas a corregir y el
bucle cierra cuando no queda ninguna. El arquitecto reescribe el plan — es su trabajo —, así
que un ✗ en el lado del plan dispararía en CADA iteración y el bucle no cerraría nunca. El
método ya tiene la distinción escrita en ese mismo archivo: «Sólo los ✗ son problemas: los
avisos los resuelve quien revisa, no el arquitecto». El lado del encargo no se mueve durante
el bucle, y por eso ése sí puede ser rojo.

Y el enlace **no se re-bendice solo**: si se actualizara en cada corrida, la comparación
siempre daría «igual» y el chequeo sería decoración — el mismo riesgo que INVESTIGACION.md
le marca al bucle de G0. Dos modos, y la diferencia es quién decide:

  RECORDAR=si-falta   registra sólo si no hay registro. Lo usa `correr-todo.sh`, DESPUÉS de
                      verificar la firma de G0: la primera corrida de un plan aprobado no
                      tiene nada contra qué comparar, y pedirle al humano que lo registre a
                      mano sería un paso que se olvida y deja el chequeo apagado.
  RECORDAR=1          registra siempre: es la re-bendición, y la decide una persona cuando
                      la cobertura se volvió a verificar. Queda en el diff del registro.

No se registra al final de `planificar.sh`: ahí el plan valida pero **todavía no está
aprobado** —lo firma una persona, HUMANO.md §1— y bendecir la cobertura de un plan sin
aprobar es registrar algo que nadie revisó.

  RECORDAR=1 ENCARGO=OBJETIVO.md PLAN=PLAN.md python3 scripts/cobertura.py
"""
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import unicodedata


def normalizar(t):
    """Sin acentos y en minúsculas: 'búsqueda' y 'busqueda' son la misma palabra, y
    escribir la clave con acento correcto no debería ser parte del trabajo."""
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")

ENCARGO = pathlib.Path(os.environ.get("ENCARGO", "OBJETIVO.md"))
PLAN = pathlib.Path(os.environ.get("PLAN", "PLAN.md"))
for f in (ENCARGO, PLAN):
    if not f.exists():
        print(f"  ✗ no existe {f}")
        sys.exit(1)

encargo = ENCARGO.read_text()
m = re.search(r"^##+ *Requisitos *$(.*?)(?=^##+ |\Z)", encargo, re.M | re.S)
if not m:
    print(f"  · {ENCARGO.name} no tiene sección «## Requisitos» con claves: no se puede")
    print(f"    verificar la cobertura. Es la única parte de G0 que se puede mecanizar;")
    print(f"    sin ella queda entera en manos de quien lea el plan.")
    sys.exit(0)

requisitos = re.findall(r"^\s*[-*] *`([^`]+)`(.*)$", m.group(1), re.M)
if not requisitos:
    print(f"  · la sección «## Requisitos» de {ENCARGO.name} no tiene claves entre backticks")
    sys.exit(0)

def huella(t):
    """Sobre texto NORMALIZADO y con los espacios colapsados: arreglarle un acento o
    realinear una tabla no es debilitar un requisito, y si disparara `outdated` por eso el
    aviso se volvería ruido y se terminaría apagando."""
    return hashlib.sha256(" ".join(normalizar(t).split()).encode()).hexdigest()[:12]


# Sólo las filas de la tabla de tareas: título y archivos. UNA POR UNA, no pegadas en un
# bloque: el enlace con versión necesita saber qué tarea cubre qué, y de paso el rojo de
# siempre ahora puede decirlo.
plan = PLAN.read_text()
filas = []
for linea in re.findall(r"^\|\s*T\d+[a-z]?\s*\|.*$", plan, re.M):
    ident = re.match(r"^\|\s*(T\d+[a-z]?)\s*\|", linea).group(1)
    filas.append((ident, linea))

faltan, cubren = [], {}
for clave, texto in requisitos:
    # Raíz, no palabra exacta: 'favorito' matchea 'favoritos' y 'favorites'. Y con `|`
    # se declaran varias formas de nombrar lo mismo: alcanza con que una aparezca.
    alias = [normalizar(a) for a in clave.split("|") if a.strip()]
    tocan = [(i, l) for i, l in filas if any(a in normalizar(l) for a in alias)]
    if not tocan:
        faltan.append((clave, texto.strip(" —-")))
    else:
        cubren[clave] = tocan

print(f"  {len(requisitos)} requisito(s) declarados en {ENCARGO.name}")
if faltan:
    print(f"  ✗ {len(faltan)} sin ninguna tarea que los cubra:")
    for clave, texto in faltan:
        print(f"     {clave}  {texto[:60]}")
else:
    print("  ✓ todos tienen al menos una tarea")

# ── Enlaces con versión ────────────────────────────────────────────────────────────────
REGISTRO = pathlib.Path(os.environ.get("REGISTRO_COBERTURA", ".cobertura.json"))
MODO = os.environ.get("RECORDAR", "")
RECORDAR = MODO == "1" or (MODO == "si-falta" and not REGISTRO.exists())
# Con RECORDAR=1 los estados se INFORMAN pero no son problemas pendientes: la decisión se
# está tomando en esta misma corrida. Y `planificar.sh` filtra por `✗` sin mirar el código de
# salida, así que un ✗ con código 0 le daría al arquitecto un problema que no existe.
MARCA = "·" if RECORDAR else "✗"
ROJO_ENLACES = False

ahora = {}
for clave, texto in requisitos:
    if clave not in cubren:
        continue                                  # ya lo dijo el rojo de arriba
    tocan = cubren[clave]
    ahora[clave] = {"requisito": huella(texto),
                    "plan": huella("\n".join(l for _, l in tocan)),
                    "tareas": [i for i, _ in tocan]}

antes, ilegible = {}, ""
if REGISTRO.exists():
    try:
        antes = json.loads(REGISTRO.read_text())["enlaces"]
    except Exception as e:                       # json roto, clave que no está, lo que sea
        ilegible = f"{type(e).__name__}: {e}"

if ilegible:
    # Ni rojo ni silencio. Rojo no, porque en el bucle el ✗ va al arquitecto y él no puede
    # arreglar un json roto. Silencio tampoco: un chequeo que no corrió y no lo dice es la
    # definición de decoración. Queda como aviso, que es de quien revisa.
    print(f"  · {REGISTRO.name} no se pudo leer ({ilegible}): los enlaces NO se verificaron")
elif antes:
    outdated, borrados, predated, nuevos = [], [], [], []
    for clave, guardado in sorted(antes.items()):
        if clave not in ahora:
            # Puede ser que lo borraron del encargo o que se quedó sin tarea que lo cubra; el
            # segundo caso ya lo dijo el rojo de arriba, así que acá se nombra el primero.
            borrados.append((clave, guardado))
        elif ahora[clave]["requisito"] != guardado.get("requisito"):
            outdated.append((clave, guardado))
        elif ahora[clave]["plan"] != guardado.get("plan"):
            predated.append((clave, guardado))
    nuevos = [c for c in ahora if c not in antes]

    print(f"  {len(antes)} enlace(s) guardados en {REGISTRO.name}")
    for clave, g in outdated:
        print(f"  {MARCA} outdated: el encargo reescribió `{clave}` después de aprobarse la")
        print(f"     cobertura. El ✓ de antes avala un requisito que ya no dice eso:")
        print(f"     tiene que volver a cubrirse, y lo decide quien planifica.")
    for clave, g in borrados:
        print(f"  {MARCA} borrado: `{clave}` ya no está en {ENCARGO.name} y su enlace quedó")
        print(f"     colgando (lo cubría {', '.join(g.get('tareas') or ['?'])}). Un requisito")
        print(f"     que se borra apaga su propio chequeo: si de verdad no va, el enlace")
        print(f"     se saca a mano y queda en el commit.")
    for clave, g in predated:
        print(f"  · predated: `{clave}` lo cubren otras tareas que las aprobadas "
              f"({', '.join(g.get('tareas') or ['?'])} → {', '.join(ahora[clave]['tareas'])})")
    if nuevos:
        print(f"  · {len(nuevos)} enlace(s) nuevos sin aprobar: {', '.join(sorted(nuevos))}")
    if not (outdated or borrados or predated or nuevos):
        print("  ✓ los enlaces siguen siendo los aprobados")
    # OJO: acá había un `sys.exit(1)`, y con él la re-bendición era INALCANZABLE — en cuanto
    # un requisito cambiaba, el script salía antes del bloque RECORDAR y el registro no se
    # podía actualizar nunca más. Un rojo permanente que no se puede sacar es el camino a
    # que alguien borre el chequeo; el método ya lo tiene escrito por el paso 7 de G4. El
    # veredicto se decide al final, una sola vez.
    ROJO_ENLACES = bool(outdated or borrados)
    if ROJO_ENLACES and not RECORDAR:
        # El rojo tiene que traer el comando que lo saca, o el único camino es borrar el
        # chequeo. La re-bendición es una decisión de persona; esto sólo la hace alcanzable.
        print(f"     Si la cobertura se volvió a verificar y sigue valiendo:")
        print(f"       RECORDAR=1 ENCARGO={ENCARGO.name} PLAN={PLAN.name} "
              f"python3 scripts/cobertura.py")
else:
    print(f"  · sin {REGISTRO.name}: no hay enlaces aprobados contra los que comparar")

if RECORDAR:
    if faltan:
        # Bendecir un plan al que le falta cobertura convierte el registro en una coartada.
        print(f"  ✗ no guardo los enlaces: hay {len(faltan)} requisito(s) sin cubrir")
        sys.exit(1)
    # Re-bendecir es una DECISIÓN, así que se dice cuál: queda en la salida y en el diff del
    # registro, que es lo único que después se puede auditar.
    if ROJO_ENLACES:
        print("  · re-bendiciendo enlaces que habían cambiado: eso es lo que RECORDAR=1 hace")
    REGISTRO.write_text(json.dumps(
        {"cuando": time.strftime("%Y-%m-%d %H:%M:%S"), "encargo": ENCARGO.name,
         "plan": PLAN.name, "enlaces": ahora}, ensure_ascii=False, indent=1) + "\n")
    print(f"  ✓ {len(ahora)} enlace(s) guardados en {REGISTRO.name} — commiteálo")
    sys.exit(0)        # la bendición ES el veredicto: lo que cambió quedó registrado

sys.exit(1 if faltan or ROJO_ENLACES else 0)
