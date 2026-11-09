"""
SXM Immo Veille - Scraper Automatique pour Locations à l'année à Saint-Martin (97150)
Architecture 100% Serverless - Compatible GitHub Actions
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SXMImmo")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "annonces.json")

KNOWN_SECTORS = [
    "Marigot", "Grand Case", "Concordia", "Hope Estate", "Baie Nettlé", 
    "Nettle Bay", "Anse Marcel", "Cul-de-Sac", "Cul de Sac", "Baie Orientale", 
    "Orient Bay", "Terres Basses", "Lowlands", "Oyster Pond", "Bellevue", 
    "Agrément", "Rambaud", "Friar's Bay", "Friars Bay", "Mont Vernon", 
    "Cole Bay", "Simpson Bay", "Cupecoy", "Pelican", "Philipsburg", "Galisbay"
]


def load_config():
    """Charge la configuration depuis config.json."""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Fichier de configuration introuvable : {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_annonces():
    """Charge la liste des annonces existantes depuis data/annonces.json."""
    if not os.path.exists(DATA_PATH):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        return []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Erreur lors de la lecture de {DATA_PATH} : {e}")
        return []


def save_annonces(annonces):
    """Sauvegarde la liste des annonces triées par date de détection."""
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    # Tri par date de détection descendante
    annonces_sorted = sorted(
        annonces,
        key=lambda x: x.get("date_detected", ""),
        reverse=True
    )
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(annonces_sorted, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 {len(annonces_sorted)} annonces sauvegardées dans {DATA_PATH}")


def detect_sector(text):
    """Extrait le quartier/secteur de Saint-Martin à partir du titre ou de la description."""
    if not text:
        return "Saint-Martin (97150)"
    text_lower = text.lower()
    for sector in KNOWN_SECTORS:
        if sector.lower() in text_lower:
            return f"{sector} (Saint-Martin)"
    return "Saint-Martin (97150)"


def is_excluded(title, description, price, config):
    """Vérifie si une annonce correspond aux critères d'exclusion (saisonnier, prix, commercial)."""
    combined_text = f"{title or ''} {description or ''}".lower()

    # 1. Vérification du prix
    max_price = config.get("max_price", 1200)
    if price is None or price <= 0:
        return True, "Prix invalide ou non renseigné"
    if price > max_price:
        return True, f"Prix ({price}€) supérieur au maximum ({max_price}€)"

    # 2. Exclusion des locations saisonnières / touristiques
    exclude_keywords = config.get("exclude_keywords", [])
    for kw in exclude_keywords:
        if kw.lower() in combined_text:
            return True, f"Mot-clé saisonnier détecté : '{kw}'"

    # Vérification explicite des unités par semaine / nuit
    if re.search(r"\b(\/semaine|par semaine|\/nuit|par nuit|la nuitée)\b", combined_text):
        return True, "Tarification par nuit ou par semaine détectée"

    # 3. Exclusion des baux commerciaux et bureaux si configuré
    if config.get("exclude_commercial", True):
        commercial_keywords = config.get("commercial_keywords", [])
        for kw in commercial_keywords:
            if kw.lower() in combined_text:
                return True, f"Mot-clé commercial détecté : '{kw}'"

    return False, "Valide"


def send_ntfy_notification(topic, annonce):
    """Envoie une notification push instantanée sur le canal ntfy.sh."""
    ntfy_url = f"https://ntfy.sh/{topic}"
    title = f"🏠 {annonce.get('price')} €/m - {annonce.get('title', 'Nouvelle annonce SXM')}"
    sector = annonce.get("location", "Saint-Martin")
    agency = annonce.get("agency", "Agence SXM")
    url = annonce.get("url", "")
    
    body = (
        f"💰 Loyer : {annonce.get('price')} € / mois\n"
        f"📍 Secteur : {sector}\n"
        f"🏢 Source : {agency}\n"
        f"🔗 Lien direct disponible ci-dessous"
    )

    headers = {
        "Title": title.encode("utf-8"),
        "Click": url,
        "Tags": "house,euro,island",
        "Priority": "high",
    }
    
    # Si une image est présente, l'ajouter comme aperçu dans la notification
    if annonce.get("image_url"):
        headers["Attach"] = annonce["image_url"]

    try:
        resp = requests.post(ntfy_url, data=body.encode("utf-8"), headers=headers, timeout=10)
        if resp.status_code == 200:
            logger.info(f"🔔 Notification ntfy envoyée avec succès pour '{title}'")
            return True
        else:
            logger.warning(f"⚠️ Échec ntfy (status {resp.status_code}) : {resp.text}")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi de la notification ntfy : {e}")
    return False


