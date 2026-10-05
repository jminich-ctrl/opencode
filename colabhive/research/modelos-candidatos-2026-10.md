# Qué modelo para cada agente, con el catálogo abierto

**Pregunta:** ColabHive permite importar desde HuggingFace, así que el catálogo no es el que
está desplegado. ¿Cuál conviene para cada papel del método?

> **Corrección, el mismo día.** La primera versión de este documento recomendaba
> GLM-4.7-Flash dando por hecho que entraba por `GLMForCausalLM`. Falso: su arquitectura
> real es **`Glm4MoeLiteForCausalLM`** y **no está en la lista de XPU** —las únicas
> entradas GLM son las del 4-9B—. El nombre que figura en la tabla de soporte no es el
> nombre de la familia: hay que leerlo del `config.json` del checkpoint. Abajo queda
> corregido, y aparece un candidato que no habíamos visto.

**Fecha:** 2026-10-05. **Todos los números de abajo son publicados, no medidos por
nosotros.** Sirven para elegir *candidatos*; quién gana lo decide `comparar-modelos.sh`
corriendo una tarea real contra el gate. Esa distinción es la misma trampa que la
presentación de Lovelace llama «creerle al banco sobre el uso real», y ya nos mordió hoy:
el `30B-A3B` tiene buenos números publicados y hoy devuelve `!` hasta agotar el presupuesto.

## El filtro que descarta primero: el hardware

Intel Arc Pro B70, 32 GB por placa, 608 GB/s. Dos cosas lo gobiernan:

1. **La arquitectura tiene que estar en la lista de XPU de vLLM.** Están
   `Qwen3ForCausalLM`, `Qwen3NextForCausalLM`, `Qwen3_5MoeForConditionalGeneration`,
   `GLMForCausalLM`, `DeepseekV4ForCausalLM`, `GPTForCausalLM`, `LlamaForCausalLM` y
   —esto sorprende— `MuseGlimmerForConditionalGeneration`.
2. **La cuantización también.** En XPU: BF16, FP8 online, e Int4 GPTQ vía el contenedor
   `llm-scaler` de Intel. **NVFP4 no corre acá**, es de Blackwell: cualquier checkpoint
   W4A4 de 25 GB que parezca entrar en una placa, no entra.

Y un tercero que decide el reloj de pared del método: **con un solo flujo, decodificar está
limitado por ancho de banda.** Un MoE de 3B activos lee 3B de pesos por token; un denso de
30B lee 30B. Por eso un MoE A3B va ~16,8 tok/s en esta placa y un denso equivalente va la
mitad o menos, por bueno que sea. Cada agente del método trabaja solo: esto pesa.

## Los candidatos que pasan el filtro

Verificado leyendo el `config.json` de cada checkpoint y el tamaño real de los pesos vía la
API de HuggingFace, no estimado:

| Modelo | Arquitectura real | Pesos en disco | Placas de 32 GB | ¿En la lista de XPU? |
|---|---|---|---|---|
| **DeepSeek-V4-Flash** 284B-**A13B**, 1M ctx, MIT | `DeepseekV4ForCausalLM` | **159,6 GB** (FP8 nativo) | **6 mínimo** | ✅ fila propia: `BF16/Online FP8` |
| **Muse Glimmer 30B** denso + ViT, 131K, Apache 2.0 | `MuseGlimmerForConditionalGeneration` | 32,78 GB (FP8) | 2 | ✅ y validado en B70 con la imagen XPU |
| GLM-4.7-Flash 31B-A3B, 200K, MIT | `Glm4MoeLiteForCausalLM` | 62,4 GB (BF16) | 1–2 con FP8 online | ❌ **no está** |
| Qwen3.8-27B FP8 *(ya desplegado)* | `Qwen3ForCausalLM` | — | 1 | ✅ |

### El hallazgo: hay un modelo que necesita Orion para existir

**DeepSeek-V4-Flash son 159,6 GB de pesos en FP8 nativo.** En las cuatro placas de hoy
(128 GB) no entra. En **Orion, 8× B70 = 256 GB, entra con ~96 GB libres para KV cache.**

