import assert from "node:assert/strict";
import test from "node:test";

import { jobStatuses, workspaceSections } from "../src/types/workspace.ts";

test("workspaceSections exposes production route order", () => {
  assert.deepEqual(workspaceSections, [
    "command",
    "cases",
    "documents",
    "review",
    "verification",
    "templates",
    "integrations",
    "analytics",
    "admin",
  ]);
});

test("jobStatuses exposes async worker states", () => {
  assert.deepEqual(jobStatuses, ["queued", "processing", "completed", "failed", "retry_scheduled"]);
});
