import type { EstimateRequest, EstimateResponse } from "../types/estimation";

export const HISTORY_KEY = "eco-routage:analyses:v1";
export const HISTORY_OPT_IN_KEY = "eco-routage:history-enabled:v1";
export const HISTORY_LIMIT = 20;
export const PAIRS_LIMIT = 5;

export interface SavedPair { left: string; right: string }
export interface AnalysisRecord {
  id: string;
  createdAt: string;
  prompt: string;
  request: EstimateRequest;
  result: EstimateResponse;
  comparisons: SavedPair[];
}
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function isRecord(value: unknown): value is AnalysisRecord {
  if (!isObject(value) || !isObject(value.request) || !isObject(value.result)) return false;
  const r = value.result;
  return typeof value.id === "string" && value.id.length < 100
    && typeof value.createdAt === "string"
    && typeof value.prompt === "string" && value.prompt.length <= 4000
    && typeof value.request.prompt === "string"
    && value.request.prompt === value.prompt
    && (value.request.energy_source === "compareai" || value.request.energy_source === "mlenergy")
    && (value.request.energy_model === "power-law"
      || value.request.energy_model === "input-output"
      || value.request.energy_model === "output-only")
    && typeof value.request.min_reactions === "number"
    && Number.isInteger(value.request.min_reactions)
    && value.request.min_reactions >= 1 && value.request.min_reactions <= 10000
    && typeof value.request.reaction_threshold === "number"
    && value.request.reaction_threshold >= 0 && value.request.reaction_threshold <= 1
    && typeof value.request.top === "number" && value.request.top >= 1
    && (r.energy_source === "compareai" || r.energy_source === "mlenergy")
    && (r.energy_model === "power-law" || r.energy_model === "input-output" || r.energy_model === "output-only")
    && typeof r.input_tokens === "number" && Number.isFinite(r.input_tokens)
    && typeof r.models_evaluated === "number" && Number.isFinite(r.models_evaluated)
    && typeof r.quality_filter_applied === "boolean"
    && Array.isArray(r.results) && r.results.length <= 30
    && typeof r.recommended_model === "string"
    && r.results.every(model => isObject(model)
      && typeof model.name === "string"
      && typeof model.estimated_wh === "number"
      && Number.isFinite(model.estimated_wh))
    && Array.isArray(value.comparisons)
    && value.comparisons.length <= PAIRS_LIMIT
    && value.comparisons.every(pair => isObject(pair)
      && typeof pair.left === "string" && typeof pair.right === "string");
}

export function readHistory(storage: Pick<Storage, "getItem">): AnalysisRecord[] {
  try {
    const raw = storage.getItem(HISTORY_KEY);
    if (!raw || raw.length > 1_000_000) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRecord).slice(0, HISTORY_LIMIT);
  } catch { return []; }
}

export function appendRecord(records: AnalysisRecord[], next: AnalysisRecord): AnalysisRecord[] {
  return [next, ...records.filter(item => item.id !== next.id)].slice(0, HISTORY_LIMIT);
}

export function addSavedPair(records: AnalysisRecord[], id: string, pair: SavedPair): AnalysisRecord[] {
  if (!pair.left || !pair.right || pair.left === pair.right) return records;
  return records.map(item => {
    if (item.id !== id || !item.result.results.some(m => m.name === pair.left)
      || !item.result.results.some(m => m.name === pair.right)) return item;
    if (item.comparisons.some(old => (old.left === pair.left && old.right === pair.right)
      || (old.left === pair.right && old.right === pair.left))) return item;
    return { ...item, comparisons: [pair, ...item.comparisons].slice(0, PAIRS_LIMIT) };
  });
}

export function removeSavedPair(records: AnalysisRecord[], id: string, pair: SavedPair): AnalysisRecord[] {
  return records.map(item => item.id === id
    ? { ...item, comparisons: item.comparisons.filter(old =>
      !(old.left === pair.left && old.right === pair.right)) }
    : item);
}
