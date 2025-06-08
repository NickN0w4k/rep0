# database_setup.py
import sqlite3

def setup_database():
    """Erstellt die korrekte Datenbankstruktur inkl. Verlaufstabelle."""
    conn = sqlite3.connect('Datenbank.db')
    cursor = conn.cursor()

    # 1. Tabelle für Unternehmen (unverändert)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unternehmen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # 2. Tabelle für Plattformen (unverändert)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plattformen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    
    # 3. Verbindungstabelle: Unternehmens-Profile (unverändert)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unternehmens_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unternehmen_id INTEGER,
            plattform_id INTEGER,
            url TEXT NOT NULL UNIQUE,
            FOREIGN KEY (unternehmen_id) REFERENCES unternehmen (id),
            FOREIGN KEY (plattform_id) REFERENCES plattformen (id),
            UNIQUE(unternehmen_id, plattform_id)
        )
    ''')

    # 4. Tabelle für einzelne Bewertungen (überarbeitet für mehrere Plattformen)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bewertungen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profil_id INTEGER,
            sterne REAL,
            titel TEXT,
            text TEXT, 
            datum TEXT, -- Veröffentlichungsdatum (Kununu: createdAt/datum, Trustpilot: dates.publishedDate)
            platform_review_id TEXT, -- Eindeutige ID der Bewertung auf der Plattform (Kununu: UUID, Trustpilot: id)
            
            scraping_datum DATETIME DEFAULT CURRENT_TIMESTAMP,
            platform_data_updated_at TEXT, -- Kununus 'updatedAt' oder Trustpilots 'dates.updatedDate'
            last_seen_scraping_datum DATETIME, 
            is_deleted BOOLEAN DEFAULT 0, 

            -- Kununu-spezifische Felder (können für Trustpilot NULL sein)
            is_former_employee BOOLEAN, 
            review_type TEXT, -- z.B. 'employer', 'apprenticeship' (Kununu)
            is_recommended BOOLEAN,
            reviewer_position TEXT,
            reviewer_department TEXT,
            reviewed_entity_name TEXT, 
            reviewed_entity_uuid TEXT, 
            reviewer_city TEXT,
            reviewer_state TEXT,
            apprenticeship_job_title TEXT, 

            -- Trustpilot-spezifische Felder (können für Kununu NULL sein)
            consumer_display_name TEXT, -- Trustpilot: review.consumer.displayName
            date_of_experience TEXT,    -- Trustpilot: review.dates.experiencedDate
            review_language TEXT,       -- Trustpilot: review.language
            review_source TEXT,         -- Trustpilot: review.source
            review_likes INTEGER,       -- Trustpilot: review.likes
            is_verified_by_platform BOOLEAN, -- Trustpilot: review.labels.verification.isVerified

            FOREIGN KEY (profil_id) REFERENCES unternehmens_profile (id),
            UNIQUE (profil_id, platform_review_id) -- Stellt sicher, dass jede Bewertung pro Profil eindeutig ist
        )
    ''')
    # 6. NEUE Tabelle für einzelne Bewertungsfaktoren und deren Sterne
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bewertung_faktoren (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bewertung_id INTEGER,
            faktor_name TEXT NOT NULL,
            faktor_sterne REAL,
            FOREIGN KEY (bewertung_id) REFERENCES bewertungen (id) ON DELETE CASCADE,
            UNIQUE (bewertung_id, faktor_name) -- Stellt sicher, dass jeder Faktor pro Bewertung eindeutig ist
        )
    ''')

    # 5. NEUE Tabelle für den Verlauf der Gesamtnote
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profil_verlauf (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profil_id INTEGER,
            scraping_datum DATETIME DEFAULT CURRENT_TIMESTAMP,
            gesamtdurchschnitt REAL,
            anzahl_bewertungen_gesamt INTEGER,
            recommendation_rate REAL, -- NEU: Empfehlungsrate in Prozent
            FOREIGN KEY (profil_id) REFERENCES unternehmens_profile (id)
        )
    ''')

    # Optional: Standard-Plattformen hinzufügen
    cursor.execute("INSERT OR IGNORE INTO plattformen (name) VALUES ('Kununu')")
    cursor.execute("INSERT OR IGNORE INTO plattformen (name) VALUES ('Glassdoor')")

    conn.commit()
    conn.close()
    print("Datenbank wurde erstellt.")

if __name__ == '__main__':
    setup_database()