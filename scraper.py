"""
Nexus Radar - Moteur de Veille Autonome Multi-Catégories
Modules intégrés :
  1. 🏠 Radar Immo (Saint-Martin 97150 & autres)
  2. ✈️ Radar Vols & Erreurs de Prix (Caraïbes, Asie, Europe, etc.)
  3. 🚄 Radar Trains & TGV (Ouigo, SNCF, Eurostar, etc.)

Architecture 100% Serverless - Compatible GitHub Actions
"""

import hashlib
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("NexusRadar")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "annonces.json")

KNOWN_SECTORS_SXM = [
    "Marigot", "Grand Case", "Concordia", "Hope Estate", "Baie Nettlé", 
    "Nettle Bay", "Anse Marcel", "Cul-de-Sac", "Cul de Sac", "Baie Orientale", 
    "Orient Bay", "Terres Basses", "Lowlands", "Oyster Pond", "Bellevue", 
    "Agrément", "Rambaud", "Friar's Bay", "Friars Bay", "Mont Vernon", 
    "Cole Bay", "Simpson Bay", "Cupecoy", "Pelican", "Philipsburg", "Galisbay"
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


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
    annonces_sorted = sorted(
        annonces,
        key=lambda x: x.get("date_detected", ""),
        reverse=True
    )
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(annonces_sorted, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 {len(annonces_sorted)} pépites sauvegardées dans {DATA_PATH}")


def detect_sector_sxm(text):
    """Extrait le quartier/secteur de Saint-Martin."""
    if not text:
        return "Saint-Martin (97150)"
    text_lower = text.lower()
    for sector in KNOWN_SECTORS_SXM:
        if sector.lower() in text_lower:
            return f"{sector} (Saint-Martin)"
    return "Saint-Martin (97150)"


def send_ntfy_notification(topic, item):
    """Envoie une notification push instantanée et stylée sur ntfy.sh."""
    ntfy_url = f"https://ntfy.sh/{topic}"
    cat = item.get("category", "immo")
    
    # Configuration par catégorie
    if cat == "flight":
        icon_tag = "airplane,moneybag,ticket"
        title_prefix = f"✈️ [VOL {item.get('price_str', '')}]"
    elif cat == "train":
        icon_tag = "bullettrain_front,zap,sparkles"
        title_prefix = f"🚄 [TRAIN {item.get('price_str', '')}]"
    else:
        icon_tag = "house,euro,island"
        title_prefix = f"🏠 [IMMO {item.get('price_str', '')}]"

    title = f"{title_prefix} {item.get('title', 'Nouvelle alerte')[:65]}"
    location = item.get("location", "Non spécifié")
    agency = item.get("agency", "Nexus Radar")
    url = item.get("url", "")
    
    body = (
        f"🎯 PÉPITE DÉTECTÉE PAR NEXUS RADAR\n"
        f"💰 Prix : {item.get('price_str') or (str(item.get('price')) + ' €')}\n"
        f"📍 Destination / Secteur : {location}\n"
        f"🏢 Source / Marchand : {agency}\n"
        f"🔗 Appuyez pour ouvrir l'offre directement"
    )

    headers = {
        "Title": title.encode("utf-8"),
        "Click": url,
        "Tags": icon_tag,
        "Priority": "high",
    }
    
    # Image jointe si disponible
    if item.get("image_url"):
        headers["Attach"] = item["image_url"]

    try:
        resp = requests.post(ntfy_url, data=body.encode("utf-8"), headers=headers, timeout=10)
        if resp.status_code == 200:
            logger.info(f"🔔 Notification ntfy envoyée : '{title}'")
            return True
        else:
            logger.warning(f"⚠️ Échec ntfy ({resp.status_code}) : {resp.text}")
    except Exception as e:
        logger.error(f"❌ Erreur notification ntfy : {e}")
    return False


# =============================================================
# MODULE 1 : 🏠 RADAR IMMOBILIER (Saint-Martin 97150 & autres)
# =============================================================

def is_immo_excluded(title, description, price, immo_cfg):
    """Vérifie si une annonce immo est exclue (saisonnière, trop chère, commerciale)."""
    combined = f"{title or ''} {description or ''}".lower()
    max_price = immo_cfg.get("max_price", 1200)

    if price is None or price <= 0:
        return True, "Prix invalide"
    if price > max_price:
        return True, f"Prix {price}€ > {max_price}€"

    # Exclusion saisonnière
    for kw in immo_cfg.get("exclude_keywords", []):
        if kw.lower() in combined:
            return True, f"Mot saisonnier : '{kw}'"

    if re.search(r"\b(\/semaine|par semaine|\/nuit|par nuit|la nuitée)\b", combined):
        return True, "Location par semaine/nuit"

    # Exclusion baux commerciaux
    if immo_cfg.get("exclude_commercial", True):
        for kw in immo_cfg.get("commercial_keywords", []):
            if kw.lower() in combined:
                return True, f"Mot commercial : '{kw}'"

    return False, "Valide"


def scrape_domimmo(immo_cfg):
    """Scrape l'API de DOMimmo (regroupe toutes les agences locales de Saint-Martin)."""
    logger.info("🔎 [Radar Immo] Scan de DOMimmo...")
    url = "https://www.domimmo.com/api/domimmo/offers"
    params = {"page": 1, "limit": 100, "id_com_pays": "SMT", "id_di_ad_cat": 6}
    annonces = []
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            items = resp.json()
            for it in items:
                ad_id = str(it.get("id", ""))
                title = (it.get("title") or "Location Saint-Martin").strip()
                price = it.get("price")
                desc = it.get("description") or ""

                excluded, _ = is_immo_excluded(title, desc, price, immo_cfg)
                if excluded:
                    continue

                sector = detect_sector_sxm(f"{title} {desc} {it.get('city', '')}")
                image_url = it.get("imageSrc") or (it.get("photos", [None])[0] if it.get("photos") else None)

                annonces.append({
                    "id": f"immo_domimmo_{ad_id}",
                    "category": "immo",
                    "category_label": "Immobilier",
                    "badge": "🏠 Immo",
                    "title": title,
                    "price": price,
                    "price_str": f"{price} € / mois",
                    "location": sector,
                    "agency": it.get("company") or "DOMimmo",
                    "url": f"https://www.domimmo.com/saint-martin/immobilier/{ad_id}",
                    "image_url": image_url,
                    "description": desc[:300] + ("..." if len(desc) > 300 else ""),
                    "surface": f"{it.get('surface_habitable')} m²" if it.get("surface_habitable") else None,
                    "rooms": it.get("pieces"),
                    "date_detected": datetime.now(timezone.utc).isoformat(),
                })
    except Exception as e:
        logger.error(f"Erreur DOMimmo : {e}")
    return annonces


def scrape_immo_module(config):
    """Orchestre la surveillance immobilière."""
    immo_cfg = config.get("radars", {}).get("immo", {})
    if not immo_cfg.get("enabled", True):
        logger.info("⏸️ [Radar Immo] Désactivé dans la configuration.")
        return []

    logger.info(f"🚀 [Radar Immo] Actif - Budget max : {immo_cfg.get('max_price', 1200)} €")
    results = []

    # 1. DOMimmo
    if immo_cfg.get("sources", {}).get("domimmo", True):
        results.extend(scrape_domimmo(immo_cfg))

    logger.info(f"✅ [Radar Immo] {len(results)} annonces retenues.")
    return results


# =============================================================
# MODULE 2 : ✈️ RADAR VOLS & ERREURS DE PRIX (Caraïbes & Monde)
# =============================================================

def scrape_flights_module(config, page=None):
    """Scrape les flux d'erreurs de prix et billets d'avion pas chers."""
    flight_cfg = config.get("radars", {}).get("flights", {})
    if not flight_cfg.get("enabled", True):
        logger.info("⏸️ [Radar Vols] Désactivé dans la configuration.")
        return []

    max_budget = flight_cfg.get("max_price", 450)
    destinations = [d.lower() for d in flight_cfg.get("target_destinations", ["sxm", "saint-martin", "caraïbes"])]
    routes = flight_cfg.get("routes", [])
    logger.info(f"🚀 [Radar Vols] Actif - Seuil max : {max_budget} € | Destinations cibles : {len(destinations)}")
    
    deals = []

    # 1. Dealabs Voyages (Flux RSS complet)
    try:
        url = "https://www.dealabs.com/rss/groupe/voyages"
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=12)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for it in root.findall(".//item"):
                title = it.findtext("title") or ""
                desc = it.findtext("description") or ""
                link = it.findtext("link") or ""
                combined = f"{title} {desc}".lower()

                # Vérifier si c'est un vol (et non un train)
                is_train = any(k in combined for k in ["train", "tgv", "ouigo", "sncf", "eurostar", "ter", "intercités"])
                if is_train:
                    continue

                is_flight = any(k in combined for k in ["vol", "vols", "billet d'avion", "billets d'avion", "a/r", "aller/retour", "aller-retour", "easyjet", "transat", "air france", "ryanair", "air caraibes", "french bee"])
                if not is_flight:
                    continue

                # Extraire le prix
                p_match = re.search(r"(\d+)\s*€", title)
                price = int(p_match.group(1)) if p_match else None
                
                # Vérifier correspondance destination
                dest_match = any(d in combined for d in destinations)

                # Route spécifique surveillée
                route_matched = False
                for r in routes:
                    r_name = r.get("name", "").lower()
                    r_from = r.get("from", "").lower()
                    r_to = r.get("to", "").lower()
                    r_max = r.get("max_price", max_budget)
                    if (r_from in combined and r_to in combined) or (r_name in combined):
                        if price and price <= r_max:
                            route_matched = True
                            break

                # Condition de retenue : prix sous le seuil général OU correspondance destination sous seuil OU route
                should_keep = False
                if price and price <= max_budget:
                    should_keep = True
                elif dest_match and (price is None or price <= (max_budget + 150)):
                    should_keep = True
                elif route_matched:
                    should_keep = True

                if should_keep:
                    # Extraction photo
                    img_match = re.search(r'<img[^>]+src="([^">]+)"', desc)
                    img_url = img_match.group(1) if img_match else None

                    deal_id = hashlib.md5(link.encode("utf-8")).hexdigest()[:12]
                    deals.append({
                        "id": f"flight_dealabs_{deal_id}",
                        "category": "flight",
                        "category_label": "Vol & Erreur de Prix",
                        "badge": "✈️ Vol",
                        "title": title,
                        "price": price or max_budget,
                        "price_str": f"{price} € A/R" if price else "Prix cassé",
                        "location": "Destination Internationale / Caraïbes",
                        "agency": "Dealabs Voyages",
                        "url": link,
                        "image_url": img_url or "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=600",
                        "description": BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:280],
                        "surface": None,
                        "rooms": None,
                        "date_detected": datetime.now(timezone.utc).isoformat(),
                    })
    except Exception as e:
        logger.warning(f"Avertissement Dealabs Voyages : {e}")

    # 2. Fly4Free (Flux RSS bons plans Europe & Monde)
    try:
        url = "https://www.fly4free.com/flight-deals/europe/feed/"
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=12)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for it in root.findall(".//item")[:20]:
                title = it.findtext("title") or ""
                link = it.findtext("link") or ""
                desc = it.findtext("description") or ""
                combined = f"{title} {desc}".lower()

                p_match = re.search(r"€\s*(\d+)|(\d+)\s*€", title)
                price = int(p_match.group(1) or p_match.group(2)) if p_match else None

                # Exclure les vieilles archives Fly4Free
                if any(yr in title for yr in ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"]):
                    continue

                dest_match = any(d in combined for d in destinations)
                is_error_fare = any(k in combined for k in ["error fare", "huge price drop", "insane", "cheap flights"])

                if (price and price <= max_budget) or (dest_match and (price is None or price <= (max_budget + 150))) or is_error_fare:
                    deal_id = hashlib.md5(link.encode("utf-8")).hexdigest()[:12]
                    deals.append({
                        "id": f"flight_f4f_{deal_id}",
                        "category": "flight",
                        "category_label": "Vol & Erreur de Prix",
                        "badge": "✈️ Vol",
                        "title": title,
                        "price": price or max_budget,
                        "price_str": f"{price} € A/R" if price else "Erreur de prix",
                        "location": "Europe / International",
                        "agency": "Fly4Free",
                        "url": link,
                        "image_url": "https://images.unsplash.com/photo-1506012787146-f92b2d7d6d96?w=600",
                        "description": BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:280],
                        "surface": None,
                        "rooms": None,
                        "date_detected": datetime.now(timezone.utc).isoformat(),
                    })
    except Exception as e:
        logger.warning(f"Avertissement Fly4Free : {e}")

    logger.info(f"✅ [Radar Vols] {len(deals)} pépites aériennes retenues.")
    return deals


