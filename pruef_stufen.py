# -*- coding: utf-8 -*-
"""Fragt das Referenzmodell, welche Werte es annimmt.

Geschickt wird eine Anfrage mit absichtlich unsinnigen Werten. fal
prueft alle Felder auf einmal und schreibt in die Antwort, was erlaubt
gewesen waere. Eine abgelehnte Anfrage kostet nichts, und es wird kein
Video erzeugt.

Der Schluessel wird aus den Kanaleinstellungen gelesen und nirgends
ausgegeben.

Aufruf:  python3 pruef_stufen.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASIS)

import animation
import einstellungen
import schluessel as schl

# Unsinnige Werte - jede Beanstandung nennt die erlaubten Werte
PROBE = {
    "prompt": "test",
    "reference_image_urls": [],
    "duration": "xxx",
    "resolution": "xxx",
    "aspect_ratio": "xxx",
}


def kanal_mit_modell():
    """Der erste Kanal, bei dem ein Referenzmodell eingetragen ist."""
    for key, k in (einstellungen.laden() or {}).items():
        kanal = dict(k)
        kanal.setdefault("id", key)
        kanal.setdefault("_key", key)
        e = animation.ref_slot(kanal)
        if e and (e.get("url") or "").strip():
            return key, kanal, e
    return None, None, None


def main():
    key, kanal, e = kanal_mit_modell()
    if not e:
        print("Kein Referenzmodell eingetragen. Im Dashboard unter "
              "KI & Technik bei Referenzclip eine Adresse eintragen.")
        return 1

    url = (e.get("url") or "").strip()
    print("Kanal:   %s" % key)
    print("Modell:  %s" % (e.get("name") or "ohne Namen"))
    print("Adresse: %s" % url)
    k = schl.fuer(kanal, e)
    print("Schluessel: %s" % ("vorhanden" if k else "FEHLT"))
    if not k:
        return 1

    ziel = animation._basis_url(url)
    print("\nFrage an: %s\n" % ziel)
    try:
        # Derselbe Weg wie im Betrieb - damit nichts anderes schiefgeht
        antwort = animation._hole(ziel, k, PROBE, zeit=60)
        print("Angenommen (unerwartet):")
        print(json.dumps(antwort, ensure_ascii=False)[:800])
    except urllib.error.HTTPError as f:
        roh = f.read().decode("utf-8", "replace")
        print("HTTP %s" % f.code)
        try:
            d = json.loads(roh)
            for p in (d.get("detail") or []):
                feld = ".".join(str(x) for x in (p.get("loc") or [])[1:])
                print("  %-18s %s" % (feld or "?", p.get("msg") or ""))
        except Exception:
            print(roh[:1200])
    except Exception as f:
        print("Keine Verbindung: %s" % f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
