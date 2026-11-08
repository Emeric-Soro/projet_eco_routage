# Documentation de la V0.2.1

## Fonctionnement

Le prototype est un outil local d'estimation et de classement de modèles. Il ne génère pas de réponse, ne transmet aucun prompt et ne mesure pas directement la consommation du fournisseur.

- La longueur d'entrée est estimée par `nombre de caractères / 4`.
- La longueur de réponse est prédite depuis les réponses historiques CompareAI.
- La V0.2 ajuste les facteurs énergétiques par modèle avec deux formulations : régression additive entrée + sortie et loi de puissance entrée + sortie.
- Un filtre facultatif s'appuie sur les réactions historiques. Il sert de proxy expérimental et ne garantit pas la qualité future.

## Résultats V0.2

L'évaluation utilise un hold-out fixe de paires CompareAI, jamais vues pendant la calibration. Les deux formulations V0.2 obtiennent :

| Indicateur | Régression additive | Loi de puissance |
|---|---:|---:|
| MAE énergétique | 1,0084 Wh | 1,0084 Wh |
| Erreur relative médiane | 38,9 % | 38,9 % |
| Exactitude de routage | 90,6 % | 90,6 % |
| Signal d'entrée médian appris | 0 % de l'énergie | Exposant 0 |

Ces résultats décrivent la reproduction de la référence énergétique estimée par CompareAI. Ils ne démontrent ni une consommation physique des API ni des économies réelles. Le signal d'entrée nul indique que ces modèles ne détectent pas de contribution d'entrée dans cette référence; il ne signifie pas que les tokens d'entrée ne consomment pas d'énergie.

Les résultats de validation SweetSpot sont disponibles dans `source_données/sweetspot_llm_energy/validation_v02_resultats.csv`. Ils sont calculés sur des mesures contrôlées H100/TensorRT-LLM et restent spécifiques à ces configurations. La démo `demo_en_ligne.py` s'appuie sur ces mesures et demande uniquement les longueurs d'entrée et de sortie en tokens.

## Données nécessaires

Les fichiers CompareAI bruts ne sont pas inclus. Ils totalisent environ 4,4 Go et doivent être obtenus depuis l'espace de partage autorisé de l'équipe :

```text
source_données/compareAI/conversations.parquet
source_données/compareAI/reactions.parquet
source_données/compareAI/votes.parquet
```

`conversations.parquet` est requis pour l'estimation et l'évaluation. L'interface utilise également `reactions.parquet`; l'évaluation des filtres utilise `votes.parquet`.

L'estimateur vérifie d'abord `source_données/compareAI` dans le dépôt, puis cherche ce dossier dans ses répertoires parents. On peut choisir un autre emplacement en définissant `COMPARIA_DATA_DIR` vers le dossier contenant les trois fichiers.

Les jeux ML.ENERGY et SweetSpot fournis dans le dépôt ont leurs informations de provenance et de licence dans leurs fichiers `README.md` respectifs.

## Lancer l'application

Avec Python 3.12 (64 bits) sous Windows / PowerShell :

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -r '.\requirements.txt'
& '.\.venv\Scripts\python.exe' -m streamlit run '.\interface_web_v01.py' --server.address 127.0.0.1
```

L'application s'ouvre sur `http://localhost:8501`. Elle reste locale à l'ordinateur. Les calculs sont exécutés par `estimateur_v0.py`.

Évaluation ou estimation directe :

```powershell
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --eval
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume la sobriété numérique en trois points.'
```

## Interpréter les indicateurs

- **MAE (Wh)** : écart absolu moyen entre l'estimation et la référence CompareAI.
- **Erreur relative médiane** : écart relatif médian par rapport à cette référence.
- **Exactitude de routage** : part des paires pour lesquelles le modèle classé comme moins énergivore l'est aussi dans la référence.
- **Couverture du filtre** : part des cas où au moins un modèle satisfait le seuil de qualité choisi.
- Les votes et réactions sont des préférences historiques subjectives, pas une garantie de qualité future.

Les facteurs ML.ENERGY sont des mesures GPU agrégées de configurations différentes. Ils ne décrivent pas directement le matériel utilisé par un fournisseur d'API. La loi de puissance et la régression additive restent des modèles expérimentaux; la longueur des prompts et les réponses sont estimées à partir des données disponibles.
