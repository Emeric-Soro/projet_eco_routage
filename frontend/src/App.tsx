import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { BookOpen, Check, ChevronDown, CircleAlert, Clock3, ExternalLink, History, Leaf, LoaderCircle, RotateCcw, Send, X } from "lucide-react";
import ResultWorkspace from "./components/ResultWorkspace";
import HistoryDrawer from "./components/HistoryDrawer";
import DocumentationViewer from "./components/DocumentationViewer";
import {
  addSavedPair, appendRecord, HISTORY_KEY, HISTORY_OPT_IN_KEY, readHistory, removeSavedPair,
} from "./utils/history";
import type { AnalysisRecord, SavedPair } from "./utils/history";
import { estimatePrompt, getHealth } from "./services/estimation";
import type { EnergyModel, EnergySource, EstimateResponse, HealthResponse } from "./types/estimation";

function initialHistoryPreference(): boolean {
  try { return window.localStorage.getItem(HISTORY_OPT_IN_KEY) === "true"; }
  catch { return false; }
}

const methods: { id: EnergyModel; label: string }[] = [
  { id: "power-law", label: "V0.2 · Loi de puissance" },
  { id: "input-output", label: "V0.2 · Régression additive" },
  { id: "output-only", label: "V0.1 · Sortie seule" },
];

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [source, setSource] = useState<EnergySource>("compareai");
  const [method, setMethod] = useState<EnergyModel>("power-law");
  const [minReactions, setMinReactions] = useState(100);
  const [reactionThreshold, setReactionThreshold] = useState(0.65);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [checking, setChecking] = useState(true);
  const [disconnected, setDisconnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EstimateResponse | null>(null);
  const requestController = useRef<AbortController | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyButtonRef = useRef<HTMLButtonElement>(null);
  const [persistHistory, setPersistHistory] = useState(initialHistoryPreference);
  const [history, setHistory] = useState<AnalysisRecord[]>(() =>
    initialHistoryPreference() ? readHistory(window.localStorage) : []
  );
  const [activeId, setActiveId] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [comparisonPreset, setComparisonPreset] = useState<{
    id: string; pair: SavedPair;
  } | null>(null);
  const closeHistory = useCallback(() => {
    setHistoryOpen(false);
    historyButtonRef.current?.focus();
  }, []);
  const [docsOpen, setDocsOpen] = useState(false);
  const docsButtonRef = useRef<HTMLButtonElement>(null);
  const closeDocs = useCallback(() => {
    setDocsOpen(false);
    docsButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!persistHistory) return;
    try { window.localStorage.setItem(HISTORY_KEY, JSON.stringify(history)); }
    catch {
      setHistoryError("Stockage local indisponible ou saturé : les analyses restent dans cet onglet.");
      setPersistHistory(false);
      try { window.localStorage.removeItem(HISTORY_OPT_IN_KEY); } catch { /* stockage bloqué */ }
    }
  }, [history, persistHistory]);

  function changePersistence(enabled: boolean) {
    setHistoryError(null);
    if (!enabled) {
      setPersistHistory(false);
      try {
        window.localStorage.removeItem(HISTORY_KEY);
        window.localStorage.removeItem(HISTORY_OPT_IN_KEY);
      } catch { setHistoryError("Impossible de vider le stockage : effacez les données du site dans votre navigateur."); }
      return;
    }
    try {
      window.localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
      window.localStorage.setItem(HISTORY_OPT_IN_KEY, "true");
      setPersistHistory(true);
    } catch { setHistoryError("Stockage indisponible : aucune sauvegarde persistante activée."); }
  }

  function restoreAnalysis(record: AnalysisRecord, pair?: SavedPair) {
    resetResult();
    setPrompt(record.prompt);
    setSource(record.request.energy_source);
    setMethod(record.request.energy_model);
    setMinReactions(record.request.min_reactions);
    setReactionThreshold(record.request.reaction_threshold);
    setResult(record.result);
    setActiveId(record.id);
    setComparisonPreset(pair ? { id: record.id + ":" + Date.now().toString(), pair } : null);
    closeHistory();
    requestAnimationFrame(() => {
      const destination = document.getElementById(pair ? "comparison-title" : "resultats");
      destination?.focus({ preventScroll: true });
      destination?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  }

  function saveComparison(pair: SavedPair) {
    if (!activeId) return;
    setHistory(prev => addSavedPair(prev, activeId, pair));
  }


  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then(value => {
      setHealth(value); setDisconnected(false);
    }).catch((reason: unknown) => {
      if (!(reason instanceof Error && reason.name === "AbortError")) setDisconnected(true);
    }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => { controller.abort(); requestController.current?.abort(); };
  }, []);

  async function refresh() {
    setChecking(true); setDisconnected(false);
    try { setHealth(await getHealth()); }
    catch { setDisconnected(true); setHealth(null); }
    finally { setChecking(false); }
  }
  function resetResult() {
    requestController.current?.abort();
    requestController.current = null;
    setLoading(false); setError(null); setResult(null);
  }
  function cancel() { requestController.current?.abort(); requestController.current = null; setLoading(false); }

  async function runEstimation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    if (!prompt.trim()) { setError("Saisissez un prompt pour démarrer une estimation."); return; }
    resetResult();
    const controller = new AbortController();
    requestController.current = controller;
    setLoading(true);
    try {
      const response = await estimatePrompt({
        prompt: prompt.trim(), energy_source: source,
        energy_model: source === "mlenergy" ? "output-only" : method,
        min_reactions: minReactions,
        reaction_threshold: reactionThreshold,
        top: 8,
      }, controller.signal);
      if (!controller.signal.aborted) {
        const completed: AnalysisRecord = {
          id: crypto.randomUUID(), createdAt: new Date().toISOString(), prompt: prompt.trim(),
          request: {
            prompt: prompt.trim(), energy_source: source,
            energy_model: source === "mlenergy" ? "output-only" : method,
            min_reactions: minReactions, reaction_threshold: reactionThreshold, top: 8,
          },
          result: response, comparisons: [],
        };
        setHistory(prev => appendRecord(prev, completed));
        setActiveId(completed.id);
        setComparisonPreset(null);
        setResult(response);
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof TypeError
        ? "Impossible de contacter l'API locale. Vérifiez le démarrage du serveur FastAPI."
        : reason instanceof Error ? reason.message : "Une erreur inattendue est survenue.");
    } finally {
      if (!controller.signal.aborted) { setLoading(false); requestController.current = null; }
    }
  }

  const missingCompareAI = health?.compareai_available === false;
  const missingReactions = health?.reactions_available === false;
  const missingMLEnergy = source === "mlenergy" && health?.mlenergy_available === false;
  const blocked = checking || disconnected || missingCompareAI || missingReactions || missingMLEnergy;
  const approxTokens = prompt.length ? Math.max(1, Math.ceil(prompt.length / 4)) : 0;
  const activeRecord = history.find(item => item.id === activeId);

  return <div className="application" id="haut">
    <header className="app-header">
      <a className="logo" href="#haut" aria-label="Éco-routage, retour en haut"><span className="logo-icon"><Leaf size={19} strokeWidth={2.1}/></span><span>éco<span className="logo-divider">/</span>routage</span></a>
      <button ref={historyButtonRef} type="button" className="header-history" onClick={() => setHistoryOpen(true)} aria-haspopup="dialog"><History size={16}/> Historique <span>{history.length}</span></button>
      <button ref={docsButtonRef} type="button" className="header-docs" aria-label="Documentation" aria-haspopup="dialog" onClick={() => setDocsOpen(true)}><BookOpen size={16}/> Documentation</button>
    </header>
    <main className="split-layout">
      <ResultWorkspace result={result} loading={loading} error={error}
        activeId={activeId}
        savedPairs={activeRecord?.comparisons ?? []}
        comparisonPreset={comparisonPreset}
        onSaveComparison={saveComparison} />
      <aside className="composer-column" id="composer" aria-labelledby="composer-title">
        <div className="composer-inner">
          <div className="composer-heading"><span className="composer-kicker">VOTRE ESPACE D'EXPÉRIMENTATION</span><h2 id="composer-title">Posez la question.<br/><em>Mesurez l'impact.</em></h2><p>Décrivez ce que vous demanderiez à une IA. Le moteur comparera l'énergie que différents modèles pourraient mobiliser.</p></div>
          <form className="prompt-form" onSubmit={runEstimation}>
            <div className="form-section-heading"><label htmlFor="prompt">01 <span>LE PROMPT À ANALYSER</span></label><span className="form-hint-light">MAX. 4 000 CARACTÈRES</span></div>
            <div className="prompt-field">
              <textarea id="prompt" name="prompt" value={prompt} maxLength={4000} rows={7} required aria-describedby="prompt-counter" onChange={event => { setPrompt(event.target.value); resetResult(); }} placeholder="Ex. Explique en quelques phrases les avantages et les limites des modèles de langage…" />
              <div className="prompt-counter" id="prompt-counter"><span>{prompt.length} / 4 000 CARACTÈRES</span><span>≈ {approxTokens} TOKENS</span></div>
            </div>
            <div className="form-section-heading source-title"><span>02 <span>LES DONNÉES DE RÉFÉRENCE</span></span></div>
            <div className="source-picker" role="group" aria-label="Source des facteurs énergétiques">
              <button type="button" className={source === "compareai" ? "source-option active" : "source-option"} aria-pressed={source === "compareai"} onClick={() => { setSource("compareai"); resetResult(); }}><span className="source-radio">{source === "compareai" && <Check size={12}/>}</span><span><strong>CompareAI</strong><small>Référence énergétique estimée</small></span></button>
              <button type="button" className={source === "mlenergy" ? "source-option active" : "source-option"} aria-pressed={source === "mlenergy"} onClick={() => { setSource("mlenergy"); resetResult(); }}><span className="source-radio">{source === "mlenergy" && <Check size={12}/>}</span><span><strong>ML.ENERGY</strong><small>Facteurs GPU agrégés</small></span></button>
            </div>
            <div className="form-section-heading"><label htmlFor="method">03 <span>MODÈLE DE CALCUL</span></label></div>
            <div className="select-shell"><select id="method" name="method" value={source === "mlenergy" ? "output-only" : method} disabled={source === "mlenergy"} onChange={event => {setMethod(event.target.value as EnergyModel);resetResult();}}>{methods.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}</select><ChevronDown size={17} aria-hidden="true"/></div>
            {source === "mlenergy" && <p className="form-helper">ML.ENERGY impose le calcul « sortie seule ».</p>}
            <details className="advanced"><summary><span>Affiner le filtre de qualité</span><span>OPTIONNEL <ChevronDown size={16}/></span></summary><div className="advanced-content"><label htmlFor="reactions-min">Réactions historiques minimales</label><input id="reactions-min" type="number" min="1" max="10000" step="1" required value={minReactions} onChange={event=>{setMinReactions(Number(event.target.value));resetResult();}}/><label htmlFor="reaction-threshold">Seuil de score de réactions <strong>{Math.round(reactionThreshold * 100)} %</strong></label><input id="reaction-threshold" type="range" min="0" max="1" step="0.01" value={reactionThreshold} onChange={event=>{setReactionThreshold(Number(event.target.value));resetResult();}} /><p>Le score repose sur les réactions des utilisateurs historiques ; ce n'est pas une garantie de qualité.</p></div></details>
            <div className="api-status" role="status"><span className={checking ? "status-light pending" : blocked ? "status-light offline" : "status-light available"}/><span>{checking ? "Connexion au moteur en cours…" : disconnected ? "API Python inaccessible." : missingCompareAI ? "Jeu de données CompareAI manquant sur le serveur." : missingReactions ? "Fichier de réactions CompareAI manquant." : missingMLEnergy ? "Données ML.ENERGY manquantes." : "Moteur disponible — calcul sur données locales."}</span>{!checking && blocked && <button type="button" onClick={refresh} aria-label="Vérifier à nouveau la disponibilité du moteur"><RotateCcw size={15}/></button>}</div>
            {blocked && !checking && <p className="api-help">{disconnected ? <>Démarrez l'API avec <code>python -m uvicorn api.main:app --reload --port 8000</code>.</> : missingCompareAI ? <>Ajoutez <code>source_données/compareAI/conversations.parquet</code> sur le serveur.</> : missingReactions ? <>Ajoutez <code>source_données/compareAI/reactions.parquet</code> sur le serveur.</> : <>Vérifiez la présence des fichiers Parquet ML.ENERGY.</>}</p>}
            {error && <div className="error-banner" role="alert"><CircleAlert size={17}/><span>{error}</span></div>}
            <div className="action-wrap">{loading ? <button type="button" className="submit-button abort" onClick={cancel}><X size={18}/> Annuler l'attente</button> : <button type="submit" className="submit-button" disabled={blocked || !prompt.trim()}><span>Lancer l'estimation</span><span className="submit-arrow">{blocked ? <Clock3 size={19}/> : <Send size={19}/>}</span></button>}</div>
            {loading && <div className="loading-indicator" role="status"><LoaderCircle size={16} className="rotate" /> Traitement en cours ; le premier calcul peut prendre du temps.</div>}
          </form>
          <div className="composer-notice"><div className="notice-icon"><InfoIcon/></div><p><strong>À savoir.</strong> Aucune réponse n'est générée par l'IA. Le prompt reste dans votre environnement local ; seules des estimations issues des jeux de données sont calculées.</p></div>
          <div className="composer-bottom"><span>ÉCO-ROUTAGE · PROTOTYPE EXPÉRIMENTAL</span><a href="https://github.com/AngeGo11/eco-routage-llm" target="_blank" rel="noopener noreferrer">SOURCE <ExternalLink size={13}/></a></div>
        </div>
      </aside>
    </main>
    <DocumentationViewer open={docsOpen} onClose={closeDocs} />
    <HistoryDrawer open={historyOpen} records={history} activeId={activeId}
      persistEnabled={persistHistory} storageError={historyError}
      onTogglePersistence={changePersistence} onClose={closeHistory}
      onRestore={restoreAnalysis}
      onRemove={id => {
        setHistory(prev => prev.filter(item => item.id !== id));
        if (activeId === id) setActiveId(null);
      }}
      onRemovePair={(id, pair) => setHistory(prev => removeSavedPair(prev, id, pair))}
      onClear={() => { setHistory([]); setActiveId(null); }} />
    <footer className="global-footer">© 2026 ÉCO-ROUTAGE · RECHERCHE SUR LA SOBRIÉTÉ DE L'IA</footer>
  </div>;
}

function InfoIcon() { return <CircleAlert size={19} strokeWidth={1.8}/> }
