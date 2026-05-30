import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const sourceFiles = ["src/app/page.tsx", "src/components/product-home.tsx"]
  .map((file) => join(root, file))
  .filter((file) => existsSync(file));
const source = sourceFiles.map((file) => readFileSync(file, "utf8")).join("\n");

const requiredText = [
  "ProductHome",
  "Nepal financial institutions",
  "Document intelligence for KYC, onboarding, and operations",
  "Human review workflow",
  "Bilingual extraction",
  "Integration-ready exports",
  "LipiCore does OCR + bilingual normalization + entity reconciliation + reviewer-safe correction",
  "Bilingual field pairing",
  "Confidence repair with audit reasons",
  "Cross-document entity reconciliation",
  "/product-documents-workbench.png",
];

const missing = requiredText.filter((text) => !source.includes(text));
if (!existsSync(join(root, "public/product-documents-workbench.png"))) {
  missing.push("public/product-documents-workbench.png");
}

if (missing.length) {
  throw new Error(`Home page contract missing: ${missing.join(", ")}`);
}

console.log("Home page contract verified");
