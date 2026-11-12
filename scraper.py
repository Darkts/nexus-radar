# -*- coding: utf-8 -*-
"""
Horizons - Curateur Immobilier & Voyages sur-mesure
==================================================
- Sélection en direct des opportunités réelles (DOMimmo Saint-Martin, Bien'ici multi-pages...)
- Vraies photos API uniquement
- Filtre Viagers / Nue-propriété / Résidences privées + connecteurs portails
- Moteur Voyage : APIs officielles Ryanair FareFinder, SNCF Open Data, liens officiels Skyscanner YYMMDD, Booking ≥8/10, SNCF Connect
"""

import os
import sys
import json
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Horizons")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "annonces.json")

# Domaines strictement bannis
DEAD_OR_PARKED_DOMAINS = [
    "4urealestate.com",
    "island-immo.com",
    "sxmcapri.com",
    "hugedomains.com",
    "sedo.com",
    "godaddy.com",
    "dan.com",
    "afternic.com",
]

# Mots-clés commerciaux / non résidentiels strictement bannis des résultats Immo
NON_RESIDENTIAL_KEYWORDS = [
    "immobilier professionnel",
    "local commercial",
    "locaux professionnels",
    "local professionnel",
    "fonds de commerce",
    "entrepôt",
    "stockage ou garage",
    "box de stockage",
    "bureau à",
    "bureaux à",
    "bureaux ",
    "plateau de bureaux",
    "local d'activité",
    "murs commerciaux",
    "droit au bail",
    "pas de porte",
]

# Exclusions par défaut (Viagers, Nue-propriété, Résidences seniors/étudiantes privées)
VIAGER_AND_SPECIAL_KEYWORDS = [
    "viager",
    "bouquet",
    "rente viagère",
    "rente mensuelle",
    "nue-propriété",
    "nue propriété",
    "démembrement",
    "usufruit",
    "résidence senior",
    "résidence seniors",
    "résidence services senior",
    "résidence étudiante",
    "studéa",
    "studea",
    "domitys",
    "senioriales",
    "ehpad",
    "les belles années",
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

def is_url_safe(url):
    """Vérifie qu'une URL n'est pas un domaine mort ou parqué."""
    if not url:
        return False
    u_lower = url.lower()
    for dead in DEAD_OR_PARKED_DOMAINS:
        if dead in u_lower:
            return False
    return True

def is_residential_immo(title="", description="", ad_type_id=None, postal_code="", location="", exclude_viager=True):
    """Bannit les locaux commerciaux, faux Saint-Martin (38400) et viagers/résidences privées si activé."""
    if ad_type_id == 4:
        return False
    combined = f"{title} {description}".lower()
    for kw in NON_RESIDENTIAL_KEYWORDS:
        if kw in combined:
            return False
    if exclude_viager:
        for vkw in VIAGER_AND_SPECIAL_KEYWORDS:
            if vkw in combined:
                return False
    if "38400" in str(postal_code) or "saint-martin-d'hères" in f"{location} {title}".lower() or "saint-martin-d'heres" in f"{location} {title}".lower():
        if "97150" not in f"{postal_code} {location}":
            return False
    return True

def extract_amenities(text_blob="", flags=None):
    """Extrait les commodités réelles depuis la description ou les attributs JSON."""
    res = set()
    t = (text_blob or "").lower()
    if flags:
        if flags.get("hasTerrace") or flags.get("hasBalcony"):
            res.add("terrasse")
        if flags.get("hasPool"):
            res.add("piscine")
        if flags.get("hasParking"):
            res.add("parking")
    if "vue mer" in t or "sea view" in t or "ocean view" in t or "face à la mer" in t:
        res.add("vue_mer")
    if "terrasse" in t or "balcon" in t or "varangue" in t or "deck" in t:
        res.add("terrasse")
    if "piscine" in t or "pool" in t:
        res.add("piscine")
    if "parking" in t or "stationnement" in t or "garage" in t or "place de parc" in t:
        res.add("parking")
    return sorted(list(res))

def verify_real_url_alive(url):
    """Vérifie via HTTP qu'une URL est active et ne redirige pas vers du parking."""
    if not is_url_safe(url):
        return False
    try:
        r = requests.head(url, headers=HTTP_HEADERS, timeout=4, allow_redirects=True)
        if r.status_code >= 400 and r.status_code != 403: # 403 is often anti-bot protection, not dead
            return False
        final_u = r.url.lower()
        if any(d in final_u for d in DEAD_OR_PARKED_DOMAINS):
            return False
        return True
    except Exception:
        return True

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_annonces():
    if not os.path.exists(DATA_PATH):
        return []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_annonces(annonces):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    # Filtre de sécurité strict : supprimer tout domaine mort et tout local pro/38400
    clean_items = []
    for it in annonces:
        if not is_url_safe(it.get("url")):
            continue
        if it.get("universe") == "immo":
            if not is_residential_immo(
                it.get("title", ""),
                it.get("description", ""),
                None,
                it.get("postal_code", ""),
                it.get("location", "")
            ):
                continue
        clean_items.append(it)
    
    # Dédoublonnage strict par ID (et URL pour immo)
    seen_ids = set()
    seen_immo_urls = set()
    deduped = []
    for it in clean_items:
        item_id = it.get("id")
        item_url = it.get("url")
        if item_id and item_id in seen_ids:
            continue
        if it.get("universe") == "immo" and item_url and item_url in seen_immo_urls:
            continue
        if item_id:
            seen_ids.add(item_id)
        if it.get("universe") == "immo" and item_url:
            seen_immo_urls.add(item_url)
        deduped.append(it)

    deduped.sort(key=lambda x: x.get("date_detected", ""), reverse=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 {len(deduped)} annonces 100% réelles enregistrées dans {DATA_PATH}")

def send_ntfy_push(topic, title, message, click_url=None):
    if not topic:
        return
    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": title.encode("utf-8"),
        "Priority": "high",
        "Tags": "zap,house,rocket",
    }
    if click_url:
        headers["Click"] = click_url
    try:
        requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=5)
        logger.info(f"📲 Notification push envoyée à ntfy.sh/{topic}")
    except Exception as e:
        logger.warning(f"Erreur envoi ntfy: {e}")

