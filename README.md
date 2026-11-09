# Éco-routage — V0.2

Prototype local pour **estimer l'énergie d'un prompt** selon différents modèles de langage, les classer du plus sobre au plus énergivore, et recommander un modèle (éventuellement filtré par réactions historiques).

À partir d'un prompt, le moteur approxime les tokens d'entrée (caractères ÷ 4), prédit les tokens de sortie via l'historique CompareAI, estime l'énergie et classe les modèles. Il **ne génère aucune réponse**, n'appelle aucune API LLM et ne mesure pas le GPU en direct.

L'interface principale est une application **React + Vite**, branchée sur une **API FastAPI** qui lance `estimateur_v0.py`.

## Prérequis

- **Python ≥ 3.11** (recommandé : 3.12 ou 3.13) — `duckdb==2.0.0` refuse les versions plus anciennes
- **Node.js** (npm) pour le frontend
- Les fichiers CompareAI (≈ 4,4 Go), **non inclus** dans le dépôt

## 1. Données locales (obligatoires pour calculer)

Placez les Parquet CompareAI ici :

```text
source_données/compareAI/conversations.parquet
source_données/compareAI/reactions.parquet
source_données/compareAI/votes.parquet   # utile pour --eval
```

Sans `conversations.parquet` et `reactions.parquet`, l'API indique `missing_data` et l'estimation reste bloquée.

Optionnel : `source_données/ml-energy-v3/runs/llm.parquet` pour la source **ML.ENERGY**.

Si les fichiers sont déjà ailleurs (ex. un dossier `ComparIA_V0_partage`), vous pouvez créer des liens symboliques plutôt que les recopier :

```bash
mkdir -p source_données/compareAI
ln -sf "$(pwd)/../ComparIA_V0_partage/source_données/compareAI/conversations.parquet" source_données/compareAI/
ln -sf "$(pwd)/../ComparIA_V0_partage/source_données/compareAI/reactions.parquet" source_données/compareAI/
ln -sf "$(pwd)/../ComparIA_V0_partage/source_données/compareAI/votes.parquet" source_données/compareAI/
```

## 2. Environnement Python

```bash
# macOS / Linux — utiliser un Python ≥ 3.11 (ex. Homebrew)
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r api/requirements.txt
```

Windows (PowerShell) :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r api/requirements.txt
```

## 3. Configurer le frontend

```bash
cd frontend
npm install
cp .env.example .env
```

Le fichier `frontend/.env` doit pointer vers l'API :

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Sans ce fichier, le navigateur peut appeler le mauvais hôte et afficher « API Python inaccessible ». Vite dispose aussi d'un proxy `/api` → `127.0.0.1:8000` (voir `frontend/vite.config.ts`).

Retournez ensuite à la racine du dépôt : `cd ..`

## 4. Lancer frontend + backend

### Option A — script unique (recommandé)

```bash
./start.sh
```

- Frontend : http://127.0.0.1:5173  
- API : http://127.0.0.1:8000 (docs interactives : `/docs`)  
- `Ctrl+C` arrête les deux.

### Option B — deux terminaux

```bash
# Terminal 1 — API
source .venv/bin/activate
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — interface
cd frontend
npm run dev
```

Dans l'interface, le voyant sous le formulaire doit indiquer **« Moteur disponible — calcul sur données locales. »** Avant de lancer une estimation.

## Vérifier que tout répond

```bash
curl -s http://127.0.0.1:8000/api/health
# attendu : "status":"ready", compareai_available et reactions_available à true
```

## Documentation dans l'interface

Le bouton **Documentation** ouvre :

- le guide d'utilisation (`frontend/public/docs/Guide_utilisation_ecoroutage.pdf`)
- la documentation technique V0.2 (`frontend/public/docs/Documentation_V0.2_ecoroutage.pdf`)

## Ligne de commande (sans interface)

```bash
source .venv/bin/activate
python estimateur_v0.py --prompt 'Résume la sobriété numérique en trois points.'
python estimateur_v0.py --eval
```

## Résultats V0.2 (rappel)

Sur le hold-out CompareAI, la régression additive et la loi de puissance donnent chacune une MAE de **1,0084 Wh**, une erreur relative médiane de **38,9 %** et une exactitude de routage de **90,6 %**. Les détails et limites sont dans [README_estimateur_v0.md](README_estimateur_v0.md).

## Dépannage rapide

| Symptôme | Cause fréquente | Action |
|---|---|---|
| `No matching distribution found for duckdb==2.0.0` | Python &lt; 3.11 | Recréer le `.venv` avec Python 3.12/3.13 |
| « API Python inaccessible » | API non démarrée ou `.env` manquant | Lancer uvicorn / `./start.sh`, vérifier `frontend/.env` |
| « Jeu de données CompareAI manquant » | Parquet absents ou liens cassés | Vérifier `source_données/compareAI/*.parquet` |
| « L'estimation n'a pas abouti… » | Moteur / estimateur incompatible | Utiliser l'`estimateur_v0.py` fourni (avec `--json-line`) et relancer |

## Contenu du dépôt

- `estimateur_v0.py` — moteur de calcul
- `api/` — API FastAPI
- `frontend/` — interface React
- `start.sh` — lancement simultané API + frontend
- `demo_en_ligne.py` — démo Streamlit autonome (SweetSpot uniquement, sans CompareAI)
