from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime # Importiere datetime für die Konvertierung
from markupsafe import Markup # Markup wird von markupsafe importiert
import threading
import math # Für math.ceil bei der Paginierung

# Importiere die notwendigen Funktionen aus deinem Scraper-Skript
# Stelle sicher, dass kununu_scraper.py im selben Verzeichnis liegt oder im Python-Pfad ist.
try:
    from trustpilot_scraper import main_trustpilot_scraper, TRUSTPILOT_JSON_BUILD_ID
except ImportError:
    print("Fehler: trustpilot_scraper.py nicht gefunden oder fehlerhaft.")
    def main_trustpilot_scraper(url, build_id, manual_unternehmen_name=None): print("main_trustpilot_scraper nicht geladen") # Add manual_unternehmen_name
    TRUSTPILOT_JSON_BUILD_ID = "businessunitprofile-consumersite-2.3939.0" # Fallback

try:
    from kununu_scraper import main_scraper, get_db_connection, DB_NAME, fetch_and_parse_url
except ImportError:
    print("Fehler: kununu_scraper.py nicht gefunden oder fehlerhaft.")
    # Fallback, falls der Import fehlschlägt, um die App zumindest starten zu können
    def main_scraper(name, url1, url2): print("main_scraper nicht geladen")
    def get_db_connection(): return sqlite3.connect('Datenbank.db') # Annahme
    DB_NAME = 'Datenbank.db'

def extract_company_name_from_kununu_profile(soup):
    """Extrahiert den Unternehmensnamen von einer geparsten Kununu-Profilseite."""
    if not soup:
        return None
    # Kununu verwendet oft ein <h1> Tag für den Unternehmensnamen,
    # manchmal mit einer spezifischen Klasse oder innerhalb eines bestimmten Containers.
    name_element = soup.select_one('div[class*="profile-header-name"] h1') # Ein häufiges Muster
    if not name_element:
        name_element = soup.select_one('h1') # Allgemeiner Fallback auf das erste H1
    
    if name_element:
        company_name_raw = name_element.get_text(strip=True)
        
        # Definiere mögliche Suffixe, die entfernt werden sollen.
        # Reihenfolge ist wichtig, falls einer ein Teil des anderen ist (hier nicht der Fall).
        suffixes_to_remove = [
            " als Arbeitgeber", # Mit führendem Leerzeichen
            "als Arbeitgeber"   # Ohne führendes Leerzeichen (für Fälle wie "ZentekGruppeals Arbeitgeber")
        ]
        
        cleaned_name = company_name_raw
        for suffix in suffixes_to_remove:
            if cleaned_name.endswith(suffix):
                cleaned_name = cleaned_name[:-len(suffix)]
                break # Nur den ersten passenden Suffix entfernen
        
        return cleaned_name.strip() # Ein abschließendes strip, um eventuelle Rest-Leerzeichen zu entfernen
    return None

app = Flask(__name__)
# Ein Secret Key wird für Flash-Nachrichten benötigt
app.secret_key = os.urandom(24)

# --- Custom Jinja2 Filter ---
def nl2br_filter(value):
    """Konvertiert Zeilenumbrüche in <br>-Tags."""
    if value is None:
        return ''
    return Markup(str(value).replace('\n', '<br>\n'))
app.jinja_env.filters['nl2br'] = nl2br_filter

@app.route('/', methods=['GET'])
def index():
    """Zeigt die Hauptseite mit dem Eingabeformular an."""
    return render_template('index.html') # Zeigt jetzt die Willkommensseite

