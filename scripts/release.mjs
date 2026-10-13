import semanticRelease from "semantic-release";
import { appendFile } from "node:fs/promises";
const result = await semanticRelease();
if (result && process.env.GITHUB_OUTPUT) {
  await appendFile(process.env.GITHUB_OUTPUT, `tag=${result.nextRelease.gitTag}\n`);
}
