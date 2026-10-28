import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {mkdtemp, readFile, rm, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join, resolve, sep} from "node:path";
import {fileURLToPath} from "node:url";
import {verifyRelease} from "@semantic-release/exec";

const root = fileURLToPath(new URL("../../", import.meta.url));
const git = (cwd, ...args) => execFileSync("pwsh", ["-File", join(root, "scripts/git.ps1"), ...args], {cwd, encoding: "utf8"}).trim();
const workflow = await readFile(join(root, ".github/workflows/ci.yml"), "utf8");
// Execute the actual workflow program so the fixture cannot drift from CI.
const program = workflow.match(/node --input-type=module <<'JS'\r?\n([\s\S]*?)\r?\n          JS/)[1]
  .replace(/^          /gm, "")
  .replace("from 'semantic-release'", `from '${import.meta.resolve("semantic-release")}'`);
const config = JSON.parse(await readFile(join(root, ".releaserc.json"), "utf8"));
const guard = config.plugins.find(plugin => Array.isArray(plugin) && plugin[0] === "@semantic-release/exec")[1];
const work = await mkdtemp(join(tmpdir(), "discuss-release-test-"));
try {
  const repo = join(work, "repo");
  git(work, "init", "--initial-branch=main", repo);
  await writeFile(join(repo, "fixture.txt"), "fixture\n");
  await writeFile(join(repo, ".releaserc.json"), JSON.stringify(config));
  git(repo, "add", ".");
  const commit = message => git(repo, "-c", "user.name=s116821", "-c", "user.email=99853371+s116821@users.noreply.github.com", "commit", "--allow-empty", "-m", message);
  commit("chore(fixture): initial history");
  git(repo, "tag", "v1.1.0");
  const tags = git(repo, "tag", "--list");
  const output = join(work, "output");
  for (const [message, tag] of [
    ["docs(setup): clarification", ""],
    ["fix(runtime): correction", "v1.1.1"],
    ["feat(runtime): capability", "v1.2.0"],
    ["feat(runtime)!: replacement", "v2.0.0"],
  ]) {
    commit(message);
    const head = git(repo, "rev-parse", "HEAD");
    await writeFile(output, "");
    execFileSync(process.execPath, ["--input-type=module", "-"], {
      cwd: repo, input: program, stdio: ["pipe", "pipe", "inherit"],
      env: {...process.env, GITHUB_OUTPUT: output, GITHUB_ACTIONS: "true", GITHUB_REF: "refs/heads/main", GITHUB_EVENT_NAME: "push", GITHUB_HEAD_REF: ""},
    });
    assert.equal(await readFile(output, "utf8"), `tag=${tag}\n`);
    assert.equal(git(repo, "tag", "--list"), tags, "preview created a tag");
    assert.equal(git(repo, "rev-parse", "HEAD"), head, "preview changed source");
  }
  const context = {
    cwd: repo, env: {...process.env, EXPECTED_TAG: "v1.1.1", EXPECTED_COMMIT: "abc"},
    nextRelease: {gitTag: "v1.1.1", gitHead: "abc"},
    stdout: process.stdout, stderr: process.stderr, logger: {log() {}},
  };
  await verifyRelease(guard, context);
  for (const env of [{}, {EXPECTED_TAG: "v1.1.2", EXPECTED_COMMIT: "abc"}, {EXPECTED_TAG: "v1.1.1", EXPECTED_COMMIT: "def"}]) {
    await assert.rejects(verifyRelease(guard, {...context, env: {...process.env, ...env}}));
  }
  console.log("Workflow preview and official pre-tag source/version guard passed");
} finally {
  if (!resolve(work).startsWith(resolve(tmpdir()) + sep)) throw Error("Fixture escaped temporary root");
  await rm(work, {recursive: true, force: true});
}