@app.route('/add', methods=['GET'])
def add_profile_page():
    """Zeigt die Seite zum Hinzufügen eines neuen Profils an."""
    return render_template('add_profile.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    """Nimmt die Formulardaten entgegen und startet den Scraping-Prozess."""
    unternehmen_name = request.form.get('unternehmen_name')
    kununu_url_raw = request.form.get('kununu_url')
    trustpilot_url_raw = request.form.get('trustpilot_url')

    kununu_url = kununu_url_raw.strip() if kununu_url_raw else None
    trustpilot_url = trustpilot_url_raw.strip() if trustpilot_url_raw else None

    if not unternehmen_name:
        flash('Unternehmensname muss ausgefüllt werden!', 'error')
        return redirect(url_for('add_profile_page'))

    if not kununu_url and not trustpilot_url:
        flash('Mindestens eine Profil-URL (Kununu oder Trustpilot) muss angegeben werden!', 'error')
        return redirect(url_for('add_profile_page'))

    # Variable, um zu prüfen, ob mindestens ein Scraper erfolgreich war (oder zumindest versucht wurde)
    scraping_erfolgreich_oder_versucht = False

    try:
        if kununu_url:
            if "kununu.com" not in kununu_url:
                flash(f"Die angegebene Kununu URL '{kununu_url}' scheint ungültig zu sein.", 'error')
            else:
                temp_kununu_url = kununu_url.rstrip('/')
                # Der Unternehmensname kommt jetzt direkt aus dem Formular.
                # Die Funktion extract_company_name_from_kununu_profile wird hier nicht mehr benötigt.
                print(f"WebUI: Verwende manuell eingegebenen Unternehmensnamen: {unternehmen_name}")
                profil_kommentare_url = f"{temp_kununu_url}/kommentare?sort=newest"

                print(f"WebUI: Starte Kununu Scraping für {unternehmen_name} mit URL {temp_kununu_url} in einem neuen Thread...")
                # Starte den Kununu-Scraper in einem neuen Thread
                kununu_thread = threading.Thread(target=main_scraper, args=(unternehmen_name, temp_kununu_url, profil_kommentare_url))
                kununu_thread.start()
                flash(f"Kununu Scraping für '{unternehmen_name}' wurde im Hintergrund gestartet.", 'info')
                scraping_erfolgreich_oder_versucht = True

        if trustpilot_url:
            if "trustpilot.com" not in trustpilot_url:
                flash(f"Die angegebene Trustpilot URL '{trustpilot_url}' scheint ungültig zu sein.", 'error')
            else:
                temp_trustpilot_url = trustpilot_url.rstrip('/')
                print(f"WebUI: Starte Trustpilot Scraping für {unternehmen_name} mit URL: {temp_trustpilot_url}...")
                # Starte den Trustpilot-Scraper in einem neuen Thread
                trustpilot_thread = threading.Thread(target=main_trustpilot_scraper, args=(temp_trustpilot_url, TRUSTPILOT_JSON_BUILD_ID, unternehmen_name))
                trustpilot_thread.start()
                flash(f"Trustpilot Scraping für '{unternehmen_name}' wurde im Hintergrund gestartet.", 'info')
                scraping_erfolgreich_oder_versucht = True

        
        if not scraping_erfolgreich_oder_versucht:
            # Dieser Fall sollte eintreten, wenn beide URLs ungültig waren (nicht kununu/trustpilot)
            # aber die Validierung oben (mind. eine URL) nicht gefeuert hat, weil sie syntaktisch URLs waren.
            # Oder wenn beide URLs leer waren, was aber durch die obere Validierung abgefangen wird.
            flash("Keine gültigen URLs für das Scraping gefunden.", "warning")

    except Exception as e:
        flash(f"Ein Fehler ist beim Scraping aufgetreten: {e}", 'error')
        print(f"WebUI: Fehler beim Aufruf von main_scraper: {e}")

    return redirect(url_for('add_profile_page')) # Leitet nach Erfolg zurück zur Add-Seite (oder Startseite)

@app.route('/scrape_company/<int:unternehmen_id>', methods=['POST'])
def scrape_company(unternehmen_id):
    """Startet den Scraping-Prozess für ein spezifisches Unternehmen."""
    conn = get_db_connection()
    unternehmen_name = None
    profil_uebersicht_url = None

    try:
        # 1. Unternehmensnamen holen
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM unternehmen WHERE id = ?", (unternehmen_id,))
        unternehmen_row = cursor.fetchone()
        if not unternehmen_row:
            flash(f"Unternehmen mit ID {unternehmen_id} nicht gefunden.", "error")
            return redirect(url_for('show_data'))
        unternehmen_name = unternehmen_row['name']

        # 2. Kununu Plattform ID holen
        cursor.execute("SELECT id FROM plattformen WHERE name = 'Kununu'")
        plattform_row = cursor.fetchone()
        if not plattform_row:
            flash("Kununu-Plattform nicht in der Datenbank gefunden. Setup überprüfen.", "error")
            return redirect(url_for('unternehmens_details', unternehmen_id=unternehmen_id))
        kununu_plattform_id = plattform_row['id']

        # 3. Profil-URL holen (kann Kununu oder Trustpilot sein, wir nehmen die erste gefundene oder priorisieren)
        # Für diesen Button nehmen wir an, wir wollen das primäre Profil (z.B. Kununu, falls vorhanden) neu scrapen
        # oder wir müssten die Logik erweitern, um auszuwählen, welches Profil gescraped wird, wenn mehrere existieren.
        # Hier vereinfacht: Wir suchen nach einer Kununu-URL, dann nach einer Trustpilot-URL.
        cursor.execute("SELECT url, p.name as plattform_name FROM unternehmens_profile up JOIN plattformen p ON up.plattform_id = p.id WHERE up.unternehmen_id = ?", (unternehmen_id,))
        profile_row = cursor.fetchone()
        if not profile_row:
            flash(f"Kein Profil (Kununu oder Trustpilot) für {unternehmen_name} in der Datenbank gefunden.", "error")
            return redirect(url_for('unternehmens_details', unternehmen_id=unternehmen_id))
        profil_uebersicht_url = profile_row['url']
        
        # Unterscheiden, welcher Scraper aufgerufen werden soll, basierend auf der URL oder Plattform
        if "kununu.com" in profil_uebersicht_url:
            # 4. Kommentare-URL generieren für Kununu
            temp_uebersicht_url = profil_uebersicht_url.rstrip('/')
            profil_kommentare_url = f"{temp_uebersicht_url}/kommentare?sort=newest"

            # 5. Kununu Scraper aufrufen
            print(f"WebUI: Starte Kununu Scraping für spezifisches Unternehmen: {unternehmen_name} (ID: {unternehmen_id})")
            kununu_thread = threading.Thread(target=main_scraper, args=(unternehmen_name, profil_uebersicht_url, profil_kommentare_url))
            kununu_thread.start()
            flash(f"Kununu Scraping für {unternehmen_name} wurde im Hintergrund gestartet.", 'info')
        elif "trustpilot.com" in profil_uebersicht_url:
            # 5. Trustpilot Scraper aufrufen
            print(f"WebUI: Starte Trustpilot Scraping für spezifisches Unternehmen: {unternehmen_name} (ID: {unternehmen_id}) im Thread")
            trustpilot_thread = threading.Thread(target=main_trustpilot_scraper, args=(profil_uebersicht_url, TRUSTPILOT_JSON_BUILD_ID, unternehmen_name))
            trustpilot_thread.start()
            flash(f"Trustpilot Scraping für {unternehmen_name} wurde im Hintergrund gestartet.", 'info')
        else:
            flash(f"Unbekannte Profil-URL-Domain für {unternehmen_name}: {profil_uebersicht_url}", "error")

    except Exception as e:
        flash(f"Ein Fehler ist beim Scraping für {unternehmen_name} aufgetreten: {e}", 'error')
        print(f"WebUI: Fehler beim Aufruf von main_scraper für ID {unternehmen_id}: {e}")
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('unternehmens_details', unternehmen_id=unternehmen_id))

