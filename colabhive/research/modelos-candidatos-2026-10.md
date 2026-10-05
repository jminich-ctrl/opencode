# Qué modelo para cada agente, con el catálogo abierto

**Pregunta:** ColabHive permite importar desde HuggingFace, así que el catálogo no es el que
está desplegado. ¿Cuál conviene para cada papel del método?

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

| Modelo | Forma | Memoria en B70 | Lo que publica | Veredicto |
|---|---|---|---|---|
| **GLM-4.7-Flash** | 30B-**A3B** MoE, 200K | FP8 ~30 GB → TP2 cómodo | SWE-bench Verified **59,2** · τ²-Bench **79,5** (herramientas) · LCB v6 64,0 | **el candidato** |
| **Muse Glimmer 30B** | 30B **denso** + ViT, 131K | FP8 32,78 GB → **TP2 mínimo** | MCP Atlas **75,5** (vs 62,5 del Qwen3.6-27B) · SWE-bench Verified 76,0 · SWE-bench Pro 51,2 | el techo de calidad, caro en placas |
| **Qwen3.8-Flash-Next** | 125B totales / **6B activos** | FP8 ~125 GB → no entra; Int4 ~63 GB → TP4, el clúster entero | Toolathlon **73,5** · CoWorkBench 73,9 | sólo si sobran placas |
| Qwen3.8-27B FP8 *(ya desplegado)* | 27B denso | 1 placa | medido por nosotros: 30,1 tok/s, 12 de 12 sano | el que funciona hoy |

### Por qué GLM-4.7-Flash es el candidato

Tres razones, en orden de peso:

1. **Es un reemplazo de forma idéntica al que está roto.** 30B-A3B MoE, mismos 3B activos,
   mismo perfil de memoria y de velocidad. No hay que replanificar nada de la topología.
2. **Trae MTP de fábrica.** El comando de servido que publican ya lleva
   `--speculative-config.method mtp`. Eso es exactamente la palanca que identifiqué esta
   mañana como la única mejora real disponible en esta placa (×2,8 publicado en B70). No
   hay que pelearla aparte: viene en la receta.
3. **τ²-Bench 79,5** mide encadenar herramientas sin perder el hilo —buscar, leer, editar—,
   que es literalmente lo que hace el `ejecutor`. Es el número más parecido a nuestro uso
   de todos los que hay publicados.

También publica `--tool-call-parser glm47` y `--reasoning-parser glm45`, o sea que el
razonamiento viene separado del contenido. Eso importa: medimos que `gpt-oss-20b` gasta el
**98% de su presupuesto en razonamiento** con `max_tokens=256`, y sin parser eso se mezcla.

### Por qué Muse Glimmer no es el candidato, aunque mida mejor

Mide mejor en uso de herramientas (75,5 contra los 62,5 del Qwen de la generación anterior)
y está **validado en B70** con la imagen XPU y `--enforce-eager`. Pero es **denso**: su
checkpoint FP8 son 32,78 GB, que no entran en una placa de 32 GB con KV cache. Mínimo TP2,
y con la mitad de la velocidad de decodificación de un A3B.

Tiene algo que sí vale la pena mirar aparte: **un draft head de 5,11 GB para decodificación
especulativa**. Es la misma palanca del MTP, empaquetada.

## Lo que hay que pedirle a ColabHive

1. **Importar `zai-org/GLM-4.7-Flash`** y servirlo con la receta publicada, con MTP activado
   y `--tool-call-parser glm47`.
2. **Arreglar o reemplazar `f5d76140`** (`30B-A3B`), que devuelve un token repetido —
   `colabhive/bug-token-repetido-30b.md`.
3. **Alinear cómo se informa la cuantización.** `oc --status` dice FP8 y la API dice AWQ
   para el mismo modelo. Con logits rotos de por medio, ese es el primer dato que uno mira.
4. Si sobran placas: **importar `Muse-Glimmer-30B` en FP8 con TP2** como candidato de techo
   para el `arquitecto`, que es el papel donde la calidad vale más que la velocidad.

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
| `ejecutor`, `build`, `tester`, `devops`, `migrador` | 30B-A3B (roto) | **GLM-4.7-Flash** | τ²-Bench, MoE rápido, MTP de fábrica |
| `arquitecto` | 30B-A3B (roto) | Muse Glimmer 30B, si hay placas | planifica: la calidad vale más que el reloj |
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
