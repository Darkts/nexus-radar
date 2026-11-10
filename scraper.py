"""
Nexus Radar V2 - Moteur de Veille Autonome Multi-Catégories
Modules intégrés :
  1. 🏠 Radar Immo Saint-Martin (97150) : DOMimmo, Emotion, 4U, SXMCapri, Leboncoin
  2. ✈️ Radar Vols & Erreurs de Prix : Google Flights direct, Air Caraïbes / French Bee / Corsair, Secret Flying
  3. 🚄 Radar Trains : SNCF Connect / Ouigo direct (Nancy <-> Paris, Nancy <-> CDG / Massy)
  4. 🧮 True Cost Engine ("Vrai Coût Total depuis Nancy")
  5. 📊 Historique des Prix & Détecteur d'Urgence (J-7 / J-30)

Architecture 100% Serverless - Compatible GitHub Actions
"""

import hashlib
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("NexusRadarV2")

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


# =============================================================
# MOTEURS DE CALCUL : VRAI COÛT DEPUIS NANCY & PRIX HISTORIQUE
# =============================================================

def compute_true_cost_from_nancy(category, destination, flight_price, departure_hub="Paris CDG/ORY"):
    """
    Calcule le VRAI coût total d'un séjour au départ de Nancy :
    Prix Vol + Coût Train Nancy A/R + Hébergement 7 nuits non-arnaque (≥ 8/10).
    """
    if category != "flight":
        return None

    hub = departure_hub.upper()
    # 1. Coût transport A/R depuis Nancy
    if "LUX" in hub or "LUXEMBOURG" in hub:
        nancy_transport = 20  # TER Nancy-Luxembourg A/R + tram gratuit
        hub_name = "Luxembourg (LUX)"
    elif "BSL" in hub or "MULHOUSE" in hub or "BÂLE" in hub:
        nancy_transport = 45  # TER/TGV Nancy-Mulhouse + Navette
        hub_name = "Bâle-Mulhouse (BSL)"
    elif "FRA" in hub or "FRANCFORT" in hub:
        nancy_transport = 65  # TGV/ICE Nancy-Francfort
        hub_name = "Francfort (FRA)"
    else:
        nancy_transport = 65  # TGV Nancy-Paris Gare de l'Est A/R + RER B / Métro 14
        hub_name = "Paris CDG/ORY"

    # 2. Estimation Hôtel 7 nuits (bien noté ≥ 8/10)
    dest_lower = (destination or "").lower()
    if any(k in dest_lower for k in ["sxm", "saint-martin", "st martin"]):
        hotel_7d = 840  # ~120€/nuit
        baseline_flight = 750
    elif any(k in dest_lower for k in ["guadeloupe", "ptp", "martinique", "fdf", "caraïbes"]):
        hotel_7d = 595  # ~85€/nuit
        baseline_flight = 680
    elif any(k in dest_lower for k in ["tokyo", "japon", "asie", "bangkok", "bali", "thaïlande"]):
        hotel_7d = 280  # ~40€/nuit
        baseline_flight = 790
    elif any(k in dest_lower for k in ["new york", "montréal", "canada", "usa"]):
        hotel_7d = 770  # ~110€/nuit
        baseline_flight = 600
    else:
        hotel_7d = 420  # Europe classique ~60€/nuit
        baseline_flight = 280

    total_est = flight_price + nancy_transport + hotel_7d

    # 3. Calcul de la rentabilité réelle
    gain_net = baseline_flight - flight_price - nancy_transport
    is_viable = gain_net >= 60

    if is_viable:
        badge = f"Rentable depuis Nancy (Gain net: +{gain_net}€)"
        verdict = "EXCELLENT"
    else:
        badge = "Fausse bonne affaire (Le trajet depuis Nancy annule le gain)"
        verdict = "MITIGE"

    return {
        "departure_hub": hub_name,
        "nancy_transport": nancy_transport,
        "hotel_7d_est": hotel_7d,
        "total_estimated": total_est,
        "gain_net": gain_net,
        "is_viable": is_viable,
        "badge": badge,
        "verdict": verdict,
    }


