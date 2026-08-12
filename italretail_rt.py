#!/usr/bin/env python3
"""
Comunicazione con Registratore Telematico ItalRetail (Start RT / ItalStart RT)
via protocollo CUSTOM S.p.A., macchine di 2a generazione (manuale ufficiale
"Manuale Comandi - Protocolli di comunicazione per prodotti fiscali").

Frame: <STX><CNT 2b><IDENT 1b='0'><COMANDO><CKS 2b><ETX>
  STX = 0x02, ETX = 0x03
  CNT = contatore "00".."99", incrementa ad ogni frame (non su retry); "00" sempre
        accettato, va usato per il primo comando della sessione.
  IDENT = carattere ASCII fisso "0"
  CKS = somma (mod 100) dei valori byte di CNT+IDENT+COMANDO, 2 cifre ASCII

Per ogni frame: la cassa risponde ACK(0x06)/NAK(0x15); l'host deve poi rispondere
a sua volta ACK(0x06) per confermare la ricezione dell'esito. Se ACK, la cassa
elabora ed emette un'eco/risultato del comando (o "ERRxx" in caso di errore).
"""
import socket
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

IP_DEFAULT = "192.168.5.4"
PORTA_DEFAULT = 9100
TIMEOUT_SOCKET = 5.0

STX = bytes([0x02])
ETX = bytes([0x03])
ACK = 0x06
NAK = 0x15

# Reparti confermati da stampa P100 sul registratore
DEPARTMENT_MAP = {
    "soggiorno": 1,
    "bar": 2,
    "tassa_soggiorno": 3,
    "penale_no_show": 3,  # riusa Tassa Sogg. (Esclusa IVA): confermato corretto, la penale non va tassata
}

# Pagamenti confermati da stampa P500 sul registratore
PAYMENT_MAP = {
    "contanti": 1,
    "assegni": 2,
    "carta_di_credito": 3,
    "pagamento_generico": 4,
    "buono_pasto": 5,
    "sospeso": 6,
    "credito": 7,
    "bancomat": 8,
    "non_risc_servizi": 11,
    "non_risc_fatture": 12,
    "non_risc_dcr_ssn": 13,
    "sconto_a_pagare": 14,
}


class ItalRetailError(Exception):
    pass


@dataclass
class RigaVendita:
    categoria: str        # chiave in DEPARTMENT_MAP
    descrizione: str
    prezzo_eur: float      # prezzo unitario in euro
    quantita: int = 1


@dataclass
class RisultatoInvio:
    ok: bool
    errore: str = ""
    dettagli: list = field(default_factory=list)  # traccia passo-passo per diagnostica


def sanitizza_descrizione(testo: str, max_len: int = 22) -> str:
    import unicodedata
    if not testo:
        return ""
    senza_accenti = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode("ascii")
    pulito = "".join(c for c in senza_accenti if c.isprintable() and ord(c) < 0x7E)
    pulito = " ".join(pulito.split())
    return pulito[:max_len]


def _centesimi(prezzo_eur: float) -> int:
    centesimi = int(Decimal(str(prezzo_eur)).scaleb(2).to_integral_value(rounding=ROUND_HALF_UP))
    if not (0 <= centesimi <= 999999999):
        raise ItalRetailError(f"Importo fuori range gestibile dal protocollo: {prezzo_eur}")
    return centesimi


def build_comando_3101_vendita_reparto(reparto: int, descrizione: str, importo_centesimi: int, pitch: str = "1") -> str:
    """3101 Operazione fiscale su reparto selezionato. pitch: 1=vendita."""
    if not (1 <= reparto <= 20):
        raise ItalRetailError(f"Reparto fuori range (1-20): {reparto}")
    desc = sanitizza_descrizione(descrizione, max_len=44)
    return "3" + "101" + pitch + f"{reparto:02d}" + f"{len(desc):02d}" + desc + f"{importo_centesimi:09d}"


def build_comando_3007_pagamento(codice_pagamento: int, descrizione: str, importo_centesimi: int) -> str:
    """3007 Pagamento prefissato (usa i codici pagamento programmati in cassa, es. da report P500)."""
    if not (1 <= codice_pagamento <= 30):
        raise ItalRetailError(f"Codice pagamento fuori range (1-30): {codice_pagamento}")
    desc = sanitizza_descrizione(descrizione, max_len=22)
    agree = "00"
    return "3" + "007" + f"{codice_pagamento:02d}" + agree + f"{len(desc):02d}" + desc + f"{importo_centesimi:09d}"


def build_comando_3011_chiusura(tipo: str = "0") -> str:
    """3011 Chiusura scontrino/fattura. tipo: 0=non stampa lista pagamenti."""
    return "3" + "011" + tipo


def build_comando_3015_espulsione_taglio_totale() -> str:
    """3015 Espulsione scontrino con taglio totale."""
    return "3" + "015"


def build_frame(comando: str, cnt: int) -> bytes:
    if not (0 <= cnt <= 99):
        raise ItalRetailError("cnt deve essere 0..99")
    cnt_str = f"{cnt:02d}"
    ident = "0"
    corpo = cnt_str + ident + comando
    cks = sum(ord(c) for c in corpo) % 100
    return STX + corpo.encode("ascii") + f"{cks:02d}".encode("ascii") + ETX


