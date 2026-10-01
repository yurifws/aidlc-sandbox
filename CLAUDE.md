# aidlc-sandbox — working agreement

A local AI-DLC pipeline connecting Jira to this GitHub repo. End goal: a Jira card
moving to "In development" is broken into subtasks, implemented subtask by subtask
on one branch, a PR is opened, and the card moves to "In review".

This is a **prototype intended for adoption inside a company**. That purpose drives
the rule below: a design that works but cannot be explained or reproduced by someone
else is a failed design here.

## Rule 1 — No undocumented decisions

Every choice that someone could reasonably have made differently gets written down
**in the same change that makes it**. Not afterwards, not at the end of the project.

| Kind of decision | Goes in |
|---|---|
| Architecture, tooling, protocol, library, process | `docs/decisions/NNNN-slug.md` (ADR) |
| Anything a human must do by hand to reproduce the setup | `docs/SETUP.md` |
| Config keys, env vars, their meaning and where to get them | `.env.example` (committed, documented) |
| Why a step of the pipeline exists and what it emits | `docs/PIPELINE.md` |
| Why one specific change was made | The commit body (see Commits below) |

### What counts as a decision

- Choosing a library, runtime, protocol, or service.
- Choosing a name that becomes an interface: env vars, CLI commands, JSON field
  names, file layout.
- Choosing a boundary: what is deterministic code vs. what an LLM decides.
- Choosing *not* to do something now (record it as Deferred, with the trigger that
  would revisit it).
- Discovering a constraint that removed an option. The constraint is the valuable
  part — record it even though it felt like it decided itself.

### What does not

Formatting, obvious naming inside one function, anything with a single sensible
option. Do not pad the record; a log full of non-decisions is as unusable as no log.

## Rule 2 — Record the alternatives, not just the winner

An ADR that lists only the chosen option is worthless to the next reader, because
the question they arrive with is "why not the obvious thing?". Every ADR names the
alternatives actually considered and why each lost. If an option lost for a reason
specific to this sandbox (local, single user, no CI) say so explicitly — that reason
may not hold at company scale, and whoever reads this later needs to know which
conclusions are portable and which are not.

## Rule 3 — Supersede, never rewrite

When a decision changes: write a new ADR, set the old one's status to
`Superseded by ADR-NNNN`, and leave its body intact. The wrong turns are evidence.
Never edit a decided ADR to make past reasoning look better than it was.

## Rule 4 — Say when you are about to decide something implicitly

If work requires a choice that is not yet recorded, name it before proceeding, in
one line: *"this needs a decision on X; I'm proposing Y because Z"*. Then record it.
Silently picking a default and moving on is the specific failure this agreement
exists to prevent.

## Rule 5 — Honest status

Unverified means unverified. "Works" is a claim about a command that was run and
watched succeed. ADRs carry a `Status`: `Proposed` (written up, not agreed),
`Accepted` (agreed), `Deferred`, `Superseded`. Do not mark Accepted on the author's
own enthusiasm — only once the person has actually agreed.

## Commits

See ADR-0007. The `commit-craft:conventional-commits` skill is the authority on
format; load it before writing a commit message.

- **Conventional Commits**, summary at most 72 chars, imperative, lowercase, no
  trailing period.
- **One commit per unit of work** — one reason to be reverted. Never mix a refactor,
  a feature and reformatting.
- **The body records why**, not what. The diff already shows what.
- **Never `--no-verify`.** A failing hook is information; fix the cause.
- **Never `git add -A` unprompted**, and never commit without showing the message
  first. Staging is a decision about what belongs in the commit.

This is not hygiene. Stage 4 of the pipeline writes commits unattended, and that
history is the only record a reviewer has of how the work was sequenced. One
subtask, one commit.

## Diagrams

See ADR-0008. Draw a diagram where the subject is structure — flow, sequence,
topology, state — and prose would make the reader reconstruct it.

- **Mermaid fenced blocks**, so it renders on GitHub and diffs as text.
- **The source must read sensibly unrendered**: readable node labels, not `A1`.
- **Never carry meaning by colour alone.** Grouping and labels do the work, so the
  diagram survives dark mode and colour-blind readers.
- **A table is better for tabular data.** Do not draw one.
- **A diagram that disagrees with the prose is a bug**, like a stale comment.

## Secrets

`.env` is gitignored and holds real credentials. Never print a token value, never
paste one into a document or a commit, never ask for one in chat. `.env.example`
carries the key names and where to obtain each value, never the values.

## Build posture

One step at a time, each independently runnable and verifiable before the next
begins. Current step is recorded in `docs/PIPELINE.md`. Do not build ahead of it.
