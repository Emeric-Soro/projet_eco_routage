# Prototype V0.2 d'éco-routage

## Guide des collaborateurs : comprendre et lancer cette version

### Ce que fait le prototype

Cette version est un **outil de recherche pour comparer des estimations d'énergie de modèles**, à partir d'un prompt. Elle ne génère pas de réponse et n'envoie le prompt à aucun fournisseur.

1. Elle approxime la longueur d'entrée par `nombre de caractères / 4`.
2. Elle prédit la longueur de réponse en tokens à partir des réponses historiques CompareAI. V0.1 utilise la médiane du modèle dans sa tranche de longueur d'entrée; si cette cellule contient trop peu d'exemples, elle revient à la médiane commune de la tranche.
3. Elle estime l'énergie et classe les modèles du plus faible au plus élevé. La référence CompareAI est une estimation historique, pas une mesure physique directe du fournisseur.
4. Elle peut filtrer les modèles selon les réactions historiques. Ce score sert de proxy de qualité; il ne prédit ni ne garantit la qualité de la prochaine réponse.

Dans la barre latérale de l'interface, **CompareAI** utilise les facteurs dérivés de cette source. **ML.ENERGY** utilise des mesures GPU agrégées et ne classe que les 11 modèles reliés. Le choix du modèle énergétique propose :

- **V0.1, sortie seule** : estime l'énergie en fonction des tokens de sortie estimés.
- **V0.2, additive** : ajuste par modèle une base par requête et un coût par token d'entrée et de sortie, avec des coefficients non négatifs.
- **V0.2, loi de puissance** : ajuste par modèle une base et deux exposants, pour modéliser séparément les longueurs d'entrée et de sortie. C'est le choix initial pour CompareAI.

Les variantes V0.2 sont expérimentales. Sur le test CompareAI actuel, elles n'améliorent pas les métriques de V0.1; l'exposant médian d'entrée de la loi de puissance et la contribution médiane d'entrée de la régression additive valent zéro. Cela décrit le signal présent dans la référence CompareAI, pas la consommation physique des tokens d'entrée. SweetSpot permet une vérification distincte sur H100, avec des résultats propres à son matériel et son moteur d'inférence.

### Préparer le dossier sur Windows

Extraire `ComparIA_V0.2_partage.zip` dans un dossier accessible, puis ouvrir **PowerShell** dans ce dossier. Chaque collaborateur doit avoir Python 3.12 (64 bits) et créer son propre environnement :

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -r '.\requirements.txt'
```

L'installation des dépendances nécessite une connexion à l'index Python. L'environnement `.venv` n'est pas inclus dans l'archive.

### Ajouter les données CompareAI

L'archive ne contient pas les fichiers CompareAI (environ 4,4 Go dans la copie du projet). Vérifiez les droits d'accès et les conditions de partage; obtenez les données auprès de la source ou de l'espace autorisé par votre équipe. Placez les trois fichiers sous ces noms :

```text
source_données/
└── compareAI/
    ├── conversations.parquet
    ├── reactions.parquet
    └── votes.parquet
```

Pour les copier depuis un emplacement autorisé, remplacez le chemin d'exemple :

```powershell
New-Item -ItemType Directory -Force -Path '.\source_données\compareAI'
Copy-Item -LiteralPath 'D:\chemin_autorise\conversations.parquet' -Destination '.\source_données\compareAI\conversations.parquet'
Copy-Item -LiteralPath 'D:\chemin_autorise\reactions.parquet' -Destination '.\source_données\compareAI\reactions.parquet'
Copy-Item -LiteralPath 'D:\chemin_autorise\votes.parquet' -Destination '.\source_données\compareAI\votes.parquet'
```

Les calculs de prompt et l'évaluation nécessitent `conversations.parquet`; l'interface utilise aussi `reactions.parquet` pour le filtre de qualité. La commande `--eval` lit également `votes.parquet`. ML.ENERGY et SweetSpot sont fournis dans le paquet, avec leurs fichiers de provenance/licence.

### Lancer l'interface web

Depuis le dossier racine extrait, lancer :

```powershell
& '.\.venv\Scripts\python.exe' -m streamlit run '.\interface_web_v01.py' --server.address 127.0.0.1
```

Ouvrir l'adresse affichée par Streamlit, généralement `http://localhost:8501`. La barre latérale permet de choisir la source énergétique, la variante V0.1/V0.2 et les seuils de qualité. Dans **Estimer un prompt**, saisir le texte et cliquer **Estimer et classer les modèles**. Dans **Évaluer V0 / V0.1 / V0.2**, cliquer **Lancer l'évaluation** pour comparer les variantes sur le split fixe. Le premier calcul peut prendre quelques minutes, car les Parquet CompareAI sont lus localement.

