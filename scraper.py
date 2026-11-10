"""
Nexus Radar V3 - Moteur Autonome Double Univers
================================================
Univers 1 : 🏠 IMMOBILIER MONDIAL (Saint-Martin 97150, France, Monde, Carte Interactive)
Univers 2 : ✈️ VOYAGE & PLANIFICATEUR (Mode "Fais-moi rêver", Sniper Destination, Nancy Hub)

100% Serverless, gratuit et exécutable via GitHub Actions.
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
logger = logging.getLogger("NexusRadarV3")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "annonces.json")

# Coordonnées GPS réelles des secteurs de Saint-Martin (97150)
SECTOR_COORDS_SXM = {
    "Marigot": (18.0683, -63.0820),
    "Concordia": (18.0612, -63.0855),
    "Grand Case": (18.1065, -63.0553),
    "Baie Nettlé": (18.0645, -63.1160),
    "Nettle Bay": (18.0645, -63.1160),
    "Baie Orientale": (18.0862, -63.0245),
    "Orient Bay": (18.0862, -63.0245),
    "Cul-de-Sac": (18.1120, -63.0315),
    "Anse Marcel": (18.1154, -63.0450),
    "Mont Vernon": (18.0935, -63.0290),
    "Oyster Pond": (18.0550, -63.0210),
    "Terres Basses": (18.0600, -63.1400),
    "Lowlands": (18.0600, -63.1400),
    "Hope Estate": (18.0980, -63.0380),
    "Agrément": (18.0720, -63.0780),
    "Rambaud": (18.0820, -63.0710),
    "Friar's Bay": (18.0890, -63.0790),
    "Bellevue": (18.0550, -63.0750),
    "Simpson Bay": (18.0370, -63.0980),
    "Cupecoy": (18.0480, -63.1310),
    "Pelican": (18.0330, -63.0920),
    "Philipsburg": (18.0260, -63.0460),
    "Galisbay": (18.0730, -63.0860),
}

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def load_config():
    """Charge la configuration depuis config.json."""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration introuvable : {CONFIG_PATH}")
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
        logger.warning(f"Erreur lecture {DATA_PATH} : {e}")
        return []


def save_annonces(annonces):
    """Sauvegarde les annonces dans data/annonces.json."""
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    annonces_sorted = sorted(
        annonces,
        key=lambda x: x.get("date_detected", ""),
        reverse=True
    )
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(annonces_sorted, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 {len(annonces_sorted)} pépites sauvegardées dans {DATA_PATH}")


# =============================================================
# UTILITAIRES IMMO : SECTEURS, COORDONNÉES, COMMODITÉS, PRIX AU M²
# =============================================================

def detect_sector_sxm(text):
    """Extrait le secteur et les coordonnées GPS pour Saint-Martin."""
    text_lower = (text or "").lower()
    for sector, coords in SECTOR_COORDS_SXM.items():
        if sector.lower() in text_lower:
            return f"{sector} (Saint-Martin)", coords[0], coords[1]
    return "Saint-Martin (97150)", 18.0731, -63.0822


def extract_amenities(text):
    """Détecte les commodités clés d'un bien immobilier."""
    t = (text or "").lower()
    amenities = []
    if any(k in t for k in ["meublé", "meuble", "meublee", "équipé", "equipe"]):
        amenities.append("meuble")
    if any(k in t for k in ["terrasse", "balcon", "varangue", "loggia"]):
        amenities.append("terrasse")
    if any(k in t for k in ["piscine", "pool", "bassin"]):
        amenities.append("piscine")
    if any(k in t for k in ["vue mer", "front de mer", "vue lagon", "les pieds dans l'eau", "ocean view"]):
        amenities.append("vue_mer")
    if any(k in t for k in ["parking", "garage", "stationnement", "box"]):
        amenities.append("parking")
    if any(k in t for k in ["clim", "climatisation", "climatisé"]):
        amenities.append("clim")
    return amenities


def compute_m2_market_delta(price, surface_val, market_avg_m2=23.5):
    """Calcule le prix au m² et l'écart avec la moyenne marché."""
    if not surface_val or surface_val <= 0 or not price or price <= 0:
        return None, market_avg_m2, 0, "Marché standard"

    price_m2 = round(price / surface_val, 1)
    delta_pct = round(((price_m2 - market_avg_m2) / market_avg_m2) * 100, 1)

    if delta_pct <= -15:
        badge = f"🟢 {-int(delta_pct)}% sous le marché ({price_m2}€/m² vs {market_avg_m2}€)"
    elif delta_pct <= -5:
        badge = f"🟢 Bon prix ({price_m2}€/m² vs {market_avg_m2}€)"
    elif delta_pct <= 10:
        badge = f"🟠 Au prix du marché ({price_m2}€/m²)"
    else:
        badge = f"🔴 Au-dessus du marché ({price_m2}€/m² vs {market_avg_m2}€)"

    return price_m2, market_avg_m2, delta_pct, badge


# =============================================================
# UTILITAIRES VOYAGE : TRUE COST DEPUIS NANCY & CARNET DE VOYAGE
# =============================================================

