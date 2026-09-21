# colabhive — el entorno de ejecución

Todo lo necesario para que OpenCode corra contra modelos open-weight servidos por ColabHive.
La explicación de cada campo está en [../OPENCODE.md](../OPENCODE.md); acá están los
archivos y cómo instalarlos.

```
config/opencode.json    la config completa: provider, 3 modelos, un agente por rol
config/prompts/*.md     el prompt de cada agente
scripts/                setup, operación y medición
research/findings.md    las mediciones, con fechas
```

> **¿Solo querés un modelo andando?** `pip install -U colabhive && colabhive agents init`
> agrega un provider de ColabHive con un modelo probado a tu config de OpenCode, sin tocar
> lo demás ([guía](https://docs.colabhive.com/guides/agents/quickstart)). Lo de abajo instala
> el equipo completo de tres modelos, con sus prompts y el atajo `oc`. **Es uno u otro:**
> correr `colabhive agents init` después de esta instalación reemplaza el symlink por un archivo
> común y reescribe el provider `colabhive` entero; para revisar esta config usá
> `colabhive agents doctor`, que sólo lee.

## Instalación, de punta a punta

Desde la raíz de este repo. Necesitás [OpenCode](https://opencode.ai) instalado y una API key
de ColabHive (empieza con `hive_`; se crea en
[console.colabhive.com](https://console.colabhive.com/builder/settings/api-keys)).

```bash
# 1. la API key: se guarda en ~/.config/colabhive/env (chmod 600) y se valida
bash colabhive/scripts/set-api-key.sh

# 2. enlazar la config (los DOS symlinks: el JSON y el directorio de prompts).
#    Esto REEMPLAZA tu opencode.json global y tu carpeta prompts/: si ya existían,
#    quedan guardadas como .bak
mkdir -p ~/.config/opencode
for f in opencode.json prompts; do
  [ -e ~/.config/opencode/$f ] && [ ! -L ~/.config/opencode/$f ] \
    && mv ~/.config/opencode/$f ~/.config/opencode/$f.bak
done
ln -sfn "$PWD/colabhive/config/opencode.json" ~/.config/opencode/opencode.json
ln -sfn "$PWD/colabhive/config/prompts"       ~/.config/opencode/prompts

# 3. el atajo `oc` en el PATH (encuentra el repo solo, siguiendo el symlink)
mkdir -p ~/bin && ln -sfn "$PWD/colabhive/scripts/oc" ~/bin/oc
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc     # o ~/.bashrc, para las terminales nuevas
export PATH="$HOME/bin:$PATH"                         # y para esta

# 4. ajustar el contexto de cada modelo al real y verificar que todo responda
source ~/.config/colabhive/env
python3 colabhive/scripts/sync_limits.py --write
oc --status
```

Si tus endpoints son otros, cambiá los ids en `config/opencode.json`: la clave de cada
modelo es el id que devuelve `GET /v1/models` (`colabhive agents models --json` los lista).
Si cambiás de modelos, actualizá también los ids de `scripts/warm.sh` y los nombres de
`scripts/_status.py`, que usan `oc --warm` y `oc --status`.

## Operación diaria

```bash
oc --status     # ● warm  ◐ cached  ○ cold
oc --warm       # despierta a los tres modelos (hacelo antes de cada tanda)
oc              # abre la TUI en el directorio actual
oc "tarea"      # una tarea suelta
```

## Medición

| Script | Para qué |
|---|---|
| `sync_limits.py` | ajusta `limit.context` al `max_model_len` real de cada réplica |
| `check_cache.py` | ¿hay prefix caching? (la diferencia medida fue 43 s vs 2,6 s por paso) |
| `concurrencia.py` | techo de paralelismo por modelo (el medido el 2026-09-21: 8 por réplica) |
| `smoke_test.py` | tool calling, warmup y tokens/s de un endpoint |
| `keepalive_burst.py` | TTFT sobre conexión reutilizada, después de una pausa |

Los tres primeros conviene correrlos antes de una tanda: los modelos se enfrían, las
réplicas cambian de ventana al reemplazarse y el caching depende de cómo se levantó el motor.

## Si no usás ColabHive

El método no cambia; cambia el `baseURL` y los ids de modelo. Con vLLM local u Ollama,
ver [../INFRAESTRUCTURA.md §6](../INFRAESTRUCTURA.md). Lo único no negociable es que el
modelo tenga **tool calling habilitado** del lado del servidor.
