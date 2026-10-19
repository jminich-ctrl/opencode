#!/usr/bin/env python3
"""Banco de razonamiento hecho con NUESTRAS fallas reales, no con un banco público.

Cada ítem es un caso que ocurrió de verdad en las últimas 30 horas, cuyo diagnóstico
correcto conocemos porque lo verificamos. Se puntea por palabra clave: no mide prosa, mide
si llegó a la causa.

Por qué estos y no un benchmark: miden el razonamiento que el método necesita —leer un
error y decir dónde está la causa— sobre el código y las convenciones de este proyecto.
Un modelo puede saber Python y no saber esto.

LÍMITE QUE QUEDA EN PIE: si un modelo escribe su pensamiento en `content` sin ninguna
etiqueta que lo delimite, no hay forma de separarlo de la respuesta y el regex vuelve a
puntuar pensamiento. Eso no se arregla acá: se arregla pidiendo un diff y puntuándolo con
`git apply` + el gate, que es lo que hace experimentos/memoria-verificada.md. Este banco
ordena y descarta candidatos; no decide entre dos modelos que queden cerca.
"""
import json, os, re, sys, urllib.request
BASE=os.environ["COLABHIVE_BASE_URL"].rstrip("/"); CLAVE=os.environ["COLABHIVE_API_KEY"]

CASOS = [
 ("import-fastapi",
  "Un test falla con: ImportError: cannot import name 'RequestValidationError' from 'fastapi'. "
  "El código dice `from fastapi import FastAPI, RequestValidationError`. ¿Cuál es el arreglo exacto? Respondé en una línea.",
  r"fastapi\.exceptions"),
 ("app-nueva",
  "Un test de FastAPI crea `app = FastAPI()` adentro del propio test y después verifica que "
  "un POST inválido devuelva 400. La aplicación real registra el manejador de errores en "
  "app/main.py. El test falla con 422. ¿Por qué no puede pasar nunca? Una línea.",
  r"(nueva|otra|distinta|propia).{0,40}(app|instancia)|no.{0,20}(tiene|registra).{0,30}manejador|import.{0,20}main"),
 ("ruta-absoluta",
  "Un test contiene la línea: down_file = '/Users/jose/tests-T03/proyecto/backend/migraciones/001.sql'. "
  "Pasó cuando se escribió y falla desde entonces en todos lados. ¿Por qué? Una línea.",
  r"(ruta|path).{0,20}absolut|worktree|(sólo|solo).{0,30}(esa|aquella|la).{0,20}(máquina|maquina|carpeta|directorio)"),
 ("test-vs-plan",
  "El plan cierra el esquema como `categorias (id PK, nombre UNIQUE, orden)`. El SQL escribe "
  "`nombre VARCHAR(255) UNIQUE NOT NULL`. El test afirma `'nombre VARCHAR(255) NOT NULL' in sql` y falla. "
  "¿Quién está mal, el SQL o el test? Una línea con el motivo.",
  r"\btest\b.{0,60}(mal|equivocad|incorrect)|el test"),
 ("directorio-vacio",
  "Un test verifica que exista el directorio backend/app/datos. Pasa en el worktree del agente "
  "y falla en el tronco después del merge. ¿Por qué? Una línea.",
  r"git.{0,30}(no|nunca).{0,30}(versiona|guarda|trackea).{0,20}(directorio|carpeta)|directorio.{0,20}vac"),
 ("contexto-400",
  "Un agente muere con: This model's maximum context length is 5312 tokens, your prompt contains 6195. "
  "La config declara limit.context 128000, copiado de la ficha del modelo. ¿Dónde está el error? Una línea.",
  r"(ficha|nominal|declarad).{0,60}(no|distint)|endpoint|servid|max_model_len|config.{0,30}(mal|incorrect|mentir)"),
]

def preguntar(mid, pregunta):
    c={"model":mid,"stream":True,"max_tokens":300,"temperature":0,
       "messages":[{"role":"system","content":"Sos un ingeniero que diagnostica fallas. Respondé en UNA línea, concreto, sin rodeos."},
                   {"role":"user","content":pregunta}]}
    rq=urllib.request.Request(f"{BASE}/chat/completions",data=json.dumps(c).encode(),
        headers={"Authorization":f"Bearer {CLAVE}","Content-Type":"application/json"})
    # El campo que se lee es `content` Y NADA MÁS. La versión anterior concatenaba
    # `content` + `reasoning` + `reasoning_content` y le pasaba la mezcla al regex: eso
    # puntúa la cadena de pensamiento, que REFORMULA LA PREGUNTA y por eso contiene las
    # palabras clave que el patrón busca. Daba ✓ a razonamientos que terminaban en una
    # respuesta equivocada, e invalidó la campaña entera de dos modelos. Ver MEDICION.md §1.6.
    cont=[]; razon=[]
    try:
        with urllib.request.urlopen(rq,timeout=600) as r:
            for l in r:
                s=l.decode("utf-8","replace").strip()
                if not s.startswith("data: ") or s[6:]=="[DONE]": continue
                try: d=json.loads(s[6:])
                except Exception: continue
                for ch in d.get("choices") or []:
                    de=ch.get("delta") or {}
                    if de.get("content"): cont.append(de["content"])
                    for k in ("reasoning","reasoning_content"):
                        if de.get(k): razon.append(de[k])
    except Exception as e:
        return f"__ERROR__ {type(e).__name__}"
    return limpiar("".join(cont))