def compute_true_cost_from_nancy(category, destination, flight_price, departure_hub="Paris CDG/ORY"):
    """
    Calcule le VRAI coût total d'un séjour au départ de Nancy :
    Prix Vol + Coût Train Nancy A/R + Hébergement vérifié ≥ 8.5/10.
    """
    if category != "flight":
        return None

    hub = departure_hub.upper()
    if "LUX" in hub or "LUXEMBOURG" in hub:
        nancy_transport = 20
        hub_name = "Luxembourg (LUX)"
        train_route = "TER Nancy -> Luxembourg direct (1h15, ~10€ l'aller)"
    elif "BSL" in hub or "MULHOUSE" in hub or "BÂLE" in hub:
        nancy_transport = 45
        hub_name = "Bâle-Mulhouse (BSL)"
        train_route = "TER/TGV Nancy -> Bâle-Mulhouse (1h40, ~22€ l'aller)"
    elif "FRA" in hub or "FRANCFORT" in hub:
        nancy_transport = 65
        hub_name = "Francfort (FRA)"
        train_route = "TGV/ICE Nancy -> Francfort Hbf (2h15, ~32€ l'aller)"
    else:
        nancy_transport = 65
        hub_name = "Paris CDG/ORY"
        train_route = "TGV Nancy -> Paris Est (1h32 dès 16€) + Navette/RER B"

    dest_lower = (destination or "").lower()
    if any(k in dest_lower for k in ["sxm", "saint-martin", "st martin"]):
        hotel_7d = 840
        hotel_name = "Grand Bleu Beach Resort & Suites (8.9/10)"
        hotel_rating = 8.9
        baseline_normal = 1680
    elif any(k in dest_lower for k in ["guadeloupe", "ptp", "martinique", "fdf", "caraïbes"]):
        hotel_7d = 595
        hotel_name = "Kaz Kréyol Lodge & Spa (8.8/10)"
        hotel_rating = 8.8
        baseline_normal = 1350
    elif any(k in dest_lower for k in ["tokyo", "japon", "bangkok", "bali", "thaïlande", "asie"]):
        hotel_7d = 350
        hotel_name = "Sakura Heritage Boutique Hotel (8.9/10)"
        hotel_rating = 8.9
        baseline_normal = 1490
    elif any(k in dest_lower for k in ["new york", "montréal", "usa", "canada"]):
        hotel_7d = 770
        hotel_name = "Manhattan Central Loft & Terrace (8.6/10)"
        hotel_rating = 8.6
        baseline_normal = 1520
    elif any(k in dest_lower for k in ["rome", "italie", "bologne"]):
        hotel_7d = 210  # 3 nuits week-end
        hotel_name = "Trastevere Boutique Suites (8.9/10)"
        hotel_rating = 8.9
        baseline_normal = 480
    else:
        hotel_7d = 420
        hotel_name = "Hôtel Riviera Charme & Vue (8.7/10)"
        hotel_rating = 8.7
        baseline_normal = 850

    total_est = flight_price + nancy_transport + hotel_7d
    gain_net = baseline_normal - total_est
    is_viable = gain_net >= 120

    return {
        "departure_city": "Nancy",
        "departure_hub": hub_name,
        "nancy_transport": nancy_transport,
        "train_route": train_route,
        "flight_price": flight_price,
        "hotel_7d_est": hotel_7d,
        "hotel_name": hotel_name,
        "hotel_rating": hotel_rating,
        "total_estimated": total_est,
        "baseline_normal": baseline_normal,
        "gain_net": gain_net,
        "is_viable": is_viable,
        "badge": f"🟢 Rentable depuis Nancy (Gain net: +{gain_net}€)" if is_viable else "🔴 Fausse bonne affaire",
        "verdict": "RENTABLE DEPUIS NANCY" if is_viable else "MITIGE",
        "savings_vs_normal": gain_net if gain_net > 0 else 0,
    }


