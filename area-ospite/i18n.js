/* Traduzioni dell'Area ospite (inglese e tedesco). L'italiano e' la lingua di partenza:
   le frasi nuove usano t('frase'), quelle gia' scritte vengono tradotte da traduciDom()
   cercando il testo esatto (DIZ) o uno schema con parti variabili (PATT).
   Le frasi non presenti restano in italiano. */
const _D = (it, en, de) => ({ it, en, de });
const _LISTA = [
  // generali
  _D('Torna indietro', 'Back', 'Zurück'), _D('Torna alla home', 'Back to home', 'Zurück zur Startseite'), _D('Chiudi', 'Close', 'Schließen'),
  _D('Annulla', 'Cancel', 'Abbrechen'), _D('Conferma', 'Confirm', 'Bestätigen'), _D('Riprova', 'Try again', 'Erneut versuchen'), _D('Avanti', 'Next', 'Weiter'),
  _D('Caricamento…', 'Loading…', 'Wird geladen…'), _D('Invio in corso…', 'Sending…', 'Wird gesendet…'), _D('Salvataggio…', 'Saving…', 'Wird gespeichert…'), _D('Annullo…', 'Cancelling…', 'Wird storniert…'),
  _D('A breve', 'Coming soon', 'Demnächst'), _D('Disponibile a breve', 'Coming soon', 'Demnächst verfügbar'), _D('Disponibile a breve.', 'Coming soon.', 'Demnächst verfügbar.'),
  _D('Connessione assente', 'No connection', 'Keine Verbindung'), _D('Connessione assente, riprova', 'No connection, try again', 'Keine Verbindung, bitte erneut versuchen'),
  _D('Connessione assente. Controlla la rete e riprova.', 'No connection. Check your network and try again.', 'Keine Verbindung. Prüfe dein Netz und versuche es erneut.'),
  _D('Controlla la connessione e riprova.', 'Check your connection and try again.', 'Prüfe deine Verbindung und versuche es erneut.'),
  _D('Controlla la connessione e ricarica la pagina.', 'Check your connection and reload the page.', 'Prüfe deine Verbindung und lade die Seite neu.'),
  _D('Link non valido', 'Invalid link', 'Ungültiger Link'), _D('Link non valido o scaduto', 'Invalid or expired link', 'Ungültiger oder abgelaufener Link'),
  _D('Questo link non è valido o è scaduto. Contatta la struttura per riceverne uno nuovo.', 'This link is not valid or has expired. Contact the resort to get a new one.', 'Dieser Link ist ungültig oder abgelaufen. Wende dich an die Anlage, um einen neuen zu erhalten.'),
  _D('Qualcosa non va', 'Something went wrong', 'Etwas ist schiefgelaufen'),
  _D('Garden River · questo link è personale, non condividerlo.', 'Garden River · this link is personal, please do not share it.', 'Garden River · dieser Link ist persönlich, bitte nicht weitergeben.'),
  _D('Benvenuto al Garden River', 'Welcome to Garden River', 'Willkommen im Garden River'),
  _D('Area ospite', 'Guest area', 'Gästebereich'), _D('Area ospite · Garden River', 'Guest area · Garden River', 'Gästebereich · Garden River'),
  // home
  _D('Da sapere', 'Good to know', 'Gut zu wissen'), _D('Oggi per te', 'Today for you', 'Heute für dich'), _D('Adesso al villaggio', 'Right now at the village', 'Jetzt im Dorf'),
  _D('Tutto il villaggio', 'The whole village', 'Das ganze Dorf'),
  _D('Da completare', 'To complete', 'Zu erledigen'), _D('Importante', 'Important', 'Wichtig'), _D('Informazione', 'Information', 'Information'), _D('Partenza', 'Departure', 'Abreise'), _D('Navetta', 'Shuttle', 'Shuttle'), _D('Meteo', 'Weather', 'Wetter'),
  _D('Il tuo parere', 'Your opinion', 'Deine Meinung'), _D('Conto', 'Bill', 'Rechnung'),
  _D('Ordine di oggi non completato', "Today's order is not complete", 'Die heutige Bestellung ist nicht abgeschlossen'),
  _D('Ordine di domani non completato', "Tomorrow's order is not complete", 'Die morgige Bestellung ist nicht abgeschlossen'),
  _D('Non hai ancora scelto cosa mangiare. Si ordina entro le 8:30.', "You haven't chosen what to eat yet. Orders close at 8:30.", 'Du hast noch nicht gewählt, was du essen möchtest. Bestellungen bis 8:30 Uhr.'),
  _D('Non hai ancora scelto cosa mangiare. Si ordina entro le 8:30 di domani mattina.', "You haven't chosen what to eat yet. Order by 8:30 tomorrow morning.", 'Du hast noch nicht gewählt, was du essen möchtest. Bestellung bis morgen früh 8:30 Uhr.'),
  _D('Ordina ora', 'Order now', 'Jetzt bestellen'), _D('Cosa fare', 'What to do', 'Was zu tun ist'), _D('Valuta', 'Rate', 'Bewerten'), _D('Vedi la corsa', 'See the ride', 'Fahrt ansehen'), _D('Vedi il conto', 'See the bill', 'Rechnung ansehen'),
  _D('Domani è il giorno della partenza', 'Tomorrow is your departure day', 'Morgen ist dein Abreisetag'), _D('Oggi è il giorno della partenza', 'Today is your departure day', 'Heute ist dein Abreisetag'),
  _D('Check-out entro le 10:00. Scopri cosa fare prima di partire.', 'Check-out by 10:00. Find out what to do before you leave.', 'Check-out bis 10:00 Uhr. Erfahre, was vor der Abreise zu tun ist.'),
  _D("Com'è andato il soggiorno?", 'How was your stay?', 'Wie war dein Aufenthalt?'), _D('Bastano 10 secondi: ci aiuta a migliorare.', 'It takes 10 seconds and helps us improve.', 'Es dauert nur 10 Sekunden und hilft uns, besser zu werden.'),
  _D('La tua corsa delle {o} è confermata', 'Your ride at {o} is confirmed', 'Deine Fahrt um {o} ist bestätigt'), _D('Richiesta navetta delle {o} in attesa', 'Shuttle request for {o} pending', 'Shuttle-Anfrage für {o} ausstehend'), _D('Autista: {n}', 'Driver: {n}', 'Fahrer: {n}'),
  _D('Possibile pioggia oggi', 'Rain possible today', 'Heute möglicherweise Regen'),
  _D("Alcune attività all'aperto potrebbero spostarsi al coperto: chiedi allo staff di animazione.", 'Some outdoor activities may move indoors: ask the entertainment team.', 'Einige Outdoor-Aktivitäten könnten nach drinnen verlegt werden: frag das Animationsteam.'),
  _D('Stasera · ore {o}', 'Tonight · {o}', 'Heute Abend · {o} Uhr'), _D('Vedi il programma', 'See the programme', 'Programm ansehen'), _D('Adesso', 'Now', 'Jetzt'), _D('fino alle {o}', 'until {o}', 'bis {o} Uhr'),
  _D('Prossima attività', 'Next activity', 'Nächste Aktivität'), _D('alle {o}', 'at {o}', 'um {o}'), _D('poi {n} alle {o}', 'then {n} at {o}', 'danach {n} um {o}'),
  _D('I tuoi pasti', 'Your meals', 'Deine Mahlzeiten'), _D('{p} ordinato', '{p} ordered', '{p} bestellt'), _D('Nessun pasto ordinato oggi', 'No meal ordered today', 'Heute noch nichts bestellt'), _D('Pasti inclusi', 'Meals included', 'Mahlzeiten inklusive'),
  _D('Domani da ordinare', 'Tomorrow still to order', 'Morgen noch zu bestellen'), _D('{n} da fare', '{n} to do', '{n} offen'),
  _D('Pranzo', 'Lunch', 'Mittagessen'), _D('Cena', 'Dinner', 'Abendessen'), _D('Colazione', 'Breakfast', 'Frühstück'),
  _D('Corsa alle {o}', 'Ride at {o}', 'Fahrt um {o}'), _D('Confermata', 'Confirmed', 'Bestätigt'), _D('In attesa di conferma', 'Awaiting confirmation', 'Wartet auf Bestätigung'),
  _D('Nessuna corsa prenotata', 'No ride booked', 'Keine Fahrt gebucht'), _D('Prenota il rientro dalla spiaggia', 'Book your ride back from the beach', 'Buche die Rückfahrt vom Strand'),
  _D('La tua spiaggia', 'Your beach', 'Dein Strand'), _D('Ombrellone {n}', 'Umbrella {n}', 'Sonnenschirm {n}'), _D('Mostra il tagliandino', 'Show your ticket', 'Ticket zeigen'),
  _D('Aperta fino alle {o}', 'Open until {o}', 'Geöffnet bis {o}'), _D('Chiusa · riapre alle {o}', 'Closed · reopens at {o}', 'Geschlossen · öffnet um {o}'), _D('Chiusa · riapre domani alle {o}', 'Closed · reopens tomorrow at {o}', 'Geschlossen · öffnet morgen um {o}'),
  _D('{s} fino alle {o}', '{s} until {o}', '{s} bis {o}'), _D('Prossimo: {s} alle {o}', 'Next: {s} at {o}', 'Als Nächstes: {s} um {o}'),
  _D('Piscina', 'Pool', 'Pool'), _D('Ristorante', 'Restaurant', 'Restaurant'), _D('Domani', 'Tomorrow', 'Morgen'),
  _D('Sereno', 'Clear', 'Klar'), _D('Poco nuvoloso', 'Partly cloudy', 'Leicht bewölkt'), _D('Coperto', 'Overcast', 'Bedeckt'), _D('Nebbia', 'Fog', 'Nebel'), _D('Pioggia', 'Rain', 'Regen'), _D('Temporale', 'Thunderstorm', 'Gewitter'), _D('Nuvoloso', 'Cloudy', 'Wolkig'),
  _D('Siamo qui per te', "We're here for you", 'Wir sind für dich da'), _D('Chiamaci o seguici: ci trovi anche online.', 'Call us or follow us: you can find us online too.', 'Ruf uns an oder folge uns: Du findest uns auch online.'), _D('Seguici', 'Follow us', 'Folge uns'), _D('Reception', 'Reception', 'Rezeption'),
  // sezioni e banner
  _D('Richiesta assistenza', 'Request assistance', 'Hilfe anfragen'), _D('Chiedi aiuto alla reception', 'Ask reception for help', 'Frag die Rezeption um Hilfe'), _D('Info utili', 'Useful info', 'Nützliche Infos'), _D('Orari e informazioni', 'Hours and information', 'Öffnungszeiten und Infos'),
  _D('Animazione', 'Entertainment', 'Animation'), _D('Il programma della settimana', "The week's programme", 'Das Wochenprogramm'), _D('Ristorazione', 'Dining', 'Gastronomie'), _D('Menu e informazioni', 'Menu and information', 'Menü und Infos'),
  _D('Pensione completa', 'Full board', 'Vollpension'), _D('Mezza pensione', 'Half board', 'Halbpension'), _D('Prenotazione e conto', 'Booking and bill', 'Buchung und Rechnung'), _D('I tuoi dati', 'Your details', 'Deine Daten'),
  _D('Mappa del villaggio', 'Village map', 'Dorfplan'), _D('Tocca un punto per vederlo', 'Tap a point to see it', 'Tippe auf einen Punkt'),
  _D('Il tuo tagliandino', 'Your ticket', 'Dein Ticket'), _D('Da mostrare allo stabilimento', 'To show at the beach club', 'Am Strandbad vorzeigen'), _D('La tua partenza', 'Your departure', 'Deine Abreise'), _D("Cosa fare e com'è andata", 'What to do and how it went', 'Was zu tun ist und wie es war'),
  // ticket / partenza / feedback
  _D("L'ombrellone non è ancora stato assegnato. Chiedi alla reception.", "Your umbrella hasn't been assigned yet. Ask reception.", 'Der Sonnenschirm wurde noch nicht zugewiesen. Frag an der Rezeption.'),
  _D('Valido oggi', 'Valid today', 'Heute gültig'), _D('Scaduto', 'Expired', 'Abgelaufen'), _D('Non ancora valido', 'Not valid yet', 'Noch nicht gültig'), _D('Ombrellone', 'Umbrella', 'Sonnenschirm'), _D('Arrivo', 'Arrival', 'Anreise'), _D('Fino al', 'Until', 'Bis'),
  _D('Navetta per il mare', 'Shuttle to the beach', 'Shuttle zum Strand'),
  _D("Mostra questa schermata allo stabilimento. L'orologio che scorre serve a riconoscere un tagliandino vero da uno screenshot.", 'Show this screen at the beach club. The running clock tells a real ticket from a screenshot.', 'Zeige diesen Bildschirm am Strandbad. Die laufende Uhr unterscheidet ein echtes Ticket von einem Screenshot.'),
  _D('Check-out entro le ore 10:00.', 'Check-out by 10:00.', 'Check-out bis 10:00 Uhr.'),
  _D("Prima di lasciare l'alloggio telefona in reception per concordare il controllo finale.", 'Before leaving, call reception to arrange the final check.', 'Rufe vor dem Verlassen die Rezeption an, um die Endkontrolle zu vereinbaren.'),
  _D('Lascia la biancheria usata in una federa fuori dalla porta.', 'Leave the used linen in a pillowcase outside the door.', 'Lege die gebrauchte Wäsche in einem Kissenbezug vor die Tür.'),
  _D('Se hai chiavi o telecomando, riconsegnali in reception.', 'If you have keys or a remote, return them to reception.', 'Gib Schlüssel oder Fernbedienung an der Rezeption zurück.'),
  _D('Ci sono € {n} da saldare', '€ {n} left to pay', '€ {n} noch zu zahlen'), _D('Oggi si parte', 'Departure today', 'Heute ist Abreise'), _D('Domani si parte', 'Departure tomorrow', 'Morgen ist Abreise'), _D('Mancano {n} giorni alla partenza', '{n} days until departure', 'Noch {n} Tage bis zur Abreise'),
  _D('Tocca le stelle: ci aiuta a migliorare.', 'Tap the stars: it helps us improve.', 'Tippe auf die Sterne: Das hilft uns, besser zu werden.'), _D('Vuoi dirci qualcosa? (facoltativo)', 'Anything to tell us? (optional)', 'Möchtest du uns etwas mitteilen? (optional)'),
  _D('Invia valutazione', 'Send rating', 'Bewertung senden'), _D('Grazie!', 'Thank you!', 'Danke!'), _D('Siamo felici che ti sia piaciuto!', "We're glad you enjoyed it!", 'Wir freuen uns, dass es dir gefallen hat!'), _D('Il tuo messaggio è arrivato alla reception.', 'Your message has reached reception.', 'Deine Nachricht ist an der Rezeption angekommen.'),
  _D('Raccontalo su Tripadvisor', 'Tell the world on Tripadvisor', 'Erzähle es auf Tripadvisor'), _D('Non sono riuscito a inviare, riprova', "Couldn't send, please try again", 'Senden fehlgeschlagen, bitte erneut versuchen'),
  // mappa punti
  _D('Ingresso', 'Entrance', 'Eingang'), _D('Teatro', 'Theatre', 'Theater'), _D('Bar', 'Bar', 'Bar'), _D('Bar teatro', 'Theatre bar', 'Theater-Bar'), _D('Bar piscina', 'Pool bar', 'Pool-Bar'), _D('Parco giochi', 'Playground', 'Spielplatz'), _D('Campo da calcio', 'Football pitch', 'Fußballplatz'), _D('Beach volley', 'Beach volleyball', 'Beachvolleyball'),
  _D('Dog zone', 'Dog zone', 'Hundezone'), _D('Lavaggio cani', 'Dog wash', 'Hundewäsche'), _D('Lavatrici', 'Laundry', 'Waschmaschinen'), _D('Bagni', 'Toilets', 'Toiletten'), _D('Water house', 'Water house', 'Water House'), _D('Isola ecologica', 'Recycling point', 'Wertstoffinsel'),
  _D('Pista ciclabile', 'Cycle path', 'Radweg'), _D('Parcheggio', 'Car park', 'Parkplatz'),
  // animazione
  _D('Diurno', 'Daytime', 'Tagsüber'), _D('Serale', 'Evening', 'Abends'), _D('Tutto', 'All', 'Alle'), _D('Teen', 'Teen', 'Teen'), _D('Mini club', 'Mini club', 'Mini-Club'), _D('Teen club', 'Teen club', 'Teen-Club'),
  _D('4-10 anni', 'ages 4–10', '4–10 Jahre'), _D('11-17 anni', 'ages 11–17', '11–17 Jahre'), _D('Evento speciale', 'Special event', 'Besonderes Event'), _D('Programma del giorno', 'Programme of the day', 'Tagesprogramma'), _D('Per oggi è tutto', "That's all for today", 'Das war es für heute'),
  _D('Nessuna attività per questa selezione.', 'No activities for this selection.', 'Keine Aktivitäten für diese Auswahl.'), _D('Il programma può variare in base al meteo.', 'The programme may change depending on the weather.', 'Das Programm kann wetterbedingt abweichen.'),
  _D('Dove sono le serate', 'Where the evenings take place', 'Wo die Abendshows stattfinden'), _D('Programma Animazione', 'Entertainment programme', 'Animationsprogramm'), _D('Ciao, sono Gardy! Cosa facciamo oggi?', "Hi, I'm Gardy! What shall we do today?", 'Hallo, ich bin Gardy! Was machen wir heute?'),
  _D('Sab', 'Sat', 'Sa'), _D('Dom', 'Sun', 'So'), _D('Lun', 'Mon', 'Mo'), _D('Mar', 'Tue', 'Di'), _D('Mer', 'Wed', 'Mi'), _D('Gio', 'Thu', 'Do'), _D('Ven', 'Fri', 'Fr'), _D('OGGI', 'TODAY', 'HEUTE'),
  _D('Sabato', 'Saturday', 'Samstag'), _D('Domenica', 'Sunday', 'Sonntag'), _D('Lunedì', 'Monday', 'Montag'), _D('Martedì', 'Tuesday', 'Dienstag'), _D('Mercoledì', 'Wednesday', 'Mittwoch'), _D('Giovedì', 'Thursday', 'Donnerstag'), _D('Venerdì', 'Friday', 'Freitag'),
  // ristorazione
  _D('Menu alla carta', 'À la carte menu', 'Speisekarte'), _D('Sempre disponibile · tocca per sfogliarlo', 'Always available · tap to browse', 'Immer verfügbar · zum Blättern tippen'), _D('Apri ›', 'Open ›', 'Öffnen ›'),
  _D('Orari del ristorante', 'Restaurant hours', 'Öffnungszeiten des Restaurants'), _D('Non riesco a caricare il menu', "I can't load the menu", 'Das Menü kann nicht geladen werden'),
  _D('Pensione completa · ordina pranzo e cena', 'Full board · order lunch and dinner', 'Vollpension · bestelle Mittag- und Abendessen'), _D('Mezza pensione · scegli un pasto', 'Half board · choose a meal', 'Halbpension · wähle eine Mahlzeit'),
  _D('Mezzogiorno', 'Midday', 'Mittag'), _D('Sera', 'Evening', 'Abend'), _D('Mezzogiorno · ordina entro le 8:30', 'Midday · order by 8:30', 'Mittag · Bestellung bis 8:30 Uhr'), _D('Sera · ordina entro le 8:30', 'Evening · order by 8:30', 'Abend · Bestellung bis 8:30 Uhr'),
  _D('✓ Ordinato', '✓ Ordered', '✓ Bestellt'), _D('✓ Confermato', '✓ Confirmed', '✓ Bestätigt'), _D('⏱ Scaduto', '⏱ Expired', '⏱ Abgelaufen'), _D('Gli ordini per questo pasto sono chiusi.', 'Orders for this meal are closed.', 'Die Bestellungen für diese Mahlzeit sind geschlossen.'),
  _D('Menu bambini', "Children's menu", 'Kindermenü'), _D('BAMBINI', 'CHILDREN', 'KINDER'), _D('Menu Bambini', "Children's menu", 'Kindermenü'),
  _D('Antipasti', 'Starters', 'Vorspeisen'), _D('Primi Carne', 'First courses · meat', 'Erste Gänge · Fleisch'), _D('Primi Pesce', 'First courses · fish', 'Erste Gänge · Fisch'), _D('Secondi Carne', 'Main courses · meat', 'Hauptgänge · Fleisch'), _D('Secondi Pesce', 'Main courses · fish', 'Hauptgänge · Fisch'), _D('Contorni', 'Sides', 'Beilagen'), _D('Dessert', 'Desserts', 'Desserts'),
  _D('Note (allergie, preferenze…)', 'Notes (allergies, preferences…)', 'Hinweise (Allergien, Vorlieben…)'),
  _D('Nessun menu disponibile per questo giorno.', 'No menu available for this day.', 'Für diesen Tag ist kein Menü verfügbar.'),
  _D('Con la mezza pensione puoi ordinare', 'With half board you can order', 'Mit Halbpension kannst du'), _D('pranzo oppure cena', 'lunch or dinner', 'Mittag- oder Abendessen'), _D(', non entrambi.', ', not both.', ' bestellen, nicht beides.'),
  _D('Recupero pasti · giorno di partenza', 'Meal recovery · departure day', 'Mahlzeiten nachholen · Abreisetag'), _D('In base al tuo piano puoi recuperare questi pasti. Ordina entro le 8:30.', 'According to your plan you can recover these meals. Order by 8:30.', 'Gemäß deinem Plan kannst du diese Mahlzeiten nachholen. Bestelle bis 8:30 Uhr.'),
  _D('Conferma ordine di oggi', "Confirm today's order", 'Heutige Bestellung bestätigen'), _D('Conferma ordine di domani', "Confirm tomorrow's order", 'Morgige Bestellung bestätigen'), _D('Ordine di oggi', "Today's order", 'Heutige Bestellung'), _D('Ordine di domani', "Tomorrow's order", 'Morgige Bestellung'),
  _D('Invia ordine', 'Send order', 'Bestellung senden'), _D('Ordine inviato ✓', 'Order sent ✓', 'Bestellung gesendet ✓'),
  _D('Seleziona almeno un piatto prima di confermare', 'Select at least one dish before confirming', 'Wähle vor der Bestätigung mindestens ein Gericht'), _D('Seleziona almeno un piatto', 'Select at least one dish', 'Wähle mindestens ein Gericht'),
  _D('Gli ordini per questo pasto sono chiusi', 'Orders for this meal are closed', 'Die Bestellungen für diese Mahlzeit sind geschlossen'), _D('Hai superato le porzioni disponibili', "You've exceeded the available portions", 'Du hast die verfügbaren Portionen überschritten'),
  _D('Questo pasto è già stato ordinato', 'This meal has already been ordered', 'Diese Mahlzeit wurde bereits bestellt'), _D('Con la mezza pensione puoi ordinare un solo pasto al giorno', 'With half board you can order one meal per day', 'Mit Halbpension kannst du eine Mahlzeit pro Tag bestellen'),
  _D('Il lunedì sera è serata sushi.', 'Monday evening is sushi night.', 'Montagabend ist Sushi-Abend.'), _D('Colazione: 8:00 – 10:00', 'Breakfast: 8:00 – 10:00', 'Frühstück: 8:00 – 10:00'), _D('Pranzo: 13:00 – 14:30', 'Lunch: 13:00 – 14:30', 'Mittagessen: 13:00 – 14:30'), _D('Cena: 20:00 – 22:00', 'Dinner: 20:00 – 22:00', 'Abendessen: 20:00 – 22:00'),
  _D('Per intolleranze, allergie o menù vegetariano/vegano contatta lo staff in anticipo.', 'For intolerances, allergies or a vegetarian/vegan menu, please contact the staff in advance.', 'Bei Unverträglichkeiten, Allergien oder vegetarischem/veganem Menü wende dich vorab an das Personal.'),
  _D('Il lunedì sera è serata sushi. Per intolleranze, allergie o menù vegetariano/vegano contatta lo staff in anticipo.', 'Monday evening is sushi night. For intolerances, allergies or a vegetarian/vegan menu, please contact the staff in advance.', 'Montagabend ist Sushi-Abend. Bei Unverträglichkeiten, Allergien oder vegetarischem/veganem Menü wende dich vorab an das Personal.'),
  _D('Il nostro ristorante', 'Our restaurant', 'Unser Restaurant'), _D('Apri il menu in PDF', 'Open the menu as PDF', 'Menü als PDF öffnen'),
  _D('Il soggiorno non include i pasti, ma il ristorante è aperto anche a te: puoi mangiare alla carta quando vuoi, nei suoi orari.', 'Your stay does not include meals, but the restaurant is open to you too: you can eat à la carte whenever you like, during its opening hours.', 'Dein Aufenthalt enthält keine Mahlzeiten, aber das Restaurant steht dir offen: Du kannst à la carte essen, wann du möchtest, zu den Öffnungszeiten.'),
  _D('Orari', 'Hours', 'Öffnungszeiten'), _D('Da sapere', 'Good to know', 'Gut zu wissen'),
  // navetta
  _D('Servizio navetta', 'Shuttle service', 'Shuttle-Service'), _D('Da quale spiaggia?', 'Which beach?', 'Von welchem Strand?'), _D('Tocca la spiaggia dove ti devono venire a prendere.', 'Tap the beach where we should pick you up.', 'Tippe auf den Strand, an dem wir dich abholen sollen.'),
  _D("Scegli l'autista", 'Choose your driver', 'Wähle deinen Fahrer'), _D("Tocca la foto dell'autista che ti verrà a prendere.", 'Tap the photo of the driver who will pick you up.', 'Tippe auf das Foto des Fahrers, der dich abholt.'),
  _D('Quante persone siete?', 'How many people?', 'Wie viele Personen seid ihr?'), _D('Seleziona un orario', 'Select a time', 'Wähle eine Uhrzeit'), _D("Tocca l'orario in cui vuoi essere riaccompagnato.", 'Tap the time you want to be taken back.', 'Tippe auf die Uhrzeit der Rückfahrt.'),
  _D('Conferma la prenotazione', 'Confirm booking', 'Buchung bestätigen'), _D('Hai già prenotato', 'You have already booked', 'Du hast bereits gebucht'),
  _D("Il tuo numero di telefono, così l'autista può chiamarti", 'Your phone number, so the driver can call you', 'Deine Telefonnummer, damit der Fahrer dich anrufen kann'),
  _D('Le tue corse di oggi', "Today's rides", 'Deine heutigen Fahrten'), _D('Corse precedenti', 'Previous rides', 'Frühere Fahrten'), _D('Cambia orario', 'Change time', 'Zeit ändern'), _D('Annulla la corsa', 'Cancel the ride', 'Fahrt stornieren'),
  _D('No, la tengo', 'No, keep it', 'Nein, behalten'), _D('Sì, annulla', 'Yes, cancel', 'Ja, stornieren'), _D('Dove farti trovare', 'Where to meet us', 'Wo wir dich abholen'), _D('Apri la mappa e raggiungi il punto', 'Open the map and go to the spot', 'Karte öffnen und zum Treffpunkt gehen'),
  _D('Orario non disponibile', 'Time not available', 'Uhrzeit nicht verfügbar'), _D('Orario non valido', 'Invalid time', 'Ungültige Uhrzeit'),
  _D('La spiaggia della tua prenotazione. Puoi sceglierne un\'altra.', 'The beach on your booking. You can choose another one.', 'Der Strand deiner Buchung. Du kannst einen anderen wählen.'),
  _D("Questa corsa è già stata chiusa.", 'This ride has already been closed.', 'Diese Fahrt wurde bereits geschlossen.'), _D('Annullamento non riuscito. Riprova.', 'Cancellation failed. Try again.', 'Stornierung fehlgeschlagen. Bitte erneut versuchen.'), _D('Modifica non riuscita. Riprova.', 'Change failed. Try again.', 'Änderung fehlgeschlagen. Bitte erneut versuchen.'),
  _D('Questo orario è appena stato prenotato da un altro ospite. Scegline un altro.', 'This time has just been booked by another guest. Choose another.', 'Diese Uhrzeit wurde gerade von einem anderen Gast gebucht. Wähle eine andere.'),
  _D("Hai già una richiesta a quell'orario.", 'You already have a request at that time.', 'Du hast zu dieser Zeit bereits eine Anfrage.'), _D('Scegli un orario tra quelli disponibili.', 'Choose one of the available times.', 'Wähle eine der verfügbaren Uhrzeiten.'),
  _D("Su quell'orario non c'è posto per tutto il gruppo. Scegli un altro orario.", 'There is no room for the whole group at that time. Choose another time.', 'Zu dieser Zeit ist nicht genug Platz für die ganze Gruppe. Wähle eine andere Uhrzeit.'),
  _D('Questa corsa non si può più modificare.', 'This ride can no longer be changed.', 'Diese Fahrt kann nicht mehr geändert werden.'),
  // conto / prenotazione
  _D('La tua prenotazione', 'Your booking', 'Deine Buchung'), _D('Il tuo conto', 'Your bill', 'Deine Rechnung'), _D('Alloggio', 'Accommodation', 'Unterkunft'), _D('Check-in', 'Check-in', 'Check-in'), _D('Check-out', 'Check-out', 'Check-out'), _D('Persone', 'Guests', 'Personen'),
  _D('Totale soggiorno', 'Stay total', 'Gesamtbetrag'), _D('Il conto non è ancora disponibile.', 'The bill is not available yet.', 'Die Rechnung ist noch nicht verfügbar.'), _D('· pagato', '· paid', '· bezahlt'), _D('(acconto)', '(deposit)', '(Anzahlung)'), _D('Saldato', 'Settled', 'Beglichen'), _D('Da pagare', 'To pay', 'Zu zahlen'), _D('✓ Nessun residuo', '✓ Nothing left to pay', '✓ Kein Restbetrag'),
  // info utili
  _D('Orari e regole del villaggio', 'Village hours and rules', 'Öffnungszeiten und Regeln des Dorfes'), _D('Check-in e check-out', 'Check-in and check-out', 'Check-in und Check-out'),
  _D("Check-in dalle 9:00 alle 21:00 (alloggio pronto dalle ore 16:00). Check-out entro le ore 10:00: prima di lasciare l'alloggio telefona in reception per concordare il controllo finale e lascia la biancheria usata in una federa fuori dalla porta.", 'Check-in from 9:00 to 21:00 (accommodation ready from 16:00). Check-out by 10:00: before leaving, call reception to arrange the final check and leave the used linen in a pillowcase outside the door.', 'Check-in von 9:00 bis 21:00 Uhr (Unterkunft ab 16:00 Uhr bezugsfertig). Check-out bis 10:00 Uhr: Rufe vor dem Verlassen die Rezeption an, um die Endkontrolle zu vereinbaren, und lege die gebrauchte Wäsche in einem Kissenbezug vor die Tür.'),
  _D('Orario del silenzio', 'Quiet hours', 'Ruhezeiten'), _D('Dalle 14:00 alle 16:00 e dalle 24:00 alle 7:00.', 'From 14:00 to 16:00 and from 24:00 to 7:00.', 'Von 14:00 bis 16:00 Uhr und von 24:00 bis 7:00 Uhr.'),
  _D('Wi-Fi', 'Wi-Fi', 'WLAN'), _D('Gratuito nelle aree comuni (Reception, Bar, Piscina, Ristorante, Teatro). Rete', 'Free in the common areas (Reception, Bar, Pool, Restaurant, Theatre). Network', 'Kostenlos in den Gemeinschaftsbereichen (Rezeption, Bar, Pool, Restaurant, Theater). Netz'), _D(', password', ', password', ', Passwort'),
  _D('. Negli alloggi la copertura non è garantita al 100%.', '. Coverage inside the accommodations is not guaranteed.', '. In den Unterkünften ist der Empfang nicht zu 100 % gewährleistet.'),
  _D('Raccolta differenziata', 'Recycling', 'Mülltrennung'), _D('Rispetta la raccolta differenziata del villaggio.', 'Please follow the village recycling rules.', 'Bitte beachte die Mülltrennung im Dorf.'), _D('Scarica la guida', 'Download the guide', 'Leitfaden herunterladen'),
  _D('Spiagge convenzionate', 'Partner beaches', 'Partnerstrände'), _D(': spiaggia di sassi, cani ammessi.', ': pebble beach, dogs allowed.', ': Kieselstrand, Hunde erlaubt.'), _D(': spiaggia di sabbia riportata, cani non ammessi.', ': imported-sand beach, dogs not allowed.', ': aufgeschütteter Sandstrand, Hunde nicht erlaubt.'),
  _D('Si prenotano in reception: dotazione standard 1 ombrellone e 2 lettini (lettini extra da richiedere e pagare direttamente in spiaggia).', 'Book at reception: standard set is 1 umbrella and 2 sunbeds (extra sunbeds to be requested and paid directly at the beach).', 'Reservierung an der Rezeption: Standard sind 1 Sonnenschirm und 2 Liegen (zusätzliche Liegen direkt am Strand anfragen und bezahlen).'),
  _D('Regolamento del villaggio', 'Village rules', 'Dorfordnung'),
  _D('Due vasche: una per adulti, profonda fino a 180 cm, e una per bambini con acquascivoli, alta 90 cm. Wi-Fi gratuito in zona piscina.', 'Two pools: one for adults, up to 180 cm deep, and one for children with water slides, 90 cm deep. Free Wi-Fi by the pool.', 'Zwei Becken: eines für Erwachsene mit bis zu 180 cm Tiefe und eines für Kinder mit Wasserrutschen, 90 cm tief. Kostenloses WLAN am Pool.'),
  _D('Orari di apertura', 'Opening hours', 'Öffnungszeiten'), _D('Mattina: 9:00 – 13:00', 'Morning: 9:00 – 13:00', 'Vormittag: 9:00 – 13:00'), _D('Pomeriggio: 15:30 – 19:00', 'Afternoon: 15:30 – 19:00', 'Nachmittag: 15:30 – 19:00'),
  _D("Fuori da questi orari l'accesso a vasca e solarium non è consentito.", 'Outside these hours, access to the pool and sundeck is not allowed.', 'Außerhalb dieser Zeiten ist der Zugang zu Becken und Sonnenterrasse nicht gestattet.'),
  _D('Chiosco bar a bordo vasca', 'Poolside snack bar', 'Poolbar'), _D("Aperto per colazione, gelati e cocktail senza allontanarti dall'acqua.", 'Open for breakfast, ice cream and cocktails without leaving the water.', 'Geöffnet für Frühstück, Eis und Cocktails, ohne das Wasser zu verlassen.'),
  _D('Pet Friendly', 'Pet friendly', 'Haustierfreundlich'), _D("I cani di tutte le taglie sono benvenuti! Molti alloggi hanno verande con cancelletto o recintate. All'arrivo il tuo cane riceve un kit di benvenuto.", 'Dogs of all sizes are welcome! Many accommodations have fenced verandas. On arrival your dog receives a welcome kit.', 'Hunde aller Größen sind willkommen! Viele Unterkünfte haben eingezäunte Veranden. Bei der Ankunft erhält dein Hund ein Willkommenspaket.'),
  _D('Servizi dedicati', 'Dedicated services', 'Besondere Angebote'), _D(': area sgambamento recintata, il cane può correre libero senza guinzaglio.', ': fenced exercise area, dogs can run free off the lead.', ': eingezäunter Auslaufbereich, Hunde dürfen frei ohne Leine laufen.'),
  _D(': zona lavaggio per rinfrescare il cane dopo spiaggia o parco.', ': wash area to freshen up your dog after the beach or park.', ': Waschbereich, um deinen Hund nach Strand oder Park zu erfrischen.'),
  _D('Regole', 'Rules', 'Regeln'), _D('Guinzaglio obbligatorio ovunque tranne nel Dog Park.', 'Lead required everywhere except in the Dog Park.', 'Leinenpflicht überall außer im Dog Park.'), _D('Cani non ammessi in piscina e nella sala interna del ristorante.', 'Dogs not allowed in the pool or the indoor restaurant room.', 'Hunde sind im Pool und im Innenraum des Restaurants nicht erlaubt.'),
  _D('Cani non ammessi nella sala interna del ristorante.', 'Dogs not allowed in the indoor restaurant room.', 'Hunde sind im Innenraum des Restaurants nicht erlaubt.'), _D('Porta sempre i sacchetti igienici e usa i cestini del villaggio.', 'Always carry waste bags and use the village bins.', 'Führe immer Kotbeutel mit und nutze die Abfallbehälter im Dorf.'),
  _D('Veterinario convenzionato', 'Partner vet', 'Partner-Tierarzt'), _D('Shop convenzionato', 'Partner pet shop', 'Partner-Tiershop'), _D('Market', 'Market', 'Markt'), _D('Spesa a domicilio', 'Grocery delivery', 'Lieferservice'),
  _D('Nel Market & Bazar del villaggio trovi alimentari, bevande, prodotti per il mare e generi di prima necessità.', 'In the village Market & Bazaar you will find groceries, drinks, beach items and basic necessities.', 'Im Markt & Bazar des Dorfes findest du Lebensmittel, Getränke, Strandartikel und Dinge des täglichen Bedarfs.'),
  _D("Ordina online e paga con carta: ti portiamo la spesa direttamente in alloggio, all'orario stabilito.", 'Order online and pay by card: we bring the groceries straight to your accommodation at the agreed time.', 'Online bestellen und mit Karte bezahlen: Wir bringen dir die Einkäufe zur vereinbarten Zeit direkt in die Unterkunft.'), _D('Ordina online', 'Order online', 'Online bestellen'),
  _D('Lavanderia', 'Laundry', 'Wäscherei'), _D("All'interno del villaggio trovi un'area lavanderia con lavatrici e asciugatrici a gettoni.", 'Inside the village there is a laundry area with coin-operated washers and dryers.', 'Im Dorf gibt es einen Waschbereich mit Münz-Waschmaschinen und -Trocknern.'), _D('Per la posizione esatta consulta la', 'For the exact location see the', 'Die genaue Lage findest du auf dem'), _D('mappa del villaggio', 'village map', 'Dorfplan'),
  _D('Farmacia e Guardia medica', 'Pharmacy and medical service', 'Apotheke und Notarzt'), _D('Negozi e servizi vicini', 'Nearby shops and services', 'Geschäfte und Dienste in der Nähe'), _D('Salute e benessere', 'Health and wellness', 'Gesundheit und Wellness'), _D('Sportelli ATM', 'ATMs', 'Geldautomaten'), _D('Carburante e ricarica auto', 'Fuel and EV charging', 'Tankstellen und E-Ladesäulen'), _D('Supermercati', 'Supermarkets', 'Supermärkte'), _D('Indicazioni', 'Directions', 'Wegbeschreibung'), _D('Tabaccheria', 'Tobacconist', 'Tabakladen'),
  _D('un pasto', 'a meal', 'eine Mahlzeit'), _D('il pranzo', 'lunch', 'das Mittagessen'), _D('la cena', 'dinner', 'das Abendessen'), _D(' e ', ' and ', ' und '), _D('Pasto', 'Meal', 'Mahlzeit'),
  _D('Ordine di oggi incompleto', "Today's order is incomplete", 'Die heutige Bestellung ist unvollständig'), _D('Ordine di domani incompleto', "Tomorrow's order is incomplete", 'Die morgige Bestellung ist unvollständig'),
  _D('Ti manca ancora: {x}. Si ordina entro le 8:30.', 'Still missing: {x}. Orders close at 8:30.', 'Es fehlt noch: {x}. Bestellung bis 8:30 Uhr.'), _D('Ti manca ancora: {x} di domani. Si ordina entro le 8:30 di domani mattina.', "Still missing: {x} for tomorrow. Order by 8:30 tomorrow morning.", 'Es fehlt noch: {x} für morgen. Bestellung bis morgen früh 8:30 Uhr.'),
  _D("Completa l'ordine", 'Complete the order', 'Bestellung vervollständigen'), _D('Trova subito ogni punto del villaggio', 'Find every spot in the village', 'Finde jeden Ort im Dorf'),
  _D('Domani si riparte con il programma', 'The programme starts again tomorrow', 'Morgen geht das Programm weiter'), _D('Per qualsiasi bisogno chiedi in reception: siamo a tua disposizione.', 'For anything you need, ask at reception: we are at your disposal.', 'Bei jedem Anliegen frag an der Rezeption: Wir sind für dich da.'),
  _D('Ti manca ancora: {x}. Lo staff ha riaperto gli ordini di oggi.', 'Still missing: {x}. The staff has reopened today\'s orders.', 'Es fehlt noch: {x}. Das Personal hat die heutigen Bestellungen wieder geöffnet.'),
  _D('Il tuo soggiorno', 'Your stay', 'Dein Aufenthalt'), _D('Ti aspettiamo domani!', 'See you tomorrow!', 'Wir erwarten dich morgen!'), _D('Ti aspettiamo tra {n} giorni', 'See you in {n} days', 'Wir erwarten dich in {n} Tagen'),
  _D('Arrivo {d}. Intanto qui trovi le informazioni utili per prepararti.', 'Arrival {d}. In the meantime, here is useful information to get ready.', 'Anreise {d}. Hier findest du schon nützliche Infos zur Vorbereitung.'), _D('Tutti i dettagli', 'All the details', 'Alle Details'),
  _D('Grazie per aver scelto Garden River', 'Thank you for choosing Garden River', 'Danke, dass du dich für Garden River entschieden hast'), _D('Grazie, {n}!', 'Thank you, {n}!', 'Danke, {n}!'),
  _D('È stato un piacere averti con noi. Speriamo di rivederti presto al Garden River!', 'It was a pleasure having you with us. We hope to see you again soon at Garden River!', 'Es war uns eine Freude, dich bei uns zu haben. Wir hoffen, dich bald wiederzusehen!'),
  _D('Se ti è piaciuto, una recensione ci aiuta tantissimo: tocca le stelle.', 'If you enjoyed it, a review helps us enormously: tap the stars.', 'Wenn es dir gefallen hat, hilft uns eine Bewertung sehr: Tippe auf die Sterne.'),
  _D('Raccontaci come è andata', 'Tell us how it went', 'Erzähl uns, wie es war'), _D('Se ti è piaciuto il soggiorno, una recensione ci aiuta tantissimo.', 'If you enjoyed your stay, a review helps us enormously.', 'Wenn dir dein Aufenthalt gefallen hat, hilft uns eine Bewertung sehr.'),
  _D('Recensisci su Google', 'Review us on Google', 'Auf Google bewerten'), _D('Recensisci su Tripadvisor', 'Review us on Tripadvisor', 'Auf Tripadvisor bewerten'),
  _D('Non riesco a caricare', "Can't load", 'Kann nicht geladen werden'),
  // banner informazioni check-in
  _D('Prima di partire', 'Before you leave', 'Vor der Anreise'),
  _D('Informazioni utili per il tuo arrivo', 'Useful information for your arrival', 'Nützliche Informationen für Ihre Anreise'),
  _D('Check-in', 'Check-in', 'Check-in'),
  _D('La consegna dell\'alloggio è prevista a partire dalle ore 16:00 del sabato di arrivo, a partire e non entro: l\'orario di consegna può infatti variare in base ai tempi necessari per la pulizia e la preparazione degli alloggi. Comprendiamo che, soprattutto dopo un lungo viaggio e in presenza di bambini, persone anziane o animali, l\'attesa possa essere scomoda e spiacevole. Purtroppo, però, non possiamo fare altrimenti: si tratta semplicemente dei tempi tecnici necessari per pulire e preparare tutti gli alloggi in arrivo. La nostra squadra di pulizie lavora ininterrottamente per rendere ogni appartamento disponibile il prima possibile, ma è umanamente impossibile riuscire a pulire e preparare tutti gli alloggi nell\'arco di poche ore. Vi ringraziamo per la comprensione e la collaborazione.', 'Accommodation handover is from 4:00 pm on the Saturday of arrival – from, not by: the handover time may vary depending on the time needed to clean and prepare the units. We understand that, especially after a long journey and with children, elderly people or pets, waiting can be uncomfortable and unpleasant. Unfortunately we cannot do otherwise: these are simply the technical times needed to clean and prepare all the arriving units. Our cleaning team works non-stop to make every apartment available as soon as possible, but it is humanly impossible to clean and prepare all the units within a few hours. Thank you for your understanding and cooperation.', 'Die Übergabe der Unterkunft erfolgt ab 16:00 Uhr am Anreisesamstag – ab, nicht bis: Die Übergabezeit kann je nach der für Reinigung und Vorbereitung der Unterkünfte benötigten Zeit variieren. Wir verstehen, dass das Warten, vor allem nach einer langen Reise und mit Kindern, älteren Personen oder Tieren, unbequem und unangenehm sein kann. Leider geht es nicht anders: Es sind schlicht die technischen Zeiten, die zum Reinigen und Vorbereiten aller ankommenden Unterkünfte nötig sind. Unser Reinigungsteam arbeitet ununterbrochen, damit jede Wohnung so schnell wie möglich verfügbar ist, aber es ist menschlich unmöglich, alle Unterkünfte innerhalb weniger Stunden zu reinigen und vorzubereiten. Vielen Dank für Ihr Verständnis und Ihre Mithilfe.'),
  _D('Check-out', 'Check-out', 'Check-out'),
  _D('Ospiti con animali', 'Guests with pets', 'Gäste mit Tieren'),
  _D('Modalità di pagamento', 'Payment methods', 'Zahlungsmöglichkeiten'),
  _D('Contanti', 'Cash', 'Bargeld'),
  _D('Carta di credito', 'Credit card', 'Kreditkarte'),
  _D('Bancomat', 'Debit card (Bancomat)', 'Bankomatkarte (Bancomat)'),
  _D('Pensione completa e mezza pensione', 'Full board and half board', 'Vollpension und Halbpension'),
  _D('Biancheria', 'Linen', 'Bettwäsche'),
  _D('Il tuo arrivo in breve', 'Your arrival at a glance', 'Ihre Anreise im Überblick'),
  _D('dalle 16:00', 'from 4:00 pm', 'ab 16:00 Uhr'),
  _D('entro le 10:00', 'by 10:00 am', 'bis 10:00 Uhr'),
  _D('Pagamenti', 'Payments', 'Zahlung'),
  _D('Contanti, carta, Bancomat', 'Cash, card, Bancomat', 'Bar, Karte, Bancomat'),
  _D('Tocca una voce per leggere i dettagli', 'Tap an item to read the details', 'Tippen Sie auf einen Punkt für Details'),
  _D('L\'alloggio è disponibile dalle 16:00 del giorno di arrivo. L\'orario può variare in base ai tempi di pulizia e preparazione.', 'Your accommodation is available from 4:00 pm on the day of arrival. The time may vary depending on cleaning and preparation.', 'Die Unterkunft ist am Anreisetag ab 16:00 Uhr verfügbar. Die Zeit kann je nach Reinigung und Vorbereitung variieren.'),
  _D('Puoi arrivare anche in tarda mattinata: faremo subito il check-in (documenti, saldo, braccialetti) e potrai usare i servizi del villaggio. L\'alloggio sarà pronto dalle 16:00.', 'You can also arrive in late morning: we will do the check-in right away (documents, payment, wristbands) and you can use the village services. Your accommodation will be ready from 4:00 pm.', 'Sie können auch am späten Vormittag anreisen: Wir machen sofort den Check-in (Dokumente, Zahlung, Armbänder) und Sie können die Services des Dorfes nutzen. Die Unterkunft ist ab 16:00 Uhr bereit.'),
  _D('Lascia l\'alloggio entro le 10:00 e riconsegna i braccialetti.', 'Please vacate the accommodation by 10:00 am and return your wristbands.', 'Bitte verlassen Sie die Unterkunft bis 10:00 Uhr und geben Sie die Armbänder zurück.'),
  _D('Dopo il check-out non è possibile restare nel villaggio né usare i servizi.', 'After check-out you cannot stay in the village or use its services.', 'Nach dem Check-out ist ein Verbleib im Dorf und die Nutzung der Services nicht möglich.'),
  _D('Serve un\'assicurazione che copra i danni causati dal cane a persone o cose.', 'Insurance covering any damage caused by the dog to people or property is required.', 'Es ist eine Versicherung erforderlich, die vom Hund verursachte Schäden an Personen oder Sachen abdeckt.'),
  _D('Con l\'ombrellone nella Dog Beach il cane può stare sotto l\'ombrellone, ma non entrare in acqua.', 'With an umbrella on the Dog Beach, your dog can stay under the umbrella but is not allowed in the water.', 'Mit einem Sonnenschirm am Dog Beach darf der Hund unter dem Schirm bleiben, aber nicht ins Wasser.'),
  _D('Accettiamo:', 'We accept:', 'Wir akzeptieren:'),
  _D('Non accettiamo assegni né bonifici il giorno dell\'arrivo.', 'We do not accept cheques or bank transfers on the day of arrival.', 'Schecks und Überweisungen werden am Anreisetag nicht akzeptiert.'),
  _D('Se hai la pensione completa o la mezza pensione, invia le scelte dei pasti dal link ricevuto su WhatsApp.', 'If you have full or half board, send your meal choices using the link received on WhatsApp.', 'Bei Voll- oder Halbpension senden Sie Ihre Menüauswahl über den auf WhatsApp erhaltenen Link.'),
  _D('Se hai chiesto di mangiare con un\'altra famiglia, arrivate ai pasti allo stesso orario.', 'If you asked to eat with another family, please arrive at meals at the same time.', 'Wenn Sie darum gebeten haben, mit einer anderen Familie zu essen, kommen Sie bitte zur gleichen Zeit zu den Mahlzeiten.'),
  _D('Per i bambini sotto i 3 anni la biancheria non è fornita.', 'Linen is not provided for children under 3.', 'Für Kinder unter 3 Jahren wird keine Bettwäsche bereitgestellt.'),
  _D('Consegniamo kit di lenzuola e asciugamani imbustati, ma i letti non li facciamo.', 'We provide bagged sheet and towel kits, but we do not make the beds.', 'Wir stellen verpackte Sets mit Bettlaken und Handtüchern bereit, die Betten beziehen wir nicht.'),
  _D('Per qualsiasi dubbio siamo a disposizione. Buon soggiorno!', 'We are here for any question. Enjoy your stay!', 'Bei Fragen sind wir gerne für Sie da. Einen angenehmen Aufenthalt!'),
  _D('Ti manca ancora: {x}. Puoi ordinare fino alle 8:30 del giorno di arrivo.', 'You still need to choose: {x}. You can order until 8:30 am on the arrival day.', 'Es fehlt noch: {x}. Sie können bis 8:30 Uhr am Anreisetag bestellen.'),
  _D('Scegli i pasti', 'Choose meals', 'Mahlzeiten wählen'),
  _D('Conferma ordine dell\'arrivo', 'Confirm arrival-day order', 'Bestellung für den Anreisetag bestätigen'),
  _D('Ordine dell\'arrivo', 'Arrival-day order', 'Bestellung für den Anreisetag'),
  _D('Scegli i tuoi pasti', 'Choose your meals', 'Wählen Sie Ihre Mahlzeiten'),
  _D('Ti manca ancora: {x} del giorno di arrivo. Puoi ordinare fino alle 8:30 di quel giorno.', 'You still need to choose: {x} for the arrival day. You can order until 8:30 am that day.', 'Es fehlt noch: {x} für den Anreisetag. Sie können bis 8:30 Uhr an diesem Tag bestellen.'),
  _D('Ti manca ancora: {x} del giorno dopo l\'arrivo. Puoi ordinare fino alle 8:30 di quel giorno.', 'You still need to choose: {x} for the day after arrival. You can order until 8:30 am that day.', 'Es fehlt noch: {x} für den Tag nach der Anreise. Sie können bis 8:30 Uhr an diesem Tag bestellen.'),
  _D('Conferma ordine del giorno dopo', 'Confirm next-day order', 'Bestellung für den Folgetag bestätigen'),
  _D('Ordine del giorno dopo', 'Next-day order', 'Bestellung für den Folgetag'),
  _D('Scegli i pasti del giorno dopo l\'arrivo', 'Choose your meals for the day after arrival', 'Wählen Sie Ihre Mahlzeiten für den Tag nach der Anreise'),
  _D('Puoi già ordinare anche il giorno dopo l\'arrivo, entro le 8:30 di quella mattina.', 'You can also already order for the day after arrival, by 8:30 am that morning.', 'Sie können auch schon für den Tag nach der Anreise bestellen, bis 8:30 Uhr an diesem Morgen.'),
  _D('Ordine del giorno dopo', 'Next-day order', 'Bestellung für den Folgetag'),
  _D('Conferma ordine del giorno dopo', 'Confirm next-day order', 'Bestellung für den Folgetag bestätigen'),
];
const DIZ = { en: {}, de: {} };
_LISTA.forEach(e => { DIZ.en[e.it] = e.en; DIZ.de[e.it] = e.de; });
const _MESI = { it: ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'], en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'], de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'] };
const _GG = ['Domenica', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato'];
const _pl = (n, a, b) => n === '1' ? a : b;
const PATT = [
  [/^(Oggi|Domani|Arrivo) · (\S+) (\d+) (\S+)$/, (m, L) => `${({ Oggi: { en: 'Today', de: 'Heute' }, Domani: { en: 'Tomorrow', de: 'Morgen' }, Arrivo: { en: 'Arrival', de: 'Anreise' } })[m[1]][L]} · ${DIZ[L][m[2]] || m[2]} ${m[3]} ${(_MESI[L][_MESI.it.indexOf(m[4])]) || m[4]}`],
  [/^La serata di (\S+)$/, (m, L) => ({ en: `${DIZ.en[m[1][0].toUpperCase() + m[1].slice(1)] || m[1]}'s evening`, de: `Der Abend am ${DIZ.de[m[1][0].toUpperCase() + m[1].slice(1)] || m[1]}` })[L]],
  [/^(\d+) attività in programma$/, (m, L) => ({ en: `${m[1]} activities planned`, de: `${m[1]} Aktivitäten geplant` })[L]],
  [/^alle (\S+)$/, (m, L) => ({ en: `at ${m[1]}`, de: `um ${m[1]}` })[L]],
  [/^Ore (\S+)(?: · (.+))?$/, (m, L) => ({ en: `${m[1]}${m[2] ? ' · ' + m[2] : ''}`, de: `${m[1]} Uhr${m[2] ? ' · ' + m[2] : ''}` })[L]],
  [/^Stasera · ore (\S+)$/, (m, L) => ({ en: `Tonight · ${m[1]}`, de: `Heute Abend · ${m[1]} Uhr` })[L]],
  [/^(\d+) richiest[ae] in corso$/, (m, L) => ({ en: `${m[1]} request${m[1] === '1' ? '' : 's'} in progress`, de: `${m[1]} Anfrage${m[1] === '1' ? '' : 'n'} in Bearbeitung` })[L]],
  [/^Vuoi annullare la corsa delle$/, (m, L) => ({ en: 'Cancel the ride at', de: 'Fahrt stornieren um' })[L]],
  [/^Autista: (.+)$/, (m, L) => ({ en: `Driver: ${m[1]}`, de: `Fahrer: ${m[1]}` })[L]],
  [/^Orario cambiato \(era (.+)\)$/, (m, L) => ({ en: `Time changed (was ${m[1]})`, de: `Zeit geändert (war ${m[1]})` })[L]],
  [/^Nuovo orario \(almeno (\d+) minuti da adesso\)$/, (m, L) => ({ en: `New time (at least ${m[1]} minutes from now)`, de: `Neue Zeit (mindestens ${m[1]} Minuten ab jetzt)` })[L]],
  [/^(.*) · Ombrellone (.+)$/, (m, L) => `${m[1]} · ${({ en: 'Umbrella', de: 'Sonnenschirm' })[L]} ${m[2]}`],
  [/^Tocca il numero di persone che tornano con la navetta \(compreso te\)\. Il pulmino ha (\d+) posti\.$/, (m, L) => ({ en: `Tap the number of people coming back on the shuttle (including you). The minibus has ${m[1]} seats.`, de: `Tippe auf die Anzahl der Personen, die mit dem Shuttle zurückfahren (dich eingeschlossen). Der Bus hat ${m[1]} Plätze.` })[L]],
  [/^Restano (\d+) (persona|persone) della tua prenotazione senza corsa\. Tocca quante tornano con questa navetta\.$/, (m, L) => ({ en: `${m[1]} ${m[1] === '1' ? 'person' : 'people'} from your booking still without a ride. Tap how many are coming back with this shuttle.`, de: `${m[1]} ${m[1] === '1' ? 'Person' : 'Personen'} deiner Buchung noch ohne Fahrt. Tippe, wie viele mit diesem Shuttle zurückfahren.` })[L]],
  [/^Non si può più annullare: mancano meno di (\d+) minuti alla corsa\. Chiama la reception\.$/, (m, L) => ({ en: `It can no longer be cancelled: less than ${m[1]} minutes to the ride. Call reception.`, de: `Stornierung nicht mehr möglich: weniger als ${m[1]} Minuten bis zur Fahrt. Ruf die Rezeption an.` })[L]],
  [/^Non si può più cambiare: mancano meno di (\d+) minuti alla corsa\.$/, (m, L) => ({ en: `It can no longer be changed: less than ${m[1]} minutes to the ride.`, de: `Änderung nicht mehr möglich: weniger als ${m[1]} Minuten bis zur Fahrt.` })[L]],
  [/^Non ci sono più orari disponibili adesso \(servono almeno (\d+) minuti di preavviso\)\. Riprova tra poco\.$/, (m, L) => ({ en: `No more times available right now (at least ${m[1]} minutes notice needed). Try again shortly.`, de: `Im Moment keine Zeiten mehr verfügbar (mindestens ${m[1]} Minuten Vorlauf nötig). Versuche es gleich noch einmal.` })[L]],
  [/^(.+) non può portare il gruppo a quest'ora$/, (m, L) => ({ en: `${m[1]} can't take the group at this time`, de: `${m[1]} kann die Gruppe zu dieser Zeit nicht fahren` })[L]],
  [/^(\d+) ([a-zA-Zà-ÿ]+)$/, null],
];
// Rimuove gli schemi segnaposto senza funzione
for (let i = PATT.length - 1; i >= 0; i--) if (!PATT[i][1]) PATT.splice(i, 1);

function _trTesto(s, L) {
  const m = s.match(/^(\s*)([\s\S]*?)(\s*)$/); const core = m[2];
  if (!core) return null;
  let r = DIZ[L][core];
  if (r === undefined) {
    for (const [re, fn] of PATT) { const x = core.match(re); if (x) { r = fn(x, L); break; } }
  }
  return r === undefined ? null : m[1] + r + m[3];
}
let _trBusy = false;
function traduciDom(root) {
  if (LANG === 'it' || !root || _trBusy) return;
  _trBusy = true;
  try {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => /^(SCRIPT|STYLE)$/.test(n.parentNode.nodeName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    const nodi = []; while (w.nextNode()) nodi.push(w.currentNode);
    nodi.forEach(n => { const r = _trTesto(n.nodeValue, LANG); if (r !== null && r !== n.nodeValue) n.nodeValue = r; });
    (root.querySelectorAll ? root.querySelectorAll('[placeholder],[aria-label],[title],[alt]') : []).forEach(el => {
      ['placeholder', 'aria-label', 'title', 'alt'].forEach(a => { const v = el.getAttribute(a); if (v) { const r = _trTesto(v, LANG); if (r !== null) el.setAttribute(a, r); } });
    });
  } finally { _trBusy = false; }
}
function avviaTraduzione() {
  document.documentElement.lang = LANG;
  const lb = document.getElementById('lang-btn'); if (lb) lb.textContent = LANG.toUpperCase();
  if (LANG === 'it') return;
  let tm = null;
  new MutationObserver(() => { clearTimeout(tm); tm = setTimeout(() => traduciDom(document.body), 30); }).observe(document.body, { childList: true, subtree: true, characterData: true });
  traduciDom(document.body);
}
function cambiaLingua(l) { try { localStorage.setItem('gr_lang', l); } catch (e) {} location.reload(); }
function menuLingua(ev) {
  ev.stopPropagation();
  const old = document.getElementById('lang-menu'); if (old) { old.remove(); return; }
  const b = ev.currentTarget, r = b.getBoundingClientRect(), m = document.createElement('div');
  m.id = 'lang-menu'; m.className = 'lang-menu'; m.style.top = (r.bottom + window.scrollY + 6) + 'px'; m.style.right = Math.max(8, document.documentElement.clientWidth - r.right) + 'px';
  m.innerHTML = [['it', 'Italiano'], ['en', 'English'], ['de', 'Deutsch']].map(([k, n]) => `<button type="button" class="${k === LANG ? 'on' : ''}" onclick="cambiaLingua('${k}')">${n}</button>`).join('');
  document.body.appendChild(m);
  setTimeout(() => document.addEventListener('click', () => { const x = document.getElementById('lang-menu'); if (x) x.remove(); }, { once: true }), 0);
}
