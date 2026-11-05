"""CompareAI ↔ SweetSpot model audit and validation of V0.2 energy terms."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from estimateur_v0 import (
    fit,
    fit_input_output_energy,
    load_model_metadata,
    load_rows,
)


ROOT = Path(__file__).resolve().parent
SWEETSPOT_ZIP = ROOT / "source_données" / "sweetspot_llm_energy" / "dataset.zip"
OUTPUT_CROSSWALK = ROOT / "source_données" / "sweetspot_llm_energy" / "rapprochement_sweetspot_compareai.csv"
OUTPUT_RESULTS = ROOT / "source_données" / "sweetspot_llm_energy" / "validation_v02_resultats.csv"

# Les liens non exacts sont conservés avec leur réserve; aucun rapprochement
# automatique par sous-chaîne n'est utilisé pour les noms de modèles.
CROSSWALK = {
    "Llama-3.1-8B-Instruct": ("llama-3.1-8b", "famille/version", "CompareAI ne précise pas le suffixe Instruct"),
    "gemma-2-9b-it": ("gemma-2-9b-it", "nom exact normalisé", "Même famille, version et suffixe instruct"),
    "Qwen2-7B": ("qwen2-7b-instruct", "famille/version proche", "CompareAI précise instruct; SweetSpot indique Qwen2-7B"),
}


def _fit_nonnegative(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x_scale = np.maximum(np.median(np.abs(x), axis=0), 1.0)
    y_scale = max(float(np.median(np.abs(y))), 1e-12)
    scaled_x = x / x_scale
    scaled_y = y / y_scale
    candidates = [np.zeros(x.shape[1])]
    for mask in range(1, 1 << x.shape[1]):
        active = np.array([index for index in range(x.shape[1])
                           if mask & (1 << index)])
        try:
            estimate = np.linalg.lstsq(scaled_x[:, active], scaled_y, rcond=None)[0]
            if np.all(estimate >= 0):
                scaled_coef = np.zeros(x.shape[1])
                scaled_coef[active] = estimate
                coef = scaled_coef * y_scale / x_scale
                candidates.append(coef)
        except np.linalg.LinAlgError:
            continue
    coefficients = min(candidates, key=lambda coef: float(np.square(x @ coef - y).sum()))
    contributions = coefficients * x_scale
    coefficients[contributions < y_scale * 1e-6] = 0.0
    return coefficients


def _split(frame: pd.DataFrame) -> pd.Series:
    def is_test(row) -> bool:
        key = f"{int(row['Input Length'])}:{int(row['Output Length'])}".encode()
        return int(hashlib.sha1(key).hexdigest()[:8], 16) % 5 == 0
    return frame.apply(is_test, axis=1)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.maximum(np.asarray(predicted, dtype=float), 1e-12)
    error = np.abs(predicted - actual)
    return {
        "mae_j_request": float(error.mean()),
        "median_ape_pct": float(np.median(error / np.maximum(actual, 1e-12) * 100)),
        "median_pred_measure_ratio": float(np.median(predicted / actual)),
        "rank_correlation": float(pd.Series(actual).rank().corr(pd.Series(predicted).rank())),
    }


def main() -> None:
    if not SWEETSPOT_ZIP.exists():
        raise SystemExit(f"Archive SweetSpot introuvable : {SWEETSPOT_ZIP}")

    rows = load_rows()
    metadata = load_model_metadata()
    _, factors, _, _, _, _, _ = fit(rows, metadata, 100, 100)
    compareai_terms = fit_input_output_energy(rows, factors, 100)

    with zipfile.ZipFile(SWEETSPOT_ZIP) as archive:
        csv_files = sorted(name for name in archive.namelist()
                           if name.endswith(".csv") and name.count("/") == 2)
        available_names = {name.split("/")[1] for name in csv_files}
        unmatched = [{
            "sweetspot_model": name,
            "compareai_model": "",
            "match_level": "aucun modèle concordant",
            "match_note": "Aucun nom de modèle/version correspondant dans les données CompareAI locales; aucun proxy par taille n'est considéré comme un match.",
        } for name in sorted(available_names - set(CROSSWALK))]
        mapped = [{"sweetspot_model": name, "compareai_model": match[0],
                   "match_level": match[1], "match_note": match[2]}
                  for name, match in CROSSWALK.items() if name in available_names]
        crosswalk = pd.DataFrame(mapped + unmatched).sort_values("sweetspot_model")
        crosswalk.to_csv(OUTPUT_CROSSWALK, index=False, encoding="utf-8-sig")

        results = []
        for match in mapped:
            model_name = match["sweetspot_model"]
            compareai_model = match["compareai_model"]
            match_level = match["match_level"]
            match_note = match["match_note"]
            csv_name = next(name for name in csv_files
                            if name.split("/")[1] == model_name)
            data = pd.read_csv(archive.open(csv_name))
            data["measured_j_request"] = (
                data["Energy (KJ)"] * 1000 / data["Number of requests"]
            )
            is_test = _split(data)
            train, test = data.loc[~is_test].copy(), data.loc[is_test].copy()
            if test.empty or train.empty:
                continue
            x_train = np.column_stack((np.ones(len(train)), train["Input Length"],
                                       train["Output Length"]))
            x_test = np.column_stack((np.ones(len(test)), test["Input Length"],
                                      test["Output Length"]))
            y_train = train.measured_j_request.to_numpy()
            y_test = test.measured_j_request.to_numpy()

            # Baseline SweetSpot : coût constant par token de sortie.
            output_only_rates = _fit_nonnegative(x_train[:, (0, 2)], y_train)
            pred_output_only = x_test[:, (0, 2)] @ output_only_rates

            # V0.2 mesurée : deux coûts non négatifs ajustés sur les seules
            # configurations de calibration SweetSpot.
            sweetspot_rates = _fit_nonnegative(x_train, y_train)
            pred_sweetspot_v02 = x_test @ sweetspot_rates

            # Variante puissance : log(E) dépend séparément de log(input)
            # et de log(output); conservée comme expérimentation comparative.
            log_x_train = np.column_stack((np.ones(len(train)),
                                           np.log1p(train["Input Length"]),
                                           np.log1p(train["Output Length"])))
            log_x_test = np.column_stack((np.ones(len(test)),
                                          np.log1p(test["Input Length"]),
                                          np.log1p(test["Output Length"])))
            log_coefficients = np.linalg.lstsq(log_x_train, np.log(y_train), rcond=None)[0]
            pred_log_v02 = np.exp(log_x_test @ log_coefficients)

            # Transfert hors source : coefficients V0.2 CompareAI appliqués aux
            # tokens exacts de SweetSpot; ce résultat ne sert pas à entraîner.
            if compareai_model in compareai_terms.index:
                ai = compareai_terms.loc[compareai_model]
                pred_compareai_v02 = (
                    x_test[:, 0] * ai.base_kwh_per_request
                    + x_test[:, 1] * ai.input_kwh_per_token
                    + x_test[:, 2] * ai.output_kwh_per_token
                ) * 3_600_000
                ai_factors = factors.loc[compareai_model, "kwh_per_output_token"]
                pred_compareai_v01 = x_test[:, 2] * ai_factors * 3_600_000
            else:
                pred_compareai_v02 = np.full(len(test), np.nan)
                pred_compareai_v01 = np.full(len(test), np.nan)

            for variant, prediction, base_rate, input_rate, output_coeff in [
                ("SweetSpot base + sortie", pred_output_only,
                 float(output_only_rates[0]), 0.0, float(output_only_rates[1])),
                ("SweetSpot base + entrée + sortie", pred_sweetspot_v02,
                 float(sweetspot_rates[0]), float(sweetspot_rates[1]), float(sweetspot_rates[2])),
                ("SweetSpot puissance entrée + sortie", pred_log_v02,
                 float(np.exp(log_coefficients[0]),), float(log_coefficients[1]),
                 float(log_coefficients[2])),
                ("CompareAI V0.1 transférée", pred_compareai_v01, 0.0, 0.0, float(ai_factors)),
                ("CompareAI V0.2 transférée", pred_compareai_v02,
                 float(ai.base_kwh_per_request * 3_600_000),
                 float(ai.input_kwh_per_token * 3_600_000),
                 float(ai.output_kwh_per_token * 3_600_000)),
            ]:
                if np.isnan(prediction).any():
                    continue
                row = {
                    "sweetspot_model": model_name,
                    "compareai_model": compareai_model,
                    "match_level": match_level,
                    "match_note": match_note,
                    "variant": variant,
                    "train_configs": int(len(train)),
                    "test_configs": int(len(test)),
                    "base_j_request": base_rate,
                    "input_j_per_token": input_rate,
                    "output_j_per_token": output_coeff,
                }
                row.update(_metrics(y_test, prediction))
                results.append(row)

    pd.DataFrame(results).to_csv(OUTPUT_RESULTS, index=False, encoding="utf-8-sig")
    print("AUDIT SWEETSPOT ↔ COMPAREAI")
    print(f"Modèles SweetSpot : {len(available_names)}")
    print(f"Correspondances documentées : {len(mapped)}")
    print(crosswalk[["sweetspot_model", "compareai_model", "match_level"]].to_string(index=False))
    print("\nVALIDATION HOLD-OUT SWEETSPOT (80/20 par configuration)")
    if results:
        print(pd.DataFrame(results)[[
            "sweetspot_model", "variant", "mae_j_request", "median_ape_pct",
            "median_pred_measure_ratio", "rank_correlation"
        ]].to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f"\nCorrespondances écrites : {OUTPUT_CROSSWALK}")
    print(f"Résultats écrits : {OUTPUT_RESULTS}")
    print("SweetSpot fournit une mesure H100/TensorRT-LLM; le transfert CompareAI est externe et ne calibre pas ces coefficients.")


if __name__ == "__main__":
    main()
