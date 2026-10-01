# ADR-0001 — Document every decision as it is made

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** What obligation accompanies a design choice in this project.

## Context

This pipeline is a sandbox, but not an experiment for its own sake: if it works it
is intended for adoption inside a company. That raises the bar on a prototype in a
specific way. The deliverable is not only working code — it is a set of choices a
colleague can evaluate, challenge and reproduce without the author present.

Prototypes built with an LLM accumulate decisions unusually fast and unusually
quietly. A model will pick a library, a transport, an env var name and a boundary
between code and prompt inside a single turn, each defensible, none announced. At
the end there is working software whose shape nobody chose on purpose. That is
tolerable for a throwaway and disqualifying for something being proposed to a team.

## Decision

Every choice that someone could reasonably have made differently is recorded in the
same change that makes it, in the location set out in `CLAUDE.md`. Architecture and
tooling choices become ADRs in this directory. Manual setup becomes `docs/SETUP.md`.
Config keys become documented entries in `.env.example`.

Each ADR names the alternatives actually considered and why each lost, and flags
whether its reasoning is portable to a company setting or is sandbox convenience.

Decisions are superseded, never rewritten.

## Alternatives considered

### Document at the end — rejected

The reasons for a choice are freshest at the moment it is made and are largely
unrecoverable a week later. Retrospective documentation reliably degrades into a
description of what the code does, which the code already states, while the
discarded alternatives — the actually scarce information — are gone.

### Document only "significant" decisions — rejected

Significance is only legible in hindsight. The two choices that have caused the most
trouble in this project so far looked incidental when made: which auth mechanism the
MCP server would accept, and where the boundary between deterministic code and model
judgement falls. A narrower rule would have skipped both.

### Rely on commit messages — rejected

Commits record what changed, are scoped to one diff, and are not read by someone
evaluating an approach. They cannot express "we considered X and rejected it", since
a rejected option produces no diff.

### Rely on code comments — rejected

Comments explain mechanism at the site of the code. They cannot hold a cross-cutting
choice such as "deterministic code watches, the model thinks", and they disappear
when the code they annotate is refactored.

## Consequences

**Good**

- The pipeline arrives at the company as a reviewable argument, not a black box.
- Rejected options stay visible, so the same ground is not re-litigated.
- Constraints discovered the hard way — auth mechanisms, data formats — are recorded
  once instead of rediscovered.
- It constrains the assistant: a choice that cannot be justified in writing tends
  not to get made.

**Bad / accepted cost**

- Real overhead on every step. A one-file change can carry a document longer than
  the diff.
- Risk of dilution: if trivia gets recorded alongside substance the log stops being
  read. `CLAUDE.md` draws the line explicitly, and the line needs defending.
- The ADR set will contain records that look obvious in hindsight. That is the
  expected cost of not being able to tell in advance which ones those are.

## Portability to a company setting

The rule is the most portable thing here, and the main reason for it. A colleague
assessing this pipeline will ask why Jira is reached over MCP rather than REST, why
Python, and what the model is trusted to decide. Those answers exist in writing
because of this rule.

Two adjustments to expect at company scale: ADRs become reviewable artifacts with
named approvers rather than a solo log, and some decisions here marked Accepted will
need re-deciding against constraints this sandbox does not have — shared service
credentials, concurrent runs, audit requirements, more than one repository.
