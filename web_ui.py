from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime # Importiere datetime für die Konvertierung
from markupsafe import Markup # Markup wird von markupsafe importiert

# Importiere die notwendigen Funktionen aus deinem Scraper-Skript
# Stelle sicher, dass kununu_scraper.py im selben Verzeichnis liegt oder im Python-Pfad ist.
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
    profil_uebersicht_url = request.form.get('profil_uebersicht_url')
    unternehmen_name = None

    if not profil_uebersicht_url:
        flash('Profil-URL muss ausgefüllt werden!', 'error')
        return redirect(url_for('add_profile_page')) # Leitet bei Fehler zurück zur Add-Seite

    try:
        # Stelle sicher, dass die URL nicht mit einem Slash endet, bevor wir den Suffix anhängen
        temp_uebersicht_url = profil_uebersicht_url.rstrip('/')
        
        # 1. Unternehmensnamen von der Kununu-Seite extrahieren
        print(f"WebUI: Rufe {temp_uebersicht_url} auf, um Unternehmensnamen zu extrahieren...")
        soup_uebersicht = fetch_and_parse_url(temp_uebersicht_url) # fetch_and_parse_url muss importiert sein
        if soup_uebersicht:
            unternehmen_name = extract_company_name_from_kununu_profile(soup_uebersicht)
        
        if not unternehmen_name:
            flash(f"Konnte Unternehmensnamen nicht von {temp_uebersicht_url} extrahieren. Bitte URL prüfen.", 'error')
            return redirect(url_for('add_profile_page'))

        print(f"WebUI: Unternehmensname extrahiert: {unternehmen_name}")
        profil_kommentare_url = f"{temp_uebersicht_url}/kommentare?sort=newest"

        print(f"WebUI: Starte Scraping für {unternehmen_name}...")
        # Rufe die main_scraper Funktion auf.
        # Beachte: Dies ist ein blockierender Aufruf. Bei sehr langen Scraping-Vorgängen
        # könnte die Webseite für die Dauer des Vorgangs nicht reagieren.
        # Für produktive Systeme wären hier asynchrone Tasks (z.B. mit Celery) besser.
        main_scraper(unternehmen_name, temp_uebersicht_url, profil_kommentare_url)
        flash(f"Scraping für {unternehmen_name} wurde gestartet/abgeschlossen. Überprüfe die Konsolenausgaben und die Datenbank.", 'success')
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

        # 3. Profil-URL für Kununu holen
        cursor.execute("SELECT url FROM unternehmens_profile WHERE unternehmen_id = ? AND plattform_id = ?", 
                       (unternehmen_id, kununu_plattform_id))
        profile_row = cursor.fetchone()
        if not profile_row:
            flash(f"Kein Kununu-Profil für {unternehmen_name} in der Datenbank gefunden.", "error")
            return redirect(url_for('unternehmens_details', unternehmen_id=unternehmen_id))
        profil_uebersicht_url = profile_row['url']

        # 4. Kommentare-URL generieren
        temp_uebersicht_url = profil_uebersicht_url
        if temp_uebersicht_url.endswith('/'):
            temp_uebersicht_url = temp_uebersicht_url[:-1]
        profil_kommentare_url = f"{temp_uebersicht_url}/kommentare?sort=newest"

        # 5. Scraper aufrufen
        print(f"WebUI: Starte Scraping für spezifisches Unternehmen: {unternehmen_name} (ID: {unternehmen_id})")
        main_scraper(unternehmen_name, profil_uebersicht_url, profil_kommentare_url)
        flash(f"Scraping für {unternehmen_name} wurde gestartet/abgeschlossen. Überprüfe die Konsolenausgaben und die Datenbank.", 'success')

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
    aktueller_gesamtdurchschnitt = None
    aktuellste_anzahl_bewertungen = None
    aktuelle_empfehlungsrate = None

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

        # Aktuellsten Gesamtdurchschnitt für die Donut-Chart holen
        if profil_verlauf_list: # Wenn es überhaupt Verlaufseinträge gibt
            aktueller_gesamtdurchschnitt = profil_verlauf_list[0]['gesamtdurchschnitt'] # Der erste Eintrag ist der neueste
            aktuellste_anzahl_bewertungen = profil_verlauf_list[0]['anzahl_bewertungen_gesamt']
            aktuelle_empfehlungsrate = profil_verlauf_list[0].get('recommendation_rate') # .get() für den Fall, dass es noch alte Einträge ohne gibt

        # Sortieroption aus Query-Parametern holen
        sort_option = request.args.get('sort', 'neueste') # Standard: neueste
        order_by_clause = "ORDER BY b.datum DESC" # Standard-Sortierung

        if sort_option == 'sterne_asc':
            order_by_clause = "ORDER BY b.sterne ASC, b.datum DESC"
        elif sort_option == 'sterne_desc':
            order_by_clause = "ORDER BY b.sterne DESC, b.datum DESC"
        # 'neueste' ist bereits der Standard


        # Die 5 neuesten Bewertungen für dieses Unternehmen holen
        # Wir gehen davon aus, dass 'datum' in der 'bewertungen'-Tabelle ein ISO-Datumsstring ist,
        # der für die Sortierung geeignet ist.
        sql_query_select_from_where = """
            SELECT
                b.sterne, b.titel, b.text, b.datum, b.is_former_employee,
                b.review_type, b.is_recommended, b.reviewer_position, b.reviewer_department,
                b.reviewed_entity_name, b.reviewer_city, b.reviewer_state,
                b.apprenticeship_job_title
            FROM bewertungen b
            JOIN unternehmens_profile up ON b.profil_id = up.id
            WHERE up.unternehmen_id = ? AND b.is_deleted = 0 
        """
        # order_by_clause ist bereits korrekt definiert (z.B. "ORDER BY b.datum DESC")
        # limit_clause ist ebenfalls statisch
        limit_clause_sql = "LIMIT 50"
        
        # Explizite String-Konkatenation für die finale Query
        final_sql_query = sql_query_select_from_where + " " + order_by_clause + " " + limit_clause_sql
        
        # Debug-Ausgabe für die finale SQL-Abfrage
        print(f"--- DEBUG SQL Query für Bewertungen ---\n{final_sql_query}\n--- END DEBUG ---")

        raw_bewertungen_data = conn.execute(final_sql_query, (unternehmen_id,)).fetchall()

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
        if 'final_sql_query' in locals(): # Prüft, ob die Variable existiert
            print(f"Fehler bei SQL-Query: {final_sql_query}")
        else:
            print("Fehler trat vor der Erstellung der SQL-Query für Bewertungen auf.")
    finally:
        if conn:
            conn.close()
    return render_template('unternehmens_details.html',
                           unternehmen_name=unternehmen_name,
                           profil_verlauf_list=profil_verlauf_list, # Für die Tabelle
                           chart_profil_verlauf_data=chart_profil_verlauf_data, # Für das Liniendiagramm
                           aktueller_gesamtdurchschnitt=aktueller_gesamtdurchschnitt, # Für die Donut-Chart
                           aktuellste_anzahl_bewertungen=aktuellste_anzahl_bewertungen, # Für die neue Stat-Kachel
                           aktuelle_empfehlungsrate=aktuelle_empfehlungsrate, # Für die neue Empfehlungsrate-Anzeige
                           neueste_bewertungen_list=neueste_bewertungen_list, # Sortierte Liste
                           current_sort_option=sort_option, # Für das Sortier-Dropdown
                           unternehmen_id=unternehmen_id) # unternehmen_id hier hinzufügen

if __name__ == '__main__':
    # Stelle sicher, dass die Datenbank initialisiert wurde, bevor die App startet.
    # from database_setup import setup_database
    # setup_database() # Bei Bedarf einmalig ausführen
    print(f"Web UI startet. Öffne http://127.0.0.1:5000 in deinem Browser.")
    app.run(debug=True) # debug=True ist für die Entwicklung hilfreich