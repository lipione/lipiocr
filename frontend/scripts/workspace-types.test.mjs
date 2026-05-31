import assert from "node:assert/strict";
import test from "node:test";

import {
  addressCandidateSources,
  documentAssetTypes,
  documentSectionSides,
  jobStatuses,
  workspaceSections,
} from "../src/types/workspace.ts";

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

test("documentAssetTypes exposes Nepal KYC evidence asset categories", () => {
  assert.deepEqual(documentAssetTypes, ["photo", "fingerprint", "signature", "stamp", "seal", "chip"]);
});

test("documentSectionSides exposes identity document side states", () => {
  assert.deepEqual(documentSectionSides, ["front", "back", "unknown"]);
});

test("addressCandidateSources exposes auditable address evidence sources", () => {
  assert.deepEqual(addressCandidateSources, [
    "nepal_location_registry",
    "address_evidence_store",
    "fuzzy_alias_match",
    "reviewer_approved",
  ]);
});
