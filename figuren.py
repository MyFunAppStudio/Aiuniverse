# -*- coding: utf-8 -*-
"""Feste Figuren je Kanal: Name, Stimme, freigestellte Posen."""
import json, os, re, subprocess, time

import szenen

BASIS = os.path.dirname(os.path.abspath(__file__))
REGELN = os.path.join(BASIS, "regeln")

PLAETZE = [["links_unten", "links unten"], ["mitte_unten", "mitte unten"],
           ["rechts_unten", "rechts unten"], ["links_oben", "links oben"],
           ["mitte", "Bildmitte"], ["rechts_oben", "rechts oben"]]
PLATZ_NAMEN = dict(PLAETZE)


def _key(kanal):
    if isinstance(kanal, dict):
        return kanal.get("_key") or kanal.get("id") or ""
    return str(kanal or "")


def _pfad(kanal):
    return os.path.join(REGELN, "figuren_%s.json" % _key(kanal))


def ordner(kanal):
    p = os.path.join(szenen.ordner(kanal), "figuren")
    os.makedirs(p, exist_ok=True)
    return p


def datei_pfad(kanal, datei):
    return os.path.join(ordner(kanal), os.path.basename(datei or ""))


def laden(kanal):
    try:
        with open(_pfad(kanal), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    sauber = []
    for f in d.get("figuren", []):
        if not isinstance(f, dict) or not (f.get("name") or "").strip():
            continue
        f["name"] = f["name"].strip()
        f.setdefault("stimme", "")
        f.setdefault("beschreibung", "")
        posen = []
        for p in f.get("posen", []):
            if isinstance(p, dict) and p.get("datei"):
                p.setdefault("name", "Pose")
                posen.append(p)
        f["posen"] = posen
        sauber.append(f)
    return {"figuren": sauber}


def speichern(kanal, d):
    os.makedirs(REGELN, exist_ok=True)
    with open(_pfad(kanal), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _finde(d, name):
    name = (name or "").strip().lower()
    for i, f in enumerate(d["figuren"]):
        if f["name"].lower() == name:
            return i
    return -1


def anlegen(kanal, name):
    d = laden(kanal)
    name = (name or "").strip()[:40]
    if not name:
        return {"ok": False, "fehler": "Name fehlt"}
    if _finde(d, name) >= 0:
        return {"ok": False, "fehler": "Gibt es schon"}
    d["figuren"].append({"name": name, "stimme": "", "beschreibung": "",
                         "bewegung": "bewegt", "posen": []})
    speichern(kanal, d)
    return {"ok": True}


def aendern(kanal, name, feld, wert):
    d = laden(kanal)
    i = _finde(d, name)
    if i < 0:
        return {"ok": False, "fehler": "Figur unbekannt"}
    if feld == "name":
        neu = str(wert or "").strip()[:40]
        if not neu:
            return {"ok": False, "fehler": "Name darf nicht leer sein"}
        if neu.lower() != name.lower() and _finde(d, neu) >= 0:
            return {"ok": False, "fehler": "Gibt es schon"}
        d["figuren"][i]["name"] = neu
    elif feld == "bewegung":
        w = str(wert or "").strip().lower()
        if w not in BEW_NAMEN:
            return {"ok": False, "fehler": "Unbekannt"}
        d["figuren"][i]["bewegung"] = w
    elif feld in ("stimme", "beschreibung"):
        d["figuren"][i][feld] = str(wert or "").strip()[:300]
    else:
        return {"ok": False, "fehler": "Feld unbekannt"}
    speichern(kanal, d)
    return {"ok": True}


def entfernen(kanal, name):
    d = laden(kanal)
    i = _finde(d, name)
    if i < 0:
        return {"ok": False, "fehler": "Figur unbekannt"}
    for p in d["figuren"][i].get("posen", []):
        try:
            os.remove(datei_pfad(kanal, p["datei"]))
        except Exception:
            pass
    d["figuren"].pop(i)
    speichern(kanal, d)
    return {"ok": True}


def pose_dazu(kanal, name, datei, posenname=""):
    d = laden(kanal)
    i = _finde(d, name)
    if i < 0:
        return {"ok": False, "fehler": "Figur unbekannt"}
    d["figuren"][i]["posen"].append({
        "datei": os.path.basename(datei),
        "name": (posenname or "").strip()[:30] or ("Pose %d" % (len(d["figuren"][i]["posen"]) + 1))})
    speichern(kanal, d)
    return {"ok": True}


def pose_weg(kanal, name, datei):
    d = laden(kanal)
    i = _finde(d, name)
    if i < 0:
        return {"ok": False, "fehler": "Figur unbekannt"}
    vorher = len(d["figuren"][i]["posen"])
    d["figuren"][i]["posen"] = [p for p in d["figuren"][i]["posen"]
                                if p["datei"] != os.path.basename(datei)]
    if len(d["figuren"][i]["posen"]) == vorher:
        return {"ok": False, "fehler": "Pose unbekannt"}
    speichern(kanal, d)
    try:
        os.remove(datei_pfad(kanal, datei))
    except Exception:
        pass
    return {"ok": True}


BEWEGUNGEN = [["statisch", "steht still"], ["bewegt", "atmet und wippt"],
              ["animiert", "Animationsschleife"]]
BEW_NAMEN = [a[0] for a in BEWEGUNGEN]
CLIP_ENDUNGEN = (".mov", ".webm", ".mp4", ".gif", ".m4v")


def pose_art(datei):
    """bild oder clip, nach der Dateiendung."""
    return "clip" if str(datei or "").lower().endswith(CLIP_ENDUNGEN) else "bild"


def pose_info(kanal, figur, posenname="", wie=""):
    """Pfad und Art der passenden Pose. Bei 'animiert' bevorzugt eine Schleife."""
    f = holen(kanal, figur)
    if not f or not f.get("posen"):
        return None
    posen = f["posen"]
    gesucht = (posenname or "").strip().lower()
    if gesucht:
        for p in posen:
            if (p.get("name") or "").strip().lower() == gesucht:
                return {"pfad": datei_pfad(kanal, p["datei"]), "art": pose_art(p["datei"])}
    if (wie or "").strip().lower() == "animiert":
        for p in posen:
            if pose_art(p["datei"]) == "clip":
                return {"pfad": datei_pfad(kanal, p["datei"]), "art": "clip"}
    for p in posen:
        if pose_art(p["datei"]) == "bild":
            return {"pfad": datei_pfad(kanal, p["datei"]), "art": "bild"}
    p = posen[0]
    return {"pfad": datei_pfad(kanal, p["datei"]), "art": pose_art(p["datei"])}


def annehmen_schleife(kanal, datei, posenname=""):
    """Nimmt eine bewegte Figur an: wandelt in MOV mit Transparenz um."""
    quelle = datei_pfad(kanal, datei)
    if not os.path.exists(quelle):
        return {"ok": False, "fehler": "Datei nicht da"}
    stamm = re.sub(r"[^a-z0-9_-]+", "_",
                   os.path.splitext(os.path.basename(datei))[0].lower())[:26] or "figur"
    name = "%s_schleife_%s.mov" % (stamm, time.strftime("%H%M%S"))
    ziel = datei_pfad(kanal, name)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-t", "8", "-i", str(quelle), "-an",
                        "-vf", "format=rgba,scale=-2:'min(ih,900)'",
                        "-c:v", "qtrle", "-pix_fmt", "argb", str(ziel)],
                       capture_output=True, text=True)
    def weg(*pfade):
        for x in pfade:
            try:
                os.remove(x)
            except Exception:
                pass
    if r.returncode or not os.path.exists(ziel):
        weg(quelle, ziel)
        return {"ok": False, "fehler": "Umwandeln ging nicht"}
    if not _wirklich_frei(ziel):
        weg(quelle, ziel)
        return {"ok": False, "fehler": "Kein durchsichtiger Hintergrund. "
                                       "Gebraucht wird MOV oder GIF mit Transparenz."}
    weg(quelle)
    vorschau_bauen(kanal, name)
    return {"ok": True, "datei": name, "wie": "Animationsschleife uebernommen"}


