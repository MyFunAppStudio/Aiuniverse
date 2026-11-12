# -*- coding: utf-8 -*-
"""Eigene Szenen je Kanal: Bilder, Clips, Texte, eigenes Lied."""
import json, os, re, time

BASIS = os.path.dirname(os.path.abspath(__file__))
REGELN = os.path.join(BASIS, "regeln")
EIGENE = os.path.join(BASIS, "eigene")

BILD_ARTEN = (".jpg", ".jpeg", ".png", ".webp")
CLIP_ARTEN = (".mp4", ".mov", ".m4v", ".webm")
TON_ARTEN = (".mp3", ".wav", ".m4a", ".aac", ".ogg")

BEWEGUNGEN = ["auto", "aus", "rein", "raus", "links", "rechts", "hoch", "runter"]
PASSEN = ["fuellen", "ganz"]
PLAETZE = ["links_unten", "mitte_unten", "rechts_unten",
           "links_oben", "mitte", "rechts_oben"]
STIMMUNGEN = [["", "wie beim Kanal"], ["ruhig", "ruhig"], ["sachlich", "sachlich"],
              ["normal", "normal"], ["lebendig", "lebendig"], ["dramatisch", "dramatisch"]]
ENERGIE = {"ruhig": 0.15, "sachlich": 0.35, "normal": 0.55,
           "lebendig": 0.75, "dramatisch": 0.92}
PASSEN_NAME = {"fuellen": "Rahmen fuellen, schneidet Raender",
               "ganz": "ganz zeigen, weicher Rand"}
BEWEGUNG_NAME = {"auto": "automatisch", "aus": "ohne Bewegung", "rein": "Zoom rein",
                 "raus": "Zoom raus", "links": "Schwenk links", "rechts": "Schwenk rechts",
                 "hoch": "Schwenk hoch", "runter": "Schwenk runter"}


FIGUR_BEWEGUNGEN = [["", "wie bei der Figur"], ["statisch", "steht still"],
                    ["bewegt", "atmet und wippt"], ["animiert", "Animationsschleife"]]
FIGUR_BEW_NAMEN = [a[0] for a in FIGUR_BEWEGUNGEN]
FELDER = ["text", "gesprochen", "untertitel", "sekunden", "bewegung", "figur",
          "ki_animation", "musik", "passen", "stimmung", "pose", "platz",
          "figur_groesse", "figur_bewegung"]


def _key(kanal):
    if isinstance(kanal, dict):
        return kanal.get("_key") or kanal.get("id") or ""
    return str(kanal or "")


def _pfad(kanal):
    return os.path.join(REGELN, "szenen_%s.json" % _key(kanal))


def ordner(kanal):
    p = os.path.join(EIGENE, _key(kanal))
    os.makedirs(p, exist_ok=True)
    return p


