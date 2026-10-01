# ADR-0006 — Trigger by deterministic poller, not a watching agent

- **Status:** Deferred
- **Date:** 2026-10-01
- **Decides:** What detects a card entering "In development" and starts a run.
- **Revisit when:** Step 2 begins, which is the first step that needs a trigger.

## Context

The end goal starts with "a Jira card moving to In development". Something has to
notice. Three mechanisms are possible, and the question was raised as an open one —
the preference expressed was for "an agent" to notice the transition, without a
settled view on how.

Worth separating two things that the word "agent" tends to merge: *noticing that
state changed* and *deciding what to do about it*. Only the second needs judgement.

## Decision (proposed, not in force)

A deterministic poller: a Python process queries Jira on an interval with JQL for
cards in "In development", keeps a small local record of which keys it has already
handed off, and invokes the pipeline for each new one.

The model is invoked after the handoff, for subtask breakdown — not for detection.

Deferred because Step 1 (ADR-0002) is invoked manually by issue key and needs no
trigger. Deferring costs nothing provided the fetch layer is callable by a poller,
which it is by construction.

## Alternatives considered

### An LLM agent watching Jira — rejected, with reasoning worth recording

This was the initial preference, so the reasoning against it matters more than the
conclusion.

An agent that continuously watches Jira is, mechanically, a poll loop — there is no
mechanism by which a model is notified of a Jira change; something must still ask
Jira, on an interval. The difference is that each tick additionally pays for an
inference call to answer a question with a precise, cheap, deterministic answer:
`status = "In development"` either matches or it does not. JQL answers it exactly.

So the comparison is not "agent vs. polling". It is "polling" against "polling, plus
a token-billed inference call on every tick, plus a chance of the model misreading
state it was handed correctly". Latency rises, cost scales with poll frequency, and
a false negative means a card silently never gets picked up — the worst failure mode
available, because nothing errors.

The appeal of the idea is real but belongs one step later. What is wanted from "an
agent" is that the system responds intelligently to a card appearing. It can: the
poller detects, then hands a real card to a model that decides how to break it down
and implement it. Judgement is applied where there is something to judge.

### Jira webhook — rejected for now, best long-term answer

The genuinely event-driven option: Jira pushes on transition, no polling, no
interval, immediate response, and no wasted requests.

Rejected for the sandbox because Jira Cloud must reach the listener over the public
internet, which from a laptop means a tunnel (ngrok, cloudflared) — another moving
part, a URL that changes between sessions, and webhook deliveries that are awkward
to replay while debugging. Polling can be run, interrupted, and re-run against the
same card freely.

**This is the right answer for a company deployment** and the reason this ADR is
Deferred rather than Accepted. Deciding "poller" permanently would be deciding it on
sandbox constraints that do not apply once there is a server with a stable address.

### Git hook or GitHub Action as the trigger — rejected

Wrong direction entirely. The pipeline is triggered by Jira and acts on GitHub; a
trigger on the GitHub side cannot observe a Jira transition.

## Consequences (of the proposed poller)

**Good**

- No inbound network exposure; works from a laptop with no tunnel.
- Detection is free, fast and exactly correct.
- Trivially debuggable: re-run the same query by hand and see what it returns.

**Bad / accepted cost**

- Latency up to one poll interval.
- Requires local state to avoid reprocessing a card, and that state is a real source
  of bugs — lose it and every in-progress card is reprocessed.
- Wasted requests when nothing changes; Jira API rate limits apply.
- Does not survive the machine being asleep, which a laptop does.

**Resolved 2026-10-01, against the real board**

- **The status name is `Development`, not "In development".** The completion status
  is `Review`, not "In review". Both names in the original specification were wrong,
  which is exactly why this was listed as something to confirm rather than assume.
- **Board column order**, from `/rest/agile/1.0/board/{id}/configuration`:

  `To Do → Analysis → Development → Review → Waiting Test → Test → Check → Done`

  `Review` is the column immediately after `Development`, so the pipeline's
  `Development → Review` move is an adjacent transition. That is the best case for
  Step 5 and makes a multi-hop walk very unlikely to be needed.

- **Correction, and a method note.** An earlier revision of this section asserted a
  different order — `Development → Check → Waiting Test → Test → Review` — and
  labelled it discovered. It was not. It came from `/project/{key}/statuses`, which
  returns an **unordered set of statuses per issue type**, printed alphabetically and
  then written up in a plausible-looking sequence. The user corrected it.

  The authoritative source for column order is the board configuration endpoint
  above, not the project statuses endpoint. Recorded because the failure mode is
  subtle: the statuses endpoint returns correct data that silently invites a wrong
  inference, and the resulting claim looked like a discovery.

- **The project is team-managed** (`style: next-gen`, `simplified: true`). The
  classic workflow endpoints (`/workflowscheme/project`, `/workflow/search`) return
  nothing useful for such a project, so **the legal transitions can still only be
  confirmed from an actual issue** via `/issue/{key}/transitions` or the equivalent
  MCP tool. Column adjacency makes the transition likely but does not prove it is
  permitted.

**Open questions for when this is revisited**
- Whether to match on current status or on a transition event. Current status plus
  local state is simpler; it cannot distinguish a card that entered the status from
  one that has been sitting there since before the pipeline existed. A first run
  against a populated board would pick up everything.
- Where handoff state lives, and what happens when a run fails partway.

## Portability to a company setting

The poller is sandbox convenience. A company deployment should use webhooks — stable
endpoint, immediate response, no polling cost, no local state file as a single point
of failure.

The part that is portable is the boundary: detection is deterministic, breakdown is
model judgement. That holds whichever mechanism does the detecting, and it is the
reason switching from poller to webhook later is a small change rather than a
redesign.
