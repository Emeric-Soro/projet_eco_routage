import { describe, expect, it } from "vitest";
import type { EstimateResponse, ModelResult } from "../types/estimation";
import {
  barRatio, comparisonInsight, lowestEnergyModel,
  recommendationInsight, relativeDifference,
} from "./energyInsights";

const makeModel = (name: string, wh: number): ModelResult => ({
  name,
  estimated_wh: wh,
  recommended: false,
  factor_source: "CompareAI observé",
  output_tokens_est: 120,
  observations: 100,
  reaction_quality: null,
  reaction_count: null,
});

const sample: EstimateResponse = {
  energy_source: "compareai",
  energy_model: "power-law",
  input_tokens: 22,
  models_evaluated: 3,
  recommended_model: "Modèle B",
  quality_filter_applied: true,
  results: [makeModel("Modèle B", 0.06), makeModel("Modèle A", 0.04), makeModel("Modèle C", 0.08)],
};

describe("synthèse énergétique", () => {
  it("identifie le minimum sans supposer un ordre des réponses", () => {
    expect(lowestEnergyModel(sample)?.name).toBe("Modèle A");
  });

  it("sépare le moins énergivore du recommandé", () => {
    const insight = recommendationInsight(sample);
    expect(insight?.chosen.name).toBe("Modèle B");
    expect(insight?.cheapest.name).toBe("Modèle A");
    expect(insight?.differs).toBe(true);
    expect(insight?.extraWh).toBeCloseTo(0.02);
    expect(insight?.extraPercent).toBeCloseTo(50);
  });

  it("ne crée pas de surcoût quand le choix recommandé est aussi le minimum", () => {
    const insight = recommendationInsight({ ...sample, recommended_model: "Modèle A" });
    expect(insight?.extraWh).toBe(0);
    expect(insight?.extraPercent).toBe(0);
    expect(insight?.differs).toBe(false);
  });

  it("n'invente pas de recommandation manquante", () => {
    expect(recommendationInsight({ ...sample, recommended_model: "Inconnu" })).toBeNull();
    expect(recommendationInsight({ ...sample, results: [] })).toBeNull();
  });

  it("protège les pourcentages contre les divisions par zéro", () => {
    expect(relativeDifference(0, 1)).toBeNull();
    expect(relativeDifference(1, 0)).toBe(-100);
    expect(relativeDifference(-1, 1)).toBeNull();
    expect(relativeDifference(1, Number.NaN)).toBeNull();
  });

  it("calcule les différences signées entre deux modèles", () => {
    expect(comparisonInsight(makeModel("A", .06), makeModel("B", .03)).differencePercent).toBeCloseTo(-50);
    expect(comparisonInsight(makeModel("A", .06), makeModel("B", .03)).differenceWh).toBeCloseTo(-.03);
  });

  it("borne correctement la longueur des barres", () => {
    expect(barRatio(2, 4)).toBe(50);
    expect(barRatio(10, 4)).toBe(100);
    expect(barRatio(0, 0)).toBe(0);
    expect(barRatio(-2, 10)).toBe(0);
  });

  it("ignore les valeurs énergétiques invalides", () => {
    const invalid = { ...sample, results: [makeModel("Invalid", Number.NaN), makeModel("A", 0.4)] };
    expect(lowestEnergyModel(invalid)?.name).toBe("A");
  });
});
