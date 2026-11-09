# Éco-routage — simulateur énergétique

Interface React + TypeScript + Vite, avec une disposition de bureau en deux colonnes : **résultats et détail des calculs à gauche, prompt et paramètres à droite**. Sur mobile, le formulaire passe avant les résultats.

## Lancer l'application (deux terminaux)

Depuis la racine du dépôt, installer les dépendances de l'estimateur ET de l'API Python :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r api/requirements.txt
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Sur Windows, activer l'environnement avec `.venv\\Scripts\\activate`.

Dans un autre terminal :

```bash
cd frontend
npm install
npm run dev
```

Ouvrir http://localhost:5173. Si votre API utilise un port différent, renseignez `VITE_API_BASE_URL` dans `frontend/.env` en vous inspirant de `.env.example`.

## Prérequis pour obtenir des chiffres réels

Le moteur requiert impérativement `source_données/compareAI/conversations.parquet`. Ce jeu de données n'est **pas** inclus dans GitHub. La source ML.ENERGY demande `source_données/ml-energy-v3/runs/llm.parquet`, en plus des données CompareAI nécessaires à la calibration. Sans fichier CompareAI, l'interface affiche l'absence des données et désactive le calcul ; elle ne fabrique pas de chiffres.

L'API ne fait **pas** d'appels à un fournisseur de modèles IA. Elle lance `estimateur_v0.py` en local et lit sa sortie JSON optionnelle (`--json-line`). Le processus peut être coûteux sur les premières requêtes et le bouton « Annuler » interrompt l'attente du navigateur, sans forcément arrêter le processus déjà lancé sur le serveur.

## Comprendre l'interface

- **Colonne gauche** : état vide explicite, recommandation calculée, énergie estimée en Wh, nombre de modèles évalués, histogramme relatif et détails d'une ligne au clic. La recommandation et le minimum énergétique peuvent différer si le filtre de réactions s'applique.
- **Colonne droite** : prompt, approximation de tokens d'entrée, source (CompareAI / ML.ENERGY), variante énergétique, seuils de réactions, bouton d'estimation et états connexion/chargement/erreur.
- **Aide à la décision** : minimum énergétique et recommandation après filtre historique affichés séparément ; surcoût estimé en Wh et en % relatif au minimum (indéfini si le minimum vaut zéro).
- **Visualisations** : classement triable (énergie ou nom), barres proportionnelles à la valeur maximale affichée, comparaison libre de deux modèles à prompt/source/méthode constants.
- **Détail du calcul** : nombre d'observations, tokens de sortie estimés, score de réaction historique ; ventilation en base/entrée/sortie uniquement pour la méthode V0.2 additive. La variante puissance n'est pas une somme additive et ML.ENERGY montre la dispersion entre configurations quand disponible.

**Attention :** le plus petit estimateur énergétique peut être différent du modèle choisi par le filtre de réactions. Un surcoût affiché n'est pas une dépense mesurée et ne garantit pas une réponse meilleure.
- **Méthodologie** : résultats estimés, score de qualité historique, contraintes de comparaison entre les sources et configurations GPU.

## Structure

```text
frontend/
  src/
    App.tsx
    components/ResultWorkspace.tsx
    services/estimation.ts
    types/estimation.ts
    styles/globals.css
```


## Sprint performance et export (novembre 2026)

