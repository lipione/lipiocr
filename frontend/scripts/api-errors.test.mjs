import assert from "node:assert/strict";
import test from "node:test";

import { formatApiError } from "../src/lib/api-errors.ts";

test("formats missing API key responses for operators", () => {
  assert.equal(formatApiError(401, '{"detail":"Missing API key"}'), "Operator session required");
});

test("formats invalid API key responses for operators", () => {
  assert.equal(formatApiError(401, '{"detail":"Invalid API key"}'), "Operator session expired or invalid");
});

test("formats missing session responses for operators", () => {
  assert.equal(formatApiError(401, '{"detail":"Missing operator session"}'), "Operator session required");
});

test("keeps non-auth API errors actionable", () => {
  assert.equal(formatApiError(403, '{"detail":"Role maker lacks export_case"}'), "403 Role maker lacks export_case");
});
