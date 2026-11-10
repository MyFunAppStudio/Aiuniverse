# -*- coding: utf-8 -*-
"""Avatare je Kanal: eine Bibliothek wiederkehrender Figuren.

Anders als die alten Figuren werden Avatare NICHT freigestellt und nicht
ins Bild geklebt. Ihre Bilder sind Referenzbilder: sie gehen an das
Videomodell, und das Modell zeichnet die Figur selbst in die Szene. Darum
darf hier jedes normale Bild hochgeladen werden, mit Hintergrund.

Die Bibliothek darf beliebig gross sein. Fuer ein Video hakst du an, wer
mitspielt - das ist die Besetzung. Gleichzeitig im Bild gehen hoechstens
BESETZUNG_MAX Figuren, denn das Videomodell nimmt zusammen mit dem
Hintergrundbild nur vier Referenzen an.

Ein Kleidungssatz sind mehrere Bilder derselben Figur in derselben Kleidung,
aus verschiedenen Blickwinkeln. Das erste Bild ist das Frontalbild. Innerhalb
eines Videos bleibt die Kleidung gleich - darum wird je Video ein Satz
ausgewaehlt und nicht je Szene.
"""
import json
import os
import re
import subprocess
import time

BASIS = os.path.dirname(os.path.abspath(__file__))
REGELN = os.path.join(BASIS, "regeln")
EIGENE = os.path.join(BASIS, "eigene")

BILD_ARTEN = (".jpg", ".jpeg", ".png", ".webp")
BILDER_MAX = 4          # je Kleidungssatz, das Modell nimmt nicht mehr
KANTE_MAX = 1024        # laengste Kante, damit die Anfrage klein bleibt
BESETZUNG_MAX = 3       # gleichzeitig im Bild; vier Referenzen minus Hintergrund

# Nur noch fuer das Umziehen alter Dateien, in denen die Besetzung ein
# Woerterbuch mit den festen Plaetzen a und b war.
ALTE_PLAETZE = ["a", "b"]


# ---------- Ablage ----------

def _key(kanal):
    if isinstance(kanal, dict):
        return kanal.get("_key") or kanal.get("id") or ""
    return str(kanal or "")


def _pfad(kanal):
    return os.path.join(REGELN, "darsteller_%s.json" % _key(kanal))


def ordner(kanal):
    p = os.path.join(EIGENE, _key(kanal), "darsteller")
    os.makedirs(p, exist_ok=True)
    return p


def datei_pfad(kanal, datei):
    return os.path.join(ordner(kanal), os.path.basename(datei or ""))


def _leer():
    return {"darsteller": [], "besetzung": []}


def _besetzung_roh(d):
    """Die gespeicherte Besetzung als Liste, egal wie alt die Datei ist."""
    b = d.get("besetzung")
    if isinstance(b, list):
        return [e for e in b if isinstance(e, dict)]
    if isinstance(b, dict):
        # Alte Form: {"a": {...}, "b": {...}} - in der Reihenfolge der Plaetze
        raus = []
        for p in ALTE_PLAETZE:
            e = b.get(p)
            if isinstance(e, dict) and str(e.get("d") or ""):
                raus.append(e)
        return raus
    return []


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
    for f in d.get("darsteller") or []:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "").strip()[:40]
        if not name:
            continue
        did = str(f.get("id") or "").strip()
        if not did or did in benutzt:
            did = _neue_id(benutzt, "d")
        benutzt.add(did)
        saetze, gbenutzt = [], set()
        for g in f.get("saetze") or []:
            if not isinstance(g, dict):
                continue
            gid = str(g.get("id") or "").strip()
            if not gid or gid in gbenutzt:
                gid = _neue_id(gbenutzt, "g")
            gbenutzt.add(gid)
            bilder = [os.path.basename(str(b)) for b in (g.get("bilder") or [])
                      if str(b or "").strip()]
            saetze.append({"id": gid,
                           "name": str(g.get("name") or "").strip()[:40] or "Kleidung",
                           "bilder": bilder[:BILDER_MAX]})
        raus["darsteller"].append({
            "id": did, "name": name,
            "rolle": str(f.get("rolle") or "").strip()[:40],
            "beschreibung": str(f.get("beschreibung") or "").strip()[:300],
            "saetze": saetze})
    gesehen = set()
    for e in _besetzung_roh(d):
        did = str(e.get("d") or "")
        f = _finde(raus, did)
        if f is None or did in gesehen:
            continue            # geloescht oder doppelt - faellt still weg
        gesehen.add(did)
        gid = str(e.get("g") or "")
        if _satz(f, gid) is None:
            gid = f["saetze"][0]["id"] if f["saetze"] else ""
        raus["besetzung"].append({"d": did, "g": gid})
        if len(raus["besetzung"]) >= BESETZUNG_MAX:
            break
    return raus


