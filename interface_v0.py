"""Petite interface graphique locale pour le démonstrateur d'éco-routage V0."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
import os
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
ESTIMATOR = ROOT / "estimateur_v0.py"

BG = "#f3f6fb"
INK = "#182235"
MUTED = "#596579"
ACCENT = "#146b55"


class EstimateurApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Éco-routage : démonstrateur V0")
        self.geometry("980x760")
        self.minsize(760, 600)
        self.configure(bg=BG)

        self.source = tk.StringVar(value="compareai")
        self.status = tk.StringVar(value="Prêt")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._build_ui()
        self.after(120, self._check_events)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground=INK)
        style.configure("Sub.TLabel", foreground=MUTED, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(14, 9))
        style.configure("Accent.TButton", background=ACCENT, foreground="white")
        style.map("Accent.TButton", background=[("active", "#0d513f"), ("disabled", "#9ab4ac")])

        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Éco-routage : V0", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Estime la consommation d’un prompt et compare les modèles disponibles dans les données.",
            style="Sub.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(3, 18))

        prompt_box = ttk.LabelFrame(outer, text=" 1 · Prompt à estimer ", padding=14)
        prompt_box.pack(fill="x", pady=(0, 12))
        self.prompt = tk.Text(
            prompt_box, height=4, wrap="word", font=("Segoe UI", 11),
            relief="solid", borderwidth=1, padx=9, pady=8,
        )
        self.prompt.pack(fill="x")
        self.prompt.insert("1.0", "Résume les enjeux de la sobriété numérique en trois points.")

        controls = ttk.LabelFrame(outer, text=" 2 · Source des facteurs énergétiques ", padding=14)
        controls.pack(fill="x", pady=(0, 12))
        radio_line = ttk.Frame(controls)
        radio_line.pack(fill="x")
        ttk.Radiobutton(radio_line, text="CompareAI (référence V0)", variable=self.source,
                        value="compareai").pack(side="left", padx=(0, 18))
        ttk.Radiobutton(radio_line, text="ML.ENERGY (11 modèles reliés)", variable=self.source,
                        value="mlenergy").pack(side="left")
        ttk.Label(
            controls,
            text="CompareAI fournit une référence estimée. ML.ENERGY utilise des mesures GPU, résumées sur plusieurs configurations.",
            style="Sub.TLabel", wraplength=880,
        ).pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(0, 12))
        self.estimate_button = ttk.Button(buttons, text="Estimer ce prompt", style="Accent.TButton",
                                          command=self._estimate)
        self.estimate_button.pack(side="left")
        self.eval_button = ttk.Button(buttons, text="Évaluer la V0 sur le jeu de test",
                                      command=self._evaluate)
        self.eval_button.pack(side="left", padx=(10, 0))
        ttk.Label(buttons, textvariable=self.status, style="Sub.TLabel").pack(side="right", padx=8)

        result_frame = ttk.LabelFrame(outer, text=" Résultats ", padding=10)
        result_frame.pack(fill="both", expand=True)
        self.output = tk.Text(
            result_frame, wrap="word", font=("Consolas", 10), bg="white", fg=INK,
            relief="solid", borderwidth=1, padx=12, pady=10, state="disabled",
        )
        scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        self.output.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._show_output(
            "Saisis un prompt puis clique sur « Estimer ce prompt ».\n\n"
            "Le bouton d’évaluation calcule les métriques sur le split de test figé; "
            "cette opération peut prendre un peu plus de temps."
        )

        ttk.Label(
            outer,
            text="Prototype de recherche : les résultats sont des estimations et ne prouvent pas une économie réelle.",
            style="Sub.TLabel", wraplength=900,
        ).pack(anchor="w", pady=(12, 0))

    def _set_busy(self, busy: bool, label: str) -> None:
        state = "disabled" if busy else "normal"
        self.estimate_button.configure(state=state)
        self.eval_button.configure(state=state)
        self.status.set(label)

    def _start(self, args: list[str], status: str) -> None:
        self._set_busy(True, status)
        self._show_output("Calcul en cours…\nLes données sont lues depuis le dossier source_données.")

        def run() -> None:
            try:
                child_env = os.environ.copy()
                # La console Windows peut choisir une page de code locale (ex. cp1252).
                # Force UTF-8 dans le processus enfant pour que les accents restent lisibles.
                child_env["PYTHONIOENCODING"] = "utf-8"
                child_env["PYTHONUTF8"] = "1"
                completed = subprocess.run(
                    [sys.executable, str(ESTIMATOR), *args],
                    cwd=ROOT,
                    env=child_env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                result = completed.stdout.strip()
                if completed.stderr.strip():
                    result += "\n\nMessages techniques :\n" + completed.stderr.strip()
                if completed.returncode:
                    result = f"La commande a échoué (code {completed.returncode}).\n\n{result}"
                    self.events.put(("error", result))
                else:
                    self.events.put(("done", result or "Aucun résultat retourné."))
            except Exception as exc:  # Affiche les erreurs de lancement dans l'interface.
                self.events.put(("error", f"Impossible de lancer l’estimateur : {exc}"))

        threading.Thread(target=run, daemon=True).start()

    def _estimate(self) -> None:
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo("Prompt manquant", "Saisis un prompt à estimer.")
            return
        self._start(["--prompt", prompt, "--energy-source", self.source.get(), "--top", "5"],
                    "Estimation en cours…")

    def _evaluate(self) -> None:
        self._start(["--eval"], "Évaluation en cours…")

    def _show_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def _check_events(self) -> None:
        try:
            while True:
                kind, text = self.events.get_nowait()
                self._show_output(text)
                self._set_busy(False, "Terminé" if kind == "done" else "Erreur")
        except queue.Empty:
            pass
        self.after(120, self._check_events)


if __name__ == "__main__":
    if not ESTIMATOR.exists():
        raise SystemExit(f"Estimateur introuvable : {ESTIMATOR}")
    EstimateurApp().mainloop()