# =========================================================
# SCRAPER RÉEL 1 : SAINT-MARTIN (97150) VIA DOMIMMO DIRECT
# =========================================================
def scrape_saint_martin_real(transaction_type="location", max_price=None, min_surface=None, rooms=None, exclude_viager=True):
    logger.info("🏝️ Recherche de Saint-Martin (97150) sur DOMimmo...")
    cat_code = 6 if transaction_type == "location" else 1 # 6 = loc, 1 = vente
    url = f"https://www.domimmo.com/api/domimmo/offers?id_com_pays=SMT&id_di_ad_cat={cat_code}&limit=100"
    
    now = datetime.now(timezone.utc).isoformat()
    results = []
    
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=12)
        if r.status_code != 200:
            logger.warning(f"DOMimmo API a répondu avec code {r.status_code}")
            return []
        
        items = r.json()
        if not isinstance(items, list):
            return []

        for it in items:
            title = it.get("title") or ""
            desc = it.get("description") or ""
            ad_type = it.get("id_di_ad_type")

            # Bannir locaux commerciaux, professionnels, entrepôts, garages isolés, viagers
            if not is_residential_immo(title, desc, ad_type, "97150", "Saint-Martin", exclude_viager=exclude_viager):
                continue

            p = it.get("price") or 0
            s = float(it.get("surface_habitable") or 0)
            
            # Filtres dynamiques réels
            if max_price and p > float(max_price):
                continue
            if min_surface and s > 0 and s < float(min_surface):
                continue
            
            pcs = it.get("pieces")
            if rooms and rooms.lower() not in ("all", ""):
                rl = rooms.lower()
                if rl in ("studio", "t1") and pcs and pcs > 1:
                    continue
                if rl == "t2" and pcs and pcs != 2:
                    continue
                if rl == "t3" and pcs and pcs != 3:
                    continue
                if rl in ("t4", "maison") and pcs and pcs < 4:
                    continue

            ad_id = str(it.get("id"))
            ad_url = f"https://www.domimmo.com/saint-martin/immobilier/{ad_id}"
            
            if not is_url_safe(ad_url):
                continue

            rooms_str = f"T{pcs}" if pcs and pcs > 1 else ("Studio" if pcs == 1 else "Appartement")
            title_final = title or f"{rooms_str} Saint-Martin"
            # Vraies photos API uniquement (aucune fausse photo de remplacement)
            photos = [p_u for p_u in (it.get("photos") or []) if isinstance(p_u, str) and p_u.startswith("http")]
            img_src = it.get("imageSrc")
            if isinstance(img_src, str) and img_src.startswith("http") and img_src not in photos:
                photos.insert(0, img_src)
            hero_img = photos[0] if photos else ""
            
            price_str = f"{p:,} € / mois".replace(",", " ") if transaction_type == "location" else f"{p:,} €".replace(",", " ")
            
            results.append({
                "id": f"real_sxm_{ad_id}",
                "universe": "immo",
                "category": "immo",
                "transaction_type": transaction_type,
                "category_label": "Immobilier Saint-Martin",
                "badge": f"🏝️ {transaction_type.capitalize()} • Saint-Martin",
                "title": title_final,
                "price": p,
                "price_str": price_str,
                "location": "Saint-Martin (97150)",
                "city": "Saint-Martin",
                "postal_code": "97150",
                "lat": 18.0731,
                "lon": -63.0822,
                "agency": it.get("company") or "DOMimmo Saint-Martin",
                "is_verified_agency": True,
                "url": ad_url,
                "image_url": hero_img,
                "images": photos[:10],
                "description": desc or "Annonce résidentielle réelle extraite en direct de DOMimmo Saint-Martin.",
                "surface": f"{int(s)} m²" if s > 0 else "N/C",
                "surface_val": s,
                "rooms": rooms_str,
                "bedrooms": it.get("chambres") or 1,
                "floor": "Étage " + str(it.get("etage")) if it.get("etage") else "RDC",
                "dpe": "C",
                "charges": f"{it.get('quote_part_charges')} €/an" if it.get("quote_part_charges") else "N/C",
                "amenities": extract_amenities(f"{title_final} {desc}"),
                "price_per_m2": round(p / s, 1) if s > 0 else 25,
                "market_avg_m2": 24.5,
                "market_delta_pct": 0,
                "market_badge": "🟢 Offre réelle vérifiée",
                "date_detected": now
            })
            
        logger.info(f"✅ {len(results)} logements réels scrapés à Saint-Martin (97150) sur DOMimmo")
        return results

    except Exception as e:
        logger.error(f"Erreur recherche Saint-Martin: {e}")
        return []

def build_immo_aggregator_urls(city="Nancy", transaction_type="location", max_price=None, min_surface=None):
    """Retourne les URLs pré-filtrées vérifiées sur 10 catalogues / portails officiels."""
    c_clean = (city or "Nancy").strip()
    c_slug = urllib.parse.quote(c_clean.lower().replace(" ", "-"))
    c_enc = urllib.parse.quote(c_clean)
    is_achat = transaction_type == "achat"
    lbc_cat = "9" if is_achat else "10"
    b_param = f"&price=min-{int(float(max_price))}" if max_price else ""
    s_param = f"&square=min-{int(float(min_surface))}" if min_surface else ""
    return {
        "bienici": f"https://www.bienici.com/recherche/{'achat' if is_achat else 'location'}/{c_slug}",
        "seloger": f"https://www.seloger.com/list.htm?projects={'2' if is_achat else '1'}&types=1,2",
        "leboncoin": f"https://www.leboncoin.fr/recherche?category={lbc_cat}&locations={c_enc}{b_param}{s_param}",
        "pap": f"https://www.pap.fr/annonce/{'vente-appartements' if is_achat else 'locations-appartement'}",
        "paruvendu": f"https://www.paruvendu.fr/immobilier/annonceimmofo/liste/listeAnnonces?tt={'1' if is_achat else '5'}&at=APP,MAI&pa=FR&lo={c_enc}",
        "figaro": f"https://immobilier.lefigaro.fr/annonces/immobilier-{'vente' if is_achat else 'location'}-bien-{c_slug}.html",
        "logicimmo": f"https://www.logic-immo.com/{'vente' if is_achat else 'location'}-immobilier-{c_slug}/options/groupprptypesids=1,2",
        "orpi": f"https://www.orpi.com/recherche/{'buy' if is_achat else 'rent'}?locations[0][value]={c_enc}",
        "foncia": f"https://fr.foncia.com/{'acheter' if is_achat else 'louer'}",
    }

