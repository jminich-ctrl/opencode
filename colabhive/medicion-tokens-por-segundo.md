# Tokens por segundo: lo que medimos y contra qué

Medición del 2026-10-05 sobre `api.colabhive.com`, con `scripts/medir-tps.py`.

**Protocolo**, porque un número sin protocolo no se puede comparar con nada: petición
`stream: true`, `temperature: 0`, prompt fijo de ~160 caracteres, `max_tokens` 256 y 512,
**cinco corridas por modelo**, se informa la **mediana**. El tiempo al primer token se mide
aparte del tiempo de generación: mezclarlos hace que una cola lenta se vea como un modelo
lento. Se descartan las corridas que llegan en ≤2 trozos —ahí el cociente mide el búfer— y
se cuentan como generación tanto los deltas de `content` como los de `reasoning`.

## Lo que medimos

| Modelo (nombre en la API) | Papel en el método | Primer token | Generación |
|---|---|---|---|
| Qwen3 Coder 30B-A3B **AWQ** | ejecutor y tester | 1,34 s | **16,8 tok/s** (16,4–16,9) |
| Qwen3.8-27B **FP8** | plan y reviewer | 1,18 s | **30,1 tok/s** (28,9–31,1) |
| gpt-oss-20b | título y explore | 1,79 s | **44,6 tok/s** (44,2–45,0) |

Las bandas son angostas y con `max_tokens=512` los números no se mueven (16,8 / 29,9 /
45,2), así que describen el modelo y no el momento.

## Contra qué

Cifras publicadas de **un solo flujo** (batch 1), que es lo que medimos nosotros:

| Modelo | Hardware | Publicado | Nosotros | Distancia |
|---|---|---|---|---|
| Qwen3-Coder-30B-A3B **FP8** | 1× H200 SXM, 1K de contexto | 164,9 tok/s | 16,8 (AWQ) | **≈10×** |
| Qwen3-32B **FP8** denso | 1 GPU, SGLang | 46,2 tok/s | 30,1 (27B FP8) | **≈1,5×** |
| gpt-oss-20b | 1× H100, concurrencia 1 | 307,6 tok/s | 44,6 | **≈7×** |
| gpt-oss-20b | H100, misma configuración de decodificación | 178 tok/s | 44,6 | **≈4×** |

## Lo que la asimetría sugiere

No sabemos con qué GPU corre la plataforma, así que la comparación absoluta contra H100 y
H200 no es justa. Pero hay una comparación **interna** que no depende del hardware:

- el modelo **denso** de 27B en FP8 queda a **1,5×** de una cifra publicada para un denso
  de 32B en FP8;
- el **MoE** de 30B con **3B activos** queda a **10×**, y debería ser el más rápido de los
  tres, no el más lento.

Un MoE con 3B activos tiene que ir claramente más rápido que un denso de 27B. Va a la
mitad. Esa inversión no se explica por la GPU —si fuera la GPU, los tres estarían igual de
lejos— sino por el camino de inferencia del MoE.

La hipótesis más barata de probar: **está servido en AWQ y no en FP8.** La API lo informa
como «Qwen3 Coder 30B-A3B AWQ», y los núcleos de MoE fusionado para 4 bits suelen quedar
muy por detrás de los de FP8. La cifra publicada de 164,9 tok/s es justamente del FP8.

Vale la pena porque es el modelo del **ejecutor**: es el que escribe el código en cada
tarea, así que su velocidad es el reloj de pared de todo el método.

## Un detalle que conviene corregir igual

`oc --status` informa ese modelo como
`hf-Qwen-Qwen3-Coder-30B-A3B-Instruct-FP8` y la API lo informa como
`Qwen3 Coder 30B-A3B AWQ`. Son dos declaraciones de lo mismo que no coinciden, y la
cuantización es exactamente el dato que uno necesita para interpretar una medición. Si la
de la API es la correcta, el nombre en el estado está mintiendo sobre qué estamos corriendo.

## Qué pedimos

1. Confirmar la cuantización real del `30B-A3B` y, si es AWQ, probar FP8: es la única
   diferencia visible entre nuestro 16,8 y los 164,9 publicados.
2. Decirnos con qué GPU corre cada modelo, para poder comparar contra la referencia que
   corresponde en vez de contra H100/H200.
3. Alinear el nombre de `oc --status` con el de la API.

## Y uno nuestro, que no es de velocidad

Con `max_tokens=256`, **el 98% de lo que emite gpt-oss-20b son tokens de `reasoning` y el
2% de `content`**; con 512, 72% y 28%. Es el modelo que opencode usa para el título de la
sesión y el que tiene asignado el agente `explore`. Para una tarea donde lo que importa es
lo que escribe, con presupuesto corto no entrega nada: eso no es un problema de la
plataforma, es una decisión de asignación nuestra que hay que revisar.

## Fuentes

- Qwen3-Coder-30B-A3B-Instruct FP8 en 1× H200 SXM: https://www.millstoneai.com/inference-benchmark/qwen3-coder-30b-a3b-instruct-fp8-1x-h200-sxm
- Qwen3 Speed Benchmark (batch 1, FP8, SGLang): https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html
- gpt-oss-20b en 1× H100, OCI Generative AI: https://docs.oracle.com/en-us/iaas/Content/generative-ai/benchmark-openai-gpt-oss-20b.htm
- gpt-oss-20b, análisis de despliegue: https://arxiv.org/html/2508.16700v1
- Optimización de gpt-oss-20b en H100 (GPUStack): https://docs.gpustack.ai/2.0/performance-lab/gpt-oss-20b/h100/
