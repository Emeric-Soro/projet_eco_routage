import type { EstimateResponse, ModelResult } from "../types/estimation";

/** Toutes les comparaisons sont internes à une estimation et à une seule source. */
export function eligibleResults(result: EstimateResponse): ModelResult[] {
  return result.results.filter(
    model => Number.isFinite(model.estimated_wh) && model.estimated_wh >= 0,
  );
}

export function lowestEnergyModel(result: EstimateResponse): ModelResult | null {
  const models = eligibleResults(result);
  return models.reduce<ModelResult | null>(
    (best, current) => !best || current.estimated_wh < best.estimated_wh ? current : best,
    null,
  );
}

export function recommendedModel(result: EstimateResponse): ModelResult | null {
  return eligibleResults(result).find(model => model.name === result.recommended_model) ?? null;
}

/** Renvoie null si la base est zéro ou si un nombre est absent / invalide. */
export function relativeDifference(reference: number, compared: number): number | null {
  if (!Number.isFinite(reference) || !Number.isFinite(compared) || reference <= 0 || compared < 0) {
    return null;
  }
  return (compared - reference) / reference * 100;
}

export interface RecommendationInsight {
  cheapest: ModelResult;
  chosen: ModelResult;
  extraWh: number;
  extraPercent: number | null;
  differs: boolean;
}

export function recommendationInsight(result: EstimateResponse): RecommendationInsight | null {
  const cheapest = lowestEnergyModel(result);
  const chosen = recommendedModel(result);
  if (!cheapest || !chosen) return null;
  return {
    cheapest,
    chosen,
    extraWh: Math.max(0, chosen.estimated_wh - cheapest.estimated_wh),
    extraPercent: relativeDifference(cheapest.estimated_wh, chosen.estimated_wh),
    differs: chosen.name !== cheapest.name,
  };
}

/** Ratio de comparaison de deux scénarios estimés sous les mêmes hypothèses. */
export function comparisonInsight(a: ModelResult, b: ModelResult) {
  return {
    differenceWh: b.estimated_wh - a.estimated_wh,
    differencePercent: relativeDifference(a.estimated_wh, b.estimated_wh),
  };
}

export function barRatio(energy: number, maxEnergy: number): number {
  if (!Number.isFinite(energy) || energy < 0 || !Number.isFinite(maxEnergy) || maxEnergy <= 0) {
    return 0;
  }
  return Math.min(100, energy / maxEnergy * 100);
}
