"""Estimateur V0/V0.1/V0.2 d'éco-routage à partir du dataset local CompareAI.

Exemples :
  python estimateur_v0.py --eval
  python estimateur_v0.py --prompt "Résume ce texte en cinq points." --top 5

Le modèle prédit l'énergie estimée de la réponse (pas une mesure GPU).
"""
from __future__ import annotations

import argparse
import json
import math

from calibration_cache import fingerprint, load_or_build
from pathlib import Path

try:
    import duckdb
    import pandas as pd
    import numpy as np
except ImportError as exc:  # pragma: no cover - aide à l'installation
    raise SystemExit(
        f"Dépendance Python indisponible ({exc.name or 'module inconnu'}). "
        "Installez les dépendances dans le même environnement que l'interface : "
        "python -m pip install duckdb pandas numpy"
    ) from exc


ROOT = Path(__file__).resolve().parent
CALIBRATION_CACHE_DIR = ROOT / ".cache" / "eco-routage"
PARQUET = ROOT / "source_données" / "compareAI" / "conversations.parquet"
MLENERGY_PARQUET = ROOT / "source_données" / "ml-energy-v3" / "runs" / "llm.parquet"
MLENERGY_CROSSWALK = ROOT / "liens_modeles_compareai_ml_energy.csv"


def load_rows() -> "duckdb.DuckDBPyRelation":
    if not PARQUET.exists():
        raise SystemExit(f"Fichier introuvable : {PARQUET}")
    path = str(PARQUET).replace("'", "''")
    # Chaque paire est placée entièrement dans un seul split pour éviter
    # qu'une même requête se retrouve en calibration et en test.
    return duckdb.sql(f"""
        WITH source AS (
          SELECT conversation_pair_id, conv_turns, opening_msg, model_a_name AS model,
                 model_a_total_params AS total_params, model_a_active_params AS active_params, 'a' AS side,
                 total_conv_a_output_tokens AS output_tokens,
                 total_conv_a_kwh AS energy_kwh
          FROM read_parquet('{path}')
          UNION ALL
          SELECT conversation_pair_id, conv_turns, opening_msg, model_b_name AS model,
                 model_b_total_params AS total_params, model_b_active_params AS active_params, 'b' AS side,
                 total_conv_b_output_tokens AS output_tokens,
                 total_conv_b_kwh AS energy_kwh
          FROM read_parquet('{path}')
        )
        SELECT conversation_pair_id, conv_turns, opening_msg, model, total_params, active_params, side,
               output_tokens, energy_kwh,
               greatest(1, ceil(length(coalesce(opening_msg, '')) / 4.0))::DOUBLE AS input_tokens,
               (hash(conversation_pair_id) % 5 <> 0) AS is_train
        FROM source
        WHERE conversation_pair_id IS NOT NULL AND model IS NOT NULL AND conv_turns = 1
          AND output_tokens > 0 AND energy_kwh > 0
    """).df().assign(bucket=lambda d: d.input_tokens.map(length_bucket))


def load_model_metadata():
    path = str(PARQUET).replace("'", "''")
    return duckdb.sql(f"""
        WITH models AS (
          SELECT model_a_name AS model, model_a_total_params AS total_params,
                 model_a_active_params AS active_params FROM read_parquet('{path}')
          UNION ALL
          SELECT model_b_name, model_b_total_params, model_b_active_params
          FROM read_parquet('{path}')
        )
        SELECT model, median(total_params) AS total_params,
               median(active_params) AS active_params
        FROM models WHERE model IS NOT NULL GROUP BY model
    """).df().set_index("model")


def length_bucket(tokens: float) -> str:
    if tokens < 32:
        return "1-31"
    if tokens < 128:
        return "32-127"
    if tokens < 512:
        return "128-511"
    return "512+"


def fit(rows, metadata, min_observations, min_model_bucket_observations):
    train = rows[rows.is_train]
    # alpha = ratio output/input (pondéré par le nombre de tokens d'entrée).
    alpha = float(train.output_tokens.sum() / train.input_tokens.sum())
    direct = (train.groupby("model", sort=True)
               .agg(energy_kwh=("energy_kwh", "sum"), output_tokens=("output_tokens", "sum"),
                    observations=("energy_kwh", "size")))
    direct["direct_factor"] = direct.energy_kwh / direct.output_tokens
    # Facteur de repli pour modèles rares : régression log-log sur les modèles
    # suffisamment observés, avec le nombre total de paramètres comme proxy.
    reg = direct[direct.observations >= min_observations].join(metadata, how="left")
    reg = reg[(reg.total_params > 0) & (reg.direct_factor > 0)]
    if len(reg) < 3:
        raise SystemExit("Pas assez de modèles calibrés avec paramètres connus pour ajuster le fallback.")
    slope, intercept = np.polyfit(np.log10(reg.total_params), np.log10(reg.direct_factor), 1)
    factors = metadata.join(direct[["observations", "direct_factor"]], how="left")
    factors["observations"] = factors.observations.fillna(0).astype(int)
    factors["kwh_per_output_token"] = np.where(
        (factors.observations >= min_observations) & factors.direct_factor.notna(),
        factors.direct_factor,
        np.where(factors.total_params > 0,
                 10 ** (intercept + slope * np.log10(factors.total_params.clip(lower=1))),
                 np.nan),
    )
    factors["factor_source"] = np.where(factors.observations >= min_observations,
                                         "CompareAI observé", "fallback paramètres")
    factors = factors.dropna(subset=["kwh_per_output_token"])
    # V0b: médiane des tokens de sortie dans chaque classe de longueur d'entrée.
    bucket_outputs = train.groupby("bucket").output_tokens.median().to_dict()
    model_bucket_stats = train.groupby(["model", "bucket"]).output_tokens.agg(
        median="median", observations="size"
    )
    model_bucket_outputs = model_bucket_stats.loc[
        model_bucket_stats.observations >= min_model_bucket_observations, "median"
    ].to_dict()
    global_output_median = float(train.output_tokens.median())
    return (alpha, factors, bucket_outputs, model_bucket_outputs, global_output_median,
            (slope, intercept), reg)


