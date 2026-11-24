---
name: invariants-review
description: Read-only review of the current branch or named files against SportApp V2's load-bearing invariants (sport and odds-provider filters, NBA game types, modelled-market filters, import boundaries, holdout discipline, versions, history floors, gray signal colors, secrets, Render memory). Use when the user runs /invariants-review or $invariants-review, asks to check project invariants, or before /complete.
---

# Invariants review

Run the checklist in [`.claude/agents/invariants-reviewer.md`](../../../.claude/agents/invariants-reviewer.md)
(the Codex copy reads the same file from the repo root). It is the single source
for the invariants list, so update it there, not here.

- **Claude Code:** delegate to the `invariants-reviewer` subagent with the scope
  (default: current branch against `master` plus uncommitted changes), and
  relay its findings.
- **Codex and other tools:** read that file and follow its Scope, Invariants and
  Output sections directly.

Never edit files during the review. Fixes go through `/fix` or `/implement`.
