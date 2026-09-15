#!/usr/bin/env node
// Generate one image with the OpenAI Images API and save it to disk.
//
// Usage:
//   node generate.mjs (--prompt "<text>" | --prompt-file <path>) --out <file.png|.jpg|.webp>
//                     [--model gpt-image-2.5-sunburst] [--size 1536x1024] [--quality high]
//                     [--background opaque|transparent|auto] [--compression 0-100]
//   node generate.mjs --check
//
// Loads ./.env from the current directory (variables already set in the
// environment win), then reads OPENAI_API_KEY and optional OPENAI_BASE_URL.
// --check only verifies that a key is available; it never calls the API.
// Refuses to overwrite --out. Prints a JSON summary on success; on failure
// prints the API error to stderr and exits 1.

import { parseArgs } from "node:util";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const DEFAULT_MODEL = "gpt-image-2.5-sunburst";
const FORMATS = { ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp" };

function fail(message) {
  console.error(`Error: ${message}`);
  process.exit(1);
}

let values;
try {
  ({ values } = parseArgs({
    options: {
      prompt: { type: "string" },
      "prompt-file": { type: "string" },
      out: { type: "string" },
      model: { type: "string", default: DEFAULT_MODEL },
      size: { type: "string" },
      quality: { type: "string" },
      background: { type: "string" },
      compression: { type: "string" },
      check: { type: "boolean" },
    },
    strict: true,
  }));
} catch (err) {
  fail(err.message);
}

const envFile = path.resolve(".env");
const keyFromEnvironment = Boolean(process.env.OPENAI_API_KEY);
try {
  process.loadEnvFile(envFile);
} catch (err) {
  if (err.code !== "ENOENT") fail(`could not load ${envFile}: ${err.message}`);
}
const apiKey = process.env.OPENAI_API_KEY;
if (!apiKey) fail(`OPENAI_API_KEY is not set in the environment or ${envFile}`);
if (values.check) {
  console.log(`OPENAI_API_KEY found (${keyFromEnvironment ? "environment" : envFile})`);
  process.exit(0);
}

if (Boolean(values.prompt) === Boolean(values["prompt-file"])) {
  fail("pass exactly one of --prompt or --prompt-file");
}
if (!values.out) fail("--out is required");
const format = FORMATS[path.extname(values.out).toLowerCase()];
if (!format) fail(`--out must end in one of ${Object.keys(FORMATS).join(", ")}`);

const prompt = values.prompt ?? (await readFile(values["prompt-file"], "utf8")).trim();
if (!prompt) fail("prompt is empty");

const body = { model: values.model, prompt, output_format: format };
if (values.size) body.size = values.size;
if (values.quality) body.quality = values.quality;
if (values.background) body.background = values.background;
if (values.compression) body.output_compression = Number(values.compression);

const baseUrl = (process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1").replace(/\/+$/, "");
const res = await fetch(`${baseUrl}/images/generations`, {
  method: "POST",
  headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
const text = await res.text();
let json;
try {
  json = JSON.parse(text);
} catch {
  fail(`HTTP ${res.status}: non-JSON response: ${text.slice(0, 500)}`);
}
if (!res.ok) fail(`HTTP ${res.status}: ${json.error?.message ?? text.slice(0, 500)}`);

const image = json.data?.[0];
if (!image?.b64_json) fail(`response has no data[0].b64_json: ${text.slice(0, 500)}`);

await mkdir(path.dirname(path.resolve(values.out)), { recursive: true });
try {
  await writeFile(values.out, Buffer.from(image.b64_json, "base64"), { flag: "wx" });
} catch (err) {
  if (err.code === "EEXIST") fail(`${values.out} already exists; use a new filename (e.g. -v2)`);
  throw err;
}

console.log(
  JSON.stringify(
    {
      out: path.resolve(values.out),
      model: values.model,
      size: json.size ?? values.size ?? null,
      quality: json.quality ?? values.quality ?? null,
      revised_prompt: image.revised_prompt ?? null,
      usage: json.usage ?? null,
    },
    null,
    2,
  ),
);
