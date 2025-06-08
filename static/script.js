document.addEventListener('DOMContentLoaded', function () {
    // Modal-Logik
    const modal = document.getElementById('bewertungModal');
    const modalCloseBtn = document.querySelector('.modal-close-btn');
    const modalTitel = document.getElementById('modalTitel');
    const modalMeta = document.getElementById('modalMeta');
    const modalReviewerStatus = document.getElementById('modalReviewerStatus');
    const modalDetails = document.getElementById('modalDetails'); // Neuer Container
    const modalText = document.getElementById('modalText');
    const bewertungsKarten = document.querySelectorAll('.bewertung-karte');

    bewertungsKarten.forEach(karte => {
        karte.addEventListener('click', function() {
            modalTitel.textContent = this.dataset.titel;
            
            // Meta-Informationen (Datum, Sterne) zusammensetzen
            let metaHTML = `<span class="datum">${this.dataset.datumDisplay}</span>`;
            if (this.dataset.sterne) {
                metaHTML += ` <span class="sterne">${this.dataset.sterne}</span>`;
            }
            // Empfehlung im Modal
            if (this.dataset.isRecommended === 'True' || this.dataset.isRecommended === 'true') {
                metaHTML += ` <span class="empfehlung empfohlen">Empfohlen</span>`;
            } else if (this.dataset.isRecommended === 'False' || this.dataset.isRecommended === 'false') {
                metaHTML += ` <span class="empfehlung nicht-empfohlen">Nicht empfohlen</span>`;
            }
            modalMeta.innerHTML = metaHTML;

            // Status des Bewerters (z.B. ehemalig)
            let reviewerStatusHTML = '';
            if (this.dataset.isFormerEmployee === 'True' || this.dataset.isFormerEmployee === 'true') {
                reviewerStatusHTML = `<p><strong>Status:</strong> Ehemalige:r Mitarbeiter:in</p>`;
            }
            modalReviewerStatus.innerHTML = reviewerStatusHTML;

            // Zusätzliche Details im Modal
            let detailsHTML = '';
            if (this.dataset.reviewType === 'apprenticeship' && this.dataset.apprenticeshipJobTitle) {
                detailsHTML += `<p><strong>Ausbildung:</strong> ${this.dataset.apprenticeshipJobTitle}</p>`;
            } else if (this.dataset.reviewerPosition) {
                detailsHTML += `<p><strong>Position:</strong> ${this.dataset.reviewerPosition}</p>`;
            }
            if (this.dataset.reviewerDepartment) {
                detailsHTML += `<p><strong>Abteilung:</strong> ${this.dataset.reviewerDepartment}</p>`;
            }
            if (this.dataset.reviewedEntityName && this.dataset.reviewedEntityName !== document.querySelector('h1').textContent.replace('Details für: ', '').trim()) {
                 detailsHTML += `<p><strong>Unternehmensteil:</strong> ${this.dataset.reviewedEntityName}</p>`;
            }
            let locationParts = [];
            if (this.dataset.reviewerCity) locationParts.push(this.dataset.reviewerCity);
            if (this.dataset.reviewerState) locationParts.push(this.dataset.reviewerState);
            if (locationParts.length > 0) {
                detailsHTML += `<p><strong>Standort:</strong> ${locationParts.join(', ')}</p>`;
            }
            modalDetails.innerHTML = detailsHTML; // Korrektur: detailsHTML in modalDetails einfügen
            // Text mit nl2br-ähnlicher Funktionalität (ersetzt \n mit <br>)
            modalText.innerHTML = this.dataset.text.replace(/\n/g, '<br>');
            modal.style.display = 'block';
        });

        // Für Tastaturbedienung (Enter-Taste)
        karte.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                this.click();
            }
        });
    });

    if (modalCloseBtn) {
        modalCloseBtn.onclick = function() {
            modal.style.display = 'none';
        }
    }
    // Schließen des Modals, wenn außerhalb geklickt wird
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }

    // Chart für Profilverlauf
    const chartCanvas = document.getElementById('profilVerlaufChart');
    if (chartCanvas) {
        // Die Daten werden vom Template als JSON-String in einem data-Attribut erwartet
        // oder direkt in ein <script>-Tag im HTML geschrieben.
        // Hier gehen wir davon aus, dass die Daten im HTML verfügbar sind.
        // Wir müssen die Daten aus dem Python-Kontext in den JS-Kontext bekommen.
        // Eine Möglichkeit ist, sie in ein <script>-Tag im HTML zu schreiben:
        // <script>
        //  const chartData = {{ chart_profil_verlauf_data|tojson|safe }};
        // </script>
        // Und dann hier darauf zuzugreifen:
        // if (typeof chartData !== 'undefined' && chartData.length > 1) { ... }

        // Da wir die Daten direkt im Template rendern, können wir sie hier extrahieren,
        // wenn sie in einem data-Attribut des Canvas gespeichert wären, oder wir greifen
        // auf eine globale Variable zu, die im HTML-Template gesetzt wurde.
        // Für dieses Beispiel gehen wir davon aus, dass `chartVerlaufData` global verfügbar ist
        // (siehe Anpassung im HTML unten)

        if (typeof profilVerlaufChartData !== 'undefined' && profilVerlaufChartData.length > 1) {
            const labels = profilVerlaufChartData.map(item => {
                // Datum formatieren, falls es als String kommt und nicht schon Date-Objekt ist
                const date = new Date(item.scraping_datum);
                return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
            });
            const durchschnittData = profilVerlaufChartData.map(item => item.gesamtdurchschnitt);
            const anzahlData = profilVerlaufChartData.map(item => item.anzahl_bewertungen_gesamt);

            new Chart(chartCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Gesamtdurchschnitt',
                        data: durchschnittData,
                        borderColor: 'rgb(187, 134, 252)', // Lila
                        tension: 0.1,
                        yAxisID: 'yDurchschnitt'
                    }, {
                        label: 'Anzahl Bewertungen',
                        data: anzahlData,
                        borderColor: 'rgb(3, 218, 198)', // Türkis
                        tension: 0.1,
                        yAxisID: 'yAnzahl'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false, // Erlaubt dem Chart, die Höhe des Canvas zu nutzen
                    scales: {
                        yDurchschnitt: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: { display: true, text: 'Durchschnitt' },
                            min: 0, // Oder einen passenderen Minimalwert
                            max: 5  // Kununu-Bewertungen gehen bis 5
                        },
                        yAnzahl: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: { display: true, text: 'Anzahl Bewertungen' },
                            grid: { drawOnChartArea: false }, // Nur die Haupt-Gridlines anzeigen
                            min: 0 // Oder einen passenderen Minimalwert
                        },
                        x: {
                            title: { display: true, text: 'Datum des Scrapings' }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                        }
                    }
                }
            });
        }
    }

    // Chart für aktuellen Gesamtdurchschnitt (Donut)
    const donutChartCanvas = document.getElementById('gesamtdurchschnittDonutChart');
    if (donutChartCanvas && typeof aktuellerDurchschnittForDonut !== 'undefined' && aktuellerDurchschnittForDonut !== null) {
        const restWert = maxSkalaForDonut - aktuellerDurchschnittForDonut;

        new Chart(donutChartCanvas, {
            type: 'doughnut',
            data: {
                labels: ['Durchschnitt', 'Rest'],
                datasets: [{
                    label: 'Gesamtdurchschnitt',
                    data: [aktuellerDurchschnittForDonut, restWert > 0 ? restWert : 0],
                    backgroundColor: [
                        'rgb(3, 218, 198)',  // Türkis für den Durchschnitt
                        'rgba(255, 255, 255, 0.1)' // Heller, transparenter Hintergrund für den Rest
                    ],
                    borderColor: [
                        'rgb(3, 218, 198)',
                        'rgba(255, 255, 255, 0.2)'
                    ],
                    borderWidth: 1,
                    circumference: 180, // Halber Donut
                    rotation: 270,      // Startet unten
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false, // Erlaubt dem CSS, die Größe und das Seitenverhältnis vollständig zu kontrollieren.
                                          // Wichtig: Der Container muss dann die korrekten Proportionen haben.
                cutout: '70%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false },
                    customCanvasBackgroundColor : { 
                        text: aktuellerDurchschnittForDonut.toFixed(1)
                    }
                }
            },
            plugins: [{
                id: 'doughnutText',
                afterDraw(chart, args, options) {
                    const {ctx, chartArea: {top, bottom, left, right, width, height}, options: {plugins}} = chart;
                    if (plugins.customCanvasBackgroundColor && plugins.customCanvasBackgroundColor.text) {
                        ctx.save();
                        const text = plugins.customCanvasBackgroundColor.text;
                        ctx.font = 'bold 30px Arial';
                        ctx.fillStyle = 'rgb(3, 218, 198)';
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        const x = left + width / 2;
                        const y = top + height * 0.75; 
                        ctx.fillText(text, x, y);
                        ctx.restore();
                    }
                }
            }]
        });
    }

    // Filter-Logik für Bewertungen
    const filterEmpfehlungSelect = document.getElementById('filterEmpfehlung');
    const filterStatusSelect = document.getElementById('filterStatus');
    const sortBewertungenSelect = document.getElementById('sortBewertungen');
    // const bewertungsKarten ist bereits oben für das Modal definiert und kann hier wiederverwendet werden.

    function applyReviewFilters() {
        const empfehlungVal = filterEmpfehlungSelect ? filterEmpfehlungSelect.value : 'alle';
        const statusVal = filterStatusSelect ? filterStatusSelect.value : 'alle';

        bewertungsKarten.forEach(karte => {
            let showKarte = true;

            // Empfehlungsfilter
            if (empfehlungVal !== 'alle') {
                // data-is-recommended ist 'True', 'False', oder 'None' (String)
                const karteEmpfohlen = karte.dataset.isRecommended.toLowerCase(); // zu 'true', 'false', 'none'
                if (empfehlungVal !== karteEmpfohlen) {
                    showKarte = false;
                }
            }

            // Statusfilter (Aktuell/Ehemalig)
            if (statusVal !== 'alle' && showKarte) {
                // data-is-former-employee ist 'True', 'False', oder 'None' (String)
                const karteEhemalig = karte.dataset.isFormerEmployee.toLowerCase(); // zu 'true', 'false', 'none'
                if (statusVal !== karteEhemalig) {
                    showKarte = false;
                }
            }

            karte.style.display = showKarte ? '' : 'none'; // '' setzt auf Standard-Displaywert zurück
        });
    }

    if (filterEmpfehlungSelect) filterEmpfehlungSelect.addEventListener('change', applyReviewFilters);
    if (filterStatusSelect) filterStatusSelect.addEventListener('change', applyReviewFilters);

    // Sortier-Logik
    if (sortBewertungenSelect) {
        sortBewertungenSelect.addEventListener('change', function() {
            const selectedSort = this.value;
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('sort', selectedSort);
            window.location.href = currentUrl.toString(); // Lädt die Seite mit dem neuen Sortierparameter neu
        });
    }
});