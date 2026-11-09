import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, BookmarkPlus, CheckCircle2, GitCompareArrows, Info } from "lucide-react";
import type { EstimateResponse, ModelResult } from "../types/estimation";
import type { SavedPair } from "../utils/history";
import {
  comparisonInsight, eligibleResults, recommendationInsight,
} from "../utils/energyInsights";

export const formatWh = (value: number) =>
  new Intl.NumberFormat("fr-FR", { maximumSignificantDigits: 5 }).format(value);

const formatPercent = (value: number) =>
  new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(value);

function LabeledMetric({ label, model, index }: { label: string; model: ModelResult; index: string }) {
  return (
    <div className="decision-metric">
      <span className="decision-metric-caption">{index} / {label}</span>
      <strong title={model.name}>{model.name}</strong>
      <span className="decision-energy">{formatWh(model.estimated_wh)} <small>Wh estimés</small></span>
    </div>
  );
}

export function DecisionInsights({ result }: { result: EstimateResponse }) {
  const insight = recommendationInsight(result);
  if (!insight) return (
    <section className="decision-insight" aria-label="Synthèse de la recommandation indisponible">
      <p>Les données ne permettent pas d'identifier le modèle recommandé. Vérifiez la réponse du moteur.</p>
    </section>
  );

  const { cheapest, chosen, differs, extraWh, extraPercent } = insight;
  const tiesOnEnergy = differs && extraWh === 0;
  return (
    <section className="decision-insight" aria-labelledby="decision-title">
      <div className="decision-header">
        <span className="eyebrow dark">LE COMPROMIS À CONNAÎTRE</span>
        <h3 id="decision-title">{tiesOnEnergy ? "Deux modèles ex æquo en énergie estimée." : differs ? "Le minimum énergétique et le modèle recommandé peuvent différer." : "Un choix qui minimise aussi l’énergie estimée."}</h3>
      </div>
      <div className="decision-metrics">
        <LabeledMetric label="MINIMUM ÉNERGÉTIQUE" model={cheapest} index="A" />
        <LabeledMetric label="RECOMMANDATION" model={chosen} index="B" />
      </div>
      <div className={differs ? "decision-summary differs" : "decision-summary"}>
        {differs ? <ArrowUpRight size={19} aria-hidden="true" /> : <CheckCircle2 size={19} aria-hidden="true" />}
        <div>
          <strong>{differs
            ? (tiesOnEnergy ? "Même énergie estimée que le minimum" : `+${formatWh(extraWh)} Wh estimés par rapport au minimum`)
            : "Le modèle recommandé est également le moins énergivore de la sélection"}
          </strong>
          <p>{differs
            ? `${tiesOnEnergy ? "Aucun surcoût énergétique estimé entre ces deux modèles." : extraPercent === null ? "Écart relatif non calculable (minimum nul)." : `Écart relatif de +${formatPercent(extraPercent)} %.`} ${result.quality_filter_applied ? "Le filtre de réactions historiques influe sur le choix." : "Les critères de classement peuvent différer."} Cette comparaison ne prédit pas la qualité d'une nouvelle réponse.`
            : "Aucun surcoût estimé par rapport au minimum affiché. Les réactions historiques ne constituent pas une garantie de qualité."}
          </p>
        </div>
      </div>
      <p className="decision-limit"><Info size={13} /> Comparaison limitée aux modèles renvoyés pour une même source énergétique et un même prompt.</p>
    </section>
  );
}

interface ComparatorProps {
  result: EstimateResponse;
  initialPair?: SavedPair;
  savedPairs: SavedPair[];
  onSaveComparison: (pair: SavedPair) => void;
  canSave: boolean;
}