Cette commande ouvre une application **sur l'ordinateur du collaborateur**, pas un site public. Pour arrêter Streamlit, revenir dans la fenêtre PowerShell et faire `Ctrl+C`. Pour que toute l'équipe utilise une application hébergée commune, il faudra la déployer sur un serveur approuvé avec les données autorisées; cette archive ne l'expose pas au réseau.

### Démo publique autonome

Le paquet contient aussi `demo_en_ligne.py`, une démo destinée à Streamlit Community Cloud. Elle utilise seulement les mesures SweetSpot/H100 incluses : l'utilisateur saisit les longueurs estimées en tokens (et pas le texte du prompt), puis obtient un classement énergétique des 13 modèles de SweetSpot. Elle ne contacte aucun LLM, ne requiert pas CompareAI et n'applique pas de filtre qualité. Ses résultats sont spécifiques à H100/TensorRT-LLM; ils ne représentent pas l'énergie des API commerciales.

Après publication sur GitHub, déployer `demo_en_ligne.py` sur Streamlit Community Cloud en sélectionnant le dépôt, la branche `main` et ce fichier d'entrée. Garder Python 3.12 si le choix de version apparaît. Le service fournit ensuite un lien `*.streamlit.app`. La démo publique a un périmètre différent de l'application locale complète, qui nécessite les fichiers CompareAI.

### Lancer en ligne de commande

```powershell
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume la sobriété numérique en trois points.'
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume la sobriété numérique en trois points.' --energy-model input-output
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume la sobriété numérique en trois points.' --energy-model output-only
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume la sobriété numérique en trois points.' --energy-source mlenergy
& '.\.venv\Scripts\python.exe' '.\estimateur_v0.py' --eval
& '.\.venv\Scripts\python.exe' '.\validation_sweetspot_v02.py'
```

La loi de puissance (`--energy-model power-law`) est le défaut pour CompareAI. `input-output` sélectionne la régression additive; `output-only` sélectionne la V0.1. Avec `--energy-source mlenergy`, le programme conserve le facteur mesuré par token de sortie et n'y ajoute pas un terme d'entrée appris sur CompareAI. La validation SweetSpot écrit l'audit des rapprochements et ses métriques dans `source_données\sweetspot_llm_energy\`.

### Lire les sorties et les limites

- L'énergie est affichée en Wh par requête estimée; les tokens de sortie sont prédits, pas générés.
- L'exactitude de routage dans `--eval` indique à quelle fréquence le système classe en premier le modèle ayant la plus faible référence CompareAI dans une paire test.
- Les erreurs de MAE et relatives évaluent la reproduction de la référence. Elles ne prouvent pas que les estimations sont égales à la consommation GPU réelle.
- Les mesures ML.ENERGY et SweetSpot dépendent du GPU, du moteur, du batch et des longueurs contrôlées. Elles ne décrivent pas directement l'infrastructure des API commerciales.
- Votes et réactions sont des préférences historiques partielles et subjectives, pas une évaluation garantie de la qualité future.
- Ne communiquez pas le ZIP comme s'il contenait CompareAI : les grands fichiers doivent être obtenus et partagés séparément sous les règles de votre équipe.

## Méthodes et sources reliées

Le script lit CompareAI, ne garde que les conversations à un tour, et sépare les paires de manière déterministe : 80 % calibration, 20 % test.

