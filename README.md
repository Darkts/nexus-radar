# 🛰️ NEXUS RADAR V5.1 - Hub Personnel Multi-Radars (Serverless & Autonome)

Hub Personnel **100 % Serverless, gratuit et autonome**, doté d'une veille dynamique par critères, d'un moteur de validation strict des URL et structuré en **2 Univers Dédiés** :

---

## 🚀 Nouveautés & Corrections Majeures V5.1

### 1. ⚡ Veille Dynamique par Critères & Bouton "Lancer un Scan Live"
* **Fin des résultats statiques restreints :** Plus jamais de blocage sur 1 seul résultat.
* **Critères complets dans la barre Immo :**
  * Sélecteur de transaction (*Tous / Louer / Acheter*).
  * Champ **💰 Budget Max (€)** et **📐 Surface min (m²)** directement dans la barre de filtres.
  * Typologies (*Studio, T2, T3+, Maison/Villa*) et Commodités (*Vue Mer, Terrasse, Piscine, Parking*).
* **Bouton [ ⚡ Lancer un Scan Live sur ces critères ] :**
  * **Action immédiate (0 sec) :** Affichage instantané des opportunités correspondantes + génération d'une barre de **Portails Officiels Directs** pré-filtrés en direct (Leboncoin, SeLoger, Bien'ici, DOMimmo, Orpi).
  * **Action Cloud (GitHub Actions) :** Envoi des critères saisis (`city`, `transaction_type`, `max_budget`, `rooms`, `min_surface`) au workflow `scan.yml` via l'API GitHub pour enrichir `data/annonces.json` et notifier en push sur votre téléphone.
* **47 Pépites réelles pré-chargées et vérifiées :**
  * 10 à Nancy (mix Achat / Location, Stanislas, Vieille Ville, Léopold, Saurupt, Blandan, Rives de Meurthe).
  * 10 à Saint-Martin 97150 (Baie Nettlé, Grand Case, Marigot, Orient Bay, Anse Marcel, Cul-de-Sac, Hope Estate).
  * 11 dans les grandes métropoles (Paris, Lyon, Nice, Marseille, Bordeaux, Strasbourg, Alicante/Malaga).
  * 16 voyages & billets cassés (Nancy Hub, TGV direct dès 10€/16€, EuroAirport BSL, LUX Findel, Paris CDG/ORY).

### 2. 🛡️ Élimination Totale des Domaines Morts & Liens 100% Vérifiés
* **Zéro domaine parqué / Zéro nom d'agence inventé :** Bannissement absolu de `4urealestate.com`, `island-immo.com`, `sxmcapri.com` ou de pages de vente de domaines (HugeDomains, Sedo, GoDaddy).
* **Portails officiels uniquement :** Redirection et validation systématique vers **DOMimmo**, **Leboncoin**, **SeLoger**, **Bien'ici**, **Orpi**, **Foncia**, **Emotion Real Estate**, **Google Flights**, **Trainline**.
* **Contrôle HTTP intégré :** Interception automatique de tout lien inaccessible ou parqué remplacé par le deep-link officiel pré-filtré.

### 3. ✈️ Moteur de Recherche Voyage Complet (Nancy Hub)
* Remplacement complet de la barre par un véritable moteur de recherche :
  * 🛫 **Ville de Départ** (par défaut : *"Nancy Hub"*, modifiable avec raccourcis *Paris CDG/ORY, Luxembourg Findel LUX, Bâle-Mulhouse BSL*).
  * 🛬 **Destination d'Arrivée** (Saisie libre de ville/pays ou raccourcis *🌍 Partout / Fais-moi rêver, Saint-Martin SXM, Guadeloupe, Italie, New York, Espagne, Paris TGV*).
  * 📅 **Dates de Voyage** : Sélecteur précis **Départ & Retour** + interrupteur **[🔄 Dates flexibles ±3 jours (Meilleurs prix)]**.
  * 💰 **Budget Max Tout Compris (€)** : Slider et champ numérique interactifs calculant en temps réel le coût Vol + Train + Hôtel vérifié.
  * Bouton **[ 🔍 Trouver & Scraper les offres ]** : Filtrage en direct et liens 1-clic vers Google Flights et Trainline.

### 4. 🎛️ Séparation Stricte des Radars (Immo vs Voyage)
* **Formulaire Radar Immobilier :**
  1. Secteur / Ville à surveiller
  2. Transaction : Location ou Achat
  3. Typologie & Surface min (m²)
  4. Budget Max (€)
  * Bouton *✨ Pré-remplir avec mes likes récents*
  * Bouton *➕ Enregistrer & Activer ce Radar Immo*
* **Formulaire Radar Voyage :**
  1. Ville de départ
  2. Destination cible (ou "Partout / Soleil / Europe / Caraïbes")
  3. Période / Dates ou Durée + Option dates flexibles
  4. Budget Max par personne (€)
  5. Type d'alerte : *Séjour Vol + Hôtel tout compris*, *Vol sec erreur de prix*, ou *Train direct*
  * Bouton *➕ Enregistrer & Activer ce Radar Voyage*
* **Mes Radars Actifs Cloud H24 :**
  * Section **🏠 Radars Immobiliers Actifs** et Section **✈️ Radars Voyage Actifs** listant chaque robot configuré avec bouton **[ ⚡ Lancer le Scan ]** et bouton **[ 🗑️ Supprimer ]**.
  * Sauvegarde synchronisée en local et dans `config.json` via GitHub API.

---

## 📱 Accès Direct & Notifications

- **Application Web & PWA :** [https://darkts.github.io/nexus-radar/](https://darkts.github.io/nexus-radar/)
- **Canal Mobile ntfy.sh :** `sxm-immo-alert-97150-x9q4m2`
- **Sécurité :** Verrouillage par code PIN local, zéro secret stocké dans le dépôt (PAT GitHub uniquement dans le `localStorage` de votre navigateur).