- **Cache de calibration** : l'API ajoute `--calibration-cache` au moteur. Après la première exécution, les facteurs de modèle et les statistiques de réactions sont réutilisés pour les prompts suivants. Le cache est recalculé lorsque les fichiers Parquet, le code de l'estimateur ou les paramètres concernés changent. Les fichiers sont enregistrés dans `.cache/eco-routage/` (ignoré par Git). Supprimer ce dossier pour forcer un nouveau calcul. Ne jamais y placer de fichiers pickle téléchargés ou non fiables.
- **Premier calcul** : il nécessite toujours la lecture et l'ajustement des grandes données CompareAI ; il peut rester long. Le cache améliore les calculs suivants mais ne garantit pas une réponse instantanée et n'est pas un cache de réponse LLM.
- **Export CSV** : le bouton « Exporter CSV » apparaît après le calcul. Il exporte **les modèles retournés et affichés**, leurs valeurs brutes en Wh, les métriques historiques et la méthode/sources de calcul. Le nombre total de candidats figure dans une colonne distincte. Le CSV UTF-8 (BOM, séparateur `;`) n'inclut pas le prompt. Les champs texte sont échappés pour éviter les formules injectées dans un tableur.
- **Validation navigateur** : la CI exécute Playwright avec Chromium sur écrans ordinateur et mobile, en utilisant des réponses API **simulées exclusivement dans les tests**. Les captures d'écran et traces sont enregistrées comme artefacts GitHub Actions pendant 7 jours. Ces simulations ne sont jamais affichées dans l'application de production.

```bash
cd frontend
npm test           # tests unitaires Vitest
npm run test:e2e   # Playwright (nécessite : npx playwright install chromium)
```

La seule validation complète du calcul réel nécessite les données CompareAI locales non publiques ; aucun test d'intégration sur ce jeu de données n'est effectué en CI.

## Sprint historique et comparaisons sauvegardées

Le bouton **Historique** en haut de l'interface ouvre le journal local des **20 dernières estimations réussies**. L'utilisateur peut :
- rouvrir un résultat précédent et ses paramètres sans relancer l'API ;
- enregistrer jusqu'à cinq comparaisons entre deux modèles par analyse, puis les rouvrir ;
- supprimer une comparaison, une analyse ou l'intégralité de l'historique.

**Confidentialité :** par défaut, l'historique est uniquement conservé en mémoire pendant la session de cet onglet. Aucun prompt n'est enregistré dans le stockage durable du navigateur sans activation volontaire de « Conserver mes analyses sur cet appareil ». Une fois activée, cette option écrit les prompts, paramètres et résultats **en clair dans le localStorage du navigateur**. Ne l'utilisez pas sur un ordinateur partagé pour des prompts sensibles. Désactiver l'option efface les données sauvegardées de cet espace local ; l'historique de session reste disponible jusqu'au rechargement. Les données ne sont pas synchronisées entre navigateurs ou appareils.

**Reproductibilité :** l'historique garde un instantané des résultats du moteur au moment de l'estimation. Les données de référence ou la calibration peuvent avoir changé depuis ; rouvrir une analyse est une consultation, **pas un nouveau calcul**. Relancez l'estimation pour actualiser ses valeurs.

Les tests Playwright vérifient aussi la sauvegarde opt-in, la restauration, la suppression de comparaisons et les interactions au clavier.

## Vérifications

```bash
cd frontend
npm run typecheck
npm test
npm run build
cd ..
python -m pip install -r api/requirements-dev.txt
python -m unittest discover -s api/tests -v
```

Le workflow GitHub Actions `.github/workflows/frontend-api.yml` automatise la compilation et les tests du contrat API. Les tests HTTP sont simulés sans données privées.

## Documentation intégrée

Le bouton **Documentation** ouvre `public/docs/Guide_utilisation_ecoroutage.pdf` (guide d'utilisation) et `public/docs/Documentation_V0.2_ecoroutage.pdf` (documentation technique).

Le guide est généré depuis `scripts/guide/guide.html`. Pour le mettre à jour après une évolution de l'interface, API et front démarrés :

```bash
cd frontend
node scripts/guide/capture.mjs    # captures d'écran réelles dans scripts/guide/screens/
node scripts/guide/build-pdf.mjs  # régénère public/docs/Guide_utilisation_ecoroutage.pdf
```

Si Playwright ne trouve pas son navigateur, indiquez un Chromium existant via la variable `GUIDE_CHROMIUM`.

## Guides ECC consultés

Principes adaptés de `frontend-design-direction`, `design-system`, `frontend-a11y`, `frontend-patterns`, `react-patterns`, `api-design`, `react-testing`, `dashboard-builder` dans le dépôt [affaan-m/ECC](https://github.com/affaan-m/ECC). Aucun script externe ECC n'est exécuté.