def load_mlenergy_factors():
    """Charge les facteurs mesurés stables de la tâche conversationnelle.

    Les configurations GPU restent hétérogènes; la médiane est conservée
    comme proxy central et les quantiles exposent cette variabilité.
    """
    if not MLENERGY_PARQUET.exists() or not MLENERGY_CROSSWALK.exists():
        return None
    crosswalk = pd.read_csv(MLENERGY_CROSSWALK)
    crosswalk = crosswalk[crosswalk.mlenergy_task == "lm-arena-chat"]
    if crosswalk.empty:
        return None
    runs = duckdb.read_parquet(str(MLENERGY_PARQUET)).df()
    runs = runs[(runs.task == "lm-arena-chat") & runs.is_stable.fillna(False)]
    runs = runs.dropna(subset=["model_id", "energy_per_token_joules"])
    runs = runs[runs.energy_per_token_joules > 0]
    joined = crosswalk.merge(runs, left_on="mlenergy_model_id", right_on="model_id")
    if joined.empty:
        return None
    stats = joined.groupby("compareai_model").energy_per_token_joules.agg(
        mlenergy_config_count="size",
        mlenergy_median_j="median",
        mlenergy_p10_j=lambda values: values.quantile(0.10),
        mlenergy_p90_j=lambda values: values.quantile(0.90),
    )
    stats["mlenergy_kwh_per_output_token"] = stats.mlenergy_median_j / 3_600_000
    return stats


def inject_mlenergy_factors(compareai_factors, mlenergy_stats):
    """Remplace les facteurs des modèles reliés par la médiane ML.ENERGY.

    Les autres modèles gardent leur facteur CompareAI ou leur fallback taille.
    """
    factors = compareai_factors.copy()
    factors["compareai_kwh_per_output_token"] = factors.kwh_per_output_token
    for column in ("mlenergy_config_count", "mlenergy_median_j", "mlenergy_p10_j",
                   "mlenergy_p90_j", "mlenergy_kwh_per_output_token"):
        factors[column] = mlenergy_stats[column].reindex(factors.index)
    available = factors.mlenergy_kwh_per_output_token.notna()
    factors.loc[available, "kwh_per_output_token"] = factors.loc[
        available, "mlenergy_kwh_per_output_token"
    ]
    factors.loc[available, "factor_source"] = "ML.ENERGY mesuré (médiane configs)"
    return factors


def score_predictions(test):
    errors_wh = (test.pred_kwh - test.energy_kwh).abs() * 1000
    ape = (errors_wh / (test.energy_kwh * 1000).clip(lower=0.001)) * 100
    ratio = test.pred_kwh / test.energy_kwh
    test = test.copy()
    test["predicted_lower"] = test.pred_kwh
    pairs = test.pivot_table(index="conversation_pair_id", columns="model",
                             values=["energy_kwh", "predicted_lower"], aggfunc="first")
    actual = pairs["energy_kwh"]
    predicted = pairs["predicted_lower"]
    valid = actual.notna().sum(axis=1).eq(2) & predicted.notna().sum(axis=1).eq(2)
    route_accuracy = float((actual.loc[valid].idxmin(axis=1) == predicted.loc[valid].idxmin(axis=1)).mean()) if valid.any() else math.nan
    return {
        "n_test": int(len(test)),
        "mae_wh": float(errors_wh.mean()),
        "median_ape_pct": float(ape.median()),
        "median_pred_ref_ratio": float(ratio.median()),
        "route_pairs": int(valid.sum()),
        "route_accuracy": route_accuracy,
    }


def estimate_output_tokens(models, buckets, model_bucket_outputs, bucket_outputs,
                           global_output_median):
    keys = pd.Series(list(zip(models.to_numpy(), buckets.to_numpy())), index=models.index)
    model_estimate = keys.map(model_bucket_outputs)
    bucket_estimate = buckets.map(bucket_outputs)
    return model_estimate.fillna(bucket_estimate).fillna(global_output_median)


def evaluate(rows, alpha, factors, bucket_outputs, model_bucket_outputs,
             global_output_median):
    test = rows[~rows.is_train].copy()
    test["factor"] = test.model.map(factors.kwh_per_output_token)
    test = test.dropna(subset=["factor"])
    test["out_global"] = alpha * test.input_tokens
    test["out_bucket"] = test.bucket.map(bucket_outputs).fillna(global_output_median)
    model_estimates = estimate_output_tokens(
        test.model, test.bucket, model_bucket_outputs, bucket_outputs, global_output_median
    )
    test["out_model_bucket"] = model_estimates
    outputs = {}
    for label, col in (("V0 globale", "out_global"),
                       ("V0 par longueur", "out_bucket"),
                       ("V0.1 modèle × longueur", "out_model_bucket")):
        data = test.copy()
        data["pred_kwh"] = data.factor * data[col]
        result = score_predictions(data)
        result["output_mae_tokens"] = float((data[col] - data.output_tokens).abs().mean())
        result["output_median_ape_pct"] = float(
            ((data[col] - data.output_tokens).abs() / data.output_tokens.clip(lower=1) * 100).median()
        )
        if label == "V0.1 modèle × longueur":
            result["model_bucket_coverage_pct"] = float(
                pd.Series(list(zip(test.model, test.bucket)), index=test.index)
                .map(model_bucket_outputs).notna().mean()
            )
        outputs[label] = result
    return outputs


def _fit_nonnegative_energy_terms(input_tokens, output_tokens, energy_kwh):
    """Ajuste E = base/requête + coût_entrée + coût_sortie, coefficients ≥ 0."""
    x = np.column_stack((np.ones(len(input_tokens), dtype=float),
                         np.asarray(input_tokens, dtype=float),
                         np.asarray(output_tokens, dtype=float)))
    y = np.asarray(energy_kwh, dtype=float)
    x_scale = np.maximum(np.median(np.abs(x), axis=0), 1.0)
    y_scale = max(float(np.median(np.abs(y))), 1e-15)
    scaled_x = x / x_scale
    scaled_y = y / y_scale
    candidates = [np.zeros(3, dtype=float)]
    for mask in range(1, 1 << x.shape[1]):
        active = np.array([index for index in range(x.shape[1])
                           if mask & (1 << index)])
        try:
            estimate = np.linalg.lstsq(scaled_x[:, active], scaled_y, rcond=None)[0]
            if np.all(estimate >= 0):
                scaled_coefficients = np.zeros(3, dtype=float)
                scaled_coefficients[active] = estimate
                coefficients = scaled_coefficients * y_scale / x_scale
                candidates.append(coefficients)
        except np.linalg.LinAlgError:
            continue
    coefficients = min(candidates, key=lambda coef: float(np.square(x @ coef - y).sum()))
    contributions = coefficients * x_scale
    coefficients[contributions < y_scale * 1e-6] = 0.0
    return coefficients, float(np.square(x @ coefficients - y).sum())


