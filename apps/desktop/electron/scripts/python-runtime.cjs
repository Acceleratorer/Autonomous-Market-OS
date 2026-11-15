"use strict";

const RUNTIME_MANIFEST_SCHEMA = "market-os.u6.4-python-runtime@v1";
const RUNTIME_VERSION_PATTERN = /^3\.11\.\d+$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

function fail(message) {
  throw new Error(message);
}

function isSafeRelativePath(value) {
  return typeof value === "string"
    && value.length > 0
    && !value.startsWith("/")
    && !value.startsWith("\\")
    && !/^[A-Za-z]:[\\/]/.test(value)
    && !value.split(/[\\/]+/).includes("..");
}

function validateRuntimeManifest(manifest, { target } = {}) {
  if (!manifest || manifest.schema !== RUNTIME_MANIFEST_SCHEMA) {
    fail("unexpected embedded Python runtime manifest schema");
  }
  if (manifest.distribution !== "cpython") fail("embedded Python runtime must be CPython");
  if (target && manifest.target !== target) fail("embedded Python runtime target does not match artifact target");
  if (!RUNTIME_VERSION_PATTERN.test(manifest.version || "")) {
    fail("embedded Python runtime must be an exact CPython 3.11 patch release");
  }
  if (manifest.source !== "python.org") fail("embedded Python runtime provenance must be python.org");
  if (typeof manifest.source_url !== "string" || !manifest.source_url.startsWith("https://www.python.org/ftp/python/")) {
    fail("embedded Python runtime source URL must be an official python.org release URL");
  }
  if (!SHA256_PATTERN.test(manifest.archive_sha256 || "")) fail("embedded Python runtime archive SHA-256 is invalid");
  if (!isSafeRelativePath(manifest.interpreter)) fail("embedded Python runtime interpreter path is unsafe");
  if (!Array.isArray(manifest.dependencies) || !manifest.dependencies.some((item) => /^duckdb(?:[<>=]|$)/.test(item))) {
    fail("embedded Python runtime must declare duckdb dependencies");
  }
  if (!manifest.dependencies.some((item) => /^pyarrow(?:[<>=]|$)/.test(item))) {
    fail("embedded Python runtime must declare pyarrow dependencies");
  }
  return {
    schema: manifest.schema,
    distribution: manifest.distribution,
    version: manifest.version,
    target: manifest.target,
    source: manifest.source,
    source_url: manifest.source_url,
    archive_sha256: manifest.archive_sha256,
    interpreter: manifest.interpreter,
    dependencies: [...manifest.dependencies],
  };
}

module.exports = {
  RUNTIME_MANIFEST_SCHEMA,
  RUNTIME_VERSION_PATTERN,
  isSafeRelativePath,
  validateRuntimeManifest,
};
