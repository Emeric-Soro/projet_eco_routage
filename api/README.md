# API locale Éco-routage

Cette API FastAPI lance le moteur historique `estimateur_v0.py` avec `--json-line`. **Aucune formule du moteur n'est dupliquée**.

## Installation depuis la racine

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r api/requirements.txt
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Sous Windows : `.venv\\Scripts\\activate` puis mêmes commandes Python.

- `GET /api/health` : disponibilité des jeux de données.
- `POST /api/estimate` : `prompt`, `energy_source`, `energy_model`, `min_reactions`, `reaction_threshold`, `top`.
- Documentation interactive : http://127.0.0.1:8000/docs

**Données obligatoires** : `source_données/compareAI/conversations.parquet`. Elles ne figurent pas dans le dépôt GitHub pour des raisons de volume et de droits. Sans elles, l'API renvoie HTTP 503 avec une explication. Le choix ML.ENERGY nécessite aussi son parquet local. L'application ne contacte aucun fournisseur de LLM.

## Tests (sans données réelles)

```bash
python -m pip install -r api/requirements-dev.txt
python -m unittest discover -s api/tests -v
```

Pour un déploiement public, ajouter authentification, quotas, protection des ressources, supervision et gestion des calculs longs. La configuration actuelle vise uniquement un usage local.