def fit_input_output_energy(rows, factors, min_observations):
    """Ajuste des coûts d'entrée et de sortie par modèle sur la calibration CompareAI."""
    train = rows[rows.is_train]
    records = []
    for model in factors.index:
        data = train[train.model == model]
        if len(data) >= min_observations:
            coefficients, sse = _fit_nonnegative_energy_terms(
                data.input_tokens, data.output_tokens, data.energy_kwh
            )
            total = float(np.square(data.energy_kwh.to_numpy() -
                                    data.energy_kwh.mean()).sum())
            r_squared = 1 - sse / total if total > 0 else math.nan
            records.append((model, coefficients[0], coefficients[1], coefficients[2], len(data), r_squared,
                            "régression entrée + sortie"))
        else:
            records.append((model, 0.0, 0.0, float(factors.loc[model, "kwh_per_output_token"]),
                            len(data), math.nan, "repli sortie seule"))
    return pd.DataFrame(records, columns=[
        "model", "base_kwh_per_request", "input_kwh_per_token", "output_kwh_per_token", "observations",
        "r_squared", "energy_model_source"
    ]).set_index("model")


def fit_powerlaw_energy(rows, factors, min_observations):
    """Ajuste E = base × (1 + entrée)^a × (1 + sortie)^b par modèle."""
    train = rows[rows.is_train]
    records = []
    for model in factors.index:
        data = train[train.model == model]
        if len(data) >= min_observations:
            x = np.column_stack((np.ones(len(data)), np.log1p(data.input_tokens),
                                 np.log1p(data.output_tokens)))
            y = np.log(data.energy_kwh.to_numpy())
            candidates = []
            # L'intercept reste libre; les exposants sont contraints à être ≥ 0.
            for mask in range(1 << 2):
                active = [0] + [index + 1 for index in range(2)
                                if mask & (1 << index)]
                coef = np.linalg.lstsq(x[:, active], y, rcond=None)[0]
                slopes = coef[1:]
                if np.all(slopes >= 0):
                    full = np.zeros(3)
                    full[active] = coef
                    candidates.append(full)
            coefficients = min(candidates, key=lambda value: float(np.square(x @ value - y).sum()))
            predicted_log = x @ coefficients
            total = float(np.square(y - y.mean()).sum())
            r_squared = 1 - float(np.square(y - predicted_log).sum()) / total if total > 0 else math.nan
            records.append((model, math.exp(float(np.clip(coefficients[0], -700, 700))),
                            coefficients[1], coefficients[2], len(data), r_squared,
                            "régression puissance entrée + sortie"))
        else:
            records.append((model, 0.0, 0.0, 0.0, len(data), math.nan,
                            "repli sortie seule"))
    return pd.DataFrame(records, columns=[
        "model", "base_kwh_per_request", "input_exponent", "output_exponent",
        "observations", "r_squared", "energy_model_source"
    ]).set_index("model")


def predict_total_energy_kwh(data, output_column, energy_terms, factors=None):
    if "input_exponent" in energy_terms.columns:
        estimate = (
            data.model.map(energy_terms.base_kwh_per_request)
            * np.power(1 + data.input_tokens,
                       data.model.map(energy_terms.input_exponent))
            * np.power(1 + data[output_column],
                       data.model.map(energy_terms.output_exponent))
        )
        fallback = data.model.map(energy_terms.energy_model_source).eq("repli sortie seule")
        if factors is not None and fallback.any():
            estimate.loc[fallback] = (
                data.loc[fallback, "model"].map(factors.kwh_per_output_token)
                * data.loc[fallback, output_column]
            )
        return estimate
    base = data.model.map(energy_terms.base_kwh_per_request).fillna(0.0)
    input_rate = data.model.map(energy_terms.input_kwh_per_token).fillna(0.0)
    output_rate = data.model.map(energy_terms.output_kwh_per_token)
    return base + input_rate * data.input_tokens + output_rate * data[output_column]


def evaluate_input_output_energy(rows, factors, bucket_outputs,
                                 model_bucket_outputs, global_output_median,
                                 energy_terms):
    test = rows[~rows.is_train].copy()
    test["factor"] = test.model.map(factors.kwh_per_output_token)
    test = test.dropna(subset=["factor"])
    test["out_model_bucket"] = estimate_output_tokens(
        test.model, test.bucket, model_bucket_outputs, bucket_outputs, global_output_median
    )
    test["pred_kwh"] = predict_total_energy_kwh(test, "out_model_bucket", energy_terms)
    result = score_predictions(test)
    result["output_mae_tokens"] = float((test.out_model_bucket - test.output_tokens).abs().mean())
    result["output_median_ape_pct"] = float(
        ((test.out_model_bucket - test.output_tokens).abs() /
         test.output_tokens.clip(lower=1) * 100).median()
    )
    result["models_with_two_terms"] = int(
        energy_terms.energy_model_source.eq("régression entrée + sortie").sum()
    )
    result["median_input_energy_share_pct"] = float(
        (test.model.map(energy_terms.input_kwh_per_token) * test.input_tokens /
         test.pred_kwh.clip(lower=1e-15) * 100).median()
    )
    return result


def evaluate_powerlaw_energy(rows, factors, bucket_outputs, model_bucket_outputs,
                             global_output_median, power_terms):
    test = rows[~rows.is_train].copy()
    test["factor"] = test.model.map(factors.kwh_per_output_token)
    test = test.dropna(subset=["factor"])
    test["out_model_bucket"] = estimate_output_tokens(
        test.model, test.bucket, model_bucket_outputs, bucket_outputs, global_output_median
    )
    test["pred_kwh"] = predict_total_energy_kwh(
        test, "out_model_bucket", power_terms, factors
    )
    result = score_predictions(test)
    result["output_mae_tokens"] = float((test.out_model_bucket - test.output_tokens).abs().mean())
    result["output_median_ape_pct"] = float(
        ((test.out_model_bucket - test.output_tokens).abs() /
         test.output_tokens.clip(lower=1) * 100).median()
    )
    result["models_with_power_terms"] = int(
        power_terms.energy_model_source.eq("régression puissance entrée + sortie").sum()
    )
    result["median_input_exponent"] = float(
        power_terms.loc[power_terms.input_exponent > 0, "input_exponent"].median()
    ) if (power_terms.input_exponent > 0).any() else 0.0
    return result


