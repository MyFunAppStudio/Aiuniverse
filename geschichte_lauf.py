# -*- coding: utf-8 -*-
"""Baut aus der hinterlegten Geschichte die Szenen. Laeuft im Hintergrund."""
import os, sys
BASIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASIS)
import einstellungen
import geschichte


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "b"
    kanal = einstellungen.laden().get(key) or {}
    text = kanal.get("geschichte_text") or ""
    if not text.strip():
        print("ACHT  Keine Geschichte hinterlegt")
        return 1
    saetze = geschichte.zerlege(text)
    print("Geschichte ergibt %d Szenen." % len(saetze))

    def melde(i, n, z):
        print("%s ..." % z)

    e = geschichte.aufbauen(kanal, text, melde)
    if not e.get("ok"):
        print("ACHT  %s" % (e.get("fehler") or "nichts erzeugt"))
        return 1
    print("FERTIG: %d Szenen, %d ohne Bild, etwa %.2f USD"
          % (e["szenen"], e["ohne_bild"], e["kosten"]))
    print("Jetzt unten im Szenen-Editor nachsehen und dann Video erzeugen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
