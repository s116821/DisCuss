import semanticRelease from "semantic-release";
import { execFileSync } from "node:child_process";
import { appendFile, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const gitScript = join(root, "scripts/git.ps1");
export const git = (cwd, ...args) => execFileSync("pwsh", ["-File", gitScript, ...args], {cwd, encoding: "utf8"}).trim();

export async function planRelease(cwd = process.cwd()) {
  const config = JSON.parse(await readFile(join(root, ".releaserc.json"), "utf8"));
  const temporaryRoot = resolve(process.env.RUNNER_TEMP || tmpdir());
  const work = await mkdtemp(join(temporaryRoot, "discuss-release-plan-"));
  try {
    const mirror = join(work, "mirror.git");
    git(cwd, "clone", "--mirror", "--no-hardlinks", ".", mirror);
    git(cwd, "--git-dir", mirror, "update-ref", "refs/heads/main", git(cwd, "rev-parse", "HEAD"));
    git(cwd, "--git-dir", mirror, "symbolic-ref", "HEAD", "refs/heads/main");
    const checkout = join(work, "checkout");
    git(cwd, "clone", "--no-hardlinks", "--branch", "main", mirror, checkout);
    const result = await semanticRelease({
      ...config, repositoryUrl: pathToFileURL(mirror).href, dryRun: true, noCi: true,
      plugins: [[fileURLToPath(import.meta.resolve("@semantic-release/commit-analyzer")), config.plugins[0][1]]],
    }, {cwd: checkout, env: {...process.env, GITHUB_ACTIONS: "true", GITHUB_REF: "refs/heads/main", GITHUB_EVENT_NAME: "push", GITHUB_HEAD_REF: ""}});
    return result ? {tag: result.nextRelease.gitTag, commit: result.nextRelease.gitHead} : {tag: "", commit: git(cwd, "rev-parse", "HEAD")};
  } finally {
    if (!resolve(work).startsWith(temporaryRoot + sep)) throw new Error("Preview directory escaped temporary root");
    await rm(work, {recursive: true, force: true});
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const plan = await planRelease();
  if (process.env.GITHUB_OUTPUT) await appendFile(process.env.GITHUB_OUTPUT, `tag=${plan.tag}\ncommit=${plan.commit}\n`);
  console.log(JSON.stringify(plan));
}
