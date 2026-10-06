#!/usr/bin/env python3
"""Banco de razonamiento hecho con NUESTRAS fallas reales, no con un banco público.

Cada ítem es un caso que ocurrió de verdad en las últimas 30 horas, cuyo diagnóstico
correcto conocemos porque lo verificamos. Se puntea por palabra clave: no mide prosa, mide
si llegó a la causa.

Por qué estos y no un benchmark: miden el razonamiento que el método necesita —leer un
error y decir dónde está la causa— sobre el código y las convenciones de este proyecto.
Un modelo puede saber Python y no saber esto.
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
    out=[]
    try:
        with urllib.request.urlopen(rq,timeout=600) as r:
            for l in r:
                s=l.decode("utf-8","replace").strip()
                if not s.startswith("data: ") or s[6:]=="[DONE]": continue
                try: d=json.loads(s[6:])
                except Exception: continue
                for ch in d.get("choices") or []:
                    de=ch.get("delta") or {}
                    for k in ("content","reasoning","reasoning_content"):
                        if de.get(k): out.append(de[k])
    except Exception as e:
        return f"__ERROR__ {type(e).__name__}"
    return "".join(out)

for linea in sys.argv[1:]:
    mid,nom=linea.split("=",1)
    aciertos=[]
    for clave,preg,patron in CASOS:
        # Una respuesta vacía no es una respuesta equivocada: es un chequeo que no pudo
        # correr (⊘). Contarla como ✗ convirtió un modelo que contesta bien en 1 de 6 —el
        # primer caso lo falló por estar frío, no por razonar mal—. Se reintenta una vez y,
        # si sigue vacía, se marca aparte y NO cuenta como fallo.
        r=preguntar(mid,preg)
        if r.startswith("__ERROR__") or not r.strip():
            r=preguntar(mid,preg)
        if r.startswith("__ERROR__") or not r.strip():
            aciertos.append("⊘"); continue
        aciertos.append("✓" if re.search(patron, r, re.I) else "✗")
    val=[a for a in aciertos if a!="⊘"]
    print(f"  {nom:26s} {' '.join(aciertos)}   {aciertos.count('✓')}/{len(val)}"
          f"{'  (⊘ ' + str(aciertos.count('⊘')) + ' sin respuesta)' if '⊘' in aciertos else ''}", flush=True)
print("\n  casos: " + " ".join(c[0] for c in CASOS))
