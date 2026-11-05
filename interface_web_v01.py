"""Interface web locale Streamlit pour le prototype d'éco-routage."""

from __future__ import annotations

import subprocess
import sys
import os
import re
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
        if "--eval" in arguments:
            display_evaluation_explanation(stdout)
            with st.expander("Afficher les résultats détaillés"):
                st.text(stdout)
        else:
            st.text(stdout)
    if stderr:
        with st.expander("Messages techniques"):
            st.code(stderr)


def _evaluation_sections(stdout: str) -> list[dict[str, object]]:
    """Extrait les métriques des sections d'évaluation imprimées par la CLI."""
    headers = (
        "BASELINE CompareAI —",
        "V0.2 CompareAI —",
        "HYBRIDE ML.ENERGY —",
    )
    raw_sections: list[tuple[str, list[str]]] = []
    current_header: str | None = None
    current_lines: list[str] = []

    def save_current() -> None:
        if current_header is not None:
            raw_sections.append((current_header, current_lines.copy()))

    for line in stdout.splitlines():
        if line.startswith(headers):
            save_current()
            current_header = line.strip()
            current_lines = []
        elif current_header is not None:
            if not line.strip():
                save_current()
                current_header = None
                current_lines = []
            else:
                current_lines.append(line)
    save_current()

    parsed: list[dict[str, object]] = []
    for header, lines in raw_sections:
        body = "\n".join(lines)

        def number(pattern: str) -> float | None:
            match = re.search(pattern, body, flags=re.IGNORECASE | re.MULTILINE)
            return float(match.group(1)) if match else None

        parsed.append({
            "header": header,
            "mae": number(r"^\s*MAE(?: énergie)?\s*:\s*(-?[\d.]+)\s*Wh"),
            "relative_error": number(r"^\s*Erreur relative méd\.\s*:\s*([\d.]+)\s*%"),
            "route_accuracy": number(r"^\s*Accuracy routage\s*:\s*([\d.]+)\s*%"),
            "input_share": number(r"^\s*Part médiane énergie d'entrée\s*:\s*([\d.]+)\s*%"),
            "input_exponent": number(r"^\s*Exposant médian d'entrée positif\s*:\s*([\d.]+)"),
        })
    return parsed


def display_evaluation_explanation(stdout: str) -> None:
    """Présente une lecture simple des métriques après l'évaluation."""
    sections = _evaluation_sections(stdout)
    st.markdown("### Comment lire ces résultats")
    st.write(
        "Le test compare les estimations à la référence énergétique historique de CompareAI. "
        "Il mesure la reproduction de cette référence, pas la consommation réelle d'un GPU."
    )

    baseline = next(
        (section for section in sections
         if str(section["header"]).startswith("BASELINE CompareAI — V0.1 modèle × longueur")),
        None,
    )
    variants = [
        section for section in sections
        if str(section["header"]).startswith("V0.2 CompareAI —")
    ]

    if baseline is not None and variants:
        baseline_header = str(baseline["header"])
        st.caption(f"Référence de comparaison : {baseline_header.split(' — ', 1)[1].split(' (', 1)[0]}.")
        for variant in variants:
            variant_header = str(variant["header"])
            name = variant_header.split(" — ", 1)[1].split(" (", 1)[0]
            comparisons: list[tuple[str, bool | None]] = []
            for key, label, lower_is_better, unit, delta_unit in (
                ("mae", "MAE", True, "Wh", "Wh"),
                ("relative_error", "erreur relative médiane", True, "%", "point(s) de pourcentage"),
                ("route_accuracy", "exactitude de routage", False, "%", "point(s) de pourcentage"),
            ):
                old_value = baseline.get(key)
                new_value = variant.get(key)
                if not isinstance(old_value, (int, float)) or not isinstance(new_value, (int, float)):
                    continue
                delta = float(new_value) - float(old_value)
                if abs(delta) < 0.0001:
                    comparisons.append((f"{label} inchangée ({old_value:.2f} {unit})", None))
                else:
                    improved = delta < 0 if lower_is_better else delta > 0
                    direction = "diminue" if delta < 0 else "augmente"
                    comparisons.append((
                        f"{label} {direction} de {abs(delta):.2f} {delta_unit} "
                        f"({old_value:.2f} → {new_value:.2f} {unit})",
                        improved,
                    ))

            if comparisons:
                outcomes = [outcome for _, outcome in comparisons if outcome is not None]
                if not outcomes:
                    conclusion = "Les indicateurs sont identiques à ceux de V0.1 sur ce test."
                elif all(outcomes):
                    conclusion = (
                        "Les trois indicateurs vont dans le sens d'une meilleure reproduction de la référence."
                        if len(outcomes) == 3 else
                        "Les indicateurs qui évoluent vont dans le sens d'une meilleure reproduction de la référence."
                    )
                elif not any(outcomes):
                    conclusion = "Aucun de ces indicateurs ne s'améliore par rapport à V0.1 sur ce test."
                else:
                    conclusion = "Le bilan est partagé : certaines mesures s'améliorent, d'autres se dégradent."
                st.markdown(f"**{name}** : " + "; ".join(text for text, _ in comparisons) + ". " + conclusion)

            if name.startswith("régression énergie") and variant.get("input_share") == 0:
                st.caption(
                    "La part d'énergie d'entrée estimée est nulle dans cette calibration CompareAI. "
                    "Cela ne signifie pas que les tokens d'entrée ne consomment aucune énergie en réalité."
                )
            if name.startswith("loi de puissance") and variant.get("input_exponent") == 0:
                st.caption(
                    "L'exposant d'entrée positif vaut zéro ici : le test CompareAI ne montre pas "
                    "de contribution d'entrée détectée par cette régression."
                )

    st.markdown(
        """
        - **MAE (Wh)** : écart absolu moyen entre estimation et référence; plus bas est préférable.
        - **Erreur relative médiane** : écart typique en pourcentage; plus bas est préférable.
        - **Exactitude de routage** : part des paires où le modèle classé moins énergivore est aussi le moins énergivore dans la référence; plus haut est préférable. Ce n'est pas une mesure de qualité de réponse.
        - **MAE de sortie (tokens)** : erreur moyenne sur la longueur de réponse prédite.
        - **Couverture du filtre** : part des cas où au moins un modèle satisfait le seuil de qualité choisi. Les votes et réactions sont des préférences historiques, pas une garantie de qualité.
        - **Accord avec le vote** : fréquence à laquelle le modèle retenu correspond au choix historique des utilisateurs. Le score qualité et le taux « égale/dépasse » résument, eux, les réactions observées.
        - Dans l'écart énergétique du filtre de votes, une valeur positive signifie que le modèle retenu est moins énergivore que le choix historique; dans l'écart « routée − autre réponse » du filtre par réactions, une valeur négative signifie que le modèle retenu est moins énergivore.
        """
    )


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
