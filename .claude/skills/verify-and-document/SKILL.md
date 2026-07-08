---
name: verify-and-document
description: Run the full verification suite for a completed Speckit feature in ADP (pytest, ruff, mypy, schema-drift gate, tsc, vitest, Playwright E2E) and, once green, confirm tasks.md is closed out and CLAUDE.md/HANDOFF.md reflect reality.
disable-model-invocation: true
metadata:
  author: house
---

## User Input

```text
$ARGUMENTS
```

Optional: a spec number or branch name (e.g. `032` or `032-governance-reporting`). If empty, resolve the feature from the current git branch if it matches `NNN-*`; otherwise ask which spec to verify.

## When to use

Run this after implementation work on a Speckit feature (`specs/NNN-*/`) is believed complete, before telling the user the feature is "done." Unlike llmasjudge, ADP's `/speckit-implement` typically embeds verification as literal checked-off tasks inside a "Polish" phase at the end of `tasks.md` (see e.g. `032-governance-reporting`'s T025–T028) — so this skill is less about retroactively marking checkboxes and more about (a) an independent, from-scratch confirmation pass rather than trusting `/speckit-implement`'s own self-reported checkmarks, and (b) catching the drift between `CLAUDE.md`/`HANDOFF.md` and actual repo state that this repo has a documented history of accumulating. **It never commits anything.**

## Steps

1. **Locate the feature**: resolve `specs/<NNN-name>/` from `$ARGUMENTS` or the current branch. Read `tasks.md` and `plan.md` — note whether the Polish phase's verification tasks are already checked, and don't just trust that; re-run them.

2. **Run verification, in this order, stopping at the first failure**:
   - `pytest tests/ --ignore=tests/integration -q --no-cov` from the repo root (unit + contract, no DB needed). If PostgreSQL is reachable and the feature touched persistence, also run `pytest tests/integration/`.
   - `ruff check src/`
   - `mypy src/`
   - `adp-generate --check` — the JSON-Schema drift gate; must exit 0. If it fails, the fix is `adp-generate` (regenerate) followed by a diff review, not silencing the check.
   - `cd web && npx tsc --noEmit` (equivalently `npm run build`, which also runs `vite build`)
   - `cd web && npx vitest run` (equivalently `npm run test:run`)
   - `cd web && npm run test:e2e:api` (Playwright API project — needs the backend running; use the `dev-server-up` skill first if it isn't)
   - If this feature touched browser-visible UI, also run the full `test:e2e` / `test:e2e:flows` project, not just the API-only one.

   If any step fails: report the failure plainly, leave `tasks.md`/`CLAUDE.md`/`HANDOFF.md` untouched, and stop.

3. **Confirm `tasks.md` matches reality**: every task should already be `[X]` from `/speckit-implement`, but cross-check the Polish-phase verification tasks specifically against what you just ran in step 2 (not what the task description merely claims) — if step 2 found a failure the task list says passed, that's a documentation bug in `tasks.md` itself, fix the checkbox back to `[ ]` and report it rather than leaving a false "done" mark in place.

4. **Update `CLAUDE.md`**:
   - Add this feature's line to `## Active Technologies` and `## Recent Changes`, matching the existing terse, single-paragraph-per-feature style (this file does not use llmasjudge's narrative "Recent Changes" or separate "Key Architectural Decisions" section — don't import that convention here, follow what's already in this file).
   - Bump the `Last updated:` line at the top.

5. **Check `HANDOFF.md` for staleness** — this file has a documented history of drifting badly behind actual repo state in ADP (it currently still describes `009-c4-workspace` as the in-progress feature needing implementation, while `CLAUDE.md`'s own `Recent Changes` shows features through `032` already done). If `HANDOFF.md` exists and describes a spec/branch that isn't the current one, or is missing recent completed specs from its "What Has Been Completed" table, flag this explicitly to the user and offer to update or remove it — don't silently leave a stale handoff doc that would mislead the next session, per this repo's own stated purpose for that file.

6. **Report, don't commit**: summarize what's green, what changed in `tasks.md`/`CLAUDE.md`/`HANDOFF.md`, and run `git status --short` to show what's uncommitted. State plainly that nothing was committed and that requires the user's explicit go-ahead.