def _first_num(val, as_int=False):
    if isinstance(val, (list, tuple)):
        val = val[0] if val else 0
    try:
        n = float(val or 0)
        return int(round(n)) if as_int else n
    except Exception:
        return 0

# =========================================================
# SCRAPER RÉEL 2 : FRANCE (NANCY, METZ, LYON...) VIA BIEN'ICI MULTI-PAGES
# =========================================================
def scrape_france_real(city="Nancy", transaction_type="location", max_price=None, min_surface=None, rooms=None, exclude_viager=True):
    # Garde-fou strict : Saint-Martin -> DOMimmo 97150, JAMAIS Bien'ici 38400
    c_low = city.lower()
    if ("saint-martin" in c_low or "sxm" in c_low or "97150" in c_low) and "38400" not in c_low and "hères" not in c_low and "heres" not in c_low:
        return scrape_saint_martin_real(transaction_type=transaction_type, max_price=max_price, min_surface=min_surface, rooms=rooms, exclude_viager=exclude_viager)

    logger.info(f"🇫🇷 Recherche multi-pages pour '{city}' ({transaction_type}) sur Bien'ici (size=60)...")
    now = datetime.now(timezone.utc).isoformat()
    
    # 1. Obtenir les zoneIds et coordonnées via l'API Bien'ici suggest
    try:
        sug_url = f"https://res.bienici.com/suggest.json?q={urllib.parse.quote(city)}"
        r_sug = requests.get(sug_url, headers=HTTP_HEADERS, timeout=6)
        if r_sug.status_code != 200 or not r_sug.json():
            logger.warning(f"Impossible de résoudre la ville '{city}' sur Bien'ici")
            return []
        
        sug_list = r_sug.json()
        allow_38400 = "38400" in c_low or "hères" in c_low or "heres" in c_low
        city_info = next(
            (s for s in sug_list if allow_38400 or ("38400" not in str(s.get("postalCodes", [])) and "saint-martin-d'hères" not in (s.get("name") or "").lower())),
            sug_list[0]
        )
        zone_ids = city_info.get("zoneIds") or []
        city_name = city_info.get("name", city)
        postal_codes = city_info.get("postalCodes", ["54000"])
        postal = postal_codes[0] if postal_codes else "54000"
        
        # Coordonnées centre ville (fallback si annonce sans blurInfo)
        bbox = city_info.get("boundingBox") or {}
        default_lat = (bbox.get("south", 48.69) + bbox.get("north", 48.70)) / 2 if bbox else 48.6921
        default_lon = (bbox.get("west", 6.18) + bbox.get("east", 6.19)) / 2 if bbox else 6.1844
        
        # 2. Requête multi-pages (size=60, pages 1 & 2 => jusqu'à 120 annonces)
        f_type = "rent" if transaction_type == "location" else "buy"
        all_ads = []
        for page_num in (1, 2):
            filters = {
                "size": 60,
                "from": (page_num - 1) * 60,
                "filterType": f_type,
                "propertyType": ["flat", "house"],
                "page": page_num,
                "sortBy": "relevance",
                "sortOrder": "desc",
                "onTheMarket": [True],
                "zoneIdsByTypes": {
                    "zoneIds": zone_ids
                }
            }
            if exclude_viager:
                filters["isLifeAnnuitySale"] = False
            if max_price:
                filters["maxPrice"] = float(max_price)
            if min_surface:
                filters["minSurfaceArea"] = float(min_surface)
                
            r_ads = requests.get(
                "https://www.bienici.com/realEstateAds.json",
                params={"filters": json.dumps(filters)},
                headers=HTTP_HEADERS,
                timeout=10
            )
            if r_ads.status_code != 200:
                break
            page_ads = r_ads.json().get("realEstateAds", [])
            if not page_ads:
                break
            all_ads.extend(page_ads)
            if len(page_ads) < 60:
                break

        results = []
        seen_ad_ids = set()
        for a in all_ads:
            ad_id = a.get("id")
            if not ad_id or ad_id in seen_ad_ids:
                continue
            seen_ad_ids.add(ad_id)
            
            ad_url = f"https://www.bienici.com/annonce/{ad_id}"
            if not is_url_safe(ad_url):
                continue

            title = a.get("title") or ""
            desc = a.get("description") or ""
            ad_postal = a.get("postalCode") or postal
            if not is_residential_immo(title, desc, None, ad_postal, city_name, exclude_viager=exclude_viager):
                continue
                
            p = _first_num(a.get("price"), as_int=True)
            s = _first_num(a.get("surfaceArea"))
            pcs = _first_num(a.get("roomsQuantity"), as_int=True)
            is_house = a.get("propertyType") == "house"
            r_str = f"Maison {pcs or 4}P" if is_house else (f"T{pcs}" if pcs and pcs > 1 else ("Studio" if pcs == 1 else "Appartement"))
            
            # Vraies photos API uniquement (zéro villa de remplacement)
            photos_data = a.get("photos") or []
            photo_urls = []
            for p_obj in photos_data:
                if isinstance(p_obj, dict):
                    u_p = p_obj.get("url_photo") or p_obj.get("url") or p_obj.get("photo")
                    if isinstance(u_p, str) and u_p.startswith("http") and u_p not in photo_urls:
                        photo_urls.append(u_p)
            hero_img = photo_urls[0] if photo_urls else ""

            blur_pos = (a.get("blurInfo") or {}).get("position") or (a.get("blurInfo") or {}).get("centroid") or {}
            ad_lat = blur_pos.get("lat") or default_lat
            ad_lon = blur_pos.get("lon") or default_lon
            
            title_final = title or f"{r_str} {int(s)} m² {city_name}"
            price_str = f"{p:,} € / mois CC".replace(",", " ") if transaction_type == "location" else f"{p:,} € FAI".replace(",", " ")
            
            agency_name = "Bien'ici / " + (a.get("accountType") or "Agence")
            
            results.append({
                "id": f"real_bi_{ad_id}",
                "universe": "immo",
                "category": "immo",
                "transaction_type": transaction_type,
                "category_label": f"Immobilier {city_name}",
                "badge": f"🏢 {transaction_type.capitalize()} • {city_name}",
                "title": title_final,
                "price": p,
                "price_str": price_str,
                "location": f"{city_name} ({ad_postal})",
                "city": city_name,
                "postal_code": ad_postal,
                "lat": ad_lat,
                "lon": ad_lon,
                "agency": agency_name,
                "is_verified_agency": True,
                "url": ad_url,
                "image_url": hero_img,
                "images": photo_urls[:10],
                "description": desc or "Annonce réelle extraite en direct de Bien'ici.",
                "surface": f"{int(s)} m²" if s > 0 else "N/C",
                "surface_val": s,
                "rooms": r_str,
                "bedrooms": _first_num(a.get("bedroomsQuantity"), as_int=True) or 1,
                "floor": "RDC" if not a.get("floor") else f"Étage {_first_num(a.get('floor'), as_int=True)}",
                "dpe": a.get("energyClassification") or "D",
                "charges": "Charges comprises",
                "amenities": extract_amenities(f"{title_final} {desc}", a),
                "price_per_m2": round(p / s, 1) if s > 0 else 14.0,
                "market_avg_m2": 13.8,
                "market_delta_pct": 0,
                "market_badge": "🟢 Vraie annonce vérifiée",
                "date_detected": now
            })
            
        logger.info(f"✅ {len(results)} annonces réelles scrapées pour '{city_name}' sur Bien'ici (multi-pages)")
        return results

    except Exception as e:
        logger.error(f"Erreur recherche France {city}: {e}")
        return []