def vorschau_name(datei):
    return os.path.splitext(os.path.basename(datei or ""))[0] + "_vorschau.png"


def vorschau_bauen(kanal, datei):
    """Standbild einer Schleife, damit das Dashboard etwas anzeigen kann."""
    quelle = datei_pfad(kanal, datei)
    ziel = datei_pfad(kanal, vorschau_name(datei))
    if os.path.exists(ziel):
        return ziel
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(quelle),
                        "-frames:v", "1", "-vf", "format=rgba", str(ziel)],
                       capture_output=True)
    return ziel if (r.returncode == 0 and os.path.exists(ziel)) else None


def vorschau_fuer(kanal, datei):
    """Was das Dashboard als Bildchen laden soll."""
    if pose_art(datei) != "clip":
        return datei
    v = vorschau_name(datei)
    if os.path.exists(datei_pfad(kanal, v)):
        return v
    return v if vorschau_bauen(kanal, datei) else datei


def holen(kanal, name):
    d = laden(kanal)
    i = _finde(d, name)
    return d["figuren"][i] if i >= 0 else None


def pose_pfad(kanal, figur, posenname=""):
    """Pfad zur gewuenschten Pose, sonst zur ersten."""
    f = holen(kanal, figur)
    if not f or not f.get("posen"):
        return None
    gesucht = (posenname or "").strip().lower()
    for p in f["posen"]:
        if gesucht and p["name"].strip().lower() == gesucht:
            return datei_pfad(kanal, p["datei"])
    return datei_pfad(kanal, f["posen"][0]["datei"])


