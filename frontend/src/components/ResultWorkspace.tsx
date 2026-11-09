import { useState } from "react";
import { Activity, ArrowUpRight, BarChart3, ChevronDown, Download, Inbox, Info, Leaf, Lightbulb, LoaderCircle } from "lucide-react";
import type { EstimateResponse, ModelResult } from "../types/estimation";
import type { SavedPair } from "../utils/history";
import { DecisionInsights, ModelComparator } from "./DecisionInsights";
import { barRatio } from "../utils/energyInsights";
import EnergyBreakdown from "./EnergyBreakdown";
import { downloadResultsCsv } from "../utils/exportResults";

type Props = {
  result: EstimateResponse | null; loading: boolean; error: string | null;
  activeId: string | null; savedPairs: SavedPair[];
  comparisonPreset: {id: string; pair: SavedPair} | null;
  onSaveComparison: (pair: SavedPair) => void;
};
const wh = (value: number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 6, maximumSignificantDigits: 5 }).format(value);
const percentage = (value: number | null) => value == null ? "n.d." : new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 1 }).format(value);

function Detail({ model, result }: { model: ModelResult; result: EstimateResponse }) {
  return <div className="model-detail">
    <div><span>Référence énergétique</span><strong>{model.factor_source || "Non renseignée"}</strong></div>
    <div><span>Sortie prévue</span><strong>{model.output_tokens_est == null ? "Indisponible" : `≈ ${Math.round(model.output_tokens_est)} tokens`}</strong></div>
    <div><span>Réactions historiques (proxy qualitatif)</span><strong>{percentage(model.reaction_quality)} · {model.reaction_count ?? "n.d."} réactions</strong></div>
    <div><span>Observations énergie</span><strong>{model.observations ?? "Indisponible"}</strong></div>
    {result.energy_model === "output-only" && <div><span>Méthode de calcul</span><strong>Facteur énergétique × sortie estimée</strong></div>}
    {result.energy_model === "input-output" && <EnergyBreakdown model={model} />}
    {result.energy_model === "power-law" && <><div><span>Exposants entrée / sortie</span><strong>{model.input_exponent == null ? "n.d." : model.input_exponent.toFixed(3)} / {model.output_exponent == null ? "n.d." : model.output_exponent.toFixed(3)}</strong></div><div><span>Interprétation du modèle</span><strong>Estimation non additive ; exposants calibrés sur CompareAI</strong></div></>}
    {result.energy_source === "mlenergy" && <div><span>Dispersion P10 à P90 (configurations)</span><strong>{model.config_p10_wh == null ? "n.d." : wh(model.config_p10_wh)} à {model.config_p90_wh == null ? "n.d." : wh(model.config_p90_wh)} Wh</strong></div>}
  </div>;
}

function Chart({ result }: { result: EstimateResponse }) {
  const [open, setOpen] = useState<string | null>(null);
  const [order, setOrder] = useState<"ascending" | "descending" | "name">("ascending");
  const models = [...result.results].sort((a, b) => order === "name"
    ? a.name.localeCompare(b.name, "fr")
    : order === "descending" ? b.estimated_wh - a.estimated_wh : a.estimated_wh - b.estimated_wh);
  const max = Math.max(0, ...models.map(item => item.estimated_wh));
  return <section className="ranking-section" aria-labelledby="ranking-title">
    <div className="section-title"><div><span className="eyebrow dark">02 / COMPARAISON</span><h2 id="ranking-title">Tous les chemins.<br/><em>Une autre perspective.</em></h2></div><button className="csv-export" type="button" onClick={() => downloadResultsCsv(result)} title="Exporter les modèles affichés en CSV"><Download size={15} aria-hidden="true"/> Exporter CSV</button></div>
    <div className="chart-tools">
      <div className="chart-legend"><span><i className="key-dot" /> Modèle recommandé</span><span><i className="key-line" /> Autres modèles</span></div>
      <label className="chart-sort" htmlFor="ranking-order">TRIER PAR <select id="ranking-order" value={order} onChange={e=>setOrder(e.target.value as typeof order)}><option value="ascending">Énergie croissante</option><option value="descending">Énergie décroissante</option><option value="name">Nom A–Z</option></select></label>
    </div>
    <div className="chart-head"><span>MODÈLE</span><span>ÉNERGIE ESTIMÉE</span></div>
    <ol className="chart-list">
      {models.map((item, i) => <li key={item.name} className={item.recommended ? "chart-item selected" : "chart-item"}>
        <button type="button" className="chart-row" onClick={() => setOpen(prev => prev === item.name ? null : item.name)} aria-expanded={open === item.name} aria-label={`Afficher les détails du modèle ${item.name}`}>
          <span className="chart-label"><span className="chart-order">{String(i+1).padStart(2,"0")}</span><span>{item.name}{item.recommended && <small>RECOMMANDÉ</small>}</span></span>
          <span className="chart-value">{wh(item.estimated_wh)} <small>Wh</small><ChevronDown size={14} className={open === item.name ? "chevron rotated" : "chevron"}/></span>
        </button>
        <div className="bar-base" aria-hidden="true"><div className="bar-value" style={{width:`${barRatio(item.estimated_wh, max)}%`}} /></div>
        {open === item.name && <Detail model={item} result={result} />}
      </li>)}
    </ol>
    <div className="chart-footnote"><Info size={16}/><p>Barres proportionnelles au modèle le plus énergivore affiché. <strong>Une barre plus courte signifie une estimation plus basse.</strong> Le classement présente une estimation de l’énergie par requête, pas une mesure GPU directe. Les scores historiques ne garantissent pas la qualité d’une nouvelle réponse.</p></div>
  </section>;
}

