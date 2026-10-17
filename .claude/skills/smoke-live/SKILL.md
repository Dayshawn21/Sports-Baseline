---
name: smoke-live
description: Run the scripted live smoke checks (health, security headers, CORS, admin 401, rate limit per client, web headers) against the hosted Render demo. Use only when the user explicitly runs /smoke-live or invokes $smoke-live.
disable-model-invocation: true
argument-hint: "[api-origin] [web-origin]"
---

# Live smoke test

Read-only HTTP checks against the hosted demo. It sends 12 requests to one heavy
route and nothing that writes data or spends provider quota.

## Steps

1. **Origins.** Use `$ARGUMENTS` if given. Otherwise take the latest live URLs
   recorded under Testing in `blueprint/context/current-feature.md` (or the
   archived 37d spec under `blueprint/history/features/`). State which URLs you
   use.
2. **Run** from the repo root:
   `bash <this skill's folder>/smoke.sh <api-origin> <web-origin>`.
   The skill folder is `.claude/skills/smoke-live/` (Claude Code) or
   `.agents/skills/smoke-live/` (Codex). A cold instance can take about 40 s on
   the first request; the script waits up to 90 s.
   - For the signed-in admin check, the owner exports `ADMIN_API_KEY` in their
     own shell first. Never ask for the key, read it from a file, or echo it.
3. **Report** the PASS/FAIL lines as a table and the exit code. For any FAIL,
   name the likely cause (for example a missing `--proxy-headers`, a
   `CORS_ORIGINS` typo, or the instance restarting mid-run) without changing
   anything.
4. **Manual checks the script cannot do**, listed for the owner: the browser
   page sweep with no console errors, the key absent from public requests in
   the network tab, and the Render Events tab showing no failed health check.
5. When a feature or fix is active, offer to record the results under its
   Testing section.
