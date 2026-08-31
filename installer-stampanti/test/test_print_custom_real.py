#!/usr/bin/env python3
"""
Test di stampa — Protocollo CUSTOM (manuale ufficiale CUSTOM S.p.A.), macchine 2a generazione.

Frame: <STX><CNT 2b><IDENT 1b='0'><COMANDO><CKS 2b><ETX>
  STX = 0x02, ETX = 0x03
  CNT = contatore "00".."99", incrementa ad ogni frame (00 sempre accettato, utile per il primo comando)
  IDENT = carattere ASCII fisso "0"
  CKS = somma (mod 100) dei valori byte di CNT+IDENT+COMANDO, 2 cifre ASCII

Dopo l'invio: la stampante risponde ACK(0x06)/NAK(0x15) sul frame; l'host deve ri-rispondere
ACK(0x06) per confermare la ricezione dell'esito, poi la stampante (se ACK) elabora ed
echeggia il comando, oppure restituisce "ERRxx".
"""
import socket

IP = "192.168.5.4"
PORTA = 9100
TIMEOUT = 5.0

STX = bytes([0x02])
ETX = bytes([0x03])
ACK = 0x06
NAK = 0x15


def build_comando_3001_vendita(descr: str, importo_centesimi: int, tipo: str = "1") -> str:
    """3001 Operazione fiscale — vendita sul reparto 1 (unico reparto gestito da 3001)."""
    if not (0 <= importo_centesimi <= 999999999):
        raise ValueError("importo fuori range")
    return "3" + "001" + tipo + f"{len(descr):02d}" + descr + f"{importo_centesimi:09d}"


def build_comando_3004_pagamento(descr: str, importo_centesimi: int) -> str:
    """3004 Pagamento con corrispettivo pagato."""
    return "3" + "004" + f"{len(descr):02d}" + descr + f"{importo_centesimi:09d}"


def build_comando_3011_chiusura(tipo: str = "0") -> str:
    """3011 Chiusura scontrino/fattura. tipo: 0=non stampa lista pagamenti."""
    return "3" + "011" + tipo


def build_comando_3013_espulsione() -> str:
    """3013 Espulsione scontrino con taglio parziale."""
    return "3" + "013"


def build_frame(comando: str, cnt: int) -> bytes:
    if not (0 <= cnt <= 99):
        raise ValueError("cnt deve essere 0..99")
    cnt_str = f"{cnt:02d}"
    ident = "0"
    corpo = cnt_str + ident + comando
    cks = sum(ord(c) for c in corpo) % 100
    return STX + corpo.encode("ascii") + f"{cks:02d}".encode("ascii") + ETX


def invia_comando(sock: socket.socket, comando: str, cnt: int) -> bytes:
    frame = build_frame(comando, cnt)
    print(f"  Frame CNT={cnt:02d} (hex): {frame.hex(' ')}")
    print(f"  Frame CNT={cnt:02d} (ascii): {frame!r}")
    sock.sendall(frame)

    esito = sock.recv(1)
    print(f"  Risposta frame: {esito.hex(' ') if esito else '(vuota)'}", end="")
    if esito == bytes([ACK]):
        print("  -> ACK")
    elif esito == bytes([NAK]):
        print("  -> NAK")
    else:
        print("  -> sconosciuto")

    # L'host deve ri-rispondere ACK, sia in caso di ACK che di NAK ricevuto
    sock.sendall(bytes([ACK]))
    print("  Inviato ACK di conferma all'host.")

    if esito == bytes([ACK]):
        try:
            eco = sock.recv(4096)
            print(f"  Eco/risultato comando: {eco!r} (hex: {eco.hex(' ')})")
        except socket.timeout:
            print("  Nessun eco ricevuto entro il timeout.")
            eco = b""
        return eco
    return b""


def test_solo_vendita():
    """Invia SOLO il comando 3001 (vendita) e mostra la risposta, senza incatenare
    pagamento/chiusura: serve a validare che framing e checksum siano ora corretti
    prima di eseguire una transazione fiscale completa."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    print(f"Connessione a {IP}:{PORTA} ...")
    s.connect((IP, PORTA))

    comando = build_comando_3001_vendita("TEST", 100)  # 1,00 EUR, reparto 1
    print("Comando 3001 (vendita 1,00 EUR reparto 1):", repr(comando))
    invia_comando(s, comando, cnt=0)  # CNT=00, sempre accettato, per il primo comando

    s.close()
    print("Socket chiusa.")


if __name__ == "__main__":
    test_solo_vendita()
