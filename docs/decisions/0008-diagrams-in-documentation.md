# ADR-0008 — Use Mermaid diagrams where structure is the point

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** Whether and how documentation carries diagrams.

## Context

Several things in this project are genuinely hard to hold in prose. The boundary
between deterministic code and model judgement (ADR-0005) spans five stages and
reverses twice. The authentication topology has two clients, two credential types
and one shared server, plus a fallback path. A board workflow is a sequence with two
marked positions in it.

Each of those was written as paragraphs and each took a reader more effort than it
should. Worse, one of them was *written wrongly in prose and nobody noticed* — the
board column order in ADR-0006 was asserted as a sequence that had never been
verified. A diagram would not have prevented the bad inference, but drawing a
sequence makes the claim that an order exists explicit, which invites checking it.

## Decision

Use Mermaid fenced code blocks (```` ```mermaid ````) where the subject is
structure: flow, sequence, topology, state. Prose stays the default; a diagram is
added when it replaces explanation rather than decorating it.

Constraints:

- **The source must read sensibly unrendered.** Not every viewer renders Mermaid, so
  node labels are written as readable text, not cryptic identifiers.
- **Never rely on colour alone** to carry meaning. Grouping, labels and position do
  the work; colour is at most reinforcement. This keeps diagrams legible in light
  and dark themes and to colour-blind readers.
- **No diagram for something a table does better.** Tabular data is a table.
- **A diagram that disagrees with the prose is a bug**, the same as a stale comment.

## Alternatives considered

### ASCII / Unicode box drawing — rejected, with one exception

Renders absolutely everywhere, including a terminal and a plain editor, and cannot
break.

Rejected as the default because it is laborious to edit — changing one node means
realigning everything around it, which in practice means diagrams stop being updated
and go stale. Staleness is the main failure mode of diagrams, so the format that is
cheapest to update wins.

Retained for the one case where rendering cannot be assumed at all: illustrative
output inside a terminal transcript or a `.env` comment.

### Images (PNG/SVG committed to the repo) — rejected

Best visual quality and no renderer dependency. Rejected because they are opaque to
diff and to review: a change shows as "the binary differed", which defeats the point
of keeping decisions reviewable. They also drift from the text with nothing to
signal it, and editing one needs a tool outside the repository.

### No diagrams, prose only — rejected

The status quo, and the reason this ADR exists. Prose is poor at topology, and the
project has already demonstrated that an unverified structural claim can hide
comfortably in a sentence.

### PlantUML — rejected

More expressive than Mermaid, especially for sequence diagrams. Rejected because it
needs a rendering toolchain, where Mermaid renders in GitHub with no setup. The
audience for these documents reads them on GitHub.

## Consequences

**Good**

- The code/model boundary, which is the project's central design idea, can be seen
  rather than reconstructed.
- Diagrams live in the same file as the prose and diff as text, so review catches
  them drifting.
- No tooling to install.

**Bad / accepted cost**

- Mermaid does not render in every viewer; in a plain editor the reader sees source.
  The readability constraint above limits the damage but does not remove it.
- Another artifact to keep honest. A wrong diagram is more persuasive than a wrong
  sentence, which makes it worse.
- Mermaid's layout is automatic and sometimes ugly, with limited recourse.

## Portability to a company setting

Portable if documents are read on GitHub, GitLab or anything else with Mermaid
support, which is most places. A company whose documentation lives in Confluence
should check rendering there before adopting this, since a page of unrendered
Mermaid source is worse than the prose it replaced.
