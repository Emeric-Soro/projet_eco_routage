# Analyse ComparIA

Ce dossier regroupe les livrables d'analyse ComparIA associés au projet :

- `analyse_comparia.ipynb` : notebook d'analyse;
- `resume_synthetique_analyse_comparia.pdf` : résumé des résultats de l'analyse.

Les données brutes `conversations.parquet`, `reactions.parquet` et `votes.parquet` ne sont pas incluses. Elles totalisent environ 4,4 Go et `conversations.parquet` fait environ 2,63 Go. GitHub bloque les fichiers de plus de 100 MiB dans Git ordinaire; Git LFS autorise jusqu'à 2 Go par fichier avec les offres Free/Pro et 4 Go avec Team. Pour inclure le Parquet de conversations dans Git LFS, il faut donc une offre compatible et assez de quota de stockage. Sinon, obtenir les données depuis l'espace de partage autorisé de l'équipe; ne pas les ajouter à Git sous forme de fichiers ordinaires.
