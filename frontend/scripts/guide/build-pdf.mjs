// Génère le PDF du guide d'utilisation à partir de guide.html.
// Usage : node scripts/guide/build-pdf.mjs (après capture.mjs)
import { chromium } from "@playwright/test";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(here, "../../public/docs/Guide_utilisation_ecoroutage.pdf");

const browser = await chromium.launch({ executablePath: process.env.GUIDE_CHROMIUM || undefined });
const page = await browser.newPage();
await page.goto(pathToFileURL(path.join(here, "guide.html")).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.pdf({
  path: output,
  format: "A4",
  printBackground: true,
  preferCSSPageSize: true,
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate: `<div style="width:100%;font:8px 'Helvetica',sans-serif;color:#7c937f;padding:0 17mm;display:flex;justify-content:space-between">
    <span>ÉCO-ROUTAGE · GUIDE D'UTILISATION V0.2</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
});
await browser.close();
console.log(`Guide généré : ${output}`);