def load_votes():
    path = str(ROOT / "source_données" / "compareAI" / "votes.parquet").replace("'", "''")
    return duckdb.sql(f"""
        SELECT conversation_pair_id, conv_turns, model_a_name, model_b_name,
               chosen_model_name, both_equal,
               (hash(conversation_pair_id) % 5 <> 0) AS is_train
        FROM read_parquet('{path}')
        WHERE conversation_pair_id IS NOT NULL AND conv_turns = 1
    """).df()


def fit_preference(votes, min_votes, threshold=0.55):
    train = votes[votes.is_train].copy()
    train = train[(train.both_equal.fillna(False)) | train.chosen_model_name.notna()]
    a = pd.DataFrame({"model": train.model_a_name,
                      "score": train.both_equal.fillna(False).astype(float) * 0.5 +
                               ((~train.both_equal.fillna(False)) & (train.chosen_model_name == train.model_a_name)).astype(float)})
    b = pd.DataFrame({"model": train.model_b_name,
                      "score": train.both_equal.fillna(False).astype(float) * 0.5 +
                               ((~train.both_equal.fillna(False)) & (train.chosen_model_name == train.model_b_name)).astype(float)})
    ratings = pd.concat([a, b]).groupby("model").score.agg(["mean", "count"])
    eligible = ratings[(ratings["count"] >= min_votes) & (ratings["mean"] >= threshold)]
    return ratings, set(eligible.index)


def load_reactions():
    path = str(ROOT / "source_données" / "compareAI" / "reactions.parquet").replace("'", "''")
    return duckdb.sql(f"""
        SELECT conversation_pair_id, refers_to_model, conv_turns,
               useful, complete, incorrect, superficial, instructions_not_followed,
               (hash(conversation_pair_id) % 5 <> 0) AS is_train
        FROM read_parquet('{path}')
        WHERE conversation_pair_id IS NOT NULL AND refers_to_model IS NOT NULL
          AND conv_turns = 1
    """).df()


def add_reaction_quality(reactions):
    positive = ["useful", "complete"]
    negative = ["incorrect", "superficial", "instructions_not_followed"]
    scores = []
    for column in positive:
        scores.append(reactions[column].astype("Float64"))
    for column in negative:
        scores.append(1 - reactions[column].astype("Float64"))
    values = pd.concat(scores, axis=1)
    reactions = reactions.copy()
    reactions["quality_score"] = values.mean(axis=1, skipna=True).astype(float)
    return reactions.dropna(subset=["quality_score"])


def fit_reaction_quality(reactions, min_reactions, threshold):
    train = add_reaction_quality(reactions[reactions.is_train])
    ratings = train.groupby("refers_to_model").quality_score.agg(["mean", "count"])
    eligible = ratings[(ratings["count"] >= min_reactions) & (ratings["mean"] >= threshold)]
    return ratings, set(eligible.index)


def evaluate_reaction_gate(rows, reactions, factors, bucket_outputs,
                           global_output_median, eligible_models,
                           model_bucket_outputs=None, energy_terms=None):
    test_rows = rows[(~rows.is_train) & rows.model.isin(factors.index)].copy()
    test_rows["factor"] = test_rows.model.map(factors.kwh_per_output_token)
    if model_bucket_outputs is None:
        test_rows["output_est"] = test_rows.bucket.map(bucket_outputs).fillna(global_output_median)
    else:
        test_rows["output_est"] = estimate_output_tokens(
            test_rows.model, test_rows.bucket, model_bucket_outputs,
            bucket_outputs, global_output_median
        )
    test_rows["pred_kwh"] = (
        predict_total_energy_kwh(test_rows, "output_est", energy_terms, factors)
        if energy_terms is not None else test_rows.factor * test_rows.output_est
    )
    pair_sides = test_rows.pivot_table(index="conversation_pair_id", columns="side",
                                       values=["model", "energy_kwh", "pred_kwh"], aggfunc="first")
    pair_sides.columns = [f"{metric}_{side}" for metric, side in pair_sides.columns]
    pair_sides = pair_sides.dropna(subset=["model_a", "model_b", "energy_kwh_a",
                                           "energy_kwh_b", "pred_kwh_a", "pred_kwh_b"])
    pair_sides["base_side"] = np.where(pair_sides.pred_kwh_a <= pair_sides.pred_kwh_b, "a", "b")

    test_reactions = add_reaction_quality(reactions[~reactions.is_train])
    long_models = pd.concat([
        pair_sides[["model_a"]].rename(columns={"model_a": "model"}).assign(side="a"),
        pair_sides[["model_b"]].rename(columns={"model_b": "model"}).assign(side="b"),
    ]).reset_index()
    rated = test_reactions.merge(long_models, left_on=["conversation_pair_id", "refers_to_model"],
                                 right_on=["conversation_pair_id", "model"], how="inner")
    rated = rated.groupby(["conversation_pair_id", "side"], as_index=False).quality_score.mean()
    quality_wide = rated.pivot(index="conversation_pair_id", columns="side", values="quality_score")
    pairs = pair_sides.join(quality_wide, how="inner").dropna(subset=["a", "b"])
    allow_a = pairs.model_a.isin(eligible_models)
    allow_b = pairs.model_b.isin(eligible_models)
    pairs["route_side"] = None
    pairs.loc[allow_a & ~allow_b, "route_side"] = "a"
    pairs.loc[allow_b & ~allow_a, "route_side"] = "b"
    both = allow_a & allow_b
    pairs.loc[both, "route_side"] = pairs.loc[both, "base_side"]
    routed = pairs.route_side.notna()
    pairs["routed_quality"] = pairs.a.where(pairs.route_side == "a", pairs.b)
    pairs["other_quality"] = pairs.b.where(pairs.route_side == "a", pairs.a)
    pairs["routed_energy"] = pairs.energy_kwh_a.where(pairs.route_side == "a", pairs.energy_kwh_b) * 1000
    pairs["other_energy"] = pairs.energy_kwh_b.where(pairs.route_side == "a", pairs.energy_kwh_a) * 1000
    return {
        "paired_test_reactions": int(len(pairs)),
        "coverage": float(routed.mean()) if len(pairs) else math.nan,
        "mean_quality": float(pairs.loc[routed, "routed_quality"].mean()) if routed.any() else math.nan,
        "quality_win_rate": float((pairs.loc[routed, "routed_quality"] >= pairs.loc[routed, "other_quality"]).mean()) if routed.any() else math.nan,
        "mean_energy_difference_wh": float((pairs.loc[routed, "routed_energy"] - pairs.loc[routed, "other_energy"]).mean()) if routed.any() else math.nan,
    }


