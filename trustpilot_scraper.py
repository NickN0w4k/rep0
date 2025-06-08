# trustpilot_scraper.py
import sqlite3
import requests
import json
from datetime import datetime
import time # Importiere das time Modul
from collections import deque # Für effizientes Verwalten der Zeitstempel

# --- Globals & Constants ---
DB_NAME = 'Datenbank.db'
# This Build ID is extracted from the example URL. It might change over time,
# making the scraper break. For a robust solution, this ID might need to be
# dynamically discovered or updated.
TRUSTPILOT_JSON_BUILD_ID = "businessunitprofile-consumersite-2.3939.0"

# Rate Limiting für Trustpilot
MAX_REQUESTS_PER_TIMEFRAME = 800 # Wieder erhöht, da Proxy-Wechsel manuell erfolgt
TIMEFRAME_SECONDS = 5 * 60  # 5 Minuten
request_timestamps = deque()

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- Database Helper Functions (adapted from kununu_scraper.py) ---
def get_or_create_unternehmen(conn, unternehmen_name):
    """Gets the ID of a company. Creates it if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM unternehmen WHERE name = ?", (unternehmen_name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        cursor.execute("INSERT INTO unternehmen (name) VALUES (?)", (unternehmen_name,))
        conn.commit()
        return cursor.lastrowid

def get_plattform_id(conn, plattform_name="Trustpilot"):
    """Gets the ID of a platform (default "Trustpilot")."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM plattformen WHERE name = ?", (plattform_name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        cursor.execute("INSERT OR IGNORE INTO plattformen (name) VALUES (?)", (plattform_name,))
        conn.commit()
        cursor.execute("SELECT id FROM plattformen WHERE name = ?", (plattform_name,))
        row = cursor.fetchone()
        if row:
            return row['id']
        else:
            raise Exception(f"Plattform {plattform_name} konnte nicht gefunden oder erstellt werden.")

def get_or_create_profil(conn, unternehmen_id, plattform_id, profil_url):
    """Gets the ID of a company profile. Creates it if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM unternehmens_profile WHERE url = ?", (profil_url,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        try:
            cursor.execute("INSERT INTO unternehmens_profile (unternehmen_id, plattform_id, url) VALUES (?, ?, ?)",
                           (unternehmen_id, plattform_id, profil_url))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Fallback if URL is not unique but unternehmen_id/plattform_id combo is
            cursor.execute("SELECT id FROM unternehmens_profile WHERE unternehmen_id = ? AND plattform_id = ?",
                           (unternehmen_id, plattform_id))
            row = cursor.fetchone()
            if row:
                print(f"Hinweis: Profil für Unternehmen ID {unternehmen_id} und Plattform ID {plattform_id} existiert bereits, ggf. mit anderer URL. Verwende existierendes Profil.")
                return row['id']
            else:
                # This case should ideally not happen if the first select by URL failed and then insert failed.
                # It implies the unique constraint on URL was violated by another record not matching this U_ID/P_ID.
                # Or, the UNIQUE(unternehmen_id, plattform_id) was violated.
                raise Exception(f"Profil konnte nicht gefunden oder erstellt werden für URL {profil_url} trotz IntegrityError.")


def add_profil_verlauf_entry_trustpilot(conn, profil_id, trust_score, num_reviews):
    """Adds an entry to the profile history for Trustpilot."""
    cursor = conn.cursor()
    try:
        current_time = datetime.now()
        # recommendation_rate is Kununu-specific, so it's passed as NULL for Trustpilot
        cursor.execute("""
            INSERT INTO profil_verlauf (profil_id, gesamtdurchschnitt, anzahl_bewertungen_gesamt, scraping_datum, recommendation_rate)
            VALUES (?, ?, ?, ?, NULL)
        """, (profil_id, trust_score, num_reviews, current_time))
        conn.commit()
        print(f"Neuer Trustpilot Verlaufseintrag für Profil ID {profil_id}: Score={trust_score}, Bewertungen={num_reviews} ({current_time}).")
    except Exception as e:
        print(f"Fehler beim Hinzufügen des Trustpilot Profilverlaufs für Profil ID {profil_id}: {e}")
        conn.rollback()

def get_existing_trustpilot_review_data(conn, profil_id, trustpilot_review_id):
    """Fetches existing review data by Trustpilot review ID."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, platform_data_updated_at, is_deleted
        FROM bewertungen
        WHERE profil_id = ? AND platform_review_id = ?
    """, (profil_id, trustpilot_review_id))
    row = cursor.fetchone()
    if row:
        return {"db_id": row["id"], "platform_data_updated_at_db": row["platform_data_updated_at"], "is_deleted_db": row["is_deleted"]}
    return None

def add_or_update_trustpilot_review(conn, profil_id, review_json):
    """Adds or updates a single Trustpilot review in the database."""
    cursor = conn.cursor()
    
    review_id_tp = review_json.get('id')
    sterne = review_json.get('rating')
    titel = review_json.get('title')
    text = review_json.get('text')
    
    published_date = review_json.get('dates', {}).get('publishedDate')
    experienced_date = review_json.get('dates', {}).get('experiencedDate')
    updated_date = review_json.get('dates', {}).get('updatedDate') # This is platform_data_updated_at
    
    consumer_name = review_json.get('consumer', {}).get('displayName')
    language = review_json.get('language')
    source = review_json.get('source')
    likes = review_json.get('likes', 0)
    is_verified = review_json.get('labels', {}).get('verification', {}).get('isVerified', False)

    if not all([review_id_tp, sterne is not None, published_date]):
        print(f"FEHLER: Unvollständige Kerndaten für Trustpilot Bewertung ID {review_id_tp}, Titel: '{titel}'. Übersprungen.")
        return

    existing_review = get_existing_trustpilot_review_data(conn, profil_id, review_id_tp)
    current_time = datetime.now()

    if existing_review:
        db_id = existing_review['db_id']
        updated_at_db = existing_review['platform_data_updated_at_db']
        is_deleted_db = existing_review['is_deleted_db']

        if updated_date and (updated_at_db is None or updated_date > updated_at_db or is_deleted_db):
            print(f"  -> Trustpilot Bewertung {review_id_tp} wird aktualisiert (ID: {db_id}).")
            try:
                cursor.execute("""
                    UPDATE bewertungen
                    SET sterne = ?, titel = ?, text = ?, datum = ?, platform_data_updated_at = ?,
                        consumer_display_name = ?, date_of_experience = ?, review_language = ?,
                        review_source = ?, review_likes = ?, is_verified_by_platform = ?,
                        last_seen_scraping_datum = ?, is_deleted = 0
                    WHERE id = ?
                """, (sterne, titel, text, published_date, updated_date,
                      consumer_name, experienced_date, language, source, likes, is_verified,
                      current_time, db_id))
                conn.commit()
            except Exception as e:
                print(f"Fehler beim Aktualisieren der Trustpilot Bewertung ID {db_id}: {e}")
                conn.rollback()
        else:
            # No change, just update last_seen and ensure is_deleted is 0
            cursor.execute("UPDATE bewertungen SET last_seen_scraping_datum = ?, is_deleted = 0 WHERE id = ?", (current_time, db_id))
            conn.commit()
            print(f"  -> Trustpilot Bewertung {review_id_tp} unverändert. 'last_seen' aktualisiert.")
    else:
        # New review
        print(f"  -> Neue Trustpilot Bewertung {review_id_tp} wird hinzugefügt.")
        try:
            cursor.execute("""
                INSERT INTO bewertungen (
                    profil_id, sterne, titel, text, datum, platform_review_id,
                    platform_data_updated_at, last_seen_scraping_datum, is_deleted,
                    consumer_display_name, date_of_experience, review_language,
                    review_source, review_likes, is_verified_by_platform, scraping_datum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (profil_id, sterne, titel, text, published_date, review_id_tp,
                  updated_date, current_time, 0,
                  consumer_name, experienced_date, language, source, likes, is_verified, current_time))
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"HINWEIS (Integrity): Trustpilot Bewertung {review_id_tp} konnte nicht hinzugefügt werden (existiert evtl. doch und wurde bereits aktualisiert).")
        except Exception as e:
            print(f"Fehler beim Hinzufügen der Trustpilot Bewertung {review_id_tp}: {e}")
            conn.rollback()

