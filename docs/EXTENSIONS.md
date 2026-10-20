# Add your own extension

Harness² lets you change an agent's instructions, skills, scripts, and hooks. You can also extend the Python code to run new task suites or agent CLIs.

Choose the smallest change that fits your goal.

| Goal | Start here | Python changes? |
| --- | --- | --- |
| Teach Codex or OpenCode a repeatable workflow | [Add a harness component](#add-a-harness-component) | No |
| Evaluate agents on your own tasks | [Add a task suite](#add-a-task-suite) | Yes |
| Run another agent CLI | [Add an agent runtime](#add-an-agent-runtime) | Yes |
| Use another model endpoint | [Configure a model endpoint](#configure-a-model-endpoint) | Sometimes |

The current release runs OpenCode (`oc`) and Codex (`cx`) against JobBench (`jb`), LAB (`lab`), and WorkBuddy-Bench (`wb`). These are explicit integrations, not dynamically discovered plugins. See [`harness2/cli/_common.py`](../harness2/cli/_common.py).

## Check the local example first

From the repository root, use Linux, Python 3.12, and `uv`:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e '.[render]'
harness2-demo --output /tmp/harness2-extension-demo --k 1
```

The demo exercises both recursion modes on two deterministic ledger tasks. It calls no AI model and needs no Google Cloud credentials. Check `/tmp/harness2-extension-demo/demo.json` for `"done": 2` and `"failed": 0`. Its implementation, [`DemoAdapter`](../harness2/demo.py), is also the smallest working example of a task adapter.

This demo checks the shared improvement workflow. It does **not** test a new external agent runtime or your model connection.

## Add a harness component

Use an existing runtime when you want to change how an agent approaches a task. A component is a file in a *harness tree* that Harness² can validate and install into a task workspace. Simply putting a skill in this repository does not install it into every run.

For a Codex example, create the following files under a temporary directory named `example-harness/`.

**`example-harness/AGENTS.md`**

```markdown
When calculating ledger totals, read `.agents/skills/check_csv_totals/SKILL.md`
and follow it before reporting the result.
```

**`example-harness/.agents/skills/check_csv_totals/SKILL.md`**

```markdown
---
name: check_csv_totals
description: Calculate signed ledger totals with exact decimal arithmetic.
---

# Check CSV totals

Run `python3 scripts/check_csv_totals.py <path-to-csv>` to sum the
`amount` column. Include negative entries. Report the computed total,
and check it against any total claimed in the task.
```

**`example-harness/scripts/check_csv_totals.py`**

```python
import csv
import sys
from decimal import Decimal

with open(sys.argv[1], newline="", encoding="utf-8") as source:
    total = sum(
        (Decimal(row["amount"]) for row in csv.DictReader(source)),
        Decimal("0"),
    )
print(f"{total:.2f}")
```

The skill advertises when to use it; the script performs the exact calculation. The script is an example, not part of the released Harness² package.

Verify the script's output:

```bash
printf 'amount\n10.00\n-2.50\n' > /tmp/harness2-ledger.csv
python3 example-harness/scripts/check_csv_totals.py /tmp/harness2-ledger.csv
# Expected: 7.50
```

Validate the harness files using Harness²'s own rules:

```bash
python3 - <<'PY'
from harness2.core import tree
from harness2.substrate.codex import CODEX_SURFACE

files = tree.read_tree(CODEX_SURFACE, "example-harness")
print(tree.validate(CODEX_SURFACE, files, allow_subagents=False))
PY
```

Expected counts include one skill and one script. Validation checks allowed paths, skill metadata and triggers, Python syntax, and script references. It does not prove Codex loaded the skill or that a task improved. To establish that, install the tree through a task adapter and compare real executions.

For OpenCode, use [`OPENCODE_SURFACE`](../harness2/substrate/opencode.py). Its files differ: always-on instructions live in `systemprompt.md` and `guardrails.md`; skills live at `skills/<name>/SKILL.md`. Codex uses `AGENTS.md`, `.agents/skills/`, and optional `.codex/hooks.json`. OpenCode supports `plugin/<name>.ts` instead of Codex hooks. See [`SurfaceSpec` and `validate()`](../harness2/core/tree.py) for the exact accepted paths and rules.

Keep the original harness tree intact while testing a candidate. Make the change in a disposable task workspace, then adopt it only after comparing the outputs.

## Add a task suite

A task suite defines **what work the agent receives** and **how its results are examined**. It is separate from the agent runtime and from the recursive improvement algorithm.

1. Start with [`harness2/demo.py`](../harness2/demo.py). Copy the `DemoAdapter` pattern into `harness2/benchmarks/<your_suite>.py`; do not modify the shared recursion code.
2. Define a [`BenchSpec`](../harness2/core/spec.py) with a unique `name`, `runs_root`, supported `install_mode`, task-focused `BenchPrompts`, and `proposer` and `selector` `ChannelSpec` values.
3. Implement the [`BenchmarkAdapter`](../harness2/core/spec.py) contract. Provide stable task IDs, domain grouping, the task prompt and source files, a base harness, harness validation, rollout execution, a readable trajectory, and extracted deliverables. For a scored benchmark, implement `score()`. The offline demo omits this because it does not run the benchmark judge.
4. Make `execute(task_id, harness_dir, run_id)` idempotent for the same run ID. Return a real run directory containing the output and recorded execution evidence.
5. Extend CLI registration and the benchmark-specific setup, readiness, and reporting paths listed below. Add focused tests for a base run, a changed harness, failed output, judging, and resume.

A task's improvement context comes from `task_prompt()`, `task_files()`, `trajectory()`, and `deliverable_text()`. `score()` is used by the separate judging command, **after** harness selection. Do not expose reference answers or grading criteria to the improver.

The release does not have one universal `register_benchmark()` call. These places require review when you add a task suite:

| File | What to change or check |
| --- | --- |
| [`cli/_common.py`](../harness2/cli/_common.py) | Add its benchmark token and adapter constructor. |
| [`cli/check.py`](../harness2/cli/check.py), [`cli/setup.py`](../harness2/cli/setup.py) | Accept the new benchmark and define its setup behavior. |
| [`preflight.py`](../harness2/preflight.py), [`install.py`](../harness2/install.py) | Replace or extend assumptions about the three bundled benchmark dependencies. |
| [`core/report.py`](../harness2/core/report.py), [`cli/judge.py`](../harness2/cli/judge.py) | Confirm that the new scoring data and model checks are handled correctly. |
| [`scripts/split_tasks.py`](../scripts/split_tasks.py), [`benchmarks/tasks.py`](../harness2/benchmarks/tasks.py) | Add task discovery or partition support if you intend to use these utilities. |

Use [`harness2/benchmarks/jobbench.py`](../harness2/benchmarks/jobbench.py) as a full integration reference. The small demo is a better starting point for a custom task set because it does not bring along JobBench's dataset and runner dependencies.

## Add an agent runtime

An agent runtime is the CLI or framework that executes a task with the proposed harness. Harness² calls it a *substrate* in the Python API.

1. Create `harness2/substrate/<your_runtime>.py` and implement [`Substrate`](../harness2/substrate/base.py). Use [`CodexSubstrate`](../harness2/substrate/codex.py) or [`OpencodeSubstrate`](../harness2/substrate/opencode.py) as the reference.
2. Define a `SurfaceSpec` for the files the runtime supports. Include its always-on instructions, skill paths, optional hook or plugin files, and validation rules.
3. Implement `materialise()` to stage a harness as the runtime's native configuration. Return an `Install` with a source-tree fingerprint.
4. Implement `execute()`, `read_trajectory()`, and `preflight()`. A trajectory should use the shared `[ACTION]`, `[OBSERVATION]`, and `[ERROR]` form expected by the improvement context.
5. Wire the runtime into the task adapters' launchers and CLI selection. Existing benchmark launchers contain runtime-specific behavior, so implementing `Substrate` alone does **not** make every benchmark compatible.

Review [`cli/_common.py`](../harness2/cli/_common.py) for `SUBSTRATES`, [`core/spec.py`](../harness2/core/spec.py) for `INSTALL_MODES`, [`cli/run_sweep.py`](../harness2/cli/run_sweep.py) for experiment identity, and [`config.py`](../harness2/config.py) and [`preflight.py`](../harness2/preflight.py) for model and runtime assumptions. Update tests that depend on the existing `oc` and `cx` choices.

Avoid changing the shared Propose–Probe–Compose logic in [`core/recursion.py`](../harness2/core/recursion.py) unless the experiment method itself needs to change.

## Configure a model endpoint

Adding another **model endpoint** is different from adding an agent runtime. For Codex, the existing release accepts a compatible Responses API endpoint through these environment variables:

```dotenv
HARNESS2_CODEX_BASE_URL=http://127.0.0.1:PORT/v1
HARNESS2_CODEX_API_KEY=YOUR_KEY
HARNESS2_CODEX_MODEL=YOUR_MODEL_ID
```

Set real values outside version control and rerun `harness2-setup <bench> --substrate cx` after changing the endpoint or model. Read [`docs/SETUP.md`](SETUP.md#codex-executor) for the complete supported configuration.

The included `harness2-bridge` is a **Vertex AI bridge**, not a general-purpose router. You do not need that bridge for an endpoint that already implements the required API. However, the bundled benchmarks can still require their own datasets, runtime dependencies, judge configuration, and provider checks. Changing the solver URL alone does not remove those requirements.

The improver and selector use the channels declared in [`ChannelSpec`](../harness2/core/spec.py); this release supports `opencode` and `claude_cli` channels for those roles. Supporting a completely new proposer provider or protocol may require changes in [`core/proposer.py`](../harness2/core/proposer.py).

## Verify before adopting an extension

Run the focused local regression suite after changing Python source:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m harness2.cli.demo --output /tmp/harness2-extension-regression --k 1
```

For a newly registered benchmark, preview its task selection without model calls:

```bash
harness2 --bench <your_bench> --substrate <your_runtime> --k 1 --dry-run
```

Then run **one real task** in an isolated workspace. Confirm that the agent received the modified harness, generated the requested files, produced a readable trajectory, and can resume without repeating completed work. Compare the result with the unchanged base harness using the same task and model. Only score a run after confirming the judge cannot leak answers into the improver's context.

**Security:** The released Codex executor uses `--dangerously-bypass-approvals-and-sandbox`, and default benchmark network access is unrestricted. Do not copy those defaults into work on private or production repositories. Isolate execution, restrict network access to what the task needs, and keep credentials out of the harness tree and saved trajectories. See [`docs/EXPERIMENTS.md`](EXPERIMENTS.md#web-access).

Store results under a distinct `HARNESS2_RUNS_DIR` when models, tasks, or run settings change. See [results and resume](EXPERIMENTS.md#results-and-resume).
