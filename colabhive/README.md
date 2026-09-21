# colabhive — el entorno de ejecución

Todo lo necesario para que OpenCode corra contra modelos self-hosted en ColabHive.
La explicación de cada campo está en [../OPENCODE.md](../OPENCODE.md); acá están los
archivos y cómo instalarlos.

```
config/opencode.json    la config completa: provider, 4 modelos, 6 agentes
config/prompts/*.md     el prompt de cada agente
scripts/                setup, operación y medición
research/findings.md    todas las mediciones, con fechas
research/colabhive-backlog.md   28 mejoras pedidas a la plataforma
```

## Instalación, de punta a punta

```bash
# 1. la API key: se guarda en ~/.config/colabhive/env (chmod 600) y se valida
bash colabhive/scripts/set-api-key.sh

# 2. enlazar la config (los DOS symlinks: el JSON y el directorio de prompts)
mkdir -p ~/.config/opencode
ln -sfn "$PWD/colabhive/config/opencode.json" ~/.config/opencode/opencode.json
ln -sfn "$PWD/colabhive/config/prompts"       ~/.config/opencode/prompts

# 3. el atajo `oc` en el PATH
mkdir -p ~/bin && ln -sfn "$PWD/colabhive/scripts/oc" ~/bin/oc
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc

# 4. ajustar el contexto de cada modelo al real y verificar que todo responda
source ~/.config/colabhive/env
python3 colabhive/scripts/sync_limits.py --write
oc --status
```

Si tus endpoints son otros, cambiá los ids en `config/opencode.json`: la clave de cada
modelo es el id que devuelve `GET /v1/models`.

## Operación diaria

```bash
oc --status     # ● warm  ◐ cached  ○ cold
oc --warm       # despierta a los cuatro modelos (hacelo antes de cada tanda)
oc              # abre la TUI en el directorio actual
oc "tarea"      # una tarea suelta
```

## Medición

| Script | Para qué |
|---|---|
| `sync_limits.py` | ajusta `limit.context` al `max_model_len` real de cada réplica |
| `check_cache.py` | ¿hay prefix caching? (la diferencia es 48 s vs 2,6 s por paso) |
| `concurrencia.py` | techo de paralelismo por modelo (el nuestro: 16) |
| `smoke_test.py` | tool calling, warmup y tokens/s de un endpoint |
| `keepalive_burst.py` | TTFT sobre conexión reutilizada, después de una pausa |

Los tres primeros conviene correrlos antes de una tanda: los modelos se enfrían, las
réplicas cambian de ventana al reemplazarse y el caching depende de cómo se levantó el motor.

## Si no usás ColabHive

El método no cambia; cambia el `baseURL` y los ids de modelo. Con vLLM local u Ollama,
ver [../INFRAESTRUCTURA.md §6](../INFRAESTRUCTURA.md). Lo único no negociable es que el
modelo tenga **tool calling habilitado** del lado del servidor.