# =============================================================
# MODULE 3 : 🚄 RADAR TRAINS & TGV (Ouigo, SNCF, Eurostar)
# =============================================================

def scrape_trains_module(config, page=None):
    """Scrape les ventes flash et billets de train à prix cassé."""
    train_cfg = config.get("radars", {}).get("trains", {})
    if not train_cfg.get("enabled", True):
        logger.info("⏸️ [Radar Trains] Désactivé dans la configuration.")
        return []

    max_budget = train_cfg.get("max_price", 25)
    routes = train_cfg.get("routes", [])
    logger.info(f"🚀 [Radar Trains] Actif - Seuil max : {max_budget} € | Trajets favoris : {len(routes)}")
    
    deals = []

    # Dealabs Transports / Billets de train
    try:
        url = "https://www.dealabs.com/rss/groupe/voyages"
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=12)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for it in root.findall(".//item"):
                title = it.findtext("title") or ""
                desc = it.findtext("description") or ""
                link = it.findtext("link") or ""
                combined = f"{title} {desc}".lower()

                # Vérifier si c'est un train
                is_train = any(k in combined for k in ["train", "tgv", "ouigo", "sncf", "eurostar", "intercités", "ter"])
                if not is_train:
                    continue

                p_match = re.search(r"(\d+)\s*€", title)
                price = int(p_match.group(1)) if p_match else None

                # Vérification des trajets favoris (ex: Nancy, Paris, Lyon, Marseille)
                route_matched = False
                for r in routes:
                    r_from = r.get("from", "").lower()
                    r_to = r.get("to", "").lower()
                    r_max = r.get("max_price", max_budget)
                    if (r_from in combined and r_to in combined) or r.get("name", "").lower() in combined:
                        if price is None or price <= r_max:
                            route_matched = True
                            break

                should_keep = False
                if price and price <= max_budget:
                    should_keep = True
                elif route_matched:
                    should_keep = True
                elif any(kw in combined for kw in ["vente flash", "billets à", "dès 10€", "dès 19€", "ouigo"]):
                    should_keep = True

                if should_keep:
                    img_match = re.search(r'<img[^>]+src="([^">]+)"', desc)
                    img_url = img_match.group(1) if img_match else None

                    deal_id = hashlib.md5(link.encode("utf-8")).hexdigest()[:12]
                    deals.append({
                        "id": f"train_dealabs_{deal_id}",
                        "category": "train",
                        "category_label": "Train & TGV",
                        "badge": "🚄 Train",
                        "title": title,
                        "price": price or max_budget,
                        "price_str": f"{price} €" if price else "Prix cassé",
                        "location": "Réseau SNCF / TGV / Ouigo",
                        "agency": "SNCF / Dealabs",
                        "url": link,
                        "image_url": img_url or "https://images.unsplash.com/photo-1474487548417-781cb71495f3?w=600",
                        "description": BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:280],
                        "surface": None,
                        "rooms": None,
                        "date_detected": datetime.now(timezone.utc).isoformat(),
                    })
    except Exception as e:
        logger.warning(f"Avertissement Radar Trains : {e}")

    logger.info(f"✅ [Radar Trains] {len(deals)} billets à prix cassé retenus.")
    return deals


