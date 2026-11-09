// Capture les écrans du guide d'utilisation.
// Prérequis : API sur :8000 et front Vite sur :5173.
// Usage : node scripts/guide/capture.mjs
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, "screens");
const BASE = process.env.GUIDE_BASE_URL ?? "http://localhost:5173/";
const PROMPT = "Explique en quelques phrases les avantages et les limites des modèles de langage pour un service client.";

await mkdir(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.GUIDE_CHROMIUM || undefined });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const shot = (name, target = page, options = {}) =>
  target.screenshot({ path: path.join(out, `${name}.png`), animations: "disabled", ...options });

await page.goto(BASE);
await page.getByText("Moteur disponible").waitFor({ timeout: 30_000 });
await shot("01-accueil");

await page.locator("#prompt").fill(PROMPT);
await page.setViewportSize({ width: 1440, height: 1700 });
await shot("02-formulaire", page.locator(".composer-inner"));
await page.locator("details.advanced summary").click();
await shot("02b-filtre", page.locator("details.advanced"));
await page.locator("details.advanced summary").click();
await page.setViewportSize({ width: 1440, height: 900 });

await page.getByRole("button", { name: "Lancer l'estimation" }).click();
await page.locator(".ranking-section").waitFor({ timeout: 240_000 });
await page.evaluate(() => window.scrollTo(0, 0));
await shot("03-synthese", page.locator(".metric-grid"));
await shot("04-compromis", page.locator(".decision-insight"));

await page.locator(".chart-row").first().click();
await shot("05-classement", page.locator(".ranking-section"));

await shot("06-comparateur", page.locator(".model-comparator"));

await page.getByRole("button", { name: "Enregistrer cette comparaison" }).click();
await page.locator(".header-history").click();
await page.locator(".history-drawer").waitFor();
await shot("07-historique", page.locator(".history-drawer"));
await page.keyboard.press("Escape");

await page.locator(".header-docs").click();
await page.locator(".docs-panel").waitFor();
await page.waitForTimeout(1500);
await shot("08-documentation");

await browser.close();
console.log(`Captures enregistrées dans ${out}`);
