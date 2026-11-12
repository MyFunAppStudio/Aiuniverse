# -*- coding: utf-8 -*-
"""Fragt das Referenzmodell, welche Werte es annimmt.

Geschickt wird eine Anfrage mit absichtlich unsinnigen Werten. Modelle,
die ihre Eingaben vorher pruefen, antworten mit der Liste der erlaubten
Werte - abgelehnt, kostenlos, kein Video.

Manche Modelle pruefen erst beim Rechnen und stellen die Anfrage
trotzdem in die Warteschlange. Die wird dann sofort zurueckgezogen.

Der Schluessel wird aus den Kanaleinstellungen gelesen und nirgends
ausgegeben.

Aufruf:
    python3 pruef_stufen.py            alle Kanaele mit Modell
    python3 pruef_stufen.py <kanal>    nur dieser Kanal
"""
import os
import sys
import urllib.error

BASIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASIS)

import animation
import einstellungen
import schluessel as schl


def kanaele_mit_modell(nur=None):
    raus = []
    for key, k in (einstellungen.laden() or {}).items():
        if nur and key != nur:
            continue
        kanal = dict(k)
        kanal.setdefault("id", key)
        kanal.setdefault("_key", key)
        e = animation.ref_slot(kanal)
        if e and (e.get("url") or "").strip():
            raus.append((key, kanal, e))
    return raus


def einen(key, kanal, e):
    url = (e.get("url") or "").strip()
    print("=" * 58)
    print("Kanal:   %s  (%s)" % (key, kanal.get("name") or ""))
    print("Modell:  %s" % (e.get("name") or "ohne Namen"))
    print("Adresse: %s" % url)
    k = schl.fuer(kanal, e)
    if not k:
        print("Schluessel: FEHLT - uebersprungen")
        return
    print("Schluessel: vorhanden")

    try:
        ziel = animation.m9_direkt(animation._basis_url(url))
        print("Frage an:   %s" % ziel)
        antwort = animation._hole(ziel, k, animation.M9_PROBE, zeit=60)
        print("\nDas Modell nimmt die Anfrage an, statt sie zu pruefen -")
        print("es sagt also nicht, welche Werte es erlaubt.")
        animation.m9_abbrechen(antwort, k)
        return
    except urllib.error.HTTPError as f:
        try:
            roh = f.read().decode("utf-8", "replace")
        except Exception:
            roh = ""
        print("\nHTTP %s - das Modell nennt seine erlaubten Werte:\n" % f.code)
    except Exception as f:
        print("\nKeine Verbindung: %s" % f)
        return

    werte = animation.m9_auswerten(roh)
    if not werte:
        print(roh[:900])
        return
    for feld in sorted(werte):
        print("  %-16s %s" % (feld, ", ".join(werte[feld])))
    laengen = animation.m9_zahlen(werte)
    if laengen:
        print("\n  -> Clip-Laengen: %s Sekunden"
              % ", ".join(str(x) for x in laengen))

    alle = animation.m9_laden()
    alle[url.lower()] = werte
    animation.m9_speichern(alle)
    print("\nGemerkt in regeln/modell_werte.json - der Bau benutzt das jetzt.")


def main():
    nur = sys.argv[1] if len(sys.argv) > 1 else None
    liste = kanaele_mit_modell(nur)
    if not liste:
        if nur:
            print("Kanal %r hat kein Referenzmodell eingetragen." % nur)
        else:
            print("Kein Kanal hat ein Referenzmodell eingetragen.")
        print("Vorhandene Kanaele: %s"
              % ", ".join((einstellungen.laden() or {}).keys()))
        return 1
    for key, kanal, e in liste:
        einen(key, kanal, e)
    print("=" * 58)
    return 0


if __name__ == "__main__":
    sys.exit(main())
