"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { uninstallPortable } = require("./install-portable.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { destination: null, json: null, markdown: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--destination") options.destination = argv[++index];
    else if (value === "--json") options.json = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/uninstall-portable.cjs --destination <dir> [--json <file>] [--markdown <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.destination) fail("--destination is required");
  return {
    destination: path.resolve(options.destination),
    json: options.json ? path.resolve(options.json) : null,
    markdown: options.markdown ? path.resolve(options.markdown) : null,
  };
}

function renderMarkdown(report) {
  return [
    "# U6.4-F Portable Uninstall",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Destination: \`${report.destination}\``,
    `- Application removed: **${report.application_removed}**`,
    `- Retained state: **${report.retained_data.preserved}**`,
    `- Retained state path: \`${report.retained_data.path || "none"}\``,
    `- Explicit state removal required: **${report.retained_data.removal_required}**`,
    "- Native service registration: **false**",
    "",
  ].join("\n");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const report = await uninstallPortable({ destination: options.destination });
  if (options.json) {
    await fsp.mkdir(path.dirname(options.json), { recursive: true });
    await fsp.writeFile(options.json, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }
  if (options.markdown) {
    await fsp.mkdir(path.dirname(options.markdown), { recursive: true });
    await fsp.writeFile(options.markdown, renderMarkdown(report), "utf8");
  }
  console.log(JSON.stringify(report, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { parseArgs, renderMarkdown };
