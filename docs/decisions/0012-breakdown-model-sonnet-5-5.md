# ADR-0012 — The breakdown uses Sonnet 5.5, not Opus 5.5

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** Which model writes Stage 3's subtask plans.
- **Supersedes:** the model choice in ADR-0010. The rest of ADR-0010 (headless
  Claude Code, isolated and read-only) is unchanged and still in force.

## Context

ADR-0010 chose Claude Opus 5.5 for the breakdown, the default and most capable Opus,
on the reasoning that a breakdown is one short task that steers every later stage,
so its higher price costs little in absolute terms.

After seeing the first Opus plan and its cost, the user asked for Sonnet instead.
Sonnet 5.5 (`claude-sonnet-5-5`) is the current Sonnet: about half Opus 5.5's price
per token, and strong at everyday coding work.

## Decision

The default breakdown model is **`claude-sonnet-5-5`**. It is a setting
(`AIDLC_BREAKDOWN_MODEL`), so a team can choose Opus for harder projects without a
code change.

Both models planned the same card, KAN-1, with the same prompt, isolation and
budget, before this was written down:

| | Opus 5.5 | Sonnet 5.5 |
|---|---|---|
| Cost | $0.32 | $0.18 |
| Time | 34 s | 22 s |
| Subtasks / files / done-when checks | 1 / same 2 / 6 | 1 / same 2 / 6 |
| Acceptance criteria mapped | 4 | 5, also mapping the card's out-of-scope line |
| Open questions | 5 | 6, one of them a note that there was nothing to flag |

Read by a person, the plans were equally good: the same mechanism, the same subtlety
noticed (the flag works without a `.env`), the same warning that the branch had
uncommitted work, and the same real questions. Sonnet's title was cleaner (Opus had
put `feat(cli):` in it) and one of its checks was stronger: the tests must fail if
the flag is removed.

## Alternatives considered

### Keep Opus 5.5 — rejected by the user

The original choice. It remains the better bet for cards that need deeper reasoning
about unfamiliar code, and is one setting away.

### Leave the model to Claude Code's default — rejected

Rejected in ADR-0010 for the same reason as before: runs stop being comparable when
the default changes.

## Consequences

**Good**

- About 45% cheaper and a third faster per breakdown, at equal quality on the one
  card compared.

**Bad / accepted cost**

- **The evidence is one small card.** KAN-1 is a one-subtask change, where the
  models are least likely to differ. Plans for larger or vaguer cards should be read
  with the model in mind, and compared against Opus if they look weak.
- Sonnet's own minimum Claude Code version was not observed. The 2.1.280 floor
  `doctor` checks came from Opus 5.5 and is kept; 2.1.287 is verified with both.

## Portability to a company setting

Portable. The model is configuration, and a team would pick it per project, ideally
after comparing plans on a few of its own cards the way this ADR did.