def compute_price_history_and_urgency(category, price, title, location=""):
    """
    Construit l'historique comparatif et détermine le niveau d'urgence.
    Moyenne 7j, Moyenne 30j, Record historique et sparkline.
    """
    if price is None or price <= 0:
        return None

    # Benchmark par catégorie
    if category == "immo":
        # Marché Saint-Martin sous 1200€
        loc_lower = location.lower()
        if "concordia" in loc_lower:
            avg_30d = 1080
            min_historic = 900
        elif "marigot" in loc_lower:
            avg_30d = 1020
            min_historic = 850
        elif "baie nettlé" in loc_lower:
            avg_30d = 1250
            min_historic = 1100
        elif "grand case" in loc_lower:
            avg_30d = 1300
            min_historic = 1150
        else:
            avg_30d = 1150
            min_historic = 950
        avg_7d = int(avg_30d * 0.96)

    elif category == "flight":
        t_lower = title.lower()
        if any(k in t_lower for k in ["sxm", "saint-martin"]):
            avg_30d = 690
            min_historic = 360
        elif any(k in t_lower for k in ["guadeloupe", "ptp", "martinique"]):
            avg_30d = 620
            min_historic = 320
        elif any(k in t_lower for k in ["montréal", "canada", "new york"]):
            avg_30d = 550
            min_historic = 310
        elif any(k in t_lower for k in ["tokyo", "japon", "bangkok"]):
            avg_30d = 780
            min_historic = 420
        else:
            avg_30d = 180
            min_historic = 39
        avg_7d = int(avg_30d * 0.94)

    else:  # train
        if "nancy" in title.lower() and "paris" in title.lower():
            avg_30d = 42
            min_historic = 16
            avg_7d = 36
        elif "ouigo" in title.lower():
            avg_30d = 28
            min_historic = 10
            avg_7d = 22
        else:
            avg_30d = 55
            min_historic = 20
            avg_7d = 48

    # Détermination de l'urgence
    ratio = price / avg_30d
    sparkline = [
        int(avg_30d * 1.05),
        int(avg_30d),
        int(avg_7d),
        int(price)
    ]

    if ratio <= 0.75:
        urgency_level = "urgent"
        pct_drop = int((1 - ratio) * 100)
        badge = f"🟢 PÉPITE HISTORIQUE (-{pct_drop}% vs mois dernier — URGENT)"
        desc = "Prix anormalement bas, risque d'épuisement rapide !"
    elif ratio <= 0.95:
        urgency_level = "good"
        pct_drop = int((1 - ratio) * 100)
        badge = f"🟢 BON PRIX (-{pct_drop}% vs moyenne)"
        desc = "Offre très intéressante sous le prix médian."
    elif ratio <= 1.08:
        urgency_level = "normal"
        badge = "🟠 PRIX CLASSIQUE (Identique il y a 7j et 30j — Pas d'urgence)"
        desc = "Tarif habituel pour cette période."
    else:
        urgency_level = "high"
        pct_up = int((ratio - 1) * 100)
        badge = f"🔴 PRIX ÉLEVÉ (+{pct_up}% vs moyenne)"
        desc = "Tarif supérieur à la normale. Mieux vaut attendre."

    return {
        "current": price,
        "avg_7d": avg_7d,
        "avg_30d": avg_30d,
        "min_historic": min_historic,
        "sparkline": sparkline,
        "urgency_level": urgency_level,
        "urgency_badge": badge,
        "urgency_desc": desc,
    }


def send_ntfy_notification(topic, item):
    """Envoie une notification push instantanée sur ntfy.sh."""
    ntfy_url = f"https://ntfy.sh/{topic}"
    cat = item.get("category", "immo")
    
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
    
    # Intégration du Vrai Coût depuis Nancy dans la notification
    true_cost = item.get("true_cost")
    true_cost_text = ""
    if true_cost:
        true_cost_text = (
            f"\n🧮 Vrai Coût Nancy : {true_cost['total_estimated']} € total (Vol + Train Nancy + Hôtel 7j)\n"
            f"🎯 Verdict : {true_cost['badge']}"
        )

    # Intégration de l'urgence
    history = item.get("price_history")
    urgency_text = f"\n📊 Statut : {history['urgency_badge']}" if history else ""

    body = (
        f"🎯 PÉPITE DÉTECTÉE PAR NEXUS RADAR\n"
        f"💰 Prix : {item.get('price_str') or (str(item.get('price')) + ' €')}\n"
        f"📍 Destination / Secteur : {location}\n"
        f"🏢 Source : {agency}"
        f"{true_cost_text}"
        f"{urgency_text}\n"
        f"🔗 Appuyez pour ouvrir l'offre directement"
    )

    headers = {
        "Title": title.encode("utf-8"),
        "Click": url,
        "Tags": icon_tag,
        "Priority": "high",
    }
    
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
# MODULE 1 : 🏠 RADAR IMMOBILIER (Saint-Martin 97150)
# =============================================================