- **V0 globale** : `T_sortie = alpha × T_prompt`, alpha appris sur le train.
- **V0 par longueur** : médiane du nombre de tokens de sortie dans la tranche d'entrée (`1–31`, `32–127`, `128–511`, `512+`).
- **V0.1 expérimentale** : médiane par modèle et tranche d'entrée, si la calibration contient au moins 100 réponses; sinon repli sur la médiane commune de la tranche.
- **V0.2 expérimentale** : prédit l'énergie totale à partir des longueurs d'entrée et de sortie. Deux régressions sont comparées : additive (`base + c_in × entrée + c_out × sortie`) et loi de puissance (`base × (1 + entrée)^a × (1 + sortie)^b`). La loi de puissance est le défaut pour la recommandation CompareAI; la sortie seule reste sélectionnable.
- **Facteur modèle** : kWh CompareAI / tokens de sortie, calculé sur la calibration quand il existe assez d'observations.
- **Facteurs externes ML.ENERGY v3** : énergie mesurée en J/token sur GPU, filtrée sur `lm-arena-chat` et configurations stables. `--energy-source mlenergy` classe uniquement les 11 modèles reliés, à partir de la médiane de leurs configurations; cela évite de comparer leurs mesures à des facteurs CompareAI pour les autres modèles.
- **Fallback paramètres** : régression log-log entre paramètres totaux du modèle et facteur kWh/token; utilisée si le modèle a moins d'observations que `--min-observations` ou pas de facteur direct.
- **Filtre votes** : taux de préférence par modèle, conservé à titre de comparaison.
- **Filtre réactions** : score historique combinant utile/complet et absence de problème (incorrect/superficiel/consignes non suivies), calculé uniquement sur la calibration.

Pour un prompt saisi, l'entrée est approximée par `caractères / 4`; la sortie estimée vient de V0.1. Les variantes V0.2 prédisent ensuite l'énergie à partir des deux longueurs, avec des coefficients appris sur la calibration CompareAI. Ce ne sont pas des mesures GPU.

## Lancer

Dans PowerShell, depuis la racine du projet :

```powershell
& '.\.venv-v0\Scripts\python.exe' '.\interface_v0.py'
& '.\.venv-v0\Scripts\python.exe' '.\estimateur_v0.py' --eval
& '.\.venv-v0\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume les enjeux de la sobriété numérique en trois points.'
& '.\.venv-v0\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume les enjeux de la sobriété numérique en trois points.' --energy-model input-output
& '.\.venv-v0\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume les enjeux de la sobriété numérique en trois points.' --energy-model output-only
& '.\.venv-v0\Scripts\python.exe' '.\estimateur_v0.py' --prompt 'Résume les enjeux de la sobriété numérique en trois points.' --energy-source mlenergy
& '.\.venv-v0\Scripts\python.exe' '.\estimateur_v0.py' --eval --min-model-bucket-observations 100
& '.\.venv-v0\Scripts\python.exe' '.\validation_sweetspot_v01.py'
& '.\.venv-v0\Scripts\python.exe' '.\validation_sweetspot_v02.py'
```

La première commande ouvre l'interface graphique locale `interface_v0.py`.

### Interface web locale

L'interface Streamlit ouvre le démonstrateur dans un navigateur. Elle réutilise le moteur CLI et les données locales; elle ne publie pas l'application sur Internet.

Installation de la dépendance, une seule fois :

```powershell
& '.\.venv-v0\Scripts\python.exe' -m pip install -r '.\requirements_web_v01.txt'
```

Lancement, depuis la racine du projet :

```powershell
& '.\.venv-v0\Scripts\python.exe' -m streamlit run '.\interface_web_v01.py' --server.address 127.0.0.1
```

La page propose le choix du modèle V0.2 puissance, V0.2 additif ou V0.1 sortie seule, l'évaluation sur le split fixe et un rappel des limites. Les résultats identiques sont mis en cache pendant 15 minutes; le premier calcul peut rester long car l'estimateur lit les Parquet locaux.

Depuis `ComparIA_analyse` :

```powershell
& '.\.venv\Scripts\python.exe' '..\estimateur_v0.py' --eval
```

Seuils réglables : `--min-observations 100`, `--min-reactions 100`, `--reaction-threshold 0.65`. Le seuil vote se règle avec `--min-votes` et `--quality-threshold`.

## Résultats du test local

Sur environ 580 000 réponses à un tour, split 80/20 par identifiant de paire; 113 modèles avec facteurs directs et 1 modèle supplémentaire imputé par paramètres :

| Métrique | V0 globale | V0 par longueur |
|---|---:|---:|
| MAE | 3,0468 Wh | 1,2130 Wh |
| Erreur relative médiane | 84,6 % | 51,9 % |
| Ratio médian prédiction/référence | 0,22 | 1,00 |
| Exactitude du classement énergie sur paires | 87,0 % | 87,0 % |

