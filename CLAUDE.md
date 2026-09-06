# CLAUDE.md

Agent guidance for this project lives in **[AGENTS.md](AGENTS.md)** — read it first.

`AGENTS.md` is the canonical, tool-agnostic entry point: the manager/worker
operating model, environment setup, the mandatory delivery loop, the guardrails
`make gate` enforces, and the architecture traps that are easy to miss.

This file exists only so that Claude Code picks up the same instructions. Keep
content in `AGENTS.md`; do not duplicate it here.

Decide your role first, then read its contract:

- `agents/opus-manager.json` — session contract for the high-effort
  manager/architect: what it owns, how it delegates, how it verifies.
- `agents/sonnet-worker.json` — session contract for a low-effort worker
  subagent: scope, allowed commands, escalation triggers, report format.

Further context:

- `agents/repo-map.md` — module-by-module map of the codebase.
- `agents/pros-n-cons.md` — current strengths, caveats, and gaps.
- `agents/todo-n-fixme.md` — active open work.
- `plans/` — plans and definitions of done for larger changes.