function EmptyGraphic() {
  return (
    <div className="empty-viz" role="status">
      <Inbox size={42} strokeWidth={1.6} aria-hidden="true" />
      <p className="empty-viz-text">AUCUNE ANALYSE EN COURS</p>
    </div>
  );
}

export default function ResultWorkspace({ result, loading, error, activeId, savedPairs, comparisonPreset, onSaveComparison }: Props) {
  const recommended = result?.results.find(model => model.name === result.recommended_model);
  return <div className="results-column" id="resultats" tabIndex={-1}>
   <div><div><span className="eyebrow dark">SYNTHÈSE DU CALCUL</span><h2>{loading ? "Analyse en cours…" : result ? "La mesure du possible." : "Votre analyse commence ici."}</h2></div><span className={result ? "result-state ready" : "result-state"}><Activity size={13}/>{result ? "ESTIMATION TERMINÉE" : loading ? "CALCUL EN COURS" : "AUCUNE ANALYSE"}</span></div>
    <div className="metric-grid">
      <div className="metric-block"><span>MODÈLE CONSEILLÉ <ArrowUpRight size={13}/></span><strong className="metric-model">{result?.recommended_model ?? "—"}</strong><small>{result ? (result.quality_filter_applied ? "Filtré par réactions" : "Classement énergétique") : "Après calcul"}</small></div>
      <div className="metric-block"><span>ÉNERGIE ESTIMÉE <Leaf size={13}/></span><strong>{recommended ? wh(recommended.estimated_wh) : "—"}<small>{recommended ? " Wh" : ""}</small></strong><small>Pour la requête · pas une mesure GPU</small></div>
      <div className="metric-block"><span>MODÈLES ÉVALUÉS <BarChart3 size={13}/></span><strong>{result ? result.models_evaluated : "—"}</strong><small>Disponibles dans le jeu de données</small></div>
    </div>
    {result && !loading && <DecisionInsights result={result} />}
    {loading ? <div className="loading-analysis" role="status"><LoaderCircle className="rotate" size={30}/><h3>Le moteur explore les modèles…</h3><p>Lecture des données historiques et calcul des estimations. Le premier lancement peut être plus long.</p></div> : result ? <Chart result={result} /> : <section className="blank-results">
      <EmptyGraphic/>
      <div className="empty-copy"><div className="round-icon"><Lightbulb size={20}/></div><div><h3>À chaque prompt, sa trajectoire.</h3><p>Saisissez votre demande à droite pour afficher ici les estimations énergétiques, les modèles comparés et le détail des calculs. Aucun chiffre fictif n'est présenté.</p>{error && <p className="empty-error">Le calcul n'a pas abouti. Consultez le message dans le panneau de droite.</p>}</div></div>
    </section>}
    {result && !loading && <ModelComparator key={comparisonPreset?.id ?? activeId ?? "no-record"}
      result={result} initialPair={comparisonPreset?.pair}
      savedPairs={savedPairs} onSaveComparison={onSaveComparison} canSave={Boolean(activeId)} />}
  </div>;
}
