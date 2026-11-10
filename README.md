# 🛰️ NEXUS RADAR V6 - Architecture 100% Dynamique (Zéro Donnée Fictive)

Hub Personnel **100 % Serverless, gratuit et autonome**, doté d'une architecture de **scraping en direct en temps réel** (Zéro fausse annonce, Zéro domaine mort), d'une barre de progression animée et structuré en **2 Univers Dédiés** :

---

## 🚀 Nouveautés Majeures V6 (Scraping Dynamique 100% Réel)

### 1. ⚡ Moteur de Scraping Direct en Temps Réel (Zéro Fausse Donnée)
* **Suppression intégrale des données simulées :** Aucune fausse annonce synthétique. Chaque bien affiché provient directement d'une requête réelle.
* **Scraping Client en direct (1-3 secondes dans l'app) :**
  * **Saint-Martin (97150) :** Connexion directe à l'API REST officielle **DOMimmo Saint-Martin** (`offers?id_com_pays=SMT&id_di_ad_cat=...`). Récupération des vrais prix, vrais titres, photos HD sur Blob Storage Keldom, vraies agences (Alliance Immo, Emotion, IAD...) et URL directes testées.
  * **France (Nancy, Metz, Lyon, Paris, Nice, etc.) :** Résolution dynamique des zones via l'API suggest Bien'ici (`suggest.json?q=...`) et aspiration en direct via l'API REST Bien'ici (`realEstateAds.json`).
  * **Géocodage :** Utilisation directe de `api-adresse.data.gouv.fr` (CORS ouvert, lat/lon exactes et code postal).
* **Barre de progression animée (0% à 100%) :** Visualisation en temps réel des étapes du scan ("🔄 Géocodage...", "🏢 Scraping des portails...", "⚡ Intégration des annonces réelles...").

### 2. 🎭 Deep Scraping Cloud (GitHub Actions + Playwright)
* En parallèle de la recherche instantanée dans l'app, si votre Token GitHub est configuré dans `🔔 Réglages`, l'application déclenche automatiquement le workflow `scan.yml` avec vos critères précis (`city`, `transaction_type`, `max_budget`, `rooms`, `min_surface`).
* Le robot Python tourne en arrière-plan sur les serveurs de GitHub, met à jour `data/annonces.json` et envoie une alerte push prioritaire sur votre téléphone via `ntfy.sh`.

### 3. 🛡️ Purge Totale des Liens Morts & Validateur Strict
* **Zéro domaine parqué :** Bannissement strict de `4urealestate.com`, `hugedomains.com`, `sedo.com`, `godaddy.com`, etc.
* **Portails officiels uniquement :** Redirection et validation systématique vers **DOMimmo**, **Bien'ici**, **Leboncoin**, **SeLoger**, **Google Flights**, **Trainline**.

### 4. ✈️ Recherche Voyage Complète & Directe (Nancy Hub)
* 🛫 Ville de départ (Nancy Hub, Paris CDG/ORY, Luxembourg Findel, Bâle-Mulhouse)
* 🛬 Destination cible (Saisie libre ou suggestions : SXM, Italie, New York...)
* 📅 Dates Départ & Retour + Option Dates flexibles ±3 jours
* 💰 Budget Max (€) avec calcul du coût réel (Vol + Train d'acheminement + Hôtel)
* Bouton **[ 🔍 Trouver & Scraper les offres ]** avec barre de progression et deep links pré-filtrés.

### 5. 🎛️ Radars Cloud Séparés avec Lancement Immédiat
* Formulaires distincts pour **Radar Immo** et **Radar Voyage**.
* À chaque ajout de radar, l'application synchronise `config.json` via l'API GitHub **ET déclenche immédiatement un premier scan réel** sur ces critères.
* Liste interactive des radars actifs avec boutons **[ ⚡ Lancer le Scan ]** et **[ 🗑️ Supprimer ]**.

---

## 📱 Accès Direct & Notifications

- **Application Web & PWA :** [https://darkts.github.io/nexus-radar/](https://darkts.github.io/nexus-radar/)
- **Canal Push ntfy :** `https://ntfy.sh/sxm-immo-alert-97150-x9q4m2`
- **Canal Mobile ntfy.sh :** `sxm-immo-alert-97150-x9q4m2`
- **Sécurité :** Verrouillage par code PIN local, zéro secret stocké dans le dépôt (PAT GitHub uniquement dans le `localStorage` de votre navigateur).
