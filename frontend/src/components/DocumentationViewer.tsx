import { useEffect, useRef, useState } from "react";
import { BookOpen, Download, ExternalLink, X } from "lucide-react";

const documents = [
  { id: "guide", label: "Guide d'utilisation", title: "Prise en main", file: "Guide_utilisation_ecoroutage.pdf" },
  { id: "technique", label: "Documentation technique", title: "Éco-routage V0.2", file: "Documentation_V0.2_ecoroutage.pdf" },
] as const;

type DocId = typeof documents[number]["id"];

const docUrl = (file: string) => `${import.meta.env.BASE_URL}docs/${file}`;

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function DocumentationViewer({ open, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const [active, setActive] = useState<DocId>("guide");
  const current = documents.find(doc => doc.id === active) ?? documents[0];
  const url = docUrl(current.file);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
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
  return <div className="docs-overlay">
    <button className="history-backdrop" type="button" aria-label="Fermer la documentation" onClick={onClose} />
    <section className="docs-panel" role="dialog" aria-modal="true" aria-labelledby="docs-heading">
      <header className="docs-header">
        <div>
          <span className="history-eyebrow"><BookOpen size={15}/> DOCUMENTATION</span>
          <h2 id="docs-heading">{current.title}</h2>
        </div>
        <div className="docs-actions">
          <a href={url} target="_blank" rel="noopener noreferrer"><ExternalLink size={15}/> Ouvrir</a>
          <a href={url} download><Download size={15}/> Télécharger</a>
          <button type="button" ref={closeRef} className="history-close" onClick={onClose} aria-label="Fermer la documentation"><X size={20}/></button>
        </div>
      </header>
      <div className="docs-tabs" role="tablist" aria-label="Documents disponibles">
        {documents.map(doc => (
          <button key={doc.id} type="button" role="tab" aria-selected={doc.id === active}
            className={doc.id === active ? "active" : undefined} onClick={() => setActive(doc.id)}>
            {doc.label}
          </button>
        ))}
      </div>
      <iframe key={current.id} className="docs-frame" src={url} title={`${current.label} — Éco-routage`} />
    </section>
  </div>;
}