def leave_one_model_out_size_check(reg):
    data = reg[(reg.total_params > 0) & (reg.direct_factor > 0)].copy()
    if len(data) < 4:
        return None
    x = np.log10(data.total_params.to_numpy())
    y = np.log10(data.direct_factor.to_numpy())
    predicted, global_predicted = [], []
    for i in range(len(data)):
        keep = np.arange(len(data)) != i
        slope, intercept = np.polyfit(x[keep], y[keep], 1)
        predicted.append(intercept + slope * x[i])
        global_predicted.append(np.median(y[keep]))
    target = 10 ** y
    size_error = np.abs(10 ** np.asarray(predicted) / target - 1)
    median_error = np.abs(10 ** np.asarray(global_predicted) / target - 1)
    return float(np.median(size_error)), float(np.median(median_error)), len(data)


def evaluate_quality_gate(rows, votes, factors, bucket_outputs, global_output_median,
                          eligible_models, model_bucket_outputs=None,
                          energy_terms=None):
    test_rows = rows[(~rows.is_train) & rows.model.isin(factors.index)].copy()
    test_rows["factor"] = test_rows.model.map(factors.kwh_per_output_token)
    if model_bucket_outputs is None:
        test_rows["output_est"] = test_rows.bucket.map(bucket_outputs).fillna(global_output_median)
    else:
        test_rows["output_est"] = estimate_output_tokens(
            test_rows.model, test_rows.bucket, model_bucket_outputs,
            bucket_outputs, global_output_median
        )
    test_rows["pred_kwh"] = (
        predict_total_energy_kwh(test_rows, "output_est", energy_terms, factors)
        if energy_terms is not None else test_rows.factor * test_rows.output_est
    )
    by_side = test_rows.pivot_table(index="conversation_pair_id", columns="side",
                                    values=["energy_kwh", "pred_kwh"], aggfunc="first")
    by_side.columns = [f"{metric}_{side}" for metric, side in by_side.columns]
    v = votes[~votes.is_train].copy()
    v = v[v.chosen_model_name.notna() & ~v.both_equal.fillna(False)]
    v = v.merge(by_side, left_on="conversation_pair_id", right_index=True, how="inner")
    v = v.dropna(subset=["energy_kwh_a", "energy_kwh_b", "pred_kwh_a", "pred_kwh_b"])
    v["base_model"] = v.model_a_name.where(v.pred_kwh_a <= v.pred_kwh_b, v.model_b_name)
    v["base_ref_wh"] = v.energy_kwh_a.where(v.base_model == v.model_a_name, v.energy_kwh_b) * 1000
    v["user_ref_wh"] = v.energy_kwh_a.where(v.chosen_model_name == v.model_a_name, v.energy_kwh_b) * 1000
    allow_a = v.model_a_name.isin(eligible_models)
    allow_b = v.model_b_name.isin(eligible_models)
    v["gated_model"] = None
    v.loc[allow_a & ~allow_b, "gated_model"] = v.loc[allow_a & ~allow_b, "model_a_name"]
    v.loc[allow_b & ~allow_a, "gated_model"] = v.loc[allow_b & ~allow_a, "model_b_name"]
    both = allow_a & allow_b
    v.loc[both, "gated_model"] = v.loc[both, "base_model"]
    v["gated_ref_wh"] = v.energy_kwh_a.where(v.gated_model == v.model_a_name, v.energy_kwh_b) * 1000
    coverage = v.gated_model.notna()
    return {
        "n_votes": int(len(v)),
        "base_preference_agreement": float((v.base_model == v.chosen_model_name).mean()) if len(v) else math.nan,
        "base_energy_accuracy": float((v.base_ref_wh <= v.user_ref_wh).mean()) if len(v) else math.nan,
        "coverage": float(coverage.mean()) if len(v) else math.nan,
        "gated_preference_agreement": float((v.loc[coverage, "gated_model"] == v.loc[coverage, "chosen_model_name"]).mean()) if coverage.any() else math.nan,
        "gated_energy_accuracy": float((v.loc[coverage, "gated_ref_wh"] <= v.loc[coverage, "user_ref_wh"]).mean()) if coverage.any() else math.nan,
        "mean_saving_vs_user_wh": float((v.loc[coverage, "user_ref_wh"] - v.loc[coverage, "gated_ref_wh"]).mean()) if coverage.any() else math.nan,
    }


