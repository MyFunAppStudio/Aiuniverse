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
