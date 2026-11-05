"""Validation externe du facteur énergétique sur le jeu SweetSpot/H100."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from estimateur_v0 import fit, load_model_metadata, load_rows


ROOT = Path(__file__).resolve().parent
SWEETSPOT_ZIP = ROOT / "source_données" / "sweetspot_llm_energy" / "dataset.zip"
SWEETSPOT_TABLE = "dataset/Llama-3.1-8B-Instruct/Llama-3.1-8B-Instruct.csv"
COMPAREAI_MODEL = "llama-3.1-8b"


def main() -> None:
    if not SWEETSPOT_ZIP.exists():
        raise SystemExit(f"Archive SweetSpot introuvable : {SWEETSPOT_ZIP}")

    with zipfile.ZipFile(SWEETSPOT_ZIP) as archive:
        measured = pd.read_csv(archive.open(SWEETSPOT_TABLE))

    rows = load_rows()
    metadata = load_model_metadata()
    _, factors, _, _, _, _, _ = fit(rows, metadata, 100, 100)
    if COMPAREAI_MODEL not in factors.index:
        raise SystemExit(f"Facteur CompareAI introuvable pour {COMPAREAI_MODEL}")

    compareai_kwh_per_output_token = float(
        factors.loc[COMPAREAI_MODEL, "kwh_per_output_token"]
    )
    compareai_j_per_output_token = compareai_kwh_per_output_token * 3_600_000

    measured["measured_j_per_request"] = (
        measured["Energy (KJ)"] * 1000 / measured["Number of requests"]
    )
    measured["measured_wh_per_request"] = measured["measured_j_per_request"] / 3600
    measured["measured_j_per_output_token"] = measured["Energy Per Token (J)"]
    measured["predicted_j_per_output_token"] = compareai_j_per_output_token
    measured["predicted_j_per_request"] = (
        compareai_j_per_output_token * measured["Output Length"]
    )
    measured["predicted_wh_per_request"] = measured["predicted_j_per_request"] / 3600

    ratio = measured.predicted_j_per_request / measured.measured_j_per_request
    relative_error = (ratio - 1).abs() * 100
    measured_rank = measured.measured_j_per_request.rank(method="average")
    predicted_rank = measured.predicted_j_per_request.rank(method="average")
    rank_correlation = measured_rank.corr(predicted_rank)

    print("VALIDATION EXTERNE SWEETSPOT — Llama 3.1 8B Instruct, GPU H100")
    print(f"Configurations mesurées : {len(measured)}")
    print(f"Facteur CompareAI calibré : {compareai_j_per_output_token:.4f} J/token de sortie")
    print(f"Énergie SweetSpot médiane : {measured.measured_j_per_output_token.median():.4f} J/token de sortie")
    print(f"Énergie mesurée médiane : {measured.measured_wh_per_request.median():.6f} Wh/requête")
    print(f"Énergie prédite médiane : {measured.predicted_wh_per_request.median():.6f} Wh/requête")
    print(f"Ratio médian prédiction / mesure : {ratio.median():.3f}")
    print(f"Erreur relative médiane : {relative_error.median():.1f} %")
    print(f"Corrélation de rang énergie : {rank_correlation:.3f}")
    print("Unité de comparaison : énergie GPU mesurée moyenne par requête; la prédiction V0.1 utilise la longueur de sortie contrôlée.")
    print("La comparaison reste indicative : SweetSpot mesure un H100/TensorRT-LLM et la V0 estime une référence fournisseur.")

    by_input = measured.groupby("Input Length").agg(
        configs=("Output Length", "size"),
        measured_median_j_per_token=("measured_j_per_output_token", "median"),
        compareai_j_per_token=("predicted_j_per_output_token", "median"),
        measured_median_wh=("measured_wh_per_request", "median"),
        predicted_median_wh=("predicted_wh_per_request", "median"),
    )
    print("\nPar longueur d'entrée (Wh/requête, médianes) :")
    print(by_input.to_string(float_format=lambda value: f"{value:.6f}"))


if __name__ == "__main__":
    main()
