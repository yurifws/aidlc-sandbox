# ADR-0007 — Conventional Commits, one commit per unit of work

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** The commit message format, and how changes are divided into commits.

## Context

The repository had no commits at all when this was decided, so there was no existing
history to stay consistent with — the convention could be chosen deliberately rather
than inherited.

There is a reason this matters more here than in an ordinary repository, and it is
easy to mistake for cosmetics. **Stage 4 of this pipeline writes commits
automatically.** A card is broken into subtasks and each subtask is implemented on
one branch. Whoever reviews the resulting PR will not have watched that happen; the
commit history is the only record of how the work was sequenced and of what the
model thought it was doing at each step. Stage 5 then derives the PR description
from those commits.

So the commit convention is not developer hygiene in this project. It is an output
contract of the pipeline, consumed by a human reviewer and by the PR-description
stage. A card that produces one opaque commit called "implement changes" has
destroyed the reviewability that the subtask-by-subtask design exists to create.

A project skill (`commit-craft:conventional-commits`) already defines the format in
detail, so the decision is to adopt it rather than to invent one.

## Decision

**Format:** Conventional Commits, per the `commit-craft:conventional-commits` skill,
which is the authority on the details. In outline:

```
<type>(<optional scope>): <summary at most 72 chars, imperative, lowercase>

<body: why, not what>

<footer: Refs #123, BREAKING CHANGE: ...>
```

Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `chore`. Chosen
by what the change *does*, not which files it touches.

**Granularity:** one commit per unit of work — one reason to be reverted. Concretely:

| Context | One commit is |
|---|---|
| Manual work in this repo | One coherent change |
| Stage 4 (pipeline-authored) | One subtask from the breakdown |

A commit mixing a refactor, a feature and reformatting is split before being
written, not explained away in the body.

**The body records why.** The diff already shows what changed; the reason is the part
that cannot be reconstructed later. For pipeline-authored commits this is where the
subtask's intent goes.

**No `--no-verify`, ever.** A failing hook is information. Bypassing it moves the
problem to CI or to someone else's machine.

**Approval.** Commit messages are shown before `git commit` runs, and nothing is
staged with `git add -A` on the assistant's own initiative — staging is a decision
about what belongs in the commit.

## Alternatives considered

### Free-form commit messages — rejected

The default, and workable in a repository where a human writes every commit and can
be asked what they meant. It fails here specifically because Stage 4 generates
commits unattended: without a required structure, the generated messages regress
toward "update files" and "implement subtask", which is precisely the information
loss this pipeline needs to avoid. A machine-authored history needs a stricter
convention than a human-authored one, not a looser one.

### One commit per card, squashed — rejected

Simpler to produce and matches how many teams squash-merge anyway. Rejected because
it discards the subtask sequence inside the branch, which is the main artifact of
Stage 4 and the only thing that makes a model-authored PR reviewable in pieces
rather than as a single wall of diff. Whether the *merge* squashes is a separate
question (see open questions) — the branch itself keeps the granularity.

### gitmoji — rejected

Prefixes type information with an emoji. Rejected on two counts: the convention this
project adopts explicitly forbids emoji in summaries, and emoji type markers are
harder to parse mechanically than text prefixes, which matters because Stage 5 reads
these commits.

### A custom scheme tailored to the pipeline — rejected

Tempting, since commits here carry a card key and a subtask index. Rejected because
Conventional Commits already has a footer for references (`Refs ABC-123`) and a scope
field, and because a bespoke format is one more thing a company adopting this would
have to learn and tool for. Standard beats clever.

## Consequences

**Good**

- Pipeline-authored history is reviewable subtask by subtask.
- Stage 5 can derive a PR description mechanically from typed, structured commits
  instead of inferring intent from diffs.
- Machine-checkable: the format can be enforced by a hook later without rewriting
  anything.
- Keeps the door open to generated changelogs and semantic versioning.
- Gives Stage 4 a crisp definition of done per subtask: one subtask, one commit.

**Bad / accepted cost**

- Choosing a type is a judgement call, and a model will sometimes get it wrong —
  `docs` when editing a `.md` file that actually contained wrong instructions and so
  should be `fix`. Expect to correct these.
- Granularity disputes are real and not fully settled by a rule. Subtasks that are
  too fine produce noisy history; too coarse and the reviewability benefit is lost.
  This lands on Stage 3, the breakdown, which means commit quality depends on
  breakdown quality.
- Overhead on trivial changes. A one-line typo fix carries a structured message.

**Unverified at time of writing**

- No commit has been made in this repository yet. The convention has not been
  exercised, by hand or by the pipeline.

## Open questions

- **Merge strategy.** Whether PRs squash-merge. If they do, the branch's per-subtask
  commits vanish from the main history and the PR title becomes the commit message —
  which makes the PR title a Conventional Commit too. Decide in Stage 5, not before.

  **Resolved 2026-10-01, earlier than planned: merge commits, not squash.** It came
  up with the first PR (#1, Step 1) rather than in Stage 5. Squashing would have
  collapsed Step 1's 22 commits into one on `main` and lost the decision trail that
  ADR-0001 exists to keep. PR #1 was merged with "Create a merge commit", so every
  commit is reachable from `main`. PR titles still follow the convention, since the
  merge commit message carries them. Stage 5 should open its PRs on the same basis.
- **Attribution of machine-authored commits.** Commits written by the pipeline
  should be identifiable as such. A trailer is the obvious mechanism. Not decided
  yet; raised under portability below because it matters far more in a company than
  here.
- **Enforcement.** Whether to add a `commit-msg` hook. Deferred until the pipeline
  actually generates commits, since there is nothing to enforce against yet.

## Portability to a company setting

The format is the most portable decision in this set — Conventional Commits is an
industry standard with existing tooling, and a company that already uses it needs no
adaptation.

Two things to settle before this runs in a company:

**A company likely already has a commit convention**, and it wins over this one.
The pipeline must therefore treat the convention as configuration, not as something
hardcoded into Stage 4's prompt. That is a design constraint on Stage 4 arising from
this ADR.

**Machine-authored commits need to be identifiable.** In this sandbox the author is
obvious. In a company, commits that a pipeline wrote and no human reviewed before
they landed are an audit question: `git log` should be able to answer "which of these
did a person write?". A `Co-authored-by` or custom trailer on pipeline-authored
commits is the cheap answer and should be decided alongside the service-account
question in ADR-0003, since both are about attributing automated action.
