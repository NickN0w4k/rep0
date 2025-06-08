# kununu_scraper.py
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re # Für das Parsen von Zahlen
import json # Für das Verarbeiten von JSON-Daten

# Name der Datenbankdatei
DB_NAME = 'Datenbank.db'

def get_db_connection():
    """Stellt eine Verbindung zur SQLite-Datenbank her."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Ermöglicht Zugriff auf Spalten per Namen
    return conn

# --- Datenbank-Hilfsfunktionen ---

def get_or_create_unternehmen(conn, unternehmen_name):
    """
    Holt die ID eines Unternehmens. Legt es neu an, falls nicht vorhanden.

    Args:
        conn: SQLite-Datenbankverbindung.
        unternehmen_name (str): Name des Unternehmens.

    Returns:
        int: ID des Unternehmens.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM unternehmen WHERE name = ?", (unternehmen_name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        cursor.execute("INSERT INTO unternehmen (name) VALUES (?)", (unternehmen_name,))
        conn.commit()
        return cursor.lastrowid

def get_plattform_id(conn, plattform_name="Kununu"):
    """
    Holt die ID einer Plattform (standardmäßig "Kununu").

    Args:
        conn: SQLite-Datenbankverbindung.
        plattform_name (str): Name der Plattform.

    Returns:
        int: ID der Plattform.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM plattformen WHERE name = ?", (plattform_name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        # Plattform sollte durch database_setup.py vorbefüllt sein, aber zur Sicherheit hier ein Fallback.
        cursor.execute("INSERT OR IGNORE INTO plattformen (name) VALUES (?)", (plattform_name,))
        conn.commit()
        cursor.execute("SELECT id FROM plattformen WHERE name = ?", (plattform_name,))
        row = cursor.fetchone()
        if row:
            return row['id']
        else:
            raise Exception(f"Plattform {plattform_name} konnte nicht gefunden oder erstellt werden.")

def get_or_create_profil(conn, unternehmen_id, plattform_id, profil_url):
    """
    Holt die ID eines Unternehmensprofils. Legt es neu an, falls nicht vorhanden.
    Ein Profil verknüpft Unternehmen und Plattform via URL.

    Args:
        conn: SQLite-Datenbankverbindung.
        unternehmen_id (int): ID des Unternehmens.
        plattform_id (int): ID der Plattform.
        profil_url (str): URL des Unternehmensprofils.

    Returns:
        int: ID des Unternehmensprofils.
    """
    cursor = conn.cursor()
    # Versuche, das Profil anhand der URL und der IDs zu finden.
    cursor.execute("""
        SELECT id FROM unternehmens_profile
        WHERE unternehmen_id = ? AND plattform_id = ? AND url = ?
    """, (unternehmen_id, plattform_id, profil_url))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        try:
            # Profil existiert nicht mit dieser URL, versuche es einzufügen
            cursor.execute("""
                INSERT INTO unternehmens_profile (unternehmen_id, plattform_id, url)
                VALUES (?, ?, ?)
            """, (unternehmen_id, plattform_id, profil_url))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Einfügen fehlgeschlagen (wahrscheinlich UNIQUE constraint).
            # Hole existierendes Profil für Unternehmen/Plattform-Kombination.
            print(f"Hinweis: Profil für Unternehmen ID {unternehmen_id} und Plattform ID {plattform_id} existiert bereits, ggf. mit anderer URL. Verwende existierendes Profil.")
            cursor.execute("""
                SELECT id FROM unternehmens_profile
                WHERE unternehmen_id = ? AND plattform_id = ?
            """, (unternehmen_id, plattform_id))
            row = cursor.fetchone()
            if row:
                return row['id']
            else:
                raise Exception(f"Profil konnte trotz IntegrityError nicht gefunden werden für URL {profil_url}")

def add_profil_verlauf(conn, profil_id, gesamtdurchschnitt, anzahl_bewertungen, recommendation_rate=None):
    """
    Fügt einen Eintrag zum Profilverlauf hinzu (Gesamtdurchschnitt, Anzahl Bewertungen).

    Args:
        conn: SQLite-Datenbankverbindung.
        profil_id (int): ID des Unternehmensprofils.
        gesamtdurchschnitt (float): Aktueller Gesamtdurchschnitt.
        anzahl_bewertungen (int): Aktuelle Gesamtanzahl der Bewertungen.
        recommendation_rate (float, optional): Die Empfehlungsrate in Prozent.
    """
    cursor = conn.cursor()
    try:
        current_time = datetime.now()
        cursor.execute("""
            INSERT INTO profil_verlauf (profil_id, gesamtdurchschnitt, anzahl_bewertungen_gesamt, scraping_datum, recommendation_rate)
            VALUES (?, ?, ?, ?, ?)
        """, (profil_id, gesamtdurchschnitt, anzahl_bewertungen, current_time, recommendation_rate))
        conn.commit()
        print(f"Neuer Verlaufseintrag für Profil ID {profil_id} hinzugefügt: Score={gesamtdurchschnitt}, Bewertungen={anzahl_bewertungen}, Empf.Rate={recommendation_rate}% ({current_time}).")
    except Exception as e:
        print(f"Fehler beim Hinzufügen des Profilverlaufs für Profil ID {profil_id}: {e}")
        conn.rollback()


def add_bewertung(conn, profil_id, sterne, titel, text, datum_str, bewertung_hash,
                  review_type=None, is_recommended=None, reviewer_position=None,
                  reviewer_department=None, reviewed_entity_name=None, reviewed_entity_uuid=None, is_former_employee=None, updated_at_kununu=None,
                  reviewer_city=None, reviewer_state=None, apprenticeship_job_title=None):
    """
    Fügt eine Bewertung zur Datenbank hinzu. Verhindert Duplikate via bewertung_hash.

    Args:
        conn: SQLite-Datenbankverbindung.
        profil_id (int): ID des Unternehmensprofils.
        sterne (float): Sternebewertung (Gesamt).
        titel (str): Titel der Bewertung.
        text (str): Vollständiger Text der Bewertung.
        datum_str (str): Datum der Bewertung (ISO-Format von Kununu).
        bewertung_hash (str): Eindeutige ID/Hash für die Bewertung.
        review_type (str, optional): Typ der Bewertung.
        is_recommended (bool, optional): Ob empfohlen.
        reviewer_position (str, optional): Position des Bewerters.
        reviewer_department (str, optional): Abteilung des Bewerters.
        reviewed_entity_name (str, optional): Name der bewerteten Unternehmenseinheit.
        reviewed_entity_uuid (str, optional): UUID der bewerteten Unternehmenseinheit.
        updated_at_kununu (str, optional): Kununus 'updatedAt' Zeitstempel.
        is_former_employee (bool, optional): Ob der Bewerter ein ehemaliger Mitarbeiter ist.
        reviewer_city (str, optional): Stadt des Bewerters.
        reviewer_state (str, optional): Bundesland des Bewerters.
        apprenticeship_job_title (str, optional): Ausbildungsberuf.
    Returns:
        int or None: ID der neu eingefügten Bewertung, sonst None.
    """
    cursor = conn.cursor()
    bewertung_id = None
    try:
        cursor.execute("""
            INSERT INTO bewertungen ( 
                profil_id, sterne, titel, text, datum, bewertung_hash, is_former_employee, updated_at_kununu, last_seen_scraping_datum,
                review_type, is_recommended, reviewer_position, reviewer_department,
                reviewed_entity_name, reviewed_entity_uuid, reviewer_city, reviewer_state,
                apprenticeship_job_title
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (profil_id, sterne, titel, text, datum_str, bewertung_hash, is_former_employee, updated_at_kununu, datetime.now(),
              review_type, is_recommended, reviewer_position, reviewer_department, 
              reviewed_entity_name, reviewed_entity_uuid, reviewer_city, reviewer_state, apprenticeship_job_title))
        conn.commit()
        bewertung_id = cursor.lastrowid
        print(f"Bewertung '{titel[:30]}...' für Profil ID {profil_id} hinzugefügt.")
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            print(f"Hinweis: Bewertung '{titel[:30]}...' (ID: {bewertung_hash}) für Profil ID {profil_id} existiert bereits. Übersprungen.")
            # Um die ID der existierenden Bewertung zu holen (optional, falls Faktoren aktualisiert werden sollen):
            # cursor.execute("SELECT id FROM bewertungen WHERE profil_id = ? AND bewertung_hash = ?", (profil_id, bewertung_hash))
            # row = cursor.fetchone()
            # if row: bewertung_id = row['id']
        else:
            print(f"Fehler (IntegrityError) beim Hinzufügen der Bewertung für Profil ID {profil_id}: {e} - Titel: {titel}")
    except Exception as e:
        print(f"Allgemeiner Fehler beim Hinzufügen der Bewertung für Profil ID {profil_id}: {e} - Titel: {titel}")
        conn.rollback()
    return bewertung_id

