# Éco-routage des prompts — V0.2.1

Cette version présente les résultats et les outils de la V0.2. Elle n'affiche pas de comparaison avec les versions antérieures.

À partir d'un prompt, le prototype approxime les tokens d'entrée par le nombre de caractères divisé par quatre, prédit les tokens de réponse depuis l'historique CompareAI, estime l'énergie et classe les modèles. Il peut appliquer un filtre basé sur les réactions historiques. Il ne génère pas de réponse, n'appelle aucune API et ne mesure pas directement le GPU.

La V0.2 propose deux modèles énergétiques : une régression additive et une loi de puissance, tous deux ajustés sur l'entrée et la sortie. Les résultats CompareAI sont des estimations de référence. Les mesures ML.ENERGY et SweetSpot décrivent des configurations matérielles particulières.

## Résultats V0.2

Sur le hold-out CompareAI, la régression additive et la loi de puissance donnent chacune une MAE de **1,0084 Wh**, une erreur relative médiane de **38,9 %** et une exactitude de routage de **90,6 %**. La part médiane attribuée à l'entrée par la régression additive et l'exposant médian d'entrée de la loi de puissance valent **0** dans cette calibration. Cela décrit le signal détecté dans la référence CompareAI; ce n'est pas une mesure de la consommation physique des tokens d'entrée.

Sur les grilles contrôlées SweetSpot/H100, les résultats V0.2 dépendent du modèle et de la configuration. Ils sont enregistrés dans `source_données/sweetspot_llm_energy/validation_v02_resultats.csv`. Ces mesures décrivent H100 avec TensorRT-LLM et ne représentent pas directement les API cloud.

## Contenu ComparIA

Le dossier `ComparIA` comprend le notebook d'analyse et son résumé PDF. Les trois fichiers de données CompareAI (`conversations.parquet`, `reactions.parquet`, `votes.parquet`) ne sont pas dans ce dépôt : ils représentent environ 4,4 Go. GitHub bloque les fichiers de plus de 100 MiB dans Git ordinaire. Git LFS autorise des fichiers jusqu'à 2 Go avec les offres Free/Pro et 4 Go avec Team; `conversations.parquet` (2,63 Go) nécessite donc une offre compatible, en plus du quota de stockage LFS. Obtenez les données depuis l'espace autorisé de l'équipe ou son stockage partagé et placez-les ici :

```text
source_données/compareAI/conversations.parquet
source_données/compareAI/reactions.parquet
source_données/compareAI/votes.parquet
```

L'estimateur recherche aussi automatiquement un dossier `source_données/compareAI` dans les dossiers parents du dépôt. Pour indiquer un autre emplacement, définir la variable d'environnement `COMPARIA_DATA_DIR` vers le dossier contenant les trois Parquet.

## Installation (Windows / PowerShell)

Python 3.12 (64 bits) est requis. Depuis le dossier du dépôt :

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -r '.\requirements.txt'
```

Lancer l'interface locale :

```powershell
& '.\.venv\Scripts\python.exe' -m streamlit run '.\interface_web_v01.py' --server.address 127.0.0.1
```

L'interface est accessible sur `http://localhost:8501`. Pour une estimation en ligne de commande :

```powershell
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume la sobriété numérique en trois points.'
```

Évaluer les deux formulations V0.2 sur le split fixe :

```powershell
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --eval
```

## Démo publique autonome

`demo_en_ligne.py` utilise uniquement les mesures SweetSpot incluses; elle demande des longueurs en tokens et n'a besoin ni des fichiers CompareAI ni du texte du prompt. Après publication du dépôt sur GitHub, ouvrir [Streamlit Community Cloud](https://share.streamlit.io), créer une application depuis ce dépôt, choisir la branche `main` et le fichier `demo_en_ligne.py`, puis déployer.

Voir [README_estimateur_v0.md](README_estimateur_v0.md) pour la méthode et les limites, et [ComparIA/README.md](ComparIA/README.md) pour les fichiers d'analyse.
