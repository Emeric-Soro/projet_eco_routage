import { expect, test } from "@playwright/test";

const sample = {
  energy_source:"compareai", energy_model:"input-output", input_tokens:12, models_evaluated:3,
  recommended_model:"Modèle B", quality_filter_applied:true,
  results: [
    {name:"Modèle A",estimated_wh:.02,output_tokens_est:200,observations:100,factor_source:"CompareAI observé",reaction_quality:.55,reaction_count:150,recommended:false,base_energy_wh:.002,input_energy_wh:.003,output_energy_wh:.015},
    {name:"Modèle B",estimated_wh:.04,output_tokens_est:210,observations:100,factor_source:"CompareAI observé",reaction_quality:.82,reaction_count:190,recommended:true,base_energy_wh:.002,input_energy_wh:.004,output_energy_wh:.034},
  ],
};

test.beforeEach(async ({page}) => {
  await page.route("**/api/health", route => route.fulfill({
    status:200, contentType:"application/json",
    body:JSON.stringify({status:"ready",compareai_available:true,reactions_available:true,mlenergy_available:true}),
  }));
  await page.route("**/api/estimate", route => route.fulfill({
    status:200, contentType:"application/json", body:JSON.stringify(sample),
  }));
  await page.goto("/");
  await expect(page.getByText("Moteur disponible — calcul sur données locales.")).toBeVisible();
  await expect(page.getByRole("button",{name:/lancer l'estimation/i})).toBeDisabled();
});

test("disposition adaptée à l'écran sans débordement", async ({page}) => {
  const mobile=test.info().project.name.includes("mobile");
  const left=await page.locator(".results-column").boundingBox();
  const right=await page.locator(".composer-column").boundingBox();
  expect(left && right).toBeTruthy();
  if(mobile) expect(right!.y+right!.height).toBeLessThanOrEqual(left!.y+2);
  else expect(left!.x+left!.width).toBeLessThanOrEqual(right!.x+2);
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(2);
  await page.screenshot({path:`test-results/layout-${test.info().project.name}.png`,fullPage:true});
});

test("résultats, ventilation et export CSV accessibles", async ({page}) => {
  await page.getByRole("textbox",{name:/prompt à analyser/i}).fill("Résume la sobriété numérique");
  await page.getByLabel("MODÈLE DE CALCUL").selectOption("input-output");
  await page.getByRole("button",{name:/lancer l'estimation/i}).click();
  await expect(page.getByText(/\+0,02 Wh estimés par rapport au minimum/)).toBeVisible();
  await page.getByRole("button",{name:"Afficher les détails du modèle Modèle A"}).click();
  await expect(page.getByText("VENTILATION DU CALCUL ADDITIF")).toBeVisible();
  const download=page.waitForEvent("download");
  await page.getByRole("button",{name:"Exporter CSV"}).click();
  expect((await download).suggestedFilename()).toMatch(/^eco-routage-resultats-/);
  await page.screenshot({path:`test-results/resultats-${test.info().project.name}.png`,fullPage:true});
});

test("les données manquantes bloquent le calcul", async ({page}) => {
  await page.route("**/api/health", route => route.fulfill({
    status:200,contentType:"application/json",
    body:JSON.stringify({status:"missing_data",compareai_available:false,reactions_available:false,mlenergy_available:false}),
  }));
  await page.reload();
  await expect(page.getByText("Jeu de données CompareAI manquant sur le serveur.")).toBeVisible();
  await expect(page.getByRole("button",{name:/lancer l'estimation/i})).toBeDisabled();
});

test("historique de session : rouvrir sans relancer le moteur", async ({page}) => {
  let requests = 0;
  await page.route("**/api/estimate", route => {
    requests++;
    return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(sample)});
  });
  await page.getByRole("textbox",{name:/prompt à analyser/i}).fill("Mon premier prompt");
  await page.getByRole("button",{name:/lancer l'estimation/i}).click();
  await expect(page.getByText("+0,02 Wh estimés par rapport au minimum")).toBeVisible();
  expect(requests).toBe(1);
  await page.getByRole("textbox",{name:/prompt à analyser/i}).fill("Une autre question");
  await page.getByRole("button",{name:/Historique/i}).click();
  const dialog=page.getByRole("dialog",{name:/Vos analyses/i});
  await expect(dialog.getByText("Mon premier prompt")).toBeVisible();
  await dialog.getByRole("button",{name:/Revoir l'analyse/i}).click();
  await expect(page.getByRole("textbox",{name:/prompt à analyser/i})).toHaveValue("Mon premier prompt");
  await expect(page.getByText("+0,02 Wh estimés par rapport au minimum")).toBeVisible();
  expect(requests).toBe(1);
});

test("sauvegarder et restaurer une comparaison", async ({page}) => {
  await page.getByRole("textbox",{name:/prompt à analyser/i}).fill("Comparer mes modèles");
  await page.getByRole("button",{name:/lancer l'estimation/i}).click();
  await page.getByRole("button",{name:"Enregistrer cette comparaison"}).click();
  await expect(page.getByRole("button",{name:"Comparaison enregistrée"})).toBeDisabled();
  await page.getByRole("button",{name:/Historique/i}).click();
  const dialog=page.getByRole("dialog",{name:/Vos analyses/i});
  await dialog.getByRole("button",{name:/Modèle A.*vs.*Modèle B/i}).click();
  await expect(page.getByRole("combobox",{name:"MODÈLE A"})).toHaveValue("Modèle A");
  await expect(page.getByRole("combobox",{name:"MODÈLE B"})).toHaveValue("Modèle B");
  await page.getByRole("button",{name:/Historique/i}).click();
  const opened = page.getByRole("dialog",{name:/Vos analyses/i});
  await opened.getByRole("button",{name:/Supprimer la comparaison Modèle A contre Modèle B/i}).click();
  await expect(opened.getByRole("button",{name:/Supprimer la comparaison/i})).toHaveCount(0);
});

test("la persistance ne fonctionne qu'après consentement et se désactive sans laisser de copie", async ({page}) => {
  await page.getByRole("textbox",{name:/prompt à analyser/i}).fill("Mon prompt local");
  await page.getByRole("button",{name:/lancer l'estimation/i}).click();
  await page.getByRole("button",{name:/Historique/i}).click();
  const dialog=page.getByRole("dialog",{name:/Vos analyses/i});
  const toggle=dialog.getByRole("checkbox",{name:/Conserver mes analyses sur cet appareil/i});
  await expect(toggle).not.toBeChecked();
  expect(await page.evaluate(()=>localStorage.getItem("eco-routage:analyses:v1"))).toBeNull();
  await toggle.check();
  await expect(toggle).toBeChecked();
  expect(await page.evaluate(()=>localStorage.getItem("eco-routage:analyses:v1"))).toContain("Mon prompt local");
  await page.reload();
  await page.getByRole("button",{name:/Historique/i}).click();
  await expect(page.getByRole("dialog").getByText("Mon prompt local")).toBeVisible();
  await page.getByRole("checkbox",{name:/Conserver mes analyses sur cet appareil/i}).uncheck();
  expect(await page.evaluate(()=>localStorage.getItem("eco-routage:analyses:v1"))).toBeNull();
  await page.reload();
  await page.getByRole("button",{name:/Historique/i}).click();
  await expect(page.getByText("Aucune analyse pour le moment.")).toBeVisible();
});

test("fermeture de l'historique au clavier et retour du focus", async ({page}) => {
  const trigger=page.getByRole("button",{name:/Historique/i});
  await trigger.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
