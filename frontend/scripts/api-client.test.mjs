import assert from "node:assert/strict";
import test from "node:test";

import { formatApiError } from "../src/lib/api-errors.ts";
import { resolveApiBaseFromConfig } from "../src/lib/api-client.ts";

test("resolveApiBaseFromConfig returns configured URL", () => {
  assert.equal(
    resolveApiBaseFromConfig({
      configured: "https://example.test/api",
      basePath: "",
      apiPort: "8020",
      origin: "https://ai.silverlining.com.np",
      hostname: "ai.silverlining.com.np",
      protocol: "https:",
    }),
    "https://example.test/api",
  );
});

test("resolveApiBaseFromConfig supports reverse-proxy base path", () => {
  assert.equal(
    resolveApiBaseFromConfig({
      configured: "auto",
      basePath: "/lipiocr",
      apiPort: "8020",
      origin: "https://ai.silverlining.com.np",
      hostname: "ai.silverlining.com.np",
      protocol: "https:",
    }),
    "/lipiocr",
  );
});

test("formatApiError hides raw missing-key JSON", () => {
  assert.equal(formatApiError(401, '{"detail":"Missing API key"}'), "Operator API key required");
});