def update_bewertung(conn, bewertung_db_id, sterne, titel, text, datum_str,
                     review_type, is_recommended, reviewer_position, reviewer_department,
                     reviewed_entity_name, reviewed_entity_uuid, is_former_employee, updated_at_kununu,
                     reviewer_city, reviewer_state, apprenticeship_job_title):
    """Aktualisiert eine bestehende Bewertung in der Datenbank."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE bewertungen
            SET sterne = ?, titel = ?, text = ?, datum = ?, review_type = ?,
                is_recommended = ?, reviewer_position = ?, reviewer_department = ?,
                reviewed_entity_name = ?, reviewed_entity_uuid = ?, is_former_employee = ?,
                updated_at_kununu = ?, last_seen_scraping_datum = ?, is_deleted = 0,
                reviewer_city = ?, reviewer_state = ?, apprenticeship_job_title = ?
            WHERE id = ?
        """, (sterne, titel, text, datum_str, review_type,
              is_recommended, reviewer_position, reviewer_department,
              reviewed_entity_name, reviewed_entity_uuid, is_former_employee,
              updated_at_kununu, datetime.now(),
              reviewer_city, reviewer_state, apprenticeship_job_title,
              bewertung_db_id))
        conn.commit()
        print(f"Bewertung ID {bewertung_db_id} ('{titel[:30]}...') aktualisiert.")
        return True
    except Exception as e:
        print(f"Fehler beim Aktualisieren der Bewertung ID {bewertung_db_id}: {e}")
        conn.rollback()
        return False

