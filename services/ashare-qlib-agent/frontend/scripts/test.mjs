import { spawn } from "node:child_process";

const args = process.argv.slice(2).filter((arg) => arg !== "--runInBand");
const child = spawn("vitest", ["run", ...args], {
  stdio: "inherit",
});

child.on("exit", (code) => {
  process.exit(code ?? 1);
});
