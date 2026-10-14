import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";
import { planRelease, git } from "./plan_release.mjs";
import { verifyRelease } from "./release_guard.mjs";

const temporaryRoot = resolve(process.env.RUNNER_TEMP || tmpdir());
const work = await mkdtemp(join(temporaryRoot, "discuss-plan-test-"));
try {
  const repo = join(work, "repo");
  git(work, "init", "--initial-branch=main", repo);
  await writeFile(join(repo, "fixture.txt"), "fixture\n");
  git(repo, "add", ".");
  const commit = message => git(repo, "-c", "user.name=s116821", "-c", "user.email=99853371+s116821@users.noreply.github.com", "commit", "--allow-empty", "-m", message);
  commit("chore(fixture): initial history");
  git(repo, "tag", "v1.1.0");
  // Preview must use the checked source even if the local main branch is stale.
  git(repo, "checkout", "-b", "fixture");
  const tags = git(repo, "tag", "--list");
  const main = git(repo, "rev-parse", "main");
  for (const [message, tag] of [
    ["docs(setup): clarification", ""],
    ["fix(runtime): correction", "v1.1.1"],
    ["feat(runtime): capability", "v1.2.0"],
    ["feat(runtime)!: replacement", "v2.0.0"],
  ]) {
    commit(message);
    const result = await planRelease(repo);
    assert.equal(result.tag, tag);
    assert.equal(result.commit, git(repo, "rev-parse", "HEAD"));
    assert.equal(git(repo, "tag", "--list"), tags, "preview created a source tag");
    assert.equal(git(repo, "rev-parse", "main"), main, "preview modified source main");
  }
  const context = {nextRelease: {gitTag: "v1.1.1", gitHead: "abc"}, env: {EXPECTED_TAG: "v1.1.1", EXPECTED_COMMIT: "abc"}};
  verifyRelease({}, context);
  assert.throws(() => verifyRelease({}, {...context, env: {}}));
  assert.throws(() => verifyRelease({}, {...context, env: {...context.env, EXPECTED_TAG: "v1.1.2"}}));
  assert.throws(() => verifyRelease({}, {...context, env: {...context.env, EXPECTED_COMMIT: "def"}}));
  console.log("Release preview and pre-tag source/version guard passed");
} finally {
  if (!resolve(work).startsWith(temporaryRoot + sep)) throw new Error("Fixture escaped temporary root");
  await rm(work, {recursive: true, force: true});
}