def speichern(kanal, d):
    os.makedirs(REGELN, exist_ok=True)
    with open(_pfad(kanal), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _neue_id(benutzt, kopf):
    i = 1
    while "%s%d" % (kopf, i) in benutzt:
        i += 1
    return "%s%d" % (kopf, i)


def _finde(d, did):
    for f in d["darsteller"]:
        if f["id"] == str(did or ""):
            return f
    return None


def _satz(f, gid):
    for g in (f or {}).get("saetze") or []:
        if g["id"] == str(gid or ""):
            return g
    return None


def _dabei(d, did):
    for e in d["besetzung"]:
        if e["d"] == str(did or ""):
            return e
    return None


# ---------- Avatare ----------

def anlegen(kanal, name, rolle=""):
    d = laden(kanal)
    name = str(name or "").strip()[:40]
    if not name:
        return {"ok": False, "fehler": "Name fehlt"}
    if any(f["name"].lower() == name.lower() for f in d["darsteller"]):
        return {"ok": False, "fehler": "Gibt es schon"}
    did = _neue_id(set(f["id"] for f in d["darsteller"]), "d")
    d["darsteller"].append({"id": did, "name": name,
                            "rolle": str(rolle or "").strip()[:40],
                            "beschreibung": "", "saetze": []})
    speichern(kanal, d)
    return {"ok": True, "id": did}


def aendern(kanal, did, feld, wert):
    if feld not in ("name", "rolle", "beschreibung"):
        return {"ok": False, "fehler": "Feld unbekannt"}
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    w = str(wert or "").strip()[:300 if feld == "beschreibung" else 40]
    if feld == "name":
        if not w:
            return {"ok": False, "fehler": "Name darf nicht leer sein"}
        if any(x["name"].lower() == w.lower() and x["id"] != f["id"]
               for x in d["darsteller"]):
            return {"ok": False, "fehler": "Gibt es schon"}
    f[feld] = w
    speichern(kanal, d)
    return {"ok": True}


def _weg(kanal, dateien):
    for n in dateien:
        try:
            os.remove(datei_pfad(kanal, n))
        except Exception:
            pass


def entfernen(kanal, did):
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    for g in f["saetze"]:
        _weg(kanal, g["bilder"])
    d["darsteller"] = [x for x in d["darsteller"] if x["id"] != f["id"]]
    d["besetzung"] = [e for e in d["besetzung"] if e["d"] != f["id"]]
    speichern(kanal, d)
    return {"ok": True}


# ---------- Kleidungssaetze ----------

def satz_anlegen(kanal, did, name=""):
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    gid = _neue_id(set(g["id"] for g in f["saetze"]), "g")
    f["saetze"].append({"id": gid,
                        "name": str(name or "").strip()[:40]
                                or ("Kleidung %d" % (len(f["saetze"]) + 1)),
                        "bilder": []})
    # Der erste Satz einer Figur wird gleich der gewaehlte, falls sie dabei ist
    e = _dabei(d, did)
    if e is not None and not e.get("g"):
        e["g"] = gid
    speichern(kanal, d)
    return {"ok": True, "id": gid}


def satz_aendern(kanal, did, gid, name):
    d = laden(kanal)
    g = _satz(_finde(d, did), gid)
    if g is None:
        return {"ok": False, "fehler": "Kleidungssatz unbekannt"}
    w = str(name or "").strip()[:40]
    if not w:
        return {"ok": False, "fehler": "Name darf nicht leer sein"}
    g["name"] = w
    speichern(kanal, d)
    return {"ok": True}


def satz_entfernen(kanal, did, gid):
    d = laden(kanal)
    f = _finde(d, did)
    g = _satz(f, gid)
    if g is None:
        return {"ok": False, "fehler": "Kleidungssatz unbekannt"}
    _weg(kanal, g["bilder"])
    f["saetze"] = [x for x in f["saetze"] if x["id"] != g["id"]]
    e = _dabei(d, did)
    if e is not None and e.get("g") == g["id"]:
        e["g"] = f["saetze"][0]["id"] if f["saetze"] else ""
    speichern(kanal, d)
    return {"ok": True}


# ---------- Bilder ----------

def _masse(pfad):
    """(Breite, Hoehe) oder None."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height",
                        "-of", "csv=p=0:s=x", str(pfad)],
                       capture_output=True, text=True)
    t = re.findall(r"(\d+)x(\d+)", (r.stdout or ""))
    if not t:
        return None
    return int(t[0][0]), int(t[0][1])


def aufbereiten(kanal, datei):
    """Macht aus der hochgeladenen Datei ein brauchbares Referenzbild.

    Verkleinert auf hoechstens KANTE_MAX und legt es als JPEG auf weissem
    Grund ab, damit durchsichtige Stellen nicht schwarz werden und die
    Anfrage an das Videomodell klein bleibt. Gibt den neuen Namen zurueck.
    """
    quelle = datei_pfad(kanal, datei)
    if not os.path.exists(quelle):
        return {"ok": False, "fehler": "Datei nicht da"}
    m = _masse(quelle)
    if not m:
        return {"ok": False, "fehler": "Bild nicht lesbar"}
    b, h = m
    if max(b, h) > KANTE_MAX:
        f = float(KANTE_MAX) / float(max(b, h))
        b, h = max(2, int(round(b * f)) // 2 * 2), max(2, int(round(h * f)) // 2 * 2)
    else:
        b, h = max(2, b // 2 * 2), max(2, h // 2 * 2)
    stamm = re.sub(r"[^a-z0-9_-]+", "_",
                   os.path.splitext(os.path.basename(datei))[0].lower())[:26]
    # Der Hochlader haengt schon eine Uhrzeit an, die nicht zweimal hinein soll
    stamm = re.sub(r"_\d{6}$", "", stamm) or "ds"
    # Zwei Bilder in derselben Sekunde duerfen sich nicht gegenseitig
    # ueberschreiben, darum wird bei Bedarf durchgezaehlt.
    uhr = time.strftime("%H%M%S")
    name = "ds_%s_%s.jpg" % (stamm, uhr)
    zaehler = 1
    while os.path.exists(datei_pfad(kanal, name)):
        zaehler += 1
        name = "ds_%s_%s_%d.jpg" % (stamm, uhr, zaehler)
    ziel = datei_pfad(kanal, name)
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(quelle),
         "-filter_complex",
         "color=white:s=%dx%d[bg];[0:v]scale=%d:%d:flags=lanczos[s];"
         "[bg][s]overlay=0:0:shortest=1,format=yuv420p" % (b, h, b, h),
         "-frames:v", "1", "-q:v", "3", str(ziel)],
        capture_output=True, text=True)
    if r.returncode or not os.path.exists(ziel):
        try:
            os.remove(ziel)
        except Exception:
            pass
        return {"ok": False, "fehler": (r.stderr or "")[-160:] or "Umwandeln ging nicht"}
    try:
        os.remove(quelle)
    except Exception:
        pass
    return {"ok": True, "datei": name, "breite": b, "hoehe": h}


def bild_dazu(kanal, did, gid, datei):
    """Haengt ein schon aufbereitetes Bild an den Kleidungssatz."""
    d = laden(kanal)
    g = _satz(_finde(d, did), gid)
    if g is None:
        return {"ok": False, "fehler": "Kleidungssatz unbekannt"}
    if len(g["bilder"]) >= BILDER_MAX:
        return {"ok": False, "fehler":
                "Hoechstens %d Bilder je Kleidungssatz" % BILDER_MAX}
    n = os.path.basename(datei or "")
    if not os.path.exists(datei_pfad(kanal, n)):
        return {"ok": False, "fehler": "Die Datei liegt nicht im Avatarordner"}
    if n not in g["bilder"]:
        g["bilder"].append(n)
    speichern(kanal, d)
    return {"ok": True, "datei": n}


def bild_weg(kanal, did, gid, datei):
    d = laden(kanal)
    g = _satz(_finde(d, did), gid)
    if g is None:
        return {"ok": False, "fehler": "Kleidungssatz unbekannt"}
    n = os.path.basename(datei or "")
    if n not in g["bilder"]:
        return {"ok": False, "fehler": "Bild unbekannt"}
    g["bilder"] = [x for x in g["bilder"] if x != n]
    speichern(kanal, d)
    _weg(kanal, [n])
    return {"ok": True}


def bild_vor(kanal, did, gid, datei):
    """Macht ein Bild zum Frontalbild, also zum ersten im Satz."""
    d = laden(kanal)
    g = _satz(_finde(d, did), gid)
    if g is None:
        return {"ok": False, "fehler": "Kleidungssatz unbekannt"}
    n = os.path.basename(datei or "")
    if n not in g["bilder"]:
        return {"ok": False, "fehler": "Bild unbekannt"}
    g["bilder"] = [n] + [x for x in g["bilder"] if x != n]
    speichern(kanal, d)
    return {"ok": True}


def satz_da(kanal, did, gid):
    """Gibt es diesen Kleidungssatz? Vor dem Hochladen zu pruefen."""
    return _satz(_finde(laden(kanal), did), gid) is not None


def platz_frei(kanal, did, gid):
    """Wie viele Bilder der Satz noch annimmt."""
    g = _satz(_finde(laden(kanal), did), gid)
    if g is None:
        return 0
    return max(0, BILDER_MAX - len(g["bilder"]))


def bilder_pfade(kanal, did, gid):
    """Vorhandene Bilddateien des Satzes, Frontalbild zuerst."""
    g = _satz(_finde(laden(kanal), did), gid)
    if g is None:
        return []
    raus = []
    for n in g["bilder"]:
        p = datei_pfad(kanal, n)
        if os.path.exists(p):
            raus.append(p)
    return raus


# ---------- Besetzung ----------

def dabei_setzen(kanal, did, an, gid=""):
    """Hakt einen Avatar fuer dieses Video an oder ab."""
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    e = _dabei(d, did)
    if not an:
        if e is None:
            return {"ok": True}
        d["besetzung"] = [x for x in d["besetzung"] if x["d"] != f["id"]]
        speichern(kanal, d)
        return {"ok": True}
    if e is not None:
        return {"ok": True}
    if not f["saetze"]:
        return {"ok": False, "fehler":
                "%s hat noch keinen Kleidungssatz. Leg einen an und lade "
                "Bilder hoch." % f["name"]}
    if len(d["besetzung"]) >= BESETZUNG_MAX:
        return {"ok": False, "fehler":
                "Hoechstens %d Avatare gleichzeitig - das Videomodell nimmt "
                "mit dem Hintergrundbild nur vier Referenzen."
                % BESETZUNG_MAX}
    g = _satz(f, gid) or f["saetze"][0]
    d["besetzung"].append({"d": f["id"], "g": g["id"]})
    speichern(kanal, d)
    return {"ok": True}


def satz_waehlen(kanal, did, gid):
    """Waehlt den Kleidungssatz, in dem ein Avatar dieses Video spielt."""
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    g = _satz(f, gid)
    if g is None:
        return {"ok": False, "fehler": "Kleidungssatz unbekannt"}
    e = _dabei(d, did)
    if e is None:
        if len(d["besetzung"]) >= BESETZUNG_MAX:
            return {"ok": False, "fehler":
                    "Hoechstens %d Avatare gleichzeitig" % BESETZUNG_MAX}
        d["besetzung"].append({"d": f["id"], "g": g["id"]})
    else:
        e["g"] = g["id"]
    speichern(kanal, d)
    return {"ok": True}


def _stand(kanal):
    """Je besetztem Avatar: (did, lage, text). Lage ist ok oder kaputt."""
    d = laden(kanal)
    raus = []
    for e in d["besetzung"]:
        f = _finde(d, e.get("d"))
        if f is None:
            continue
        g = _satz(f, e.get("g"))
        if g is None:
            raus.append((f["id"], "kaputt",
                         "%s hat keinen Kleidungssatz mehr" % f["name"]))
            continue
        if not [n for n in g["bilder"] if os.path.exists(datei_pfad(kanal, n))]:
            raus.append((f["id"], "kaputt",
                         "%s: im Satz \"%s\" liegt kein Bild"
                         % (f["name"], g["name"])))
            continue
        raus.append((f["id"], "ok", f["name"]))
    return raus


def besetzung(kanal):
    """Die angehakten Avatare, in der Reihenfolge der Besetzung.

    Je Eintrag: id, name, rolle, beschreibung, satz, bilder (ganze Pfade).
    Avatare ohne brauchbares Bild fallen weg.
    """
    d = laden(kanal)
    raus = []
    for e in d["besetzung"]:
        f = _finde(d, e.get("d"))
        if f is None:
            continue
        g = _satz(f, e.get("g"))
        if g is None:
            continue
        bilder = [datei_pfad(kanal, n) for n in g["bilder"]
                  if os.path.exists(datei_pfad(kanal, n))]
        if not bilder:
            continue
        raus.append({"id": f["id"], "name": f["name"], "rolle": f.get("rolle", ""),
                     "beschreibung": f.get("beschreibung", ""),
                     "satz": g["name"], "bilder": bilder})
    return raus


def bereit(kanal):
    """(ok, Grund) - ob die Besetzung fuer einen Referenzclip reicht.

    Ein angehakter Avatar, der kein Bild hat, ist ein Fehler und nicht
    einfach einer weniger: sonst laeuft das Video still mit einer Figur
    weniger durch, und das faellt erst am Ende auf.
    """
    st = _stand(kanal)
    kaputt = [t for _d, lage, t in st if lage == "kaputt"]
    if kaputt:
        return False, ". ".join(kaputt)
    gut = [t for _d, lage, t in st if lage == "ok"]
    if not gut:
        return False, ("Kein Avatar angehakt. Leg im Reiter Avatare eine Figur "
                       "an, gib ihr einen Kleidungssatz mit Bildern und hak sie "
                       "fuer dieses Video an.")
    return True, ""


def prompt_vorspann(kanal, hintergrund=True):
    """Der Satz, der dem Modell sagt, wer wer ist.

    Das Videomodell spricht die Referenzen als @Element1, @Element2 und
    @Image1 an. Ohne diesen Vorspann weiss es nicht, welches Bild welche
    Figur ist.
    """
    teile = []
    for i, x in enumerate(besetzung(kanal)):
        wer = x["name"]
        if x.get("rolle"):
            wer += ", %s" % x["rolle"]
        if x.get("beschreibung"):
            wer += " (%s)" % x["beschreibung"]
        teile.append("@Element%d is %s." % (i + 1, wer))
    if hintergrund:
        teile.append("@Image1 is the background scene they are standing in.")
    return " ".join(teile)


# ---------- fuer das Dashboard ----------

def fuer_anzeige(kanal):
    d = laden(kanal)
    raus = []
    for f in d["darsteller"]:
        saetze = []
        for g in f["saetze"]:
            bilder = []
            for n in g["bilder"]:
                p = datei_pfad(kanal, n)
                bilder.append({"datei": n, "da": os.path.exists(p),
                               "groesse": os.path.getsize(p) if os.path.exists(p) else 0})
            saetze.append({"id": g["id"], "name": g["name"], "bilder": bilder,
                           "voll": len(bilder) >= BILDER_MAX})
        e = _dabei(d, f["id"])
        raus.append({"id": f["id"], "name": f["name"], "rolle": f.get("rolle", ""),
                     "beschreibung": f.get("beschreibung", ""), "saetze": saetze,
                     "dabei": e is not None,
                     "gewaehlt": (e or {}).get("g", "")
                                 or (saetze[0]["id"] if saetze else "")})
    ok, grund = bereit(kanal)
    return {"darsteller": raus, "besetzung": d["besetzung"],
            "max": BESETZUNG_MAX, "bilder_max": BILDER_MAX,
            "anzahl": len(d["besetzung"]),
            "bereit": ok, "grund": grund,
            "vorspann": prompt_vorspann(kanal)}
