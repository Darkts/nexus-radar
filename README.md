# 🛰️ NEXUS RADAR V3 - Architecture Double Univers

Hub Personnel **100 % Serverless, gratuit et autonome**, structuré en **2 Univers Dédiés** au sein de la même application mobile PWA :

1. 🏠 **UNIVERS 1 : IMMOBILIER MONDIAL** (Saint-Martin 97150, France, Monde)
2. ✈️ **UNIVERS 2 : VOYAGE & PLANIFICATEUR INTELLIGENT** (Départ Nancy Hub)

---

## ⚡ Les Fonctionnalités Majeures de la V3

### 1. 🔄 Switch Double Univers Instantané (60 FPS)
- Sélecteur au sommet de l'application : `[ 🏠 IMMOBILIER MONDIAL ]` et `[ ✈️ VOYAGE & ÉVASION ]`.
- Basculement instantané de l'interface, des filtres, du catalogue de favoris et des radars sans rechargement de page.

---

### 2. 🏠 UNIVERS 1 : IMMOBILIER MONDIAL
- 🗺️ **Carte Interactive Leaflet.js + OpenStreetMap (100% Gratuite)** :
  - Exploration géographique fluide sans clé API ni frais.
  - Recherche par géocodage mondial Nominatim (ex: Saint-Martin, Nancy, Alicante, Bali...).
  - Rayon de surveillance paramétrable (5, 15, 30, 50 km) avec cercle dynamique.
  - Marqueurs interactifs avec aperçu photo, loyer, prix au m², commodités et Like / Dislike.
- 📐 **Filtres Précis & Indicateur Marché** :
  - Surface minimale (m²), pièces (Studio, T2, T3+), budget max.
  - Commodités clés : 🛋️ Meublé, ☀️ Terrasse/Balcon, 🏊 Piscine, 🌊 Vue Mer, 🚗 Parking.
  - Calcul automatique du **prix au m²** vs prix moyen du marché (badge vert : *ex: 🟢 -18% sous le marché*).
- ⭐ **Catalogue Perso avec Notes Privées** :
  - Possibilité d'ajouter des notes personnelles sur chaque bien sauvegardé (*"À visiter mardi"*, *"Investissement locatif idéal"*).
- 👎 **Système de Dislike Intelligent** :
  - Mémorise vos critères d'exclusion (secteur, surface insuffisante, hors budget) pour affiner les prochaines alertes.

---

### 3. ✈️ UNIVERS 2 : VOYAGE ("FAIS-MOI RÊVER" & NANCY HUB)
- ✨ **Mode "Fais-moi rêver"** :
  - Indiquez une période (*Week-end 3 jours*, *1 semaine*, *Vacances d'Hiver*) + votre budget global tout compris.
  - L'application déniche les meilleures opportunités combinées (TGV au départ de Nancy + Vols réguliers + Hôtels vérifiés ≥ 8.5/10).
- 🎯 **Mode "Sniper Destination"** :
  - Surveillance des baisses de prix historiques (J-7 / J-30) sur vos destinations favorites (Saint-Martin SXM, Guadeloupe PTP, Martinique FDF, New York, Tokyo, Italie...).
- 🧠 **Auto-Apprentissage Like / Dislike** :
  - Deux dislikes sur une même destination la bannissent automatiquement du flux principal.
  - Bouton de réinitialisation et switch vers le *Mode Exploration* pour sortir de sa zone de confort.

---

### 4. 📖 PAGE DÉDIÉE : "CARNET DE VOYAGE TOUT COMPRIS"
En cliquant sur une opportunité de voyage, une vue immersive complète s'ouvre :
- **Onglet 1 : Le Vrai Coût & Logistique depuis Nancy** :
  - Trajet étape par étape : TGV Nancy -> Paris/Luxembourg (dès 16€) + Vol direct A/R + Hôtel de charme ≥ 8.5/10.
  - Explication claire de l'économie réalisée vs prix standard en agence.
- **Onglet 2 : Activités & Restos Pépites (≥ 4.5★ Google)** :
  - Liste des meilleures activités sur place (ex: *Snorkeling tortues à Tintamarre*, *Sunset à Baie Rouge*).
  - Liste des meilleurs restaurants testés et approuvés (ex: *Le Cottage Grand-Case*, *Lolos traditionnels*).
  - **Bouton ❤️ "Ajouter au planning"** : Intègre l'activité ou le resto dans votre **Programme Jour par Jour** (Jour 1, Jour 2, Jour 3...).
- **Onglet 3 : Preuve Sociale & Vidéos TikTok Virales** :
  - Liens et boutons d'ouverture directe vers les vidéos TikTok virales (`https://www.tiktok.com/tag/...`) et Google Maps pour voir la réalité des spots en 1 tap avant d'y aller.

---

### 5. 🔒 Sécurité & Confidentialité
- **Code PIN à 4 chiffres local** : Verrouillage à l'ouverture de l'application sur smartphone.
- **Zéro Token dans Git** : Vos accès API restent cantonnés au navigateur de votre téléphone.

---

## 📱 Accès à l'Application

- **Lien Web & PWA :** [https://darkts.github.io/nexus-radar/](https://darkts.github.io/nexus-radar/)
- **Canal Push ntfy.sh :** `sxm-immo-alert-97150-x9q4m2`
