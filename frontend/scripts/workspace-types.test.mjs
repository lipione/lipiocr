import assert from "node:assert/strict";
import test from "node:test";

import { workspaceSections } from "../src/types/workspace.ts";

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