def limpiar(txt):
    """Saca el pensamiento que el modelo metió DENTRO de `content`.

    Qwen3.8-27B emite su cadena de pensamiento en `content` con `reasoning` vacío, y encima
    declara `"reasoning": false` en su config. Puntuar eso es puntuar el pensamiento aunque
    se haya leído el campo correcto, así que el corte por `</think>` no es cosmético: es
    parte de leer la respuesta. Si no queda nada después del corte, no hubo respuesta (⊘).
    """
    for cierre in ("</think>", "</thinking>", "</reasoning>"):
        if cierre in txt:
            txt = txt.rsplit(cierre, 1)[1]
    # Un bloque abierto que nunca cerró = se truncó pensando: no hay respuesta.
    for apertura in ("<think>", "<thinking>"):
        if apertura in txt:
            return ""
    return txt.strip()

# Una corrida por caso no alcanza para ordenar dos modelos: la MISMA petición a
# temperature 0 produjo un tool_call una vez y prosa la siguiente. El éxito por corrida es
# estocástico, así que el caso se resuelve por MAYORÍA de REPS corridas.
REPS=int(os.environ.get("REPS","3"))

def una(mid,preg,patron):
    """Una corrida → '✓', '✗' o '⊘'. Vacío no es equivocado: es un chequeo que no corrió."""
    # Reintento único: el primer caso de una tanda lo falló por estar el modelo frío, no por
    # razonar mal, y eso convirtió un modelo que contesta bien en 1 de 6.
    r=preguntar(mid,preg)
    if r.startswith("__ERROR__") or not r.strip():
        r=preguntar(mid,preg)
    if r.startswith("__ERROR__") or not r.strip():
        return "⊘"
    return "✓" if re.search(patron, r, re.I) else "✗"

def resolver(reps):
    """Las REPS corridas de un caso → ('✓'|'✗'|'⊘', ¿fue inestable?).

    Está acá y no dentro del bucle por el mismo motivo que la campaña corre bajo `__main__`:
    la regla de agregación decide el resultado de cada caso, así que es parte del corrector y
    tiene que poder probarse sin gastar una campaña.

    ⊘ **sólo** si la MAYORÍA no pudo contestar. Un modelo que contesta 2 de 3 veces sí se
    midió, y marcarlo ⊘ es el error que hace pasar a todos: tirar los datos de los sujetos
    peor comportados en vez de reprobarlos (ver MEDICION.md §4, «el espejo»).
    """
    val = [x for x in reps if x != "⊘"]
    if len(val) * 2 <= len(reps):
        return "⊘", False
    # La inestabilidad es métrica de primera clase, no ruido a promediar: un modelo que acierta
    # los mismos casos siempre es mejor compañero que uno que varía, porque el segundo rompe el
    # presupuesto de reintentos de correr-plan.sh.
    return ("✓" if val.count("✓") * 2 > len(val) else "✗"), len(set(val)) > 1


# La campaña corre bajo `__main__` y no al importar: el corrector tiene que poder
# probarse sin lanzar la campaña. Un instrumento que sólo se puede ejercitar
# corriéndolo entero no se valida nunca.
# El espejo del control positivo: un sujeto que se sabe MALO, que tiene que volver FALLA.
#
# Un control positivo prueba que el corrector puede aprobar. Éste prueba que puede REPROBAR,
# que es la mitad que faltaba — y la que hace pasar a todos cuando falta. Está medido: GLM-4.7
# contestó vacío 6 de 6 y DESAPARECIÓ de la tabla de razonamiento que publicamos, en vez de
# sacar 0. El camino del ⊘ lo volvió invisible, y el modelo peor comportado se fue del ranking.
#
# Se pasa como MALO_CONOCIDO=<id>. Si la respuesta de ese sujeto no es ✗ en el primer caso, el
# banco no corre: un instrumento que no puede reprobar a nadie no mide nada.
def control_negativo(mid):
    clave, preg, patron = CASOS[0]
    r = una(mid, preg, patron)
    if r != "✗":
        sys.exit(f"  ✗ el control negativo dio «{r}» y tenía que dar ✗ sobre un sujeto que se\n"
                 f"    sabe malo ({mid[:8]}, caso {clave}). Un ⊘ acá significa que el corrector\n"
                 f"    no puede reprobar a nadie: el banco no corre. Ver MEDICION.md §4.")
    print(f"  · control negativo: {mid[:8]} reprobó como se esperaba ({clave})")


if __name__ == "__main__":
    if os.environ.get("MALO_CONOCIDO"):
        control_negativo(os.environ["MALO_CONOCIDO"])
    for linea in sys.argv[1:]:
        mid,nom=linea.split("=",1)
        aciertos=[]; inestables=[]
        for clave,preg,patron in CASOS:
            reps=[una(mid,preg,patron) for _ in range(REPS)]
            res,inestable=resolver(reps)
            aciertos.append(res)
            if inestable: inestables.append(clave)
        val=[a for a in aciertos if a!="⊘"]
        extra=""
        if "⊘" in aciertos: extra+=f"  (⊘ {aciertos.count('⊘')} sin respuesta)"
        if inestables: extra+=f"  (inestable: {', '.join(inestables)})"
        print(f"  {nom:26s} {' '.join(aciertos)}   {aciertos.count('✓')}/{len(val)}{extra}", flush=True)
    print("\n  casos: " + " ".join(c[0] for c in CASOS))
    print(f"  {REPS} corridas por caso, mayoría decide · se puntúa `content` sin el pensamiento")
    print("  6 casos ordenan y descartan; NO deciden entre dos modelos que queden cerca.")
