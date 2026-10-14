export function verifyRelease(config, {nextRelease, env}) {
  if (!env.EXPECTED_TAG || !env.EXPECTED_COMMIT) throw new Error("Verified build identity is required before publication");
  if (nextRelease.gitTag !== env.EXPECTED_TAG || nextRelease.gitHead !== env.EXPECTED_COMMIT) {
    throw new Error("Final release identity differs from the validated build artifacts");
  }
}
