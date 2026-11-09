# 🛰️ NEXUS RADAR - Autonomous Multi-Category Hunting Hub

Hub Personnel Multi-Radars **100 % Serverless, gratuit et autonome**, conçu pour surveiller 24h/24 :
1. 🏠 **Radar Immobilier** : Locations à l'année à **Saint-Martin (97150)** (et îles) sous votre loyer cible (ex: ≤ 1 200 € / mois).
2. ✈️ **Radar Vols & Erreurs de Prix** : Vols cassés (Caraïbes, Asie, Europe, etc. ex: < 450 € A/R) via Dealabs Voyages, Fly4Free et Secret Flying.
3. 🚄 **Radar Trains & TGV** : Ventes flash TGV INOUI, Ouigo, Eurostar et trajets prioritaires (ex: < 19 €).

L'application mobile PWA vous permet de **tout piloter directement depuis votre smartphone sans toucher au code**, grâce à la **GitHub REST API**.

---

## 📱 Fonctionnalités de l'Application Mobile (Nexus Radar)

- 🔥 **Onglet Pépites** : Flux en temps réel de toutes les alertes (Immo, Vols, Trains), filtrage par catégorie, recherche instantanée et tri par prix.
- ⭐ **Onglet Favoris** : Sauvegarde locale de vos appartements ou billets préférés.
- 🎛️ **Onglet Radars (Éditeur Cloud direct)** :
  - Ajustez vos budgets max, activez/désactivez un radar ou ajoutez des destinations en 1 tap.
  - Cliquez sur **"Sauvegarder mes critères dans GitHub (Cloud)"** : l'application met à jour `config.json` via l'API GitHub directement.
  - Bouton **"⚡ Lancer un scan GitHub Actions maintenant"** pour forcer un scan immédiat.
- 🔔 **Onglet Réglages** :
  - Connexion GitHub API (Token PAT + Dépôt).
  - Écoute du flux SSE en direct via `ntfy.sh` avec chime audio cyberpunk, vibration et notifications Web Push.

---

## 📲 1. Activer les Notifications sur votre Smartphone

1. Installez l'application gratuite **ntfy** ([iOS](https://apps.apple.com/app/ntfy/id1625396347) ou [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
2. Appuyez sur **`+`** et abonnez-vous au canal :
   ```
   sxm-immo-alert-97150-x9q4m2
   ```
3. Chaque nouvelle annonce envoie un push avec le titre, le prix, la photo et un bouton direct pour ouvrir le deal en 1 tap.

---

## 🔑 2. Générer votre Token GitHub (Optionnel mais recommandé pour piloter depuis le smartphone)

Pour pouvoir modifier vos critères et lancer des scans depuis votre téléphone :
1. Sur GitHub, allez dans **Settings** > **Developer settings** > **Personal access tokens** > **Tokens (classic)**.
2. Cliquez sur **Generate new token (classic)**.
3. Cochez la case **`repo`** (Full control of private repositories).
4. Copiez le token (`ghp_...`).
5. Dans l'onglet **🔔 Réglages** de l'application Nexus Radar sur votre téléphone, collez votre Token et le nom de votre dépôt (ex: `monpseudo/mon-depot`).
6. Vos réglages sont stockés uniquement sur votre téléphone (localStorage).

---

## 🌐 3. Déploiement sur GitHub

Dans le dossier `c:\SxmImmoCloud` :

```powershell
# 1. Ajouter les modifications
git add .
git commit -m "feat: upgrade to Nexus Radar Multi-Category Hub"

# 2. Lier votre dépôt GitHub (si ce n'est pas déjà fait)
git remote add origin https://github.com/VOTRE_PSEUDO/VOTRE_DEPOT.git

# 3. Pousser la branche principale
git push -u origin main
```

### Réglages GitHub indispensables :
1. **Écriture GitHub Actions** : Dans votre dépôt, allez dans **Settings** > **Actions** > **General** > **Workflow permissions** > sélectionnez **Read and write permissions** > **Save**.
2. **GitHub Pages (App Mobile)** : Allez dans **Settings** > **Pages** > sous **Branch**, choisissez **main** et **`/ (root)`** > **Save**.

---

## 🧪 Tester en Local

Pour lancer un scan multi-catégories complet :
```bash
python scraper.py
```

Pour envoyer une notification de test sur votre téléphone :
```bash
python scraper.py --test-notify
```