La variante par longueur réduit la MAE d'environ 60 %. Cette évaluation historique correspond à la V0, qui utilisait une longueur de sortie commune aux modèles. La V0.1 ajoute une estimation par modèle et tranche; `--eval` compare désormais ces variantes et affiche aussi l'erreur de prédiction du nombre de tokens de sortie. Le seuil de repli est réglable avec `--min-model-bucket-observations`.

### Résultats V0.2

Sur le même hold-out, les deux nouvelles régressions obtiennent la même MAE et le même classement que V0.1 : **1,0084 Wh**, erreur relative médiane **38,9 %**, exactitude de routage **90,6 %**. La part médiane attribuée à l'entrée par la régression additive et l'exposant médian d'entrée de la loi de puissance sont **nuls**. Cela signifie que les estimations CompareAI apprises dans ce jeu n'apportent pas de signal d'énergie d'entrée détectable par ces modèles; cela ne prouve pas que l'entrée ne consomme pas d'énergie physique.

SweetSpot montre un signal distinct. Dans un hold-out interne à ses mesures H100, la régression puissance entrée/sortie réduit l'erreur relative médiane sur chacun des trois modèles rapprochés (environ **32–34 %**, contre **49–63 %** pour une loi de base + sortie). La MAE, elle, est plus élevée pour cette loi de puissance dans les trois cas. Ces résultats sur une petite grille contrôlée ne suffisent donc pas à remplacer la calibration CompareAI. La loi de puissance appliquée aux facteurs CompareAI n'améliore pas le hold-out CompareAI : ses métriques restent identiques à V0.1 et son exposant d'entrée médian vaut 0. La nouvelle interface la présente donc comme une expérimentation, pas comme un gain démontré.

### Résultats V0.1

Split test fixe, modèle et tranche appris uniquement sur les paires de calibration; seuil de repli de 100 réponses par modèle et tranche :

| Métrique | V0 par longueur | V0.1 modèle × longueur |
|---|---:|---:|
| MAE énergie vs référence CompareAI | 1,2130 Wh | 1,0084 Wh |
| Erreur relative médiane énergie | 51,9 % | 38,9 % |
| MAE nombre de tokens de sortie | 497,9 | 412,7 |
| Exactitude du classement sur paires | 87,0 % | 90,6 % |
| Couverture d'une médiane modèle × tranche | — | 99,1 % |

Avec les facteurs ML.ENERGY, la MAE passe de 1,2310 Wh à 1,0286 Wh, l'erreur relative médiane de 57,5 % à 45,1 %, et l'exactitude du classement de 86,2 % à 88,5 %. Ces métriques mesurent la reproduction de CompareAI; elles ne démontrent pas l'énergie physique du fournisseur.

### Facteur de repli taille modèle

Validation descriptive leave-one-model-out sur les modèles assez observés : erreur relative médiane d'environ **37,6 %** avec la taille totale, contre **87,4 %** avec le facteur médian global. Pour l'instant, un modèle parmi les candidats utilise ce fallback dans le calcul du prompt.

### Filtre de qualité

Les indicateurs ci-dessous utilisent les sorties V0.1 sur le split fixe. Avec le filtre de votes, 23 modèles passent le seuil; la couverture est de **42,5 %** des paires test éligibles, l'accord avec la préférence historique est de **63,7 %** sur les cas routés, et l'exactitude énergie est de **79,3 %**. L'économie moyenne estimée par rapport au modèle préféré par les votes est de **−0,0183 Wh** : ce filtre n'assure donc pas une économie moyenne.

Avec le filtre de réactions, 49 modèles passent le seuil. Sur 3 455 paires test avec un retour sur les deux réponses, la couverture est de **67,9 %**. Le score moyen de la réponse choisie est de **0,654**; elle égale ou dépasse le score de l'autre réponse dans **78,3 %** des paires. Son énergie estimée est en moyenne **0,6092 Wh plus basse** que celle de l'autre réponse. Ces retours sont subjectifs, et le score composite est une convention expérimentale, pas une mesure académique de qualité.

Avec le classement par défaut V0.2 puissance, l'accord du filtre de votes devient **63,8 %** et l'écart moyen avec le choix utilisateur est de **−0,0198 Wh**; cela reste une légère hausse d'énergie estimée, pas une économie.

### Exemple prompt

Pour le prompt de démonstration, longueur estimée 15 tokens et sortie de classe estimée 539 tokens. Le filtre de réactions recommande `gemma-4-26b-a4b-it` à environ `0,04544 Wh`; la valeur vient du facteur CompareAI observé et son score historique de réaction est `0,655` sur 105 réactions train.