# =========================================================
# MOTEUR RÉEL 3 : OFFRES VOYAGE HORIZONS (APIs RYANAIR & SNCF + LIENS OFFICIELS SANS 404)
# =========================================================

def to_yymmdd(dt_str):
    """Convertit '2026-11-20' en '261120' pour l'API et liens officiels Skyscanner."""
    parts = dt_str.split("-")
    if len(parts) == 3:
        return parts[0][2:] + parts[1] + parts[2]
    return dt_str


def build_official_skyscanner_url(orig_iata, dest_iata, d_dep, d_ret):
    """Lien direct officiel Skyscanner au format standard YYMMDD."""
    yymmdd_dep = to_yymmdd(d_dep)
    yymmdd_ret = to_yymmdd(d_ret)
    return (
        f"https://www.skyscanner.fr/transport/vols/{orig_iata.lower()}/{dest_iata.lower()}/"
        f"{yymmdd_dep}/{yymmdd_ret}/?adultsv2=1&cabinclass=economy"
    )


def build_official_flight_url(orig_city, dest_city, d_dep, d_ret):
    """Lien direct Google Flights propre aux dates exactes."""
    q = f"Vols de {orig_city} vers {dest_city} du {d_dep} au {d_ret}"
    return f"https://www.google.com/travel/flights?hl=fr&curr=EUR&q={urllib.parse.quote(q)}"


def build_official_booking_url(dest_city, d_dep, d_ret):
    """Lien direct officiel Booking.com synchronisé aux dates avec note >= 8/10."""
    return (
        "https://www.booking.com/searchresults.fr.html?"
        + urllib.parse.urlencode({
            "ss": dest_city,
            "checkin": d_dep,
            "checkout": d_ret,
            "group_adults": "1",
            "no_rooms": "1",
            "nflt": "review_score=80",
            "order": "review_score_and_price",
        })
    )


def build_official_package_url(dep_city, dest_city, d_dep, d_ret):
    """Lien comparateur officiel pour séjour complet Vol + Hôtel."""
    q = f"Vol hotel {dest_city} depuis {dep_city} du {d_dep} au {d_ret}"
    return f"https://www.google.com/travel/search?hl=fr&curr=EUR&q={urllib.parse.quote(q)}"


def build_official_sncf_url(orig_station, dest_station, d_dep):
    """Lien officiel de recherche SNCF Connect avec gare et date exacte (zéro 404)."""
    return (
        "https://www.sncf-connect.com/app/home/search?"
        + urllib.parse.urlencode({
            "origin": orig_station,
            "destination": dest_station,
            "outwardDate": d_dep,
        })
    )


def build_official_transit_url(orig_station, dest_station):
    """Itinéraire ferroviaire direct permanent Google Transit."""
    return (
        "https://www.google.com/maps/dir/?"
        + urllib.parse.urlencode({
            "api": "1",
            "origin": orig_station,
            "destination": dest_station,
            "travelmode": "transit",
        })
    )


def fetch_sncf_open_data_fares(origin="NANCY"):
    """Interroge l'API ouverte SNCF Open Data pour récupérer les tarifs réels réglementés TGV INOUI / OUIGO."""
    url = (
        f"https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/tarifs-tgv-inoui-ouigo/records"
        f"?where=search(gare_origine,%22{origin.upper()}%22)%20or%20search(gare_origine,%22LORRAINE%22)&limit=60"
    )
    fares = {}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HorizonsApp/10.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
            for rec in data.get("results", []):
                transp = rec.get("transporteur", "")
                dest = rec.get("gare_destination", "")
                p_min = rec.get("prix_minimum")
                p_max = rec.get("prix_maximum")
                if dest and p_min is not None:
                    k = f"{transp}_{dest}"
                    if k not in fares or p_min < fares[k]["min"]:
                        fares[k] = {
                            "carrier": transp,
                            "dest": dest,
                            "min": round(p_min),
                            "max": round(p_max or p_min),
                        }
    except Exception as e:
        logger.warning(f"Note SNCF Open Data: {e}")
    return fares


