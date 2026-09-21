# Coding agents on open-weight models — method, config and a worked example

*[Castellano](LEEME.md)*

How to run a large project with coding agents (OpenCode) on 27B–30B open-weight models served
by [ColabHive](https://colabhive.com) — or by your own vLLM or Ollama. This repository is what
we learned doing it for real: the method, the complete OpenCode configuration for a three-model
team, the scripts, and a worked example that keeps everything that went wrong in plain sight.

The documents are written in Spanish. This page is the English entry point; the product
documentation is at [docs.colabhive.com/guides/agents](https://docs.colabhive.com/guides/agents).

## Five minutes: one model in OpenCode

```bash
pip install -U colabhive
export COLABHIVE_API_KEY=hive_...   # create one at console.colabhive.com → Settings → API keys
colabhive agents init               # picks a model, proves it with a real tool call, writes the config
opencode
```

`colabhive agents init` adds a ColabHive provider to your existing `opencode.json` and leaves
the rest of the file alone (it keeps a timestamped backup). `colabhive agents doctor` checks the
result. Step by step: [Quickstart](https://docs.colabhive.com/guides/agents/quickstart).

## The full team

One model is enough to try it. For a real project, split the work by what each model is good at —
the deciding factor is not a benchmark but **whether the model acts or deliberates**:

| OpenCode role | Model | Why |
|---|---|---|
| `plan` | gpt-oss-20b | reasons before splitting the work, and it is fast |
| `build`, `tester` | Qwen3-Coder-30B-A3B | instruct model: calls tools instead of deliberating |
| `reviewer` | Qwen3.8-27B FP8 | a thinking model — deliberation helps when reading a diff |
| `explore`, titles, summaries | gpt-oss-20b | the fastest to answer; a model that deliberates spends seconds on a title |

Install it with [`colabhive/README.md`](colabhive/README.md): API key, the config in
[`colabhive/config/opencode.json`](colabhive/config/opencode.json), the prompts, and the `oc`
shortcut (`oc --status`, `oc --warm`). **Pick one path or the other**: the five-minute path merges
into your `opencode.json`; the full-team path replaces it with a symlink to this repository's
file (your previous one is kept as `.bak`). More on choosing roles:
[Choosing a model team](https://docs.colabhive.com/guides/agents/model-team).

## The method, in three lines

> A human (or a large model) breaks the project down. The agent executes one task at a time.
> No task is done because the agent says so: a command decides.
> Retrying is cheap: launch several in parallel and discard the ones that went wrong.

Each task runs in its own git worktree with a clean context, and the project's `scripts/gate.sh` —
tests, scope and hygiene; the example's is [`ejemplo-pacman/scripts/gate.sh`](ejemplo-pacman/scripts/gate.sh)
— gives the verdict. The runner runs the gate after the agent has finished and decides on its exit
code, never on what the agent wrote: in our logs, an agent reported "GATE VERDE" (green) after seeing
the gate fail three times. The method, in English:
[The agent task method](https://docs.colabhive.com/concepts/agent-task-method).

## What to expect: the worked example

[`ejemplo-pacman/`](ejemplo-pacman/) is a terminal Pac-Man built this way, with its plan, 12 tasks,
the gate, 73 tests and a log of every run ([`BITACORA.md`](ejemplo-pacman/BITACORA.md)):

- **First round, 0 of 4 green on the first attempt.** The tasks asked for code and its tests in one
  step, one contradicted the map, and a thinking model used as the executor wrote 300+ lines of
  deliberation without touching a file. Most tasks ended up done by hand.
- **The game passed every test and was bad to play.** What the plan could not verify by command
  (several ghosts, smooth controls) never made it into a task.
- **Second round, 3 of 4 green on the first attempt**, after naming the required tests in each task,
  making contracts explicit and declaring the human check. Playing it still found five bugs, all in
  code that had no tests; a fake screen now tests the game loop.

Your first tasks will likely fail too. The lesson of the example is that when fewer than 30% of
the tasks pass on the first attempt, the problem is the plan, not the model.

## Files

| File | What it answers |
|---|---|
| [EMPEZAR.md](EMPEZAR.md) | From zero to the first task run by an agent |
| [METODO.md](METODO.md) | Principles, roles, gates G0–G3, how to run and what to measure |
| [DESCOMPOSICION.md](DESCOMPOSICION.md) | How to break a big project into tasks a 30B model can execute |
| [INFRAESTRUCTURA.md](INFRAESTRUCTURA.md) | Models, context windows, prefix caching, parallelism, traps |
| [OPENCODE.md](OPENCODE.md) | The OpenCode configuration, field by field, and cold starts |
| [colabhive/](colabhive/) | Config, prompts, setup and measurement scripts, dated measurements |
| [plantillas/](plantillas/) | Templates: plan, task, review checklist |
| [scripts/](scripts/) | `correr-tarea.sh` (run tasks in worktrees, in parallel), `estado.sh`, `comparar-modelos.sh` |
| [AGENTS.md](AGENTS.md) | Rules the agent reads on its own |

## Without ColabHive

The method does not change; the provider does. Point OpenCode at any OpenAI-compatible server
(vLLM, Ollama) — see [INFRAESTRUCTURA.md §6](INFRAESTRUCTURA.md). The one requirement is that the
server has **tool calling enabled** for the model.

## License

[MIT](LICENSE).
