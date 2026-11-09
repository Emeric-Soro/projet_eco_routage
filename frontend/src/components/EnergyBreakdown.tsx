import type { ModelResult } from "../types/estimation";
import { formatWh } from "./DecisionInsights";

type Part = { label: string; value: number; className: string };

export default function EnergyBreakdown({ model }: { model: ModelResult }) {
  const base = model.base_energy_wh;
  const input = model.input_energy_wh;
  const output = model.output_energy_wh;
  if ([base, input, output].some(value => value == null || !Number.isFinite(value) || value < 0)) {
    return <p className="breakdown-unavailable">Ventilation additive indisponible pour ce modèle.</p>;
  }
  const parts: Part[] = [
    { label: "Base par requête", value: base!, className: "breakdown-base" },
    { label: "Tokens d'entrée", value: input!, className: "breakdown-input" },
    { label: "Tokens de sortie", value: output!, className: "breakdown-output" },
  ];
  const sum = parts.reduce((total, part) => total + part.value, 0);
  return <div className="energy-breakdown" aria-label="Décomposition de l'énergie estimée par le modèle additif">
    <span className="breakdown-title">VENTILATION DU CALCUL ADDITIF</span>
    <div className="breakdown-bar" role="img" aria-label={parts.map(p => `${p.label} : ${formatWh(p.value)} Wh`).join(", ")}>
      {parts.map(p => <span key={p.label} className={p.className} style={{ width: sum > 0 ? `${p.value / sum * 100}%` : "0%" }} />)}
    </div>
    <div className="breakdown-legend">{parts.map(p => <span key={p.label}><i className={p.className} /> {p.label}<strong>{formatWh(p.value)} Wh</strong></span>)}</div>
    <p className="breakdown-footnote">Ventilation propre au modèle additif V0.2, et non une mesure des composants matériels.</p>
  </div>;
}
