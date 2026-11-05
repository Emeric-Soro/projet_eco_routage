"""Interface web locale Streamlit pour le prototype d'éco-routage."""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
ESTIMATOR = ROOT / "estimateur_v0.py"


@st.cache_data(ttl=900, max_entries=16, show_spinner=False)
def run_estimator(arguments: tuple[str, ...], estimator_mtime: int) -> tuple[int, str, str]:
    """Exécute la CLI existante et mémorise brièvement son résultat."""
    del estimator_mtime  # Sert de clé de cache pour invalider après une modification du moteur.
    child_env = os.environ.copy()
    # Force l'UTF-8 dans le processus Python enfant, notamment sous Windows.
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, str(ESTIMATOR), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def display_result(arguments: tuple[str, ...], label: str) -> None:
    if not ESTIMATOR.exists():
        st.error(f"Estimateur introuvable : {ESTIMATOR}")
        return

    try:
        estimator_mtime = ESTIMATOR.stat().st_mtime_ns
        with st.spinner(label):
            return_code, stdout, stderr = run_estimator(arguments, estimator_mtime)
    except OSError as exc:
        st.error(f"Impossible de lancer l'estimateur : {exc}")
        return

    if return_code:
        st.error(f"La commande de l'estimateur a échoué (code {return_code}).")
    if stdout:
        st.text(stdout)
    if stderr:
        with st.expander("Messages techniques"):
            st.code(stderr)


st.set_page_config(
    page_title="Éco-routage des prompts — V0.2",
    page_icon="🌿",
    layout="wide",
)

st.title("Éco-routage des prompts : V0.2 expérimentale")
st.caption(
    "Prototype de recherche local : compare des estimations énergétiques et des retours historiques de qualité."
)

with st.sidebar:
    st.header("Paramètres")
    energy_source = st.radio(
        "Facteurs énergétiques",
        options=("compareai", "mlenergy"),
        format_func=lambda value: "CompareAI (référence estimée)"
        if value == "compareai"
        else "ML.ENERGY (11 modèles reliés)",
        help="ML.ENERGY utilise des mesures GPU agrégées sur plusieurs configurations.",
    )
    energy_model = st.radio(
        "Modèle énergétique",
        options=("power-law", "input-output", "output-only"),
        format_func=lambda value: {
            "power-law": "V0.2 : loi de puissance entrée + sortie",
            "input-output": "V0.2 : régression additive entrée + sortie",
            "output-only": "V0.1 : sortie seule",
        }[value],
        help="V0.2 modélise séparément l'effet des longueurs d'entrée et de sortie sur les facteurs CompareAI.",
    )
    if energy_source == "mlenergy" and energy_model != "output-only":
        st.caption("ML.ENERGY ne fournit ici qu'un facteur de sortie; le classement utilisera donc la sortie seule.")
    min_reactions = st.number_input(
        "Réactions minimales par modèle",
        min_value=1,
        max_value=10000,
        value=100,
        step=10,
    )
    reaction_threshold = st.slider(
        "Seuil du score de réactions",
        min_value=0.0,
        max_value=1.0,
        value=0.65,
        step=0.01,
    )
    st.divider()
    st.caption("Les données restent dans le dossier local du projet.")

estimate_tab, evaluation_tab, method_tab = st.tabs(
    ("Estimer un prompt", "Évaluer V0 / V0.1 / V0.2", "Méthode et limites")
)

with estimate_tab:
    st.subheader("Estimation pour une requête")
    with st.form("prompt_form"):
        prompt = st.text_area(
            "Prompt",
            value="Résume les enjeux de la sobriété numérique en trois points.",
            height=150,
            placeholder="Saisissez le prompt à estimer…",
        )
        estimate_clicked = st.form_submit_button(
            "Estimer et classer les modèles", type="primary", use_container_width=True
        )

    if estimate_clicked:
        if not prompt.strip():
            st.warning("Saisissez un prompt avant de lancer l'estimation.")
        else:
            display_result(
                (
                    "--prompt",
                    prompt.strip(),
                    "--energy-source",
                    energy_source,
                    "--energy-model",
                    energy_model,
                    "--top",
                    "5",
                    "--min-reactions",
                    str(int(min_reactions)),
                    "--reaction-threshold",
                    str(reaction_threshold),
                ),
                "Lecture des données et calcul du classement…",
            )

with evaluation_tab:
    st.subheader("Évaluation V0 / V0.1 / V0.2 sur le split de test fixe")
    st.write(
        "L'évaluation compare les estimations à la référence CompareAI et affiche aussi "
        "les résultats des filtres de qualité. Le split de paires est déterministe."
    )
    st.info(
        f"Source utilisée pour les classements de qualité : {energy_source}. "
        "Les résultats de MAE affichent les variantes CompareAI et ML.ENERGY disponibles."
    )
    if st.button("Lancer l'évaluation", type="primary"):
        display_result(("--eval", "--energy-source", energy_source,
                        "--energy-model", energy_model,
                        "--min-reactions", str(int(min_reactions)),
                        "--reaction-threshold", str(reaction_threshold)),
                       "Évaluation en cours sur les données locales…")

with method_tab:
    st.subheader("Comment lire les résultats")
    st.markdown(
        """
        - **CompareAI** fournit une référence énergétique estimée, pas une mesure directe de consommation GPU.
        - **ML.ENERGY** fournit des mesures GPU. Les configurations diffèrent et seulement 11 modèles sont reliés.
        - La longueur du prompt est approximée par `caractères / 4`.
        - La variante V0.1 estime la longueur de sortie par modèle et tranche d'entrée quand il y a assez d'exemples de calibration.
        - La V0.2 propose une loi de puissance et une régression additive qui modélisent séparément les longueurs d'entrée et de sortie; la V0.1 reste disponible comme référence.
        - Sur le test CompareAI, la loi de puissance est à comparer à la baseline avant d'en tirer une conclusion; les coefficients restent des estimations, pas des mesures physiques.
        - ML.ENERGY fournit ici un facteur de sortie mesuré; la composante d'entrée V0.2 n'est pas mélangée à cette source.
        - Les votes et réactions sont des retours historiques. Ils ne garantissent pas la qualité d'une réponse future.
        - Les économies affichées sont des comparaisons avec les références disponibles, pas des économies physiques garanties.
        """
    )

st.divider()
st.caption(
    "Les calculs sont exécutés par estimateur_v0.py. Le premier calcul peut prendre du temps; "
    "les résultats identiques sont mis en cache pendant 15 minutes."
)