# --- Rate Limiting Helper ---
def _apply_trustpilot_rate_limit():
    """
    Stellt sicher, dass das Rate-Limit für Trustpilot-Anfragen eingehalten wird.
    Wartet, falls notwendig.
    """
    global request_timestamps
    current_time = time.time()

    # Entferne Zeitstempel, die älter als das Zeitfenster sind
    while request_timestamps and request_timestamps[0] < current_time - TIMEFRAME_SECONDS:
        request_timestamps.popleft()

    if len(request_timestamps) >= MAX_REQUESTS_PER_TIMEFRAME:
        oldest_relevant_request_time = request_timestamps[0]
        time_to_wait = (oldest_relevant_request_time + TIMEFRAME_SECONDS) - current_time + 0.5 # +0.5s Puffer
        if time_to_wait > 0:
            print(f"Trustpilot Rate-Limit fast erreicht ({len(request_timestamps)} Anfragen). Warte {time_to_wait:.2f} Sekunden...")
            time.sleep(time_to_wait)
            _apply_trustpilot_rate_limit() # Erneuter Check nach dem Warten

# --- Trustpilot Scraping Functions ---
def fetch_trustpilot_page_json(json_url):
    """Fetches and parses JSON data from a Trustpilot URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json'
    }
    try:
        _apply_trustpilot_rate_limit() # Rate-Limit prüfen/anwenden VOR der Anfrage
        
        # Zeitstempel für die aktuelle Anfrage hinzufügen, NACHDEM das Rate-Limit bestanden wurde
        request_timestamps.append(time.time())
        print(f"Rufe Trustpilot JSON API ab: {json_url}")
        response = requests.get(json_url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen der Trustpilot JSON-Daten von {json_url}: {e}")
    except json.JSONDecodeError as e:
        print(f"Fehler beim Parsen der Trustpilot JSON-Antwort von {json_url}: {e}")
    return None

def main_trustpilot_scraper(trustpilot_profile_base_url, json_build_id=TRUSTPILOT_JSON_BUILD_ID, manual_unternehmen_name=None):
    """
    Main function for scraping a Trustpilot company profile.

    Args:
        trustpilot_profile_base_url (str): The base URL of the Trustpilot profile 
                                           (e.g., "https://de.trustpilot.com/review/www.mindfactory.de").
        json_build_id (str): The build ID for the JSON API URL.
        manual_unternehmen_name (str, optional): Manually provided company name.
                                                 If provided, this name is used for DB operations.
    """
    conn = None
    try:
        conn = get_db_connection()
        
        # Extract slug from base URL
        if not trustpilot_profile_base_url.endswith('/'):
            trustpilot_profile_base_url += '/'
        slug = trustpilot_profile_base_url.split('/review/')[1].split('/')[0]
        if not slug:
            print(f"FEHLER: Konnte Slug nicht aus Trustpilot URL extrahieren: {trustpilot_profile_base_url}")
            return

        # Fetch initial page to get company info and total pages
        initial_json_url = f"https://de.trustpilot.com/_next/data/{json_build_id}/review/{slug}.json"
        print(f"Starte Trustpilot Scraper für Slug: {slug} mit URL: {initial_json_url}")
        
        initial_data = fetch_trustpilot_page_json(initial_json_url)
        if not initial_data or "pageProps" not in initial_data or "businessUnit" not in initial_data["pageProps"]:
            print(f"FEHLER: Konnte initiale JSON-Daten für {slug} nicht laden oder ungültige Struktur.")
            return

        business_unit = initial_data["pageProps"]["businessUnit"]
        company_name_from_json = business_unit.get("displayName")
        trust_score = business_unit.get("trustScore")
        total_reviews_count = business_unit.get("numberOfReviews")
        
        pagination_info = initial_data["pageProps"].get("filters", {}).get("pagination", {})
        total_pages = pagination_info.get("totalPages", 1)

        # Prioritize manually entered name, otherwise use name from JSON
        final_unternehmen_name = manual_unternehmen_name if manual_unternehmen_name else company_name_from_json

        if not final_unternehmen_name:
            print(f"FEHLER: Unternehmensname weder manuell angegeben noch in JSON-Daten für {slug} gefunden.")
            return

        print(f"Unternehmen (final): {final_unternehmen_name}, TrustScore: {trust_score}, Bewertungen: {total_reviews_count}, Seiten: {total_pages}")
        if manual_unternehmen_name and company_name_from_json and manual_unternehmen_name.lower() != company_name_from_json.lower():
            print(f"HINWEIS: Manueller Name '{manual_unternehmen_name}' weicht von Trustpilot-Name '{company_name_from_json}' ab. Manueller Name wird verwendet.")

        unternehmen_id = get_or_create_unternehmen(conn, final_unternehmen_name)
        plattform_id = get_plattform_id(conn, "Trustpilot")
        # Use the base profile URL for storing in the database
        db_profile_url = f"https://de.trustpilot.com/review/{slug}"
        profil_id = get_or_create_profil(conn, unternehmen_id, plattform_id, db_profile_url)

        if trust_score is not None and total_reviews_count is not None:
            add_profil_verlauf_entry_trustpilot(conn, profil_id, trust_score, total_reviews_count)
        
        # --- Mark all existing reviews for this profile as potentially deleted ---
        # This helps in identifying reviews that were removed from the platform
        cursor = conn.cursor()
        cursor.execute("UPDATE bewertungen SET is_deleted = 1, last_seen_scraping_datum = ? WHERE profil_id = ?", (datetime.now(), profil_id))
        conn.commit()
        print(f"Alle bestehenden Bewertungen für Profil ID {profil_id} als 'is_deleted=1' markiert vor dem Scannen.")

        pages_since_last_manual_pause = 0
        MANUAL_PAUSE_AFTER_PAGES = 200

        # Process reviews from all pages
        for page_num in range(1, total_pages + 1):
            current_page_json_url = f"https://de.trustpilot.com/_next/data/{json_build_id}/review/{slug}.json?page={page_num}"
            if page_num == 1 and initial_data: # Use already fetched data for page 1
                page_data = initial_data
            else:
                # Der einfache time.sleep(2) wird durch den Rate-Limiter _apply_trustpilot_rate_limit
                # ersetzt, der vor dem fetch_trustpilot_page_json Aufruf greift.
                # Ein kleiner, genereller Sleep kann trotzdem sinnvoll sein, um nicht zu aggressiv zu wirken,
                # auch wenn das Rate-Limit noch nicht erreicht ist. Erhöht für mehr Vorsicht.

                # Manuelle Pause nach X Seiten
                if pages_since_last_manual_pause >= MANUAL_PAUSE_AFTER_PAGES:
                    print(f"\n--- MANUELLE PAUSE ---")
                    print(f"{MANUAL_PAUSE_AFTER_PAGES} Seiten wurden gescraped.")
                    input("Bitte wechsle jetzt den Proxy und drücke dann ENTER, um fortzufahren...")
                    print(f"Scraping wird fortgesetzt...\n")
                    pages_since_last_manual_pause = 0 # Zähler zurücksetzen
                time.sleep(0.5) # Generelle Pause zwischen den Seiten wieder reduziert
                page_data = fetch_trustpilot_page_json(current_page_json_url)

            if not page_data or "pageProps" not in page_data or "reviews" not in page_data["pageProps"]:
                print(f"FEHLER: Konnte JSON-Daten für Seite {page_num} von {slug} nicht laden oder ungültige Struktur.")
                continue
            
            reviews_on_page = page_data["pageProps"]["reviews"]
            if not reviews_on_page:
                print(f"Keine Bewertungen auf Seite {page_num} für {slug} gefunden.")
                continue

            print(f"Verarbeite {len(reviews_on_page)} Bewertungen von Seite {page_num}/{total_pages} für {final_unternehmen_name}...")
            for review_item_json in reviews_on_page:
                add_or_update_trustpilot_review(conn, profil_id, review_item_json)
            pages_since_last_manual_pause += 1
        
        print(f"Trustpilot Scraping für {final_unternehmen_name} abgeschlossen.")

    except Exception as e:
        print(f"Ein Fehler ist im Trustpilot Hauptprozess aufgetreten: {e}")
    finally:
        if conn:
            conn.close()
            print("Trustpilot: Datenbankverbindung geschlossen.")

if __name__ == '__main__':
    # --- WICHTIG: Stelle sicher, dass database_setup.py vorher einmal ausgeführt wurde! ---
    # from database_setup import setup_database
    # setup_database() # Nur einmalig oder bei Bedarf ausführen
    
    # Beispielaufruf:
    test_trustpilot_url = "https://de.trustpilot.com/review/www.mindfactory.de"
    # Der json_build_id wird standardmäßig aus der Konstante oben verwendet.
    # Man könnte ihn auch hier übergeben: main_trustpilot_scraper(test_trustpilot_url, "neuer_build_id_falls_bekannt")
    
    print(f"Starte Trustpilot-Scraper für: {test_trustpilot_url}")
    main_trustpilot_scraper(test_trustpilot_url)
    print("Trustpilot-Scraper-Durchlauf beendet.")
