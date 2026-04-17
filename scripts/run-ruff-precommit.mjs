import { spawnSync } from "node:child_process";
import path from "node:path";

const stagedFiles = process.argv.slice(2);
const uvExecutable = process.platform === "win32" ? "uv.exe" : "uv";
const repoRoot = process.cwd();

if (stagedFiles.length === 0) {
  process.exit(0);
}

const groups = new Map();
const unsupportedFiles = [];

for (const file of stagedFiles) {
  const normalizedFile = normalizeFilePath(file);

  if (normalizedFile.startsWith("apps/api/")) {
    addFile("apps/api", normalizedFile);
    continue;
  }

  if (normalizedFile.startsWith("apps/pytorch-engine/")) {
    addFile("apps/pytorch-engine", normalizedFile);
    continue;
  }

  if (normalizedFile.startsWith("apps/model-service/")) {
    addFile("apps/model-service", normalizedFile);
    continue;
  }

  unsupportedFiles.push(normalizedFile);
}

if (unsupportedFiles.length > 0) {
  console.error("ruff pre-commit: unsupported Python file location.");
  console.error("Expected file under apps/api, apps/pytorch-engine, or apps/model-service.");
  printFileList(unsupportedFiles);
  process.exit(1);
}

for (const [projectDir, files] of groups) {
  console.log(`\n[ruff] ${projectDir}`);
  printFileList(files);

  const checkResult = runRuff(projectDir, ["check", "--fix", ...files]);
  if (checkResult !== 0) {
    process.exit(checkResult);
  }

  const formatResult = runRuff(projectDir, ["format", ...files]);
  if (formatResult !== 0) {
    process.exit(formatResult);
  }
}

function addFile(projectDir, file) {
  const existingFiles = groups.get(projectDir);

  if (existingFiles) {
    existingFiles.push(file);
    return;
  }

  groups.set(projectDir, [file]);
}

function runRuff(projectDir, args) {
  const command = [uvExecutable, "run", "--project", projectDir, "ruff", ...args];
  console.log(`$ ${command.join(" ")}`);

  const result = spawnSync(command[0], command.slice(1), {
    encoding: "utf8",
    stdio: "pipe",
  });

  if (result.stdout) {
    process.stdout.write(result.stdout);
  }

  if (result.stderr) {
    process.stderr.write(result.stderr);
  }

  if (result.error) {
    console.error(`ruff pre-commit: failed to start command for ${projectDir}.`);
    console.error(result.error.message);
    return 1;
  }

  return result.status ?? 1;
}

function printFileList(files) {
  for (const file of files) {
    console.log(` - ${file}`);
  }
}

function normalizeFilePath(file) {
  const absoluteFile = path.isAbsolute(file) ? file : path.resolve(repoRoot, file);
  const relativeFile = path.relative(repoRoot, absoluteFile);
  return relativeFile.replace(/\\/g, "/");
}
