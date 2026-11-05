# ML.ENERGY Benchmark V3 — données utilisées

- Source officielle : https://huggingface.co/datasets/ml-energy/benchmark-v3
- Publication citée par la fiche du jeu : *The ML.ENERGY Benchmark: Toward Automated Inference Energy Measurement and Optimization*, NeurIPS Datasets and Benchmarks 2025.
- Licence affichée par le dépôt : Apache-2.0.
- Le dépôt indique que l'accès aux fichiers nécessite d'accepter ses conditions d'accès et de partager des informations de compte Hugging Face. Chaque collaborateur doit vérifier et accepter ces conditions auprès de la source.
- Copie partielle utilisée ici : `runs/llm.parquet` (environ 232 Ko), limitée aux résultats LLM nécessaires au prototype; ce n'est pas le jeu complet.

Le code conserve les configurations stables de la tâche `lm-arena-chat`, les agrège en médianes par modèle relié, puis utilise les facteurs pour une recommandation expérimentale. Les GPU, nombres de GPU et batchs sont hétérogènes : les valeurs ne décrivent pas l'infrastructure d'un fournisseur commercial.

Voir aussi `facteurs_chat_compareai.csv` et, à la racine du projet, `liens_modeles_compareai_ml_energy.csv` pour les facteurs et les correspondances de noms.
