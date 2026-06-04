import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../src/app/demo/page.tsx", import.meta.url), "utf8");
const lab = readFileSync(new URL("../src/components/demo/demo-extraction-lab.tsx", import.meta.url), "utf8");

test("demo page renders the extraction lab", () => {
  assert.match(page, /DemoExtractionLab/);
});

test("demo extraction lab posts uploads to the demo API", () => {
  assert.match(lab, /\/api\/demo\/extract/);
  assert.match(lab, /Bilingual field pairing/);
  assert.match(lab, /Download JSON/);
});
