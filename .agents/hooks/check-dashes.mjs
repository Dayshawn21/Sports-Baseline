// PostToolUse check for the Writing rule in coding-standards.md: no em dash,
// en dash or ellipsis character in new text. Only inserted text is checked,
// because existing files still hold some and are not to be swept.
import { fileChanges, readPayload } from "./lib.mjs";

const TEXT_FILE = /\.(md|py|ts|tsx|js|mjs|css|ya?ml|toml|txt)$/i;
const BANNED = { "\u2014": "em dash", "\u2013": "en dash", "\u2026": "ellipsis" };

const reports = [];
for (const { path, added } of fileChanges(readPayload())) {
  if (!TEXT_FILE.test(path)) continue;
  const lines = added.split("\n").filter((l) => Object.keys(BANNED).some((ch) => l.includes(ch)));
  if (!lines.length) continue;
  const kinds = Object.entries(BANNED)
    .filter(([ch]) => added.includes(ch))
    .map(([, label]) => label)
    .join(", ");
  reports.push(`${path} (${kinds}):\n` + lines.slice(0, 5).map((l) => `  ${l.trim()}`).join("\n"));
}

if (reports.length) {
  process.stderr.write(
    "New text breaks the coding-standards.md Writing rule. Use a hyphen, comma, colon " +
      "or parentheses instead.\n" + reports.join("\n") + "\n",
  );
  process.exit(2);
}
process.exit(0);