# -------------------------------------------------------------
# SCRAPERS POUR CHAQUE SOURCE
# -------------------------------------------------------------

def scrape_domimmo(config):
    """
    Scrape le portail DOMimmo (regroupe Emotion, Alliance SXM, Oceano, Tropic Immo, IAD, etc.).
    Catégorie 6 = Location longue durée à Saint-Martin (id_com_pays=SMT).
    """
    logger.info("🔎 Scraping DOMimmo (Saint-Martin SMT, Catégorie 6 - Locations)...")
    url = "https://www.domimmo.com/api/domimmo/offers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.domimmo.com/immobilier/location/saint-martin/"
    }
    params = {
        "page": 1,
        "limit": 100,
        "id_com_pays": "SMT",
        "id_di_ad_cat": 6
    }
    annonces = []
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"DOMimmo API a retourné le code {resp.status_code}")
            return annonces
        
        items = resp.json()
        logger.info(f"DOMimmo a retourné {len(items)} offres brutes.")
        
        for it in items:
            ad_id = str(it.get("id", ""))
            title = (it.get("title") or "Location Saint-Martin").strip()
            price = it.get("price")
            desc = it.get("description") or ""
            
            # Vérifier l'exclusion
            excluded, reason = is_excluded(title, desc, price, config)
            if excluded:
                continue

            # Secteur
            sector = detect_sector(f"{title} {desc} {it.get('city', '')}")
            
            # Image
            image_url = it.get("imageSrc") or (it.get("photos", [None])[0] if it.get("photos") else None)
            
            annonce = {
                "id": f"domimmo_{ad_id}",
                "source_id": ad_id,
                "title": title,
                "price": price,
                "price_str": f"{price} € / mois",
                "location": sector,
                "agency": it.get("company") or "DOMimmo",
                "url": f"https://www.domimmo.com/saint-martin/immobilier/{ad_id}",
                "image_url": image_url,
                "description": desc[:350] + ("..." if len(desc) > 350 else ""),
                "surface": f"{it.get('surface_habitable')} m²" if it.get("surface_habitable") else None,
                "rooms": it.get("pieces"),
                "date_detected": datetime.now(timezone.utc).isoformat(),
            }
            annonces.append(annonce)
            
    except Exception as e:
        logger.error(f"Erreur lors du scraping DOMimmo : {e}")

    logger.info(f"✅ DOMimmo : {len(annonces)} annonces retenues sous {config.get('max_price')}€.")
    return annonces