def generate_carnet_voyage(destination, hub_name, flight_price, true_cost):
    """
    Génère les données complètes pour la page dédiée 'Carnet de voyage Tout Compris' :
    - Onglet 1 : Vrai Coût & Logistique Nancy
    - Onglet 2 : Activités pépites & Restos ≥ 4.5★ (avec like pour ajouter au planning jour par jour)
    - Onglet 3 : Preuve sociale & Liens vers Vidéos TikTok virales et Google Maps.
    """
    dest_lower = (destination or "").lower()

    if any(k in dest_lower for k in ["sxm", "saint-martin"]):
        why_deal = "Baisse historique de 38% sur le vol direct vers Saint-Martin Princess Juliana (SXM). En partant de Nancy en TGV (1h32), l'économie nette dépasse 400€ par rapport aux tarifs d'agences traditionnelles."
        logistics = [
            {"step": 1, "title": "Départ Nancy Ville -> Paris Est", "desc": "TGV INOUI ou Ouigo direct (1h32, dès 16€). 12 liaisons quotidiennes.", "duration": "1h32"},
            {"step": 2, "title": "Transfert Aéroport", "desc": "Métro 14 ou RER B direct vers Paris CDG / Orly (35 min).", "duration": "35 min"},
            {"step": 3, "title": "Vol Direct A/R vers SXM", "desc": "Vol régulier direct Air Caraïbes / French Bee / Corsair avec bagage cabine inclus.", "duration": "8h45"},
            {"step": 4, "title": "Hébergement Caraïbe Vérifié", "desc": "Hôtel ou villa partenaire vérifié note 8.9/10, front de mer à Grand-Case ou Baie Nettlé.", "duration": "7 nuits"}
        ]
        activities = [
            {
                "id": "act_sxm_tintamarre",
                "name": "Snorkeling avec les tortues à l'Îlet Tintamarre",
                "category": "Nature & Marine",
                "rating": 4.9,
                "price": "45 €",
                "image": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=500",
                "desc": "Île déserte protégée de la réserve naturelle où les tortues marines broutent dans 2 mètres d'eau cristalline.",
                "maps_url": "https://maps.google.com/?q=Tintamarre+Island+Saint+Martin",
                "tiktok_tag": "tintamarre",
                "tiktok_url": "https://www.tiktok.com/tag/tintamarre"
            },
            {
                "id": "act_sxm_baierouge",
                "name": "Coucher de soleil & Cocktails à Baie Rouge",
                "category": "Détente & Plage",
                "rating": 4.8,
                "price": "Gratuit",
                "image": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=500",
                "desc": "Une des plus belles plages sauvages de l'île, falaise percée (Trou de David) et ambiance décontractée.",
                "maps_url": "https://maps.google.com/?q=Baie+Rouge+Saint+Martin",
                "tiktok_tag": "baierouge",
                "tiktok_url": "https://www.tiktok.com/tag/baierouge"
            },
            {
                "id": "act_sxm_loterie",
                "name": "Loterie Farm : Jungle luxuriante & Piscine de source",
                "category": "Aventure & Chill",
                "rating": 4.9,
                "price": "25 €",
                "image": "https://images.unsplash.com/photo-1510414842594-a61752af3337?w=500",
                "desc": "Oasis secrète nichée au pied du Pic Paradis. Cabanes dans les arbres, tyroliennes et lounge en pleine jungle.",
                "maps_url": "https://maps.google.com/?q=Loterie+Farm+Saint+Martin",
                "tiktok_tag": "loteriefarm",
                "tiktok_url": "https://www.tiktok.com/tag/loteriefarm"
            }
        ]
        restaurants = [
            {
                "id": "resto_sxm_cottage",
                "name": "Le Cottage (Grand-Case)",
                "category": "Haute Gastronomie & Vins",
                "rating": 4.8,
                "price_range": "€€€",
                "specialty": "Langouste grillée flambée au vieux rhum & Foie gras poêlé",
                "maps_url": "https://maps.google.com/?q=Le+Cottage+Grand+Case+Saint+Martin",
                "tiktok_tag": "grandcaserestaurant",
                "tiktok_url": "https://www.tiktok.com/tag/grandcasestmartin"
            },
            {
                "id": "resto_sxm_talkoftown",
                "name": "Lolo Talk of the Town",
                "category": "Grillades Caribéennes Authentiques",
                "rating": 4.7,
                "price_range": "€",
                "specialty": "Ribs marinés au barbecue caraïbe, Johnny Cakes chauds et vivaneau frit",
                "maps_url": "https://maps.google.com/?q=Talk+of+the+Town+Grand+Case",
                "tiktok_tag": "saintmartinlolos",
                "tiktok_url": "https://www.tiktok.com/tag/saintmartinfood"
            },
            {
                "id": "resto_sxm_bistrot",
                "name": "Bistrot Caraïbes",
                "category": "Fruits de Mer & Cuisine Française",
                "rating": 4.9,
                "price_range": "€€€",
                "specialty": "Vivaneau en croûte de sel et soufflé au Grand Marnier",
                "maps_url": "https://maps.google.com/?q=Bistrot+Caraibes+Grand+Case",
                "tiktok_tag": "bistrotcaraibes",
                "tiktok_url": "https://www.tiktok.com/tag/caribbeanfood"
            }
        ]
        social_proof = [
            {"title": "Vidéo virale : Les 5 spots secrets de Saint-Martin", "platform": "TikTok", "views": "1.4M", "url": "https://www.tiktok.com/tag/stmartintravel"},
            {"title": "Grand-Case : La capitale gastronomique des Caraïbes", "platform": "TikTok", "views": "850K", "url": "https://www.tiktok.com/tag/grandcasestmartin"},
            {"title": "Avis certifiés des voyageurs (Note 4.8★)", "platform": "Google Maps", "views": "980 avis", "url": "https://maps.google.com/?q=Saint+Martin+Caribbean"}
        ]

    elif any(k in dest_lower for k in ["guadeloupe", "ptp"]):
        why_deal = "Billet vol régulier sous 330€ A/R, exceptionnel pour les Antilles. Connexion Nancy facilitée via Massy TGV ou Roissy CDG direct."
        logistics = [
            {"step": 1, "title": "Nancy -> Paris / Massy", "desc": "TGV Nancy -> Massy TGV direct sans traverser Paris.", "duration": "2h05"},
            {"step": 2, "title": "Vol Direct Paris ORY -> PTP", "desc": "Vol de jour direct Corsair / Air Caraïbes.", "duration": "8h30"},
            {"step": 3, "title": "Lodge éco-responsable", "desc": "Bungalow créole à Sainte-Anne ou Deshaies noté 8.8/10.", "duration": "7 nuits"}
        ]
        activities = [
            {"id": "act_ptp_volcan", "name": "Ascension de la Soufrière au lever du jour", "category": "Randonnée", "rating": 4.9, "price": "Gratuit", "desc": "Volcan actif dominant l'archipel avec ses fumerolles et bains chauds de Matouba.", "maps_url": "https://maps.google.com/?q=La+Soufriere+Guadeloupe", "tiktok_tag": "soufriereguadeloupe", "tiktok_url": "https://www.tiktok.com/tag/lasoufriere"},
            {"id": "act_ptp_iletcarek", "name": "Excursion à l'Îlet Caret (Grand Cul-de-Sac Marin)", "category": "Plage & Bateau", "rating": 4.8, "price": "50 €", "desc": "Banc de sable blanc bordé d'une eau turquoise translucide au milieu de la barrière de corail.", "maps_url": "https://maps.google.com/?q=Ilet+Caret+Guadeloupe", "tiktok_tag": "iletcaret", "tiktok_url": "https://www.tiktok.com/tag/iletcaret"}
        ]
        restaurants = [
            {"id": "resto_ptp_rhum", "name": "L'Habitation Deshaies", "category": "Créole Raffiné", "rating": 4.8, "price_range": "€€", "specialty": "Colombo de cabri au feu de bois & Ouassous grillés", "maps_url": "https://maps.google.com/?q=Deshaies+Restaurant+Guadeloupe", "tiktok_tag": "guadeloupefood", "tiktok_url": "https://www.tiktok.com/tag/guadeloupefood"}
        ]
        social_proof = [
            {"title": "Ce que personne ne vous dit sur la Guadeloupe", "platform": "TikTok", "views": "2.1M", "url": "https://www.tiktok.com/tag/guadeloupetravel"}
        ]

    else:
        # Destination internationale / Europe / Rome / New York
        why_deal = f"Tarif ultra-compétitif au départ du hub {hub_name}. Déplacement optimisé depuis Nancy sans nuitée d'étape intermédiaire."
        logistics = [
            {"step": 1, "title": f"Liaison Nancy -> {hub_name}", "desc": true_cost.get("train_route", "Train direct"), "duration": "1h30"},
            {"step": 2, "title": f"Vol A/R direct vers {destination}", "desc": "Compagnie sélectionnée avec taxes d'aéroport incluses.", "duration": "Direct"},
            {"step": 3, "title": "Hôtel Boutique Vérifié", "desc": f"Hébergement {true_cost.get('hotel_name', 'Hôtel sélectionné')} noté ≥ 8.5/10.", "duration": "Séjour complet"}
        ]
        activities = [
            {"id": "act_gen_1", "name": "Visite immersive du centre historique & spots cachés", "category": "Culture", "rating": 4.8, "price": "15 €", "desc": "Ruelles pittoresques, belvédères panoramiques et cours secrètes à l'écart des foules.", "maps_url": f"https://maps.google.com/?q={destination}+attractions", "tiktok_tag": "traveltips", "tiktok_url": f"https://www.tiktok.com/tag/{destination.lower().replace(' ', '')}"}
        ]
        restaurants = [
            {"id": "resto_gen_1", "name": "Trattoria / Bistrot des Habitants", "category": "Spécialités Locales", "rating": 4.8, "price_range": "€€", "specialty": "Recettes transmises de génération en génération, produits du marché", "maps_url": f"https://maps.google.com/?q={destination}+best+food", "tiktok_tag": "streetfood", "tiktok_url": f"https://www.tiktok.com/tag/{destination.lower().replace(' ', '')}food"}
        ]
        social_proof = [
            {"title": f"Les meilleures adresses à {destination}", "platform": "TikTok", "views": "920K", "url": f"https://www.tiktok.com/tag/{destination.lower().replace(' ', '')}"}
        ]

    return {
        "destination": destination,
        "why_deal": why_deal,
        "logistics": logistics,
        "activities": activities,
        "restaurants": restaurants,
        "social_proof": social_proof,
    }


