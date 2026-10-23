// PreToolUse guard for files the project rules say are never hand-edited.
// Exit 2 refuses the edit and shows the reason to the agent.
import { existsSync } from "node:fs";
import { relative, resolve } from "node:path";
import { fileChanges, projectRoot, readPayload } from "./lib.mjs";

const payload = readPayload();
const root = projectRoot(payload);

const GENERATED_FITS = new Set([
  "api/app/core/nfl_over_probability_fit.py",
  "api/app/core/nba_over_probability_fit.py",
  "api/app/core/nba_over_probability_v2_fit.py",
  "api/app/core/tennis_market_blend_fit.py",
]);

function reasonFor({ path, tool }) {
  const abs = resolve(root, path);
  const rel = relative(root, abs).replaceAll("\\", "/");
  const name = rel.split("/").pop();

  if (/^\.env(\..+)?$/.test(name) && name !== ".env.example") {
    return [rel, "secrets live in .env; ask the owner to change it."];
  }
  if (/^api\/app\/db\/migrations\/versions\/\d{4}_.+\.py$/.test(rel) && existsSync(abs)) {
    return [rel, 'applied migrations are never edited. Write a new one with `alembic revision -m "..."`.'];
  }
  if (GENERATED_FITS.has(rel)) {
    return [rel, "this fit table is generated. Re-run its `python -m app.backtest.<name> --write` CLI instead."];
  }
  // /overview regenerates the overview with a full Write (Claude) or a patch (Codex),
  // so only Claude's partial edit tools are refused here.
  if (rel === "blueprint/context/project-overview.md" && /^(Edit|MultiEdit)$/.test(tool)) {
    return [rel, "the overview is generated. Change project-plan.md or build-plan.md and run /overview."];
  }
  return null;
}

const blocked = fileChanges(payload).map(reasonFor).filter(Boolean);
if (blocked.length) {
  process.stderr.write(blocked.map(([rel, why]) => `Blocked edit to ${rel}: ${why}`).join("\n") + "\n");
  process.exit(2);
}
process.exit(0);