Eso cambia de qué se trata la ventana de Orion. No es solamente «más paralelismo»: es una
clase de modelo que en el hardware actual no se puede servir en absoluto. Y no es un modelo
cualquiera para lo que hacemos — Terminal Bench 2.1 **82,7**, Toolathlon-Verified **70,3**,
que son las dos varas más parecidas a un agente trabajando en una terminal sobre un repo.

Dos cosas más que lo hacen encajar acá y no sólo en un benchmark:

- **13B activos de 284B.** La decodificación con un solo flujo lee sólo los expertos
  activos, así que repartidos en ocho placas cada una lee algo así como 1,6 GB por token.
  No es el cuello de botella que sí tiene un denso de 30B. (Aritmética de techo, no
  medición: la ruteo de expertos y la atención se pagan igual.)
- **Viene cuantizado de fábrica**, `fp8` e4m3 con bloques de 128×128 declarado en su
  `config.json`, y la fila de XPU dice exactamente `BF16/Online FP8`. No hay que producir
  un checkpoint ni confiar en una cuantización de terceros — que es, literalmente, el
  problema que hoy nos rompió el ejecutor.

### Muse Glimmer 30B: el candidato para las cuatro placas de hoy

Es el único de la lista que está **validado en B70** con receta publicada (imagen XPU,
`--enforce-eager`) y que entra en el hardware actual: 32,78 GB en FP8, o sea TP2. Publica
MCP Atlas **75,5** en uso de herramientas contra 62,5 del Qwen de la generación anterior, y
SWE-bench Verified 76,0. Es denso, así que decodifica a la mitad que un A3B — el precio de
la calidad. Trae además un **draft head de 5,11 GB** para decodificación especulativa, que
es la palanca ×2,8 empaquetada.

### Por qué GLM-4.7-Flash queda afuera, aunque era el mejor candidato sobre el papel

Sobre el papel era ideal: misma forma que el modelo roto (30B-A3B), MIT, MTP en la receta
publicada, τ²-Bench 79,5. Pero su arquitectura es `Glm4MoeLiteForCausalLM`, que no figura
en la lista de XPU, y el propio modelo aclara que **vLLM y SGLang lo soportan sólo en sus
ramas principales**. Tampoco publica checkpoints cuantizados oficiales.

Queda como **pedido**, no como plan: si Intel o el equipo de vLLM agregan
`Glm4MoeLiteForCausalLM` al backend XPU, es el mejor candidato para una sola placa.

## Lo que hay que pedirle a ColabHive

1. **Importar `zai-org/GLM-4.7-Flash`** y servirlo con la receta publicada, con MTP activado
   y `--tool-call-parser glm47`.
2. **Arreglar o reemplazar `f5d76140`** (`30B-A3B`), que devuelve un token repetido —
   `colabhive/bug-token-repetido-30b.md`.
3. **Alinear cómo se informa la cuantización.** `oc --status` dice FP8 y la API dice AWQ
   para el mismo modelo. Con logits rotos de por medio, ese es el primer dato que uno mira.
4. **Importar `Muse-Glimmer-30B` en FP8 con TP2**: es el único candidato nuevo que entra en
   el hardware de hoy y está validado en B70.
5. **`DeepSeek-V4-Flash` necesita 6 placas como mínimo** (159,6 GB de pesos). Si hay acceso a
   Orion, es el candidato de techo; en las cuatro de hoy no entra.

## Lo que midió el gate, que desmintió a la tabla

Lo de arriba son números publicados. Esto es `comparar-modelos.sh` sobre **T08 de
clasificados**: misma tarea real, mismo repo, mismo arnés, mismo gate que puede reprobar.

| Modelo | Herramientas | Deliberación | **Archivos** | Segundos | ¿Su código sostiene peso? |
|---|---|---|---|---|---|
| **Devstral-Small-2-24B** | 20 | 700 | **3** | **192** | ✅ revertirlos rompe la suite |
| Qwen3.8-27B FP8 | 26 | 974 | 3 | 1574 | — |
| GLM-4.7-Flash | 4 | 9 | **0** | 82 | no hizo nada |

**Ganó el que no estaba en esta investigación.** Devstral-Small-2-24B no aparecía en ninguna
de mis búsquedas: lo encontré mirando el catálogo que ya estaba desplegado. Escribió
`AdsList.jsx`, `AdDetail.jsx` y `services/ads.ts`, y la prueba de mutación del gate confirma
que no es decorado: al revertir esos archivos la suite se cae.