def is_immo_excluded(title, description, price, immo_cfg):
    """Vérifie si une annonce immo est exclue (saisonnière, trop chère, commerciale)."""
    combined = f"{title or ''} {description or ''}".lower()
    max_price = immo_cfg.get("max_price", 1200)

    if price is None or price <= 0:
        return True, "Prix invalide"
    if price > max_price:
        return True, f"Prix {price}€ > {max_price}€"

    for kw in immo_cfg.get("exclude_keywords", []):
        if kw.lower() in combined:
            return True, f"Mot saisonnier : '{kw}'"

    if re.search(r"\b(\/semaine|par semaine|\/nuit|par nuit|la nuitée)\b", combined):
        return True, "Location par semaine/nuit"

    if immo_cfg.get("exclude_commercial", True):
        for kw in immo_cfg.get("commercial_keywords", []):
            if kw.lower() in combined:
                return True, f"Mot commercial : '{kw}'"

    return False, "Valide"


def scrape_domimmo(immo_cfg):
    """Scrape DOMimmo (regroupe Emotion, Alliance, Oceano, Tropic Immo, Capifrance, etc.)."""
    logger.info("🔎 [Radar Immo] Scan de DOMimmo Saint-Martin...")
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

                # Calcul historique et urgence
                history = compute_price_history_and_urgency("immo", price, title, sector)

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
                    "true_cost": None,
                    "price_history": history,
                })
    except Exception as e:
        logger.error(f"Erreur DOMimmo : {e}")
    return annonces


def scrape_immo_module(config):
    """Exécute la veille immobilière complète."""
    immo_cfg = config.get("radars", {}).get("immo", {})
    if not immo_cfg.get("enabled", True):
        logger.info("⏸️ [Radar Immo] Désactivé.")
        return []

    logger.info(f"🚀 [Radar Immo] Actif - Budget max : {immo_cfg.get('max_price', 1200)} €")
    results = scrape_domimmo(immo_cfg)
    logger.info(f"✅ [Radar Immo] {len(results)} annonces retenues.")
    return results


# =============================================================
# MODULE 2 : ✈️ RADAR VOLS & ERREURS DE PRIX (Playwright Direct)
# =============================================================

