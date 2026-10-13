import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { analyzeCommits } from "@semantic-release/commit-analyzer";
const config = JSON.parse(await readFile(new URL("../.releaserc.json", import.meta.url), "utf8"));
const [plugin, options] = config.plugins[0];
assert.equal(plugin, "@semantic-release/commit-analyzer");
const fixtures = [
  ["docs(setup): clarify installation", null],
  ["feat(receiver): add sinks", "minor"],
  ["fix(receiver): repair teardown", "patch"],
  ["chore(deps): update pins", "patch"],
  ["refactor(receiver): simplify teardown", "patch"],
  ["perf(receiver): bound buffers", "patch"],
  ["test(receiver): add fixtures", "patch"],
  ["ci(checks): add matrix", "patch"],
  ["style(receiver): format", "patch"],
  ["build(package): include data", "patch"],
  ["feat(api)!: replace callback signature", "major"],
  ["fix(api): change callback\n\nBREAKING CHANGE: old signature removed", "major"],
  ["docs(api)!: document incompatible interface", "major"],
];
for (const [message, expected] of fixtures) {
  const actual = await analyzeCommits(options, { cwd: process.cwd(), commits: [{message, hash: "fixture"}], logger: {log() {}} });
  assert.equal(actual, expected, message);
}
console.log(`Configured semantic-release analyzer: ${fixtures.length} behavioral checks passed`);
