#!/usr/bin/env python3
"""Tasa de tool_call por modelo. No un sí/no: una TASA, porque el fenómeno no es determinista.

Medido antes: la misma petición a temperature 0 produjo tool_call una vez y prosa la
siguiente. Un binario no puede describir eso; hace falta contar.

El control es el Qwen3-Coder-30B: es el ejecutor con el que T06c cerró en verde hace un
rato, así que en producción llama herramientas. Si acá sale bajo, el arnés está mal y
ningún otro número de esta tabla significa nada.
"""
import json, os, sys, time, urllib.request
BASE=os.environ["COLABHIVE_BASE_URL"].rstrip("/"); CLAVE=os.environ["COLABHIVE_API_KEY"]
N=int(os.environ.get("N","6"))
H=[{"type":"function","function":{"name":"write","description":"Escribe un archivo",
    "parameters":{"type":"object","properties":{"path":{"type":"string"},
     "content":{"type":"string"}},"required":["path","content"]}}}]
SIS="Sos un agente que escribe código. Usá las herramientas."
PED="Escribí backend/app/main.py con una app FastAPI mínima. Usá la herramienta write."

def una(mid):
    c={"model":mid,"stream":True,"max_tokens":384,"temperature":0,"tools":H,"tool_choice":"auto",
       "messages":[{"role":"system","content":SIS},{"role":"user","content":PED}]}
    rq=urllib.request.Request(f"{BASE}/chat/completions",data=json.dumps(c).encode(),
        headers={"Authorization":f"Bearer {CLAVE}","Content-Type":"application/json"})
    t0=time.time(); nom=None; n=0
    try:
        with urllib.request.urlopen(rq,timeout=600) as r:
            for l in r:
                s=l.decode("utf-8","replace").strip()
                if not s.startswith("data: ") or s[6:]=="[DONE]": continue
                try: d=json.loads(s[6:])
                except Exception: continue
                for ch in d.get("choices") or []:
                    de=ch.get("delta") or {}
                    if de.get("content"): n+=len(de["content"])
                    for tc in de.get("tool_calls") or []:
                        if (tc.get("function") or {}).get("name"): nom=tc["function"]["name"]
    except Exception as e:
        return "E", time.time()-t0, 0
    return ("T" if nom else ("p" if n else "_")), time.time()-t0, n

for linea in sys.argv[1:]:
    mid,nom_m=linea.split("=",1)
    marcas=[]; llamo=0; segs=[]
    for _ in range(N):
        m,s,n=una(mid); marcas.append(m); segs.append(s); llamo += (m=="T")
    print(f"  {nom_m:26s} {''.join(marcas)}  tasa {llamo}/{N}  "
          f"({sum(segs)/len(segs):.0f}s prom)", flush=True)
print("\n  T = llamó la herramienta · p = contestó en prosa · _ = vacío · E = error")
