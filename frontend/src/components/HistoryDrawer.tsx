import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Clock3, History, LockKeyhole, RotateCcw, Trash2, X } from "lucide-react";
import type { AnalysisRecord, SavedPair } from "../utils/history";

interface Props {
  open: boolean;
  records: AnalysisRecord[];
  activeId: string | null;
  persistEnabled: boolean;
  storageError: string | null;
  onClose: () => void;
  onTogglePersistence: (enabled: boolean) => void;
  onRestore: (record: AnalysisRecord, pair?: SavedPair) => void;
  onRemove: (id: string) => void;
  onRemovePair: (id: string, pair: SavedPair) => void;
  onClear: () => void;
}

function stamp(iso: string) {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.valueOf()) ? "Date inconnue" :
    new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

export default function HistoryDrawer({
  open, records, activeId, persistEnabled, storageError, onClose,
  onTogglePersistence, onRestore, onRemove, onRemovePair, onClear,
}: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!open) return;
    setConfirmClear(false);
    closeRef.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key === "Tab" && dialogRef.current) {
        const elements = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])'
        )).filter(el => el.getClientRects().length > 0);
        if (elements.length === 0) return;
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    }
    document.addEventListener("keydown", keydown);
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", keydown);
      document.body.style.overflow = originalOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;
  return <div className="history-overlay">
    <button className="history-backdrop" type="button" aria-label="Fermer l'historique" onClick={onClose} />
    <aside ref={dialogRef} className="history-drawer" role="dialog" aria-modal="true"
      aria-labelledby="history-heading" aria-describedby="history-description">
      <div className="history-header">
        <span className="history-eyebrow"><History size={15}/> ARCHIVES DU LABORATOIRE</span>
        <button type="button" ref={closeRef} className="history-close" onClick={onClose} aria-label="Fermer l'historique"><X size={20}/></button>
      </div>
      <h2 id="history-heading">Vos analyses,<br/><em>à portée de main.</em></h2>
      <p id="history-description">Retrouvez une estimation précédente ou reprenez une comparaison sans relancer le moteur.</p>
      <div className="history-privacy">
        <div className="privacy-top"><LockKeyhole size={17}/><strong>Confidentialité maîtrisée</strong></div>
        <label className="privacy-toggle">
          <input type="checkbox" checked={persistEnabled}
            onChange={event => onTogglePersistence(event.target.checked)}/>
          <span>Conserver mes analyses sur cet appareil</span>
        </label>
        <p>{persistEnabled
          ? "Stockage dans ce navigateur uniquement (localStorage). Les prompts sont conservés en clair sur cet appareil. Désactiver efface leur copie enregistrée."
          : "Mode privé : les analyses restent en mémoire jusqu'à la fermeture ou au rechargement de cet onglet. Rien n'est enregistré dans le navigateur."}</p>
        {storageError && <p className="privacy-error" role="alert">{storageError}</p>}
      </div>
      <div className="history-list-heading">
        <span>HISTORIQUE <strong>{records.length} / 20</strong></span>
        {records.length > 0 && (!confirmClear ?
          <button type="button" onClick={() => setConfirmClear(true)}>Tout effacer</button> :
          <div className="history-confirm">
            <button type="button" onClick={() => setConfirmClear(false)}>Annuler</button>
            <button type="button" className="confirm-danger" onClick={() => { onClear(); setConfirmClear(false); }}>Confirmer l'effacement</button>
          </div>)}
      </div>
      {records.length === 0 ? <div className="history-empty">
        <Clock3 size={28}/><h3>Aucune analyse pour le moment.</h3>
        <p>Effectuez une première estimation pour alimenter votre historique.</p>
      </div> :
        <ol className="history-list">{records.map(item => <li key={item.id} className={activeId === item.id ? "history-item active" : "history-item"}>
          <div className="history-item-top"><span>{stamp(item.createdAt)}</span><span>{item.result.energy_source === "mlenergy" ? "ML.ENERGY" : "CompareAI"}</span></div>
          <p className="history-prompt">{item.prompt}</p>
          <div className="history-meta"><span>{item.result.recommended_model}</span><span>{item.result.results.length} modèles affichés</span></div>
          <div className="history-actions">
            <button type="button" className="history-reopen" onClick={() => onRestore(item)}><RotateCcw size={14}/> Revoir l'analyse</button>
            <button type="button" className="history-delete" aria-label={"Supprimer l'analyse du " + stamp(item.createdAt)} onClick={() => onRemove(item.id)}><Trash2 size={15}/></button>
          </div>
          {item.comparisons.length > 0 && <div className="history-pairs">
            <span>COMPARAISONS ENREGISTRÉES</span>
            {item.comparisons.map(pair => <div className="history-pair-row" key={pair.left + "|" + pair.right}>
              <button type="button" onClick={() => onRestore(item, pair)}>
                {pair.left} <span>vs</span> {pair.right}<ArrowUpRight size={14}/>
              </button>
              <button type="button" className="history-pair-remove"
                aria-label={`Supprimer la comparaison ${pair.left} contre ${pair.right}`}
                onClick={() => onRemovePair(item.id, pair)}><X size={14}/></button>
            </div>)}
          </div>}
        </li>)}</ol>}
      <div className="history-footer">ÉCO-ROUTAGE · JOURNAL PERSONNEL DES ESTIMATIONS</div>
    </aside>
  </div>;
}