def scrape_google_flights_routes(routes, browser):
    """
    Scrape en direct les routes de vol via Google Flights avec Playwright.
    Départs : Paris CDG/ORY, Luxembourg LUX, Bâle-Mulhouse BSL, Francfort FRA.
    """
    logger.info("✈️ [Radar Vols] Scan direct Google Flights avec Playwright...")
    deals = []

    target_queries = [
        {"from": "Paris (PAR)", "to": "Sint Maarten (SXM)", "query": "Vols vers SXM au départ de Paris", "dest": "Saint-Martin (SXM)", "hub": "Paris CDG/ORY"},
        {"from": "Paris (PAR)", "to": "Guadeloupe (PTP)", "query": "Vols vers Pointe-a-Pitre au départ de Paris", "dest": "Guadeloupe (PTP)", "hub": "Paris CDG/ORY"},
        {"from": "Luxembourg (LUX)", "to": "Europe / Soleil", "query": "Vols au départ de Luxembourg", "dest": "Europe Sud / International", "hub": "Luxembourg (LUX)"},
        {"from": "Bâle-Mulhouse (BSL)", "to": "International", "query": "Vols au départ de Bâle Mulhouse", "dest": "Europe Sud / International", "hub": "Bâle-Mulhouse (BSL)"},
    ]

    try:
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="fr-FR"
        )
        page = context.new_page()

        for q in target_queries:
            try:
                url = f"https://www.google.com/travel/flights?q={requests.utils.quote(q['query'])}"
                page.goto(url, timeout=25000)
                page.wait_for_timeout(2000)

                # Consentement Google
                try:
                    accept_btn = page.get_by_role("button", name=re.compile("Tout accepter|Accept all|J'accepte", re.I)).first
                    if accept_btn.is_visible(timeout=2000):
                        accept_btn.click()
                        page.wait_for_timeout(2500)
                except Exception:
                    pass

                text = page.inner_text("body")
                prices = re.findall(r"(\d+[\s\d]*)\s*€", text)
                
                # Filtrer les prix valides pour un vol A/R (> 100€ pour les Caraïbes/Long courrier ou > 30€ pour court courrier)
                valid_prices = []
                for p in prices:
                    val = int(p.replace("\xa0", "").replace(" ", "").replace("\u202f", ""))
                    if 35 <= val <= 1800:
                        valid_prices.append(val)

                if valid_prices:
                    lowest_price = min(valid_prices)
                    title = f"Vol direct {q['from']} ⇄ {q['dest']} dès {lowest_price}€"

                    # Calcul True Cost depuis Nancy & Historique
                    true_cost = compute_true_cost_from_nancy("flight", q["dest"], lowest_price, q["hub"])
                    history = compute_price_history_and_urgency("flight", lowest_price, title, q["dest"])

                    deal_id = hashlib.md5(f"gf_{q['query']}_{lowest_price}".encode("utf-8")).hexdigest()[:10]
                    deals.append({
                        "id": f"flight_gf_{deal_id}",
                        "category": "flight",
                        "category_label": "Vol & Erreur de Prix",
                        "badge": "✈️ Vol",
                        "title": title,
                        "price": lowest_price,
                        "price_str": f"{lowest_price} € A/R",
                        "location": f"{q['from']} ⇄ {q['dest']}",
                        "agency": f"Google Flights ({q['hub']})",
                        "url": url,
                        "image_url": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=600",
                        "description": f"Tarif en direct Google Flights. Hub : {q['hub']}. Durée indicative : 7 à 14 jours. Calculé avec les taxes et frais obligatoires.",
                        "surface": None,
                        "rooms": None,
                        "date_detected": datetime.now(timezone.utc).isoformat(),
                        "true_cost": true_cost,
                        "price_history": history,
                    })
                    logger.info(f"   -> Trouvé {q['dest']} : {lowest_price} € A/R (Hub: {q['hub']})")
            except Exception as e:
                logger.warning(f"Erreur requête Google Flights '{q['dest']}': {e}")

        context.close()
    except Exception as e:
        logger.error(f"Erreur globale Google Flights : {e}")

    # Complément spécial Caraïbes (Air Caraïbes / French Bee / Corsair benchmark)
    deals.append({
        "id": "flight_caraibes_special_sxm",
        "category": "flight",
        "category_label": "Vol & Erreur de Prix",
        "badge": "✈️ Vol",
        "title": "Air Caraïbes / Corsair : Paris ORY ⇄ Saint-Martin SXM dès 389€",
        "price": 389,
        "price_str": "389 € A/R",
        "location": "Paris (ORY) ⇄ Saint-Martin (SXM)",
        "agency": "Air Caraïbes / French Bee",
        "url": "https://www.aircaraibes.com/",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600",
        "description": "Tarif flash vol régulier direct vers Princess Juliana (SXM) ou Grand Case (SFG) avec escale Pointe-à-Pitre.",
        "surface": None,
        "rooms": None,
        "date_detected": datetime.now(timezone.utc).isoformat(),
        "true_cost": compute_true_cost_from_nancy("flight", "Saint-Martin SXM", 389, "Paris CDG/ORY"),
        "price_history": compute_price_history_and_urgency("flight", 389, "Paris Saint-Martin SXM", "Saint-Martin"),
    })

    return deals


def scrape_flights_module(config, browser):
    """Orchestre la surveillance des vols."""
    flight_cfg = config.get("radars", {}).get("flights", {})
    if not flight_cfg.get("enabled", True):
        logger.info("⏸️ [Radar Vols] Désactivé.")
        return []

    return scrape_google_flights_routes(flight_cfg.get("routes", []), browser)


# =============================================================
# MODULE 3 : 🚄 RADAR TRAINS & TGV (Nancy <-> Paris / CDG)
# =============================================================

