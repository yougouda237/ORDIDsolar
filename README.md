# ORDIDSOLARCALC

ORDIDSOLARCALC est une application Streamlit de démonstration pour la gestion de projets de solarisation à Maroua (Cameroun).

Contenu ajouté sur la branche feat/ordidsolar-app :
- app.py — application Streamlit (auth demo, dashboard, CRUD dossiers, monitoring simulé, uploads)
- Dockerfile — image pour exécuter l'application
- requirements.txt — dépendances
- .dockerignore — éléments à exclure de l'image
- README.md — (ce fichier)

Exécution locale
-----------------
1. Créer et activer un environnement virtuel (recommandé)

   python3 -m venv .venv
   source .venv/bin/activate   # Linux / macOS
   .\.venv\Scripts\activate  # Windows (PowerShell)

2. Installer les dépendances

   pip install -r requirements.txt

3. Lancer l'application

   streamlit run app.py

L'application sera disponible sur http://localhost:8501

Exécution avec Docker
---------------------
1. Construire l'image

   docker build -t ordidsolarcalc:latest .

2. Lancer le conteneur (monter uploads et la BD pour persistance)

   docker run -it --rm -p 8501:8501 \
     -v "$(pwd)/uploads:/app/uploads" \
     -v "$(pwd)/ordidsolar.db:/app/ordidsolar.db" \
     ordidsolarcalc:latest

Notes de sécurité / production
------------------------------
- Les comptes fournis dans l'app sont uniquement pour démonstration. Remplacez le mécanisme d'authentification par une solution sécurisée en production (stockage dans la BD, hashing avec bcrypt/argon2, salage, politiques de mot de passe, gestion sessions).
- Ne conservez pas ordidsolar.db et uploads dans l'image Docker ; utilisez des volumes, un stockage externe, ou une base de données dédiée.
- Ajoutez un reverse proxy (nginx/Caddy) pour TLS et protections supplémentaires.
- Pinner les versions de dépendances et exécutez des scans de vulnérabilités avant déploiement.

Ressources
---------
- Branche : feat/ordidsolar-app
  https://github.com/yougouda237/ORDIDsolar/tree/feat%2Fordidsolar-app
- Commit initial :
  https://github.com/yougouda237/ORDIDsolar/commit/8a5b434065877444cd539c1bf2a160a91ab26ee7

Prochaines étapes possibles (je peux m'en charger si vous confirmez) :
- Créer une Pull Request depuis feat/ordidsolar-app vers la branche par défaut
- Ajouter un workflow GitHub Actions pour builder l'image et exécuter tests
- Remplacer la gestion d'utilisateurs par une table users + bcrypt/argon2