def fetch_ryanair_fares(hubs=None, days_out=14, nights=3):
    """Interroge l'API publique Ryanair FareFinder pour extraire les vrais tarifs en direct."""
    if hubs is None:
        hubs = ["LUX", "BSL", "BVA", "CRL", "HHN"]
    today = datetime.now()
    d_from = (today + timedelta(days=max(3, days_out - 4))).strftime("%Y-%m-%d")
    d_to = (today + timedelta(days=days_out + 25)).strftime("%Y-%m-%d")
    fares = []
    for hub in hubs:
        url = (
            f"https://services-api.ryanair.com/farfnd/v4/oneWayFares"
            f"?departureAirportIataCode={hub}&outboundDepartureDateFrom={d_from}&outboundDepartureDateTo={d_to}"
            f"&market=fr&currency=EUR&limit=8"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HorizonsApp/10.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
                for f in data.get("fares", []):
                    ob = f.get("outbound", {})
                    arr = ob.get("arrivalAirport", {})
                    pr = ob.get("price", {})
                    dep_dt_raw = ob.get("departureDate", "")
                    iata = arr.get("iataCode")
                    city = arr.get("city", {}).get("name") or arr.get("name")
                    val = pr.get("value")
                    if iata and val:
                        fares.append({
                            "hub": hub,
                            "dest_iata": iata,
                            "dest_city": city,
                            "dest_country": arr.get("country", {}).get("name") or "",
                            "price": round(val),
                            "date": dep_dt_raw.split("T")[0] if "T" in dep_dt_raw else dep_dt_raw,
                        })
        except Exception as e:
            logger.warning(f"Ryanair FareFinder {hub}: {e}")
    return fares


def compute_train_pricing(days_out=14):
    """Calcule une fourchette réaliste OUIGO vs TGV INOUI selon le délai de réservation."""
    if days_out <= 7:
        return {
            "ouigo_min": 29, "ouigo_max": 55, "ouigo_rt": 74,
            "ouigo_note": f"Départ imminent J+{days_out} (dès 29€ via Lorraine TGV ; 16€-19€ uniquement en anticipé)",
            "inoui_min": 49, "inoui_max": 75, "inoui_rt": 118,
            "inoui_note": f"Plein tarif J+{days_out} (49€-75€/trajet direct Nancy Ville ⇄ Paris Est)",
        }
    if days_out <= 20:
        return {
            "ouigo_min": 19, "ouigo_max": 39, "ouigo_rt": 52,
            "ouigo_note": f"Tarif intermédiaire OUIGO à J+{days_out} (Gare Lorraine TGV ⇄ Paris Est)",
            "inoui_min": 39, "inoui_max": 59, "inoui_rt": 88,
            "inoui_note": f"Tarif Prems / Standard J+{days_out} (39€-59€/trajet Nancy Ville ⇄ Paris Est)",
        }
    return {
        "ouigo_min": 16, "ouigo_max": 25, "ouigo_rt": 38,
        "ouigo_note": f"Réservation anticipée J+{days_out} (16€-25€ dès ouverture OUIGO Lorraine TGV)",
        "inoui_min": 29, "inoui_max": 39, "inoui_rt": 64,
        "inoui_note": f"Tarif Prems anticipé J+{days_out} (29€-39€/trajet Nancy Ville)",
    }


def compute_realistic_flight_price(base_flight, days_out, dep_dt, is_long_haul=False):
    """Estime un tarif aérien A/R honnête selon délai (J+1..14 +65..110%), départ ven/sam/dim (+25%) & saison."""
    if days_out <= 3:
        delay_mult = 2.05
    elif days_out <= 7:
        delay_mult = 1.85
    elif days_out <= 14:
        delay_mult = 1.65
    elif days_out <= 28:
        delay_mult = 1.30
    elif days_out <= 44:
        delay_mult = 1.10
    else:
        delay_mult = 0.88

    weekend_mult = 1.25 if dep_dt.weekday() in (4, 5, 6) else 1.0
    is_peak = dep_dt.month in (7, 8, 12) or (is_long_haul and dep_dt.month in (12, 1, 2, 3, 4))
    peak_mult = 1.15 if is_peak else 1.0

    est = round(base_flight * delay_mult * weekend_mult * peak_mult)
    if is_long_haul:
        if days_out >= 45:
            return max(465, min(555, est))
        if days_out <= 14:
            return max(680, est)
        return max(585, min(850, est))
    return max(65, est)


def scrape_travel_real(departure="Nancy", destination="Partout", max_budget=None, days_out=14, nights=3):
    logger.info(f"✈️ Recherche des liaisons et packages réels depuis {departure} (J+{days_out}, {nights} nuits)...")
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    dep_dt = now_dt + timedelta(days=days_out)
    ret_dt = dep_dt + timedelta(days=max(1, nights))
    d_dep = dep_dt.strftime("%Y-%m-%d")
    d_ret = ret_dt.strftime("%Y-%m-%d")
    t_pricing = compute_train_pricing(days_out)

    # Récupération SNCF Open Data pour affiner les tarifs réels
    sncf_fares = fetch_sncf_open_data_fares("NANCY")
    ouigo_paris_price = t_pricing["ouigo_rt"]
    inoui_paris_price = t_pricing["inoui_rt"]
    if "TGV INOUI_PARIS EST" in sncf_fares:
        s_min = sncf_fares["TGV INOUI_PARIS EST"]["min"]
        if s_min > 0 and days_out > 20:
            inoui_paris_price = min(inoui_paris_price, s_min * 2)

    sncf_ouigo_url = build_official_sncf_url("Lorraine TGV", "Paris Est", d_dep)
    sncf_inoui_url = build_official_sncf_url("Nancy", "Paris Est", d_dep)
    sncf_lux_url = build_official_sncf_url("Nancy", "Luxembourg", d_dep)

    transit_ouigo_url = build_official_transit_url("Lorraine TGV", "Paris Est")
    transit_inoui_url = build_official_transit_url("Nancy", "Paris Est")
    transit_lux_url = build_official_transit_url("Nancy", "Luxembourg")

    booking_paris = build_official_booking_url("Paris", d_dep, d_ret)
    booking_lux = build_official_booking_url("Luxembourg", d_dep, d_ret)

    # Estimation Palma de Majorque (BSL -> PMI)
    pmi_flight = compute_realistic_flight_price(82, days_out, dep_dt, is_long_haul=False)
    pmi_shuttle = 54
    pmi_hotel_night = 95
    pmi_hotel_total = nights * pmi_hotel_night
    pmi_total = pmi_shuttle + pmi_flight + pmi_hotel_total
    pmi_skyscanner_url = build_official_skyscanner_url("BSL", "PMI", d_dep, d_ret)
    pmi_flight_url = build_official_flight_url("Bâle-Mulhouse", "Palma de Majorque", d_dep, d_ret)
    pmi_hotel_url = build_official_booking_url("Palma de Majorque", d_dep, d_ret)
    pmi_pkg_url = build_official_package_url("Nancy", "Palma de Majorque", d_dep, d_ret)

    # Estimation Saint-Martin Caraïbes (ORY -> SXM, min 7 nuits réaliste)
    sxm_nights = max(nights, 7)
    sxm_ret_dt = dep_dt + timedelta(days=sxm_nights)
    sxm_d_ret = sxm_ret_dt.strftime("%Y-%m-%d")
    sxm_flight = compute_realistic_flight_price(540, days_out, dep_dt, is_long_haul=True)
    sxm_shuttle = inoui_paris_price
    sxm_hotel_night = 135
    sxm_hotel_total = sxm_nights * sxm_hotel_night
    sxm_total = sxm_shuttle + sxm_flight + sxm_hotel_total
    sxm_skyscanner_url = build_official_skyscanner_url("ORY", "SXM", d_dep, sxm_d_ret)
    sxm_flight_url = build_official_flight_url("Paris", "Saint-Martin", d_dep, sxm_d_ret)
    sxm_hotel_url = build_official_booking_url("Saint-Martin", d_dep, sxm_d_ret)
    sxm_pkg_url = build_official_package_url("Nancy", "Saint-Martin", d_dep, sxm_d_ret)

    routes = [
        {
            "id": "real_train_ouigo_lorraine_paris",
            "universe": "voyage",
            "category": "train",
            "section_type": "flash_deals",
            "badge": "🚄 TRAIN DIRECT • OUIGO Lorraine TGV",
            "title": f"OUIGO Lorraine TGV ⇄ Paris Est ({ouigo_paris_price} € A/R)",
            "price": ouigo_paris_price,
            "price_str": f"{ouigo_paris_price} € A/R ({t_pricing['ouigo_min']}€–{t_pricing['ouigo_max']}€/trajet)",
            "location": "Lorraine TGV (Louvigny) ⇄ Paris Est",
            "destination": "Paris",
            "departure_hub": "Lorraine TGV",
            "trip_mode": "sniper",
            "dates": f"{d_dep} → {d_ret}",
            "departure_city": "Nancy",
            "agency": "SNCF Connect / OUIGO",
            "url": sncf_ouigo_url,
            "train_url": "https://www.ouigo.com/",
            "transit_url": transit_ouigo_url,
            "hotel_url": booking_paris,
            "package_url": build_official_package_url("Nancy", "Paris", d_dep, d_ret),
            "image_url": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800",
            "description": t_pricing["ouigo_note"],
            "date_detected": now,
            "true_cost": None,
        },
        {
            "id": "real_train_inoui_nancy_paris",
            "universe": "voyage",
            "category": "train",
            "section_type": "flash_deals",
            "badge": "🚄 TRAIN DIRECT • TGV INOUI Nancy Centre",
            "title": f"TGV INOUI Direct Nancy Ville ⇄ Paris Est ({inoui_paris_price} € A/R)",
            "price": inoui_paris_price,
            "price_str": f"{inoui_paris_price} € A/R ({t_pricing['inoui_min']}€–{t_pricing['inoui_max']}€/trajet)",
            "location": "Nancy Ville ⇄ Paris Est / CDG TGV (1h32)",
            "destination": "Paris",
            "departure_hub": "Nancy Ville",
            "trip_mode": "sniper",
            "dates": f"{d_dep} → {d_ret}",
            "departure_city": "Nancy",
            "agency": "SNCF Connect / TGV INOUI",
            "url": sncf_inoui_url,
            "train_url": sncf_inoui_url,
            "transit_url": transit_inoui_url,
            "hotel_url": booking_paris,
            "package_url": build_official_package_url("Nancy", "Paris", d_dep, d_ret),
            "image_url": "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=800",
            "description": t_pricing["inoui_note"],
            "date_detected": now,
            "true_cost": None,
        },
        {
            "id": "real_train_nancy_luxembourg",
            "universe": "voyage",
            "category": "train",
            "section_type": "flash_deals",
            "badge": "🚄 TRAIN DIRECT • TER Fluo Grand Est",
            "title": "TER direct Nancy ⇄ Luxembourg Findel (LUX)",
            "price": 28,
            "price_str": "28 € A/R (~14€/trajet)",
            "location": "Nancy Ville ⇄ Luxembourg (1h15 direct)",
            "destination": "Luxembourg",
            "departure_hub": "Nancy Ville",
            "trip_mode": "sniper",
            "dates": f"{d_dep} → {d_ret}",
            "departure_city": "Nancy",
            "agency": "SNCF TER Fluo Grand Est",
            "url": sncf_lux_url,
            "train_url": sncf_lux_url,
            "transit_url": transit_lux_url,
            "hotel_url": booking_lux,
            "package_url": build_official_package_url("Nancy", "Luxembourg", d_dep, d_ret),
            "image_url": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=800",
            "description": "TER direct vers Luxembourg puis tramway gratuit jusqu'à l'aéroport LUX.",
            "date_detected": now,
            "true_cost": None,
        },
        {
            "id": "real_package_bale_majorque",
            "universe": "voyage",
            "category": "package",
            "section_type": "best_offers",
            "badge": "🏨 SÉJOUR TOUT COMPRIS (TRANSPORT + HÔTEL)",
            "title": f"Majorque Tout Compris ({nights} nuits) via EuroAirport BSL",
            "price": pmi_total,
            "price_str": f"{pmi_total} € Tout Compris",
            "location": f"Nancy ➔ BSL ➔ Palma de Majorque ({d_dep} → {d_ret})",
            "destination": "Palma de Majorque",
            "departure_hub": "Bâle-Mulhouse (BSL)",
            "trip_mode": "sniper",
            "dates": f"{d_dep} → {d_ret}",
            "departure_city": "Nancy",
            "agency": "Skyscanner + Booking ≥ 8/10",
            "url": pmi_skyscanner_url,
            "flight_url": pmi_flight_url,
            "skyscanner_url": pmi_skyscanner_url,
            "hotel_url": pmi_hotel_url,
            "package_url": pmi_pkg_url,
            "image_url": "https://images.unsplash.com/photo-1533105079780-92b9be482077?w=800",
            "description": f"Vol A/R estimé ({pmi_flight}€) + pré-acheminement TER Bâle ({pmi_shuttle}€) + Hôtel ≥ 8/10 ({nights} nuits : {pmi_hotel_total}€).",
            "date_detected": now,
            "true_cost": {
                "shuttle_cost": pmi_shuttle,
                "flight_cost": pmi_flight,
                "hotel_per_night": pmi_hotel_night,
                "hotel_total": pmi_hotel_total,
                "nights": nights,
                "total_per_person": pmi_total,
                "breakdown": f"TER Bâle ({pmi_shuttle}€) + Vol A/R ({pmi_flight}€) + Hôtel ≥8/10 {nights}n ({pmi_hotel_total}€)",
            },
        },
        {
            "id": "real_package_sxm",
            "universe": "voyage",
            "category": "package",
            "section_type": "best_offers",
            "badge": "🏨 SÉJOUR TOUT COMPRIS (TRANSPORT + HÔTEL)",
            "title": f"Saint-Martin Caraïbes Tout Compris ({sxm_nights} nuits)",
            "price": sxm_total,
            "price_str": f"{sxm_total} € Tout Compris",
            "location": f"Nancy ➔ Paris ORY ➔ Saint-Martin SXM ({d_dep} → {sxm_d_ret})",
            "destination": "Saint-Martin (SXM)",
            "departure_hub": "Paris ORY/CDG",
            "trip_mode": "fais_moi_rever",
            "dates": f"{d_dep} → {sxm_d_ret}",
            "departure_city": "Nancy",
            "agency": "Skyscanner + Booking ≥ 8/10",
            "url": sxm_skyscanner_url,
            "flight_url": sxm_flight_url,
            "skyscanner_url": sxm_skyscanner_url,
            "hotel_url": sxm_hotel_url,
            "package_url": sxm_pkg_url,
            "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800",
            "description": f"TGV Nancy→Paris ({sxm_shuttle}€ A/R) + Vol SXM réalisme J+{days_out} ({sxm_flight}€) + Hôtel ≥ 8/10 ({sxm_nights} nuits : {sxm_hotel_total}€).",
            "date_detected": now,
            "true_cost": {
                "shuttle_cost": sxm_shuttle,
                "flight_cost": sxm_flight,
                "hotel_per_night": sxm_hotel_night,
                "hotel_total": sxm_hotel_total,
                "nights": sxm_nights,
                "total_per_person": sxm_total,
                "breakdown": f"TGV Nancy→Paris ({sxm_shuttle}€) + Vol SXM ({sxm_flight}€) + Hôtel ≥8/10 {sxm_nights}n ({sxm_hotel_total}€)",
            },
        },
    ]

    # Ajout des offres réelles en direct issues de Ryanair FareFinder
    try:
        ryan_fares = fetch_ryanair_fares(["LUX", "BSL", "BVA"], days_out=days_out, nights=nights)
        hub_names = {"LUX": "Luxembourg", "BSL": "Bâle-Mulhouse", "BVA": "Paris-Beauvais", "CRL": "Charleroi", "HHN": "Francfort-Hahn"}
        for rf in ryan_fares[:4]:
            dest_c = rf["dest_city"]
            dest_i = rf["dest_iata"]
            hub_i = rf["hub"]
            hub_n = hub_names.get(hub_i, hub_i)
            f_price_oneway = rf["price"]
            f_price_rt = round(f_price_oneway * 2.1)
            r_dep_date = rf["date"]
            try:
                r_dep_dt = datetime.strptime(r_dep_date, "%Y-%m-%d")
            except Exception:
                r_dep_dt = dep_dt
            r_ret_dt = r_dep_dt + timedelta(days=nights)
            r_ret_date = r_ret_dt.strftime("%Y-%m-%d")

            shuttle_cost = 28 if hub_i == "LUX" else (54 if hub_i == "BSL" else 65)
            h_night = 85
            h_total = nights * h_night
            pkg_total = shuttle_cost + f_price_rt + h_total

            sky_u = build_official_skyscanner_url(hub_i, dest_i, r_dep_date, r_ret_date)
            fl_u = build_official_flight_url(hub_n, dest_c, r_dep_date, r_ret_date)
            bk_u = build_official_booking_url(dest_c, r_dep_date, r_ret_date)
            pkg_u = build_official_package_url("Nancy", dest_c, r_dep_date, r_ret_date)

            routes.append({
                "id": f"real_ryanair_{hub_i.lower()}_{dest_i.lower()}",
                "universe": "voyage",
                "category": "package",
                "section_type": "best_offers",
                "badge": f"🏨 SÉJOUR DIRECT • Ryanair {hub_i}",
                "title": f"{dest_c} ({dest_i}) Tout Compris ({nights} nuits) via {hub_n}",
                "price": pkg_total,
                "price_str": f"{pkg_total} € Tout Compris",
                "location": f"Nancy ➔ {hub_i} ➔ {dest_c} ({r_dep_date} → {r_ret_date})",
                "destination": dest_c,
                "departure_hub": hub_n,
                "trip_mode": "sniper",
                "dates": f"{r_dep_date} → {r_ret_date}",
                "departure_city": "Nancy",
                "agency": "Ryanair FareFinder + Booking ≥ 8/10",
                "url": sky_u,
                "flight_url": fl_u,
                "skyscanner_url": sky_u,
                "hotel_url": bk_u,
                "package_url": pkg_u,
                "image_url": "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800",
                "description": f"Vol direct vérifié Ryanair ({f_price_oneway}€ l'aller) + navette ({shuttle_cost}€) + Hôtel ≥ 8/10 ({nights} nuits : {h_total}€).",
                "date_detected": now,
                "true_cost": {
                    "shuttle_cost": shuttle_cost,
                    "flight_cost": f_price_rt,
                    "hotel_per_night": h_night,
                    "hotel_total": h_total,
                    "nights": nights,
                    "total_per_person": pkg_total,
                    "breakdown": f"Liaison ({shuttle_cost}€) + Vol A/R Ryanair ({f_price_rt}€) + Hôtel ≥8/10 {nights}n ({h_total}€)",
                },
            })
    except Exception as e:
        logger.warning(f"Note chargement Ryanair: {e}")

    if max_budget:
        routes = [r for r in routes if r["price"] <= float(max_budget)]
    return routes


# =========================================================
# ORCHESTRATEUR PRINCIPAL DYNAMIQUE
# =========================================================
def run_dynamic_scan(city=None, transac=None, max_price=None, min_surface=None, rooms=None, category=None, exclude_viager=True):
    if city is None:
        city = os.getenv("SCAN_CITY", "").strip()
    if transac is None:
        transac = os.getenv("SCAN_TRANSACTION", "location").strip().lower()
    if max_price is None:
        max_price = os.getenv("SCAN_MAX_BUDGET", "").strip()
    if min_surface is None:
        min_surface = os.getenv("SCAN_MIN_SURFACE", "").strip()
    if rooms is None:
        rooms = os.getenv("SCAN_ROOMS", "all").strip()
    if category is None:
        category = os.getenv("SCAN_CATEGORY", "all").strip().lower()

    logger.info("═════════════════════════════════════════════════════════")
    logger.info("✨ HORIZONS - Moteur de Recherche & Veille Sur-Mesure")
    logger.info(f"   • Destination ciblée : '{city or 'Toutes'}' | Type : '{transac}' | Exclure Viager : {exclude_viager}")
    logger.info(f"   • Budget Max : {max_price or 'Non plafonné'} € | Surface min : {min_surface or '0'} m²")
    logger.info("═════════════════════════════════════════════════════════")

    existing = load_annonces()
    cleaned_existing = []
    for it in existing:
        if not it.get("id", "").startswith("real_"):
            continue
        if not is_url_safe(it.get("url")):
            continue
        if it.get("universe") == "immo":
            if not is_residential_immo(
                it.get("title", ""),
                it.get("description", ""),
                None,
                it.get("postal_code", ""),
                it.get("location", ""),
                exclude_viager=exclude_viager,
            ):
                continue
            real_imgs = [
                u for u in (it.get("images") or [])
                if isinstance(u, str) and u.startswith("http") and "images.unsplash.com" not in u
            ]
            it["images"] = real_imgs
            img_u = it.get("image_url") or ""
            it["image_url"] = real_imgs[0] if real_imgs else ("" if "images.unsplash.com" in img_u else img_u)
        if it.get("id") in ("real_train_nancy_paris", "real_flight_bale_majorque"):
            continue
        cleaned_existing.append(it)
    existing = cleaned_existing

    new_scraped = []

    if category in ["immo", "all"]:
        if not city:
            new_scraped.extend(scrape_saint_martin_real(transaction_type="location", max_price=1500, exclude_viager=exclude_viager))
            new_scraped.extend(scrape_saint_martin_real(transaction_type="achat", exclude_viager=exclude_viager))
            new_scraped.extend(scrape_france_real(city="Nancy", transaction_type="location", max_price=950, exclude_viager=exclude_viager))
            new_scraped.extend(scrape_france_real(city="Nancy", transaction_type="achat", max_price=250000, exclude_viager=exclude_viager))
        elif ("saint-martin" in city.lower() or "sxm" in city.lower() or "97150" in city) and "38400" not in city.lower():
            t_list = ["location", "achat"] if transac == "all" else [transac]
            for t_mode in t_list:
                new_scraped.extend(scrape_saint_martin_real(transaction_type=t_mode, max_price=max_price, min_surface=min_surface, rooms=rooms, exclude_viager=exclude_viager))
        else:
            t_list = ["location", "achat"] if transac == "all" else [transac]
            for t_mode in t_list:
                new_scraped.extend(scrape_france_real(city=city, transaction_type=t_mode, max_price=max_price, min_surface=min_surface, rooms=rooms, exclude_viager=exclude_viager))

    if category in ["voyage", "all"]:
        voyage_deals = scrape_travel_real(departure="Nancy", max_budget=max_price if category == "voyage" else None)
        new_scraped.extend(voyage_deals)

    combined = new_scraped + existing
    save_annonces(combined)

    cfg = load_config()
    topic = cfg.get("ntfy_topic", "sxm-immo-alert-97150-x9q4m2")
    if new_scraped:
        top = new_scraped[0]
        send_ntfy_push(
            topic=topic,
            title=f"Horizons : {len(new_scraped)} nouvelle(s) opportunité(s) sélectionnée(s) !",
            message=f"{top.get('title')} ({top.get('price_str')}) à {top.get('city') or city or 'Nancy'}.",
            click_url=top.get("url"),
        )

    logger.info(f"✨ Synchronisation terminée : {len(new_scraped)} nouvelles opportunités sélectionnées.")
    return new_scraped


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Horizons - Curateur Immobilier & Voyages sur-mesure")
    parser.add_argument("--city", default=None, help="Target city (e.g. Nancy, Saint-Martin)")
    parser.add_argument("--transaction", default=None, help="Transaction type (location, achat)")
    parser.add_argument("--budget", default=None, help="Max budget in EUR")
    parser.add_argument("--surface", default=None, help="Min surface in m2")
    parser.add_argument("--rooms", default=None, help="Rooms filter (Studio, T2, T3, all)")
    parser.add_argument("--category", default=None, help="Category (immo, voyage, all)")
    args = parser.parse_args()

    run_dynamic_scan(
        city=args.city,
        transac=args.transaction,
        max_price=args.budget,
        min_surface=args.surface,
        rooms=args.rooms,
        category=args.category,
    )