**Perdió el que yo había elegido.** GLM-4.7-Flash tiene los mejores números publicados de
los tres —τ²-Bench 79,5, SWE-bench Verified 59,2— y en la tarea real se rinde tras cuatro
llamadas a herramientas con cero archivos. No está roto: el chequeo de salud le da 4 de 4
sano y llamando herramientas. Simplemente **no termina el trabajo en este arnés**.

**El 27B llega al mismo lugar que Devstral y tarda 8 veces más.** 1574 segundos contra 192,
con más deliberación (974 líneas contra 700) para el mismo resultado.

Tres advertencias sobre esta tabla, para que no se lea de más:

- **Es UNA tarea y UNA corrida por modelo.** Suficiente para descartar a GLM-4.7-Flash como
  ejecutor y para preferir a Devstral sobre el 27B por un factor de 8; insuficiente para
  ordenar dos modelos que queden cerca.
- **Mide el par modelo + arnés, no el modelo.** Con otro arnés —OpenHands, por ejemplo— el
  orden puede ser otro, y medirlo es justamente para lo que sirve el modo `@agente` de
  `comparar-modelos.sh`.
- **Tres veces en el día el número publicado eligió mal.** Primero recomendé GLM-4.7-Flash
  por τ²-Bench; después lo descarté porque su arquitectura no figuraba en la lista de XPU
  de vLLM —y ya estaba desplegado y andando—; y al final la tarea real lo descartó por un
  motivo que ninguna tabla decía. La lista de arquitecturas y el banco público son dos
  documentos, y los dos estaban desactualizados respecto del sistema.

## Lo que decide, que no es esta tabla

El método ya tiene el instrumento, y es el único honesto para esto:

```
PROYECTO=ejemplo-clasificados bash scripts/comparar-modelos.sh T06 \
    colabhive/<glm-4.7-flash> colabhive/<27B> colabhive/<muse-glimmer>
```

Corre **la misma tarea real** con cada modelo y compara gate verde/rojo, tiempo,
herramientas usadas, líneas de deliberación y archivos tocados. Los benchmarks públicos no
miden si un modelo llama a las herramientas o se queda deliberando, y hoy tenemos la prueba
de que tampoco miden si el servido está sano.

**Propuesta de asignación, a confirmar con esa corrida:**

| Papel | Hoy | Propuesto | Por qué |
|---|---|---|---|
| `ejecutor`, `build`, `tester`, `devops`, `migrador` | 30B-A3B (roto) | **Muse Glimmer 30B** (TP2) hoy; **DeepSeek-V4-Flash** en Orion | los dos están en la lista de XPU; GLM-4.7-Flash no |
| `arquitecto` | 30B-A3B (roto) | DeepSeek-V4-Flash si hay 6+ placas | planifica: la calidad vale más que el reloj, y 13B activos no castigan tanto |
| `plan`, `reviewer`, `seguridad` | 27B FP8 | se queda | medido sano, 30,1 tok/s |
| `title`, `summary`, `compaction` | gpt-oss-20b / 30B | un modelo chico **sin razonamiento** | el 98% del presupuesto se va razonando: para un título es puro desperdicio |

El último renglón no necesita catálogo nuevo: necesita que dejemos de usar un modelo que
razona para escribir un título.

## Fuentes

- Arquitecturas soportadas en Intel XPU: https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/
- GLM-4.7-Flash (pesos y receta): https://huggingface.co/zai-org/GLM-4.7-Flash
- GLM-4.7-Flash, análisis y números: https://llm-stats.com/blog/research/glm-4.7-flash-launch
- Muse Glimmer 30B, receta vLLM y validación en B70/B60: https://recipes.vllm.ai/meta-models/Muse-Glimmer-30B
- Qwen3.8-Flash-Next: https://huggingface.co/Qwen/Qwen3.8-Flash-Next
- Configs de B70 en vLLM recipes: https://github.com/vllm-project/recipes/pull/1024
- Modelos de código con herramientas, panorama: https://modal.com/resources/best-open-source-code-llms-tool-calling-agents
