# 🛰️ NEXUS RADAR V2 - Autonomous Multi-Category Hunting Hub

Hub Personnel Multi-Radars **100 % Serverless, gratuit et autonome**, conçu pour surveiller 24h/24 :
1. 🏠 **Radar Immobilier** : Locations à l'année à **Saint-Martin (97150)** (DOMimmo, 4U Real Estate, Emotion Real Estate, SXMCapri, Leboncoin) sous loyer cible.
2. ✈️ **Radar Vols Directs & Erreurs de Prix** : Google Flights (CDG, ORY, LUX, BSL, FRA), Secret Flying, Air Caraïbes / Corsair / French Bee vers SXM/SFG avec **Calculateur de Vrai Coût depuis Nancy**.
3. 🚄 **Radar Trains & TGV** : Lignes prioritaires SNCF / Ouigo (Nancy <-> Paris Est, Nancy <-> Roissy CDG 2, Nancy <-> Massy TGV) dès 10 €.

L'application mobile PWA vous permet de **tout piloter directement depuis votre smartphone sans toucher au code**, protégée par code PIN et synchronisée via la **GitHub REST API**.

---

## ⚡ Les Nouveautés Majeures de la V2

### 1. 🔒 Sécurité & Écran de Verrouillage PIN
- **Écran de verrouillage PIN à 4 chiffres** : À la première ouverture de l'application, définissez votre code secret à 4 chiffres (stocké chiffré dans le `localStorage` de votre téléphone). Impossible pour un tiers d'accéder au Hub ou de modifier vos critères sans votre code.
- **Zéro Token dans le code** : Aucun token ni credential n'est écrit dans le dépôt. Le GitHub Personal Access Token (PAT) reste strictement cantonné au navigateur de votre appareil.

### 2. 🚀 Refonte UI/UX 60 FPS
- **Header ultra-léger & fluide** : Suppression de la bannière SVG lourde, intégration native avec `safe-area-inset-top` pour les encoches Android/iPhone.
- **Suppression des filtres CSS lourds** (`backdrop-filter`) : Défilement fluide à 60 images/seconde sur réseau 4G/5G mobile.

### 3. 🎯 True Cost Engine : Vrai Coût depuis Nancy
Pour chaque offre de vol au départ de Paris, Luxembourg, Bâle ou Francfort, l'application calcule le **coût total réel** pour un départ depuis Nancy :
$$\text{Budget Total} = \text{Billet d'avion A/R} + \text{Train A/R Nancy}\,(20€-65€) + \text{Hôtel 7 nuits}\,(\ge 8/10)$$
- 🟢 **Badge "Rentable depuis Nancy"** : L'économie réalisée surpasse largement le trajet de pré-acheminement.
- 🔴 **Badge "Fausse bonne affaire"** : Le coût du train/navette annule l'intérêt du vol discount.

### 4. 📈 Historique des Prix & Détecteur d'Urgence (J-7 / J-30)
- Suivi de l'évolution des prix par route aérienne, ligne TGV et type de logement à Saint-Martin.
- Mini-comparatif : **Prix actuel** vs **Moyenne 7j** vs **Moyenne 30j** vs **Minimum historique**.
- Badges d'urgence dynamiques :
  - 🟢 **PÉPITE HISTORIQUE (-XX% vs mois dernier — URGENT)** : Anomalie de prix réelle.
  - 🟠 **PRIX CLASSIQUE** : Tarif standard sans urgence.
  - 🔴 **PRIX ÉLEVÉ** : Ne pas acheter maintenant.

### 5. 👎 Dislike Intelligent & Mode Exploration
- Bouton **👎 Pas intéressé** sur chaque carte : mémorise vos désintérêts (ex: "Moins de : Canada", "Trop cher", "Période inadaptée").
- Bascule en 1 tap en haut du flux :
  - 🎯 **Mode Sur-Mesure** : Vos alertes filtrées selon vos critères et préférences.
  - 🌍 **Mode Exploration** : Réaffiche l'intégralité des opportunités détectées sans exclusion.

### 6. 🧠 Assistant de Configuration IA Local (100% Gratuit)
Dans l'onglet **🎛️ Radars**, créez ou ajustez vos recherches sans taper de JSON :
- **Requête en langage naturel** : Entrez simplement *"Trouve-moi un T2 à Saint-Martin Baie Nettlé max 1100€"* ou *"Vol pour New York depuis Paris max 300€"*. Le moteur d'analyse NLP local prépare la configuration instantanément.
- **Analyseur d'URL** : Collez un lien Google Flights, Leboncoin ou DOMimmo pour en extraire automatiquement les filtres de route et de prix.
- **Synchronisation Cloud en 1 tap** : Mise à jour immédiate de `config.json` via l'API GitHub.

---

## 📱 Utilisation de l'Application

- **Lien Web & PWA** : [https://darkts.github.io/nexus-radar/](https://darkts.github.io/nexus-radar/)
- **Installation sur Smartphone** :
  - **Android (Chrome)** : Menu `⋮` > *Installer l'application* ou *Ajouter à l'écran d'accueil*.
  - **iOS (Safari)** : Bouton *Partager* > *Sur l'écran d'accueil*.

---

## 🔔 Notifications Push Mobiles (ntfy.sh)

1. Installez l'application gratuite **ntfy** ([Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy) ou [App Store](https://apps.apple.com/app/ntfy/id1625396347)).
2. Abonnez-vous au canal :
   ```
   sxm-immo-alert-97150-x9q4m2
   ```
3. Les notifications arrivent avec l'icône de catégorie (🏠, ✈️, 🚄), le prix, la photo et un bouton direct pour ouvrir le deal en 1 tap.

---

## 🔒 Confidentialité & Passage du Repo en Privé

### Pourquoi le repo est-il public par défaut ?
Sur GitHub gratuit, **GitHub Pages** (qui héberge l'application web PWA) requiert un dépôt public. Pour héberger GitHub Pages depuis un dépôt privé, un abonnement **GitHub Pro** ($4/mois) ou le pack **GitHub Student Developer** est requis.

### Comment vos données sont-elles protégées en mode public ?
1. **Écran PIN local** : Toute personne ouvrant votre lien `github.io` tombe sur un cadenas PIN à 4 chiffres bloquant l'affichage.
2. **Tokens sécurisés** : Votre GitHub Token n'est **JAMAIS** sur GitHub ni dans les commits. Il est stocké uniquement dans le `localStorage` de votre téléphone.
3. **Annonces publiques** : `data/annonces.json` ne contient que des annonces publiques d'agences et de compagnies de transport.

### Comment passer en Privé si vous avez GitHub Pro ou un hébergement alternatif :
1. Dans GitHub : **Settings** > tout en bas **Danger Zone** > **Change repository visibility** > **Make private**.
2. Si vous avez GitHub Pro, Pages continue de fonctionner avec restriction d'accès.
3. Alternative 100% gratuite et privée : Déployer le dossier front-end sur **Cloudflare Pages** ou **Vercel** relié à votre repo privé en 2 clics.

---

## 🧪 Tests en Local

```powershell
# Exécuter le scan multi-catégories complet (Playwright + APIs)
python scraper.py

# Envoyer une notification de test sur ntfy.sh
python scraper.py --test-notify
```
