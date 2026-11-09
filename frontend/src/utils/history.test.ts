import { describe, expect, it } from "vitest";
import type { AnalysisRecord } from "./history";
import { addSavedPair, appendRecord, HISTORY_KEY, HISTORY_LIMIT, readHistory, removeSavedPair } from "./history";

const model = (name: string) => ({ name, estimated_wh: 0.015, recommended: name === "A",
  output_tokens_est: 12, observations: 50, reaction_quality: .5, reaction_count: 60, factor_source: "test" });
const makeRecord = (id: string): AnalysisRecord => ({
  id, prompt: "Test local", createdAt: "2026-11-05T00:00:00Z",
  request: { prompt: "Test local", energy_source: "compareai", energy_model: "output-only",
    min_reactions: 100, reaction_threshold: .65, top: 8 },
  result: { energy_source: "compareai", energy_model: "output-only", input_tokens: 3,
    models_evaluated: 2, recommended_model: "A", quality_filter_applied: false,
    results: [model("A"), model("B")] }, comparisons: [],
});
describe("historique privé des analyses", () => {
  it("garde au maximum 20 analyses en mémoire", () => {
    let records: AnalysisRecord[] = [];
    for (let i = 0; i < 30; i++) records = appendRecord(records, makeRecord(String(i)));
    expect(records).toHaveLength(HISTORY_LIMIT);
    expect(records[0].id).toBe("29");
    expect(records.at(-1)?.id).toBe("10");
  });
  it("ne duplique pas une comparaison et rejette un modèle absent", () => {
    const input = [makeRecord("x")];
    const stored = addSavedPair(input, "x", { left: "A", right: "B" });
    expect(stored[0].comparisons).toEqual([{ left: "A", right: "B" }]);
    expect(addSavedPair(stored, "x", { left: "A", right: "B" })[0].comparisons).toHaveLength(1);
    expect(addSavedPair(stored, "x", { left: "B", right: "A" })[0].comparisons).toHaveLength(1);
    expect(removeSavedPair(stored, "x", { left: "A", right: "B" })[0].comparisons).toHaveLength(0);
    expect(addSavedPair(stored, "x", { left: "A", right: "inconnu" })).toEqual(stored);
  });
  it("rejette les fichiers invalides et les structures inattendues", () => {
    expect(readHistory({ getItem: () => "{not json" })).toEqual([]);
    expect(readHistory({ getItem: () => JSON.stringify([{ id: "x", prompt: "secret" }]) })).toEqual([]);
    expect(readHistory({ getItem: key => key === HISTORY_KEY ? JSON.stringify([makeRecord("ok")]) : null })[0].id).toBe("ok");
  });
});
