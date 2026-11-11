# -*- coding: utf-8 -*-
"""Abspann-Bibliothek je Kanal.

Mehrere Abspaenne liegen bereit, Standbilder und Videos gemischt. Fuer ein
Video wird einer genommen: entweder ein fest gewaehlter oder bei jedem Lauf
ein anderer aus der Liste.

Bei einem Video gilt seine eigene Laenge. Bei einem Standbild gilt die
Sekundenzahl, die daneben steht.

Wozu der Zufall gut ist: Fuer einen Kanal ist Wiedererkennung normalerweise
mehr wert als Abwechslung. Der Zufall lohnt sich als Versuch - drei
verschiedene Schlussaufforderungen zwanzig Videos lang laufen lassen, sehen
welche die meisten Abos bringt, danach auf die Gewinnerin festschalten.
"""
import json
import os
import random
import re
import subprocess
import time

BASIS = os.path.dirname(os.path.abspath(__file__))
REGELN = os.path.join(BASIS, "regeln")
EIGENE = os.path.join(BASIS, "eigene")

BILD_ARTEN = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_ARTEN = (".mp4", ".mov", ".m4v", ".webm", ".mkv")
SEKUNDEN_MIN = 2.0
SEKUNDEN_MAX = 15.0
SEKUNDEN_STANDARD = 6.0
ZUFALL = "zufall"


def _key(kanal):
    if isinstance(kanal, dict):
        return kanal.get("_key") or kanal.get("id") or ""
    return str(kanal or "")


def _pfad(kanal):
    return os.path.join(REGELN, "abspann_%s.json" % _key(kanal))


def ordner(kanal):
    p = os.path.join(EIGENE, _key(kanal), "abspann")
    os.makedirs(p, exist_ok=True)
    return p


def datei_pfad(kanal, datei):
    return os.path.join(ordner(kanal), os.path.basename(datei or ""))


def art(name):
    e = os.path.splitext(name or "")[1].lower()
    if e in BILD_ARTEN:
        return "bild"
    if e in VIDEO_ARTEN:
        return "video"
    return ""


