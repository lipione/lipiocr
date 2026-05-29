export type TemplateDragMode = "move" | "resize-nw" | "resize-ne" | "resize-sw" | "resize-se";

type PageSize = {
  width: number;
  height: number;
};

type CanvasSize = {
  width: number;
  height: number;
};

export type TemplateDragInput = {
  mode: TemplateDragMode;
  startBbox: number[];
  startClientX: number;
  startClientY: number;
  clientX: number;
  clientY: number;
  page: PageSize;
  canvasRect: CanvasSize;
};

const MIN_FIELD_WIDTH = 40;
const MIN_FIELD_HEIGHT = 24;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function normalizePage(page: PageSize) {
  return {
    width: Math.max(1, page.width),
    height: Math.max(1, page.height),
  };
}

export function clampTemplateBbox(bbox: number[], page: PageSize) {
  const normalizedPage = normalizePage(page);
  let [x1, y1, x2, y2] = bbox.map((value) => (Number.isFinite(value) ? value : 0));
  const minWidth = Math.min(MIN_FIELD_WIDTH, normalizedPage.width);
  const minHeight = Math.min(MIN_FIELD_HEIGHT, normalizedPage.height);

  x1 = clamp(x1, 0, normalizedPage.width);
  y1 = clamp(y1, 0, normalizedPage.height);
  x2 = clamp(x2, 0, normalizedPage.width);
  y2 = clamp(y2, 0, normalizedPage.height);

  if (x2 - x1 < minWidth) {
    if (x1 + minWidth <= normalizedPage.width) {
      x2 = x1 + minWidth;
    } else {
      x1 = Math.max(0, x2 - minWidth);
    }
  }

  if (y2 - y1 < minHeight) {
    if (y1 + minHeight <= normalizedPage.height) {
      y2 = y1 + minHeight;
    } else {
      y1 = Math.max(0, y2 - minHeight);
    }
  }

  return [Math.round(x1), Math.round(y1), Math.round(x2), Math.round(y2)];
}

function translateBboxWithinPage(bbox: number[], page: PageSize) {
  const normalizedPage = normalizePage(page);
  const [x1, y1, x2, y2] = bbox;
  const width = Math.max(MIN_FIELD_WIDTH, x2 - x1);
  const height = Math.max(MIN_FIELD_HEIGHT, y2 - y1);
  const nextX1 = clamp(x1, 0, Math.max(0, normalizedPage.width - width));
  const nextY1 = clamp(y1, 0, Math.max(0, normalizedPage.height - height));

  return [
    Math.round(nextX1),
    Math.round(nextY1),
    Math.round(Math.min(normalizedPage.width, nextX1 + width)),
    Math.round(Math.min(normalizedPage.height, nextY1 + height)),
  ];
}

function clampResizeBbox(bbox: number[], page: PageSize, mode: Exclude<TemplateDragMode, "move">) {
  const normalizedPage = normalizePage(page);
  const minWidth = Math.min(MIN_FIELD_WIDTH, normalizedPage.width);
  const minHeight = Math.min(MIN_FIELD_HEIGHT, normalizedPage.height);
  let [x1, y1, x2, y2] = bbox.map((value) => (Number.isFinite(value) ? value : 0));

  x1 = clamp(x1, 0, normalizedPage.width);
  y1 = clamp(y1, 0, normalizedPage.height);
  x2 = clamp(x2, 0, normalizedPage.width);
  y2 = clamp(y2, 0, normalizedPage.height);

  if (x2 - x1 < minWidth) {
    if (mode === "resize-nw" || mode === "resize-sw") {
      x1 = Math.max(0, x2 - minWidth);
      x2 = x1 + minWidth;
    } else {
      x2 = Math.min(normalizedPage.width, x1 + minWidth);
      x1 = x2 - minWidth;
    }
  }

  if (y2 - y1 < minHeight) {
    if (mode === "resize-nw" || mode === "resize-ne") {
      y1 = Math.max(0, y2 - minHeight);
      y2 = y1 + minHeight;
    } else {
      y2 = Math.min(normalizedPage.height, y1 + minHeight);
      y1 = y2 - minHeight;
    }
  }

  return [Math.round(x1), Math.round(y1), Math.round(x2), Math.round(y2)];
}

export function computeTemplateDragBbox(input: TemplateDragInput) {
  const page = normalizePage(input.page);
  const canvasWidth = Math.max(1, input.canvasRect.width);
  const canvasHeight = Math.max(1, input.canvasRect.height);
  const dx = ((input.clientX - input.startClientX) / canvasWidth) * page.width;
  const dy = ((input.clientY - input.startClientY) / canvasHeight) * page.height;
  const [x1, y1, x2, y2] = input.startBbox;

  if (input.mode === "move") {
    return translateBboxWithinPage([x1 + dx, y1 + dy, x2 + dx, y2 + dy], page);
  }

  const nextBbox =
    input.mode === "resize-nw"
      ? [x1 + dx, y1 + dy, x2, y2]
      : input.mode === "resize-ne"
        ? [x1, y1 + dy, x2 + dx, y2]
        : input.mode === "resize-sw"
          ? [x1 + dx, y1, x2, y2 + dy]
          : [x1, y1, x2 + dx, y2 + dy];

  return clampResizeBbox(nextBbox, page, input.mode);
}