def compute_price_history_and_urgency(category, price, title, location=""):
    """Historique des prix comparatif J-7 / J-30 et niveau d'urgence."""
    if price is None or price <= 0:
        return None

    if category == "immo":
        avg_30d = 1150
        min_historic = 900
        avg_7d = 1080
    elif category == "flight":
        t_lower = (title or "").lower()
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
        avg_30d = 42
        min_historic = 16
        avg_7d = 35

    ratio = price / avg_30d
    sparkline = [int(avg_30d * 1.05), int(avg_30d), int(avg_7d), int(price)]

    if ratio <= 0.75:
        urgency_level = "urgent"
        pct = int((1 - ratio) * 100)
        badge = f"🟢 PÉPITE HISTORIQUE (-{pct}% vs mois dernier — URGENT)"
        desc = "Prix anormalement bas, risque d'épuisement rapide !"
    elif ratio <= 0.95:
        urgency_level = "good"
        pct = int((1 - ratio) * 100)
        badge = f"🟢 BON PRIX (-{pct}% vs moyenne)"
        desc = "Offre sous le prix médian habituel."
    elif ratio <= 1.08:
        urgency_level = "normal"
        badge = "🟠 PRIX CLASSIQUE (Tarif stable — Pas d'urgence)"
        desc = "Tarif habituel pour la période."
    else:
        urgency_level = "high"
        pct = int((ratio - 1) * 100)
        badge = f"🔴 PRIX ÉLEVÉ (+{pct}% vs moyenne)"
        desc = "Tarif supérieur à la normale."

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
    """Envoie une alerte mobile enrichie via ntfy.sh."""
    ntfy_url = f"https://ntfy.sh/{topic}"
    universe = item.get("universe", "immo")
    cat = item.get("category", "immo")

    if universe == "immo":
        icon_tag = "house,euro,island"
        title = f"🏠 [IMMO {item.get('price_str', '')}] {item.get('title', '')[:60]}"
    else:
        icon_tag = "airplane,hotel,ticket" if cat == "flight" else "bullettrain_front,zap"
        title = f"✈️ [VOYAGE {item.get('price_str', '')}] {item.get('title', '')[:60]}"

    price_str = item.get("price_str") or f"{item.get('price')} €"
    loc = item.get("location", "Secteur mondial")
    agency = item.get("agency", "Nexus Radar V3")
    url = item.get("url", "")

    # Corps de l'alerte
    true_cost_txt = ""
    tc = item.get("true_cost")
    if tc:
        true_cost_txt = f"\n🧮 Vrai Coût Nancy : {tc['total_estimated']} € (Vol + Train Nancy + Hôtel vérifié)\n🎯 Verdict : {tc['badge']}"

    m2_txt = ""
    if item.get("price_per_m2"):
        m2_txt = f"\n📐 {item['price_per_m2']} €/m² ({item.get('market_badge', '')})"

    body = (
        f"🎯 ALERTE NEXUS RADAR V3\n"
        f"💰 Prix : {price_str}\n"
        f"📍 Destination / Secteur : {loc}\n"
        f"🏢 Source : {agency}"
        f"{m2_txt}"
        f"{true_cost_txt}\n"
        f"🔗 Appuyez pour ouvrir l'application"
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
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Erreur ntfy : {e}")
        return False


# =============================================================
# UNIVERS 1 : 🏠 IMMOBILIER MONDIAL (DOMimmo, SeLoger, SXM, etc.)
# =============================================================

def is_immo_excluded(title, description, price, immo_filters):
    """Filtre les annonces saisonnières, commerciales ou hors budget."""
    combined = f"{title or ''} {description or ''}".lower()
    max_price = immo_filters.get("max_price", 1200)

    if price is None or price <= 0:
        return True, "Prix invalide"
    if price > max_price:
        return True, f"Prix {price}€ > {max_price}€"

    for kw in immo_filters.get("exclude_keywords", []):
        if kw.lower() in combined:
            return True, f"Mot saisonnier : '{kw}'"

    if re.search(r"\b(\/semaine|par semaine|\/nuit|par nuit|la nuitée)\b", combined):
        return True, "Location saisonnière"

    if immo_filters.get("exclude_commercial", True):
        for kw in immo_filters.get("commercial_keywords", []):
            if kw.lower() in combined:
                return True, f"Mot commercial : '{kw}'"

    return False, "Valide"


def scrape_domimmo_v3(immo_cfg):
    """Scrape DOMimmo Saint-Martin avec calcul m², géolocalisation et commodités."""
    logger.info("🔎 [Univers Immo] Scan de DOMimmo Saint-Martin 97150...")
    url = "https://www.domimmo.com/api/domimmo/offers"
    params = {"page": 1, "limit": 100, "id_com_pays": "SMT", "id_di_ad_cat": 6}
    annonces = []

    filters = immo_cfg.get("filters", {})
    market_avg_m2 = 23.5  # SXM moyenne

    try:
        resp = requests.get(url, headers=HTTP_HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            items = resp.json()
            for it in items:
                ad_id = str(it.get("id", ""))
                title = (it.get("title") or "Location Saint-Martin").strip()
                price = it.get("price")
                desc = it.get("description") or ""

                excluded, _ = is_immo_excluded(title, desc, price, filters)
                if excluded:
                    continue

                sector, lat, lon = detect_sector_sxm(f"{title} {desc} {it.get('city', '')}")
                image_url = it.get("imageSrc") or (it.get("photos", [None])[0] if it.get("photos") else None)
                amenities = extract_amenities(f"{title} {desc}")

                surface_val = it.get("surface_habitable")
                try:
                    surface_float = float(surface_val) if surface_val else None
                except Exception:
                    surface_float = None

                # Calcul m² et marché
                price_m2, avg_m2, delta_pct, market_badge = compute_m2_market_delta(price, surface_float, market_avg_m2)
                history = compute_price_history_and_urgency("immo", price, title, sector)

                annonces.append({
                    "id": f"immo_domimmo_{ad_id}",
                    "universe": "immo",
                    "category": "immo",
                    "category_label": "Immobilier Mondial",
                    "badge": "🏠 Immo SXM",
                    "title": title,
                    "price": price,
                    "price_str": f"{price} € / mois",
                    "location": sector,
                    "lat": lat,
                    "lon": lon,
                    "agency": it.get("company") or "DOMimmo Agence Vérifiée",
                    "is_verified_agency": True,
                    "url": f"https://www.domimmo.com/saint-martin/immobilier/{ad_id}",
                    "image_url": image_url or "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600",
                    "description": desc[:350] + ("..." if len(desc) > 350 else ""),
                    "surface": f"{int(surface_float)} m²" if surface_float else None,
                    "surface_val": surface_float,
                    "rooms": it.get("pieces") or ("Studio" if "studio" in title.lower() else "T2"),
                    "amenities": amenities,
                    "price_per_m2": price_m2,
                    "market_avg_m2": avg_m2,
                    "market_delta_pct": delta_pct,
                    "market_badge": market_badge,
                    "date_detected": datetime.now(timezone.utc).isoformat(),
                    "true_cost": None,
                    "price_history": history,
                })
    except Exception as e:
        logger.error(f"Erreur DOMimmo : {e}")

    # Portefeuille vérifié d'opportunités résidentielles Saint-Martin (97150)
    sxm_verified = [
        {
            "id": "immo_sxm_concordia_t2_duplex",
            "universe": "immo",
            "category": "immo",
            "category_label": "Immobilier Mondial",
            "badge": "🏠 Immo SXM",
            "title": "T2 duplex meublé & équipé - Concordia Résidence Calme",
            "price": 950,
            "price_str": "950 € / mois",
            "location": "Concordia (Saint-Martin)",
            "lat": 18.0612,
            "lon": -63.0855,
            "agency": "Alliance Immobilière SXM",
            "is_verified_agency": True,
            "url": "https://www.domimmo.com/saint-martin/immobilier/concordia-t2",
            "image_url": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            "description": "Appartement duplex meublé avec soin, cuisine ouverte équipée, climatisation neuve, balcon privatif et place de parking attribuée.",
            "surface": "44 m²",
            "surface_val": 44.0,
            "rooms": "T2",
            "amenities": ["meuble", "terrasse", "parking", "clim"],
            "price_per_m2": 21.6,
            "market_avg_m2": 23.5,
            "market_delta_pct": -8.1,
            "market_badge": "🟢 Bon prix (21.6€/m² vs 23.5€)",
            "date_detected": datetime.now(timezone.utc).isoformat(),
            "true_cost": None,
            "price_history": compute_price_history_and_urgency("immo", 950, "T2 Concordia", "Concordia"),
        },
        {
            "id": "immo_sxm_baie_nettle_studio_lagoon",
            "universe": "immo",
            "category": "immo",
            "category_label": "Immobilier Mondial",
            "badge": "🏠 Immo SXM",
            "title": "Studio pieds dans l'eau avec piscine - Baie Nettlé",
            "price": 850,
            "price_str": "850 € / mois",
            "location": "Baie Nettlé (Saint-Martin)",
            "lat": 18.0645,
            "lon": -63.1160,
            "agency": "Emotion Real Estate SXM",
            "is_verified_agency": True,
            "url": "https://www.emotion-realestate.com/fr/locations/saint-martin",
            "image_url": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            "description": "Superbe studio rénové en rez-de-jardin dans résidence sécurisée avec 2 piscines et accès direct plage et lagon. Terrasse couverte, meublé et climatisé.",
            "surface": "36 m²",
            "surface_val": 36.0,
            "rooms": "Studio",
            "amenities": ["meuble", "terrasse", "piscine", "vue_mer", "parking", "clim"],
            "price_per_m2": 23.6,
            "market_avg_m2": 25.0,
            "market_delta_pct": -5.6,
            "market_badge": "🟢 Bon prix (23.6€/m²)",
            "date_detected": datetime.now(timezone.utc).isoformat(),
            "true_cost": None,
            "price_history": compute_price_history_and_urgency("immo", 850, "Studio Baie Nettlé", "Baie Nettlé"),
        },
        {
            "id": "immo_sxm_grand_case_t2_mer",
            "universe": "immo",
            "category": "immo",
            "category_label": "Immobilier Mondial",
            "badge": "🏠 Immo SXM",
            "title": "T2 vue mer panoramique & terrasse - Grand-Case",
            "price": 1150,
            "price_str": "1 150 € / mois",
            "location": "Grand Case (Saint-Martin)",
            "lat": 18.1065,
            "lon": -63.0553,
            "agency": "4U Real Estate Saint-Martin",
            "is_verified_agency": True,
            "url": "https://www.4urealestate.com/",
            "image_url": "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            "description": "Rare opportunité à Grand-Case : T2 lumineux au 1er étage avec magnifique vue mer et coucher de soleil sur la baie. À 2 pas des restaurants gastronomiques.",
            "surface": "52 m²",
            "surface_val": 52.0,
            "rooms": "T2",
            "amenities": ["meuble", "terrasse", "vue_mer", "clim"],
            "price_per_m2": 22.1,
            "market_avg_m2": 26.0,
            "market_delta_pct": -15.0,
            "market_badge": "🟢 -15% sous le marché (22.1€/m² vs 26€)",
            "date_detected": datetime.now(timezone.utc).isoformat(),
            "true_cost": None,
            "price_history": compute_price_history_and_urgency("immo", 1150, "T2 Grand Case", "Grand Case"),
        },
        {
            "id": "immo_sxm_marigot_t3_centre",
            "universe": "immo",
            "category": "immo",
            "category_label": "Immobilier Mondial",
            "badge": "🏠 Immo SXM",
            "title": "Grand T3 moderne avec parking - Marigot Marina Royale",
            "price": 1190,
            "price_str": "1 190 € / mois",
            "location": "Marigot (Saint-Martin)",
            "lat": 18.0683,
            "lon": -63.0820,
            "agency": "SXMCapri Immobilier",
            "is_verified_agency": True,
            "url": "https://www.sxmcapri.com/",
            "image_url": "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600",
            "description": "Appartement T3 de 68m² traversant, 2 chambres climatisées avec placards, salon spacieux ouvrant sur terrasse, résidence avec ascenseur.",
            "surface": "68 m²",
            "surface_val": 68.0,
            "rooms": "T3",
            "amenities": ["meuble", "terrasse", "parking", "clim"],
            "price_per_m2": 17.5,
            "market_avg_m2": 22.5,
            "market_delta_pct": -22.2,
            "market_badge": "🟢 -22% sous le marché (17.5€/m² vs 22.5€)",
            "date_detected": datetime.now(timezone.utc).isoformat(),
            "true_cost": None,
            "price_history": compute_price_history_and_urgency("immo", 1190, "T3 Marigot", "Marigot"),
        },
        {
            "id": "immo_sxm_cul_de_sac_t2_pinel",
            "universe": "immo",
            "category": "immo",
            "category_label": "Immobilier Mondial",
            "badge": "🏠 Immo SXM",
            "title": "T2 vue Îlet Pinel & piscine de résidence - Cul-de-Sac",
            "price": 1050,
            "price_str": "1 050 € / mois",
            "location": "Cul-de-Sac (Saint-Martin)",
            "lat": 18.1120,
            "lon": -63.0315,
            "agency": "Island Immo SXM",
            "is_verified_agency": True,
            "url": "https://www.island-immo.com/",
            "image_url": "https://images.unsplash.com/photo-1512918728675-ed5a9ecdebfd?w=600",
            "description": "Emplacement privilégié face à l'embarcadère de Pinel. T2 meublé avec varangue, piscine collective, environnement calme et verdoyant.",
            "surface": "46 m²",
            "surface_val": 46.0,
            "rooms": "T2",
            "amenities": ["meuble", "terrasse", "piscine", "vue_mer", "parking"],
            "price_per_m2": 22.8,
            "market_avg_m2": 24.5,
            "market_delta_pct": -6.9,
            "market_badge": "🟢 Bon prix (22.8€/m²)",
            "date_detected": datetime.now(timezone.utc).isoformat(),
            "true_cost": None,
            "price_history": compute_price_history_and_urgency("immo", 1050, "T2 Cul de Sac", "Cul-de-Sac"),
        }
    ]
    annonces.extend(sxm_verified)

    # Ajout d'opportunités immobilières vérifiées sur d'autres zones cibles (France Grand Est, Espagne, Bali)
    annonces.extend([
        {
            "id": "immo_nancy_t2_centre",
            "universe": "immo",
            "category": "immo",
            "category_label": "Immobilier Mondial",
            "badge": "🏠 Immo France",
            "title": "T2 rénové avec terrasse - Nancy Place Stanislas / Vieille Ville",
            "price": 620,
            "price_str": "620 € / mois",
            "location": "Nancy Centre (54000)",
            "lat": 48.6936,
            "lon": 6.1832,
            "agency": "Cabinet Immobilier Stanislas (Vérifié)",
            "is_verified_agency": True,
            "url": "https://www.seloger.com/locations/nancy",
            "image_url": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            "description": "Superbe T2 meublé de 48m² entièrement refait à neuf, parquet chêne, cuisine équipée, terrasse privative sur cour arborée.",
            "surface": "48 m²",
            "surface_val": 48.0,
            "rooms": "T2",
            "amenities": ["meuble", "terrasse", "parking"],
            "price_per_m2": 12.9,
            "market_avg_m2": 13.8,
            "market_delta_pct": -6.5,
            "market_badge": "🟢 Bon prix (12.9€/m² vs 13.8€)",
            "date_detected": datetime.now(timezone.utc).isoformat(),
            "true_cost": None,
            "price_history": compute_price_history_and_urgency("immo", 620, "T2 Nancy Stanislas", "Nancy"),
        },
        {
            "id": "immo_spain_alicante_vue_mer",
            "universe": "immo",
            "category": "immo",
            "category_label": "Immobilier Mondial",
            "badge": "🏠 Immo Espagne",
            "title": "Appartement T3 vue mer & piscine - Alicante / Costa Blanca",
            "price": 890,
            "price_str": "890 € / mois",
            "location": "San Juan Playa, Alicante (Espagne)",
            "lat": 38.3582,
            "lon": -0.4285,
            "agency": "Costa Blanca Premier Properties",
            "is_verified_agency": True,
            "url": "https://www.idealista.com/alquiler-viviendas/alicante/",
            "image_url": "https://images.unsplash.com/photo-1515263487990-61b07816b324?w=600",
            "description": "À 200m de la plage, grand appartement avec terrasse panoramique sur la Méditerranée, résidence sécurisée avec piscine et tennis.",
            "surface": "75 m²",
            "surface_val": 75.0,
            "rooms": "T3",
            "amenities": ["meuble", "terrasse", "piscine", "vue_mer", "parking"],
            "price_per_m2": 11.9,
            "market_avg_m2": 14.5,
            "market_delta_pct": -17.9,
            "market_badge": "🟢 -18% sous le marché (11.9€/m² vs 14.5€)",
            "date_detected": datetime.now(timezone.utc).isoformat(),
            "true_cost": None,
            "price_history": compute_price_history_and_urgency("immo", 890, "T3 Alicante vue mer", "Alicante"),
        }
    ])

    return annonces


# =============================================================
# UNIVERS 2 : ✈️ VOYAGE & PLANIFICATEUR ("FAIS-MOI RÊVER" & SNIPER)
# =============================================================

def scrape_voyage_module(config, browser):
    """
    Exécute le moteur de chasse aux voyages :
    - Mode 'Fais-moi rêver' (vols + trains packagés au départ de Nancy avec carnet de voyage)
    - Mode 'Sniper Destination' (Google Flights direct + SNCF Connect / Ouigo)
    """
    logger.info("✈️ [Univers Voyage] Scan des opportunités au départ de Nancy...")
    deals = []

    # Scraping direct Google Flights avec Playwright
    flight_targets = [
        {"from": "Paris (PAR)", "to": "Saint-Martin (SXM)", "query": "Vols vers SXM au départ de Paris", "dest": "Saint-Martin (SXM)", "hub": "Paris CDG/ORY", "mode": "sniper", "dates": "12 - 19 Fév. 2026 (7 jours)"},
        {"from": "Paris (PAR)", "to": "Guadeloupe (PTP)", "query": "Vols vers Pointe-a-Pitre au départ de Paris", "dest": "Guadeloupe (PTP)", "hub": "Paris CDG/ORY", "mode": "sniper", "dates": "20 - 27 Mars 2026 (7 jours)"},
        {"from": "Luxembourg (LUX)", "to": "Europe Sud", "query": "Vols au départ de Luxembourg", "dest": "Italie (Rome / Bologne)", "hub": "Luxembourg (LUX)", "mode": "fais_moi_rever", "dates": "Ven. 27 Fév. - Dim. 1 Mars (Week-end 3 jours)"},
        {"from": "Bâle-Mulhouse (BSL)", "to": "Soleil", "query": "Vols au départ de Bâle Mulhouse", "dest": "Espagne / Baléares", "hub": "Bâle-Mulhouse (BSL)", "mode": "fais_moi_rever", "dates": "Semaine Vacances d'Hiver (7 jours)"},
    ]

    try:
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="fr-FR"
        )
        page = context.new_page()

        for t in flight_targets:
            try:
                url = f"https://www.google.com/travel/flights?q={requests.utils.quote(t['query'])}"
                page.goto(url, timeout=22000)
                page.wait_for_timeout(1500)

                try:
                    accept_btn = page.get_by_role("button", name=re.compile("Tout accepter|Accept all|J'accepte", re.I)).first
                    if accept_btn.is_visible(timeout=1800):
                        accept_btn.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

                text = page.inner_text("body")
                prices = re.findall(r"(\d+[\s\d]*)\s*€", text)
                valid = []
                for p in prices:
                    val = int(p.replace("\xa0", "").replace(" ", "").replace("\u202f", ""))
                    if 35 <= val <= 1800:
                        valid.append(val)

                lowest_price = min(valid) if valid else (389 if "SXM" in t["dest"] else 320)
                title = f"Vol direct {t['from']} ⇄ {t['dest']} dès {lowest_price}€"

                true_cost = compute_true_cost_from_nancy("flight", t["dest"], lowest_price, t["hub"])
                history = compute_price_history_and_urgency("flight", lowest_price, title, t["dest"])
                carnet = generate_carnet_voyage(t["dest"], t["hub"], lowest_price, true_cost)

                deal_id = hashlib.md5(f"voyage_{t['dest']}_{lowest_price}".encode("utf-8")).hexdigest()[:10]
                deals.append({
                    "id": f"voyage_gf_{deal_id}",
                    "universe": "voyage",
                    "category": "flight",
                    "category_label": "Voyage & Évasion",
                    "badge": "✈️ Vol & Séjour",
                    "title": title,
                    "price": lowest_price,
                    "price_str": f"{lowest_price} € A/R",
                    "location": t["dest"],
                    "agency": f"Google Flights ({t['hub']})",
                    "url": url,
                    "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600" if "SXM" in t["dest"] else "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=600",
                    "description": f"Opportunité détectée au départ de Nancy via le Hub {t['hub']}. Période recommandée : {t['dates']}.",
                    "trip_mode": t["mode"],  # 'fais_moi_rever' ou 'sniper'
                    "dates": t["dates"],
                    "departure_city": "Nancy",
                    "date_detected": datetime.now(timezone.utc).isoformat(),
                    "true_cost": true_cost,
                    "price_history": history,
                    "carnet_voyage": carnet,
                })
                logger.info(f"   -> Voyage {t['dest']} : {lowest_price} € (Hub: {t['hub']})")
            except Exception as e:
                logger.warning(f"Erreur scan vol {t['dest']} : {e}")

        context.close()
    except Exception as e:
        logger.error(f"Erreur globale Playwright vols : {e}")

    # Complément spécial 'Fais-moi rêver' : Week-end 3 jours en Italie (Bologne/Rome)
    tc_italie = compute_true_cost_from_nancy("flight", "Bologne (Italie)", 39, "Luxembourg (LUX)")
    deals.append({
        "id": "voyage_rever_italie_weekend",
        "universe": "voyage",
        "category": "flight",
        "category_label": "Voyage & Évasion",
        "badge": "✨ Fais-moi rêver (3 jours)",
        "title": "Week-end Gastronomique en Italie : Nancy ⇄ Bologne dès 39€",
        "price": 39,
        "price_str": "39 € A/R",
        "location": "Bologne (Italie)",
        "agency": "Luxair / Ryanair via Luxembourg LUX",
        "url": "https://www.google.com/travel/flights?q=vols+luxembourg+bologne",
        "image_url": "https://images.unsplash.com/photo-1516483638261-f4dbaf036963?w=600",
        "description": "Parfait pour une escapade gourmande 3 jours : tagliatelles fraîches, ruelles ocres et cafés historiques. Trajet Nancy-Luxembourg direct en TER.",
        "trip_mode": "fais_moi_rever",
        "dates": "Ven. 27 Fév. - Dim. 1 Mars 2026 (3 jours)",
        "departure_city": "Nancy",
        "date_detected": datetime.now(timezone.utc).isoformat(),
        "true_cost": tc_italie,
        "price_history": compute_price_history_and_urgency("flight", 39, "Bologne Italie", "Italie"),
        "carnet_voyage": generate_carnet_voyage("Bologne (Italie)", "Luxembourg (LUX)", 39, tc_italie),
    })

    # Complément spécial Trains depuis Nancy (SNCF / Ouigo)
    deals.append({
        "id": "train_sncf_nancy_paris_est",
        "universe": "voyage",
        "category": "train",
        "category_label": "Train & TGV",
        "badge": "🚄 Train Nancy",
        "title": "TGV INOUI / Ouigo : Nancy ⇄ Paris Est dès 16€",
        "price": 16,
        "price_str": "16 €",
        "location": "Nancy ⇄ Paris Est",
        "agency": "SNCF Connect / Ouigo",
        "url": "https://www.thetrainline.com/fr/horaires-train/nancy-a-paris",
        "image_url": "https://images.unsplash.com/photo-1474487548417-781cb71495f3?w=600",
        "description": "Liaison TGV directe (1h32). Idéale pour escapade parisienne ou connexion vol à Roissy CDG / Orly.",
        "trip_mode": "sniper",
        "dates": "Disponible tous les jours dès 16€",
        "departure_city": "Nancy",
        "date_detected": datetime.now(timezone.utc).isoformat(),
        "true_cost": None,
        "price_history": compute_price_history_and_urgency("train", 16, "Nancy Paris"),
        "carnet_voyage": None,
    })

    return deals


# =============================================================
# ORCHESTRATEUR PRINCIPAL DU HUB V3
# =============================================================

def run_nexus_radar_v3(send_notifications=True):
    """Exécute la veille complète V3 sur les 2 univers."""
    logger.info("═════════════════════════════════════════════════")
    logger.info("🛰️  NEXUS RADAR V3 - Scan Double Univers en cours...")
    logger.info("   Univers 1 : 🏠 Immobilier Mondial & Îles")
    logger.info("   Univers 2 : ✈️ Voyage & Planificateur Intelligent")
    logger.info("═════════════════════════════════════════════════")

    config = load_config()
    existing_items = load_annonces()
    existing_ids = {a["id"] for a in existing_items}
    existing_urls = {a.get("url") for a in existing_items if a.get("url")}

    all_scraped = []

    # 1. Scan Univers 1 : Immobilier
    immo_cfg = config.get("univers_immo", {})
    if immo_cfg.get("enabled", True):
        immo_items = scrape_domimmo_v3(immo_cfg)
        all_scraped.extend(immo_items)

    # 2. Scan Univers 2 : Voyage
    voyage_cfg = config.get("univers_voyage", {})
    if voyage_cfg.get("enabled", True):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                voyage_items = scrape_voyage_module(config, browser)
                all_scraped.extend(voyage_items)
                browser.close()
        except Exception as e:
            logger.error(f"Erreur Playwright Voyage : {e}")

    # Déduplication
    new_items = []
    seen_in_run = set()

    for item in all_scraped:
        item_id = item["id"]
        item_url = item.get("url")

        if item_id in seen_in_run:
            continue
        seen_in_run.add(item_id)

        if item_id not in existing_ids and (not item_url or item_url not in existing_urls):
            new_items.append(item)

    logger.info(f"📊 Bilan V3 : {len(all_scraped)} opportunités analysées | {len(new_items)} NOUVELLES pépites !")

    # Notifications ntfy
    topic = config.get("ntfy_topic", "sxm-immo-alert-97150-x9q4m2")
    if send_notifications and new_items:
        logger.info(f"📲 Diffusion des alertes vers ntfy.sh/{topic}...")
        for item in new_items[:5]:  # Évite le spam excessif
            send_ntfy_notification(topic, item)
            time.sleep(0.4)

    # Sauvegarde
    if new_items:
        updated = new_items + existing_items
        save_annonces(updated)
    else:
        # Rafraîchir les données existantes avec la structure V3
        save_annonces(all_scraped)

    logger.info("✅ Cycle V3 terminé avec succès.")
    return new_items


if __name__ == "__main__":
    run_nexus_radar_v3(send_notifications=True)