def fuer_anzeige(kanal):
    d = laden(kanal)
    raus = []
    for f in d["figuren"]:
        posen = []
        for p in f["posen"]:
            pfad = datei_pfad(kanal, p["datei"])
            a = pose_art(p["datei"])
            posen.append({"name": p["name"], "datei": p["datei"], "art": a,
                          "vorschau": vorschau_fuer(kanal, p["datei"]),
                          "da": os.path.exists(pfad),
                          "frei": os.path.exists(pfad) and _wirklich_frei(pfad)})
        raus.append({"name": f["name"], "stimme": f.get("stimme", ""),
                     "bewegung": (f.get("bewegung") or "bewegt"),
                     "hat_schleife": any(x["art"] == "clip" for x in posen),
                     "beschreibung": f.get("beschreibung", ""), "posen": posen})
    return {"figuren": raus, "plaetze": [list(x) for x in PLAETZE],
            "bewegungen": [list(x) for x in BEWEGUNGEN]}


# ---------- Hintergrund entfernen ----------
def _fleck(pfad, x, y):
    """Mittlere Farbe eines kleinen Flecks, als (r, g, b)."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(pfad),
         "-vf", "crop=iw*0.06:ih*0.06:%s:%s,scale=1:1" % (x, y),
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    d = r.stdout or b""
    return (d[0], d[1], d[2]) if len(d) >= 3 else None


def _abstand(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def freistellen(kanal, datei, aehnlich=0.17):
    """Einfarbigen Hintergrund durchsichtig machen. Neue Datei, Original bleibt."""
    quelle = datei_pfad(kanal, datei)
    if not os.path.exists(quelle):
        return {"ok": False, "fehler": "Datei nicht da"}
    ecken = [_fleck(quelle, "0", "0"), _fleck(quelle, "iw*0.94", "0"),
             _fleck(quelle, "0", "ih*0.94"), _fleck(quelle, "iw*0.94", "ih*0.94")]
    ecken = [e for e in ecken if e]
    if len(ecken) < 4:
        return {"ok": False, "fehler": "Bild nicht lesbar"}
    mitte = tuple(sum(e[i] for e in ecken) // len(ecken) for i in range(3))
    if max(_abstand(e, mitte) for e in ecken) > 34:
        return {"ok": False, "fehler":
                "Der Hintergrund ist nicht einfarbig. Erzeuge die Figur vor einer "
                "glatten Flaeche oder lade ein schon freigestelltes PNG hoch."}
    stamm = os.path.splitext(os.path.basename(datei))[0][:34]
    ziel_name = "%s_frei_%s.png" % (stamm, time.strftime("%H%M%S"))
    ziel = datei_pfad(kanal, ziel_name)
    farbe = "0x%02X%02X%02X" % mitte
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(quelle),
         "-vf", "colorkey=%s:%.2f:0.10,format=rgba" % (farbe, aehnlich),
         "-frames:v", "1", str(ziel)], capture_output=True, text=True)
    if r.returncode or not os.path.exists(ziel):
        return {"ok": False, "fehler": (r.stderr or "")[-160:] or "ffmpeg"}
    zuschneiden(ziel)
    return {"ok": True, "datei": ziel_name, "farbe": farbe}


def zuschneiden(pfad):
    """Durchsichtigen Rand wegschneiden, damit die Figur buendig sitzt."""
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(pfad),
         "-vf", "alphaextract,cropdetect=limit=0:round=2:skip=0",
         "-frames:v", "1", "-f", "null", "-"], capture_output=True, text=True)
    treffer = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr or "")
    if not treffer:
        return False
    w, hh, x, y = (int(v) for v in treffer[-1])
    if w < 8 or hh < 8:
        return False
    tmp = str(pfad) + ".tmp.png"
    s = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(pfad),
                        "-vf", "crop=%d:%d:%d:%d" % (w, hh, x, y),
                        "-frames:v", "1", tmp], capture_output=True)
    if s.returncode or not os.path.exists(tmp):
        return False
    os.replace(tmp, str(pfad))
    return True


def pose_freistellen(kanal, name, datei):
    e = freistellen(kanal, datei)
    if not e.get("ok"):
        return e
    d = laden(kanal)
    i = _finde(d, name)
    if i < 0:
        return {"ok": False, "fehler": "Figur unbekannt"}
    for p in d["figuren"][i]["posen"]:
        if p["datei"] == os.path.basename(datei):
            alt = p["datei"]
            p["datei"] = e["datei"]
            speichern(kanal, d)
            try:
                os.remove(datei_pfad(kanal, alt))
            except Exception:
                pass
            return {"ok": True, "datei": e["datei"]}
    return {"ok": False, "fehler": "Pose unbekannt"}


# ---------- Pruefung beim Hochladen (Patch S11) ----------
def hat_alpha(pfad):
    """Hat das Bild einen Transparenzkanal?"""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=pix_fmt", "-of", "default=nw=1:nk=1",
                        str(pfad)], capture_output=True, text=True)
    art = (r.stdout or "").strip().lower()
    return "a" in art.replace("yuv", "").replace("gray", "")


def _wirklich_frei(pfad):
    """Sind an den Raendern wirklich durchsichtige Stellen?"""
    if not hat_alpha(pfad):
        return False
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(pfad),
                        "-vf", "alphaextract,scale=1:1", "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
    d = r.stdout or b""
    return bool(d) and d[0] < 250


def annehmen(kanal, datei, posenname=""):
    """Nimmt eine Pose nur an, wenn sie freigestellt ist oder freigestellt werden kann."""
    pfad = datei_pfad(kanal, datei)
    if not os.path.exists(pfad):
        return {"ok": False, "fehler": "Datei nicht da"}
    if _wirklich_frei(pfad):
        zuschneiden(pfad)
        return {"ok": True, "datei": datei, "wie": "war schon freigestellt"}
    e = freistellen(kanal, datei)
    if e.get("ok"):
        try:
            os.remove(pfad)
        except Exception:
            pass
        return {"ok": True, "datei": e["datei"], "wie": "Hintergrund entfernt"}
    try:
        os.remove(pfad)
    except Exception:
        pass
    return {"ok": False, "fehler": e.get("fehler") or "Freistellen nicht moeglich"}
