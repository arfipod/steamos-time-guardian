import { access, mkdir, rm, stat } from "node:fs/promises";
import { constants } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const checkOnly = process.argv.includes("--check");
const localTsc = resolve(root, "node_modules/.bin/tsc");
let command = "tsc";
try {
  await access(localTsc, constants.X_OK);
  command = localTsc;
} catch {
  // CI and bootstrap-dev install the pinned global TypeScript 5.8.3 compiler.
}
const version = spawnSync(command, ["--version"], { encoding: "utf8" });
if (version.status !== 0) {
  console.error("TypeScript compiler not found. Install TypeScript 5.8.3 or run scripts/bootstrap-dev.sh --online.");
  process.exit(1);
}
if (!/Version 5\.8\./.test(version.stdout)) {
  console.error(`Expected TypeScript 5.8.x, found ${version.stdout.trim()}`);
  process.exit(1);
}
if (!checkOnly) {
  await rm(resolve(root, "dist"), { recursive: true, force: true });
  await mkdir(resolve(root, "dist"), { recursive: true });
}
const args = ["-p", resolve(root, "tsconfig.json")];
if (checkOnly) args.push("--noEmit");
const result = spawnSync(command, args, { cwd: root, stdio: "inherit" });
if (result.status !== 0) process.exit(result.status ?? 1);
if (!checkOnly) {
  const output = resolve(root, "dist/index.js");
  const info = await stat(output);
  if (info.size < 1000) {
    console.error("Decky build output is unexpectedly small");
    process.exit(1);
  }
  console.log(`Built ${output} (${info.size} bytes)`);
}
