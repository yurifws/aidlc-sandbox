# ADR-0011 — Subtask plans stay in a local file; Jira subtasks deferred

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** Where the subtasks produced by Stage 3 live.
- **Revisit when:** plans have been judged good on real cards, and before Stage 5,
  which may want subtasks visible on the board.

## Context

The end goal says a card "gets broken into subtasks". That can mean a plan the
pipeline follows, or real Subtask issues under the card in Jira. The project's issue
types include Subtask, so the second is possible.

Stage 3 is also the first stage whose output is a model's judgement. Until a few
plans have been read by a person, nobody knows whether they are good.

## Decision

Stage 3 writes the plan to `.aidlc/runs/<KEY>/plan.json` and nowhere else. No Jira
writes. Chosen by the user over also creating Jira subtasks, and over posting the
plan as a comment.

The plan format is designed so that each subtask could become a Jira subtask later
without changing it: each has a title, a description and its own done-when checks.

## Alternatives considered

### Also create real Jira subtasks — deferred

Makes the breakdown visible on the board, and subtasks can be tracked and checked
off. Deferred because it adds writes through `createJiraIssue`, which is untested,
and because re-running a card would need duplicate detection, which is real work.
More importantly, it would publish model-made plans to the board before anyone has
judged whether they are good.

### Post the plan as a comment on the card — rejected for now

One simple write and visible to whoever reads the card. Rejected for the same
publishing reason, and because a comment cannot be tracked or checked off.

## Consequences

**Good**

- Plan quality can be judged on its own, with no side effects to undo.
- Re-running a breakdown overwrites a file, not a set of Jira issues.

**Bad / accepted cost**

- Nobody looking at the board can see the plan. For now it is a file on one machine.

## Portability to a company setting

A team will likely want the breakdown visible in Jira, as subtasks or as a comment
for review. That is a later decision, made once plan quality is known.
