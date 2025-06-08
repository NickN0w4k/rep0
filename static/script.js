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
            // Kurze Verzögerung, um den CSS-Übergang für das Modal zu ermöglichen
            setTimeout(() => {
                modal.classList.add('active');
            }, 10); // 10ms sollten reichen, um den display-Wechsel zu verarbeiten
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
            modal.classList.remove('active');
            // Warte, bis der Übergang beendet ist, bevor das Display auf none gesetzt wird
            setTimeout(() => { modal.style.display = 'none'; }, 300); // 300ms entspricht der CSS-Transition-Dauer
        }
    }
    // Schließen des Modals, wenn außerhalb geklickt wird
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }

    // Funktion zum Erstellen eines Profilverlauf-Linien-Charts
    function createProfileHistoryChart(canvasId, chartData, platformName) {
        const historyChartCanvas = document.getElementById(canvasId);
        if (!historyChartCanvas) {
            console.warn(`Canvas mit ID ${canvasId} für Verlaufschart nicht gefunden.`);
            return;
        }
        if (typeof chartData === 'undefined' || chartData === null || chartData.length <= 1) {
            console.warn(`Nicht genügend Daten für Verlaufschart ${canvasId} vorhanden.`);
            // Optional: Canvas leeren oder Platzhalter anzeigen
            return;
        }

        const labels = chartData.map(item => {
            const date = new Date(item.scraping_datum);
            return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
        });
        const durchschnittData = chartData.map(item => item.gesamtdurchschnitt);
        const anzahlData = chartData.map(item => item.anzahl_bewertungen_gesamt);

        const yDurchschnittLabel = `${platformName} Durchschnitt`;
        const yAnzahlLabel = `${platformName} Bewertungen`;

        new Chart(historyChartCanvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: yDurchschnittLabel,
                    data: durchschnittData,
                    borderColor: 'rgb(187, 134, 252)', // Lila
                    tension: 0.1,
                    yAxisID: 'yDurchschnitt'
                }, {
                    label: yAnzahlLabel,
                    data: anzahlData,
                    borderColor: 'rgb(3, 218, 198)', // Türkis
                    tension: 0.1,
                    yAxisID: 'yAnzahl'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    yDurchschnitt: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Durchschnitt' },
                        min: 0,
                        max: 5
                    },
                    yAnzahl: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Anzahl Bewertungen' },
                        grid: { drawOnChartArea: false },
                        min: 0
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

    // Initialisiere Kununu Profilverlauf Chart
    // Die Variable kununuProfilVerlaufChartData wird im HTML-Template global definiert
    if (typeof kununuProfilVerlaufChartData !== 'undefined') {
        createProfileHistoryChart('kununuProfilVerlaufChart', kununuProfilVerlaufChartData, 'Kununu');
    }

    // Initialisiere Trustpilot Profilverlauf Chart
    // Die Variable trustpilotProfilVerlaufChartData wird im HTML-Template global definiert
    if (typeof trustpilotProfilVerlaufChartData !== 'undefined') {
        createProfileHistoryChart('trustpilotProfilVerlaufChart', trustpilotProfilVerlaufChartData, 'Trustpilot');
    }


    // Funktion zum Erstellen eines Donut-Charts
    function createDonutChart(canvasId, currentScore, maxScore, scoreLabel) {
        const donutCanvas = document.getElementById(canvasId);
        if (!donutCanvas) {
            console.warn(`Canvas mit ID ${canvasId} nicht gefunden.`);
            return;
        }
        if (typeof currentScore === 'undefined' || currentScore === null) {
            console.warn(`Kein aktueller Score für Chart ${canvasId} vorhanden.`);
            // Optional: Canvas leeren oder Platzhalter anzeigen
            return;
        }

        const restWert = maxScore - currentScore;

        new Chart(donutCanvas, {
            type: 'doughnut',
            data: {
                labels: [scoreLabel || 'Schnitt', 'Rest'],
                datasets: [{
                    label: scoreLabel || 'Aktueller Schnitt',
                    data: [currentScore, restWert > 0 ? restWert : 0],
                    backgroundColor: [
                        'rgb(3, 218, 198)',  // Türkis für den Score
                        'rgba(255, 255, 255, 0.1)' // Heller, transparenter Hintergrund für den Rest
                    ],
                    borderColor: [
                        'rgb(3, 218, 198)',
                        'rgba(255, 255, 255, 0.2)'
                    ],
                    borderWidth: 1,
                    circumference: 180, // Halber Donut (optional, kann auch ein voller sein)
                    rotation: 270,      // Startet unten (optional)
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false },
                    customCanvasBackgroundColor : { 
                        text: currentScore.toFixed(1) // Zeigt den Wert mit einer Dezimalstelle
                    }
                }
            },
            plugins: [{
                id: 'doughnutText',
                afterDraw(chart, args, options) {
                    const {ctx, chartArea: {top, left, width, height}, options: {plugins}} = chart;
                    const customText = plugins?.customCanvasBackgroundColor?.text;
                    if (customText) {
                        ctx.save();
                        ctx.font = 'bold 30px Arial';
                        ctx.fillStyle = 'rgb(3, 218, 198)';
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        const x = left + width / 2;
                        // Y-Position anpassen, wenn es ein halber Donut ist, der unten startet
                        const yPositionFactor = chart.config.data.datasets[0].circumference === 180 && chart.config.data.datasets[0].rotation === 270 ? 0.75 : 0.5;
                        const y = top + height * yPositionFactor; 
                        ctx.fillText(customText, x, y);
                        ctx.restore();
                    }
                }
            }]
        });
    }

    // Initialisiere Kununu Donut Chart, wenn Daten vorhanden sind
    // Die Variablen aktuellerKununuSchnittForDonut und maxSkalaKununu werden im HTML-Template global definiert
    if (typeof aktuellerKununuSchnittForDonut !== 'undefined') {
        createDonutChart('kununuDurchschnittDonutChart', aktuellerKununuSchnittForDonut, maxSkalaKununu, 'Kununu');
    }

    // Initialisiere Trustpilot Donut Chart, wenn Daten vorhanden sind
    if (typeof aktuellerTrustpilotSchnittForDonut !== 'undefined') {
        createDonutChart('trustpilotDurchschnittDonutChart', aktuellerTrustpilotSchnittForDonut, maxSkalaTrustpilot, 'Trustpilot');
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