def get_existing_review_data(conn, profil_id, bewertung_kununu_uuid):
    """Holt Daten einer existierenden Bewertung anhand der Kununu UUID."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, updated_at_kununu, is_deleted
        FROM bewertungen
        WHERE profil_id = ? AND bewertung_hash = ?
    """, (profil_id, bewertung_kununu_uuid))
    row = cursor.fetchone()
    if row:
        return {"db_id": row["id"], "updated_at_kununu_db": row["updated_at_kununu"], "is_deleted_db": row["is_deleted"]}
    return None


def add_bewertung_faktor(conn, bewertung_id, faktor_name, faktor_sterne):
    """
    Fügt die Sternebewertung eines Faktors zu einer Bewertung hinzu.

    Args:
        conn: SQLite-Datenbankverbindung.
        bewertung_id (int): ID der zugehörigen Bewertung.
        faktor_name (str): Name des Bewertungsfaktors.
        faktor_sterne (float): Sternebewertung für diesen Faktor.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO bewertung_faktoren (bewertung_id, faktor_name, faktor_sterne)
            VALUES (?, ?, ?)
        """, (bewertung_id, faktor_name, faktor_sterne))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Hinweis: Faktor '{faktor_name}' für Bewertung ID {bewertung_id} existiert bereits oder konnte nicht hinzugefügt werden.")
    except Exception as e:
        print(f"Fehler beim Hinzufügen des Faktors '{faktor_name}' für Bewertung ID {bewertung_id}: {e}")
        conn.rollback()

