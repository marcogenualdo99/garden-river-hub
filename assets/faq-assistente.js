/* ══════════════════════════════════════════════════════════════════════════
   GARDEN RIVER · ASSISTENTE FAQ STRUTTURA (home page)
   Chat locale, nessuna chiamata esterna: risponde confrontando le parole del
   testo digitato con le parole chiave di FAQ_DATA e mostra la risposta
   migliore. Contenuti presi da FAQ-Garden-River-agg.pdf (aggiornare questo
   file quando cambiano orari, prezzi o regole della struttura).
   "chip: true" = mostrata come scorciatoia veloce in alto nel pannello.
   ═══════════════════════════════════════════════════════════════════════ */

const FAQ_DATA = [
  {
    id: 'apertura', titolo: 'Periodo apertura', chip: false,
    parole: ['apertura', 'quando apre', 'periodo apertura', 'stagione', 'quando chiude', 'fino a quando aperto'],
    risposta: '📅 Nel 2027 il Garden River è aperto dal 29 maggio all’11 settembre.'
  },
  {
    id: 'checkin', titolo: 'Check-in', chip: true,
    parole: ['check in', 'checkin', 'arrivo', 'arrivi', 'a che ora arrivo', 'orario arrivo', 'quando posso arrivare'],
    risposta: '🛎️ Si può arrivare già in tarda mattinata: dopo registrazione e saldo si ricevono i braccialetti e si possono usare subito i servizi del villaggio. L’alloggio è garantito a partire dalle 16:00.'
  },
  {
    id: 'checkout', titolo: 'Check-out', chip: true,
    parole: ['check out', 'checkout', 'partenza', 'orario partenza', 'a che ora lascio'],
    risposta: '🧳 Il check-out è entro le 10:00 del giorno di partenza. Prima di lasciare l’alloggio va avvisata la reception, che manda un incaricato per il controllo.'
  },
  {
    id: 'reception', titolo: 'Reception', chip: true,
    parole: ['reception', 'ufficio', 'orari reception', 'telefono', 'numero', 'contatti', 'assistenza', 'arrivo tardi', 'reception chiusa'],
    risposta: '📞 La reception è aperta dalle 8:00 alle 22:00 — tel. +39 0734 932686, WhatsApp +39 366 824 4322. Chi arriva dopo le 22:00 viene fatto entrare dalla sorveglianza notturna; le procedure di check-in si completano il giorno dopo.'
  },
  {
    id: 'documenti', titolo: 'Documenti check-in', chip: false,
    parole: ['documenti', 'carta identita', 'check in online', 'documento'],
    risposta: '🪪 Il check-in si può fare online tramite il sistema di prenotazione. In reception basta un documento d’identità del capofamiglia e le generalità di tutti i componenti del gruppo.'
  },
  {
    id: 'braccialetto', titolo: 'Braccialetto', chip: false,
    parole: ['braccialetto', 'braccialetti'],
    risposta: '📿 Il braccialetto è obbligatorio per tutto il soggiorno: serve a riconoscere chi alloggia nel villaggio.'
  },
  {
    id: 'ospiti-esterni', titolo: 'Visite di amici/parenti', chip: false,
    parole: ['amici a trovare', 'parenti a trovare', 'ospiti esterni', 'visite', 'visitatori'],
    risposta: '👋 Amici e parenti possono venire in visita, ma va chiesto prima alla struttura: gli ingressi esterni sono gestiti in base all’affluenza per mantenere il villaggio vivibile.'
  },
  {
    id: 'parcheggio', titolo: 'Parcheggio', chip: false,
    parole: ['parcheggio', 'parcheggiare', 'dove metto auto', 'posto auto'],
    risposta: '🚗 Zone parcheggio interne vicine ai blocchi degli alloggi. All’arrivo si può avvicinare l’auto per scaricare i bagagli, poi va lasciata in parcheggio: non si può tenerla accanto all’alloggio o sulla piazzola.'
  },
  {
    id: 'cancello-auto', titolo: 'Orari cancello auto', chip: false,
    parole: ['cancello', 'orario cancello', 'fino a che ora entro in auto', 'targhe', 'lettura targhe'],
    risposta: '🚧 Il cancello auto chiude alle 22 a giugno, alle 23 a luglio e a mezzanotte ad agosto. Dopo l’orario si lascia l’auto nel parcheggio esterno e si entra a piedi dal cancello pedonale (aperto 24h). Per la lettura targhe va registrata prima la targa del veicolo.'
  },
  {
    id: 'silenzio', titolo: 'Orari di silenzio', chip: false,
    parole: ['silenzio', 'orari di silenzio', 'riposo'],
    risposta: '🤫 Orari di silenzio: dalle 14:00 alle 16:00 e da mezzanotte alle 7:00.'
  },
  {
    id: 'rifiuti', titolo: 'Raccolta rifiuti', chip: false,
    parole: ['rifiuti', 'spazzatura', 'differenziata', 'isola ecologica'],
    risposta: '♻️ C’è un’isola ecologica nel villaggio con i bidoni per la raccolta differenziata.'
  },
  {
    id: 'alloggi', titolo: 'Tipologie alloggio', chip: true,
    parole: ['alloggi', 'case mobili', 'villini', 'tipologie', 'joy', 'titania', 'riviera', 'blue house', 'villino comfort', 'villino deluxe', 'quanti posti letto'],
    risposta: '🏠 Case mobili e villini in muratura da 4 a 6 posti: Joy (34,5 mq, 5 posti, 2 camere, 2 bagni, 2 bici incluse, no animali), Super Titania (32 mq, 6 posti, 3 camere, microonde, animali ok), Riviera (26 mq, 4 posti, animali ok), Blue House (24 mq, 4 posti, TV a pagamento, animali ok), Villino Comfort (36 mq, 5 posti, 2 unità accessibili a disabili, animali ok), Villino Deluxe (36 mq, 5 posti, giardino recintato, animali ok).'
  },
  {
    id: 'dotazioni', titolo: 'Dotazioni alloggio', chip: false,
    parole: ['dotazioni', 'cucina', 'aria condizionata', 'tv', 'televisione', 'zanzariere', 'microonde'],
    risposta: '🧊 Tutti gli alloggi hanno aria condizionata, angolo cottura attrezzato (per 5 persone) e kit pulizie. TV ovunque tranne Blue House (a pagamento su richiesta). Microonde solo nel Super Titania. Zanzariere ovunque tranne Villini Comfort e Deluxe.'
  },
  {
    id: 'biancheria', titolo: 'Biancheria', chip: true,
    parole: ['biancheria', 'lenzuola', 'asciugamani', 'cambio biancheria'],
    risposta: '🛏️ Lenzuola e asciugamani non sono inclusi: si richiedono a pagamento. Dove previsto, il cambio settimanale è il venerdì (biancheria usata in una federa fuori dall’alloggio).'
  },
  {
    id: 'culla-seggiolone', titolo: 'Culla e seggiolone', chip: false,
    parole: ['culla', 'seggiolone', 'spondine', 'bambino piccolo'],
    risposta: '👶 Culla, seggiolone e spondine per il letto sono disponibili: vanno richiesti al momento della conferma della prenotazione.'
  },
  {
    id: 'persona-in-piu', titolo: 'Persona in più', chip: false,
    parole: ['persona in piu', 'divano letto', 'aggiungere persona'],
    risposta: '➕ In alcuni alloggi si può ospitare una persona in più sul divano letto: conviene segnalarlo già in fase di preventivo.'
  },
  {
    id: 'disabilita', titolo: 'Accessibilità disabili', chip: false,
    parole: ['disabilita', 'disabili', 'accessibile', 'handicap'],
    risposta: '♿ 2 Villini Comfort sono attrezzati per persone con disabilità.'
  },
  {
    id: 'fumo', titolo: 'Fumare', chip: false,
    parole: ['fumare', 'fumo', 'sigarette'],
    risposta: '🚭 Non si può fumare all’interno degli alloggi; è consentito in veranda o sul patio esterno.'
  },
  {
    id: 'barbecue', titolo: 'Barbecue', chip: false,
    parole: ['barbecue', 'griglia'],
    risposta: '🔥 Non ci sono aree barbecue comuni, ma si può fare il barbecue all’esterno del proprio alloggio.'
  },
  {
    id: 'pulizie', titolo: 'Pulizie e check-out', chip: true,
    parole: ['pulizie', 'pulizia finale', 'pulizie giornaliere', 'lasciare alloggio'],
    risposta: '🧹 Gli alloggi vengono puliti solo all’arrivo e alla partenza, non giornalmente. Prima del check-out va lasciato in ordine, senza rifiuti, con stoviglie e piano cottura puliti — in alternativa pulizia finale a 35€ (50€, obbligatoria, se ci sono animali).'
  },
  {
    id: 'lavanderia', titolo: 'Lavatrici', chip: false,
    parole: ['lavatrice', 'lavanderia', 'asciugatrice', 'lavare vestiti'],
    risposta: '🧺 Gli alloggi non hanno lavatrice, ma nel villaggio ci sono lavatrici e asciugatrici a pagamento con carta: 5€ un lavaggio, 2,50€ un’asciugatura (detersivo incluso).'
  },
  {
    id: 'piazzole', titolo: 'Piazzole e camper', chip: true,
    parole: ['piazzola', 'piazzole', 'camper', 'caravan', 'tenda', 'carrello tenda', 'allaccio elettrico', 'camper service'],
    risposta: '⛺ Piazzole in media 64 mq, per lo più ombreggiate, allaccio elettrico fino a 6A. Adatte a camper, caravan, carrelli tenda e tende (per mezzi grandi si prenotano più piazzole). Scarico cassette WC nei bagni comuni, scarico acque camper fuori dal cancello. L’ingresso in piscina NON è incluso per chi sta in piazzola.'
  },
  {
    id: 'piscina', titolo: 'Piscina', chip: true,
    parole: ['piscina', 'vasca', 'nuotare', 'cuffia'],
    risposta: '🏊 Due vasche (adulti fino a 180 cm, bambini da 90 cm), aperta dalle 9:00 alle 13:00 e dalle 15:30 alle 19:00, con assistente bagnanti, lettini e ombrelloni. Cuffia obbligatoria; fuori orario piscina e solarium non sono accessibili.'
  },
  {
    id: 'animazione', titolo: 'Animazione e Mini/Teen Club', chip: true,
    parole: ['animazione', 'mini club', 'teen club', 'baby dance', 'spettacoli'],
    risposta: '🎉 Nel 2027 attiva dal 15 giugno all’11 settembre (formula ridotta a giugno, piena da luglio). Mini Club 4-11 anni, Teen Club 11-17 anni, baby dance ogni sera e spettacoli serali nel teatro all’aperto.'
  },
  {
    id: 'sport', titolo: 'Sport e giochi', chip: false,
    parole: ['beach volley', 'calcetto', 'ping pong', 'calcio balilla', 'parco giochi', 'sport'],
    risposta: '🏐 Campo da beach volley, campo da calcetto, ping pong, calcio balilla e parco giochi per bambini.'
  },
  {
    id: 'bici', titolo: 'Noleggio bici', chip: true,
    parole: ['bici', 'bicicletta', 'biciclette', 'noleggio bici'],
    risposta: '🚲 Si noleggiano in reception: bici piccole, medie e grandi (classiche, non elettriche), con seggiolini anteriori/posteriori su richiesta. Nelle case mobili Joy sono incluse 2 bici. In bici il mare si raggiunge in meno di 10 minuti su pista ciclabile.'
  },
  {
    id: 'wifi', titolo: 'Wi-Fi', chip: true,
    parole: ['wifi', 'wi fi', 'internet', 'rete'],
    risposta: '📶 Il Wi-Fi è gratuito nelle aree comuni: bar, ristorante, piscina e teatro.'
  },
  {
    id: 'ristorante', titolo: 'Ristorante e orari pasti', chip: true,
    parole: ['ristorante', 'colazione', 'pranzo', 'cena', 'menu', 'orari ristorante', 'bar', 'asporto', 'allergie', 'vegetariano', 'vegano', 'glutine'],
    risposta: '🍽️ Colazione 8:00-10:00, pranzo 13:00-14:30, cena 20:00-22:00. Bar piscina 8:00-22:30, bar teatro 21:00-mezzanotte. Cucina di famiglia, menù à la carte o fisso, serata sushi il lunedì, menù bambini e asporto disponibili. Per allergie, intolleranze o menù vegetariano/vegano va avvisata la struttura prima dell’arrivo.'
  },
  {
    id: 'pensione', titolo: 'Mezza pensione / pensione completa', chip: false,
    parole: ['mezza pensione', 'pensione completa', 'pasti inclusi'],
    risposta: '🍲 Mezza pensione e pensione completa prenotabili: ogni pasto include primo, secondo e contorno (carne o pesce) più acqua. Bevande e dolci a parte; i pasti non consumati non si recuperano.'
  },
  {
    id: 'market', titolo: 'Spesa e market', chip: false,
    parole: ['market', 'spesa', 'supermercato', 'garden shop'],
    risposta: '🛒 Non c’è un market interno, ma con il Garden Shop (QR code) si fa la spesa online con consegna in alloggio, si prenota il tavolo al ristorante e si ordina da asporto. Supermercati vicini: D’Italy a Marina di Altidona (800 m) e Conad a Pedaso (1,4 km).'
  },
  {
    id: 'casetta-acqua', titolo: 'Casetta dell’acqua', chip: false,
    parole: ['casetta acqua', 'acqua naturale', 'acqua frizzante'],
    risposta: '💧 La casetta dell’acqua distribuisce acqua naturale e frizzante a 0,20€ al litro; in alloggio ci sono due bottiglie di vetro da riempire (o si usa la propria borraccia).'
  },
  {
    id: 'animali', titolo: 'Animali domestici', chip: true,
    parole: ['animali', 'cane', 'cani', 'gatto', 'pet', 'animale domestico'],
    risposta: '🐾 Il Garden River è pet friendly, senza limiti di taglia: animali ammessi in piazzola e in tutti gli alloggi tranne le case mobili Joy, massimo 2 cani per alloggio. Guinzaglio obbligatorio, servono libretto vaccinazioni e microchip.'
  },
  {
    id: 'servizi-cani', titolo: 'Servizi per cani', chip: false,
    parole: ['area sgambamento', 'toelettatura', 'addestratore cinofilo', 'pettinato'],
    risposta: '🐕 C’è un’area sgambamento recintata e PETtinato (area self-service per bagno e toelettatura). Una volta a settimana un addestratore cinofilo propone dimostrazioni gratuite (Agility, Disc Dog, ricerca tartufo) e lezioni private su richiesta.'
  },
  {
    id: 'cani-regole', titolo: 'Cani: ristorante, piscina, spiaggia', chip: false,
    parole: ['cane ristorante', 'cane piscina', 'cane spiaggia', 'veterinario', 'cane in spiaggia'],
    risposta: '🐕‍🦺 Il cane può stare nella sala esterna del ristorante ma non al coperto, e non può entrare in piscina. In spiaggia è ammesso solo a Puntarena (area dedicata, niente bagno in mare); a Matepaya i cani non sono ammessi. C’è un veterinario nelle vicinanze: la reception dà le indicazioni.'
  },
  {
    id: 'spiaggia', titolo: 'Spiaggia', chip: true,
    parole: ['spiaggia', 'mare', 'navetta', 'ombrellone', 'lettino'],
    risposta: '🏖️ Il mare è a 700 m (spiaggia di sassi, Marina di Altidona) o 1,2 km (spiaggia di sabbia, Pedaso/Matepaya). Navetta gratuita 9:00-13:00 e 15:30-19:00, oppure pista ciclopedonale ombreggiata (meno di 10 min). Servizio spiaggia (1 ombrellone + 2 lettini) prenotabile in reception. Mare Bandiera Blu.'
  },
  {
    id: 'prenotazione', titolo: 'Prenotazione e caparra', chip: true,
    parole: ['prenotazione', 'preventivo', 'caparra', 'acconto', 'come prenoto', 'soggiorno minimo'],
    risposta: '📝 Preventivo al +39 0734 932686, WhatsApp +39 366 824 4322 o dal modulo sul sito. Prenotazione confermata solo con la caparra, da versare entro 2 giorni. Soggiorno minimo 7 notti (sab-sab) a luglio/agosto, più flessibile negli altri mesi.'
  },
  {
    id: 'pagamento', titolo: 'Pagamento e saldo', chip: false,
    parole: ['pagamento', 'saldo', 'bonifico', 'scalapay', 'assegni'],
    risposta: '💳 Il saldo si paga all’arrivo in contanti, bancomat o carta di credito (bonifico solo se accreditato prima dell’arrivo; assegni non accettati). Disponibile anche il pagamento in 3 rate con Scalapay.'
  },
  {
    id: 'cancellazione', titolo: 'Cancellazione e cambio date', chip: false,
    parole: ['cancellazione', 'disdetta', 'rimborso', 'cambio data', 'no show'],
    risposta: '🔁 La caparra non è mai rimborsabile in denaro. Con almeno 30 giorni di preavviso diventa un voucher di pari importo (tranne ad agosto, dove può essere trattenuta senza voucher); con meno di 30 giorni o no-show è dovuto l’intero importo. Cambio data possibile una sola volta per prenotazione, nella stessa stagione.'
  },
  {
    id: 'tassa-soggiorno', titolo: 'Tassa di soggiorno', chip: false,
    parole: ['tassa di soggiorno', 'tassa soggiorno'],
    risposta: '🏛️ La tassa di soggiorno è 1€ al giorno a persona; esenti le persone con disabilità e i loro accompagnatori.'
  },
  {
    id: 'costi-extra', titolo: 'Costi extra e cauzione', chip: false,
    parole: ['costi extra', 'cauzione', 'tessera club'],
    risposta: '✅ Nessun costo extra obbligatorio: tessera club e pulizie iniziali/finali sono incluse (se l’alloggio viene lasciato pulito). Nessuna cauzione richiesta.'
  },
  {
    id: 'offerte', titolo: 'Offerte e sconti', chip: false,
    parole: ['offerte', 'sconti', 'coupon', 'newsletter', 'prenota prima'],
    risposta: '🎁 Chi si iscrive alla newsletter riceve un coupon da 50€ (valido per prenotazioni di almeno 7 notti, non cumulabile). Le promozioni attive, come il Prenota Prima, sono nella pagina Offerte del sito.'
  },
  {
    id: 'all-inclusive', titolo: 'Pacchetto All Inclusive', chip: false,
    parole: ['all inclusive', 'pacchetto all inclusive'],
    risposta: '⭐ L’All Inclusive comprende colazione, pranzo, cena, biancheria da letto/bagno e servizio spiaggia; va richiesto in fase di preventivo. La pensione completa comprende solo i pasti.'
  },
  {
    id: 'come-arrivare', titolo: 'Come arrivare', chip: false,
    parole: ['come arrivare', 'autostrada', 'stazione', 'treno', 'aeroporto', 'indirizzo', 'dove si trova'],
    risposta: '🧭 Via Ottorino Respighi, Marina di Altidona (FM), a 700 m dal mare. Uscita A14 a Pedaso (5 min), stazione più vicina Pedaso (2 km, transfer gratuito su richiesta), aeroporto più vicino Ancona "Raffaello Sanzio".'
  },
  {
    id: 'dintorni', titolo: 'Dintorni da visitare', chip: false,
    parole: ['dintorni', 'visitare', 'escursioni', 'cosa fare vicino'],
    risposta: '🗺️ Torre di Palme, Fermo, il faro di Pedaso, Porto San Giorgio, San Benedetto del Tronto, i borghi di Moresco, Monterubbiano e Ripatransone, e più lontano Loreto, Recanati e i Monti Sibillini. Pesca sportiva al Lago Azzurro.'
  },
  {
    id: 'salute', titolo: 'Guardia medica e ospedale', chip: false,
    parole: ['guardia medica', 'ospedale', 'medico', 'emergenza', 'farmacia'],
    risposta: '🏥 Guardia medica turistica più vicina: Casa della Comunità di Porto San Giorgio, Via Leonardo da Vinci 7 (8:00-20:00 tutti i giorni). Ospedale di riferimento: Ospedale Civile "A. Murri" di Fermo, tel. 0734 625111.'
  },
  {
    id: 'contatti', titolo: 'Contatti struttura', chip: true,
    parole: ['contatti', 'telefono struttura', 'email', 'whatsapp'],
    risposta: '☎️ Tel. +39 0734 932686, WhatsApp +39 366 824 4322, oppure il modulo contatti sul sito.'
  }
];