def _dauer_messen(pfad):
    """Laenge einer Videodatei in Sekunden, oder 0."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", str(pfad)],
                           capture_output=True, text=True)
        return round(float((r.stdout or "0").strip().split(",")[0]), 2)
    except Exception:
        return 0.0


def _sekunden(wert, standard=SEKUNDEN_STANDARD):
    try:
        w = float(str(wert).replace(",", "."))
    except Exception:
        return standard
    return round(max(SEKUNDEN_MIN, min(SEKUNDEN_MAX, w)), 2)


def _leer():
    return {"eintraege": [], "wahl": ""}


def laden(kanal):
    try:
        with open(_pfad(kanal), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    raus = _leer()
    benutzt = set()
    for e in d.get("eintraege") or []:
        if not isinstance(e, dict):
            continue
        datei = os.path.basename(str(e.get("datei") or ""))
        if not datei or not os.path.exists(datei_pfad(kanal, datei)):
            continue            # weggeraeumte Datei faellt still weg
        a = art(datei)
        if not a:
            continue
        eid = str(e.get("id") or "").strip()
        if not eid or eid in benutzt:
            i = 1
            while "a%d" % i in benutzt:
                i += 1
            eid = "a%d" % i
        benutzt.add(eid)
        # Beim Standbild gilt die eingetragene Sekundenzahl und damit auch
        # ihre Grenzen. Beim Video gilt die Laenge des Videos - die wird
        # nicht gestutzt, der Abspann ist so lang, wie er gemacht wurde.
        if a == "video":
            try:
                sek = round(float(str(e.get("sekunden")).replace(",", ".")), 2)
            except Exception:
                sek = 0.0
            if sek <= 0:
                sek = _dauer_messen(datei_pfad(kanal, datei))
        else:
            sek = _sekunden(e.get("sekunden"))
        raus["eintraege"].append({
            "id": eid,
            "name": str(e.get("name") or "").strip()[:40] or "Abspann",
            "datei": datei, "art": a, "sekunden": sek})
    wahl = str(d.get("wahl") or "")
    if wahl != ZUFALL and wahl not in benutzt:
        wahl = raus["eintraege"][0]["id"] if raus["eintraege"] else ""
    raus["wahl"] = wahl
    return raus


def speichern(kanal, d):
    os.makedirs(REGELN, exist_ok=True)
    with open(_pfad(kanal), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _finde(d, eid):
    for e in d["eintraege"]:
        if e["id"] == str(eid or ""):
            return e
    return None


def sauberer_name(name):
    name = os.path.basename(name or "abspann")
    stamm, endung = os.path.splitext(name)
    stamm = re.sub(r"[^A-Za-z0-9_-]+", "_", stamm)[:30] or "abspann"
    endung = re.sub(r"[^A-Za-z0-9.]+", "", endung).lower()[:6]
    return "ab_%s_%s%s" % (stamm, time.strftime("%H%M%S"), endung)


def annehmen(kanal, datei, name=""):
    """Traegt eine schon abgelegte Datei als Abspann ein."""
    n = os.path.basename(datei or "")
    a = art(n)
    if not a:
        return {"ok": False, "fehler": "Nur Bilder oder Videos"}
    if not os.path.exists(datei_pfad(kanal, n)):
        return {"ok": False, "fehler": "Die Datei liegt nicht im Abspannordner"}
    d = laden(kanal)
    eid, i = "a1", 1
    vorhanden = set(e["id"] for e in d["eintraege"])
    while eid in vorhanden:
        i += 1
        eid = "a%d" % i
    sek = SEKUNDEN_STANDARD
    if a == "video":
        gemessen = _dauer_messen(datei_pfad(kanal, n))
        if gemessen > 0:
            sek = round(gemessen, 2)
    d["eintraege"].append({
        "id": eid,
        "name": str(name or "").strip()[:40] or ("Abspann %d" % (len(d["eintraege"]) + 1)),
        "datei": n, "art": a, "sekunden": sek})
    if not d["wahl"]:
        d["wahl"] = eid
    speichern(kanal, d)
    return {"ok": True, "id": eid, "art": a, "sekunden": sek}


def aendern(kanal, eid, feld, wert):
    if feld not in ("name", "sekunden"):
        return {"ok": False, "fehler": "Feld unbekannt"}
    d = laden(kanal)
    e = _finde(d, eid)
    if e is None:
        return {"ok": False, "fehler": "Abspann unbekannt"}
    if feld == "name":
        w = str(wert or "").strip()[:40]
        if not w:
            return {"ok": False, "fehler": "Name darf nicht leer sein"}
        e["name"] = w
    else:
        if e["art"] == "video":
            return {"ok": False, "fehler":
                    "Bei einem Video gilt die Laenge des Videos"}
        e["sekunden"] = _sekunden(wert)
    speichern(kanal, d)
    return {"ok": True}


def entfernen(kanal, eid):
    d = laden(kanal)
    e = _finde(d, eid)
    if e is None:
        return {"ok": False, "fehler": "Abspann unbekannt"}
    d["eintraege"] = [x for x in d["eintraege"] if x["id"] != e["id"]]
    if d["wahl"] == e["id"]:
        d["wahl"] = d["eintraege"][0]["id"] if d["eintraege"] else ""
    speichern(kanal, d)
    try:
        os.remove(datei_pfad(kanal, e["datei"]))
    except Exception:
        pass
    return {"ok": True}


def waehlen(kanal, wahl):
    """Setzt den festen Abspann oder den Zufall."""
    d = laden(kanal)
    w = str(wahl or "")
    if w and w != ZUFALL and _finde(d, w) is None:
        return {"ok": False, "fehler": "Abspann unbekannt"}
    d["wahl"] = w
    speichern(kanal, d)
    return {"ok": True}


# ---------- fuer den Zusammenbau ----------

def naechster(kanal):
    """(Pfad, Sekunden) des Abspanns fuer diesen Lauf, oder (None, 0)."""
    d = laden(kanal)
    if not d["eintraege"]:
        return None, 0.0
    if d["wahl"] == ZUFALL:
        e = random.choice(d["eintraege"])
    else:
        e = _finde(d, d["wahl"]) or d["eintraege"][0]
    p = datei_pfad(kanal, e["datei"])
    if not os.path.exists(p):
        return None, 0.0
    sek = e["sekunden"]
    if e["art"] == "video":
        gemessen = _dauer_messen(p)
        if gemessen > 0:
            sek = gemessen
    return p, float(sek)


def fuer_anzeige(kanal):
    d = laden(kanal)
    for e in d["eintraege"]:
        p = datei_pfad(kanal, e["datei"])
        e["groesse"] = os.path.getsize(p) if os.path.exists(p) else 0
    d["zufall"] = ZUFALL
    d["anzahl"] = len(d["eintraege"])
    return d

# ---------- Vorschaubild ----------
# Die Liste hat bisher fuer jede Vorschau das ganze Video geladen. Bei drei
# Abspaennen a 20 MB zieht das Handy 60 MB, nur um drei Bildchen zu zeigen.
# Darum wird einmal ein Standbild daraus gemacht und nur das ausgeliefert.

VORSCHAU_BREITE = 180


def vorschau_pfad(kanal, datei):
    stamm = os.path.splitext(os.path.basename(datei or ""))[0]
    return os.path.join(ordner(kanal), ".v_%s.jpg" % stamm)


def vorschau(kanal, datei):
    """Pfad zum Standbild. Wird einmal erzeugt und dann wiederverwendet."""
    quelle = datei_pfad(kanal, datei)
    if not os.path.exists(quelle):
        return None
    if art(datei) == "bild":
        return quelle
    ziel = vorschau_pfad(kanal, datei)
    if os.path.exists(ziel) and os.path.getmtime(ziel) >= os.path.getmtime(quelle):
        return ziel
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", "0.5", "-i", str(quelle),
         "-frames:v", "1", "-vf", "scale=%d:-2" % VORSCHAU_BREITE,
         "-q:v", "5", str(ziel)],
        capture_output=True, text=True)
    if r.returncode or not os.path.exists(ziel):
        # Manche Clips sind kuerzer als eine halbe Sekunde
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(quelle),
             "-frames:v", "1", "-vf", "scale=%d:-2" % VORSCHAU_BREITE,
             "-q:v", "5", str(ziel)],
            capture_output=True, text=True)
    return ziel if os.path.exists(ziel) else None