def main():
    parser = argparse.ArgumentParser(description="Estimateur V0/V0.1/V0.2 énergie / éco-routage")
    parser.add_argument("--eval", action="store_true", help="évaluer sur le split test figé")
    parser.add_argument("--prompt", help="estimer l'énergie pour ce prompt")
    parser.add_argument("--json-line", action="store_true", help="ajouter une ligne JSON structurée pour l’API")
    parser.add_argument("--calibration-cache", action="store_true", help="utiliser le cache privé des calibrations (mode local uniquement)")
    parser.add_argument("--top", type=int, default=5, help="nombre de modèles à afficher")
    parser.add_argument("--energy-source", choices=("compareai", "mlenergy"), default="compareai",
                        help="source des facteurs énergie pour la recommandation (défaut : compareai)")
    parser.add_argument("--energy-model", choices=("power-law", "input-output", "output-only"),
                        default="power-law",
                        help="modèle CompareAI : puissance entrée/sortie, régression additive, ou sortie seule")
    parser.add_argument("--min-observations", type=int, default=100,
                        help="minimum de réponses de calibration par modèle")
    parser.add_argument("--min-model-bucket-observations", type=int, default=100,
                        help="minimum d'observations pour estimer une sortie par modèle et tranche")
    parser.add_argument("--min-votes", type=int, default=100,
                        help="minimum de votes train avant d'appliquer le filtre de préférence")
    parser.add_argument("--quality-threshold", type=float, default=0.55,
                        help="taux minimal de préférence utilisateur (défaut : 0.55)")
    parser.add_argument("--min-reactions", type=int, default=100,
                        help="minimum de réactions train pour le filtre qualité direct")
    parser.add_argument("--reaction-threshold", type=float, default=0.65,
                        help="score composite minimal de réaction (défaut : 0.65)")
    args = parser.parse_args()
    if not args.eval and args.prompt is None:
        parser.error("indiquez --eval et/ou --prompt")

    rows = None
    def build_calibration():
        nonlocal rows
        raw_rows = load_rows()
        if args.eval:
            rows = raw_rows
        metadata = load_model_metadata()
        (fit_alpha, calibrated_factors, calibrated_buckets, calibrated_model_buckets,
         global_median, size_regression, reg_data) = fit(
            raw_rows, metadata, args.min_observations, args.min_model_bucket_observations
        )
        return {
            "valid_rows": len(raw_rows),
            "alpha": fit_alpha,
            "compareai_factors": calibrated_factors,
            "bucket_outputs": calibrated_buckets,
            "model_bucket_outputs": calibrated_model_buckets,
            "global_output_median": global_median,
            "reg_data": reg_data,
            "input_output_terms": fit_input_output_energy(
                raw_rows, calibrated_factors, args.min_observations
            ),
            "power_terms": fit_powerlaw_energy(
                raw_rows, calibrated_factors, args.min_observations
            ),
            "mlenergy_stats": load_mlenergy_factors(),
        }

    if args.calibration_cache and not args.eval:
        cache_key = fingerprint(
            [PARQUET, MLENERGY_PARQUET, MLENERGY_CROSSWALK, Path(__file__).resolve()],
            {"min_observations": args.min_observations,
             "min_model_bucket_observations": args.min_model_bucket_observations}
        )
        calibration = load_or_build(
            CALIBRATION_CACHE_DIR, "calibration", cache_key, build_calibration
        )
    else:
        calibration = build_calibration()

    (alpha, compareai_factors, bucket_outputs, model_bucket_outputs,
     global_output_median, reg_data, input_output_terms, power_terms, mlenergy_stats) = (
        calibration["alpha"], calibration["compareai_factors"],
        calibration["bucket_outputs"], calibration["model_bucket_outputs"],
        calibration["global_output_median"], calibration["reg_data"],
        calibration["input_output_terms"], calibration["power_terms"], calibration["mlenergy_stats"]
    )
    mlenergy_factors = (inject_mlenergy_factors(compareai_factors, mlenergy_stats)
                        if mlenergy_stats is not None else None)
    if args.energy_source == "mlenergy" and mlenergy_factors is None:
        raise SystemExit("Facteurs ML.ENERGY indisponibles : vérifiez le Parquet et le crosswalk local.")
    if args.energy_source == "mlenergy":
        # Ne pas classer ensemble des facteurs physiques ML.ENERGY et des
        # estimations CompareAI : les configurations sous-jacentes diffèrent.
        factors = mlenergy_factors[mlenergy_factors.mlenergy_kwh_per_output_token.notna()].copy()
    else:
        factors = compareai_factors
    print(f"Données valides : {calibration['valid_rows']:,} réponses | modèles candidats : {len(factors)}")
    print(f"Facteurs de base CompareAI observés : {(compareai_factors.factor_source == 'CompareAI observé').sum()} | fallback paramètres : {(compareai_factors.factor_source == 'fallback paramètres').sum()}")
    if mlenergy_stats is not None:
        injected = mlenergy_factors.factor_source.eq("ML.ENERGY mesuré (médiane configs)").sum()
        print(f"Facteurs ML.ENERGY injectés : {injected} modèles ({int(mlenergy_stats.mlenergy_config_count.sum())} configurations stables)")
    else:
        print("ML.ENERGY absent : facteurs CompareAI/fallback conservés")
    print(f"alpha moyen calibre : {alpha:.3f} token de sortie / token d'entree")
    print(f"Source active pour la recommandation : {args.energy_source}")
    if args.eval:
        if rows is None:
            rows = load_rows()
        baseline_results = evaluate(rows, alpha, compareai_factors, bucket_outputs,
                                     model_bucket_outputs, global_output_median)
        print("\nÉVALUATION HOLD-OUT (20 %, paires jamais vues en calibration)")
        for name, result in baseline_results.items():
            print(f"\nBASELINE CompareAI — {name} ({result['n_test']:,} réponses test)")
            print(f"MAE                 : {result['mae_wh']:.4f} Wh")
            print(f"Erreur relative méd. : {result['median_ape_pct']:.1f} %")
            print(f"MAE sortie estimée  : {result['output_mae_tokens']:.1f} tokens")
            print(f"Erreur méd. sortie  : {result['output_median_ape_pct']:.1f} %")
            print(f"Ratio médiane préd/réf. : {result['median_pred_ref_ratio']:.2f}")
            print(f"Accuracy routage     : {result['route_accuracy']:.1%} ({result['route_pairs']:,} paires)")
            if "model_bucket_coverage_pct" in result:
                print(f"Couverture modèle × tranche : {result['model_bucket_coverage_pct']:.1%}")
        v02 = evaluate_input_output_energy(
            rows, compareai_factors, bucket_outputs, model_bucket_outputs,
            global_output_median, input_output_terms
        )
        print(f"\nV0.2 CompareAI — régression énergie entrée + sortie ({v02['n_test']:,} réponses test)")
        print(f"MAE énergie         : {v02['mae_wh']:.4f} Wh")
        print(f"Erreur relative méd. : {v02['median_ape_pct']:.1f} %")
        print(f"Accuracy routage     : {v02['route_accuracy']:.1%} ({v02['route_pairs']:,} paires)")
        print(f"Modèles avec deux coûts ajustés : {v02['models_with_two_terms']}")
        print(f"Part médiane énergie d'entrée : {v02['median_input_energy_share_pct']:.1f} %")
        power = evaluate_powerlaw_energy(
            rows, compareai_factors, bucket_outputs, model_bucket_outputs,
            global_output_median, power_terms
        )
        print(f"\nV0.2 CompareAI — loi de puissance entrée + sortie ({power['n_test']:,} réponses test)")
        print(f"MAE énergie         : {power['mae_wh']:.4f} Wh")
        print(f"Erreur relative méd. : {power['median_ape_pct']:.1f} %")
        print(f"Accuracy routage     : {power['route_accuracy']:.1%} ({power['route_pairs']:,} paires)")
        print(f"Modèles avec exposants ajustés : {power['models_with_power_terms']}")
        print(f"Exposant médian d'entrée positif : {power['median_input_exponent']:.3f}")
        if mlenergy_stats is not None:
            injected_results = evaluate(rows, alpha, mlenergy_factors, bucket_outputs,
                                        model_bucket_outputs, global_output_median)
            for name, result in injected_results.items():
                print(f"\nHYBRIDE ML.ENERGY — {name} ({result['n_test']:,} réponses test)")
                print(f"MAE                 : {result['mae_wh']:.4f} Wh")
                print(f"Erreur relative méd. : {result['median_ape_pct']:.1f} %")
                print(f"MAE sortie estimée  : {result['output_mae_tokens']:.1f} tokens")
                print(f"Erreur méd. sortie  : {result['output_median_ape_pct']:.1f} %")
                print(f"Ratio médiane préd/réf. : {result['median_pred_ref_ratio']:.2f}")
                print(f"Accuracy routage     : {result['route_accuracy']:.1%} ({result['route_pairs']:,} paires)")
                if "model_bucket_coverage_pct" in result:
                    print(f"Couverture modèle × tranche : {result['model_bucket_coverage_pct']:.1%}")
        cold = leave_one_model_out_size_check(reg_data)
        if cold:
            print(f"\nTest fallback paramètres (leave-one-model-out, {cold[2]} modèles)")
            print(f"Erreur relative médiane taille -> facteur : {cold[0]:.1%}")
            print(f"Erreur relative médiane facteur global     : {cold[1]:.1%}")
        votes = load_votes()
        ratings, eligible = fit_preference(votes, args.min_votes, args.quality_threshold)
        active_energy_terms = None
        if args.energy_source == "compareai":
            active_energy_terms = power_terms if args.energy_model == "power-law" else (
                input_output_terms if args.energy_model == "input-output" else None
            )
        quality = evaluate_quality_gate(rows, votes, factors, bucket_outputs,
                                        global_output_median, eligible, model_bucket_outputs,
                                        active_energy_terms)
        print(f"\nFILTRE DE PRÉFÉRENCE UTILISATEUR (seuil {args.quality_threshold:.0%}, calibration uniquement)")
        print(f"Modeles eligibles : {len(eligible)} (au moins {args.min_votes} votes de calibration)")
        print(f"Paires votées testées : {quality['n_votes']:,}")
        print(f"Accord du routage énergie seul avec le vote test : {quality['base_preference_agreement']:.1%}")
        print(f"Couverture après filtre : {quality['coverage']:.1%}")
        print(f"Accord du routage filtré avec le vote test : {quality['gated_preference_agreement']:.1%}")
        print(f"Part des choix filtrés moins énergivores que le choix utilisateur (réf. CompareAI) : {quality['gated_energy_accuracy']:.1%}")
        print(f"Écart moyen vs choix utilisateur : {quality['mean_saving_vs_user_wh']:.4f} Wh")
        reactions = load_reactions()
        reaction_ratings, reaction_eligible = fit_reaction_quality(
            reactions, args.min_reactions, args.reaction_threshold
        )
        direct_quality = evaluate_reaction_gate(rows, reactions, factors, bucket_outputs,
                                                global_output_median, reaction_eligible,
                                                model_bucket_outputs, active_energy_terms)
        print(f"\nFILTRE DIRECT PAR RÉACTIONS (seuil {args.reaction_threshold:.0%}, calibration uniquement)")
        print(f"Modèles éligibles : {len(reaction_eligible)} (au moins {args.min_reactions} réactions train)")
        print(f"Paires test avec réactions des deux côtés : {direct_quality['paired_test_reactions']:,}")
        print(f"Couverture : {direct_quality['coverage']:.1%}")
        print(f"Score qualité moyen du modèle routé : {direct_quality['mean_quality']:.3f}")
        print(f"Le modèle routé égale/dépasse l'autre réponse : {direct_quality['quality_win_rate']:.1%}")
        print(f"Écart énergie routée - autre réponse : {direct_quality['mean_energy_difference_wh']:.4f} Wh")
    if args.prompt is not None:
        input_tokens = max(1, math.ceil(len(args.prompt) / 4))
        bucket = length_bucket(input_tokens)
        ranking = factors.copy()
        prompt_models = pd.Series(ranking.index, index=ranking.index)
        prompt_buckets = pd.Series(bucket, index=ranking.index)
        ranking["output_tokens_est"] = estimate_output_tokens(
            prompt_models, prompt_buckets, model_bucket_outputs,
            bucket_outputs, global_output_median
        )
        ranking["output_energy_wh"] = ranking.kwh_per_output_token * ranking.output_tokens_est * 1000
        ranking["input_energy_wh"] = 0.0
        ranking["base_energy_wh"] = 0.0
        ranking["input_exponent"] = 0.0
        ranking["output_exponent"] = 1.0
        if args.energy_source == "compareai" and args.energy_model == "input-output":
            ranking["base_energy_wh"] = (
                ranking.index.to_series().map(input_output_terms.base_kwh_per_request).to_numpy()
                * 1000
            )
            ranking["input_energy_wh"] = (
                ranking.index.to_series().map(input_output_terms.input_kwh_per_token).to_numpy()
                * input_tokens * 1000
            )
            ranking["output_energy_wh"] = (
                ranking.index.to_series().map(input_output_terms.output_kwh_per_token).to_numpy()
                * ranking.output_tokens_est.to_numpy() * 1000
            )
        if args.energy_source == "compareai" and args.energy_model == "power-law":
            ranking["base_energy_wh"] = (
                ranking.index.to_series().map(power_terms.base_kwh_per_request).to_numpy()
                * 1000
            )
            ranking["input_exponent"] = (
                ranking.index.to_series().map(power_terms.input_exponent).to_numpy()
            )
            ranking["output_exponent"] = (
                ranking.index.to_series().map(power_terms.output_exponent).to_numpy()
            )
            input_multiplier = np.power(1 + input_tokens, ranking.input_exponent)
            output_multiplier = np.power(1 + ranking.output_tokens_est,
                                         ranking.output_exponent)
            fallback = ranking.index.to_series().map(power_terms.energy_model_source).eq("repli sortie seule").to_numpy()
            ranking["estimated_wh"] = (
                ranking.base_energy_wh * input_multiplier * output_multiplier
            )
            ranking.loc[fallback, "estimated_wh"] = (
                ranking.loc[fallback, "kwh_per_output_token"]
                * ranking.loc[fallback, "output_tokens_est"] * 1000
            )
        else:
            ranking["estimated_wh"] = (
                ranking.base_energy_wh + ranking.input_energy_wh + ranking.output_energy_wh
            )
        if args.energy_source == "mlenergy":
            ranking["config_p10_wh"] = ranking.mlenergy_p10_j * ranking.output_tokens_est / 3600
            ranking["config_p90_wh"] = ranking.mlenergy_p90_j * ranking.output_tokens_est / 3600
        def build_reaction_scores():
            return fit_reaction_quality(
                load_reactions(), args.min_reactions, args.reaction_threshold
            )

        if args.calibration_cache:
            reaction_key = fingerprint(
                [ROOT / "source_données" / "compareAI" / "reactions.parquet",
                 Path(__file__).resolve()],
                {"min_reactions": args.min_reactions,
                 "reaction_threshold": args.reaction_threshold}
            )
            ratings, eligible = load_or_build(
                CALIBRATION_CACHE_DIR, "reactions", reaction_key,
                build_reaction_scores
            )
        else:
            ratings, eligible = build_reaction_scores()
        ranking["reaction_quality"] = ranking.index.map(ratings["mean"])
        ranking["reaction_count"] = ranking.index.map(ratings["count"]).fillna(0)
        ranking = ranking.sort_values("estimated_wh")
        print(f"\nPrompt : {args.prompt}")
        if args.energy_source == "compareai" and args.energy_model == "input-output":
            print(f"Entrée approximée : {input_tokens} tokens | régression additive entrée/sortie (V0.2)")
        elif args.energy_source == "compareai" and args.energy_model == "power-law":
            print(f"Entrée approximée : {input_tokens} tokens | loi de puissance entrée/sortie (V0.2)")
        else:
            print(f"Entrée approximée : {input_tokens} tokens | énergie sortie seule")
        print("Les sorties sont estimées par modèle et longueur (repli global si peu de données).")
        eligible_ranking = ranking[ranking.index.isin(eligible)]
        if len(eligible_ranking):
            chosen_model = eligible_ranking.index[0]
            print("\nRecommandation avec filtre de réactions : " + str(chosen_model))
        else:
            chosen_model = ranking.index[0]
            print("\nAucun modèle n'atteint le seuil de réactions; meilleur facteur énergétique : " + str(chosen_model))
        display = ranking.head(max(1, args.top))
        if chosen_model not in display.index:
            display = pd.concat([display, ranking.loc[[chosen_model]]])
        display = display.copy()
        display["recommended"] = display.index == chosen_model
        if args.json_line:
            # Contrat machine lisible ; la sortie CLI historique reste inchangée par défaut.
            columns = ["estimated_wh", "output_tokens_est", "observations",
                       "factor_source", "reaction_quality", "reaction_count", "recommended",
                       "config_p10_wh", "config_p90_wh", "input_exponent", "output_exponent",
                       "input_energy_wh", "output_energy_wh", "base_energy_wh"]
            frame = display.reset_index().rename(columns={"model": "name"})
            record_columns = ["name"] + [col for col in columns if col in frame.columns]
            payload = {
                "energy_source": args.energy_source,
                "energy_model": "output-only" if args.energy_source == "mlenergy" else args.energy_model,
                "input_tokens": int(input_tokens),
                "models_evaluated": int(len(ranking)),
                "recommended_model": str(chosen_model),
                "quality_filter_applied": bool(len(eligible_ranking)),
                "results": json.loads(frame[record_columns].to_json(orient="records")),
            }
            print("ECO_ROUTAGE_JSON:" + json.dumps(payload, ensure_ascii=False, allow_nan=False))
        display_columns = ["estimated_wh", "output_tokens_est", "observations", "factor_source", "reaction_quality", "reaction_count", "recommended"]
        rename_columns = {"estimated_wh": "énergie estimée (Wh)", "base_energy_wh": "base/requête (Wh)",
                          "input_energy_wh": "entrée estimée (Wh)",
                          "output_energy_wh": "sortie estimée (Wh)", "output_tokens_est": "sortie estimée (tokens)", "observations": "obs. énergie",
                          "factor_source": "source facteur", "reaction_quality": "score réactions",
                          "reaction_count": "réactions train", "recommended": "recommandé"}
        if args.energy_source == "compareai" and args.energy_model == "input-output":
            display_columns[1:1] = ["base_energy_wh", "input_energy_wh", "output_energy_wh"]
        elif args.energy_source == "compareai" and args.energy_model == "power-law":
            display_columns[1:1] = ["input_exponent", "output_exponent"]
            rename_columns.update({"input_exponent": "exposant entrée",
                                   "output_exponent": "exposant sortie"})
        if args.energy_source == "mlenergy":
            display_columns[1:1] = ["config_p10_wh", "config_p90_wh"]
            rename_columns.update({"config_p10_wh": "P10 configs (Wh)",
                                   "config_p90_wh": "P90 configs (Wh)"})
        print(display[display_columns].rename(
            columns=rename_columns
        ).to_string(float_format=lambda x: f"{x:.5f}"))
    print("\nAttention : la référence est l'énergie estimée par CompareAI; ce n'est pas une mesure GPU.")
    print("Le score de réactions est un proxy subjectif, calibré sur des retours historiques; il ne garantit pas la qualité.")
    if args.energy_source == "compareai" and args.energy_model in ("input-output", "power-law"):
        print("V0.2 : énergie estimée selon une régression apprise sur la référence CompareAI; tokens d'entrée approx. caractères/4.")
    else:
        print("Ce classement omet l'énergie du prompt d'entrée et approxime ses tokens par caractères/4.")
    if args.energy_source == "mlenergy":
        print("ML.ENERGY : médiane de mesures stables lm-arena-chat, toutes configurations GPU/batch; P10-P90 décrit leur dispersion, pas un intervalle de confiance.")


if __name__ == "__main__":
    main()