const FAQ_FALLBACK = 'Non ho una risposta pronta per questa domanda. Prova a riformularla, scegli uno degli argomenti qui sopra, oppure chiedi direttamente in reception.';
const FAQ_GREETING = 'Ciao! Scegli un argomento oppure scrivimi una domanda sulla struttura (check-in, Wi-Fi, piscina, animali, spiaggia…).';

function faqNormalizza(testo) {
  return String(testo || '')
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function faqTokenizza(testo) {
  return faqNormalizza(testo).split(' ').filter(Boolean);
}

// Confronto approssimato per i plurali/coniugazioni italiane più comuni
// (es. "contatti"/"contatta"/"contattare" condividono il prefisso "contat"):
// evita di richiedere la parola esatta digitata dall'operatore.
function faqRadice(parola) {
  return parola.length > 5 ? parola.slice(0, 5) : parola;
}

function faqCerca(domanda) {
  const tokens = faqTokenizza(domanda);
  const radici = tokens.map(faqRadice);
  let migliore = null;
  let punteggioMax = 0;
  FAQ_DATA.forEach(voce => {
    let punteggio = 0;
    voce.parole.forEach(parola => {
      const paroleTokens = faqTokenizza(parola);
      const trovate = paroleTokens.every(pt => {
        const radicePt = faqRadice(pt);
        return tokens.includes(pt) || radici.includes(radicePt);
      });
      if (paroleTokens.length && trovate) punteggio += paroleTokens.length;
    });
    if (punteggio > punteggioMax) { punteggioMax = punteggio; migliore = voce; }
  });
  return migliore;
}

function faqAggiungiMessaggio(ruolo, testo) {
  const wrap = document.getElementById('faq-messages');
  if (!wrap) return;
  const div = document.createElement('div');
  div.className = 'faq-msg ' + (ruolo === 'user' ? 'faq-msg-user' : 'faq-msg-bot');
  div.textContent = testo;
  wrap.appendChild(div);
  const body = document.getElementById('faq-body');
  if (body) body.scrollTop = body.scrollHeight;
}

function faqRenderChips() {
  const wrap = document.getElementById('faq-chips');
  if (!wrap) return;
  wrap.innerHTML = FAQ_DATA.filter(v => v.chip).map(v =>
    `<button type="button" class="faq-chip" onclick="faqChiediArgomento('${v.id}')">${escHtml(v.titolo)}</button>`
  ).join('');
}

function faqChiediArgomento(id) {
  const voce = FAQ_DATA.find(v => v.id === id);
  if (!voce) return;
  faqAggiungiMessaggio('user', voce.titolo);
  faqAggiungiMessaggio('bot', voce.risposta);
}

function sendFaqMessage() {
  const input = document.getElementById('faq-input');
  if (!input) return;
  const testo = input.value.trim();
  if (!testo) return;
  faqAggiungiMessaggio('user', testo);
  input.value = '';
  const voce = faqCerca(testo);
  faqAggiungiMessaggio('bot', voce ? voce.risposta : FAQ_FALLBACK);
}

function openFaqAssistant() {
  const overlay = document.getElementById('faq-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden');
  if (!document.getElementById('faq-chips').innerHTML) faqRenderChips();
  const messages = document.getElementById('faq-messages');
  if (messages && !messages.children.length) faqAggiungiMessaggio('bot', FAQ_GREETING);
  setTimeout(() => { const i = document.getElementById('faq-input'); if (i) i.focus(); }, 50);
}

function closeFaqAssistant() {
  const overlay = document.getElementById('faq-overlay');
  if (overlay) overlay.classList.add('hidden');
}