def scrape_emotion_direct(page, config):
    """
    Scrape le site officiel d'Emotion Real Estate (https://www.emotion-realestate.com/louer).
    """
    logger.info("🔎 Scraping Emotion Real Estate (direct)...")
    annonces = []
    try:
        page.goto("https://www.emotion-realestate.com/louer", timeout=25000, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # Récupère les données des annonces
        items = page.evaluate("""() => {
            const results = [];
            const links = document.querySelectorAll("a[href*='/location/'], a[href*='/bien/']");
            links.forEach(a => {
                const text = a.innerText || "";
                if (text.includes("€") && (text.includes("97150") || text.includes("Saint-Martin"))) {
                    const img = a.querySelector("img");
                    results.push({
                        href: a.href,
                        text: text.trim(),
                        img: img ? img.src : null
                    });
                }
            });
            return results;
        }""")

        for it in items:
            raw_text = it["text"]
            # Extraction du prix (ex: "940 €" ou "1 100 €")
            price_match = re.search(r"(\d[\d\s]*)\s*€", raw_text)
            if not price_match:
                continue
            price = int(price_match.group(1).replace(" ", ""))
            
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            title = lines[1] if len(lines) > 1 else lines[0]
            
            excluded, reason = is_excluded(title, raw_text, price, config)
            if excluded:
                continue

            ref_match = re.search(r"Réf\s*:\s*([A-Za-z0-9\-]+)", raw_text)
            ad_id = ref_match.group(1) if ref_match else it["href"].rstrip("/").split("/")[-1]

            annonces.append({
                "id": f"emotion_{ad_id}",
                "source_id": ad_id,
                "title": title,
                "price": price,
                "price_str": f"{price} € / mois",
                "location": detect_sector(raw_text),
                "agency": "Emotion Real Estate",
                "url": it["href"],
                "image_url": it.get("img"),
                "description": raw_text[:250],
                "surface": None,
                "rooms": None,
                "date_detected": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.warning(f"Avertissement lors du scraping Emotion direct : {e}")

    logger.info(f"✅ Emotion Direct : {len(annonces)} annonces retenues.")
    return annonces


def scrape_four_u(page, config):
    """
    Scrape 4U Real Estate (https://www.4u-realestate.com/our-rentals/).
    """
    logger.info("🔎 Scraping 4U Real Estate...")
    annonces = []
    try:
        page.goto("https://www.4u-realestate.com/our-rentals/", timeout=25000, wait_until="networkidle")
        page.wait_for_timeout(2000)

        items = page.evaluate("""() => {
            const results = [];
            document.querySelectorAll("article, .property-item, a[href*='/propriete/']").forEach(el => {
                const text = el.innerText || "";
                const link = el.tagName === 'A' ? el : el.querySelector("a[href*='/propriete/']");
                const img = el.querySelector("img");
                if (link && text && (text.includes("€") || text.includes("$"))) {
                    results.push({
                        href: link.href,
                        text: text.trim(),
                        img: img ? img.src : null
                    });
                }
            });
            return results;
        }""")

        for it in items:
            raw_text = it["text"]
            # Recherche prix € ou $
            price_match = re.search(r"(\d[\d\s,]*)\s*(€|\$)", raw_text)
            if not price_match:
                continue
            price = int(price_match.group(1).replace(" ", "").replace(",", ""))

            title = raw_text.split("\n")[0]
            excluded, reason = is_excluded(title, raw_text, price, config)
            if excluded:
                continue

            slug = it["href"].rstrip("/").split("/")[-1]
            annonces.append({
                "id": f"4u_{slug}",
                "source_id": slug,
                "title": title,
                "price": price,
                "price_str": f"{price} € / mois",
                "location": detect_sector(raw_text),
                "agency": "4U Real Estate",
                "url": it["href"],
                "image_url": it.get("img"),
                "description": raw_text[:250],
                "surface": None,
                "rooms": None,
                "date_detected": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.warning(f"Avertissement lors du scraping 4U Real Estate : {e}")

    logger.info(f"✅ 4U Real Estate : {len(annonces)} annonces retenues.")
    return annonces


def scrape_leboncoin(page, config):
    """
    Scrape Leboncoin pour Saint-Martin (97150) avec protection anti-bot gérée avec résilience.
    """
    logger.info("🔎 Tentative de scan Leboncoin Saint-Martin (97150)...")
    annonces = []
    max_price = config.get("max_price", 1200)
    url = f"https://www.leboncoin.fr/recherche?category=10&locations=Saint-Martin_97150&price=min-{max_price}"
    try:
        resp = page.goto(url, timeout=15000)
        status = resp.status if resp else None
        if status in [403, 429]:
            logger.info("ℹ️ Leboncoin : Protection WAF/Datadome active (accès restreint). Source ignorée pour ce cycle.")
            return annonces
        
        page.wait_for_timeout(2000)
        items = page.evaluate("""() => {
            const results = [];
            document.querySelectorAll("a[data-qa-id*='aditem_container']").forEach(a => {
                results.push({
                    href: a.href,
                    text: a.innerText
                });
            });
            return results;
        }""")
        for it in items:
            raw_text = it["text"]
            price_match = re.search(r"(\d[\d\s]*)\s*€", raw_text)
            if not price_match:
                continue
            price = int(price_match.group(1).replace(" ", ""))
            title = raw_text.split("\n")[0]
            
            excluded, reason = is_excluded(title, raw_text, price, config)
            if excluded:
                continue

            slug = it["href"].rstrip("/").split("/")[-1]
            annonces.append({
                "id": f"lbc_{slug}",
                "source_id": slug,
                "title": title,
                "price": price,
                "price_str": f"{price} € / mois",
                "location": detect_sector(raw_text),
                "agency": "Leboncoin",
                "url": it["href"],
                "image_url": None,
                "description": raw_text[:250],
                "surface": None,
                "rooms": None,
                "date_detected": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.info(f"ℹ️ Leboncoin indisponible ou protégé ({e}) - passage aux autres sources.")

    return annonces


# -------------------------------------------------------------
# FONCTION PRINCIPALE
# -------------------------------------------------------------

def run_scraper(send_notifications=True):
    """Exécute l'ensemble des scrapers, déduplique et notifie pour les nouveautés."""
    logger.info("🚀 Démarrage du cycle de veille SXM Immo...")
    config = load_config()
    existing_annonces = load_annonces()
    existing_ids = {a["id"] for a in existing_annonces}
    existing_urls = {a.get("url") for a in existing_annonces if a.get("url")}
    
    all_scraped = []

    # 1. Scraping DOMimmo (API rapide et ultra-complète)
    if config.get("enabled_sources", {}).get("domimmo", True):
        domimmo_ads = scrape_domimmo(config)
        all_scraped.extend(domimmo_ads)

    # 2. Scraping Playwright (Emotion, 4U, Leboncoin)
    need_playwright = any([
        config.get("enabled_sources", {}).get("emotion", True),
        config.get("enabled_sources", {}).get("four_u", True),
        config.get("enabled_sources", {}).get("leboncoin", True)
    ])

    if need_playwright:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )

                if config.get("enabled_sources", {}).get("emotion", True):
                    emotion_ads = scrape_emotion_direct(page, config)
                    all_scraped.extend(emotion_ads)

                if config.get("enabled_sources", {}).get("four_u", True):
                    four_u_ads = scrape_four_u(page, config)
                    all_scraped.extend(four_u_ads)

                if config.get("enabled_sources", {}).get("leboncoin", True):
                    lbc_ads = scrape_leboncoin(page, config)
                    all_scraped.extend(lbc_ads)

                browser.close()
        except Exception as e:
            logger.error(f"Erreur durant l'exécution Playwright : {e}")

    # Déduplication
    new_annonces = []
    seen_in_this_run = set()

    for ad in all_scraped:
        ad_id = ad["id"]
        ad_url = ad.get("url")

        if ad_id in seen_in_this_run or ad_url in seen_in_this_run:
            continue
        seen_in_this_run.add(ad_id)
        if ad_url:
            seen_in_this_run.add(ad_url)

        if ad_id not in existing_ids and ad_url not in existing_urls:
            new_annonces.append(ad)

    logger.info(f"📊 Résultats du scan : {len(all_scraped)} annonces trouvées au total | {len(new_annonces)} NOUVELLES annonces !")

    # Envoi des notifications ntfy pour les nouvelles annonces
    topic = config.get("ntfy_topic", "sxm-immo-alert-97150-x9q4m2")
    if send_notifications and new_annonces:
        logger.info(f"📲 Envoi des notifications push vers ntfy.sh/{topic}...")
        for ad in new_annonces:
            send_ntfy_notification(topic, ad)
            time.sleep(0.5)  # Pause pour éviter d'inonder l'API ntfy

    # Mise à jour et sauvegarde du fichier JSON
    if new_annonces:
        updated_list = new_annonces + existing_annonces
        save_annonces(updated_list)
        logger.info(f"✨ {len(new_annonces)} nouvelles annonces ajoutées à data/annonces.json.")
    else:
        logger.info("ℹ️ Aucune nouvelle annonce à ajouter pour ce cycle.")

    return new_annonces


if __name__ == "__main__":
    # Paramètre optionnel : --test-notify pour envoyer une notification de test
    if "--test-notify" in sys.argv:
        cfg = load_config()
        t = cfg.get("ntfy_topic", "sxm-immo-alert-97150-x9q4m2")
        logger.info(f"Envoi d'une notification de test sur https://ntfy.sh/{t}")
        test_ad = {
            "title": "T2 Meublé Concordia - Test Veille SXM",
            "price": 950,
            "location": "Concordia (Saint-Martin)",
            "agency": "Alliance Immobilière SXM",
            "url": "https://www.domimmo.com/immobilier/location/saint-martin/",
            "image_url": "https://keldom.blob.core.windows.net/domimmo/pro/photos/100/iad2025.png"
        }
        send_ntfy_notification(t, test_ad)
        print("Test terminé.")
    else:
        run_scraper(send_notifications=True)
