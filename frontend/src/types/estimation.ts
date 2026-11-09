export type EnergySource = "compareai" | "mlenergy";
export type EnergyModel = "power-law" | "input-output" | "output-only";

export interface EstimateRequest {
  prompt: string;
  energy_source: EnergySource;
  energy_model: EnergyModel;
  min_reactions: number;
  reaction_threshold: number;
  top: number;
}

export interface ModelResult {
  name: string;
  estimated_wh: number;
  output_tokens_est: number | null;
  observations: number | null;
  factor_source: string | null;
  reaction_quality: number | null;
  reaction_count: number | null;
  recommended: boolean;
  config_p10_wh?: number | null;
  config_p90_wh?: number | null;
  input_exponent?: number | null;
  output_exponent?: number | null;
  base_energy_wh?: number | null;
  input_energy_wh?: number | null;
  output_energy_wh?: number | null;
}

export interface EstimateResponse {
  energy_source: EnergySource;
  energy_model: EnergyModel;
  input_tokens: number;
  models_evaluated: number;
  recommended_model: string;
  quality_filter_applied: boolean;
  results: ModelResult[];
}

export interface HealthResponse {
  status: "ready" | "missing_data";
  compareai_available: boolean;
  reactions_available: boolean;
  mlenergy_available: boolean;
}
