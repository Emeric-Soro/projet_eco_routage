import type { EstimateResponse, ModelResult } from "../types/estimation";

/** Préfixe les formules qui pourraient s'exécuter dans un tableur. */
function csvText(value: string): string {
  const safe = /^\s*[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${safe.replace(/"/g, '""')}"`;
}

function numberCell(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "" : String(value);
}

function rowCells(model: ModelResult, result: EstimateResponse): string[] {
  return [
    csvText(model.name),
    numberCell(model.estimated_wh),
    numberCell(model.output_tokens_est),
    numberCell(model.observations),
    csvText(model.factor_source ?? ""),
    numberCell(model.reaction_quality),
    numberCell(model.reaction_count),
    model.recommended ? "oui" : "non",
    csvText(result.energy_source),
    csvText(result.energy_model),
    numberCell(result.input_tokens),
    String(result.models_evaluated),
    csvText(result.recommended_model),
    result.quality_filter_applied ? "oui" : "non",
    numberCell(model.base_energy_wh),
    numberCell(model.input_energy_wh),
    numberCell(model.output_energy_wh),
    numberCell(model.input_exponent),
    numberCell(model.output_exponent),
    numberCell(model.config_p10_wh),
    numberCell(model.config_p90_wh),
  ];
}

export function resultsToCsv(result: EstimateResponse): string {
  const header = [
    "modele", "energie_estimee_Wh", "tokens_sortie_estimes", "observations_energie",
    "source_facteur", "score_reactions", "nombre_reactions",
    "recommande", "source_energetique", "methode_energetique", "tokens_entree_approximes",
    "modeles_evalues", "modele_recommande", "filtre_qualite_applique",
    "base_requete_Wh", "entree_estimee_Wh", "sortie_estimee_Wh",
    "exposant_entree", "exposant_sortie", "config_p10_Wh", "config_p90_Wh",
  ];
  return "\uFEFF" + [header.join(";"), ...result.results.map(model => rowCells(model, result).join(";"))].join("\r\n") + "\r\n";
}

export function downloadResultsCsv(result: EstimateResponse) {
  const file = new Blob([resultsToCsv(result)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = `eco-routage-resultats-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
