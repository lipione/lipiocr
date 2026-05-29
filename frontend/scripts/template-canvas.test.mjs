import assert from "node:assert/strict";
import test from "node:test";

import { computeTemplateDragBbox } from "../src/lib/template-canvas.ts";

const page = { width: 1000, height: 700 };
const canvasRect = { width: 500, height: 350 };

test("moves template boxes in page coordinates and keeps them inside the page", () => {
  const bbox = computeTemplateDragBbox({
    mode: "move",
    startBbox: [900, 620, 980, 680],
    startClientX: 100,
    startClientY: 100,
    clientX: 150,
    clientY: 160,
    page,
    canvasRect,
  });

  assert.deepEqual(bbox, [920, 640, 1000, 700]);
});

test("resizes template boxes with a minimum field size", () => {
  const bbox = computeTemplateDragBbox({
    mode: "resize-nw",
    startBbox: [100, 100, 180, 150],
    startClientX: 100,
    startClientY: 100,
    clientX: 180,
    clientY: 150,
    page,
    canvasRect,
  });

  assert.deepEqual(bbox, [140, 126, 180, 150]);
});

test("resizes southeast handle without moving northwest anchor", () => {
  const bbox = computeTemplateDragBbox({
    mode: "resize-se",
    startBbox: [100, 100, 180, 150],
    startClientX: 100,
    startClientY: 100,
    clientX: 200,
    clientY: 170,
    page,
    canvasRect,
  });

  assert.deepEqual(bbox, [100, 100, 380, 290]);
});