def laden(kanal):
    try:
        with open(_pfad(kanal), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("szenen", [])
    d.setdefault("musik", "")
    sauber = []
    for s in d["szenen"]:
        if not isinstance(s, dict) or not s.get("datei"):
            continue
        s.setdefault("id", "s%d" % (len(sauber) + 1))
        s.setdefault("text", "")
        s.setdefault("gesprochen", True)
        s.setdefault("untertitel", True)
        s.setdefault("sekunden", 0)
        if s.get("bewegung") not in BEWEGUNGEN:
            s["bewegung"] = "auto"
        s.setdefault("ki_animation", False)
        s.setdefault("figur", "")
        if s.get("passen") not in PASSEN:
            s["passen"] = "fuellen"
        if s.get("stimmung") not in ENERGIE:
            s["stimmung"] = ""
        s.setdefault("pose", "")
        if s.get("figur_bewegung") not in FIGUR_BEW_NAMEN:
            s["figur_bewegung"] = ""
        if s.get("platz") not in PLAETZE:
            s["platz"] = "rechts_unten"
        try:
            s["figur_groesse"] = max(10, min(100, int(s.get("figur_groesse") or 55)))
        except Exception:
            s["figur_groesse"] = 55
        if s.get("musik") in (None, "", "auto"):
            s["musik"] = "auto"
        sauber.append(s)
    d["szenen"] = sauber
    return d


def speichern(kanal, d):
    os.makedirs(REGELN, exist_ok=True)
    with open(_pfad(kanal), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def art(name):
    e = os.path.splitext(name or "")[1].lower()
    if e in BILD_ARTEN:
        return "bild"
    if e in CLIP_ARTEN:
        return "clip"
    if e in TON_ARTEN:
        return "ton"
    return ""


def sauberer_name(name):
    name = os.path.basename(name or "datei")
    name = name.replace("\\", "_").replace("/", "_")
    stamm, endung = os.path.splitext(name)
    stamm = re.sub(r"[^A-Za-z0-9_.-]+", "_", stamm)[:40] or "datei"
    endung = re.sub(r"[^A-Za-z0-9.]+", "", endung).lower()[:6]
    return "%s_%s%s" % (stamm, time.strftime("%H%M%S"), endung)


def datei_pfad(kanal, datei):
    return os.path.join(ordner(kanal), os.path.basename(datei or ""))


def neue_id(d):
    n = 1
    da = set(s.get("id") for s in d.get("szenen", []))
    while ("s%d" % n) in da:
        n += 1
    return "s%d" % n


def hinzufuegen(kanal, datei, text=""):
    d = laden(kanal)
    a = art(datei)
    if a not in ("bild", "clip"):
        return {"ok": False, "fehler": "Nur Bilder oder Videoclips"}
    d["szenen"].append({"id": neue_id(d), "datei": os.path.basename(datei),
                        "typ": a, "text": text or "",
                        "gesprochen": True, "untertitel": True, "sekunden": 0,
                        "bewegung": "auto", "ki_animation": False, "figur": "", "passen": "fuellen", "stimmung": "", "pose": "",
                        "platz": "rechts_unten", "figur_groesse": 55,
                        "musik": "auto"})
    speichern(kanal, d)
    return {"ok": True}


def _index(d, sid):
    for i, s in enumerate(d.get("szenen", [])):
        if s.get("id") == sid:
            return i
    return -1


def aendern(kanal, sid, feld, wert):
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    if feld == "text":
        d["szenen"][i]["text"] = str(wert or "")
    elif feld in ("gesprochen", "untertitel"):
        d["szenen"][i][feld] = bool(wert)
    elif feld == "bewegung":
        if str(wert) not in BEWEGUNGEN:
            return {"ok": False, "fehler": "Bewegung unbekannt"}
        d["szenen"][i]["bewegung"] = str(wert)
    elif feld == "musik":
        w = str(wert or "").strip().replace(",", ".").replace("%", "")
        if w == "" or w.lower() in ("auto", "automatisch"):
            d["szenen"][i]["musik"] = "auto"
        else:
            try:
                d["szenen"][i]["musik"] = max(0.0, min(150.0, float(w)))
            except Exception:
                return {"ok": False, "fehler": "Zahl oder leer lassen"}
    elif feld == "pose":
        d["szenen"][i]["pose"] = str(wert or "").strip()[:30]
    elif feld == "platz":
        if str(wert) not in PLAETZE:
            return {"ok": False, "fehler": "Unbekannt"}
        d["szenen"][i]["platz"] = str(wert)
    elif feld == "figur_groesse":
        try:
            d["szenen"][i]["figur_groesse"] = max(10, min(100, int(float(str(wert).replace(",", ".")))))
        except Exception:
            return {"ok": False, "fehler": "Zahl zwischen 10 und 100"}
    elif feld == "stimmung":
        w = str(wert or "")
        if w and w not in ENERGIE:
            return {"ok": False, "fehler": "Unbekannt"}
        d["szenen"][i]["stimmung"] = w
    elif feld == "passen":
        if str(wert) not in PASSEN:
            return {"ok": False, "fehler": "Unbekannt"}
        d["szenen"][i]["passen"] = str(wert)
    elif feld == "figur":
        d["szenen"][i]["figur"] = str(wert or "").strip()[:40]
    elif feld == "figur_bewegung":
        w = str(wert or "").strip()
        if w not in FIGUR_BEW_NAMEN:
            return {"ok": False, "fehler": "Unbekannt"}
        d["szenen"][i]["figur_bewegung"] = w
    elif feld == "ki_animation":
        d["szenen"][i]["ki_animation"] = bool(wert)
    elif feld == "sekunden":
        try:
            d["szenen"][i]["sekunden"] = max(0.0, min(120.0, float(str(wert).replace(",", "."))))
        except Exception:
            d["szenen"][i]["sekunden"] = 0
    else:
        return {"ok": False, "fehler": "Feld unbekannt"}
    speichern(kanal, d)
    return {"ok": True}


def verschieben(kanal, sid, richtung):
    d = laden(kanal)
    i = _index(d, sid)
    j = i + (-1 if richtung == "hoch" else 1)
    if i < 0 or j < 0 or j >= len(d["szenen"]):
        return {"ok": False, "fehler": "geht nicht"}
    d["szenen"][i], d["szenen"][j] = d["szenen"][j], d["szenen"][i]
    speichern(kanal, d)
    return {"ok": True}


def entfernen(kanal, sid):
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    datei = d["szenen"][i].get("datei")
    d["szenen"].pop(i)
    speichern(kanal, d)
    if datei and not any(s.get("datei") == datei for s in d["szenen"]) and d.get("musik") != datei:
        try:
            os.remove(datei_pfad(kanal, datei))
        except Exception:
            pass
    return {"ok": True}


def musik_setzen(kanal, datei):
    d = laden(kanal)
    alt = d.get("musik")
    d["musik"] = os.path.basename(datei or "")
    speichern(kanal, d)
    if alt and alt != d["musik"] and not any(s.get("datei") == alt for s in d["szenen"]):
        try:
            os.remove(datei_pfad(kanal, alt))
        except Exception:
            pass
    return {"ok": True}


def geschaetzte_sekunden(text):
    woerter = len([w for w in re.split(r"\s+", (text or "").strip()) if w])
    return max(2.0, round(woerter / 2.6 + 0.6, 1)) if woerter else 3.0


def fuer_anzeige(kanal):
    d = laden(kanal)
    raus = []
    for s in d["szenen"]:
        p = datei_pfad(kanal, s["datei"])
        raus.append({
            "figur_bewegung": s.get("figur_bewegung", ""),
            "id": s["id"], "datei": s["datei"], "typ": s.get("typ") or art(s["datei"]),
            "text": s.get("text", ""), "gesprochen": bool(s.get("gesprochen")),
            "untertitel": bool(s.get("untertitel")),
            "sekunden": s.get("sekunden") or 0,
            "bewegung": s.get("bewegung", "auto"),
            "ki_animation": bool(s.get("ki_animation")),
            "figur": s.get("figur", ""),
            "passen": s.get("passen", "fuellen"),
            "stimmung": s.get("stimmung", ""),
            "pose": s.get("pose", ""),
            "platz": s.get("platz", "rechts_unten"),
            "figur_groesse": s.get("figur_groesse", 55),
            "musik": s.get("musik", "auto"),
            "vorschlag": geschaetzte_sekunden(s.get("text", "")),
            "da": os.path.exists(p),
            "groesse": (os.path.getsize(p) if os.path.exists(p) else 0),
        })
    return {"szenen": raus, "musik": d.get("musik", ""),
            "bewegungen": [[b, BEWEGUNG_NAME[b]] for b in BEWEGUNGEN],
            "passenarten": [[p, PASSEN_NAME[p]] for p in PASSEN],
            "stimmungen": [list(x) for x in STIMMUNGEN],
            "figur_bewegungen": [list(x) for x in FIGUR_BEWEGUNGEN]}


# ---------- Nachtrag p50: Regie zaehlt nicht mit ----------

import re as _p50_re

_p50_klammern = _p50_re.compile(r"\[[^\]]*\]")
_p50_sek_alt = geschaetzte_sekunden


def _p50_ohne_regie(text):
    """Nimmt die eckigen Klammern samt Inhalt raus - die wird nicht gesprochen."""
    return _p50_klammern.sub(" ", text or "")


def geschaetzte_sekunden(text):
    return _p50_sek_alt(_p50_ohne_regie(text))


# ---------- Nachtrag p90: Datei einer Szene tauschen ----------


def p90_datei_setzen(kanal, sid, datei):
    """Haengt eine andere Datei an eine bestehende Szene.

    aendern() hat eine feste Liste erlaubter Felder, und datei steht
    bewusst nicht darin - sonst koennte man eine Szene aus Versehen auf
    eine Datei zeigen lassen, die es nicht gibt. Darum dieser eigene Weg,
    der vorher nachsieht, ob die Datei wirklich im Ordner liegt.
    """
    name = os.path.basename(str(datei or ""))
    if not name:
        return {"ok": False, "fehler": "Kein Dateiname"}
    a = art(name)
    if a not in ("bild", "clip"):
        return {"ok": False, "fehler": "Nur Bilder oder Videoclips"}
    if not os.path.exists(datei_pfad(kanal, name)):
        return {"ok": False, "fehler": "Die Datei liegt nicht im Szenenordner"}
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    alt = d["szenen"][i].get("datei")
    d["szenen"][i]["datei"] = name
    d["szenen"][i]["typ"] = a
    speichern(kanal, d)
    return {"ok": True, "datei": name, "vorher": alt}


# ---------- Nachtrag r3: Clip und Regie je Szene ----------

_r3_laden_alt = laden
_r3_aendern_alt = aendern
_r3_anzeige_alt = fuer_anzeige

R3_STAENDE = ("", "laeuft", "fertig", "fehler")

if "regie" not in FELDER:
    FELDER.append("regie")


def laden(kanal):
    d = _r3_laden_alt(kanal)
    for s in d["szenen"]:
        s.setdefault("regie", "")
        s.setdefault("clip", "")
        if s.get("clip_stand") not in R3_STAENDE:
            s["clip_stand"] = ""
        s.setdefault("clip_text", "")
        # Ein Clip, dessen Datei nicht mehr da ist, zaehlt nicht
        if s["clip"] and not os.path.exists(datei_pfad(kanal, s["clip"])):
            s["clip"] = ""
            if s["clip_stand"] == "fertig":
                s["clip_stand"] = ""
    return d


def aendern(kanal, sid, feld, wert):
    if feld != "regie":
        return _r3_aendern_alt(kanal, sid, feld, wert)
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    d["szenen"][i]["regie"] = " ".join(str(wert or "").split())[:600]
    speichern(kanal, d)
    return {"ok": True}


def r3_clip_setzen(kanal, sid, datei):
    """Haengt einen fertigen Clip an die Szene. Leer heisst: Clip weg."""
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    name = os.path.basename(str(datei or ""))
    if not name:
        alt = d["szenen"][i].get("clip") or ""
        d["szenen"][i]["clip"] = ""
        d["szenen"][i]["clip_stand"] = ""
        d["szenen"][i]["clip_text"] = ""
        speichern(kanal, d)
        if alt and not any(s.get("clip") == alt for s in d["szenen"]):
            try:
                os.remove(datei_pfad(kanal, alt))
            except Exception:
                pass
        return {"ok": True, "clip": ""}
    if art(name) != "clip":
        return {"ok": False, "fehler": "Das ist kein Videoclip"}
    if not os.path.exists(datei_pfad(kanal, name)):
        return {"ok": False, "fehler": "Die Datei liegt nicht im Szenenordner"}
    alt = d["szenen"][i].get("clip") or ""
    d["szenen"][i]["clip"] = name
    d["szenen"][i]["clip_stand"] = "fertig"
    speichern(kanal, d)
    if alt and alt != name and not any(s.get("clip") == alt for s in d["szenen"]):
        try:
            os.remove(datei_pfad(kanal, alt))
        except Exception:
            pass
    return {"ok": True, "clip": name}


def r3_stand_setzen(kanal, sid, lage, text=""):
    """Haelt fest, wie es dieser Szene gerade ergeht."""
    if lage not in R3_STAENDE:
        return {"ok": False, "fehler": "Stand unbekannt"}
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    d["szenen"][i]["clip_stand"] = lage
    d["szenen"][i]["clip_text"] = str(text or "")[:300]
    speichern(kanal, d)
    return {"ok": True}


def r3_szene(kanal, sid):
    """Die eine Szene, oder None."""
    d = laden(kanal)
    i = _index(d, sid)
    return d["szenen"][i] if i >= 0 else None


def r3_clip_dauer(s):
    """Wie lang der Clip werden soll. Kling nimmt 3 bis 15 ganze Sekunden."""
    try:
        w = float(s.get("sekunden") or 0)
    except Exception:
        w = 0.0
    if w <= 0:
        w = float(geschaetzte_sekunden(s.get("text", "")))
    return int(max(3, min(15, round(w))))


def fuer_anzeige(kanal):
    d = _r3_anzeige_alt(kanal)
    roh = {s["id"]: s for s in laden(kanal)["szenen"]}
    for s in d["szenen"]:
        q = roh.get(s["id"]) or {}
        s["regie"] = q.get("regie", "")
        s["clip"] = q.get("clip", "")
        s["clip_stand"] = q.get("clip_stand", "")
        s["clip_text"] = q.get("clip_text", "")
        s["clip_dauer"] = r3_clip_dauer(q) if q else 5
    return d


# ---------- Nachtrag r6: Schalter je Szene, Versionen, eigene Clips ----------
#
# Drei Dinge auf einmal, weil sie dieselben Felder anfassen:
#
# 1. Je Szene ein Schalter mit drei Stellungen statt der alten Felder figur,
#    pose, platz, figur_groesse und ki_animation. Dazu ein Feld, wer spricht.
# 2. Die letzten drei Fassungen von Bild und Clip bleiben liegen, damit ein
#    misslungener zweiter Versuch den guten ersten nicht vernichtet.
# 3. Ein selbst hochgeladener Clip ueberspringt Bild und Videomodell.

_r6_laden_alt = laden
_r6_aendern_alt = aendern
_r6_anzeige_alt = fuer_anzeige
_r6_datei_setzen_alt = p90_datei_setzen

import subprocess as _r6_sub

R6_MODI = [["avatare", "Avatare im Bild"],
           ["bewegt", "Nur Bild, bewegt"],
           ["still", "Nur Bild, still"]]
R6_MODUS_NAMEN = [a[0] for a in R6_MODI]
R6_SPRICHT = [["sprecher", "Sprecher aus dem Off"],
              ["avatar", "Die Avatare reden"],
              ["niemand", "Niemand, nur Bild und Ton"]]
R6_SPRICHT_NAMEN = [a[0] for a in R6_SPRICHT]
R6_VERSIONEN = 3

for _f in ("modus", "spricht"):
    if _f not in FELDER:
        FELDER.append(_f)


def _r6_modus_aus_alt(s):
    """Welche Schalterstellung zu einer alten Szene passt."""
    if s.get("figur"):
        return "avatare"
    if s.get("ki_animation"):
        return "bewegt"
    return "still"


def laden(kanal):
    d = _r6_laden_alt(kanal)
    for s in d["szenen"]:
        if s.get("modus") not in R6_MODUS_NAMEN:
            s["modus"] = _r6_modus_aus_alt(s)
        if s.get("spricht") not in R6_SPRICHT_NAMEN:
            s["spricht"] = "sprecher" if s.get("gesprochen", True) else "niemand"
        for feld in ("bild_alt", "clip_alt"):
            v = s.get(feld)
            if not isinstance(v, list):
                v = []
            s[feld] = [os.path.basename(str(x)) for x in v
                       if str(x or "").strip()
                       and os.path.exists(datei_pfad(kanal, os.path.basename(str(x))))
                       ][:R6_VERSIONEN]
        s["eigener_clip"] = bool(s.get("eigener_clip")) and bool(s.get("clip"))
        s["clip_veraltet"] = bool(s.get("clip_veraltet")) and bool(s.get("clip"))
    return d


def aendern(kanal, sid, feld, wert):
    if feld not in ("modus", "spricht"):
        return _r6_aendern_alt(kanal, sid, feld, wert)
    w = str(wert or "")
    if w not in (R6_MODUS_NAMEN if feld == "modus" else R6_SPRICHT_NAMEN):
        return {"ok": False, "fehler": "Wert unbekannt"}
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    d["szenen"][i][feld] = w
    if feld == "spricht":
        # Das alte Feld mitfuehren, damit der Zusammenbau es weiter versteht
        d["szenen"][i]["gesprochen"] = (w != "niemand")
    speichern(kanal, d)
    return {"ok": True}


# ---------- Verlauf ----------

def _r6_merken(d, i, feld, name):
    """Legt eine Datei vorn in den Verlauf. Gibt zurueck, was hinten rausfaellt."""
    if not name:
        return []
    v = [x for x in (d["szenen"][i].get(feld) or []) if x != name]
    v.insert(0, name)
    d["szenen"][i][feld] = v[:R6_VERSIONEN]
    return v[R6_VERSIONEN:]


def _r6_benutzt(d, name):
    if not name:
        return True
    if d.get("musik") == name:
        return True
    for s in d["szenen"]:
        if s.get("datei") == name or s.get("clip") == name:
            return True
        if name in (s.get("bild_alt") or []) or name in (s.get("clip_alt") or []):
            return True
    return False


def _r6_aufraeumen(kanal, namen):
    """Loescht Dateien, auf die keine Szene mehr zeigt."""
    if not namen:
        return
    d = laden(kanal)
    for n in namen:
        if _r6_benutzt(d, n):
            continue
        try:
            os.remove(datei_pfad(kanal, n))
        except Exception:
            pass


def p90_datei_setzen(kanal, sid, datei):
    """Wie vorher, aber das bisherige Bild wandert in den Verlauf.

    Ein neues Bild macht einen vorhandenen Clip ungueltig: der waere sonst
    noch vom alten Bild und faellt erst im fertigen Video auf.
    """
    r = _r6_datei_setzen_alt(kanal, sid, datei)
    if not r.get("ok"):
        return r
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return r
    raus = _r6_merken(d, i, "bild_alt", r.get("vorher") or "")
    d["szenen"][i]["bild_alt"] = [x for x in d["szenen"][i]["bild_alt"]
                                  if x != d["szenen"][i].get("datei")]
    if d["szenen"][i].get("clip") and not d["szenen"][i].get("eigener_clip"):
        d["szenen"][i]["clip_veraltet"] = True
    speichern(kanal, d)
    _r6_aufraeumen(kanal, raus)
    return r


def r3_clip_setzen(kanal, sid, datei):
    """Haengt einen fertigen Clip an die Szene. Leer heisst: Clip weg.

    Der bisherige Clip wird nicht mehr geloescht, sondern in den Verlauf
    gelegt - erst wenn er hinten herausfaellt, verschwindet die Datei.
    """
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    name = os.path.basename(str(datei or ""))
    if name:
        if art(name) != "clip":
            return {"ok": False, "fehler": "Das ist kein Videoclip"}
        if not os.path.exists(datei_pfad(kanal, name)):
            return {"ok": False, "fehler": "Die Datei liegt nicht im Szenenordner"}
    alt = d["szenen"][i].get("clip") or ""
    raus = _r6_merken(d, i, "clip_alt", alt) if alt and alt != name else []
    d["szenen"][i]["clip"] = name
    d["szenen"][i]["clip_stand"] = "fertig" if name else ""
    d["szenen"][i]["clip_veraltet"] = False
    if not name:
        d["szenen"][i]["clip_text"] = ""
        d["szenen"][i]["eigener_clip"] = False
    d["szenen"][i]["clip_alt"] = [x for x in (d["szenen"][i].get("clip_alt") or [])
                                  if x != name]
    speichern(kanal, d)
    _r6_aufraeumen(kanal, raus)
    return {"ok": True, "clip": name}


def r6_zurueck(kanal, sid, welche, datei):
    """Schaltet auf eine aeltere Fassung zurueck. welche: bild oder clip."""
    if welche not in ("bild", "clip"):
        return {"ok": False, "fehler": "Unbekannt"}
    name = os.path.basename(str(datei or ""))
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    s = d["szenen"][i]
    feld = "bild_alt" if welche == "bild" else "clip_alt"
    if name not in (s.get(feld) or []):
        return {"ok": False, "fehler": "Diese Fassung gibt es nicht mehr"}
    if not os.path.exists(datei_pfad(kanal, name)):
        return {"ok": False, "fehler": "Die Datei ist weg"}
    jetzt = s.get("datei" if welche == "bild" else "clip") or ""
    s[feld] = [x for x in s[feld] if x != name]
    if jetzt and jetzt != name:
        s[feld].insert(0, jetzt)
        s[feld] = s[feld][:R6_VERSIONEN]
    if welche == "bild":
        s["datei"] = name
        s["typ"] = art(name)
        if s.get("clip") and not s.get("eigener_clip"):
            s["clip_veraltet"] = True
    else:
        s["clip"] = name
        s["clip_stand"] = "fertig"
        s["clip_veraltet"] = False
    speichern(kanal, d)
    return {"ok": True}


# ---------- Eigener Clip ----------

def r6_dauer(pfad):
    """Laenge einer Videodatei in Sekunden, oder 0."""
    try:
        r = _r6_sub.run(["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "csv=p=0", str(pfad)],
                        capture_output=True, text=True)
        return round(float((r.stdout or "0").strip().split(",")[0]), 2)
    except Exception:
        return 0.0


def r6_clip_eigen(kanal, sid, datei):
    """Haengt einen selbst hochgeladenen Clip an die Szene.

    Die Szene ueberspringt dann Bild und Videomodell, und ihre Laenge
    richtet sich nach der Laenge des Videos.
    """
    r = r3_clip_setzen(kanal, sid, datei)
    if not r.get("ok"):
        return r
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return r
    d["szenen"][i]["eigener_clip"] = True
    sek = r6_dauer(datei_pfad(kanal, r.get("clip") or ""))
    if sek > 0:
        d["szenen"][i]["sekunden"] = sek
    speichern(kanal, d)
    r["sekunden"] = sek
    return r


def r6_braucht_clip(s):
    """Soll fuer diese Szene ein Referenzclip erzeugt werden?"""
    if s.get("eigener_clip"):
        return False
    if s.get("modus") != "avatare":
        return False
    return art(s.get("datei") or "") == "bild"


def fuer_anzeige(kanal):
    d = _r6_anzeige_alt(kanal)
    roh = {s["id"]: s for s in laden(kanal)["szenen"]}
    for s in d["szenen"]:
        q = roh.get(s["id"]) or {}
        s["modus"] = q.get("modus", "still")
        s["spricht"] = q.get("spricht", "sprecher")
        s["bild_alt"] = q.get("bild_alt", [])
        s["clip_alt"] = q.get("clip_alt", [])
        s["clip_veraltet"] = bool(q.get("clip_veraltet"))
        s["eigener_clip"] = bool(q.get("eigener_clip"))
        s["braucht_clip"] = r6_braucht_clip(q) if q else False
    d["modi"] = [list(x) for x in R6_MODI]
    d["sprichtarten"] = [list(x) for x in R6_SPRICHT]
    d["versionen"] = R6_VERSIONEN
    return d


# ---------- Nachtrag r7: wer in welcher Szene steht ----------
#
# Die Besetzung oben sagt, wer in dieser FOLGE vorkommt. Hier steht, wer
# in der einzelnen SZENE im Bild ist. Leer heisst: die ganze Besetzung.
#
# Das ist nicht nur Bequemlichkeit: Das Videomodell nimmt vier Referenzen
# an, eine davon ist der Hintergrund. Steht eine Figur allein in der Szene,
# bekommt sie drei Bilder von sich statt einem und bleibt sich deutlich
# aehnlicher.

_r7_laden_alt = laden
_r7_aendern_alt = aendern
_r7_anzeige_alt = fuer_anzeige

if "wer" not in FELDER:
    FELDER.append("wer")


def _r7_liste(w):
    if isinstance(w, str):
        w = w.split(",")
    if not isinstance(w, list):
        return []
    raus = []
    for x in w:
        x = str(x or "").strip()
        if x and x not in raus:
            raus.append(x)
    return raus[:8]


def laden(kanal):
    d = _r7_laden_alt(kanal)
    for s in d["szenen"]:
        s["wer"] = _r7_liste(s.get("wer"))
    return d


def aendern(kanal, sid, feld, wert):
    if feld != "wer":
        return _r7_aendern_alt(kanal, sid, feld, wert)
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    d["szenen"][i]["wer"] = _r7_liste(wert)
    speichern(kanal, d)
    return {"ok": True}


def r7_wer_um(kanal, sid, did):
    """Haengt einen Avatar an die Szene an oder nimmt ihn heraus."""
    did = str(did or "").strip()
    if not did:
        return {"ok": False, "fehler": "Avatar fehlt"}
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    w = list(d["szenen"][i].get("wer") or [])
    if did in w:
        w = [x for x in w if x != did]
    else:
        w.append(did)
    d["szenen"][i]["wer"] = w[:8]
    speichern(kanal, d)
    return {"ok": True, "wer": d["szenen"][i]["wer"]}


def fuer_anzeige(kanal):
    d = _r7_anzeige_alt(kanal)
    roh = {s["id"]: s for s in laden(kanal)["szenen"]}
    for s in d["szenen"]:
        s["wer"] = (roh.get(s["id"]) or {}).get("wer", [])
    return d


# ---------- Nachtrag r10: alle Szenen auf einmal weg ----------

def r10_alle_weg(kanal):
    """Leert die Szenenliste. Die Dateien bleiben im Ordner liegen."""
    d = laden(kanal)
    n = len(d.get("szenen") or [])
    d["szenen"] = []
    speichern(kanal, d)
    return {"ok": True, "weg": n}


# ---------- Nachtrag r11: eigenes Feld fuer die Bildbeschreibung ----------
#
# Bisher stand alles in einem Textfeld: gesprochener Satz, Avatartext
# in Anfuehrungszeichen und die Regie in eckigen Klammern. Jetzt gibt
# es drei Felder. "regie" gab es schon, es hatte nur nie eine
# Bedienung; "bild" kommt neu dazu.

if "bild" not in FELDER:
    FELDER.append("bild")

_r11_laden_alt = laden
_r11_aendern_alt = aendern
_r11_anzeige_alt = fuer_anzeige


def laden(kanal):
    d = _r11_laden_alt(kanal)
    for s in d["szenen"]:
        s.setdefault("bild", "")
    return d


def aendern(kanal, sid, feld, wert):
    if feld != "bild":
        return _r11_aendern_alt(kanal, sid, feld, wert)
    d = laden(kanal)
    i = _index(d, sid)
    if i < 0:
        return {"ok": False, "fehler": "Szene unbekannt"}
    d["szenen"][i]["bild"] = " ".join(str(wert or "").split())[:600]
    speichern(kanal, d)
    return {"ok": True}


def fuer_anzeige(kanal):
    d = _r11_anzeige_alt(kanal)
    roh = {s["id"]: s for s in laden(kanal)["szenen"]}
    for s in d["szenen"]:
        s["bild"] = (roh.get(s["id"]) or {}).get("bild", "")
    return d


# ---------- Nachtrag r13: Klammern in die eigenen Felder ----------
#
# Von Claude geschriebene Szenen haben alles in einem Satz stehen:
# gesprochener Text, [BILD: ...] und [BEWEGUNG: ...]. Seit es drei
# Felder gibt, gehoert jedes an seinen Platz - sonst steht im
# Sprechtext Englisch mitten im Satz, und Bildbeschreibung und
# Animationsanweisung bleiben leer.
#
# Aufgeteilt wird nur, was noch nicht aufgeteilt ist: Felder, in denen
# schon etwas steht, bleiben unberuehrt.

import re as _r13_re

R13_GANZ = _r13_re.compile(r"\[([^\[\]]{1,400})\]", _r13_re.S)
R13_OFFEN = _r13_re.compile(r"\[([^\[\]]{1,400})$", _r13_re.S)
R13_BILD = _r13_re.compile(r"^BILD\s*[:\-]\s*", _r13_re.I)
R13_BEWEG = _r13_re.compile(r"^BEWEGUNG\s*[:\-]\s*", _r13_re.I)


def r13_trennen(satz):
    """(gesprochen, bild, bewegung) aus einem Satz mit Klammern."""
    ganz = satz or ""
    roh = [" ".join(x.split()) for x in R13_GANZ.findall(ganz) if x and x.strip()]
    rest = R13_GANZ.sub(" ", ganz)
    offen = R13_OFFEN.search(rest)
    if offen:
        if offen.group(1).strip():
            roh.append(" ".join(offen.group(1).split()))
        rest = rest[:offen.start()]
    rest = " ".join(rest.replace("[", " ").replace("]", " ").split())

    bild, beweg, ohne = [], [], []
    for x in roh:
        if R13_BILD.match(x):
            w = R13_BILD.sub("", x).strip()
            if w:
                bild.append(w)
        elif R13_BEWEG.match(x):
            w = R13_BEWEG.sub("", x).strip()
            if w:
                beweg.append(w)
        else:
            ohne.append(x)
    # Eine Klammer ohne Namen beschreibt ein Bild, keine Bewegung.
    # Sie landet deshalb nur in der Bildbeschreibung; die Animation
    # bleibt leer und wird zur ruhigen Fahrt.
    return (rest,
            ", ".join(bild) or ", ".join(ohne),
            ", ".join(beweg))


def r13_aufteilen(kanal):
    """Fuellt leere Felder aus den Klammern. Gibt die Anzahl zurueck."""
    d = _r13_laden_alt(kanal)
    n = 0
    for s in d["szenen"]:
        satz = s.get("text") or ""
        if "[" not in satz:
            continue
        rest, bild, beweg = r13_trennen(satz)
        if not rest.strip():
            continue
        s["text"] = rest
        if bild and not (s.get("bild") or "").strip():
            s["bild"] = bild[:600]
        if beweg and not (s.get("regie") or "").strip():
            s["regie"] = beweg[:600]
        n += 1
    if n:
        speichern(kanal, d)
    return n


_r13_laden_alt = laden


def laden(kanal):
    d = _r13_laden_alt(kanal)
    if any("[" in (s.get("text") or "") for s in d["szenen"]):
        try:
            if r13_aufteilen(kanal):
                d = _r13_laden_alt(kanal)
        except Exception as e:
            print("[Szenen] Klammern nicht aufteilbar:", e)
    return d


# ---------- Nachtrag r14: doppelte Regie aufraeumen ----------
#
# r13 hat eine namenlose Klammer zuerst in beide Felder geschrieben.
# Dann steht in der Animationsanweisung eine Bildbeschreibung, und der
# Clip bekommt als Bewegungsbefehl "wide shot silhouette of three
# ships" - also gar keine Bewegung. Wo beide Felder gleich sind, wird
# die Regie geleert; dann gilt wieder die ruhige Fahrt.

def r14_doppelte_regie_weg(kanal):
    d = _r13_laden_alt(kanal)
    n = 0
    for s in d["szenen"]:
        b = (s.get("bild") or "").strip()
        r = (s.get("regie") or "").strip()
        if b and r and b == r:
            s["regie"] = ""
            n += 1
    if n:
        speichern(kanal, d)
    return n


_r14_laden_alt = laden


def laden(kanal):
    d = _r14_laden_alt(kanal)
    if any((s.get("bild") or "").strip()
           and (s.get("bild") or "").strip() == (s.get("regie") or "").strip()
           for s in d["szenen"]):
        try:
            if r14_doppelte_regie_weg(kanal):
                d = _r14_laden_alt(kanal)
        except Exception as e:
            print("[Szenen] Regie nicht aufraeumbar:", e)
    return d


# ---------- Nachtrag r16: [IM BILD: ...] in die Schalter ----------
#
# Claude schreibt je Szene mit, wer zu sehen ist. Daraus werden die
# Besetzung der Szene und der Dreierschalter vorbelegt:
#   Namen genannt -> "Avatare im Bild", diese Figuren angewaehlt
#   "niemand"     -> "Nur Bild, bewegt"
# Danach ist es ein ganz normales Feld - wer umschaltet, dessen
# Einstellung bleibt.

R16_IM_BILD = _r13_re.compile(r"^IM\s*BILD\s*[:\-]\s*", _r13_re.I)


def r16_trennen(satz):
    """(rest, bild, bewegung, im_bild) - im_bild ist None wenn nichts stand."""
    rest, bild, beweg = r13_trennen(satz)
    treffer = None
    for roh in R13_GANZ.findall(satz or ""):
        x = " ".join(roh.split())
        if R16_IM_BILD.match(x):
            treffer = R16_IM_BILD.sub("", x).strip()
    if treffer is None:
        return rest, bild, beweg, None
    if treffer.lower() in ("niemand", "keiner", "keine", "-", ""):
        return rest, bild, beweg, []
    return rest, bild, beweg, [n.strip() for n in treffer.split(",") if n.strip()]


def r16_zuordnen(kanal, namen):
    """Namen zu Avatar-Ids des Kanals, so gut es geht."""
    try:
        import darsteller
        d = darsteller.laden(kanal)
    except Exception:
        return []
    raus = []
    for n in namen or []:
        for x in d.get("darsteller") or []:
            if (x.get("name") or "").strip().lower() == n.strip().lower():
                if x.get("id") not in raus:
                    raus.append(x["id"])
                break
    return raus


_r16_aufteilen_alt = r13_aufteilen


def r13_aufteilen(kanal):
    d = _r13_laden_alt(kanal)
    n = 0
    for s in d["szenen"]:
        satz = s.get("text") or ""
        if "[" not in satz:
            continue
        rest, bild, beweg, im_bild = r16_trennen(satz)
        if not rest.strip():
            continue
        s["text"] = rest
        if bild and not (s.get("bild") or "").strip():
            s["bild"] = bild[:600]
        if beweg and not (s.get("regie") or "").strip():
            s["regie"] = beweg[:600]
        if im_bild is not None and not s.get("wer"):
            ids = r16_zuordnen(kanal, im_bild)
            if ids:
                s["wer"] = ids
                s["modus"] = "avatare"
            else:
                s["wer"] = []
                s["modus"] = "bewegt"
        n += 1
    if n:
        speichern(kanal, d)
    return n


# ---------- Nachtrag r17: jede Szene wird gesprochen ----------
#
# "Wer spricht" und der Haken "Gesprochen" sind aus dem Dashboard
# raus. Claude schreibt zu jeder Szene Text, und wer ihn spricht,
# steht als Name vor der Zeile. Ein Schalter, der den geschriebenen
# Text wegwirft, ergibt keinen Sinn - und eine stumme Szene kostet in
# einem 20-Sekunden-Video nur Zeit.
#
# Alte Szenen mit gesprochen=False werden beim Laden mitgenommen.

_r17_laden_alt = laden


def laden(kanal):
    d = _r17_laden_alt(kanal)
    for s in d["szenen"]:
        if s.get("gesprochen") is False and (s.get("text") or "").strip():
            s["gesprochen"] = True
    return d


# ---------- Nachtrag m2: Hintergrund allein animieren ----------
#
# Bisher gab es drei Schalter je Szene, und nur einer hat einen KI-Clip
# ausgeloest: "Avatare im Bild". Wer wollte, dass geredet wird, ohne dass
# jemand zu sehen ist, bekam ein Standbild - das Hintergrundbild liess
# sich nicht allein animieren.
#
# Jetzt sind es vier:
#   avatare  - KI-Clip, die Avatare sind drin und gestikulieren  (kostet)
#   bild_ki  - KI-Clip nur vom Hintergrund, niemand zu sehen     (kostet)
#   bewegt   - Standbild mit langsamer Kamerafahrt               (gratis)
#   still    - Standbild, steht                                   (gratis)
#
# Geredet wird in allen vieren. Wer redet, steht im Sprechtext.

M2_MODI = [["avatare", "Avatare im Bild"],
           ["bild_ki", "Nur Bild animieren"],
           ["bewegt", "Kamerafahrt"],
           ["still", "Standbild"]]

R6_MODI[:] = [list(x) for x in M2_MODI]
R6_MODUS_NAMEN[:] = [a[0] for a in R6_MODI]


def r6_braucht_clip(s):
    """Soll fuer diese Szene ein KI-Clip erzeugt werden?"""
    if s.get("eigener_clip"):
        return False
    if (s.get("modus") or "") not in ("avatare", "bild_ki"):
        return False
    return art(s.get("datei") or "") == "bild"


# ---------- Nachtrag r19: nur zeigen, wer auch redet ----------
#
# In einer Szene hat Mara gesprochen, zu sehen war aber Jonas. Das sieht
# nach Fehler aus, weil es einer ist: wer im Bild steht und den Mund
# nicht aufmacht, wirkt wie vergessen.
#
# Erlaubt sind von jetzt an nur zwei Faelle:
#   wer = []        niemand im Bild, es wird aus dem Off geredet
#   wer = Sprecher  genau die, die in dieser Szene reden
# Alles andere wird zurechtgerueckt. Reine Sprecher ohne Bilder zaehlen
# nicht mit - die stehen nie im Bild.

# Nur bekannte Namen zaehlen. Ein freies Muster hat aus "Mara: Eins.
# Jonas: Zwei." den Sprecher "ins. Jonas" gemacht - Punkte und
# Leerzeichen gehoeren eben auch zu erlaubten Namen.


def r19_namen(kanal):
    try:
        import darsteller
        return [(x.get("name") or "").strip()
                for x in (darsteller.laden(kanal).get("darsteller") or [])
                if (x.get("name") or "").strip()]
    except Exception:
        return []


def r19_redner(kanal, text):
    """Die bekannten Namen, die in diesem Text vor einem Doppelpunkt stehen."""
    t = text or ""
    treffer = []
    # Laengere Namen zuerst pruefen, damit "Sprecherin Frau" nicht als
    # "Frau" durchgeht. Sortiert wird am Ende nach der Stelle im Text.
    for n in sorted(r19_namen(kanal), key=len, reverse=True):
        m = re.search(r"(?<![\wÄÖÜäöüß])" + re.escape(n) + r"\s*:", t, re.I)
        if m and n not in [x[1] for x in treffer]:
            treffer.append((m.start(), n))
    return [n for _, n in sorted(treffer)]


def r19_richten(kanal, s):
    """Setzt wer auf die, die reden. Gibt True, wenn sich etwas geaendert hat."""
    alt = list(s.get("wer") or [])
    if not alt:
        return False                      # niemand im Bild ist in Ordnung
    ids = r16_zuordnen(kanal, r19_redner(kanal, s.get("text") or ""))
    try:
        import darsteller
        d = darsteller.laden(kanal)
        echte = set(x["id"] for x in (d.get("darsteller") or [])
                    if x.get("art") != "sprecher")
        ids = [i for i in ids if i in echte]
    except Exception:
        pass
    if ids == alt:
        return False
    s["wer"] = ids
    return True


_r19_aufteilen_alt = r13_aufteilen


def r13_aufteilen(kanal):
    n = _r19_aufteilen_alt(kanal)
    try:
        d = _r13_laden_alt(kanal)
        geaendert = 0
        for s in d["szenen"]:
            if r19_richten(kanal, s):
                geaendert += 1
        if geaendert:
            speichern(kanal, d)
            print("[Szenen] %d mal zurechtgerueckt: nur zeigen, wer redet"
                  % geaendert)
            n += geaendert
    except Exception as e:
        print("[Szenen] wer nicht pruefbar:", e)
    return n


_r19_aendern_alt = aendern


def aendern(kanal, sid, feld, wert):
    r = _r19_aendern_alt(kanal, sid, feld, wert)
    if feld != "text":
        return r
    try:
        d = _r13_laden_alt(kanal)
        for s in d["szenen"]:
            if s.get("id") == sid and r19_richten(kanal, s):
                speichern(kanal, d)
                break
    except Exception as e:
        print("[Szenen] wer nach Textaenderung nicht pruefbar:", e)
    return r