### Intégration ML.ENERGY v3

Le Parquet léger est enregistré dans `source_données/ml-energy-v3/runs/llm.parquet` (231 706 octets). Il contient 1 138 configurations LLM, dont 838 stables. Le rapprochement avec CompareAI relie 11 modèles de la tâche `lm-arena-chat`, sur 202 configurations stables. Les facteurs calculés et leurs dispersions sont dans [facteurs_chat_compareai.csv](source_données/ml-energy-v3/facteurs_chat_compareai.csv); les noms, IDs et niveau de correspondance restent dans [liens_modeles_compareai_ml_energy.csv](liens_modeles_compareai_ml_energy.csv).

La médiane agrège des GPU, nombres de GPU et tailles de batch différents; les P10–P90 représentent la dispersion de configurations, pas un intervalle de confiance. `--eval` affiche côte à côte le baseline CompareAI et l'hybride, qui remplace les facteurs des 11 modèles reliés et conserve le baseline ailleurs. Face à la référence estimée CompareAI, cette variante **ne l'améliore pas** : pour V0 par longueur, MAE 1,2310 Wh contre 1,2130 Wh, erreur relative médiane 57,5 % contre 51,9 %, et exactitude de routage 86,2 % contre 87,0 %. Pour une recommandation `--energy-source mlenergy`, le script classe uniquement les 11 modèles mesurés. C'est une estimation indépendante fondée sur des mesures GPU; la configuration du fournisseur réel est inconnue.

### Validation indépendante SweetSpot

`source_données/sweetspot_llm_energy/dataset.zip` contient des mesures sous licence CC BY 4.0 pour 13 modèles sur H100 avec TensorRT-LLM. La validation lit la grille de 49 longueurs entrée/sortie contrôlées de Llama 3.1 8B Instruct. Elle applique le facteur CompareAI calibré au nombre exact de tokens de sortie, afin d'isoler le facteur énergétique. Les mesures SweetSpot restent séparées des références CompareAI, car elles décrivent un matériel et un moteur d'inférence précis.

Pour ces 49 configurations, le facteur CompareAI calibré est de 0,3209 J/token de sortie; la médiane SweetSpot est de 0,1045 J/token. La prédiction médiane par requête est 3,07 fois la mesure et la corrélation de rang entre configurations vaut 0,841. Le coût mesuré par token de sortie augmente avec la longueur d'entrée (médiane 0,0481 J à 64 tokens, 0,3121 J à 4096 tokens), alors que le facteur CompareAI est constant. Ce contrôle indique une dépendance au contexte matériel et à la longueur d'entrée; il ne valide pas directement l'énergie des API cloud.

L'audit complet des 13 tables trouve **3 rapprochements documentés** : Llama 3.1 8B Instruct ↔ `llama-3.1-8b` (suffixe instruct absent côté CompareAI), Gemma 2 9B IT (nom concordant), et Qwen2 7B ↔ `qwen2-7b-instruct` (suffixe instruct différent). Les 10 autres modèles n'ont pas de version CompareAI suffisamment concordante dans le jeu local. La table de correspondance et les résultats hold-out sont enregistrés dans `source_données/sweetspot_llm_energy/rapprochement_sweetspot_compareai.csv` et `validation_v02_resultats.csv`.

## Limites

1. CompareAI fournit une estimation énergétique, pas une mesure GPU indépendante.
2. L'erreur relative médiane de V0.1 reste élevée (38,9 %); les résultats ne démontrent pas d'économies réelles.
3. Le fallback par paramètres risque de reproduire une formule déjà utilisée par CompareAI; le LOO prédit une référence, pas une mesure physique.
4. Le score de réaction est subjectif; la couverture reste partielle et le seuil choisi influe le compromis énergie/qualité.
5. La longueur de tokens est estimée par caractères/4, les tranches sont fixes et la catégorie/tâche n'est pas utilisée.
6. La régression V0.2 ne détecte pas de coût d'entrée supplémentaire dans la référence CompareAI; sa généralisation physique reste non validée.
7. Le split reste figé par hash de la paire pour comparer les variantes.
8. Les facteurs ML.ENERGY sont des mesures physiques mais dépendent fortement du GPU, de la précision et de la charge (batch); ils ne décrivent pas directement le centre de données du fournisseur CompareAI.
