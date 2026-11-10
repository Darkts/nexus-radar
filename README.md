# 🛰️ NEXUS RADAR V5 - Hub Personnel Multi-Radars (Serverless & Autonome)

Hub Personnel **100 % Serverless, gratuit et autonome**, doté d'une ergonomie mobile fluide 60 FPS et structuré en **2 Univers Dédiés** avec un moteur de validation strict des URL :

---

## 🚀 Nouveautés Majeures de la Version V5

### 1. 🛡️ Validateur d'URL Certifiées & Suppression des Domaines Morts
- **Zéro lien mort / Zéro domaine parqué :** Bannissement total des anciens domaines inactifs (ex: 4U Real Estate, Island Immo, SXMCapri) qui redirigeaient vers des parcs publicitaires.
- **Deep-links officiels uniquement :** Redirection et validation automatique vers les portails officiels vérifiés (**DOMimmo**, **Leboncoin**, **SeLoger**, **Bien'ici**, **Google Flights**, **Trainline**, **SNCF Connect**).
- **Interception des racines génériques :** Tous les liens pointent directement sur des requêtes filtrées avec code postal, dates, budget ou directement sur la fiche du bien.

### 2. 🏠 Univers Immobilier Mondial
- **Entonnoir de recherche progressif en 3 étapes :**
  1. **Étape 1 :** Sélection de l'endroit (Barre de recherche + Géolocalisation *"📍 Autour de moi"* + pastilles de raccourcis : *Nancy, Saint-Martin 97150, Paris, Lyon, Nice, Espagne*).
  2. **Étape 2 :** Filtres propres et précis (*Switch Louer / Acheter / Tous*, budget max, typologie *Studio / T2 / T3+ / Maison*, surface minimum en m², commodités).
  3. **Étape 3 :** Switch visuel immédiat `[ 📋 Vue Liste ]` | `[ 🗺️ Vue Carte Leaflet ]` directement au-dessus des résultats, sans devoir changer d'onglet.
- **Swipe Tactile Fluide :**
  - 👉 Droite (💚) = J'aime / Enregistre dans les préférences d'apprentissage.
  - 👈 Gauche (❌) = Dislike / Masque immédiatement l'annonce.
  - ⭐ Étoile = Ajout instantané aux Favoris.
- **Fiche Détaillée Plein Écran (`#immoDetailModal`) :**
  - Galerie photos HD interactive.
  - Caractéristiques complètes, DPE dynamique et comparaison prix/m² vs marché.
  - Mini-carte Leaflet interactive du quartier (`#detailMiniMap`).
  - Bouton officiel certifié menant au deep-link de l'agence / portail.

### 3. 🎛️ Espace Radars Dédié (Immo vs Voyage)
- **Sélecteur d'espace :** `[ 🏠 Radar Immobilier ]` | `[ ✈️ Radar Voyage ]`.
- **Radar Immo :**
  - Configuration de la zone active, type d'opération (Location / Achat), typologie & surface min, budget max.
  - Bouton de pré-remplissage automatique basé sur vos likes récents.
  - Synchronisation Cloud 1-clic vers GitHub (`config.json`).
- **Radar Voyage :**
  - Configuration ville de départ (Nancy Hub / Paris / etc.), destination cible (ou "Partout / N'importe où"), dates/période et budget max total.
  - Synchronisation Cloud 1-clic vers GitHub (`config.json`).
- **Déclenchement instantané :** Bouton pour forcer un scan GitHub Actions à la demande.

### 4. ✈️ Univers Voyage & Planificateur Intelligent (Nancy Hub)
- **Entonnoir de recherche en 4 étapes :**
  - `[ 🛫 Départ ]` (Nancy, Lorraine TGV, Paris CDG/Orly...)
  - `[ 🛬 Destination ]` (Partout, Europe du Sud, Canaries, Antilles...)
  - `[ 📅 Dates & Flexibilité ]` (Week-end 3j, 1 semaine, Vacances...)
  - `[ 💰 Budget Max ]` (Filtrage en direct).
- **Deux sections distinctes et lisibles :**
  - **Section 1 :** 🔥 *Flash Deals & Erreurs de Prix* (vols dès 36€ A/R, TGV directs Nancy dès 10€ / 16€).
  - **Section 2 :** 🎯 *Meilleures Offres selon vos critères* (séjours tout compris calculés au "Vrai Coût depuis Nancy", hôtels notés ≥ 8.5/10, carnet de voyage, activités et adresses recommandées).

---

## 📱 Accès Direct & Notifications

- **Application Web & PWA :** [https://darkts.github.io/nexus-radar/](https://darkts.github.io/nexus-radar/)
- **Canal Mobile ntfy.sh :** `sxm-immo-alert-97150-x9q4m2`
- **Sécurité :** Verrouillage par code PIN local, zéro secret stocké dans le dépôt (PAT GitHub uniquement dans le `localStorage` de votre navigateur).
