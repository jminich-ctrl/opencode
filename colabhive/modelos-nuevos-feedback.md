# Los cuatro modelos nuevos: qué medimos

Medición del 2026-10-06 contra `api.colabhive.com`, desde el método de agentes.
**Protocolo:** `temperature 0`, `stream: true`, herramientas declaradas, el arranque en frío
medido **aparte** del resto —si se mezclan, se informa el despertar y no el modelo—, tres
corridas por modelo ya caliente.

## Resumen

| Modelo | Arranque en frío | Caliente | Contexto real | Veredicto |
|---|---|---|---|---|
| **CodeScout-14B** | 848 s → 61 s | 22 s · 942–1680 car. | 40.960 | **el único usable de los tres CodeScout** |
| CodeScout-4B | 257 s | 5 s · 169 car. | 34.880 | anda, pero entrega muy poco |
| **CodeScout-1.7B** | 3 s → 81 s | **8 caracteres, siempre** | 40.960 | **roto** |
| **openhands-lm-32b-v0.1** | 1202 s → **16 s** | 323 s → **19 s** | 32.768 | **lo arreglaron entre las dos mediciones** |

## Lo que hay que mirar, en orden

### 1. CodeScout-1.7B devuelve 8 caracteres

Tres de tres, en las dos tandas, separadas por horas. Ocho caracteres, con herramientas
declaradas y sin llamar ninguna. No es «un modelo chico que responde poco»: es una
respuesta que no existe.

Y empeoró entre mediciones: pasó de 3 s de arranque y 4 s por corrida a **81 s de arranque
y 319 s de promedio**, con la misma salida de 8 caracteres.

Es el más barato de arreglar de los cuatro y el que más olor a configuración tiene
—plantilla de chat, `max_tokens` efectivo, o tokenizador—. Si sirviera, sería el único con
arranque instantáneo.

### 2. El arranque en frío del 14B: 848 segundos

Catorce minutos. Eso no es sólo lento: **rompe el método**. Nuestra sonda de plataforma
consulta el modelo del ejecutor con 45 s de tope antes de arrancar una corrida; un modelo
frío se come el timeout y la corrida se niega a empezar diciendo «la plataforma no
responde», con la plataforma perfectamente arriba. Ya nos pasó hoy con Devstral y perdimos
una hora buscando la causa en el lugar equivocado.

En la segunda medición arrancó en 61 s, así que el número depende del estado del clúster.

### 3. openhands-lm-32b: antes y después

| | primera medición | segunda |
|---|---|---|
| arranque | 1202 s | **16 s** |
| promedio caliente | 323 s | **19 s** |
| corridas con salida | 1 de 3 | **3 de 3** |

Lo que sea que hicieron entre las dos, funcionó. Lo anotamos porque el **control no se
movió**: CodeScout-14B dio 22 s de promedio y salidas idénticas carácter por carácter
(1185/942/1680) en las dos tandas. O sea que no fue una mejora general de plataforma: fue
específica de ese modelo.

Ese control es también la razón por la que no reportamos antes «el modelo de OpenHands no
anda». Sin él, cinco fallos limpios y reproducibles habrían salido como un veredicto sobre
el modelo de un partner.

### 4. El `tool_call` no es determinista — y esto es lo importante

La misma petición, `temperature 0`, al mismo modelo: una llamada produjo `tool_call` y la
siguiente contestó en prosa. Cuando una entrada idéntica da salidas distintas, la causa no
puede estar en la entrada.

Lo medimos como **tasa** sobre seis modelos, con el `Qwen3-Coder-30B` de control: es el
ejecutor con el que una tarea cerró en verde hoy, así que en el camino real llama
herramientas. Seis corridas, misma petición, `temperature 0`:

| Modelo | Patrón | Tasa | Prom. |
|---|---|---|---|
| Qwen3.8-27B | `TTTTTT` | **6/6** | 33 s |
| Qwen3-Coder-30B *(control)* | `_TTTTT` | 5/6 | 52 s |
| CodeScout-4B | `__TTTT` | 4/6 | 16 s |
| **CodeScout-14B** | `pppppT` | **1/6** | 9 s |
| **openhands-lm-32b** | `pppppp` | **0/6** | 6 s |
| **GLM-4.7-Flash** | `______` | **0/6** | **934 s** |

`T` llamó · `p` contestó en prosa · `_` vacío.

**El control llama 5 de 6, así que el arnés es válido** y las tasas bajas son de los
modelos, no de la medición.

**GLM-4.7-Flash: seis vacías a 934 s de promedio.** Es la firma de «no consigue GPU» que ya
vimos hoy, no un problema del modelo.

**Sobre openhands-lm-32b, 0 de 6:** es un dato sólido por el camino OpenAI-compatible, y
**no es un veredicto sobre el modelo**. OpenHands LM está entrenado para el arnés de
OpenHands, que usa su propia convención. Evaluarlo de verdad pide correrlo con su arnés.

## Razonamiento

Banco de seis casos armados con fallas reales nuestras de las últimas 30 horas, cuyo
diagnóstico correcto conocemos porque lo verificamos. Corrección por palabra clave; una
respuesta vacía cuenta como ⊘ y no como error.

| Modelo | Razonamiento | Herramientas |
|---|---|---|
| **Qwen3.8-27B** | **6/6** | **6/6** |
| CodeScout-14B | 3/6 | 1/6 |
| CodeScout-4B | 3/6 | 4/6 |
| Qwen3-Coder-30B | 2/6 | 5/6 |
| openhands-lm-32b | 2/6 | 0/6 |

Dos casos los falló todo el mundo menos el 27B: por qué un test que crea su propia
`FastAPI()` no ve los manejadores del proyecto, y que git no versiona directorios vacíos.
Los dos exigen razonar sobre un mecanismo que el síntoma no muestra.

**Las dos columnas se separan:** el 30B llama herramientas y razona poco; el 14B razona más
y casi no llama. Son para papeles distintos.

**Límites del banco:** seis casos, una corrida, corrección por palabra clave. Ordena y
descarta; no decide entre dos modelos que queden cerca.

Para un método de agentes esto es lo que más duele: un modelo que contesta en prosa donde
debería llamar una herramienta **no falla, inventa** — describe el archivo que debería
haber leído. Es la falla más cara de detectar porque parece trabajo.

## Lo que no podemos distinguir desde afuera

Si el `8 caracteres` del 1.7B y la intermitencia del `tool_call` son del modelo o del
servido. Es la misma pregunta que ya resolvieron una vez hoy —el token repetido del
`30B-A3B` resultó ser presión de memoria, no cuantización— y la resolvieron mirando las
placas, que es algo que nosotros no podemos hacer.
