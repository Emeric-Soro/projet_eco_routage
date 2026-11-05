"""Démo autonome fondée sur les mesures publiques SweetSpot/H100."""

from __future__ import annotations

import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
SWEETSPOT_ZIP = ROOT / "source_données" / "sweetspot_llm_energy" / "dataset.zip"


def fit_nonnegative_power_law(frame: pd.DataFrame) -> tuple[float, float, float]:
    """Fit E = base × (1 + input)^a × (1 + output)^b with a,b >= 0."""
    inputs = frame["Input Length"].to_numpy(dtype=float)
    outputs = frame["Output Length"].to_numpy(dtype=float)
    energy = frame["measured_j_per_request"].to_numpy(dtype=float)
    x = np.column_stack((np.ones(len(frame)), np.log1p(inputs), np.log1p(outputs)))
    y = np.log(energy)
    candidates = []
    for mask in range(1 << 2):
        active = [0] + [idx + 1 for idx in range(2) if mask & (1 << idx)]
        coef = np.linalg.lstsq(x[:, active], y, rcond=None)[0]
        if np.all(coef[1:] >= 0):
            full = np.zeros(3, dtype=float)
            full[active] = coef
            candidates.append(full)
    best = min(candidates, key=lambda value: float(np.square(x @ value - y).sum()))
    return math.exp(float(np.clip(best[0], -700, 700))), float(best[1]), float(best[2])


@st.cache_data(show_spinner=False)
def load_sweetspot_models() -> tuple[pd.DataFrame, dict[str, tuple[float, float, float]]]:
    if not SWEETSPOT_ZIP.exists():
        raise FileNotFoundError(f"Archive SweetSpot absente : {SWEETSPOT_ZIP}")

    tables = []
    with zipfile.ZipFile(SWEETSPOT_ZIP) as archive:
        csv_paths = sorted(
            name for name in archive.namelist()
            if name.endswith(".csv") and name.count("/") == 2 and "traces/" not in name
        )
        for csv_path in csv_paths:
            frame = pd.read_csv(archive.open(csv_path))
            frame["model"] = csv_path.split("/")[1]
            frame["measured_j_per_request"] = (
                frame["Energy (KJ)"] * 1000 / frame["Number of requests"]
            )
            tables.append(frame)

    all_data = pd.concat(tables, ignore_index=True)
    coefficients = {
        model: fit_nonnegative_power_law(frame)
        for model, frame in all_data.groupby("model", sort=True)
    }
    return all_data, coefficients


def main() -> None:
    st.set_page_config(page_title="Démo éco-routage V0.2", page_icon="🌿", layout="wide")
    st.title("Éco-routage : démonstrateur V0.2")
    st.caption("Démo publique autonome — mesures SweetSpot sur NVIDIA H100 avec TensorRT-LLM.")

    st.info(
        "Cette page ne demande que des longueurs en tokens, pas le texte du prompt. "
        "Elle n'appelle aucun modèle et n'envoie aucun prompt à une API. "
        "Le classement décrit les configurations SweetSpot/H100, pas les API cloud."
    )

    try:
        all_data, coefficients = load_sweetspot_models()
    except Exception as exc:
        st.error(f"Impossible de lire les données SweetSpot : {exc}")
        st.stop()

    model_names = sorted(coefficients)
    min_input = int(all_data["Input Length"].min())
    max_input = int(all_data["Input Length"].max())
    min_output = int(all_data["Output Length"].min())
    max_output = int(all_data["Output Length"].max())

    left, right = st.columns(2)
    with left:
        input_tokens = st.number_input(
            "Longueur d'entrée estimée (tokens)",
            min_value=1,
            max_value=100000,
            value=256,
            step=64,
            help="Pour un prompt connu, une approximation simple est nombre de caractères / 4.",
        )
    with right:
        output_tokens = st.number_input(
            "Longueur de réponse visée (tokens)",
            min_value=1,
            max_value=100000,
            value=256,
            step=64,
        )

    outside = (
        input_tokens < min_input or input_tokens > max_input
        or output_tokens < min_output or output_tokens > max_output
    )
    if outside:
        st.warning(
            f"Au moins une longueur est hors de la plage mesurée ({min_input}–{max_input} tokens "
            f"en entrée; {min_output}–{max_output} en sortie). La prédiction extrapole les mesures."
        )

    rows = []
    for model in model_names:
        base, input_exponent, output_exponent = coefficients[model]
        joules = base * (1 + input_tokens) ** input_exponent * (1 + output_tokens) ** output_exponent
        subset = all_data[all_data.model == model]
        rows.append({
            "Modèle": model,
            "Énergie estimée (Wh/requête)": joules / 3600,
            "Exposant entrée": input_exponent,
            "Exposant sortie": output_exponent,
            "Configurations mesurées": int(len(subset)),
        })
    ranking = pd.DataFrame(rows).sort_values("Énergie estimée (Wh/requête)").reset_index(drop=True)
    ranking.insert(0, "Rang", np.arange(1, len(ranking) + 1))

    st.subheader("Classement énergétique estimé")
    st.dataframe(
        ranking,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Énergie estimée (Wh/requête)": st.column_config.NumberColumn(format="%.6f"),
            "Exposant entrée": st.column_config.NumberColumn(format="%.3f"),
            "Exposant sortie": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    st.caption(
        "Le rang 1 est le modèle dont l'énergie prédite est la plus faible pour ces longueurs. "
        "Le calcul ajuste une loi de puissance non négative sur les mesures de chaque modèle."
    )

    st.subheader("Comment lire cette démo")
    st.markdown(
        """
        - Les entrées sont des **longueurs de séquence**. Cette démo ne prédit pas le nombre de tokens de réponse.
        - L'énergie affichée est extrapolée d'un modèle puissance ajusté aux configurations mesurées de SweetSpot.
        - Les modèles ont été testés sur H100/TensorRT-LLM; batch et configuration influencent l'énergie observée.
        - SweetSpot ne fournit pas les votes/réactions de qualité de CompareAI : le classement est énergétique seulement.
        - Les résultats sont indicatifs et ne décrivent pas la consommation d'un fournisseur d'API.
        """
    )
    st.caption(
        "Données : SweetSpot, licence CC BY 4.0. Source et auteurs : "
        "https://doi.org/10.5281/zenodo.18714476 — "
        "https://arxiv.org/abs/2602.05695"
    )


if __name__ == "__main__":
    main()
