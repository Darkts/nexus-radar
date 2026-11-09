# 🌴 SXM Immo Veille - Saint-Martin (97150)

Robot de veille immobilière **100 % Serverless, gratuit et autonome**, conçu pour surveiller les locations longue durée à **Saint-Martin (97150)** sous **1 200 € / mois**.

Fonctionne H24 sans laisser votre ordinateur allumé grâce à **GitHub Actions**, envoie des **notifications push instantanées sur votre téléphone** via **ntfy.sh**, et héberge un **dashboard mobile PWA** élégant sur **GitHub Pages**.

---

## 🏗️ Architecture du Projet

```
c:\SxmImmoCloud
├── .github/
│   └── workflows/
│       └── scan.yml          # GitHub Actions (Cron */15 min + Push auto)
├── data/
│   └── annonces.json         # Base de données JSON des annonces détectées
├── config.json               # Critères de recherche (prix max, exclusions)
├── scraper.py                # Script de scraping Python + Playwright
├── index.html                # Dashboard Mobile PWA (Dark Mode)
├── manifest.json             # Manifeste PWA pour installation mobile
├── sw.js                     # Service Worker PWA
├── requirements.txt          # Dépendances Python
└── README.md                 # Documentation complète
```

---

## 🚀 Fonctionnalités Clés

1. **Scraping Multi-Sources Résilient :**
   - **DOMimmo** (Portail #1 regroupant Emotion Real Estate, Alliance Immobilière SXM, Oceano, Tropic Immo, Grandchamp, IAD France, Capifrance, etc.).
   - **Emotion Real Estate** (Scan direct).
   - **4U Real Estate** (Scan direct).
   - **Leboncoin** (Scan avec gestion gracieuse de la protection anti-bot).

2. **Filtrage Intelligent des Critères :**
   - Loyer maximum : **1 200 € / mois** (ajustable dans `config.json`).
   - Exclusion automatique des locations saisonnières et touristiques (mots-clés : *saisonnière, vacances, court séjour, nuitée, /semaine, holiday, etc.*).
   - Exclusion des baux commerciaux et bureaux pour ne garder que les logements habitables.
   - Détection automatique du quartier (*Marigot, Concordia, Grand Case, Hope Estate, Baie Nettlé, etc.*).

3. **Notifications Push Instantanées sur Smartphone (ntfy.sh) :**
   - Canal privé unique : `sxm-immo-alert-97150-x9q4m2`.
   - Notification avec titre, prix, secteur, agence et photo.
   - Header `Click:` intégré pour ouvrir l'annonce en **1 tap** depuis la notification !

4. **Dashboard Mobile & PWA (index.html) :**
   - Interface moderne en Dark Mode, glassmorphism.
   - Recherche plein texte, filtres par budget (<800€, <1000€, ≤1200€) et par secteur.
   - Tri par date ou par prix.
   - Installable sur l'écran d'accueil iOS et Android comme une vraie application mobile.

5. **Automatisation Cloud H24 (scan.yml) :**
   - Tourne toutes les **15 minutes** dans le cloud GitHub (gratuit).
   - Déclenchable manuellement en 1 clic via le bouton `Run workflow`.
   - Auto-commit et auto-push de `data/annonces.json`.

---

## 📲 1. Activer les notifications sur votre téléphone

1. Téléchargez l'application gratuite **ntfy** :
   - [ntfy pour iPhone (App Store)](https://apps.apple.com/app/ntfy/id1625396347)
   - [ntfy pour Android (Google Play)](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
2. Ouvrez l'application, appuyez sur **`+`** (Ajouter un sujet).
3. Entrez le nom de votre canal unique :
   ```
   sxm-immo-alert-97150-x9q4m2
   ```
4. Appuyez sur **S'abonner**.
   *(Vous pouvez aussi tester directement depuis votre navigateur sur [https://ntfy.sh/sxm-immo-alert-97150-x9q4m2](https://ntfy.sh/sxm-immo-alert-97150-x9q4m2)).*

---

## 🌐 2. Déployer sur votre compte GitHub

Ouvrez un terminal dans le dossier `c:\SxmImmoCloud` et exécutez les commandes suivantes :

```bash
# 1. Initialiser le dépôt git
git init

# 2. Ajouter tous les fichiers
git add .

# 3. Créer le commit initial
git commit -m "feat: initial release SXM Immo Veille Bot"

# 4. Renommer la branche en main
git branch -M main

# 5. Lier votre dépôt GitHub (remplacez VOTRE_PSEUDO et NOM_DU_DEPOT)
git remote add origin https://github.com/VOTRE_PSEUDO/NOM_DU_DEPOT.git

# 6. Pousser le code
git push -u origin main
```

---

## ⚙️ 3. Configurations Essentielles sur GitHub

Deux réglages simples à activer sur votre dépôt GitHub :

### A. Autoriser GitHub Actions à sauvegarder les annonces (Écriture)
1. Rendez-vous sur votre dépôt GitHub.
2. Allez dans **Settings** > **Actions** > **General**.
3. Descendez jusqu'à la section **Workflow permissions**.
4. Sélectionnez **Read and write permissions**.
5. Cliquez sur **Save**.

### B. Activer l'Application Mobile (GitHub Pages)
1. Dans votre dépôt GitHub, allez dans **Settings** > **Pages**.
2. Dans **Build and deployment** > **Source**, choisissez **Deploy from a branch**.
3. Sous **Branch**, sélectionnez **main** et le dossier **`/ (root)`**, puis cliquez sur **Save**.
4. Votre dashboard mobile sera accessible à l'adresse :
   ```
   https://VOTRE_PSEUDO.github.io/NOM_DU_DEPOT/
   ```

---

## 🧪 Tester en Local

Pour lancer un scan manuellement depuis votre machine :
```bash
python scraper.py
```

Pour envoyer une notification de test sur votre téléphone :
```bash
python scraper.py --test-notify
```

---

## ⚙️ Personnaliser les Critères (`config.json`)

Vous pouvez ajuster les critères à tout moment dans le fichier `config.json` :
- `max_price` : Loyer mensuel maximum (défaut : `1200`).
- `exclude_commercial` : Mettre à `false` si vous souhaitez aussi surveiller les locaux commerciaux / bureaux.
- `exclude_keywords` : Mots-clés déclenchant l'exclusion.