class RegistratoreItalRetail:
    def __init__(self, ip: str = IP_DEFAULT, porta: int = PORTA_DEFAULT, timeout: float = TIMEOUT_SOCKET):
        self.ip = ip
        self.porta = porta
        self.timeout = timeout
        self._sock = None
        self._cnt = 0

    def _prossimo_cnt(self) -> int:
        cnt = self._cnt
        self._cnt = (self._cnt + 1) % 100
        return cnt

    def verifica_connessione(self) -> RisultatoInvio:
        """Apre e chiude subito la socket, senza inviare alcun comando: verifica solo
        che IP/porta siano raggiungibili. Nessun effetto sulla cassa/memoria fiscale."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.ip, self.porta))
            return RisultatoInvio(ok=True)
        except socket.timeout:
            return RisultatoInvio(ok=False, errore=f"Timeout ({self.timeout}s) verso {self.ip}:{self.porta}")
        except OSError as e:
            return RisultatoInvio(ok=False, errore=f"Errore socket verso {self.ip}:{self.porta}: {e}")
        finally:
            sock.close()

    def _invia_comando(self, comando: str, dettagli: list) -> None:
        """Invia un comando, gestisce l'handshake ACK/NAK+ack-host. Solleva ItalRetailError su NAK o errore."""
        cnt = self._prossimo_cnt()
        frame = build_frame(comando, cnt)
        self._sock.sendall(frame)

        esito = self._sock.recv(1)
        dettagli.append({"comando": comando, "cnt": cnt, "esito_frame": esito.hex() if esito else None})

        if not esito:
            raise ItalRetailError(f"Nessuna risposta al frame CNT={cnt} (comando {comando[:4]})")

        # L'host deve ri-rispondere ACK sia in caso di ACK che di NAK ricevuto
        self._sock.sendall(bytes([ACK]))

        if esito != bytes([ACK]):
            raise ItalRetailError(f"NAK ricevuto per il comando {comando[:4]} (CNT={cnt})")

        try:
            eco = self._sock.recv(4096)
        except socket.timeout:
            eco = b""
        dettagli[-1]["eco"] = eco.decode("ascii", errors="replace") if eco else None

        if eco.startswith(b"ERR"):
            raise ItalRetailError(f"Errore dal registratore per il comando {comando[:4]}: {eco!r}")

    def _costruisci_comandi(self, righe: list, metodo_pagamento: str) -> list:
        """Valida le righe/il pagamento e costruisce i comandi (senza toccare la rete)."""
        comandi_vendita = []
        totale_centesimi = 0
        for r in righe:
            if r.categoria not in DEPARTMENT_MAP:
                raise ItalRetailError(f"Categoria reparto sconosciuta: '{r.categoria}'")
            if r.quantita <= 0:
                raise ItalRetailError(f"Quantita non valida per riga '{r.descrizione}': {r.quantita}")
            reparto = DEPARTMENT_MAP[r.categoria]
            importo_riga = _centesimi(r.prezzo_eur) * r.quantita
            totale_centesimi += importo_riga
            comandi_vendita.append(build_comando_3101_vendita_reparto(reparto, r.descrizione, importo_riga))

        codice_pagamento = PAYMENT_MAP[metodo_pagamento]
        comando_pagamento = build_comando_3007_pagamento(codice_pagamento, metodo_pagamento, totale_centesimi)
        comando_chiusura = build_comando_3011_chiusura()
        comando_espulsione = build_comando_3015_espulsione_taglio_totale()
        return [*comandi_vendita, comando_pagamento, comando_chiusura, comando_espulsione]

    def invia_scontrino(self, righe: list, metodo_pagamento: str, dry_run: bool = False) -> RisultatoInvio:
        """dry_run=True costruisce e valida tutti i frame (mappatura reparti/pagamenti,
        checksum) SENZA aprire la socket ne' toccare la cassa: utile per testare la
        pipeline browser->proxy senza generare un'operazione fiscale reale."""
        if not righe:
            return RisultatoInvio(ok=False, errore="Nessuna riga da fiscalizzare")
        if metodo_pagamento not in PAYMENT_MAP:
            return RisultatoInvio(ok=False, errore=f"Metodo di pagamento sconosciuto: '{metodo_pagamento}'")

        try:
            comandi = self._costruisci_comandi(righe, metodo_pagamento)
        except ItalRetailError as e:
            return RisultatoInvio(ok=False, errore=str(e))

        if dry_run:
            dettagli = [
                {"comando": c, "frame_hex": build_frame(c, i % 100).hex(' ')}
                for i, c in enumerate(comandi)
            ]
            return RisultatoInvio(ok=True, errore="[DRY RUN] nessun dato inviato alla cassa", dettagli=dettagli)

        dettagli = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._cnt = 0
        try:
            self._sock.connect((self.ip, self.porta))
            for comando in comandi:
                self._invia_comando(comando, dettagli)
            return RisultatoInvio(ok=True, dettagli=dettagli)
        except socket.timeout:
            return RisultatoInvio(ok=False, errore=f"Timeout ({self.timeout}s) verso {self.ip}:{self.porta}", dettagli=dettagli)
        except OSError as e:
            return RisultatoInvio(ok=False, errore=f"Errore socket verso {self.ip}:{self.porta}: {e}", dettagli=dettagli)
        except ItalRetailError as e:
            return RisultatoInvio(ok=False, errore=str(e), dettagli=dettagli)
        finally:
            self._sock.close()
            self._sock = None


if __name__ == "__main__":
    rt = RegistratoreItalRetail()
    righe = [RigaVendita(categoria="soggiorno", descrizione="Soggiorno", prezzo_eur=1.00, quantita=1)]
    risultato = rt.invia_scontrino(righe, "contanti")
    print(risultato)
