# Kununu Scraper und Analyse Web UI

Dieses Projekt ist ein Web-Scraper, der Daten von Kununu-Unternehmensprofilen sammelt, einschließlich Gesamtbewertungen, individuellen Bewertungen und deren Details. Die gesammelten Daten werden in einer SQLite-Datenbank gespeichert. Eine Web-Benutzeroberfläche, die mit Flask erstellt wurde, ermöglicht das Hinzufügen neuer Unternehmensprofile zum Scrapen und die Anzeige der gesammelten Daten, einschließlich Diagrammen zur Visualisierung von Trends.

## Funktionen

*   **Daten-Scraping:** Extrahiert Unternehmensinformationen und Bewertungen von Kununu.
*   **Datenspeicherung:** Speichert die gesammelten Daten in einer SQLite-Datenbank.
*   **Web-Benutzeroberfläche:**
    *   Hinzufügen neuer Kununu-Profile über deren URL.
    *   Anzeige einer Liste aller gescrapten Unternehmen.
    *   Detailansicht für jedes Unternehmen mit:
        *   Aktuellem Bewertungsdurchschnitt (Donut-Diagramm).
        *   Gesamtzahl der Bewertungen.
        *   Empfehlungsrate.
        *   Verlauf des Bewertungsdurchschnitts und der Anzahl der Bewertungen (Liniendiagramm).
        *   Liste der neuesten Bewertungen mit Filter- und Sortieroptionen.
        *   Modalansicht für vollständige Bewertungstexte.
    *   Manuelles Auslösen eines erneuten Scrapings für ein bestehendes Unternehmen.
*   **Datenbank-Setup:** Skript zum Initialisieren der Datenbankstruktur.
*   **Datenverlauf:** Speichert historische Daten des Profils (Durchschnitt, Anzahl Bewertungen) bei jedem Scraping-Vorgang.
*   **Umgang mit Änderungen:** Aktualisiert bestehende Bewertungen, wenn Änderungen auf Kununu erkannt werden (basierend auf `updatedAt` Zeitstempel). Markiert nicht mehr gefundene Bewertungen als potenziell gelöscht (obwohl die Logik zum expliziten Markieren als gelöscht noch implementiert werden könnte).

## Setup und Installation

1.  **Klone das Repository (optional, falls du es bereits hast):**
    ```bash
    git clone https://github.com/NickN0w4k/rep0.git
    cd rep0
    ```

2.  **Erstelle eine virtuelle Umgebung (empfohlen):**
    ```bash
    python -m venv venv
    ```
    Aktiviere die virtuelle Umgebung:
    *   Windows: `venv\Scripts\activate`
    *   macOS/Linux: `source venv/bin/activate`

3.  **Installiere die Abhängigkeiten:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialisiere die Datenbank:**
    Führe das `database_setup.py` Skript aus, um die `Datenbank.db` Datei und die notwendigen Tabellen zu erstellen:
    ```bash
    python database_setup.py
    ```
    Dies muss nur einmalig oder bei Änderungen an der Datenbankstruktur ausgeführt werden.

## Benutzung

1.  **Starte die Flask Web-Anwendung:**
    ```bash
    python web_ui.py
    ```

2.  **Öffne die Anwendung im Browser:**
    Navigiere zu `http://127.0.0.1:5000/`.

3.  **Füge ein neues Unternehmensprofil hinzu:**
    *   Klicke auf "Profil Hinzufügen".
    *   Gib die Kununu Profil-URL ein (z.B. `https://www.kununu.com/de/firmenname`).
    *   Klicke auf "Scraping starten". Der Scraper extrahiert den Unternehmensnamen automatisch von der Seite.

4.  **Unternehmensübersicht anzeigen:**
    *   Klicke auf "Unternehmensübersicht", um eine Liste aller gescrapten Unternehmen zu sehen.

5.  **Unternehmensdetails anzeigen:**
    *   Klicke auf ein Unternehmen in der Übersicht, um detaillierte Informationen, Diagramme und Bewertungen anzuzeigen.
    *   Auf der Detailseite kannst du das Scraping für dieses spezifische Unternehmen erneut auslösen.
    *   Filtere und sortiere die angezeigten Bewertungen.

## Verwendete Technologien

*   **Backend:** Python, Flask
*   **Datenbank:** SQLite
*   **Web Scraping:** `requests`, `BeautifulSoup4`
*   **Frontend:** HTML, CSS, JavaScript
*   **Diagramme:** Chart.js
*   **Templating:** Jinja2

## Mögliche zukünftige Erweiterungen

*   Asynchrone Scraping-Tasks (z.B. mit Celery), um die Web-UI nicht zu blockieren.
*   Verbesserte Fehlerbehandlung und Logging.
*   Benutzerauthentifizierung.
*   Automatisches, periodisches Scrapen.
*   Erweiterte Datenanalyse und Visualisierungen.
*   Explizites Markieren von gelöschten Bewertungen.