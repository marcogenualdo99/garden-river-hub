#!/usr/bin/env python3
"""
Test di stampa minimo — Registratore Telematico ItalRetail, protocollo Custom
2a Generazione (framing STX/Seq/Comando/ETX/BCC).

Uso: python3 test_print_gen2.py
"""
import socket

IP = "192.168.5.4"
PORTA = 9100
TIMEOUT = 5.0

STX = 0x02
ETX = 0x03

COMANDO_TEST = "11R1KEYTEST\r1T\r"          # vendita 0,01 EUR su reparto 1, chiusura contanti
COMANDO_TEST_1EURO = "11R100KEYTEST\r1T\r"  # alternativa da 1,00 EUR se la cassa rifiuta 0,01


def build_custom_gen2_packet(command_string: str, seq: str = '0') -> bytes:
    """Costruisce il frame STX + Seq + Comando + ETX + BCC.
    BCC = XOR di tutti i byte da Seq a ETX compreso."""
    if len(seq) != 1:
        raise ValueError(f"seq deve essere un singolo carattere ASCII, ricevuto: {seq!r}")

    seq_byte = seq.encode("ascii")
    cmd_bytes = command_string.encode("ascii")
    etx_byte = bytes([ETX])

    corpo_per_bcc = seq_byte + cmd_bytes + etx_byte
    bcc = 0
    for b in corpo_per_bcc:
        bcc ^= b

    return bytes([STX]) + seq_byte + cmd_bytes + etx_byte + bytes([bcc])


def invia_test(command_string: str, seq: str = '0') -> None:
    pacchetto = build_custom_gen2_packet(command_string, seq)
    print("Comando:", repr(command_string))
    print("Pacchetto (hex):", pacchetto.hex(' '))
    print(f"Connessione a {IP}:{PORTA} ...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    try:
        sock.connect((IP, PORTA))
        sock.sendall(pacchetto)
        print("Pacchetto inviato. In attesa di risposta...")

        try:
            risposta = sock.recv(4096)
            if risposta:
                print("Risposta ricevuta (hex):", risposta.hex(' '))
                for b in risposta:
                    if b == 0x06:
                        print("  -> byte 0x06 = ACK (comando accettato)")
                    elif b == 0x15:
                        print("  -> byte 0x15 = NAK (comando rifiutato)")
            else:
                print("Connessione chiusa dal peer senza inviare dati.")
        except socket.timeout:
            print("Nessuna risposta ricevuta entro il timeout.")

        sock.shutdown(socket.SHUT_WR)
    except socket.timeout:
        print(f"Timeout ({TIMEOUT}s) verso {IP}:{PORTA}")
    except OSError as e:
        print(f"Errore socket verso {IP}:{PORTA}: {e}")
    finally:
        sock.close()
        print("Socket chiusa.")


if __name__ == "__main__":
    invia_test(COMANDO_TEST)
