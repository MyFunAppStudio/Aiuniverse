# -*- coding: utf-8 -*-
"""Baut die Testdaten fuer den Oberflaechen-Probelauf aus den echten Modulen.

Von Hand geschriebene Testdaten laufen dem Code davon: man baut das Modul
um und vergisst die Probe. Darum wird hier ein Wegwerf-Kanal befuellt und
genau das ausgegeben, was der Server spaeter auch ausliefert.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, "/home/claude/aiuniverse")
import abspann as A          # noqa: E402
import darsteller as D       # noqa: E402
import szenen as S           # noqa: E402

TMP = tempfile.mkdtemp()
for m in (A, D, S):
    m.REGELN = os.path.join(TMP, "regeln")
    m.EIGENE = os.path.join(TMP, "eigene")
os.makedirs(os.path.join(TMP, "regeln"), exist_ok=True)

K = "probe"


def leer(pfad, gross=False):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "wb") as f:
        f.write(b"\0" * (140000 if gross else 40))


# ---------- Avatare ----------
D.anlegen(K, "Mara")
D.anlegen(K, "Mara Feldjacke")
D.anlegen(K, "Jonas")
D.anlegen(K, "Lina")
for did, wieviel in (("d1", 3), ("d2", 1), ("d3", 2)):
    for i in range(wieviel):
        n = "ds_%s_%d.jpg" % (did, i)
        leer(D.datei_pfad(K, n), True)
        D.bild_dazu(K, did, n)
D.dabei_setzen(K, "d1", True)
D.dabei_setzen(K, "d3", True)

# ---------- Szenen ----------
for n in ("sz1.png", "sz2.png", "alt1.png", "alt2.png",
          "c_neu.mp4", "c_alt.mp4"):
    leer(S.datei_pfad(K, n), True)
S.hinzufuegen(K, "sz1.png", "Am 24. August bebte der Boden unter Pompeji.")
S.hinzufuegen(K, "sz2.png", "Die Säule stieg zweiunddreißig Kilometer hoch.")
d = S.laden(K)
s1, s2 = d["szenen"][0]["id"], d["szenen"][1]["id"]
S.aendern(K, s1, "modus", "avatare")
S.aendern(K, s1, "regie", "Mara zeigt nach oben, Jonas folgt ihrem Blick. Kamera steht fest.")
S.r3_clip_setzen(K, s1, "c_alt.mp4")
S.r3_clip_setzen(K, s1, "c_neu.mp4")       # der alte wandert in den Verlauf
S.p90_datei_setzen(K, s1, "alt1.png")      # macht den Clip veraltet
S.p90_datei_setzen(K, s1, "alt2.png")
S.aendern(K, s2, "modus", "still")
S.aendern(K, s1, "wer", ["d1"])        # Mara allein in der ersten Szene

# ---------- Abspann ----------
for n, bez in (("ab_folgen.png", "Folgen & Liken"),
               ("ab_qr.png", "QR zur Kleidung"),
               ("ab_grok.mp4", "Grok-Clip")):
    leer(A.datei_pfad(K, n), True)
    A.annehmen(K, n, bez)
A.waehlen(K, A.ZUFALL)

RAUS = {
    "/api/darsteller": D.fuer_anzeige(K),
    "/api/szenen": S.fuer_anzeige(K),
    "/api/abspann": A.fuer_anzeige(K),
}

ziel = sys.argv[1] if len(sys.argv) > 1 else "/tmp/testdaten.json"
with open(ziel, "w", encoding="utf-8") as f:
    json.dump(RAUS, f, ensure_ascii=False, indent=1)

print("Testdaten aus den echten Modulen nach %s" % ziel)
a = RAUS["/api/darsteller"]
print("  Avatare:   %s" % [(x["name"], x["dabei"], len(x["bilder"]))
                           for x in a["darsteller"]])
print("  Vorspann:  %s" % a["vorspann"])
print("             bereit=%s  %d von %d dabei" % (a["bereit"], a["anzahl"], a["max"]))
z = RAUS["/api/szenen"]["szenen"]
print("  Szenen:    %s" % [(x["modus"], x.get("clip_veraltet"),
                            len(x.get("bild_alt") or []),
                            len(x.get("clip_alt") or [])) for x in z])
print("  Abspann:   %d Einträge, Wahl=%s"
      % (RAUS["/api/abspann"]["anzahl"], RAUS["/api/abspann"]["wahl"]))
