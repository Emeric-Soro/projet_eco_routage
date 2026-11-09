import { describe, expect, it } from "vitest";
import type { EstimateResponse } from "../types/estimation";
import { resultsToCsv } from "./exportResults";

const result: EstimateResponse = {
  energy_source: "compareai",
  energy_model: "input-output",
  input_tokens: 14,
  models_evaluated: 14,
  recommended_model: "Bon modèle",
  quality_filter_applied: true,
  results: [{
    name: "Bon modèle", estimated_wh: 0.0001234, output_tokens_est: 234,
    observations: 100, factor_source: "CompareAI observé", reaction_quality: .7,
    reaction_count: 102, recommended: true, base_energy_wh: 0,
    input_energy_wh: .000012, output_energy_wh: .0001114,
  }],
};

describe("export CSV scientifique", () => {
  it("produit un CSV français UTF-8 avec les valeurs numériques et les métadonnées", () => {
    const csv = resultsToCsv(result);
    expect(csv.charCodeAt(0)).toBe(65279);
    expect(csv).toContain("modele;energie_estimee_Wh;tokens_sortie_estimes");
    expect(csv).toContain('"Bon modèle";0.0001234;234;100;"CompareAI observé";0.7;102;oui;"compareai";"input-output";14;14;"Bon modèle";oui;0;0.000012;0.0001114');
    expect(csv).toContain("\r\n");
  });

  it("échappe les guillemets et bloque les formules tableur injectées dans les noms", () => {
    const csv = resultsToCsv({
      ...result,
      results: [{...result.results[0], name: '  =SUM(1,1)" \u00e9chec', factor_source: "@cmd"}],
    });
    expect(csv).toContain('"\'  =SUM(1,1)"" échec"');
    expect(csv).toContain('"\'@cmd"');
  });

  it("laisse vides les indicateurs absents sans inventer des zéros", () => {
    const csv = resultsToCsv({
      ...result,
      results: [{...result.results[0], reaction_quality: null, base_energy_wh: undefined}],
    });
    expect(csv).toContain(';"CompareAI observé";;102;oui;');
    expect(csv).toContain(';"Bon modèle";oui;;0.000012;');
  });

  it("exporte un en-tête même si aucun modèle n'est présent", () => {
    expect(resultsToCsv({...result, results: []}).split("\r\n").length).toBe(2);
  });
});
