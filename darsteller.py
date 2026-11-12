# -*- coding: utf-8 -*-
"""Avatare je Kanal: eine Bibliothek wiederkehrender Figuren.

Ein Avatar ist ein Name und bis zu BILDER_MAX Bilder. Mehr nicht. Das
erste Bild ist das Frontalbild.

Die Bilder werden NICHT freigestellt und nicht ins Bild geklebt. Sie gehen
als Referenz an das Videomodell, und das zeichnet die Figur selbst in die
Szene. Darum darf hier jedes normale Bild hochgeladen werden, mit
Hintergrund.

Die Bibliothek darf beliebig gross sein. Fuer ein Video hakst du an, wer
mitspielt - das ist die Besetzung. Gleichzeitig im Bild gehen hoechstens
BESETZUNG_MAX Figuren, denn das Videomodell nimmt zusammen mit dem
Hintergrundbild nur vier Referenzen an.

Andere Kleidung fuer eine spaetere Folge wird als eigener Avatar angelegt
("Mara Feldjacke") und statt der anderen angehakt. Das ist ein Eintrag
mehr in der Liste und dafuer keine zweite Ebene in der Bedienung.

Warum ueberhaupt ein Name: Das Modell bekommt einen Vorspann, der sagt,
welches Referenzbild wer ist - sonst versteht es "Mara zeigt nach oben"
in der Regieanweisung nicht. Wie die Figur AUSSIEHT steht schon auf den
Bildern. Dasselbe nochmal als Text zu beschreiben bringt Bild und Text
gegeneinander auf und laesst die Figur driften, darum gibt es hier kein
einziges Feld dafuer.
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
BILDER_MAX = 4          # je Avatar, das Modell nimmt nicht mehr
KANTE_MAX = 1024        # laengste Kante, damit die Anfrage klein bleibt
BESETZUNG_MAX = 3       # gleichzeitig im Bild; vier Referenzen minus Hintergrund

ALTE_PLAETZE = ["a", "b"]   # nur noch zum Umziehen ganz alter Dateien


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


def _neue_id(benutzt, kopf="d"):
    i = 1
    while "%s%d" % (kopf, i) in benutzt:
        i += 1
    return "%s%d" % (kopf, i)


# ---------- Umziehen alter Dateien ----------

def _alte_besetzung(roh):
    """Jede je gespeicherte Form der Besetzung als Liste von (id, satz)."""
    if isinstance(roh, dict):          # ganz alt: {"a": {...}, "b": {...}}
        raus = []
        for p in ALTE_PLAETZE:
            e = roh.get(p)
            if isinstance(e, dict) and str(e.get("d") or ""):
                raus.append((str(e["d"]), str(e.get("g") or "")))
        return raus
    if isinstance(roh, list):
        raus = []
        for e in roh:
            if isinstance(e, dict) and str(e.get("d") or ""):
                raus.append((str(e["d"]), str(e.get("g") or "")))
            elif isinstance(e, str) and e.strip():   # neu: nur noch die id
                raus.append((e.strip(), ""))
        return raus
    return []


def _umziehen(f, benutzt):
    """Ein alter Eintrag mit Kleidungssaetzen wird zu einem oder mehreren
    Avataren. Gibt (Liste neuer Avatare, {alte Satz-id: neue Avatar-id}).
    """
    name = str(f.get("name") or "").strip()[:40]
    alt_id = str(f.get("id") or "").strip()

    # Schon im flachen Modell?
    if isinstance(f.get("bilder"), list) and "saetze" not in f:
        did = alt_id if alt_id and alt_id not in benutzt else _neue_id(benutzt)
        benutzt.add(did)
        bilder = [os.path.basename(str(b)) for b in f["bilder"] if str(b or "").strip()]
        return [{"id": did, "name": name,
                 "bilder": bilder[:BILDER_MAX]}], {"": did}

    raus, karte = [], {}
    saetze = [g for g in (f.get("saetze") or []) if isinstance(g, dict)]
    if not saetze:
        saetze = [{"id": "", "name": "", "bilder": []}]
    for nr, g in enumerate(saetze):
        bilder = [os.path.basename(str(b)) for b in (g.get("bilder") or [])
                  if str(b or "").strip()][:BILDER_MAX]
        gname = str(g.get("name") or "").strip()[:40]
        if nr == 0:
            did = alt_id if alt_id and alt_id not in benutzt else _neue_id(benutzt)
            wie = name
        else:
            did = _neue_id(benutzt)
            # Der zweite Kleidungssatz wird eine eigene Figur
            wie = ("%s %s" % (name, gname)).strip()[:40] if gname else \
                  ("%s %d" % (name, nr + 1))[:40]
        benutzt.add(did)
        karte[str(g.get("id") or "")] = did
        raus.append({"id": did, "name": wie, "bilder": bilder})
    return raus, karte


# ---------- Laden und Speichern ----------

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
    karten = {}
    for f in d.get("darsteller") or []:
        if not isinstance(f, dict) or not str(f.get("name") or "").strip():
            continue
        neue, karte = _umziehen(f, benutzt)
        raus["darsteller"].extend(neue)
        karten[str(f.get("id") or "")] = karte

    gesehen = set()
    for alt_id, satz_id in _alte_besetzung(d.get("besetzung")):
        karte = karten.get(alt_id) or {}
        did = karte.get(satz_id) or karte.get("") or \
            (alt_id if any(x["id"] == alt_id for x in raus["darsteller"]) else "")
        if not did or did in gesehen:
            continue
        if not any(x["id"] == did for x in raus["darsteller"]):
            continue
        gesehen.add(did)
        raus["besetzung"].append(did)
        if len(raus["besetzung"]) >= BESETZUNG_MAX:
            break
    return raus


def speichern(kanal, d):
    os.makedirs(REGELN, exist_ok=True)
    with open(_pfad(kanal), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _finde(d, did):
    for f in d["darsteller"]:
        if f["id"] == str(did or ""):
            return f
    return None


# ---------- Avatare ----------

def _eindeutig(name, vorhanden):
    """Haengt bei Bedarf eine Zahl an, damit kein Name zweimal vorkommt."""
    if name.lower() not in vorhanden:
        return name
    grund, i = name, 2
    while name.lower() in vorhanden:
        name = ("%s %d" % (grund, i))[:40]
        i += 1
    return name


def _name_aus_datei(dateiname, vorhanden):
    """Macht aus einem Dateinamen einen brauchbaren Avatarnamen.

    Bildgeneratoren spucken Namen wie 1000057330.png aus - daraus laesst
    sich nichts machen, dann heisst der Avatar eben "Avatar 1" und wird
    auf der Karte umbenannt.
    """
    stamm = os.path.splitext(os.path.basename(dateiname or ""))[0]
    stamm = re.sub(r"[_\-]+", " ", stamm)
    stamm = re.sub(r"\s+", " ", stamm).strip()[:40]
    if re.fullmatch(r"[\d\s.]*", stamm or ""):
        i = 1
        while ("avatar %d" % i) in vorhanden:
            i += 1
        return "Avatar %d" % i
    return _eindeutig(stamm[0].upper() + stamm[1:], vorhanden)


def anlegen(kanal, name, rolle=""):
    """Legt einen Avatar an. Ohne Namen wird nach der Datei benannt."""
    d = laden(kanal)
    vorhanden = set(f["name"].lower() for f in d["darsteller"])
    name = str(name or "").strip()[:40]
    if not name:
        return {"ok": False, "fehler": "Name fehlt"}
    if name.lower() in vorhanden:
        return {"ok": False, "fehler": "Gibt es schon"}
    did = _neue_id(set(f["id"] for f in d["darsteller"]))
    d["darsteller"].append({"id": did, "name": name, "bilder": []})
    speichern(kanal, d)
    return {"ok": True, "id": did, "name": name}


def anlegen_fuer_datei(kanal, dateiname):
    """Legt beim Hochladen einen Avatar an, benannt nach der Datei."""
    d = laden(kanal)
    vorhanden = set(f["name"].lower() for f in d["darsteller"])
    name = _name_aus_datei(dateiname, vorhanden)
    did = _neue_id(set(f["id"] for f in d["darsteller"]))
    d["darsteller"].append({"id": did, "name": name, "bilder": []})
    speichern(kanal, d)
    return {"ok": True, "id": did, "name": name}


def aendern(kanal, did, feld, wert):
    if feld != "name":
        return {"ok": False, "fehler": "Feld unbekannt"}
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    w = str(wert or "").strip()[:40]
    if not w:
        return {"ok": False, "fehler": "Name darf nicht leer sein"}
    if any(x["name"].lower() == w.lower() and x["id"] != f["id"]
           for x in d["darsteller"]):
        return {"ok": False, "fehler": "Gibt es schon"}
    f["name"] = w
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
    _weg(kanal, f["bilder"])
    d["darsteller"] = [x for x in d["darsteller"] if x["id"] != f["id"]]
    d["besetzung"] = [x for x in d["besetzung"] if x != f["id"]]
    speichern(kanal, d)
    return {"ok": True}


# ---------- Bilder ----------

def _masse(pfad):
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
    stamm = re.sub(r"_\d{6}$", "", stamm) or "ds"
    # Zwei Bilder in derselben Sekunde duerfen sich nicht ueberschreiben
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
        # ffmpeg redet in Fachkauderwelsch; das hilft niemandem weiter
        print("[Avatar] ffmpeg: %s" % (r.stderr or "")[-300:])
        return {"ok": False, "fehler":
                "Das Bild lässt sich nicht lesen. Probier es als JPG oder PNG "
                "noch einmal."}
    try:
        os.remove(quelle)
    except Exception:
        pass
    return {"ok": True, "datei": name, "breite": b, "hoehe": h}


def da(kanal, did):
    """Gibt es diesen Avatar? Vor dem Hochladen zu pruefen."""
    return _finde(laden(kanal), did) is not None


def platz_frei(kanal, did):
    """Wie viele Bilder der Avatar noch annimmt."""
    f = _finde(laden(kanal), did)
    if f is None:
        return 0
    return max(0, BILDER_MAX - len(f["bilder"]))


def bild_dazu(kanal, did, datei):
    """Haengt ein schon aufbereitetes Bild an den Avatar."""
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    if len(f["bilder"]) >= BILDER_MAX:
        return {"ok": False, "fehler": "Hoechstens %d Bilder je Avatar" % BILDER_MAX}
    n = os.path.basename(datei or "")
    if not os.path.exists(datei_pfad(kanal, n)):
        return {"ok": False, "fehler": "Die Datei liegt nicht im Avatarordner"}
    if n not in f["bilder"]:
        f["bilder"].append(n)
    speichern(kanal, d)
    return {"ok": True, "datei": n}


def bild_weg(kanal, did, datei):
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    n = os.path.basename(datei or "")
    if n not in f["bilder"]:
        return {"ok": False, "fehler": "Bild unbekannt"}
    f["bilder"] = [x for x in f["bilder"] if x != n]
    speichern(kanal, d)
    _weg(kanal, [n])
    return {"ok": True}


def bild_vor(kanal, did, datei):
    """Macht ein Bild zum Frontalbild, also zum ersten."""
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    n = os.path.basename(datei or "")
    if n not in f["bilder"]:
        return {"ok": False, "fehler": "Bild unbekannt"}
    f["bilder"] = [n] + [x for x in f["bilder"] if x != n]
    speichern(kanal, d)
    return {"ok": True}


# ---------- Besetzung ----------

def dabei_setzen(kanal, did, an):
    """Hakt einen Avatar fuer dieses Video an oder ab."""
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Avatar unbekannt"}
    if not an:
        d["besetzung"] = [x for x in d["besetzung"] if x != f["id"]]
        speichern(kanal, d)
        return {"ok": True}
    if f["id"] in d["besetzung"]:
        return {"ok": True}
    if not [n for n in f["bilder"] if os.path.exists(datei_pfad(kanal, n))]:
        return {"ok": False, "fehler":
                "%s hat noch kein Bild. Lad erst eins hoch." % f["name"]}
    if len(d["besetzung"]) >= BESETZUNG_MAX:
        return {"ok": False, "fehler":
                "Hoechstens %d Avatare gleichzeitig - das Videomodell nimmt "
                "mit dem Hintergrundbild nur vier Referenzen." % BESETZUNG_MAX}
    d["besetzung"].append(f["id"])
    speichern(kanal, d)
    return {"ok": True}


def _stand(kanal):
    """Je angehaktem Avatar: (id, lage, text). Lage ist ok oder kaputt."""
    d = laden(kanal)
    raus = []
    for did in d["besetzung"]:
        f = _finde(d, did)
        if f is None:
            continue
        if not [n for n in f["bilder"] if os.path.exists(datei_pfad(kanal, n))]:
            raus.append((did, "kaputt", "%s hat kein Bild mehr" % f["name"]))
            continue
        raus.append((did, "ok", f["name"]))
    return raus


def besetzung(kanal, nur=None):
    """Die angehakten Avatare, in der Reihenfolge der Besetzung.

    Je Eintrag: id, name, bilder (ganze Pfade). Avatare ohne brauchbares
    Bild fallen weg.

    Mit "nur" (Liste von ids) kommen nur diese zurueck, und zwar in der
    Reihenfolge, in der sie dort stehen - in einer Szene steht so die
    sprechende Figur vorn und bekommt das zusaetzliche Referenzbild.
    Was nicht angehakt ist, wird ignoriert; eine leere oder unbekannte
    Liste heisst "die ganze Besetzung".
    """
    d = laden(kanal)
    reihe = list(d["besetzung"])
    if nur:
        gewaehlt = [x for x in nur if x in d["besetzung"]]
        if gewaehlt:
            reihe = gewaehlt
    raus = []
    for did in reihe:
        f = _finde(d, did)
        if f is None:
            continue
        bilder = [datei_pfad(kanal, n) for n in f["bilder"]
                  if os.path.exists(datei_pfad(kanal, n))]
        if not bilder:
            continue
        raus.append({"id": f["id"], "name": f["name"], "bilder": bilder})
    return raus


def bereit(kanal):
    """(ok, Grund) - ob die Besetzung fuer einen Referenzclip reicht.

    Ein angehakter Avatar ohne Bild ist ein Fehler und nicht einfach einer
    weniger: sonst laeuft das Video still mit einer Figur weniger durch,
    und das faellt erst am Ende auf.
    """
    st = _stand(kanal)
    kaputt = [t for _d, lage, t in st if lage == "kaputt"]
    if kaputt:
        return False, ". ".join(kaputt)
    if not [t for _d, lage, t in st if lage == "ok"]:
        return False, ("Kein Avatar angehakt. Leg im Reiter Avatare eine Figur "
                       "an, lad ein paar Bilder hoch und hak sie an.")
    return True, ""


def prompt_vorspann(kanal, hintergrund=True, nur=None):
    """Der Satz, der dem Modell sagt, wer wer ist.

    Das Videomodell spricht die Referenzen als @Element1, @Element2 und
    @Image1 an. Ohne diesen Vorspann weiss es nicht, welches Bild welche
    Figur ist, und die Regieanweisung mit den Namen laeuft ins Leere.

    "nur" schraenkt auf die Avatare einer Szene ein.
    """
    teile = []
    for i, x in enumerate(besetzung(kanal, nur)):
        teile.append("@Element%d is %s." % (i + 1, x["name"]))
    if hintergrund:
        teile.append("@Image1 is the background scene they are standing in.")
    return " ".join(teile)


# ---------- fuer das Dashboard ----------

def fuer_anzeige(kanal):
    d = laden(kanal)
    raus = []
    for f in d["darsteller"]:
        bilder = []
        for n in f["bilder"]:
            p = datei_pfad(kanal, n)
            bilder.append({"datei": n, "da": os.path.exists(p),
                           "groesse": os.path.getsize(p) if os.path.exists(p) else 0})
        raus.append({"id": f["id"], "name": f["name"],
                     "bilder": bilder, "voll": len(bilder) >= BILDER_MAX,
                     "dabei": f["id"] in d["besetzung"]})
    ok, grund = bereit(kanal)
    return {"darsteller": raus, "besetzung": list(d["besetzung"]),
            "max": BESETZUNG_MAX, "bilder_max": BILDER_MAX,
            "anzahl": len(d["besetzung"]),
            "bereit": ok, "grund": grund,
            "vorspann": prompt_vorspann(kanal)}


# ---------- Nachtrag d2: Stimme je Avatar, dazu reine Sprecher ----------
#
# Bisher musste ein Eintrag in der Stimmenliste unter Einstellungen
# genauso heissen wie der Avatar - ein unsichtbarer Trick, den niemand
# ahnt. Jetzt steht die Stimme beim Avatar selbst.
#
# Dazu gibt es Eintraege ohne Bilder: reine Sprecher. Die koennen in
# jeder Szene reden ("Sprecher Mann: ...") und tauchen nie im Bild
# auf. art ist "avatar" oder "sprecher".

_d2_laden_alt = laden


def laden(kanal):
    d = _d2_laden_alt(kanal)
    for f in d["darsteller"]:
        f.setdefault("stimme", "")
        f.setdefault("art", "sprecher" if not f.get("bilder") else "avatar")
    # Sprecher gehoeren nie in die Besetzung - sie sind nie im Bild.
    ids = set(f["id"] for f in d["darsteller"] if f.get("art") != "sprecher")
    d["besetzung"] = [x for x in d.get("besetzung") or [] if x in ids]
    return d


_d2_aendern_alt = aendern


def aendern(kanal, did, feld, wert):
    if feld != "stimme":
        return _d2_aendern_alt(kanal, did, feld, wert)
    d = laden(kanal)
    f = _finde(d, did)
    if f is None:
        return {"ok": False, "fehler": "Eintrag unbekannt"}
    f["stimme"] = str(wert or "").strip()[:80]
    speichern(kanal, d)
    return {"ok": True}


def sprecher_anlegen(kanal, name):
    """Ein Eintrag, der nur redet und nie im Bild steht."""
    d = laden(kanal)
    w = str(name or "").strip()[:40]
    if not w:
        return {"ok": False, "fehler": "Name darf nicht leer sein"}
    if any(x["name"].lower() == w.lower() for x in d["darsteller"]):
        return {"ok": False, "fehler": "Gibt es schon"}
    benutzt = set(x["id"] for x in d["darsteller"])
    d["darsteller"].append({"id": _neue_id(benutzt), "name": w,
                            "bilder": [], "stimme": "", "art": "sprecher"})
    speichern(kanal, d)
    return {"ok": True}


def stimme_von(kanal, name):
    """Die beim Avatar oder Sprecher hinterlegte Stimm-ID, sonst ''."""
    if not str(name or "").strip():
        return ""
    try:
        for f in laden(kanal).get("darsteller") or []:
            if (f.get("name") or "").strip().lower() == str(name).strip().lower():
                return (f.get("stimme") or "").strip()
    except Exception:
        pass
    return ""


# ---------- Nachtrag d8: Stimme und Art ueberleben das Laden ----------
#
# laden() liest die Datei nicht einfach ein, es baut jeden Eintrag neu
# auf - mit genau den Feldern, die es kennt. stimme und art kennt es
# nicht. Gespeichert wurden sie also richtig, waren beim naechsten Laden
# aber wieder weg. Im Dashboard sprang die Stimmenauswahl deshalb sofort
# auf "Kanalstimme" zurueck, und ein Sprecher wurde wieder zum Avatar.
#
# Hier werden beide Felder aus der Datei nachgereicht: erst ueber die id,
# sonst ueber den Namen - Namen sind eindeutig.

_d8_laden_alt = laden


def _d8_roh(kanal):
    try:
        with open(_pfad(kanal), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return {}, {}
    if not isinstance(d, dict):
        return {}, {}
    nach_id, nach_name = {}, {}
    for f in d.get("darsteller") or []:
        if not isinstance(f, dict):
            continue
        satz = {}
        for feld in ("stimme", "art"):
            if f.get(feld):
                satz[feld] = f[feld]
        if not satz:
            continue
        i = str(f.get("id") or "").strip()
        n = str(f.get("name") or "").strip().lower()
        if i:
            nach_id[i] = satz
        if n:
            nach_name[n] = satz
    return nach_id, nach_name


def _d8_besetzung_roh(kanal):
    try:
        with open(_pfad(kanal), encoding="utf-8") as f:
            d = json.load(f)
        return [str(x) for x in (d.get("besetzung") or []) if isinstance(x, str)]
    except Exception:
        return []


def laden(kanal):
    d = _d8_laden_alt(kanal)
    nach_id, nach_name = _d8_roh(kanal)
    for f in d.get("darsteller") or []:
        satz = (nach_id.get(str(f.get("id") or ""))
                or nach_name.get(str(f.get("name") or "").strip().lower()) or {})
        for feld, wert in satz.items():
            f[feld] = wert
    # Der Vorgaenger hat die Besetzung gefiltert, als art noch geraten war:
    # ein Avatar ohne Bilder galt dort als Sprecher und flog raus. Darum
    # wird sie hier aus der Datei nachgezogen, jetzt mit dem richtigen art.
    erlaubt = set(f["id"] for f in d["darsteller"] if f.get("art") != "sprecher")
    bes = [x for x in (d.get("besetzung") or []) if x in erlaubt]
    for x in _d8_besetzung_roh(kanal):
        if x in erlaubt and x not in bes:
            bes.append(x)
    d["besetzung"] = bes[:BESETZUNG_MAX]
    return d