@app.route('/data')
def show_data():
    """Zeigt eine Übersicht der gesammelten Daten aus der profil_verlauf Tabelle."""
    # Diese Route zeigt jetzt eine Liste der Unternehmen an.
    conn = get_db_connection()
    unternehmen_liste = []
    try:
        # Hole alle Unternehmen, für die es Profile gibt
        unternehmen_liste = conn.execute("""
            SELECT DISTINCT u.id, u.name 
            FROM unternehmen u
            JOIN unternehmens_profile up ON u.id = up.unternehmen_id
            ORDER BY u.name ASC
        """).fetchall()
    except sqlite3.Error as e:
        flash(f"Datenbankfehler beim Laden der Unternehmensliste: {e}", "error")
    finally:
        if conn:
            conn.close()
    return render_template('data.html', unternehmen_liste=unternehmen_liste)

@app.route('/unternehmen/<int:unternehmen_id>')
def unternehmens_details(unternehmen_id):
    """Zeigt Detailinformationen für ein spezifisches Unternehmen."""
    conn = get_db_connection()
    unternehmen_name = None
    profil_verlauf_list = []
    neueste_bewertungen_list = []
    gesamtzahl_bewertungen_unternehmen = 0 # Für den Link "Alle Bewertungen anzeigen"
    
    # Variablen für plattformspezifische aktuelle Daten
    aktueller_kununu_schnitt = None
    aktuellste_kununu_anzahl_bewertungen = None
    aktuelle_kununu_empfehlungsrate = None

    aktueller_trustpilot_schnitt = None
    aktuellste_trustpilot_anzahl_bewertungen = None
    try:
        # Unternehmensnamen holen
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM unternehmen WHERE id = ?", (unternehmen_id,))
        unternehmen_row = cursor.fetchone()
        if unternehmen_row:
            unternehmen_name = unternehmen_row['name']
        else:
            flash(f"Unternehmen mit ID {unternehmen_id} nicht gefunden.", "error")
            return redirect(url_for('show_data'))

        # Rohdaten des Profilverlaufs für dieses Unternehmen holen
        raw_profil_verlauf_data = conn.execute("""
            SELECT pv.gesamtdurchschnitt, pv.anzahl_bewertungen_gesamt, pv.scraping_datum, pv.recommendation_rate, up.url
            FROM profil_verlauf pv
            JOIN unternehmens_profile up ON pv.profil_id = up.id
            WHERE up.unternehmen_id = ?
            ORDER BY pv.scraping_datum DESC
        """, (unternehmen_id,)).fetchall()

        # Konvertiere die Datumsstrings im Profilverlauf in datetime-Objekte
        profil_verlauf_list = []
        for row in raw_profil_verlauf_data:
            item = dict(row) # Konvertiere sqlite3.Row in ein Dictionary für einfachere Bearbeitung
            datum_str = item.get('scraping_datum')
            if datum_str:
                try:
                    item['scraping_datum'] = datetime.strptime(datum_str, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    try:
                        item['scraping_datum'] = datetime.strptime(datum_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        print(f"Warnung: Konnte Datumsstring '{datum_str}' nicht parsen. Wird als None behandelt.")
                        item['scraping_datum'] = None
            else:
                item['scraping_datum'] = None
            profil_verlauf_list.append(item)
        
        # Erstelle eine Kopie der Liste für das Diagramm, sortiert nach Datum aufsteigend
        # (oder verarbeite die Daten direkt für das Diagramm in der gewünschten Reihenfolge)
        # Die aktuelle profil_verlauf_list ist DESC sortiert, was für die Tabelle gut ist.
        # Für das Diagramm brauchen wir ASC.
        chart_profil_verlauf_data = sorted(
            [item for item in profil_verlauf_list if item.get('scraping_datum')],
            key=lambda x: x['scraping_datum']
        )

        kununu_verlauf_data = []
        trustpilot_verlauf_data = []
        for item in chart_profil_verlauf_data: # chart_profil_verlauf_data ist bereits ASC sortiert
            if "kununu.com" in item.get('url', '').lower():
                kununu_verlauf_data.append(item)
            elif "trustpilot.com" in item.get('url', '').lower():
                trustpilot_verlauf_data.append(item)

        # Aktuellste Daten für Kununu und Trustpilot extrahieren
        # profil_verlauf_list ist bereits nach scraping_datum DESC sortiert
        for item in profil_verlauf_list:
            url = item.get('url', '').lower()
            if "kununu.com" in url:
                if aktueller_kununu_schnitt is None: # Erster (neuester) Kununu-Eintrag
                    aktueller_kununu_schnitt = item['gesamtdurchschnitt']
                    aktuellste_kununu_anzahl_bewertungen = item['anzahl_bewertungen_gesamt']
                    aktuelle_kununu_empfehlungsrate = item.get('recommendation_rate')
            elif "trustpilot.com" in url:
                if aktueller_trustpilot_schnitt is None: # Erster (neuester) Trustpilot-Eintrag
                    aktueller_trustpilot_schnitt = item['gesamtdurchschnitt']
                    aktuellste_trustpilot_anzahl_bewertungen = item['anzahl_bewertungen_gesamt']
            # Wenn beide gefunden wurden, könnten wir theoretisch abbrechen, aber die Liste ist meist kurz.

        # --- SQL-Vorbereitung für Bewertungen (wird auch von alle_bewertungen genutzt) ---
        # Basis-SQL ohne Filter, Sortierung oder Limit
        sql_base_select = """
            SELECT
                b.sterne, b.titel, b.text, b.datum, b.is_former_employee,
                b.review_type, b.is_recommended, b.reviewer_position, b.reviewer_department,
                p.name as plattform_name,
                b.reviewed_entity_name, b.reviewer_city, b.reviewer_state,
                b.apprenticeship_job_title,
                b.consumer_display_name, b.date_of_experience, b.review_language, b.review_source, b.review_likes, b.is_verified_by_platform
        """
        sql_base_from_where = """
            FROM bewertungen b
            JOIN unternehmens_profile up ON b.profil_id = up.id
            JOIN plattformen p ON up.plattform_id = p.id
            WHERE up.unternehmen_id = ? AND b.is_deleted = 0 
        """

        # Gesamtzahl der Bewertungen für dieses Unternehmen ermitteln (für den Link "Alle anzeigen")
        count_sql = f"SELECT COUNT(b.id) FROM bewertungen b JOIN unternehmens_profile up ON b.profil_id = up.id WHERE up.unternehmen_id = ? AND b.is_deleted = 0"
        count_row = conn.execute(count_sql, (unternehmen_id,)).fetchone()
        gesamtzahl_bewertungen_unternehmen = count_row[0] if count_row else 0

        # Sortieroption für Bewertungen aus Query-Parametern holen (nur für die ersten 10 hier)
        # Die "Alle Bewertungen"-Seite hat ihre eigene Sortierlogik im Request.
        # Für die Detailseite zeigen wir immer die neuesten, aber das Dropdown soll den URL-Parameter widerspiegeln.
        order_by_clause_details = "ORDER BY b.datum DESC"
        sort_option = request.args.get('sort', 'neueste') # Definiere sort_option hier

        # Die 10 neuesten Bewertungen für die Detailseite holen
        limit_clause_sql_details = "LIMIT 8"
        
        # Explizite String-Konkatenation für die finale Query
        final_sql_query_details = sql_base_select + " " + sql_base_from_where + " " + order_by_clause_details + " " + limit_clause_sql_details
        
        # Debug-Ausgabe für die finale SQL-Abfrage
        print(f"--- DEBUG SQL Query für Detail-Bewertungen ---\n{final_sql_query_details}\n--- END DEBUG ---")

        raw_bewertungen_data = conn.execute(final_sql_query_details, (unternehmen_id,)).fetchall()

        # Konvertiere die Datumsstrings der Bewertungen in datetime-Objekte für die Anzeige
        for row in raw_bewertungen_data:
            item = dict(row)
            
            # Boolean-Felder für data-Attribute konsistent als Strings 'True'/'False'/'None' aufbereiten
            for bool_field in ['is_recommended', 'is_former_employee']:
                if item.get(bool_field) is not None:
                    item[bool_field] = 'True' if item[bool_field] else 'False'
                else:
                    # Falls der DB-Wert NULL ist, als 'None' (String) für data-Attribut setzen
                    item[bool_field] = 'None' 

            datum_bewertung_str = item.get('datum')
            if datum_bewertung_str:
                try:
                    # Kununu-Datum ist oft im Format 'YYYY-MM-DDTHH:MM:SS+HH:MM' oder ähnlich
                    # Wir versuchen, den Teil vor dem 'T' oder dem '+' zu nehmen für eine einfache Anzeige
                    # oder parsen es, wenn es einheitlich ist. Für strftime brauchen wir datetime.
                    item['datum_obj'] = datetime.fromisoformat(datum_bewertung_str.replace('Z', '+00:00'))
                except ValueError:
                    print(f"Warnung: Konnte Bewertungs-Datumsstring '{datum_bewertung_str}' nicht parsen.")
                    item['datum_obj'] = None # Oder den String direkt anzeigen lassen
            neueste_bewertungen_list.append(item)

    except sqlite3.Error as e:
        flash(f"Datenbankfehler beim Laden der Unternehmensdetails: {e}", "error")
        # Zusätzliche Debug-Info, falls der Fehler hier auftritt
        if 'final_sql_query_details' in locals(): # Prüft, ob die Variable existiert
            print(f"Fehler bei SQL-Query: {final_sql_query_details}")
        else:
            print("Fehler trat vor der Erstellung der SQL-Query für Bewertungen auf.")
    finally:
        if conn:
            conn.close()
    return render_template('unternehmens_details.html',
                           unternehmen_name=unternehmen_name,
                           profil_verlauf_list=profil_verlauf_list, # Für die Tabelle
                           kununu_verlauf_data=kununu_verlauf_data,
                           trustpilot_verlauf_data=trustpilot_verlauf_data,
                           aktueller_kununu_schnitt=aktueller_kununu_schnitt,
                           aktuellste_kununu_anzahl_bewertungen=aktuellste_kununu_anzahl_bewertungen,
                           aktuelle_kununu_empfehlungsrate=aktuelle_kununu_empfehlungsrate,
                           aktueller_trustpilot_schnitt=aktueller_trustpilot_schnitt,
                           aktuellste_trustpilot_anzahl_bewertungen=aktuellste_trustpilot_anzahl_bewertungen,
                           neueste_bewertungen_list=neueste_bewertungen_list, # Sortierte Liste
                           current_sort_option=sort_option, # Für das Sortier-Dropdown
                           unternehmen_id=unternehmen_id,
                           gesamtzahl_bewertungen_unternehmen=gesamtzahl_bewertungen_unternehmen)

@app.route('/unternehmen/<int:unternehmen_id>/alle_bewertungen')
def alle_bewertungen(unternehmen_id):
    conn = get_db_connection()
    unternehmen_name = None
    bewertungen_list = []
    
    page = request.args.get('page', 1, type=int)
    reviews_per_page = 25 # Anzahl der Bewertungen pro Seite
    offset = (page - 1) * reviews_per_page

    # Filter- und Sortierparameter aus der URL holen
    sort_option = request.args.get('sort', 'neueste')
    filter_empfehlung = request.args.get('empfehlung', 'alle')
    filter_status = request.args.get('status', 'alle')

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM unternehmen WHERE id = ?", (unternehmen_id,))
        unternehmen_row = cursor.fetchone()
        if not unternehmen_row:
            flash(f"Unternehmen mit ID {unternehmen_id} nicht gefunden.", "error")
            return redirect(url_for('show_data'))
        unternehmen_name = unternehmen_row['name']

        # Basis-SQL
        sql_base_select = "SELECT b.sterne, b.titel, b.text, b.datum, b.is_former_employee, b.review_type, b.is_recommended, b.reviewer_position, b.reviewer_department, p.name as plattform_name, b.reviewed_entity_name, b.reviewer_city, b.reviewer_state, b.apprenticeship_job_title, b.consumer_display_name, b.date_of_experience, b.review_language, b.review_source, b.review_likes, b.is_verified_by_platform"
        sql_base_from = "FROM bewertungen b JOIN unternehmens_profile up ON b.profil_id = up.id JOIN plattformen p ON up.plattform_id = p.id"
        
        # WHERE-Klauseln und Parameter dynamisch erstellen
        where_clauses_list = ["up.unternehmen_id = ?", "b.is_deleted = 0"]
        params_list = [unternehmen_id]

        if filter_empfehlung != 'alle':
            # Konvertiere 'true'/'false' (aus URL) zu 1/0 für DB-Abfrage
            # oder handle 'None' wenn die DB NULLs speichert und Python Booleans verwendet
            # In unserem Fall haben wir 'True'/'False'/'None' Strings in den data-Attributen,
            # aber die DB speichert Booleans als 0/1 oder NULL.
            # Die Konvertierung zu 'True'/'False' Strings passiert erst für die Template-Darstellung.
            # Hier müssen wir mit den DB-Werten arbeiten.
            if filter_empfehlung == 'true':
                where_clauses_list.append("b.is_recommended = 1")
            elif filter_empfehlung == 'false':
                where_clauses_list.append("b.is_recommended = 0")
            # 'None' wird nicht explizit gefiltert, es sei denn, man fügt eine Option hinzu

        if filter_status != 'alle':
            if filter_status == 'true': # Ehemalig
                where_clauses_list.append("b.is_former_employee = 1")
            elif filter_status == 'false': # Aktuell
                where_clauses_list.append("b.is_former_employee = 0")

        sql_where_clause = " WHERE " + " AND ".join(where_clauses_list)

        # Gesamtzahl der gefilterten Bewertungen für Paginierung
        count_sql = f"SELECT COUNT(b.id) {sql_base_from} {sql_where_clause}"
        total_reviews_count = conn.execute(count_sql, tuple(params_list)).fetchone()[0]
        total_pages = math.ceil(total_reviews_count / reviews_per_page)

        # ORDER BY-Klausel
        order_by_clause = "ORDER BY b.datum DESC" # Standard
        if sort_option == 'sterne_asc':
            order_by_clause = "ORDER BY b.sterne ASC, b.datum DESC"
        elif sort_option == 'sterne_desc':
            order_by_clause = "ORDER BY b.sterne DESC, b.datum DESC"

        # Finale Query für die aktuelle Seite
        limit_offset_clause = "LIMIT ? OFFSET ?"
        final_query = f"{sql_base_select} {sql_base_from} {sql_where_clause} {order_by_clause} {limit_offset_clause}"
        
        params_list_with_pagination = params_list + [reviews_per_page, offset]
        print(f"--- DEBUG SQL Alle Bewertungen ---\n{final_query}\nParams: {params_list_with_pagination}\n--- END DEBUG ---")
        
        raw_data = conn.execute(final_query, tuple(params_list_with_pagination)).fetchall()

        for row in raw_data:
            item = dict(row)
            for bool_field in ['is_recommended', 'is_former_employee']:
                if item.get(bool_field) is not None:
                    item[bool_field] = 'True' if item[bool_field] else 'False'
                else:
                    item[bool_field] = 'None'
            
            datum_bewertung_str = item.get('datum')
            if datum_bewertung_str:
                try:
                    item['datum_obj'] = datetime.fromisoformat(datum_bewertung_str.replace('Z', '+00:00'))
                except ValueError:
                    item['datum_obj'] = None
            bewertungen_list.append(item)

    except sqlite3.Error as e:
        flash(f"Datenbankfehler: {e}", "error")
    finally:
        if conn:
            conn.close()

    return render_template('alle_bewertungen.html',
                           unternehmen_name=unternehmen_name,
                           unternehmen_id=unternehmen_id,
                           bewertungen_list=bewertungen_list,
                           current_page=page,
                           total_pages=total_pages,
                           current_sort_option=sort_option,
                           current_filter_empfehlung=filter_empfehlung,
                           current_filter_status=filter_status,
                           reviews_per_page=reviews_per_page,
                           total_reviews_count_filtered=total_reviews_count
                           )

if __name__ == '__main__':
    # Stelle sicher, dass die Datenbank initialisiert wurde, bevor die App startet.
    # from database_setup import setup_database
    # setup_database() # Bei Bedarf einmalig ausführen
    print(f"Web UI startet. Öffne http://127.0.0.1:5000 in deinem Browser.")
    app.run(debug=True) # debug=True ist für die Entwicklung hilfreich