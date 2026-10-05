# Tokens por segundo: lo que medimos, y contra qué hay que compararlo

Medición del 2026-10-05 sobre `api.colabhive.com`, con `scripts/medir-tps.py`.

> **Corrección importante.** La primera versión de este documento comparaba contra H100 y
> H200 y concluía que el MoE estaba «10× lejos» por un problema del camino de inferencia.
> Estaba mal: la plataforma corre **Intel Arc Pro B70**, y contra las cifras publicadas de
> ese hardware nuestros números están **en línea o mejor**. La conclusión se da vuelta y
> queda explicada abajo.

**Protocolo**, porque un número sin protocolo no se puede comparar con nada: petición
`stream: true`, `temperature: 0`, prompt fijo de ~160 caracteres, `max_tokens` 256 y 512,
**cinco corridas por modelo**, se informa la **mediana**. El tiempo al primer token se mide
aparte del de generación: mezclarlos hace que una cola lenta se vea como un modelo lento.
Se descartan las corridas que llegan en ≤2 trozos —ahí el cociente mide el búfer— y cuentan
como generación tanto los deltas de `content` como los de `reasoning`.

## Lo que medimos

| Modelo (nombre en la API) | Papel en el método | Primer token | Generación |
|---|---|---|---|
| Qwen3 Coder 30B-A3B AWQ | ejecutor y tester | 1,34 s | **16,8 tok/s** (16,4–16,9) |
| Qwen3.8-27B FP8 | plan y reviewer | 1,18 s | **30,1 tok/s** (28,9–31,1) |
| gpt-oss-20b | título y explore | 1,79 s | **44,6 tok/s** (44,2–45,0) |

Bandas angostas, y con `max_tokens=512` no se mueven (16,8 / 29,9 / 45,2): describen el
modelo, no el momento.

## Contra el hardware que corresponde

**Intel Arc Pro B70**: 32 GB GDDR6 ECC, **608 GB/s** de ancho de banda, 256 XMX, $949.
Para comparar: H200 SXM está en ~4,8 TB/s, o sea **~7,9× más ancho de banda**. Y la
decodificación con un solo flujo está limitada por ancho de banda, no por cómputo: se lee
todo el peso activo por cada token. Así que **una diferencia de ~8× contra una H200 es lo
que el hardware predice**, no una anomalía.

Cifras publicadas **en B70**, de un solo usuario:

| Modelo publicado | Configuración | Publicado | Nosotros |
|---|---|---|---|
| Qwen3.6-35B-**A3B** (MoE) | 4× B70, 1 usuario, llm-scaler | **16,3 tok/s** | **16,8** (30B-A3B) |
| Qwen3.5-27B Q4 (denso) | 1× B70, 1 usuario, vLLM | **13,4 tok/s** | **30,1** (27B FP8) |
| Qwen3.8-27B (denso) | vLLM XPU **con MTP4** | **84,6 tok/s** | 30,1 (sin MTP) |
| Qwen3 8B (denso) | 1× B70 | 34,7 tok/s | — |

## Lo que esto dice de verdad

1. **El MoE no está mal: está exactamente donde la referencia.** 16,8 contra 16,3
   publicados para un MoE A3B equivalente en B70. Mi conclusión anterior —que la inversión
   MoE/denso delataba un problema de kernels— era un artefacto de comparar contra H200.
2. **El denso está mejor que la referencia**: 30,1 contra 13,4 publicados para un 27B Q4 en
   una B70. Probablemente por FP8 contra Q4 y por una mejor configuración de servido.
3. **La distancia contra H100/H200 es de hardware, no de software.** ~8× de ancho de banda
   explica ~8× de tokens por segundo con un solo flujo. No hay nada que «arreglar» ahí: hay
   que comprar otra GPU o cambiar de estrategia.

## Dónde está la mejora real: MTP

El único número publicado en B70 que nos deja muy atrás es **Qwen3.8-27B con MTP4: 84,6
tok/s** contra nuestros 30,1. Eso es **×2,8 en el mismo hardware**, y no es cuantización ni
suerte: es **multi-token prediction / decodificación especulativa**, que ataca justamente el
cuello de botella de un solo flujo —emite varios tokens por lectura de pesos—.

Para el método esto vale más que cualquier otra optimización, porque el reloj de pared de
una corrida es casi todo decodificación con un solo flujo: cada agente trabaja solo.

**Pedido concreto:** evaluar MTP / speculative decoding en el servido del `30B-A3B` y del
`27B`. Si da algo parecido al ×2,8 publicado, una etapa de cuatro tareas pasa de ~20
minutos a ~7.

Lo segundo, mucho menor: la concurrencia. El mismo MoE A3B publica **122 tok/s con ocho
usuarios** contra 16,3 con uno. El método corre las tareas de una etapa en paralelo, así
que parte de ese escalado ya lo estamos aprovechando sin saberlo —y conviene medirlo: si
cuatro tareas en paralelo rinden como cuatro usuarios, el paralelismo del plan vale el doble
de lo que creíamos—.