export function ModelComparator({ result, initialPair, savedPairs, onSaveComparison, canSave }: ComparatorProps) {
  const options = eligibleResults(result);
  const insight = recommendationInsight(result);
  const firstDefault = insight?.cheapest.name ?? options[0]?.name ?? "";
  const secondDefault = insight && insight.differs
    ? insight.chosen.name
    : (options.find(model => model.name !== firstDefault)?.name ?? firstDefault);

  const [left, setLeft] = useState(
    initialPair && options.some(m => m.name === initialPair.left) ? initialPair.left : firstDefault
  );
  const [right, setRight] = useState(
    initialPair && options.some(m => m.name === initialPair.right) ? initialPair.right : secondDefault
  );
  const a = options.find(item => item.name === left);
  const b = options.find(item => item.name === right);

  if (options.length < 2) return null;
  const diff = a && b ? comparisonInsight(a, b) : null;
  const same = a?.name === b?.name;
  const alreadySaved = savedPairs.some(pair =>
    (pair.left === left && pair.right === right) || (pair.left === right && pair.right === left)
  );

  return (
    <section className="model-comparator" aria-labelledby="comparison-title">
      <div className="comparator-heading">
        <div><span className="eyebrow dark">03 / FACE À FACE</span><h2 id="comparison-title" tabIndex={-1}>Comparer deux modèles,<br/><em>à conditions égales.</em></h2></div>
        <GitCompareArrows size={22} aria-hidden="true" />
      </div>
      <div className="comparator-grid">
        <div className="comparator-side">
          <label htmlFor="compare-left">MODÈLE A</label>
          <select id="compare-left" value={left} onChange={e => setLeft(e.target.value)}>
            {options.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}
          </select>
          <strong>{a ? formatWh(a.estimated_wh) : "—"} <small>Wh</small></strong>
          <span>Énergie estimée pour la requête</span>
        </div>
        <div className="comparator-side">
          <label htmlFor="compare-right">MODÈLE B</label>
          <select id="compare-right" value={right} onChange={e => setRight(e.target.value)}>
            {options.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}
          </select>
          <strong>{b ? formatWh(b.estimated_wh) : "—"} <small>Wh</small></strong>
          <span>Énergie estimée pour la requête</span>
        </div>
      </div>
      <div className="comparator-conclusion" aria-live="polite">
        {!diff || same ? <><CheckCircle2 size={17}/><p>Sélectionnez deux modèles différents pour comparer leurs estimations.</p></> :
          diff.differenceWh > 0 ? <><ArrowUpRight size={18}/><p><strong>Le modèle B est estimé plus énergivore de {formatWh(diff.differenceWh)} Wh</strong>{diff.differencePercent === null ? " (pourcentage non calculable)." : ` (+${formatPercent(diff.differencePercent)} % par rapport au modèle A).`}</p></> :
          diff.differenceWh < 0 ? <><ArrowDownRight size={18}/><p><strong>Le modèle B est estimé moins énergivore de {formatWh(Math.abs(diff.differenceWh))} Wh</strong>{diff.differencePercent === null ? " (pourcentage non calculable)." : ` (${formatPercent(diff.differencePercent)} % par rapport au modèle A).`}</p></> :
          <><CheckCircle2 size={17}/><p>Même énergie estimée pour les deux modèles dans la précision du calcul.</p></>}
      </div>
      <div className="comparison-save-area">
        <button type="button" className="comparison-save" onClick={() => onSaveComparison({ left, right })}
          disabled={!canSave || !a || !b || same || alreadySaved}>
          {alreadySaved ? <CheckCircle2 size={17}/> : <BookmarkPlus size={17}/>}
          {alreadySaved ? "Comparaison enregistrée" : "Enregistrer cette comparaison"}
        </button>
        <p>Retrouvez vos comparaisons dans « Historique ». Stockage sur cet appareil uniquement si vous l'activez.</p>
      </div>
      <p className="comparator-note">Les valeurs sont calculées à partir de la même requête, de la même source et de la même méthode. Les différences ne sont pas des économies réelles mesurées.</p>
    </section>
  );
}
