// Normalizes Claude Code and Codex hook payloads into a list of file changes:
// { path, tool, added }, where `added` is the new text for that file.
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

export function readPayload() {
  return JSON.parse(readFileSync(0, "utf8"));
}

export function projectRoot(payload) {
  if (process.env.CLAUDE_PROJECT_DIR) return process.env.CLAUDE_PROJECT_DIR;
  try {
    return execSync("git rev-parse --show-toplevel", { cwd: payload.cwd, encoding: "utf8" }).trim();
  } catch {
    return payload.cwd ?? process.cwd();
  }
}

function findPatch(value) {
  if (typeof value === "string") return value.includes("*** Begin Patch") ? value : null;
  if (Array.isArray(value)) return value.map(findPatch).find(Boolean) ?? null;
  if (value && typeof value === "object") return Object.values(value).map(findPatch).find(Boolean) ?? null;
  return null;
}

// Codex apply_patch: "*** Add File: p", "*** Update File: p", "*** Delete File: p",
// optionally followed by "*** Move to: p"; added lines start with "+".
function parsePatch(patch) {
  const changes = [];
  let current = null;
  for (const line of patch.split(/\r?\n/)) {
    const header = line.match(/^\*\*\* (Add|Update|Delete) File: (.+)$/);
    const move = line.match(/^\*\*\* Move to: (.+)$/);
    if (header) {
      current = { path: header[2].trim(), tool: `apply_patch:${header[1].toLowerCase()}`, added: [] };
      changes.push(current);
    } else if (move && current) {
      changes.push({ path: move[1].trim(), tool: "apply_patch:add", added: current.added });
    } else if (current && line.startsWith("+")) {
      current.added.push(line.slice(1));
    }
  }
  return changes.map((c) => ({ ...c, added: c.added.join("\n") }));
}

export function fileChanges(payload) {
  const ti = payload.tool_input ?? {};
  const patch = findPatch(ti);
  if (patch) return parsePatch(patch);

  const path = ti.file_path ?? ti.notebook_path;
  if (!path) return [];
  const added = [ti.content, ti.new_string, ti.new_source, ...(ti.edits ?? []).map((e) => e.new_string)]
    .filter((s) => typeof s === "string")
    .join("\n");
  return [{ path, tool: payload.tool_name, added }];
}