# =============================================================
# ORCHESTRATEUR PRINCIPAL DU HUB
# =============================================================

def run_nexus_radar(send_notifications=True):
    """Exécute l'ensemble des modules de veille de Nexus Radar."""
    logger.info("═════════════════════════════════════════════════")
    logger.info("🛰️  NEXUS RADAR - Démarrage du cycle de veille...")
    logger.info("═════════════════════════════════════════════════")

    config = load_config()
    existing_items = load_annonces()
    existing_ids = {a["id"] for a in existing_items}
    existing_urls = {a.get("url") for a in existing_items if a.get("url")}

    all_scraped = []

    # 1. Module Immobilier (Saint-Martin)
    immo_items = scrape_immo_module(config)
    all_scraped.extend(immo_items)

    # 2. Module Vols & Erreurs de Prix
    flight_items = scrape_flights_module(config)
    all_scraped.extend(flight_items)

    # 3. Module Trains & TGV
    train_items = scrape_trains_module(config)
    all_scraped.extend(train_items)

    # Déduplication
    new_items = []
    seen_in_run = set()

    for item in all_scraped:
        item_id = item["id"]
        item_url = item.get("url")

        if item_id in seen_in_run or (item_url and item_url in seen_in_run):
            continue
        seen_in_run.add(item_id)
        if item_url:
            seen_in_run.add(item_url)

        if item_id not in existing_ids and (not item_url or item_url not in existing_urls):
            new_items.append(item)

    logger.info(f"📊 Bilan du scan : {len(all_scraped)} pépites analysées | {len(new_items)} NOUVELLES pépites !")

    # Notifications ntfy
    topic = config.get("ntfy_topic", "sxm-immo-alert-97150-x9q4m2")
    if send_notifications and new_items:
        logger.info(f"📲 Diffusion des alertes vers ntfy.sh/{topic}...")
        for item in new_items:
            send_ntfy_notification(topic, item)
            time.sleep(0.4)

    # Mise à jour et sauvegarde
    if new_items:
        updated = new_items + existing_items
        save_annonces(updated)
        logger.info(f"✨ {len(new_items)} pépites enregistrées dans data/annonces.json.")
    else:
        logger.info("ℹ️ Aucun nouvel élément détecté lors de ce cycle.")

    return new_items


if __name__ == "__main__":
    if "--test-notify" in sys.argv:
        cfg = load_config()
        top = cfg.get("ntfy_topic", "sxm-immo-alert-97150-x9q4m2")
        logger.info(f"Test de notification vers https://ntfy.sh/{top}")
        test_flight = {
            "category": "flight",
            "title": "A/R Paris <-> Saint-Martin (SXM) dès 380€ (Air Caraïbes)",
            "price": 380,
            "price_str": "380 € A/R",
            "location": "Saint-Martin (SXM)",
            "agency": "Nexus Radar Flash",
            "url": "https://www.google.com/travel/flights",
            "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600"
        }
        send_ntfy_notification(top, test_flight)
        print("Notification de test envoyée.")
    else:
        run_nexus_radar(send_notifications=True)