## Un detalle de higiene que sigue en pie

`oc --status` informa ese modelo como `hf-Qwen-Qwen3-Coder-30B-A3B-Instruct-FP8` y la API lo
informa como `Qwen3 Coder 30B-A3B AWQ`. Son dos declaraciones de lo mismo que no coinciden,
y la cuantización es exactamente el dato que uno necesita para interpretar una medición —de
hecho fue lo que me llevó a la hipótesis equivocada—. Conviene alinearlas.

## Y uno nuestro, que no es de velocidad

Con `max_tokens=256`, **el 98% de lo que emite gpt-oss-20b son tokens de `reasoning` y el
2% de `content`**; con 512, 72% y 28%. Es el modelo que opencode usa para el título de la
sesión y el que tiene asignado el agente `explore`. Con presupuesto corto no entrega nada:
eso no es de la plataforma, es una decisión de asignación nuestra que hay que revisar.

## Fuentes

- Especificaciones del Arc Pro B70 (32 GB, 608 GB/s): https://www.igorslab.de/en/intel-arc-pro-b70-review-teardown-topology-material-tests-workstation-ai-benchmarks/
- Benchmarks de LLM en Arc Pro B60/B70, todos los backends: https://bentech.substack.com/p/intel-arc-pro-b60-b70-llm-benchmarks
- Qwen3.8-27B en Arc Pro B70 (MTP4, 84,56 tok/s): https://jonathanmann.tech/blog/qwen38-intel-arc-b70/
- Inferencia multi-GPU en Arc Pro B70 (Puget Systems): https://www.pugetsystems.com/labs/articles/intel-arc-pro-b70-multi-gpu-ai-inference-performance/
- Arc Pro B70 para IA local, costo por token (Gigazine): https://gigazine.net/gsc_news/en/20260619-intel-arc-pro-b70-local-ai/
- Review del stack en Arc Pro B70 (StorageReview): https://www.storagereview.com/review/intel-arc-pro-b70-review
- Referencia H200 para el contraste: https://www.millstoneai.com/inference-benchmark/qwen3-coder-30b-a3b-instruct-fp8-1x-h200-sxm

---

## Apéndice: el cuelgue era la plataforma cortando el stream

**Esta sección estuvo mal escrita dos veces el mismo día, y las dos veces por la misma
causa: un instrumento que mataba al sujeto antes de que hablara.**

Lo que decía antes: «el cuelgue de opencode no llega a la plataforma», apoyado en que un
proxy grabador sólo registró `GET /models` y ninguna petición de completado. Y lo que
decía después: «es la longitud del prompt», apoyado en un A/B de 8 contra 8.

Las dos conclusiones eran artefactos. Lo que pasa de verdad, medido corriendo tres agentes
**sin vigilante de inactividad**:

```
t=  2.0s  silencio=  2.0s     4B
t=  2.0s  silencio=  0.0s    57B   ← el encabezado de opencode
t= 70.3s  silencio= 68.4s   108B   ← Error: {"message":"upstream stream ended
                                      without a complete EOS handshake"}
```

**La plataforma corta el stream a mitad de la generación y tarda 68,4 segundos en
informarlo.** Dos de las tres corridas murieron así, con el mismo tiempo al decimal. La
tercera siguió trabajando más de diez minutos sin un solo problema.

Por qué nunca lo vimos:

| El instrumento | Cortaba a los | El error llega a los | Qué quedaba en el log |
|---|---|---|---|
| ventana de arranque (<1 KB) | 20 s | 68,4 s | 61 bytes: el encabezado |
| ventana larga | 45 s | 68,4 s | 61 bytes: el encabezado |
| proxy grabador | — | — | sólo el `GET /models` |

El proxy merece su propio renglón porque falla por lo mismo con otro mecanismo: **graba la
petición recién cuando la respuesta termina.** Una petición de completado que estaba en
vuelo cuando el vigilante mató el proceso no se graba nunca. O sea que «sólo llegó el
listado de modelos» no era un hallazgo sobre opencode: era el eco del mismo corte.

El error `upstream stream ended without a complete EOS handshake` **no aparece ni una sola
vez en ningún log de todo el día.** No porque no pasara: porque lo borrábamos 23 segundos
antes de que se imprimiera.

### Lo que hay que pedirle a la plataforma

Que el stream de `/chat/completions` termine con su EOS. Se corta a mitad de generación,
de forma intermitente y simultánea entre peticiones concurrentes —dos de tres cayeron en el
mismo segundo—, lo que apunta a algo del lado del servidor o del gateway y no del cliente.
Dato útil para buscarlo: el cliente se queda 68 segundos esperando antes de recibir el
error, así que hay un temporizador de ~70s en algún lado del camino.

### Y lo que nos dejó a nosotros

La regla está ahora en METODO.md y tiene un test que la sostiene: **un vigilante tiene que
perder siempre la carrera contra el error que la herramienta vigilada sabe imprimir.** Si
corta antes, no observa el sistema: lo fabrica.
