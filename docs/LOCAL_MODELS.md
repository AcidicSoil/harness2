# Self-hosted models (no paid API calls)

Harness² can use local inference without Vertex, Google Cloud CLI, or paid model keys.
The executor and improver use OpenCode's `provider/model` identifiers.
Harness² generates isolated, pinned-OpenCode-compatible routes under
`dependencies/opencode-config/` so an incompatible global OpenCode
configuration cannot affect this fork. Edit `.env`, not generated routes,
and rerun `harness2-setup` after model or endpoint changes. The judge uses
a model ID understood by its benchmark adapter.

## Configure

Start a compatible local server and load a **tool-capable** model with enough
context for the task. For LM Studio, for example:

```bash
lms load qwen3.5-9b-mtp --context-length 16384 --ttl 3600
```

Copy `.env.example` to `.env` and set these values, replacing the example model
ID with the **actual ID served by your endpoint**:

```dotenv
HARNESS2_SOLVER_MODEL=lmstudio/qwen3.5-9b-mtp
HARNESS2_IMPROVER_MODEL=lmstudio/qwen3.5-9b-mtp
HARNESS2_JUDGE_MODEL=openai/qwen3.5-9b-mtp
HARNESS2_JUDGE_BASE_URL=http://127.0.0.1:1234/v1
HARNESS2_JUDGE_API_KEY=local
OPENAI_BASE_URL=http://127.0.0.1:1234/v1
OPENAI_API_KEY=local
```

`openai/<id>` explicitly selects the LAB judge's OpenAI-compatible client. The
prefix is removed before the request, so JobBench and LAB both send `<id>` to
the backend. `local` is a placeholder bearer token for an unauthenticated local
server; use a real secret only when your server requires one. Shell variables
override `.env`. Do **not** set Vertex credentials to run this configuration.

## Run

For JobBench:

```bash
harness2-setup jb
harness2-check --bench jb
harness2 --bench jb --k 1 --mode parallel --max-tasks 1
```

For LAB, install Pandoc and Poppler first and run `harness2-setup lab`; its
judge reads `OPENAI_BASE_URL` and `OPENAI_API_KEY`. Local judging changes the
measured scores relative to the published benchmark baseline.

For WorkBuddy, Docker containers must be able to reach the host's model server:

```dotenv
HARNESS2_WB_BASE_URL=http://host.docker.internal:1234/v1
HARNESS2_WB_API_KEY=local
```

Ensure the model server accepts connections from the container network, then
run `harness2-setup wb --subset code`. The existing Vertex route remains
available when configured with a Vertex Gemini executor and judge.
WorkBuddy's upstream license has separate usage restrictions.

For Codex, use a **Responses API** endpoint. LM Studio supports `/v1/responses`:

```dotenv
HARNESS2_CODEX_BASE_URL=http://127.0.0.1:1234/v1
HARNESS2_CODEX_API_KEY=local
HARNESS2_CODEX_MODEL=qwen3.5-9b-mtp
```

Run `harness2-setup jb --substrate cx` to generate its Codex configuration;
check tool invocation and response content before any large benchmark run.

Do not enable fallback to hosted providers or expose model ports to untrusted
networks. Test one task first; a local API being reachable does not establish
benchmark fidelity or support for long-context agent rollouts.
