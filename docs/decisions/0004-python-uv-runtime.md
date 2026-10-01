# ADR-0004 — Python with uv as the pipeline runtime

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** What language and dependency tooling the pipeline is written in.

## Context

The pipeline is glue: it talks to an MCP server over HTTP, shells out to `git`, `gh`
and `claude`, and moves JSON between stages. It is not the application under
development — this repository happens to be both the sandbox being modified and the
host of the automation, but the pipeline code itself has no requirement to match the
language of whatever it edits.

Available on the machine, verified: Node 22.20.0, Python 3.14.5, uv 0.11.30, gh
2.97.0, git 2.51.0, Docker 29.2.0. Not available: `jq`, `pipx`. Platform is Windows
11 with Git Bash alongside PowerShell.

## Decision

Python 3 with **uv** for dependency and environment management, in a `src/` layout
with a `pyproject.toml`. Dependencies: the MCP Python SDK, and `python-dotenv` for
configuration.

## Alternatives considered

### Node with TypeScript — rejected (close call)

Node 22 is present, `fetch` is built in, the MCP TypeScript SDK is the reference
implementation and tends to track the protocol most promptly, and no extra runtime
would be needed.

It lost narrowly. The deciding consideration was ergonomics for glue code that
shells out heavily — subprocess handling and text wrangling are less ceremonious in
Python — plus `uv` removing the install step entirely. Worth being honest: had this
repository been destined to hold a TypeScript application that the pipeline edits,
sharing one toolchain would probably have outweighed that.

### Bash with `gh` and `curl` — rejected

Zero runtime dependencies, which is appealing for something billed as local glue.
Rejected because `jq` is not installed and every stage of this pipeline passes
structured JSON. JSON manipulation in shell without `jq` is painful and error-prone,
and the target is Windows, where shell portability is a recurring tax rather than a
one-time cost.

### Python with pip and a venv — rejected

The conventional setup. `uv` is already installed, resolves and installs
substantially faster, and gives one reproducible `uv run` entry point with no
"activate the venv first" step to forget or document. No reason to prefer the slower
path.

## Consequences

**Good**

- `uv run` is the single entry point; no activation step, no documented venv dance.
- Lock file gives reproducible dependency resolution for whoever runs this next.
- Comfortable fit for subprocess-heavy orchestration.

**Bad / accepted cost**

- `uv` is an extra tool a colleague must install before the pipeline runs. It is one
  command, but it is one more thing than "you already have Node".
- The MCP Python SDK follows the TypeScript reference implementation rather than
  leading it, so new protocol features may land later here.
- Two language ecosystems in play if the sandbox application turns out to be
  JavaScript or TypeScript.

## Portability to a company setting

Portable, with the caveat that the choice was made on what happened to be installed
on one laptop. A company should re-decide against what its platform team actually
supports and already has in CI — if that is Node, the reasoning above is thin enough
to flip without much loss, since ADR-0005 confines the MCP interaction to a single
adapter module.

The `src/` layout and lock-file discipline are worth keeping either way.
