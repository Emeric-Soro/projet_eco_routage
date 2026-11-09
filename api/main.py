"""Adaptateur HTTP local : réutilise le calculateur sans refaire les estimations."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
ESTIMATOR = ROOT / "estimateur_v0.py"
COMPAREAI = ROOT / "source_données" / "compareAI" / "conversations.parquet"
REACTIONS = ROOT / "source_données" / "compareAI" / "reactions.parquet"
MLENERGY = ROOT / "source_données" / "ml-energy-v3" / "runs" / "llm.parquet"
JSON_PREFIX = "ECO_ROUTAGE_JSON:"

app = FastAPI(title="Éco-routage API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class EstimateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    energy_source: Literal["compareai", "mlenergy"] = "compareai"
    energy_model: Literal["power-law", "input-output", "output-only"] = "power-law"
    min_reactions: int = Field(default=100, ge=1, le=10000)
    reaction_threshold: float = Field(default=0.65, ge=0, le=1)
    top: int = Field(default=8, ge=1, le=20)


def parse_estimator_output(stdout: str) -> dict:
    """Extraction stricte de la dernière ligne JSON contractuelle."""
    lines = [line[len(JSON_PREFIX):] for line in stdout.splitlines()
             if line.startswith(JSON_PREFIX)]
    if not lines:
        raise ValueError("Résultat structuré absent de l'estimateur")
    result = json.loads(lines[-1])
    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise ValueError("Résultat structuré invalide")
    return result


@app.get("/api/health")
def health() -> dict:
    available = COMPAREAI.is_file() and REACTIONS.is_file()
    return {
        "status": "ready" if available else "missing_data",
        "compareai_available": COMPAREAI.is_file(),
        "reactions_available": REACTIONS.is_file(),
        "mlenergy_available": MLENERGY.is_file(),
    }


@app.post("/api/estimate")
def estimate(request: EstimateRequest) -> dict:
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Saisissez un prompt non vide.")
    if not COMPAREAI.is_file():
        raise HTTPException(
            status_code=503,
            detail="Données CompareAI manquantes. Placez conversations.parquet dans source_données/compareAI/ sur le serveur.",
        )
    if not REACTIONS.is_file():
        raise HTTPException(status_code=503, detail="Données de réactions manquantes. Placez reactions.parquet dans source_données/compareAI/.")
    if request.energy_source == "mlenergy" and not MLENERGY.is_file():
        raise HTTPException(
            status_code=503,
            detail="Données ML.ENERGY indisponibles sur le serveur.",
        )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    args = [
        sys.executable, str(ESTIMATOR), f"--prompt={prompt}",
        "--energy-source", request.energy_source,
        "--energy-model", request.energy_model,
        "--min-reactions", str(request.min_reactions),
        "--reaction-threshold", str(request.reaction_threshold),
        "--top", str(request.top), "--json-line", "--calibration-cache",
    ]
    try:
        result = subprocess.run(
            args, cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Calcul trop long. Réessayez ou contactez l'administrateur.") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Le moteur Python est indisponible.") from exc
    if result.returncode != 0:
        raise HTTPException(
            status_code=503,
            detail="L'estimation n'a pas abouti. Vérifiez les données locales et la configuration du moteur.",
        )
    try:
        return parse_estimator_output(result.stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Le moteur a renvoyé un résultat inattendu.") from exc
