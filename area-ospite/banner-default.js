/* Banner a fasce orarie predefiniti (Area ospite). Compaiono in Gestione area ospite come punto di partenza: gli ospiti li vedono solo dopo il salvataggio. */
const BANNER_FASCE_DEF = {
 "attivo": true,
 "secondi": 6,
 "banner": [
  {
   "id": "colazione",
   "attivo": true,
   "titolo": {
    "it": "Buongiorno! Colazione al bar",
    "en": "Good morning! Breakfast at the bar",
    "de": "Guten Morgen! Frühstück an der Bar"
   },
   "testo": {
    "it": "Cornetti caldi, caffè e cappuccino per iniziare bene la giornata.",
    "en": "Warm croissants, coffee and cappuccino to start the day.",
    "de": "Warme Croissants, Kaffee und Cappuccino zum Tagesstart."
   },
   "dalle": "07:30",
   "alle": "10:30",
   "posizione": "alto",
   "pubblico": "dentro",
   "tema": "arancio",
   "azione": {
    "tipo": "servizio",
    "valore": "ristorazione",
    "etichetta": {
     "it": "Vedi il menu",
     "en": "See the menu",
     "de": "Zum Menü"
    }
   },
   "grafica": ""
  },
  {
   "id": "pane",
   "attivo": true,
   "titolo": {
    "it": "Pane fresco appena sfornato",
    "en": "Freshly baked bread",
    "de": "Frisch gebackenes Brot"
   },
   "testo": {
    "it": "Pane e focacce per il pranzo: chiedi al bar o in reception.",
    "en": "Bread and focaccia for lunch: ask at the bar or reception.",
    "de": "Brot und Focaccia zum Mittagessen: an der Bar oder an der Rezeption."
   },
   "dalle": "10:30",
   "alle": "12:00",
   "posizione": "alto",
   "pubblico": "dentro",
   "tema": "verde",
   "azione": {
    "tipo": "servizio",
    "valore": "ristorazione",
    "etichetta": {
     "it": "Vedi il menu",
     "en": "See the menu",
     "de": "Zum Menü"
    }
   },
   "grafica": ""
  },
  {
   "id": "pranzo",
   "attivo": true,
   "titolo": {
    "it": "È ora di pranzo",
    "en": "Time for lunch",
    "de": "Zeit fürs Mittagessen"
   },
   "testo": {
    "it": "Il piatto del giorno e le insalatone ti aspettano.",
    "en": "The dish of the day and big salads are waiting for you.",
    "de": "Das Tagesgericht und große Salate warten auf Sie."
   },
   "dalle": "12:00",
   "alle": "14:30",
   "posizione": "alto",
   "pubblico": "dentro",
   "tema": "verde",
   "azione": {
    "tipo": "servizio",
    "valore": "ristorazione",
    "etichetta": {
     "it": "Ordina il pranzo",
     "en": "Order lunch",
     "de": "Mittagessen bestellen"
    }
   },
   "grafica": ""
  },
  {
   "id": "pausa",
   "attivo": true,
   "titolo": {
    "it": "Pausa dolce",
    "en": "Sweet break",
    "de": "Süße Pause"
   },
   "testo": {
    "it": "Gelato, granite e caffè freddo al bar piscina.",
    "en": "Ice cream, granita and iced coffee at the pool bar.",
    "de": "Eis, Granita und Eiskaffee an der Poolbar."
   },
   "dalle": "14:30",
   "alle": "17:30",
   "posizione": "alto",
   "pubblico": "dentro",
   "tema": "arancio",
   "azione": {
    "tipo": "nessuno",
    "valore": "",
    "etichetta": {
     "it": "",
     "en": "",
     "de": ""
    }
   },
   "grafica": ""
  },
  {
   "id": "aperitivo",
   "attivo": true,
   "titolo": {
    "it": "Aperitivo al tramonto",
    "en": "Sunset aperitif",
    "de": "Aperitif bei Sonnenuntergang"
   },
   "testo": {
    "it": "Spritz, vino e stuzzichini: il momento giusto per rilassarsi.",
    "en": "Spritz, wine and snacks: the perfect time to relax.",
    "de": "Spritz, Wein und Snacks: der richtige Moment zum Entspannen."
   },
   "dalle": "17:30",
   "alle": "19:30",
   "posizione": "alto",
   "pubblico": "dentro",
   "tema": "arancio",
   "azione": {
    "tipo": "nessuno",
    "valore": "",
    "etichetta": {
     "it": "",
     "en": "",
     "de": ""
    }
   },
   "grafica": ""
  },
  {
   "id": "cena",
   "attivo": true,
   "titolo": {
    "it": "Stasera a cena",
    "en": "Dinner tonight",
    "de": "Heute zum Abendessen"
   },
   "testo": {
    "it": "Scopri il menu della sera e scegli cosa ordinare.",
    "en": "Discover tonight's menu and choose what to order.",
    "de": "Entdecken Sie das Abendmenü und wählen Sie."
   },
   "dalle": "19:30",
   "alle": "21:30",
   "posizione": "alto",
   "pubblico": "dentro",
   "tema": "verde",
   "azione": {
    "tipo": "servizio",
    "valore": "ristorazione",
    "etichetta": {
     "it": "Ordina la cena",
     "en": "Order dinner",
     "de": "Abendessen bestellen"
    }
   },
   "grafica": ""
  },
  {
   "id": "dopocena",
   "attivo": true,
   "titolo": {
    "it": "Dopocena",
    "en": "After dinner",
    "de": "Nach dem Essen"
   },
   "testo": {
    "it": "Un dolce, un amaro o un gelato per chiudere in bellezza.",
    "en": "A dessert, a digestif or ice cream to end the evening.",
    "de": "Ein Dessert, ein Digestif oder ein Eis zum Abschluss."
   },
   "dalle": "21:30",
   "alle": "23:30",
   "posizione": "alto",
   "pubblico": "dentro",
   "tema": "verde",
   "azione": {
    "tipo": "nessuno",
    "valore": "",
    "etichetta": {
     "it": "",
     "en": "",
     "de": ""
    }
   },
   "grafica": ""
  }
 ]
};
