# ADR-0010 — Break cards down with headless Claude Code, isolated and read-only

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** How Stage 3 asks a model to turn a card into a subtask plan, which
  model, and what the model is allowed to touch.

## Context

Stage 3 is the first stage where a model decides something (ADR-0005): given a
card, produce an ordered plan of subtasks, each of which becomes one commit in
Stage 4 (ADR-0007). A good plan depends on the code as much as on the card — which
files exist, how the CLI is laid out, what the tests look like — so the model needs
to be able to look at the repository.

On the development machine there was no `ANTHROPIC_API_KEY` and no `ant` CLI, but
Claude Code was installed and logged in.

Five probes against the real CLI shaped this decision more than the options did:

1. **The `claude` on PATH was 2.1.97, too old for the model.** The API answered
   *"Claude Code 2.1.97 does not support this model; version 2.1.280 or newer is
   required"*. The machine had three installs (native, npm, and the one bundled in
   the VS Code extension), and the oldest was first on PATH. Fixed with
   `claude update` (now 2.1.287).
2. **A failed run reports `subtype: "success"` with `is_error: true`.** Code that
   trusted `subtype` would have read an API error as a successful plan.
3. **Without stdin closed, the CLI waits 3 seconds** for input before continuing.
4. **With the user's normal configuration, a trivial run cost $0.35**, of which
   about 40,000 tokens were Claude Code's setup: system prompt, tool definitions,
   `CLAUDE.md`, and the user's installed plugins and skills. The user's personal
   MCP connectors (Gmail, Calendar, Drive) were also loaded into the run.
5. **`--allowedTools` alone did not reliably make the run read-only.** A shell
   command was refused only because it used output redirection, which implies a
   harmless command could have run.

## Decision

Stage 3 runs headless Claude Code in the repository, isolated from the machine's
configuration and limited to reading:

```
claude -p                       # prompt on stdin, which also avoids the 3s wait
  --output-format json
  --json-schema <plan schema>   # the answer arrives validated in structured_output
  --model claude-opus-5-5       # AIDLC_BREAKDOWN_MODEL
  --safe-mode                   # no CLAUDE.md, plugins, skills, hooks or MCP from the machine
  --restricted                  # no command- or code-running tools, no user settings files
  --tools Read,Glob,Grep        # the only built-in tools that exist in the run
  --allowedTools Read,Glob,Grep
  --strict-mcp-config           # and no MCP servers
  --max-budget-usd <cap>        # AIDLC_BREAKDOWN_BUDGET_USD, default 2.00
  --no-session-persistence
```

Verified with that exact configuration: the model reported its tools as `Glob`,
`Grep`, `Read` and the structured-output tool; an attempt to create a file found no
tool to do it with; nothing was written; and the trivial run cost **$0.056 instead
of $0.35**, with setup down from about 40,000 tokens to 5,000.

Because `--safe-mode` also drops `CLAUDE.md`, the prompt tells the model to read the
project's conventions itself (`CLAUDE.md`, ADR-0007, `docs/PIPELINE.md`). That is
deliberate: the context a plan is made from is then the same on every machine,
instead of depending on whatever is installed where it runs.

A run is a failure unless `is_error` is false **and** `structured_output` is
present; `subtype` is not consulted. The raw result is always kept beside the plan
for inspection.

**Model:** Claude Opus 5.5, chosen by the user over Sonnet 5.5 and over leaving it
to Claude Code's default. A breakdown is one short task that steers every later
stage, so the most capable default model costs little in absolute terms. Pinned
explicitly so runs stay comparable when Claude Code's default changes.

## Alternatives considered

### Claude API through the `anthropic` SDK — rejected

One structured request, simple and predictable, and the conventional way to call a
model from code. Rejected because the model could not look at the code unless the
pipeline packed files into the prompt itself, deciding in advance what is relevant;
and because it needed a new API key with separate billing. It remains the better
shape for a stage that needs no repository access.

### Claude Agent SDK — rejected

Claude Code as a Python library rather than a subprocess: the same capabilities with
a nicer interface. Rejected as a new dependency and an extra layer over a CLI that is
already installed and verified. Worth revisiting if Stage 4 needs finer control over
a running session than flags give.

### Headless Claude Code with the machine's normal configuration — rejected

What the first probe used. Rejected on three counts found above: six times the cost
per run, a plan made from context that differs per machine (whoever has which
plugins and skills installed), and personal connectors loaded into a run that sends
card content to a model.

### `--bare` — rejected for now, the likely company answer

Minimal mode, the most reproducible option. Rejected here because it reads only
`ANTHROPIC_API_KEY` (never an OAuth login), and the sandbox has no key. In a company
CI, where there is no personal login, it is probably the right choice; see
portability.

## Consequences

**Good**

- The plan is grounded in the real code, read by the model itself.
- The model cannot change anything: the tools to do so do not exist in the run.
- Identical context on every machine; no personal connectors near card content.
- Spending per run has a hard cap.
- Stage 4 will almost certainly also run Claude Code, so both model stages share one
  runtime and one way of being called.

**Bad / accepted cost**

- **A minimum CLI version is now a dependency** (2.1.280+ for Opus 5.5), and the
  machine's PATH decides which install runs. `doctor` checks it.
- Runs use the logged-in person's Claude account and count against its limits.
- Flags are the interface; a Claude Code release could change their behaviour. The
  probes above are the regression check to repeat after an upgrade.
- `total_cost_usd` is Claude Code's own estimate. Under a subscription it is not a
  bill, so the budget cap limits usage rather than money.

**Unverified at time of writing**

- A full breakdown of a real card. The probes asked trivial questions.
- That a long card description passes cleanly through stdin.

## Portability to a company setting

The isolation carries over unchanged and is the part to keep. The credential does
not: a CI runner has no personal login, so it needs `ANTHROPIC_API_KEY` (or an
`apiKeyHelper`), at which point `--bare` becomes available and the budget cap limits
real money. Pin the CLI version in CI rather than relying on whatever `claude update`
installs.

Card content is sent to Anthropic to make the plan. A company should confirm that is
acceptable under its data policy before pointing this at real projects.