# --- Hilfsfunktion zum Abrufen und Parsen von URLs ---
def fetch_and_parse_url(url_to_fetch):
    """
    Ruft eine URL ab, parst HTML und gibt ein BeautifulSoup-Objekt zurück.

    Args:
        url_to_fetch (str): Die abzurufende URL.

    Returns:
        BeautifulSoup or None: BeautifulSoup-Objekt bei Erfolg, sonst None.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        print(f"Rufe URL ab: {url_to_fetch}")
        response = requests.get(url_to_fetch, headers=headers, timeout=15)
        response.raise_for_status() # Löst HTTPError bei fehlerhaften Antworten (4XX, 5XX)
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen und Parsen der URL {url_to_fetch}: {e}")
        return None

def fetch_json_data(url_to_fetch):
    """Ruft eine URL ab, die JSON-Daten zurückgibt, und parst diese."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json' # Wichtig, um sicherzustellen, dass der Server JSON sendet
    }
    try:
        print(f"Rufe JSON-API ab: {url_to_fetch}")
        response = requests.get(url_to_fetch, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json() # Parst die JSON-Antwort direkt in ein Python-Dict
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen der JSON-Daten von {url_to_fetch}: {e}")
    except json.JSONDecodeError as e:
        print(f"Fehler beim Parsen der JSON-Antwort von {url_to_fetch}: {e}")
    return None


# --- Kununu Scraper Funktionen ---

def scrape_kununu_overview_data(soup, kununu_url_for_logging):
    """
    Extrahiert Gesamtdurchschnitt und Anzahl der Bewertungen von einer Kununu-Übersichtsseite.

    Args:
        soup (BeautifulSoup): Geparstes HTML-Objekt der Übersichtsseite.
        kununu_url_for_logging (str): URL der Seite (für Log-Zwecke).

    Returns:
        tuple: (gesamtdurchschnitt, anzahl_bewertungen) oder (None, None).
    """
    if not soup:
        return None, None

    gesamtdurchschnitt_str = None
    anzahl_bewertungen_str = None

    score_element = soup.select_one('span.h2[class*="index__value__"]')
    if score_element:
        gesamtdurchschnitt_str = score_element.get_text(strip=True)

    # Alter Selektor: 'a#company-rating-widget-see-all span.index-0-plain'
    # Neuer Selektor basierend auf: <span class="helper-regular p-tiny-regular-tablet text-dark-53">41 Bewertungen</span>
    reviews_element = soup.select_one('span.helper-regular.p-tiny-regular-tablet.text-dark-53')
    if reviews_element:
        anzahl_bewertungen_str = reviews_element.get_text(strip=True) # z.B. "13.163 Bewertungen"

    if not gesamtdurchschnitt_str:
        print(f"Gesamtdurchschnitt nicht auf {kununu_url_for_logging} gefunden. Überprüfe Selektoren.")
    if not anzahl_bewertungen_str:
        print(f"Anzahl Bewertungen nicht auf {kununu_url_for_logging} gefunden. Überprüfe Selektoren.")

    gesamtdurchschnitt = None
    if gesamtdurchschnitt_str:
        try:
            # Kununu verwendet Komma als Dezimaltrennzeichen, z.B. "3,8"
            gesamtdurchschnitt = float(gesamtdurchschnitt_str.replace(',', '.'))
        except ValueError:
            print(f"Fehler beim Umwandeln des Gesamtdurchschnitts: '{gesamtdurchschnitt_str}'")

    anzahl_bewertungen = None
    if anzahl_bewertungen_str:
        try:
            anzahl_bewertungen_numeric_str = re.sub(r'[^\d]', '', anzahl_bewertungen_str.split(' ')[0])
            if anzahl_bewertungen_numeric_str:
                 anzahl_bewertungen = int(anzahl_bewertungen_numeric_str)
        except ValueError:
            print(f"Fehler beim Umwandeln der Anzahl Bewertungen: '{anzahl_bewertungen_str}'")
            
    return gesamtdurchschnitt, anzahl_bewertungen

def extract_profile_uuid_from_html(soup):
    """
    Versucht, die Kununu Profil-UUID aus dem HTML einer Übersichtsseite zu extrahieren.
    Oft in einem <script data-testid="apollo-state"> Tag.
    """
    if not soup:
        return None
    
    apollo_state_script = soup.find('script', attrs={'data-testid': 'apollo-state'})
    if apollo_state_script:
        try:
            json_data = json.loads(apollo_state_script.string)
            # Durchsuche die JSON-Struktur nach einem Schlüssel, der die Profil-UUID enthält.
            # Dies ist spezifisch für Kununus Struktur und muss ggf. angepasst werden.
            # Beispiel: ROOT_QUERY -> profile({"slug":"..."}) -> uuid
            for key, value in json_data.get("ROOT_QUERY", {}).items():
                if isinstance(value, dict) and "uuid" in value and "slug" in value: # Einfache Prüfung
                    profile_uuid = value.get("uuid")
                    if isinstance(profile_uuid, str) and len(profile_uuid) == 36: # UUID v4 Länge
                        print(f"  DEBUG: Profil-UUID aus Apollo-State extrahiert: {profile_uuid}")
                        return profile_uuid
        except json.JSONDecodeError:
            print("  DEBUG: Fehler beim Parsen des Apollo-State JSON.")
        except Exception as e:
            print(f"  DEBUG: Unerwarteter Fehler beim Extrahieren der UUID aus Apollo-State: {e}")
    
    # Fallback: Suche nach Mustern im gesamten HTML (weniger zuverlässig)
    # Dieses Muster ist sehr generisch und sollte nur als letzte Möglichkeit dienen.
    uuid_match = re.search(r'"uuid":"([a-f0-9\-]{36})"', str(soup))
    if uuid_match:
        profile_uuid = uuid_match.group(1)
        # Hier müsste man noch prüfen, ob es wirklich die *Profil*-UUID ist.
        # Fürs Erste nehmen wir an, die erste gefundene 36-stellige UUID in diesem Format ist es.
        print(f"  DEBUG: Profil-UUID (potenziell) aus HTML-Regex extrahiert: {profile_uuid}")
        return profile_uuid
        
    print("  DEBUG: Profil-UUID konnte nicht aus HTML extrahiert werden.")
    return None


def scrape_kununu_individual_reviews_from_json(json_page_data, profil_id, conn):
    """
    Verarbeitet eine Seite mit Bewertungsdaten im JSON-Format und speichert sie.

    Args:
        json_page_data (dict): Die geparsten JSON-Daten einer Bewertungsseite.
        profil_id (int): ID des Unternehmensprofils.
        conn: SQLite-Datenbankverbindung.
    """
    if not json_page_data or 'reviews' not in json_page_data:
        print("Keine gültigen JSON-Bewertungsdaten oder 'reviews'-Schlüssel nicht gefunden.")
        return [] # Leere Liste zurückgeben, wenn keine Daten vorhanden sind

    reviews = json_page_data.get('reviews', [])
    print(f"Verarbeite {len(reviews)} Bewertungen von der aktuellen JSON-Seite.")
    
    seen_review_uuids_on_page = []

    for review_data in reviews:
        titel = None
        sterne = None
        datum_iso = None
        bewertung_unique_id = None
        is_former_employee = None
        updated_at_kununu_api = None
        review_type = None
        is_recommended = None
        reviewer_position = None
        reviewer_department = None
        reviewed_entity_name = None
        reviewed_entity_uuid = None
        reviewer_city = None
        reviewer_state = None
        apprenticeship_job_title = None
        gesammelte_faktoren = []
        full_review_text_parts = []

        bewertung_unique_id = review_data.get('uuid')
        titel = review_data.get('title')
        sterne = review_data.get('score') # Ist bereits eine Zahl
        datum_iso = review_data.get('createdAt')
        review_type = review_data.get('type')
        is_recommended = review_data.get('recommended')

        is_former_employee_json_val = review_data.get('former')
        # Ein ehemaliger Mitarbeiter wird durch ein Objekt im 'former'-Feld signalisiert (z.B. {"since": ...}).
        # null oder boolean false bedeuten aktueller Mitarbeiter.
        if isinstance(is_former_employee_json_val, dict):
            is_former_employee = True
        else: # 'former' ist null, also kein ehemaliger Mitarbeiter
            is_former_employee = False
        updated_at_kununu_api = review_data.get('updatedAt')

        if bewertung_unique_id:
            seen_review_uuids_on_page.append(bewertung_unique_id)
            
        print(f"\n--- Verarbeite Bewertung (JSON): UUID={bewertung_unique_id}, Titel='{titel}' ---")

        for text_item in review_data.get('texts', []):
            text_id = text_item.get('id', 'unknown').capitalize() # z.B. Positive, Negative, Suggestion
            text_content = text_item.get('text')
            if text_content:
                full_review_text_parts.append(f"{text_id}: {text_content}")
        
        full_review_text = "\n\n".join(full_review_text_parts)

        # Zusätzliche Meta-Daten des Bewerters/der Bewertung
        reviewer_position = review_data.get('position')
        reviewer_department = review_data.get('department')
        apprenticeship_job_title = review_data.get('apprenticeshipJob')

        company_info = review_data.get('company', {})
        reviewed_entity_name = company_info.get('name')
        reviewed_entity_uuid = company_info.get('uuid')
        
        location_info = company_info.get('location', {})
        reviewer_city = location_info.get('city')
        reviewer_state = location_info.get('state')

        for rating_item in review_data.get('ratings', []):
            faktor_name = rating_item.get('id') # z.B. "atmosphere", "image"
            faktor_sterne_wert = rating_item.get('score') # Ist bereits eine Zahl

            if faktor_name and faktor_sterne_wert is not None:
                # Stelle sicher, dass faktor_sterne_wert ein Float ist, falls es als String kommt (sollte aber Zahl sein)
                try:
                    gesammelte_faktoren.append({"name": faktor_name, "sterne": float(faktor_sterne_wert)})
                except (ValueError, TypeError):
                    print(f"Warnung: Ungültiger Sternewert '{faktor_sterne_wert}' für Faktor '{faktor_name}'.")

        if titel and sterne is not None and datum_iso and bewertung_unique_id:
            existing_review = get_existing_review_data(conn, profil_id, bewertung_unique_id)

            if existing_review:
                # Bewertung existiert bereits, prüfe auf Änderungen
                print(f"  DEBUG: Bewertung {bewertung_unique_id} existiert in DB (ID: {existing_review['db_id']}). API updatedAt: {updated_at_kununu_api}, DB updatedAt: {existing_review['updated_at_kununu_db']}")
                if updated_at_kununu_api and (existing_review['updated_at_kununu_db'] is None or updated_at_kununu_api > existing_review['updated_at_kununu_db'] or existing_review['is_deleted_db']):
                    print(f"  -> Bewertung {bewertung_unique_id} wurde geändert oder war gelöscht. Aktualisiere...")
                    # Faktoren der alten Bewertung löschen, bevor neue hinzugefügt werden
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM bewertung_faktoren WHERE bewertung_id = ?", (existing_review['db_id'],))
                    conn.commit()
                    
                    update_successful = update_bewertung(
                        conn, existing_review['db_id'], sterne, titel, full_review_text, datum_iso,
                        review_type, is_recommended, reviewer_position, reviewer_department,
                        reviewed_entity_name, reviewed_entity_uuid, is_former_employee, updated_at_kununu_api,
                        reviewer_city, reviewer_state, apprenticeship_job_title
                    )
                    if update_successful:
                        for faktor_data in gesammelte_faktoren:
                            add_bewertung_faktor(conn, existing_review['db_id'], faktor_data["name"], faktor_data["sterne"])
                else:
                    # Keine Änderung, nur last_seen aktualisieren
                    cursor = conn.cursor()
                    cursor.execute("UPDATE bewertungen SET last_seen_scraping_datum = ?, is_deleted = 0 WHERE id = ?", (datetime.now(), existing_review['db_id']))
                    conn.commit()
                    print(f"  -> Bewertung {bewertung_unique_id} unverändert. 'last_seen' aktualisiert.")
            else:
                # Neue Bewertung
                bewertung_id_in_db = add_bewertung(
                    conn=conn, profil_id=profil_id, sterne=sterne, titel=titel,
                    text=full_review_text, datum_str=datum_iso, bewertung_hash=bewertung_unique_id,
                    review_type=review_type,
                    is_recommended=is_recommended,
                    reviewer_position=reviewer_position,
                    reviewer_department=reviewer_department,
                    reviewed_entity_name=reviewed_entity_name,
                    reviewed_entity_uuid=reviewed_entity_uuid,
                    is_former_employee=is_former_employee,
                    updated_at_kununu=updated_at_kununu_api,
                    reviewer_city=reviewer_city,
                    reviewer_state=reviewer_state,
                    apprenticeship_job_title=apprenticeship_job_title
                )
                if bewertung_id_in_db:
                    for faktor_data in gesammelte_faktoren:
                        add_bewertung_faktor(conn, bewertung_id_in_db, faktor_data["name"], faktor_data["sterne"])
                if not full_review_text and bewertung_id_in_db:
                    print(f"Hinweis: Bewertung '{titel[:30]}...' (DB-ID: {bewertung_id_in_db}, Kununu-ID: {bewertung_unique_id}) wurde ohne beschreibenden Text gespeichert.")
        else:
            print(f"FEHLER: Unvollständige Kerndaten für Bewertung (Titel: {titel or 'N/A'}) oder ID fehlt, wird übersprungen:")
            if not titel: print("  - Grund: Titel fehlt")
            if sterne is None: print(f"  - Grund: Gesamtsterne fehlen")
            if not datum_iso: print("  - Grund: Datum fehlt")
            if not bewertung_unique_id: print("  - Grund: Eindeutige Bewertungs-ID (aus JSON) fehlt (Finale Prüfung)")
    
    return seen_review_uuids_on_page

# --- Haupt-Ausführungslogik ---

def main_scraper(unternehmen_name, profil_uebersicht_url, profil_kommentare_url):
    """
    Hauptfunktion für den Kununu-Scraping-Prozess eines Unternehmens.
    Holt Übersichtsdaten und einzelne Bewertungen.

    Args:
        unternehmen_name (str): Name des Unternehmens.
        profil_uebersicht_url (str): URL zur Kununu-Übersichtsseite.
        profil_kommentare_url (str): URL zur Kununu-Kommentarseite.
    """
    conn = None
    try:
        conn = get_db_connection()

        unternehmen_id = get_or_create_unternehmen(conn, unternehmen_name)
        plattform_id = get_plattform_id(conn, "Kununu")

        if not unternehmen_id or not plattform_id:
            print(f"Fehler: Unternehmen '{unternehmen_name}' oder Plattform 'Kununu' konnte nicht initialisiert werden.")
            return

        profil_id = get_or_create_profil(conn, unternehmen_id, plattform_id, profil_uebersicht_url)
        if not profil_id:
            print(f"Fehler: Unternehmensprofil für URL '{profil_uebersicht_url}' konnte nicht initialisiert werden.")
            return
        
        print(f"Verarbeite Profil ID: {profil_id} für {unternehmen_name} (Übersicht: {profil_uebersicht_url}, Kommentare: {profil_kommentare_url})")

        # 1. Übersichtsdaten holen und Profil-UUID extrahieren
        soup_uebersicht = fetch_and_parse_url(profil_uebersicht_url)
        gesamtdurchschnitt, anzahl_bewertungen = None, None
        recommendation_rate_overview = None # Für die Empfehlungsrate von der Übersichtsseite/ersten JSON-Seite
        profile_uuid = None
        
        if soup_uebersicht:
            gesamtdurchschnitt, anzahl_bewertungen = scrape_kununu_overview_data(soup_uebersicht, profil_uebersicht_url)
            # Die recommendationRate ist nicht direkt auf der HTML-Übersichtsseite, sondern in der JSON-API.
            profile_uuid = extract_profile_uuid_from_html(soup_uebersicht) # UUID aus HTML extrahieren

        if gesamtdurchschnitt is not None and anzahl_bewertungen is not None:
            # Wir übergeben recommendation_rate_overview hier noch als None, da wir es erst aus der JSON holen.
            # Alternativ: add_profil_verlauf erst nach dem ersten JSON-Abruf aufrufen.
            pass # add_profil_verlauf wird nach dem ersten JSON-Abruf aufgerufen
        else:
            print(f"Keine vollständigen Übersichtsdaten von {profil_uebersicht_url} gescraped. Nichts zum Profilverlauf hinzugefügt.")
        
        # 2. Einzelne Bewertungen über die JSON-API holen, falls UUID vorhanden
        if not profile_uuid:
            print(f"FEHLER: Profil-UUID konnte für {unternehmen_name} nicht extrahiert werden. Überspringe das Scrapen einzelner Bewertungen via API.")
            # Fallback: Versuche, die alte HTML-basierte Methode für Kommentare zu nutzen, falls gewünscht
            # print(f"\nVersuche, einzelne Bewertungen von {profil_kommentare_url} (HTML) zu laden...")
            # soup_kommentare_html = fetch_and_parse_url(profil_kommentare_url)
            # if soup_kommentare_html:
            #     scrape_kununu_individual_reviews_from_html(soup_kommentare_html, profil_id, conn) # Alte Funktion umbenennen
            # else:
            #     print(f"Konnte die Kommentarseite {profil_kommentare_url} (HTML) nicht laden. Überspringe Einzelbewertungen.")
            return # Beende hier, wenn keine UUID für API-Abruf da ist

        # Extrahiere Slug und Ländercode aus der Übersichts-URL für die API-URL
        # Beispiel: https://www.kununu.com/de/deutsche-bahn -> slug='deutsche-bahn', country_code='de'
        url_parts = profil_uebersicht_url.split('/')
        slug = url_parts[-1] if url_parts else unternehmen_name.lower().replace(' ', '-') # Fallback für Slug
        country_code = "de" # Standard, oder aus URL extrahieren, falls variabler
        if len(url_parts) > 3 and len(url_parts[-2]) == 2 : # Einfache Prüfung für Ländercode
            country_code = url_parts[-2]

        current_page = 1
        total_pages = 1 # Wird nach dem ersten API-Aufruf aktualisiert
        all_seen_review_uuids_this_scrape = []

        while current_page <= total_pages:
            # JSON API URL konstruieren
            # Basis-URL: https://www.kununu.com/middlewares/profiles/{countryCode}/{slug}/{profileUuid}/reviews
            # Parameter: ?fetchFactorScores=0&reviewType=employees&sort=newest&page={page}
            # urlParams ist optional und wird hier durch sort=newest abgedeckt
            json_api_url = f"https://www.kununu.com/middlewares/profiles/{country_code}/{slug}/{profile_uuid}/reviews?fetchFactorScores=1&reviewType=employees&sort=newest&page={current_page}"
            
            json_data = fetch_json_data(json_api_url)

            if json_data:
                if current_page == 1 and 'pagesCount' in json_data: # Gesamtseitenzahl vom ersten Aufruf holen
                    if 'recommendationRate' in json_data and 'percentage' in json_data['recommendationRate']:
                        recommendation_rate_overview = json_data['recommendationRate']['percentage']
                    # Jetzt den Profilverlauf mit allen Daten hinzufügen/aktualisieren
                    if gesamtdurchschnitt is not None and anzahl_bewertungen is not None:
                         add_profil_verlauf(conn, profil_id, gesamtdurchschnitt, anzahl_bewertungen, recommendation_rate_overview)
                    total_pages = json_data['pagesCount']
                    print(f"Insgesamt {total_pages} Seiten mit Bewertungen gefunden.")
                scrape_kununu_individual_reviews_from_json(json_data, profil_id, conn)
                current_page += 1
            else:
                print(f"Keine JSON-Daten für Seite {current_page} erhalten. Breche Paginierung ab.")
                break # Paginierung abbrechen, wenn eine Seite fehlschlägt

    except Exception as e:
        print(f"Ein Fehler ist im Hauptprozess aufgetreten: {e}")
    finally:
        if conn:
            conn.close()
            print("Datenbankverbindung geschlossen.")

if __name__ == '__main__':
    # WICHTIG: Stelle sicher, dass database_setup.py vorher einmal ausgeführt wurde!
    # from database_setup import setup_database
    # setup_database() # Nur einmalig oder bei Bedarf ausführen

    test_unternehmen_name = "Zentek"
    test_profil_uebersicht_url = "https://www.kununu.com/de/sap"
    test_profil_kommentare_url = "https://www.kununu.com/de/sap/kommentare?sort=newest" 

    print(f"Starte Kununu-Scraper für: {test_unternehmen_name}")
    main_scraper(test_unternehmen_name, test_profil_uebersicht_url, test_profil_kommentare_url)
    print("Kununu-Scraper-Durchlauf beendet.")