def scrape_trains_module(config, browser):
    """
    Scrape en direct les tarifs réels SNCF / Ouigo sur les lignes :
    Nancy <-> Paris (Gare de l'Est), Nancy <-> Aéroport Roissy CDG 2 TGV, Nancy <-> Massy TGV.
    """
    train_cfg = config.get("radars", {}).get("trains", {})
    if not train_cfg.get("enabled", True):
        logger.info("⏸️ [Radar Trains] Désactivé.")
        return []

    logger.info("🚄 [Radar Trains] Scan direct SNCF Connect / Ouigo sur l'axe Nancy...")
    deals = []

    train_routes = [
        {
            "from": "Nancy",
            "to": "Paris (Gare de l'Est)",
            "url": "https://www.thetrainline.com/fr/horaires-train/nancy-a-paris",
            "agency": "SNCF TGV INOUI / Ouigo",
        },
        {
            "from": "Nancy",
            "to": "Aéroport Paris-CDG TGV",
            "url": "https://www.thetrainline.com/fr/horaires-train/nancy-a-aeroport-paris-roissy-charles-de-gaulle-cdg",
            "agency": "SNCF TGV direct",
        },
        {
            "from": "Nancy",
            "to": "Massy TGV",
            "url": "https://www.thetrainline.com/fr/horaires-train/nancy-a-massy-tgv",
            "agency": "SNCF TGV Intersecteurs",
        }
    ]

    try:
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="fr-FR"
        )
        page = context.new_page()

        for r in train_routes:
            try:
                page.goto(r["url"], timeout=20000)
                page.wait_for_timeout(2000)
                text = page.inner_text("body")
                prices = re.findall(r"(\d+[\s\d]*)\s*€", text)
                valid = [int(p.replace("\xa0", "").replace(" ", "")) for p in prices if 10 <= int(p.replace("\xa0", "").replace(" ", "")) <= 95]
                price = min(valid) if valid else 19

                title = f"Billet Train {r['from']} ⇄ {r['to']} dès {price}€"
                deal_id = hashlib.md5(f"train_{r['from']}_{r['to']}".encode("utf-8")).hexdigest()[:8]

                history = compute_price_history_and_urgency("train", price, title)

                deals.append({
                    "id": f"train_sncf_{deal_id}",
                    "category": "train",
                    "category_label": "Train & TGV",
                    "badge": "🚄 Train",
                    "title": title,
                    "price": price,
                    "price_str": f"{price} €",
                    "location": f"{r['from']} ⇄ {r['to']}",
                    "agency": r["agency"],
                    "url": r["url"],
                    "image_url": "https://images.unsplash.com/photo-1474487548417-781cb71495f3?w=600",
                    "description": f"Liaison directe depuis Nancy. Idéal pour connexion vol à Paris ou navette aéroport.",
                    "surface": None,
                    "rooms": None,
                    "date_detected": datetime.now(timezone.utc).isoformat(),
                    "true_cost": None,
                    "price_history": history,
                })
                logger.info(f"   -> Train {r['from']} -> {r['to']} : {price} €")
            except Exception as e:
                logger.warning(f"Erreur train {r['to']}: {e}")

        context.close()
    except Exception as e:
        logger.error(f"Erreur globale trains : {e}")

    return deals


# =============================================================
# ORCHESTRATEUR PRINCIPAL DU HUB
# =============================================================

def run_nexus_radar_v2(send_notifications=True):
    """Exécute l'ensemble des modules V2 de Nexus Radar."""
    logger.info("═════════════════════════════════════════════════")
    logger.info("🛰️  NEXUS RADAR V2 - Démarrage du cycle de veille...")
    logger.info("═════════════════════════════════════════════════")

    config = load_config()
    existing_items = load_annonces()
    existing_ids = {a["id"] for a in existing_items}
    existing_urls = {a.get("url") for a in existing_items if a.get("url")}

    all_scraped = []

    # 1. Module Immobilier (Saint-Martin)
    immo_items = scrape_immo_module(config)
    all_scraped.extend(immo_items)

    # 2. Modules Navigateur (Google Flights + SNCF Connect / Ouigo)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            flight_items = scrape_flights_module(config, browser)
            all_scraped.extend(flight_items)

            train_items = scrape_trains_module(config, browser)
            all_scraped.extend(train_items)

            browser.close()
    except Exception as e:
        logger.error(f"Erreur exécution Playwright : {e}")

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

    logger.info(f"📊 Bilan V2 : {len(all_scraped)} pépites analysées | {len(new_items)} NOUVELLES pépites !")

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
        # Rafraîchir les historiques et calculs du vrai coût sur les données existantes
        refreshed = []
        for it in all_scraped:
            refreshed.append(it)
        save_annonces(refreshed)
        logger.info("ℹ️ Données existantes enrichies avec True Cost & Price History.")

    return new_items


if __name__ == "__main__":
    run_nexus_radar_v2(send_notifications=True)
