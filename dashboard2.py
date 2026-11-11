"""AiUniverse Dashboard 2 - Server und Schnittstellen. Port 8091."""
import json, mimetypes, os, re, shutil, subprocess, sys, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

BASIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASIS)
import szenen
import figuren
import abspann
import darsteller
import einstellungen, kanaele, vorlagen, themen

PORT = 8091
VIDEOS = os.path.join(BASIS, "fertige_videos")
REGELN = os.path.join(BASIS, "regeln")
HTML = os.path.join(BASIS, "dashboard2.html")
ENVDATEI = os.path.join(BASIS, ".env")
TOKEN = "RnLok_Sh_ExvSBNb"

LAUF = {"prozess": None, "kanal": None, "start": 0, "zeilen": []}


# ---------- Hilfen ----------

def env_lesen():
    d = {}
    try:
        with open(ENVDATEI, encoding="utf-8") as f:
            for z in f:
                z = z.strip()
                if z and not z.startswith("#") and "=" in z:
                    k, v = z.split("=", 1)
                    d[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return d


def env_setzen(name, wert):
    d = env_lesen()
    d[name] = wert
    with open(ENVDATEI, "w", encoding="utf-8") as f:
        for k, v in d.items():
            f.write("%s=%s\n" % (k, v))
    os.environ[name] = wert


def schluessel(teil):
    t = teil.upper()
    for k, v in list(env_lesen().items()) + list(os.environ.items()):
        kk = k.upper()
        if t in kk and v and ("KEY" in kk or "TOKEN" in kk or "SECRET" in kk):
            return v
    return ""


def maske(wert):
    if not wert:
        return ""
    return "gesetzt, endet auf " + wert[-4:]


def fal_guthaben():
    k = schluessel("FAL")
    if not k:
        return {"ok": False, "text": "kein Schluessel"}
    try:
        r = urllib.request.Request(
            "https://api.fal.ai/v1/account/billing?expand=credits",
            headers={"Authorization": "Key " + k})
        with urllib.request.urlopen(r, timeout=12) as a:
            d = json.loads(a.read().decode("utf-8"))
        c = d.get("credits") or {}
        return {"ok": True, "betrag": c.get("current_balance"),
                "waehrung": c.get("currency") or "USD"}
    except Exception as ex:
        return {"ok": False, "text": str(ex)[:80]}


def ordner_liste(key=None):
    raus = []
    try:
        for n in sorted(os.listdir(VIDEOS), reverse=True):
            p = os.path.join(VIDEOS, n)
            if not os.path.isdir(p):
                continue
            kid = n.split("_", 1)[0]
            if key and kid != key:
                continue
            v = os.path.join(p, "video.mp4")
            if not os.path.exists(v):
                continue
            titel = n
            try:
                with open(os.path.join(p, "paket.json"), encoding="utf-8") as f:
                    titel = (json.load(f).get("titel") or n).strip()
            except Exception:
                pass
            raus.append({
                "ordner": n, "kanal": kid, "titel": titel,
                "mb": round(os.path.getsize(v) / 1048576.0, 1),
                "zeit": time.strftime("%d.%m. %H:%M", time.localtime(os.path.getmtime(v))),
                "thumb": os.path.exists(os.path.join(p, "thumbnail.jpg")),
            })
    except Exception:
        pass
    return raus


def preis_szenen(key, d):
    """Eigene Szenen: keine Bilder, kein Skript - nur die Stimme kostet."""
    try:
        daten = szenen.fuer_anzeige(key)
    except Exception:
        daten = {"szenen": []}
    gesamt_sek, sprech_sek, gesprochen = 0.0, 0.0, 0
    for s in daten.get("szenen", []):
        vor = float(s.get("vorschlag") or 3)
        if s.get("gesprochen") and (s.get("text") or "").strip():
            gesamt_sek += vor
            sprech_sek += vor
            gesprochen += 1
        else:
            gesamt_sek += float(s.get("sekunden") or vor)
    stimme = round(sprech_sek * modell_preis(key, "stimme", 0.008), 3)
    animiert, je_clip = 0, 0.0
    try:
        import animation
        liste = [{"typ": s.get("typ")} for s in daten.get("szenen", [])]
        manuell = set(i for i, s in enumerate(daten.get("szenen", []))
                      if s.get("ki_animation"))
        animiert = len(manuell | animation.auswahl(liste, d.get("kling_anteil", 0)))
        if animiert and animation.bereit(d)[0]:
            je_clip = animation.preis_je_clip(d, 5)
        else:
            animiert = 0
    except Exception:
        animiert, je_clip = 0, 0.0
    anim = round(animiert * je_clip, 3)
    return {"bilder": 0, "je_bild": 0.0, "text": 0.0, "stimme": stimme,
            "animation": anim, "animiert": animiert, "je_clip": je_clip,
            "gesamt": round(stimme + anim, 3), "modus": "szenen",
            "szenen": len(daten.get("szenen", [])), "gesprochen": gesprochen,
            "sekunden": round(gesamt_sek, 1)}


def preis(key):
    d = einstellungen.laden().get(key) or {}
    if d.get("modus") in ("szenen", "geschichte"):
        return preis_szenen(key, d)
    try:
        sek = float(d.get("laenge") or 20)
    except Exception:
        sek = 20.0
    try:
        bpm = float(d.get("bilder_pro_minute") or 24)
    except Exception:
        bpm = 24.0
    bilder = max(3, int(round(sek / 60.0 * bpm)))
    p_bild = 0.04
    try:
        p_bild = float(einstellungen.preis_fuer(key, "bilder") or 0.04)
    except Exception:
        pass
    p_bild = modell_preis(key, "bilder", p_bild)
    text = modell_preis(key, "text", 0.02)
    # Frueher hing das an d["stimme_an"]. Den Schalter gibt es nicht mehr,
    # gelesen hat ihn ausser dieser Zeile ohnehin nie jemand - gesprochen
    # wurde immer. Alte Kanaldateien mit stimme_an=False haben deshalb
    # 0,00 EUR fuer die Stimme angezeigt, obwohl sie Geld gekostet hat.
    stimme = round(sek * modell_preis(key, "stimme", 0.008), 3)
    gesamt = round(bilder * p_bild + text + stimme, 3)
    return {"bilder": bilder, "je_bild": p_bild, "text": text,
            "stimme": stimme, "gesamt": gesamt, "modus": "auto",
            "sekunden": round(sek, 1)}



def _woher_sicher(kanal, eintrag):
    """Nur das Wort, woher der Schluessel kommt. Nie der Schluessel."""
    try:
        import schluessel
        return schluessel.woher(kanal, eintrag)
    except Exception:
        return ""


def slots():
    standard = ["text", "bilder", "stimme", "video", "ref", "musik", "sound", "avatar"]
    try:
        roh = list(einstellungen.API_SLOTS)
    except Exception:
        return standard
    raus = []
    for x in roh:
        if isinstance(x, dict):
            x = x.get("slot") or x.get("key") or x.get("name") or ""
        elif isinstance(x, (list, tuple)):
            x = x[0] if x else ""
        if isinstance(x, str) and x and x not in raus:
            raus.append(x)
    return raus or standard


def modelle_lesen(key):
    d = einstellungen.laden().get(key) or {}
    apis = d.get("apis") or {}
    raus = {}
    for s in slots():
        liste = []
        for e in (apis.get(s) or []):
            if not isinstance(e, dict):
                continue
            liste.append({
                "name": e.get("name") or "",
                "url": e.get("url") or "",
                "preis": e.get("preis", ""),
                "aktiv": bool(e.get("aktiv")),
                "key": maske(e.get("key") or ""),
                "woher": _woher_sicher(d, e),
            })
        raus[s] = liste
    return {"slots": slots(), "apis": raus}


def modelle_schreiben(key, b):
    alles = einstellungen.laden()
    d = alles.get(key)
    if not isinstance(d, dict):
        return {"ok": False, "fehler": "Kanal unbekannt"}
    d.setdefault("apis", {})
    s = b.get("slot") or ""
    if s not in slots():
        return {"ok": False, "fehler": "Slot unbekannt"}
    d["apis"].setdefault(s, [])
    liste = d["apis"][s]
    a = b.get("aktion")
    i = b.get("i")
    try:
        i = int(i)
    except Exception:
        i = -1
    if a == "neu":
        liste.append({"name": (b.get("name") or "Neu").strip(),
                      "url": (b.get("url") or "").strip(),
                      "key": (b.get("key") or "").strip(),
                      "preis": b.get("preis", ""),
                      "aktiv": False})
    elif 0 <= i < len(liste):
        e = liste[i]
        if a == "weg":
            liste.pop(i)
        elif a == "aktiv":
            for x in liste:
                x["aktiv"] = False
            e["aktiv"] = True
        elif a == "speichern":
            if b.get("name") is not None:
                e["name"] = (b.get("name") or "").strip()
            if b.get("url") is not None:
                e["url"] = (b.get("url") or "").strip()
            if b.get("preis") is not None:
                e["preis"] = b.get("preis")
            if (b.get("key") or "").strip():
                e["key"] = b["key"].strip()
    else:
        return {"ok": False, "fehler": "Eintrag unbekannt"}
    einstellungen.speichern(alles)
    return {"ok": True}


def modell_preis(key, slot, standard):
    for e in ((einstellungen.laden().get(key) or {}).get("apis") or {}).get(slot) or []:
        if isinstance(e, dict) and e.get("aktiv"):
            try:
                return float(str(e.get("preis")).replace(",", "."))
            except Exception:
                return standard
    return standard


def _slot_stand(key, slot, *teile):
    eintraege = []
    try:
        eintraege = ((einstellungen.laden().get(key) or {}).get("apis") or {}).get(slot) or []
    except Exception:
        eintraege = []
    aktiv = None
    for e in eintraege:
        if isinstance(e, dict) and e.get("aktiv"):
            aktiv = e
            break
    if aktiv is not None:
        if (aktiv.get("key") or "").strip():
            return True, (aktiv.get("name") or "").strip()
        for teil in teile:
            if schluessel(teil):
                return True, (aktiv.get("name") or "").strip()
        return False, ""
    for e in eintraege:
        if isinstance(e, dict) and (e.get("key") or "").strip():
            return True, (e.get("name") or "").strip()
    for teil in teile:
        if schluessel(teil):
            return True, ""
    return False, ""


# ---------- Darsteller (Patch r1) ----------

def darsteller_lesen(key):
    return darsteller.fuer_anzeige(key)


def darsteller_schreiben(key, b):
    a = b.get("aktion") or ""
    did = str(b.get("id") or "")
    wert = b.get("wert")
    if a == "neu":
        return darsteller.anlegen(key, b.get("name") or "")
    if a == "weg":
        return darsteller.entfernen(key, did)
    if a == "name":
        return darsteller.aendern(key, did, a, wert)
    if a == "bild_weg":
        return darsteller.bild_weg(key, did, b.get("datei") or "")
    if a == "bild_vor":
        return darsteller.bild_vor(key, did, b.get("datei") or "")
    if a == "dabei":
        return darsteller.dabei_setzen(key, did, bool(wert))
    return {"ok": False, "fehler": "Aktion unbekannt"}


# ---------- Abspann-Bibliothek (r6) ----------

def abspann_lesen(key):
    return abspann.fuer_anzeige(key)


def abspann_schreiben(key, b):
    a = b.get("aktion") or ""
    eid = str(b.get("id") or "")
    if a == "weg":
        return abspann.entfernen(key, eid)
    if a in ("name", "sekunden"):
        return abspann.aendern(key, eid, a, b.get("wert"))
    if a == "waehlen":
        return abspann.waehlen(key, str(b.get("wert") or ""))
    return {"ok": False, "fehler": "Aktion unbekannt"}

def szenen_schreiben(key, b):
    a = b.get("aktion") or ""
    sid = b.get("id") or ""
    if a in getattr(szenen, "FELDER", ("text", "gesprochen", "untertitel", "sekunden", "bewegung", "figur", "ki_animation", "musik", "passen")):
        return szenen.aendern(key, sid, a, b.get("wert"))
    if a in ("hoch", "runter"):
        return szenen.verschieben(key, sid, a)
    if a == "wer_um":
        return szenen.r7_wer_um(key, sid, b.get("wer") or "")
    if a == "zurueck":
        return szenen.r6_zurueck(key, sid, str(b.get("welche") or ""),
                                 b.get("datei") or "")
    if a == "weg":
        return szenen.entfernen(key, sid)
    if a == "musik_weg":
        return szenen.musik_setzen(key, "")
    if a == "alle_weg":
        return szenen.r10_alle_weg(key)
    return {"ok": False, "fehler": "Aktion unbekannt"}


def figuren_lesen(key):
    d = figuren.fuer_anzeige(key)
    d["stimmen"] = [[e.get("name", ""), e.get("id", "")]
                    for e in ((einstellungen.laden().get(key) or {}).get("stimmen") or [])
                    if isinstance(e, dict) and e.get("name")]
    return d


def figuren_schreiben(key, b):
    a = b.get("aktion") or ""
    name = b.get("name") or ""
    if a == "neu":
        return figuren.anlegen(key, name)
    if a == "weg":
        return figuren.entfernen(key, name)
    if a in ("umbenennen", "stimme", "beschreibung", "bewegung"):
        feld = "name" if a == "umbenennen" else a
        return figuren.aendern(key, name, feld, b.get("wert"))
    if a == "pose_weg":
        return figuren.pose_weg(key, name, b.get("datei") or "")
    if a == "freistellen":
        return figuren.pose_freistellen(key, name, b.get("datei") or "")
    return {"ok": False, "fehler": "Aktion unbekannt"}


def telegram_lesen(key):
    d = einstellungen.laden().get(key) or {}
    return {"token": maske(d.get("telegram_token") or ""),
            "chat": d.get("telegram_chat") or "",
            "adresse": d.get("dashboard_adresse") or "",
            "bereit": bool(d.get("telegram_token") and d.get("telegram_chat"))}


def telegram_schreiben(key, b):
    alles = einstellungen.laden()
    d = alles.get(key)
    if not isinstance(d, dict):
        return {"ok": False, "fehler": "Kanal unbekannt"}
    if (b.get("token") or "").strip():
        d["telegram_token"] = b["token"].strip()
    if b.get("chat") is not None:
        d["telegram_chat"] = (b.get("chat") or "").strip()
    if b.get("adresse") is not None:
        d["dashboard_adresse"] = (b.get("adresse") or "").strip().rstrip("/")
    einstellungen.speichern(alles)
    return {"ok": True}


def telegram_test(key):
    d = dict(einstellungen.laden().get(key) or {})
    d.setdefault("id", key)
    d.setdefault("name", d.get("name") or key)
    d.setdefault("emoji", d.get("emoji") or "\U0001F3AC")
    if not d.get("telegram_token") or not d.get("telegram_chat"):
        return {"ok": False, "fehler": "Token oder Chat-ID fehlt"}
    try:
        import telegram_sender
        ok = telegram_sender.sende_text(d, "%s Test aus dem Dashboard - Telegram funktioniert."
                                        % d.get("emoji", ""))
        return {"ok": bool(ok)} if ok else {"ok": False, "fehler": "Telegram hat abgelehnt"}
    except Exception as e:
        return {"ok": False, "fehler": str(e)[:200]}


def api_stand(key=None):
    # Die Slots avatar und sound sind raus. ref ("Clips mit Avataren")
    # fehlte hier, obwohl ohne ihn keine Szene mit Avataren gebaut wird.
    paare = [("text", "text", ("ANTHROPIC", "OPENAI")),
             ("bilder", "bilder", ("FAL",)),
             ("stimme", "stimme", ("FAL", "ELEVEN")),
             ("ref", "ref", ("FAL", "KLING")),
             ("video", "video", ("FAL", "KLING")),
             ("musik", "musik", ("FAL",))]
    raus = {}
    for name, slot, teile in paare:
        ok, wie = _slot_stand(key, slot, *teile)
        raus[name] = ok
        raus[name + "_name"] = wie
    return raus


def geschichte_starten(key):
    """Startet den Aufbau der Szenen aus der Geschichte im Hintergrund."""
    p = LAUF["prozess"]
    if p and p.poll() is None:
        return {"ok": False, "text": "Es laeuft schon etwas"}
    d = einstellungen.laden().get(key) or {}
    if not (d.get("geschichte_text") or "").strip():
        return {"ok": False, "text": "Keine Geschichte eingegeben"}
    try:
        import bilder
        ok, grund = bilder.bereit(d)
        if not ok:
            return {"ok": False, "text": grund}
    except Exception as e:
        return {"ok": False, "text": "Bildmodul fehlt: %s" % e}
    befehl = [sys.executable, "-u", os.path.join(BASIS, "geschichte_lauf.py"), key]
    log = open(os.path.join(BASIS, "lauf.log"), "w", encoding="utf-8")
    LAUF["prozess"] = subprocess.Popen(befehl, cwd=BASIS, stdout=log,
                                       stderr=subprocess.STDOUT)
    LAUF["kanal"] = key
    LAUF["start"] = time.time()
    LAUF["zeilen"] = []
    return {"ok": True, "text": "Bilder werden erzeugt"}


def geschichte_stand(key):
    """Was der Geschichten-Modus gerade anzeigen soll."""
    d = einstellungen.laden().get(key) or {}
    raus = {"saetze": 0, "figuren": [], "kann_figur": False, "figur_bild": True,
            "je_bild": 0.0, "bereit": False, "grund": "Bildmodul fehlt"}
    try:
        import geschichte, bilder, figuren
        raus["saetze"] = len(geschichte.zerlege(d.get("geschichte_text") or ""))
        raus["stile"] = [list(x) for x in geschichte.STILE]
        raus["figuren"] = [f["name"] for f in figuren.fuer_anzeige(key)["figuren"]]
        raus["kann_figur"] = bilder.kann_figur(d)[0]
        gf = (d.get("geschichte_figur") or "").strip()
        raus["figur_bild"] = bool(bilder.figur_referenz(d, gf)) if gf else True
        raus["je_bild"] = bilder.preis_je_bild(d)
        raus["bereit"], raus["grund"] = bilder.bereit(d)
    except Exception as e:
        raus["grund"] = str(e)[:120]
    raus["kosten"] = round(raus["saetze"] * raus["je_bild"], 2)
    return raus


VOREINSTELLUNGEN = [
    ["erklaer", "Erklaervideo", {
        "bildstimmung": "kalt",
        "tempo": "schnell",
        "stimme_energie": 0.55, "untertitel_an": True, "untertitel_woerter": 3,
        "musik_an": True, "musik_leise": 10, "musik_laut": 70}],
    ["fakten", "Fakten und Listen", {
        "bildstimmung": "kalt",
        "tempo": "sehr_schnell",
        "stimme_energie": 0.75, "untertitel_an": True, "untertitel_woerter": 2,
        "musik_an": True, "musik_leise": 14, "musik_laut": 85}],
    ["story", "Geschichte", {
        "bildstimmung": "warm",
        "tempo": "normal",
        "stimme_energie": 0.45, "untertitel_an": True, "untertitel_woerter": 3,
        "musik_an": True, "musik_leise": 11, "musik_laut": 62}],
    ["maerchen", "Maerchen", {
        "bildstimmung": "warm",
        "tempo": "ruhig",
        "stimme_energie": 0.15, "untertitel_an": True, "untertitel_woerter": 3,
        "musik_an": True, "musik_leise": 9, "musik_laut": 45}],
    ["build", "Build und Prozess", {
        "bildstimmung": "kalt",
        "tempo": "schnell",
        "untertitel_an": True, "untertitel_woerter": 3,
        "musik_an": True, "musik_leise": 60, "musik_laut": 85}],
    ["firma", "Firmenvideo", {
        "bildstimmung": "warm",
        "tempo": "schnell",
        "stimme_energie": 0.5, "untertitel_an": True, "untertitel_woerter": 3,
        "musik_an": True, "musik_leise": 12, "musik_laut": 68}],
]


def voreinstellung_setzen(key, name):
    """Setzt alle Schalter einer Videoart auf einmal."""
    alles = einstellungen.laden()
    d = alles.get(key)
    if not isinstance(d, dict):
        return {"ok": False, "fehler": "Kanal unbekannt"}
    for schl, titel, werte in VOREINSTELLUNGEN:
        if schl == name:
            d.update(werte)
            d["voreinstellung"] = schl
            einstellungen.speichern(alles)
            return {"ok": True, "name": titel, "anzahl": len(werte)}
    return {"ok": False, "fehler": "Unbekannte Videoart"}


def lauf_stand():
    p = LAUF["prozess"]
    if p and p.poll() is None:
        return {"laeuft": True, "kanal": LAUF["kanal"],
                "sekunden": int(time.time() - LAUF["start"]),
                "zeilen": LAUF["zeilen"][-14:]}
    return {"laeuft": False, "kanal": LAUF["kanal"],
            "zeilen": LAUF["zeilen"][-14:]}


def lauf_starten(key, thema):
    p = LAUF["prozess"]
    if p and p.poll() is None:
        return False, "Es laeuft schon ein Video"
    befehl = [sys.executable, "-u", os.path.join(BASIS, "lauf.py"), key]
    if thema:
        befehl.append(thema)
    log = open(os.path.join(BASIS, "lauf.log"), "w", encoding="utf-8")
    LAUF["prozess"] = subprocess.Popen(befehl, cwd=BASIS, stdout=log,
                                       stderr=subprocess.STDOUT)
    LAUF["kanal"] = key
    LAUF["start"] = time.time()
    LAUF["zeilen"] = []
    return True, "gestartet"


def log_zeilen():
    try:
        with open(os.path.join(BASIS, "lauf.log"), encoding="utf-8") as f:
            return [z.rstrip() for z in f.readlines()[-14:]]
    except Exception:
        return []


# ---------- Server ----------

P53_DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regeln", "passwort.txt")


def _p53_passwort():
    """Das gesetzte Passwort, oder leer wenn keins da ist."""
    try:
        with open(P53_DATEI, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _p53_unterhalb(pfad):
    """True, wenn der Pfad wirklich im Projektordner liegt."""
    try:
        wurzel = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
        echt = os.path.realpath(str(pfad))
        return echt == wurzel or echt.startswith(wurzel + os.sep)
    except Exception:
        return False


class Griff(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def sende(self, daten, typ="application/json", code=200, kopf=None):
        if isinstance(daten, (dict, list)):
            daten = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        elif isinstance(daten, str):
            daten = daten.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (kopf or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(daten)
        except Exception:
            pass

    def koerper(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def datei(self, pfad, typ=None):
        if not _p53_unterhalb(pfad) or os.path.isdir(str(pfad)):
            return self.sende({"fehler": "nicht da"}, code=404)
        if not os.path.exists(pfad):
            return self.sende({"fehler": "nicht da"}, code=404)
        typ = typ or (mimetypes.guess_type(pfad)[0] or "application/octet-stream")
        groesse = os.path.getsize(pfad)
        bereich = self.headers.get("Range")
        if bereich and bereich.startswith("bytes="):
            teil = bereich[6:].split("-")
            a = int(teil[0] or 0)
            b = int(teil[1]) if len(teil) > 1 and teil[1] else groesse - 1
            b = min(b, groesse - 1)
            with open(pfad, "rb") as f:
                f.seek(a)
                d = f.read(b - a + 1)
            self.send_response(206)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, groesse))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(d)))
            self.end_headers()
            try:
                self.wfile.write(d)
            except Exception:
                pass
            return
        with open(pfad, "rb") as f:
            d = f.read()
        self.sende(d, typ, kopf={"Accept-Ranges": "bytes"})

    def _p53_offen(self):
        """Laesst die Anfrage durch, oder schickt die Passwortabfrage."""
        soll = _p53_passwort()
        if not soll:
            return True
        kopf = self.headers.get("Authorization") or ""
        if kopf.startswith("Basic "):
            import base64, hmac
            try:
                roh = base64.b64decode(kopf[6:]).decode("utf-8", "replace")
            except Exception:
                roh = ""
            ist = roh.split(":", 1)[1] if ":" in roh else ""
            if hmac.compare_digest(ist, soll):
                return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="AiUniverse"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    # ----- GET -----
    def do_GET(self):
        if not self._p53_offen():
            return
        u = urlparse(self.path)
        w = u.path
        q = parse_qs(u.query)
        k = (q.get("k") or [""])[0]

        if w in ("/", "/index.html"):
            if os.path.exists(HTML):
                return self.datei(HTML, "text/html; charset=utf-8")
            return self.sende("<h1>dashboard2.html fehlt noch</h1>",
                              "text/html; charset=utf-8")

        if w == "/api/stand":
            LAUF["zeilen"] = log_zeilen()
            return self.sende({
                "kanaele": kanaele.liste(),
                "apis": api_stand(k),
                "lauf": lauf_stand(),
                "zeit": time.strftime("%H:%M"),
            })

        if w == "/api/guthaben":
            return self.sende({"fal": fal_guthaben()})

        if w == "/api/kanal":
            d = dict(einstellungen.laden().get(k) or {})
            d.pop("_key", None)
            return self.sende(d)

        if w == "/api/vorlagen":
            return self.sende(vorlagen.alle())

        if w == "/api/themen":
            return self.sende(themen.laden(k))

        if w == "/api/videos":
            return self.sende(ordner_liste(k or None))

        if w == "/api/preis":
            return self.sende(preis(k))

        if w == "/api/schluessel":
            return self.sende({
                "anthropic": maske(schluessel("ANTHROPIC")),
                "fal": maske(schluessel("FAL")),
                "eleven": maske(schluessel("ELEVEN")),
                "hedra": maske(schluessel("HEDRA")),
                "kling": maske(schluessel("KLING")),
                "freesound": maske(schluessel("FREESOUND")),
            })

        if w == "/api/darsteller":
            return self.sende(darsteller_lesen(k))

        if w == "/api/abspann":
            return self.sende(abspann_lesen(k))

        if w == "/api/clip_stand":
            return self.sende(r5_clip_stand(k))

        if w == "/api/figuren":
            return self.sende(figuren_lesen(k))

        if w == "/api/telegram":
            return self.sende(telegram_lesen(k))

        if w == "/api/modelle":
            return self.sende(modelle_lesen(k))

        if w == "/api/arten":
            return self.sende({"arten": [[a, b] for a, b, _c in VOREINSTELLUNGEN],
                               "jetzt": (einstellungen.laden().get(k) or {}).get("voreinstellung", "")})

        if w == "/api/geschichte":
            return self.sende(geschichte_stand(k))

        if w == "/api/vorschau":
            return self._p69_vorschau(k)

        if w == "/api/schriften":
            return self.sende(_p71_schriften())

        if w == "/api/figurlage":
            return self.sende(_p76_lage(k))

        if w == "/api/szenen":
            return self.sende(szenen.fuer_anzeige(k))

        if w.startswith("/darsteller/"):
            return self.datei(darsteller.datei_pfad(k, unquote(w[12:])))

        if w.startswith("/abspann_bild/"):
            # Nur das Standbild, nicht das ganze Video
            p = abspann.vorschau(k, unquote(w[14:]))
            return self.datei(p) if p else self.sende({"ok": False}, code=404)

        if w.startswith("/abspann/"):
            return self.datei(abspann.datei_pfad(k, unquote(w[9:])))

        if w.startswith("/figur/"):
            return self.datei(figuren.datei_pfad(k, unquote(w[7:])))

        if w.startswith("/eigen/"):
            return self.datei(szenen.datei_pfad(k, unquote(w[7:])))

        if w.startswith("/laden/"):
            o = unquote(w[7:])
            pf = os.path.join(VIDEOS, o, "video.mp4")
            if not os.path.exists(pf):
                return self.sende({"fehler": "nicht da"}, code=404)
            with open(pf, "rb") as f:
                roh = f.read()
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", o) or "video"
            return self.sende(roh, "video/mp4", kopf={
                "Content-Disposition": 'attachment; filename="%s.mp4"' % name})

        if w.startswith("/video/"):
            return self.datei(os.path.join(VIDEOS, unquote(w[7:]), "video.mp4"), "video/mp4")

        if w.startswith("/thumb/"):
            return self.datei(os.path.join(VIDEOS, unquote(w[7:]), "thumbnail.jpg"), "image/jpeg")

        if w.startswith("/texte/"):
            p = os.path.join(VIDEOS, unquote(w[7:]), "texte.txt")
            if not os.path.exists(p):
                return self.sende({"fehler": "keine Texte"}, code=404)
            return self.sende(open(p, encoding="utf-8").read(),
                              "text/plain; charset=utf-8")

        return self.sende({"fehler": "unbekannt"}, code=404)

    # ----- POST -----
    def hochladen(self, k, q):
        name = (q.get("name") or [""])[0]
        zweck = (q.get("zweck") or ["szene"])[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if not k or k not in einstellungen.laden():
            return self.sende({"ok": False, "fehler": "Kanal unbekannt"}, code=400)
        if n <= 0:
            return self.sende({"ok": False, "fehler": "Datei ist leer"}, code=400)
        if n > 90 * 1024 * 1024:
            return self.sende({"ok": False, "fehler": "Datei zu gross, hoechstens 90 MB"}, code=400)
        a = szenen.art(name)
        if zweck == "abspann":
            if abspann.art(name) not in ("bild", "video"):
                return self.sende({"ok": False, "fehler":
                                   "Nur Bilder oder Videos"}, code=400)
            zname = abspann.sauberer_name(name)
            ziel = os.path.join(abspann.ordner(k), zname)
            rest = n
            try:
                with open(ziel, "wb") as f:
                    while rest > 0:
                        stueck = self.rfile.read(min(262144, rest))
                        if not stueck:
                            break
                        f.write(stueck)
                        rest -= len(stueck)
            except Exception:
                rest = -1
            if rest != 0:
                try:
                    os.remove(ziel)
                except Exception:
                    pass
                return self.sende({"ok": False, "fehler": "Hochladen abgebrochen"}, code=400)
            r = abspann.annehmen(k, zname, (q.get("bez") or [""])[0])
            if not r.get("ok"):
                try:
                    os.remove(ziel)
                except Exception:
                    pass
                return self.sende(r, code=400)
            return self.sende({"ok": True, "datei": zname,
                               "id": r.get("id"), "sekunden": r.get("sekunden")})

        if zweck == "darsteller":
            if a != "bild":
                return self.sende({"ok": False, "fehler":
                                   "Nur Bilder: jpg, png, webp"}, code=400)
            did = (q.get("id") or [""])[0]
            frisch = ""
            if not did:
                # Kein Avatar genannt: einer wird angelegt und nach der
                # Datei benannt. So reicht ein einziger Knopf zum Hochladen.
                # Geht das Bild schief, muss er wieder weg - sonst bleibt
                # eine leere Karte stehen.
                neu = darsteller.anlegen_fuer_datei(k, name)
                if not neu.get("ok"):
                    return self.sende(neu, code=400)
                did = frisch = neu["id"]
            elif not darsteller.da(k, did):
                return self.sende({"ok": False, "fehler":
                                   "Avatar unbekannt"}, code=400)
            def _zurueck(antwort):
                if frisch:
                    darsteller.entfernen(k, frisch)
                return self.sende(antwort, code=400)

            if not darsteller.platz_frei(k, did):
                return _zurueck({"ok": False, "fehler":
                                 "Dieser Avatar hat schon %d Bilder"
                                 % darsteller.BILDER_MAX})
            zname = szenen.sauberer_name(name)
            ziel = os.path.join(darsteller.ordner(k), zname)
            rest = n
            try:
                with open(ziel, "wb") as f:
                    while rest > 0:
                        stueck = self.rfile.read(min(262144, rest))
                        if not stueck:
                            break
                        f.write(stueck)
                        rest -= len(stueck)
            except Exception:
                rest = -1
            if rest != 0:
                try:
                    os.remove(ziel)
                except Exception:
                    pass
                return _zurueck({"ok": False, "fehler": "Hochladen abgebrochen"})
            e = darsteller.aufbereiten(k, zname)
            if not e.get("ok"):
                try:
                    os.remove(os.path.join(darsteller.ordner(k), zname))
                except Exception:
                    pass
                return _zurueck(e)
            r = darsteller.bild_dazu(k, did, e["datei"])
            if not r.get("ok"):
                try:
                    os.remove(darsteller.datei_pfad(k, e["datei"]))
                except Exception:
                    pass
                return _zurueck(r)
            return self.sende({"ok": True, "datei": e["datei"], "id": did})

        if zweck == "figur":
            schleife = (a == "clip" or name.lower().endswith(".gif"))
            if a != "bild" and not schleife:
                return self.sende({"ok": False, "fehler":
                                   "Nur Bilder (PNG) oder bewegte Figuren (MOV, GIF)"}, code=400)
            fig = (q.get("figur") or [""])[0]
            if not figuren.holen(k, fig):
                return self.sende({"ok": False, "fehler": "Figur unbekannt"}, code=400)
            zname = szenen.sauberer_name(name)
            ziel = os.path.join(figuren.ordner(k), zname)
            rest = n
            try:
                with open(ziel, "wb") as f:
                    while rest > 0:
                        stueck = self.rfile.read(min(262144, rest))
                        if not stueck:
                            break
                        f.write(stueck)
                        rest -= len(stueck)
            except Exception:
                rest = -1
            if rest != 0:
                try:
                    os.remove(ziel)
                except Exception:
                    pass
                return self.sende({"ok": False, "fehler": "Hochladen abgebrochen"}, code=400)
            if schleife:
                e = figuren.annehmen_schleife(k, zname, (q.get("pose") or [""])[0])
            else:
                e = figuren.annehmen(k, zname, (q.get("pose") or [""])[0])
            if not e.get("ok"):
                return self.sende(e, code=400)
            figuren.pose_dazu(k, fig, e["datei"], (q.get("pose") or [""])[0])
            return self.sende(e)

        if zweck == "musik" and a != "ton":
            return self.sende({"ok": False, "fehler": "Nur Tondateien: mp3, wav, m4a"}, code=400)
        if zweck != "musik" and a not in ("bild", "clip"):
            return self.sende({"ok": False, "fehler": "Nur Bilder oder Videoclips"}, code=400)
        zname = szenen.sauberer_name(name)
        ziel = os.path.join(szenen.ordner(k), zname)
        rest = n
        try:
            with open(ziel, "wb") as f:
                while rest > 0:
                    stueck = self.rfile.read(min(262144, rest))
                    if not stueck:
                        break
                    f.write(stueck)
                    rest -= len(stueck)
        except Exception:
            rest = -1
        if rest != 0:
            try:
                os.remove(ziel)
            except Exception:
                pass
            return self.sende({"ok": False, "fehler": "Hochladen abgebrochen"}, code=400)
        if zweck == "musik":
            szenen.musik_setzen(k, zname)
        else:
            _p90_annehmen(k, zname, q)
        return self.sende({"ok": True, "datei": zname})

    def do_POST(self):
        if not self._p53_offen():
            return
        if urlparse(self.path).path == "/api/figurlage":
            q0 = parse_qs(urlparse(self.path).query)
            return self._p76_post((q0.get("k") or [""])[0], self.koerper())
        u = urlparse(self.path)
        w = u.path
        q = parse_qs(u.query)
        k = (q.get("k") or [""])[0]

        if w == "/api/hochladen":
            return self.hochladen(k, q)

        if w == "/api/szene_neu":
            return self.sende(_p90_neu(k, (self.koerper() or {}).get("sid")))

        b = self.koerper()

        if w == "/api/kanal":
            d = einstellungen.laden()
            if k not in d:
                return self.sende({"fehler": "unbekannt"}, code=404)
            for kk, vv in (b or {}).items():
                if kk not in ("_key",):
                    d[k][kk] = vv
            einstellungen.speichern(d)
            return self.sende({"ok": True})

        if w == "/api/kanal_neu":
            key = kanaele.anlegen(b.get("name"), None, b.get("sprache") or "de")
            return self.sende({"ok": True, "key": key})

        if w == "/api/kanal_klon":
            key = kanaele.klonen(b.get("quelle"), b.get("name"))
            return self.sende({"ok": bool(key), "key": key})

        if w == "/api/kanal_geschwister":
            key = kanaele.geschwister(b.get("eltern"), b.get("name"),
                                      b.get("sprache") or "en", b.get("stimme"))
            return self.sende({"ok": bool(key), "key": key})

        if w == "/api/kanal_loesen":
            return self.sende({"ok": kanaele.loesen(b.get("k"))})

        if w == "/api/kanal_weg":
            f = kanaele.loeschen(b.get("k"), bool(b.get("mit_videos")))
            return self.sende({"ok": f is None, "fehler": f})

        if w == "/api/stil_vorschlag":
            try:
                return self.sende(stil_vorschlag(k))
            except Exception as e:
                import traceback
                traceback.print_exc()
                return self.sende({"ok": False, "fehler": str(e)[:200]})

        if w == "/api/themen_vorschlag":
            # Faellt hier etwas um, muss trotzdem JSON zurueckkommen -
            # sonst sieht der Browser nur eine abgebrochene Verbindung
            # und meldet etwas Falsches.
            try:
                return self.sende(themen_vorschlagen(k, (b or {}).get("wieviel")))
            except Exception as e:
                import traceback
                traceback.print_exc()
                return self.sende({"ok": False, "fehler": str(e)[:200]})

        if w == "/api/themen":
            if b.get("hinzu"):
                themen.hinzufuegen(k, b["hinzu"])
            if b.get("weg"):
                themen.entfernen(k, b["weg"])
            if b.get("zuruecksetzen"):
                themen.zuruecksetzen(k)
            if isinstance(b.get("liste"), list):
                d = themen.laden(k)
                d["offen"] = [str(x).strip() for x in b["liste"] if str(x).strip()]
                themen.speichern(k, d)
            return self.sende(themen.laden(k))

        if w == "/api/vorschlag":
            import geschichte
            d = dict(einstellungen.laden().get(k) or {})
            d.setdefault("id", k)
            d.setdefault("name", k)
            return self.sende(geschichte.vorschlag(d, b.get("thema") or ""))

        if w == "/api/darsteller":
            return self.sende(darsteller_schreiben(k, b))

        if w == "/api/abspann":
            return self.sende(abspann_schreiben(k, b))

        if w == "/api/szene_clip":
            return self.sende(r5_clip_start(k, b))

        if w == "/api/clip_stop":
            return self.sende(r5_clip_stop(k))

        if w == "/api/clip_weg":
            return self.sende(r5_clip_weg(k, (b.get("sid") or "")))

        if w == "/api/figuren":
            return self.sende(figuren_schreiben(k, b))

        if w == "/api/telegram":
            return self.sende(telegram_schreiben(k, b))

        if w == "/api/telegram_test":
            return self.sende(telegram_test(k))

        if w == "/api/modelle":
            return self.sende(modelle_schreiben(k, b))

        if w == "/api/szenen":
            return self.sende(szenen_schreiben(k, b))

        if w == "/api/voreinstellung":
            return self.sende(voreinstellung_setzen(k, (b.get("name") or "").strip()))

        if w == "/api/geschichte_start":
            return self.sende(geschichte_starten(k))

        if w == "/api/start":
            ok, text = lauf_starten(b.get("k") or "b", (b.get("thema") or "").strip())
            return self.sende({"ok": ok, "text": text})

        if w == "/api/stop":
            p = LAUF["prozess"]
            if p and p.poll() is None:
                p.terminate()
                return self.sende({"ok": True})
            return self.sende({"ok": False, "text": "laeuft nichts"})

        if w == "/api/video_weg":
            n = (b.get("ordner") or "").strip()
            p = os.path.join(VIDEOS, n)
            if n and os.path.isdir(p) and os.path.dirname(p) == VIDEOS:
                shutil.rmtree(p, ignore_errors=True)
                return self.sende({"ok": True})
            return self.sende({"ok": False}, code=400)

        if w == "/api/schluessel":
            name = {"anthropic": "ANTHROPIC_API_KEY", "fal": "FAL_KEY",
                    "eleven": "ELEVENLABS_API_KEY", "hedra": "HEDRA_API_KEY",
                    "kling": "KLING_API_KEY",
                    "freesound": "FREESOUND_API_KEY"}.get(b.get("slot") or "")
            wert = (b.get("wert") or "").strip()
            if not name or not wert:
                return self.sende({"ok": False}, code=400)
            env_setzen(name, wert)
            return self.sende({"ok": True})

        return self.sende({"fehler": "unbekannt"}, code=404)


# ---------- Nachtrag p69: Die Bildvorschau ----------

P69_WORTE = ["Das", "wird", "jetzt", "richtig", "gut", "so"]

# ein einziges Bild je Eingang, und der Zeitpunkt, den es darstellen soll
_P69_EINS = ["-loop", "1", "-framerate", "1", "-t", "1"]
_P69_ZEIT = "1.5"


def _p69_hintergrund(k):
    """Das erste brauchbare Szenenbild des Kanals, sonst eines aus dem
    letzten fertigen Video. Gibt (Pfad, Szene) oder (None, None)."""
    import szenen
    try:
        d = szenen.fuer_anzeige(k)
    except Exception:
        d = {}
    for s in (d.get("szenen") or []):
        if s.get("da") and s.get("typ") == "bild":
            try:
                pf = szenen.datei_pfad(k, s["datei"])
            except Exception:
                continue
            if os.path.exists(pf):
                return pf, s
    try:
        for n in sorted(os.listdir(VIDEOS), reverse=True):
            if not n.startswith(k + "_"):
                continue
            o = os.path.join(VIDEOS, n)
            if not os.path.isdir(o):
                continue
            for bild in sorted(os.listdir(o)):
                if bild.startswith("bild_") and bild.lower().endswith((".jpg", ".png")):
                    return os.path.join(o, bild), None
    except Exception:
        pass
    return None, None


def _p69_figur(k, szene):
    """Die Figurendatei, die in dieser Szene im Bild steht, sonst None."""
    import figuren
    name = ((szene or {}).get("figur") or "").strip()
    if not name:
        name = ((einstellungen.laden().get(k) or {}).get("geschichte_figur") or "").strip()
    if not name:
        return None
    try:
        pf = figuren.pose_pfad(k, name, (szene or {}).get("pose") or "")
    except Exception:
        return None
    pf = str(pf or "")
    return pf if pf and os.path.exists(pf) else None


def _p69_einblendung(kanal, b, h):
    """Abgeschafft - die Vorschau zeigt keine Folgen/Like-Grafik mehr."""
    return None, None, None
    import einblendung
    an = False
    if not an:
        return None, None, None
    try:
        gr = max(3.0, min(20.0, float(kanal.get("eb_groesse", 7) or 7)))
    except Exception:
        gr = 7.0
    hoehe = max(30, int(h * gr / 100.0))
    text = kanal.get("eb_text")
    if text is None:
        text = "FOLGEN"
    try:
        pfad = einblendung.datei(kanal.get("eb_art") or "folgen", text, hoehe,
                                 kanal.get("eb_farbe") or "")
    except Exception:
        return None, None, None
    pfad = str(pfad or "")
    if not pfad or not os.path.exists(pfad):
        return None, None, None
    platz = kanal.get("eb_platz") or "links_unten"
    rand, unten, oben = int(b * 0.05), int(h * 0.30), int(h * 0.11)
    y = str(oben) if platz.endswith("_oben") else "H-h-%d" % unten
    if platz.startswith("mitte"):
        x = "(W-w)/2"
    elif platz.startswith("links"):
        x = str(rand)
    else:
        x = "W-w-%d" % rand
    return pfad, x, y


def _p69_bild(k):
    """Rechnet ein Einzelbild und gibt (Rohdaten, None) oder (None, Grund)."""
    import tempfile
    import szenen_video as sv
    import video_bauen as vb

    kanal = dict(einstellungen.laden().get(k) or {})
    if not kanal:
        return None, "Kanal unbekannt"
    try:
        vb._setze_format(kanal)
    except Exception:
        pass
    b = int(getattr(vb, "BREITE", 1080))
    h = int(getattr(vb, "HOEHE", 1920))

    arbeit = tempfile.mkdtemp(prefix="p69_")
    try:
        hg, szene = _p69_hintergrund(k)

        try:
            n = max(1, min(6, int(kanal.get("untertitel_woerter") or 3)))
        except Exception:
            n = 3
        ass = os.path.join(arbeit, "ut.ass")
        plan = [{"untertitel": True, "text": " ".join(P69_WORTE[:n]),
                 "start": 0.0, "dauer": 3.0, "ton": None, "stuecke": []}]
        try:
            sv._ass(plan, ass, b, h, kanal)
        except Exception as e:
            return None, "Untertitel: %s" % e

        # Genau ein Bild durch die ganze Kette, mit dem Zeitstempel 1,5 s -
        # dort steht bei jedem Stil ein Wort mitten im Satz, und die
        # Einblendungen sind fertig eingeflogen.
        ein, teile, nr = [], [], 0
        if hg:
            ein += _P69_EINS + ["-i", hg]
        else:
            ein += ["-f", "lavfi", "-i",
                    "color=c=0x23232C:s=%dx%d:r=1:d=1" % (b, h)]
        teile.append("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,"
                     "crop=%d:%d,setsar=1,setpts=%s/TB[bg]"
                     % (b, h, b, h, _P69_ZEIT))
        v = "[bg]"

        fig, fplatz, fgroesse = _p76_figur(k, szene)
        if fig:
            try:
                kette = sv._figur_filter(fplatz, fgroesse,
                                         b, h, v, "[fg]", "statisch")
            except Exception:
                kette = ""
            if kette and "[1:v]" in kette:
                nr += 1
                ein += _P69_EINS + ["-i", fig]
                teile.append("[%d:v]setpts=%s/TB[figq]" % (nr, _P69_ZEIT))
                teile.append(kette.replace("[1:v]", "[figq]", 1))
                v = "[fg]"

        try:
            lk = sv._p56_look(kanal)
        except Exception:
            lk = ""
        if lk:
            teile.append("%s%s[lk]" % (v, lk))
            v = "[lk]"

        if os.path.exists(ass):
            teile.append("%sass='%s'[ut]"
                         % (v, ass.replace("\\", "/").replace(":", "\\:")))
            v = "[ut]"

        ebp, ebx, eby = _p69_einblendung(kanal, b, h)
        if ebp:
            nr += 1
            ein += _P69_EINS + ["-i", ebp]
            teile.append("[%d:v]format=rgba,setpts=%s/TB[eb];%s[eb]"
                         "overlay=x='%s':y='%s':format=auto[ebo]"
                         % (nr, _P69_ZEIT, v, ebx, eby))
            v = "[ebo]"

        breit = 540 if b <= h else 760
        teile.append("%sscale=%d:-2[out]" % (v, breit))

        ziel = os.path.join(arbeit, "vorschau.jpg")
        cmd = (["ffmpeg", "-y", "-loglevel", "error"] + ein
               + ["-filter_complex", ";".join(teile), "-map", "[out]",
                  "-frames:v", "1", "-q:v", "4", "-an", ziel])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=55)
        if r.returncode or not os.path.exists(ziel):
            return None, (r.stderr or "ffmpeg").strip()[-200:]
        with open(ziel, "rb") as f:
            return f.read(), None
    except Exception as e:
        return None, str(e)[:200]
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)


def _p69_vorschau(self, k):
    if not k or k not in einstellungen.laden():
        return self.sende({"fehler": "Kanal unbekannt"}, code=404)
    roh, grund = _p69_bild(k)
    if not roh:
        print("[Vorschau] %s" % grund)
        return self.sende({"fehler": grund or "ging nicht"}, code=500)
    return self.sende(roh, "image/jpeg")


Griff._p69_vorschau = _p69_vorschau


# ---------- Nachtrag p71: Welche Schriften es wirklich gibt ----------

# Was sich fuer Untertitel in Kurzvideos eignet - fett, breit, gut lesbar.
P71_GUT = ["Anton", "Bebas Neue", "Montserrat ExtraBold", "Montserrat Black",
           "Montserrat", "Oswald", "Archivo Black", "Fjalla One", "Russo One",
           "Luckiest Guy", "Bangers", "Titan One", "Permanent Marker", "Teko",
           "Inter Display Black", "Inter Black", "Inter ExtraBold",
           "Open Sans", "Lato", "Roboto", "Liberation Sans", "DejaVu Sans"]

# Was in einer Untertitelliste nichts verloren hat.
P71_WEG = ("mono", "math", "emoji", "symbol", "awesome", "ipa", "lohit",
           "kacst", "tlwg", "samyak", "gyre", "courier", "gargi", "nakula",
           "sahadeva", "mukti", "navilu", "pagul", "likhan", "jamrul",
           "padauk", "abyssinica", "kalapi", "rekha", "sarai", "lklug",
           "ori1uni", "pothana", "vemana", "suruma", "chandas", "gubbi",
           "nimbus", "standard symbols", "c059", "d050", "p052", "z003",
           "urw ", "opensymbol", "dingbats")


def _p71_vorhanden():
    """Die Schriftfamilien, die fontconfig wirklich kennt."""
    try:
        r = subprocess.run(["fc-list", ":", "family"],
                           capture_output=True, text=True, timeout=15)
    except Exception:
        return set()
    namen = set()
    for z in (r.stdout or "").splitlines():
        for teil in z.split(","):
            n = " ".join(teil.split())
            if n:
                namen.add(n)
    return namen


def _p71_schriften():
    """Zwei Listen: die guten zuerst, dahinter alles andere Installierte."""
    da = _p71_vorhanden()
    klein = {}
    for n in da:
        klein.setdefault(n.lower(), n)
    gut = [klein[n.lower()] for n in P71_GUT if n.lower() in klein]
    gutset = set(gut)
    rest = sorted((n for n in da
                   if n not in gutset
                   and not any(w in n.lower() for w in P71_WEG)),
                  key=lambda s: s.lower())
    return {"gut": gut, "rest": rest[:120]}


# ---------- Nachtrag p76: Figur in der Vorschau ----------


def _p76_figur(k, szene):
    """Die Figur, die in den Szenen steht, mit Platz und Groesse.

    Sucht erst in der Szene des Hintergrundbildes, dann in allen uebrigen.
    Gibt (Pfad, Platz, Groesse) oder (None, Platz, Groesse) zurueck.
    """
    import szenen as sz
    import figuren
    name = ((szene or {}).get("figur") or "").strip()
    pose = (szene or {}).get("pose") or ""
    platz = (szene or {}).get("platz") or "rechts_unten"
    groesse = (szene or {}).get("figur_groesse", 55)

    if not name:
        try:
            for s in (sz.fuer_anzeige(k).get("szenen") or []):
                if (s.get("figur") or "").strip():
                    name = s["figur"].strip()
                    pose = s.get("pose") or ""
                    platz = s.get("platz") or "rechts_unten"
                    groesse = s.get("figur_groesse", 55)
                    break
        except Exception:
            pass
    if not name:
        name = ((einstellungen.laden().get(k) or {}).get("geschichte_figur") or "").strip()
    if not name:
        return None, platz, groesse
    try:
        pf = figuren.pose_pfad(k, name, pose)
    except Exception:
        return None, platz, groesse
    pf = str(pf or "")
    return (pf if pf and os.path.exists(pf) else None), platz, groesse


def _p76_lage(k):
    """Welche Figur steht in den Szenen, wo - und welche gaebe es."""
    import szenen as sz
    import figuren
    try:
        szl = sz.fuer_anzeige(k).get("szenen") or []
    except Exception:
        szl = []
    namen = []
    try:
        for f in (figuren.fuer_anzeige(k).get("figuren") or []):
            if f.get("name"):
                namen.append(f["name"])
    except Exception:
        pass

    jetzt, platz, groesse = "", "rechts_unten", 55
    for s in szl:
        if (s.get("figur") or "").strip():
            jetzt = s["figur"].strip()
            platz = s.get("platz") or "rechts_unten"
            groesse = s.get("figur_groesse", 55)
            break
    else:
        if szl:
            platz = szl[0].get("platz") or "rechts_unten"
            groesse = szl[0].get("figur_groesse", 55)

    return {"figur": jetzt, "platz": platz, "groesse": groesse,
            "figuren": namen, "szenen": len(szl),
            "plaetze": [list(x) for x in figuren.PLAETZE]}


def _p76_setzen(k, d):
    """Setzt Figur, Platz und Groesse auf allen Szenen des Kanals."""
    import szenen as sz
    try:
        szl = sz.fuer_anzeige(k).get("szenen") or []
    except Exception:
        szl = []
    if not szl:
        return {"ok": False, "fehler": "Der Kanal hat noch keine Szenen"}
    felder = [f for f in ("figur", "platz", "figur_groesse") if f in d]
    if not felder:
        return {"ok": False, "fehler": "nichts zu setzen"}
    for s in szl:
        for f in felder:
            r = sz.aendern(k, s["id"], f, d[f])
            if not r.get("ok"):
                return r
    return {"ok": True, "szenen": len(szl)}


def _p76_post(self, k, d):
    if not k or k not in einstellungen.laden():
        return self.sende({"ok": False, "fehler": "Kanal unbekannt"}, code=404)
    return self.sende(_p76_setzen(k, d or {}))


Griff._p76_post = _p76_post


# ---------- Nachtrag p90: eine Szene nachziehen ----------

import time as _p90_time


def _p90_annehmen(k, zname, q):
    """Nach dem Hochladen: ersetzen, wenn eine Szene genannt ist, sonst anhaengen.

    Ein Videoclip, der zu einer bestehenden Szene hochgeladen wird, ersetzt
    nicht deren Bild, sondern wird ihr fertiger Clip: die Szene ueberspringt
    dann Bild und Videomodell.
    """
    sid = (q.get("sid") or [""])[0]
    if sid:
        if szenen.art(zname) == "clip" and hasattr(szenen, "r6_clip_eigen"):
            r = szenen.r6_clip_eigen(k, sid, zname)
            if r.get("ok"):
                print("[Szene] eigener Clip %s, %s Sek." % (zname, r.get("sekunden")))
            return r
        d = einstellungen.laden().get(k) or {}
        r = szenen.p90_datei_setzen(d, sid, zname)
        if r.get("ok"):
            print("[Szene] %s ersetzt durch %s" % (r.get("vorher"), zname))
        return r
    return szenen.hinzufuegen(k, zname, (q.get("text") or [""])[0])


def _p90_szene(dd, sid):
    for x in (dd.get("szenen") or []):
        if x.get("id") == sid:
            return x
    return None


def _p90_neu(k, sid):
    """Erzeugt das Bild genau einer Szene neu. Alle anderen bleiben unberuehrt."""
    import geschichte
    import bilder
    sid = str(sid or "").strip()
    if not sid:
        return {"ok": False, "fehler": "Keine Szene genannt"}
    kanal = einstellungen.laden().get(k) or {}
    if not kanal:
        return {"ok": False, "fehler": "Kanal unbekannt"}

    dd = szenen.laden(kanal)
    s = _p90_szene(dd, sid)
    if s is None:
        return {"ok": False, "fehler": "Szene unbekannt"}

    text = (s.get("text") or "").strip()
    if not text:
        return {"ok": False, "fehler":
                "Diese Szene hat keinen Text - ohne Text gibt es nichts zu malen"}

    ok, grund = bilder.bereit(kanal)
    if not ok:
        return {"ok": False, "fehler": grund}

    stil = kanal.get("geschichte_stil") or ""
    zusatz = kanal.get("stil_zusatz") or ""
    figur = (kanal.get("geschichte_figur") or "").strip()
    referenz = bilder.figur_referenz(kanal, figur) if figur else None

    # Nachtrag r11: steht im Feld "Bildbeschreibung" etwas, wird danach
    # gemalt. Sonst wie bisher aus dem Satz und seinen Klammern.
    eigen = (s.get("bild") or "").strip()
    prompt = geschichte.bildprompt(eigen or text, stil, figur, zusatz)
    name = "gs_%s_s%s.png" % (_p90_time.strftime("%H%M%S"), re.sub(r"\W", "", str(sid))[:6])
    ziel = os.path.join(szenen.ordner(kanal), name)

    pfad = bilder.erzeuge(kanal, prompt, ziel, referenz=referenz,
                          seite=kanal.get("format") or "9:16")
    if not pfad:
        return {"ok": False, "fehler":
                "Das Bildmodell hat nichts geliefert - im Lauf-Fenster steht der Grund"}

    r = szenen.p90_datei_setzen(kanal, sid, name)
    if not r.get("ok"):
        return r
    try:
        preis = round(bilder.preis_je_bild(kanal), 3)
    except Exception:
        preis = 0
    print("[Szene] %s neu erzeugt: %s" % (sid, name))
    return {"ok": True, "datei": name, "kosten": preis, "prompt_laenge": len(prompt)}


# ---------- Nachtrag r5: Clips je Szene ----------
#
# Der Ablauf, den Stefan wollte: Hintergrundbild je Szene steht schon,
# dazu kommen die beiden Darsteller und eine Anweisung, was in der Szene
# passiert. Daraus macht das Referenzmodell einen Clip. Jeder Clip wird
# einzeln angesehen und darf einzeln neu gemacht werden. Erst danach
# laeuft das Video zusammen.

import threading as _r5_threading
import time as _r5_time
import re as _r5_re

_R5_SPERRE = _r5_threading.Lock()
_R5_LAEUFT = {}      # kanal -> {"sid":..., "rest":[...], "stop":False, "text":...}

_R5_KLAMMER = _r5_re.compile(r"\[([^\[\]]{1,400})\]", _r5_re.S)
_R5_BEWEG = _r5_re.compile(r"^\s*BEWEGUNG\s*[:\-]\s*", _r5_re.I)
_R5_BILD = _r5_re.compile(r"^\s*BILD\s*[:\-]\s*", _r5_re.I)


def _r5_kanal(k):
    d = dict(einstellungen.laden().get(k) or {})
    d.setdefault("_key", k)
    return d


def _r5_regie(s, kanal):
    """Was in dieser Szene passieren soll.

    Erst das eigene Regiefeld, dann eine BEWEGUNG-Klammer im Text, dann
    die Vorgabe des Kanals. Eine BILD-Klammer ist fuer das Bildmodell
    gedacht und hat hier nichts zu suchen.
    """
    eigen = (s.get("regie") or "").strip()
    if eigen:
        return eigen
    teile = []
    for x in _R5_KLAMMER.findall(s.get("text") or ""):
        if _R5_BILD.match(x):
            continue
        teile.append(" ".join(_R5_BEWEG.sub("", x).split()))
    if teile:
        return " ".join(t for t in teile if t)
    return (kanal.get("kling_prompt") or "").strip()


def _r5_wer(s):
    """Welche Avatare in dieser Szene stehen. Leer heisst: die ganze Besetzung."""
    w = (s or {}).get("wer")
    return [str(x) for x in w if str(x or "").strip()] if isinstance(w, list) else []


def _r5_prompt(k, kanal, s):
    """Vorspann, wer wer ist. Dann was passiert. Dann die feste Regel."""
    import animation
    teile = []
    v = darsteller.prompt_vorspann(k, nur=_r5_wer(s))
    if v:
        teile.append(v)
    r = _r5_regie(s, kanal)
    if r:
        teile.append(r if r[-1] in ".!?" else r + ".")
    teile.append(animation.R4_STILL)
    return " ".join(t for t in teile if t)


def _r5_figuren(k, s=None):
    return [{"name": x["name"], "bilder": x["bilder"]}
            for x in darsteller.besetzung(k, _r5_wer(s))]


def _r5_einen(k, sid):
    """Erzeugt den Clip einer Szene. (ok, Text)."""
    import animation
    kanal = _r5_kanal(k)
    s = szenen.r3_szene(k, sid)
    if not s:
        return False, "Szene unbekannt"
    ok, grund = animation.ref_bereit(kanal)
    if not ok:
        return False, grund
    ok, grund = darsteller.bereit(k)
    if not ok:
        return False, grund

    hintergrund = ""
    if szenen.art(s.get("datei") or "") == "bild":
        p = szenen.datei_pfad(k, s["datei"])
        if os.path.exists(p):
            hintergrund = p
    figuren = _r5_figuren(k, s)
    if not figuren and not hintergrund:
        return False, "Diese Szene hat weder Hintergrundbild noch Besetzung"

    dauer = szenen.r3_clip_dauer(s)
    prompt = _r5_prompt(k, kanal, s)
    ziel = os.path.join(szenen.ordner(k),
                        "clip_%s_%s.mp4" % (re.sub(r"[^A-Za-z0-9]+", "", str(sid))[:12],
                                            time.strftime("%H%M%S")))

    def melden(t):
        szenen.r3_stand_setzen(k, sid, "laeuft", t)
        with _R5_SPERRE:
            if k in _R5_LAEUFT:
                _R5_LAEUFT[k]["text"] = t

    szenen.r3_stand_setzen(k, sid, "laeuft", "wird geschickt")
    pfad = animation.erzeuge_referenz(kanal, hintergrund, figuren, prompt,
                                      dauer, ziel,
                                      kanal.get("format") or "9:16", melden)
    if not pfad or not os.path.exists(ziel):
        szenen.r3_stand_setzen(k, sid, "fehler",
                               "Das Modell hat keinen Clip geliefert. "
                               "Siehe Zeilen oben.")
        return False, "kein Clip"
    r = szenen.r3_clip_setzen(k, sid, os.path.basename(ziel))
    if not r.get("ok"):
        szenen.r3_stand_setzen(k, sid, "fehler", r.get("fehler") or "nicht angenommen")
        return False, r.get("fehler") or "nicht angenommen"
    szenen.r3_stand_setzen(k, sid, "fertig", "%d Sekunden" % dauer)
    return True, os.path.basename(ziel)


def _r5_lauf(k, sids):
    """Arbeitet die Liste der Szenen nacheinander ab."""
    try:
        for nr, sid in enumerate(sids):
            with _R5_SPERRE:
                e = _R5_LAEUFT.get(k)
                if not e or e.get("stop"):
                    break
                e["sid"] = sid
                e["text"] = "faengt an"
                e["nummer"] = nr + 1
                e["rest"] = list(sids[nr + 1:])
            try:
                _r5_einen(k, sid)
            except Exception as f:
                print("[Referenz] Szene %s ging schief: %s" % (sid, f))
                try:
                    szenen.r3_stand_setzen(k, sid, "fehler", str(f)[:200])
                except Exception:
                    pass
    finally:
        with _R5_SPERRE:
            _R5_LAEUFT.pop(k, None)


def r5_clip_start(k, b):
    """Startet einen Clip oder alle. Antwortet sofort."""
    import animation
    if not k or k not in einstellungen.laden():
        return {"ok": False, "fehler": "Kanal unbekannt"}
    with _R5_SPERRE:
        if k in _R5_LAEUFT:
            return {"ok": False, "fehler":
                    "Es laeuft schon ein Clip. Einer nach dem anderen."}
    kanal = _r5_kanal(k)
    ok, grund = animation.ref_bereit(kanal)
    if not ok:
        return {"ok": False, "fehler": grund}
    ok, grund = darsteller.bereit(k)
    if not ok:
        return {"ok": False, "fehler": grund}

    alle = bool(b.get("alle"))
    d = szenen.laden(k)
    if alle:
        sids = [s["id"] for s in d["szenen"] if _r6_offen(s)]
        if not sids:
            return {"ok": False, "fehler":
                    "Keine Szene offen - alle haben schon einen Clip."}
    else:
        sid = str(b.get("sid") or "")
        if not szenen.r3_szene(k, sid):
            return {"ok": False, "fehler": "Szene unbekannt"}
        sids = [sid]

    with _R5_SPERRE:
        if k in _R5_LAEUFT:
            return {"ok": False, "fehler": "Es laeuft schon ein Clip."}
        _R5_LAEUFT[k] = {"sid": sids[0], "rest": sids[1:], "stop": False,
                         "text": "faengt an", "start": _r5_time.time(),
                         "gesamt": len(sids)}
    t = _r5_threading.Thread(target=_r5_lauf, args=(k, sids), daemon=True)
    t.start()
    return {"ok": True, "anzahl": len(sids)}


def _r6_offen(s):
    """Braucht diese Szene (noch) einen Referenzclip?

    Offen ist sie, wenn der Schalter auf "Avatare im Bild" steht und
    entweder noch kein Clip da ist oder das Bild inzwischen ausgetauscht
    wurde - dann ist der vorhandene Clip noch vom alten Bild.
    """
    if not hasattr(szenen, "r6_braucht_clip"):
        return not s.get("clip") and szenen.art(s.get("datei") or "") == "bild"
    if not szenen.r6_braucht_clip(s):
        return False
    return (not s.get("clip")) or bool(s.get("clip_veraltet"))

def r5_clip_stop(k):
    with _R5_SPERRE:
        e = _R5_LAEUFT.get(k)
        if not e:
            return {"ok": False, "fehler": "Es laeuft gerade nichts"}
        e["stop"] = True
    return {"ok": True, "hinweis": "Der laufende Clip wird noch fertig, "
                                   "danach ist Schluss."}


def r5_clip_stand(k):
    """Was gerade laeuft, und wie es um jede Szene steht."""
    import animation
    kanal = _r5_kanal(k)
    with _R5_SPERRE:
        e = dict(_R5_LAEUFT.get(k) or {})
    laeuft = bool(e)
    if laeuft:
        e["dauer"] = int(_r5_time.time() - (e.get("start") or _r5_time.time()))
        e.pop("start", None)
    d = szenen.laden(k)
    szn = [{"id": s["id"], "clip": s.get("clip", ""),
            "stand": s.get("clip_stand", ""), "text": s.get("clip_text", "")}
           for s in d["szenen"]]
    bereit, grund = animation.ref_bereit(kanal)
    dsok, dsgrund = darsteller.bereit(k)
    offen = [s for s in d["szenen"] if _r6_offen(s)]
    sek = sum(szenen.r3_clip_dauer(s) for s in offen)
    return {"laeuft": laeuft, "lauf": e, "szenen": szn,
            "bereit": bool(bereit and dsok),
            "grund": grund if not bereit else ("" if dsok else dsgrund),
            "offen": len(offen), "offen_sekunden": sek,
            "offen_preis": animation.ref_preis(kanal, sek) if sek else 0.0,
            "je_sekunde": animation.ref_preis(kanal, 1)}


def r5_clip_weg(k, sid):
    with _R5_SPERRE:
        e = _R5_LAEUFT.get(k)
        if e and e.get("sid") == sid:
            return {"ok": False, "fehler": "Diese Szene laeuft gerade"}
    return szenen.r3_clip_setzen(k, sid, "")


if __name__ == "__main__":
    os.makedirs(VIDEOS, exist_ok=True)
    os.makedirs(REGELN, exist_ok=True)
    print("Dashboard 2 laeuft auf Port %d" % PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Griff).serve_forever()


# ---------- Nachtrag n1: strenge Pruefung fuer die Kopfzeile ----------
#
# _slot_stand sagt auch dann "eingerichtet", wenn gar kein Modell
# eingetragen ist - es reicht, dass der fal.ai-Schluessel existiert.
# Fuer die alte Kachelleiste war das egal. Fuer die neue Zeile "Das
# fehlt noch" ist es falsch: "Clips mit Avataren" waere als fertig
# gemeldet worden, obwohl kein Modell drinsteht und jede Szene mit
# Avataren grau bleibt.
#
# Hier gilt ein Slot nur als bereit, wenn ein Eintrag existiert, der
# eine Adresse hat und an einen Schluessel kommt.

def slot_bereit(key, slot, *teile):
    try:
        eintraege = ((einstellungen.laden().get(key) or {}).get("apis") or {}).get(slot) or []
    except Exception:
        return False, ""
    eintraege = [e for e in eintraege if isinstance(e, dict) and (e.get("url") or "").strip()]
    if not eintraege:
        return False, ""
    nimm = None
    for e in eintraege:
        if e.get("aktiv"):
            nimm = e
            break
    if nimm is None:
        nimm = eintraege[0]
    name = (nimm.get("name") or "").strip()
    if (nimm.get("key") or "").strip():
        return True, name
    for teil in teile:
        if schluessel(teil):
            return True, name
    return False, ""


_n1_paare = [("text", "text", ("ANTHROPIC", "OPENAI")),
             ("bilder", "bilder", ("FAL",)),
             ("stimme", "stimme", ("FAL", "ELEVEN")),
             ("ref", "ref", ("FAL", "KLING")),
             ("video", "video", ("FAL", "KLING")),
             ("musik", "musik", ("FAL",))]


def api_stand(key=None):
    raus = {}
    for name, slot, teile in _n1_paare:
        ok, wie = slot_bereit(key, slot, *teile)
        raus[name] = ok
        raus[name + "_name"] = wie
    return raus


# ---------- Nachtrag g3: Drehbuch je Szene ansehen ----------
#
# Bisher stand die ganze Geschichte in einem Feld und man musste sich
# selbst zusammenreimen, was davon gesprochen wird, was der Avatar
# sagt, was Flux malt und was den Clip bewegt. Hier wird derselbe
# Zerleger benutzt, den auch der Bau spaeter nimmt - was hier steht,
# wird also wirklich so gebaut.

G3_MAX = 60


def _g3_zitate(text):
    try:
        import szenen_video as _sv
        return _sv._nach_anfuehrung(text or "")
    except Exception:
        return [(False, text or "")]


def drehbuch_lesen(key):
    d = einstellungen.laden().get(key) or {}
    try:
        import geschichte
        roh = geschichte.zerlege(d.get("geschichte_text") or "")
    except Exception as e:
        return {"ok": False, "fehler": str(e)[:120], "szenen": []}
    raus = []
    for s in roh[:G3_MAX]:
        try:
            rest, bild, beweg, ohne = geschichte._p84_klammern(s)
        except Exception:
            rest, bild, beweg, ohne = s, [], [], []
        stuecke = _g3_zitate(rest)
        raus.append({
            "erzaehler": " ".join(x for ist, x in stuecke if not ist).strip(),
            "avatar": " ".join(x for ist, x in stuecke if ist).strip(),
            "bild": ", ".join(bild) or ", ".join(ohne),
            "bewegung": ", ".join(beweg) or ", ".join(ohne),
        })
    return {"ok": True, "szenen": raus, "mehr": max(0, len(roh) - G3_MAX)}


_g3_stand_alt = geschichte_stand


def geschichte_stand(key):
    raus = _g3_stand_alt(key)
    try:
        _g3 = drehbuch_lesen(key)
        raus["drehbuch"] = _g3.get("szenen") or []
        raus["drehbuch_mehr"] = _g3.get("mehr") or 0
    except Exception as e:
        raus["drehbuch"] = []
        print("[Dashboard] Drehbuch nicht lesbar:", e)
    return raus


# ---------- Nachtrag g4: Themen vorschlagen lassen ----------
#
# Zwanzig Themen am Handy eintippen will niemand. Der Knopf laesst
# die Text-KI welche vorschlagen, passend zum Masterprompt und zu den
# Regeln des Kanals. Was schon offen oder erledigt ist, kommt nicht
# noch einmal.

G4_WIEVIEL = 12


def themen_vorschlagen(key, wieviel=G4_WIEVIEL):
    import text_generator, themen, json as _j, re as _re
    d = einstellungen.laden().get(key) or {}
    if not d:
        return {"ok": False, "fehler": "Kanal unbekannt"}
    try:
        wieviel = max(3, min(30, int(wieviel or G4_WIEVIEL)))
    except Exception:
        wieviel = G4_WIEVIEL

    liste = themen.laden(key)
    schon = list(liste.get("offen") or [])
    schon += [(x.get("thema") or "") for x in (liste.get("erledigt") or [])]
    schon = [x for x in schon if x][-80:]

    prompt = (
        "Du planst die Themenliste fuer einen Kurzvideo-Kanal.\n\n"
        "SO BESCHREIBT SICH DER KANAL:\n%s\n\n"
        "REGELN DES KANALS:\n%s\n\n"
        "Schlage genau %d Themen vor, die zu diesem Kanal passen.\n"
        "Jedes Thema ist eine Zeile und steht fuer sich: konkret genug, dass man "
        "sofort weiss, worum es geht, aber kurz. Keine Nummerierung, keine "
        "Erklaerung, kein Doppelpunkt-Geschwafel.\n"
        "%s\n"
        "Antworte NUR mit einer JSON-Liste von Zeichenketten, sonst nichts."
        % ((d.get("prompt") or "").strip() or "(noch nichts eingetragen)",
           (d.get("regeln") or "").strip() or "(keine)",
           wieviel,
           ("Diese sind schon vergeben, nimm andere:\n- " + "\n- ".join(schon))
           if schon else "")
    )
    try:
        antwort = text_generator._claude_anfrage(prompt, max_tokens=2000, kanal=d)
    except Exception as e:
        return {"ok": False, "fehler": "Die Text-KI hat nicht geantwortet: %s" % str(e)[:120]}
    if not antwort:
        return {"ok": False, "fehler": "Die Text-KI hat nichts geliefert"}

    roh = str(antwort)
    m = _re.search(r"\[.*\]", roh, _re.S)
    neu = []
    if m:
        try:
            neu = [str(x).strip() for x in _j.loads(m.group(0)) if str(x).strip()]
        except Exception:
            neu = []
    if not neu:
        neu = [_re.sub(r"^\s*[-*\d.)\s]+", "", z).strip().strip('",')
               for z in roh.splitlines()]
        neu = [z for z in neu if 8 < len(z) < 160]

    kleine = set(x.strip().lower() for x in schon)
    dazu = []
    for x in neu:
        if x.lower() not in kleine:
            kleine.add(x.lower())
            dazu.append(x)
    for x in dazu:
        themen.hinzufuegen(key, x)
    return {"ok": True, "dazu": len(dazu), "themen": themen.laden(key)}


# ---------- Nachtrag g5: Stil-Anker vorschlagen ----------
#
# Der alte Vorschlag war fuer die festen, aufgeklebten Figuren
# geschrieben - die gibt es nicht mehr. Jetzt laesst der Knopf die
# Text-KI einen Anker passend zum Masterprompt des Kanals schreiben.
# Der Anker haengt an jedem einzelnen Bild, muss also englisch sein
# und darf nichts ueber den Inhalt einer Szene sagen.

G5_NOTNAGEL = ("painterly historical illustration, warm natural light, "
               "rich earth tones, deep shadows, visible brushwork, "
               "period-accurate clothing and architecture, cinematic "
               "composition, shallow depth of field, no text, no letters, "
               "no numbers, no modern objects")


def stil_vorschlag(key):
    import text_generator
    d = einstellungen.laden().get(key) or {}
    eigen = (d.get("prompt") or "").strip()
    if not eigen:
        return {"ok": True, "text": G5_NOTNAGEL, "woher": "notnagel"}

    prompt = (
        "Schreibe einen Stil-Anker fuer einen Kurzvideo-Kanal.\n\n"
        "SO BESCHREIBT SICH DER KANAL:\n%s\n\n"
        "Der Stil-Anker wird an die Bildbeschreibung JEDER Szene angehaengt, "
        "damit alle Bilder eines Videos wie aus einem Guss aussehen.\n\n"
        "Regeln fuer deine Antwort:\n"
        "- Englisch, weil das Bildmodell englisch versteht\n"
        "- Nur durch Komma getrennte Eigenschaften, kein ganzer Satz\n"
        "- Nur wie es aussieht: Maltechnik, Licht, Farben, Kameranaehe, "
        "Bildaufbau. Nichts ueber den Inhalt einer Szene, keine Orte, "
        "keine Personen, keine Handlung\n"
        "- Hoechstens 30 Woerter\n"
        "- Am Ende immer: no text, no letters, no numbers\n\n"
        "Antworte NUR mit dem Stil-Anker, ohne Anfuehrungszeichen, ohne "
        "Erklaerung." % eigen
    )
    try:
        antwort = text_generator._claude_anfrage(prompt, max_tokens=400, kanal=d)
    except Exception as e:
        return {"ok": True, "text": G5_NOTNAGEL, "woher": "notnagel",
                "hinweis": str(e)[:140]}
    text = " ".join(str(antwort or "").split()).strip().strip('"').strip()
    if not text or len(text) > 600:
        return {"ok": True, "text": G5_NOTNAGEL, "woher": "notnagel"}
    return {"ok": True, "text": text, "woher": "ki"}


# ---------- Nachtrag g6: zeigen, welches Modell benutzt wird ----------
#
# Bei Kling gibt es zwei Modelle mit aehnlichem Namen:
# .../ai-avatar/v2/standard macht Lippensync zu einem fertigen Bild,
# .../o3/standard/reference-to-video baut den Clip aus Hintergrund
# und Avatarbildern. Nur das zweite kann, was wir brauchen. Wer das
# falsche eintraegt, kommt durch die Pruefung und scheitert erst bei
# fal.ai. Deshalb steht die Adresse jetzt in der Clips-Karte.

G6_RICHTIG = "reference-to-video"

_g6_stand_alt = r5_clip_stand


def r5_clip_stand(k):
    raus = _g6_stand_alt(k)
    try:
        import animation
        e = animation.ref_slot(_r5_kanal(k)) or {}
        url = (e.get("url") or "").strip()
        raus["ref_name"] = (e.get("name") or "").strip()
        raus["ref_url"] = url
        raus["ref_passt"] = (G6_RICHTIG in url.lower()) if url else None
    except Exception as f:
        print("[Referenz] Modell nicht lesbar:", f)
    return raus


# ---------- Nachtrag n2: Schluessel richtig suchen ----------
#
# slot_bereit() hat nur zwei Stellen gekannt: den Schluessel am
# Eintrag selbst und die Serverdatei (schluessel("FAL") liest die
# Umgebung). Den haeufigsten Fall kannte es nicht: ein Eintrag ohne
# eigenen Schluessel, dessen Anbieter schon bei einem anderen Eintrag
# desselben Kanals hinterlegt ist - im Dashboard steht dann
# "Schluessel mitbenutzt". Genau so laeuft Kling Referenz ueber den
# fal.ai-Schluessel von Flux Pro. Der Bau hat es gekonnt
# (schluessel.fuer), die Kopfzeile nicht - und meldete ein Modell als
# fehlend, das laengst da war.

def slot_bereit(key, slot, *teile):
    try:
        kanal = einstellungen.laden().get(key) or {}
        eintraege = (kanal.get("apis") or {}).get(slot) or []
    except Exception:
        return False, ""
    eintraege = [e for e in eintraege
                 if isinstance(e, dict) and (e.get("url") or "").strip()]
    if not eintraege:
        return False, ""
    nimm = None
    for e in eintraege:
        if e.get("aktiv"):
            nimm = e
            break
    if nimm is None:
        nimm = eintraege[0]
    name = (nimm.get("name") or "").strip()

    if (nimm.get("key") or "").strip():
        return True, name
    try:
        import schluessel as _n2_sm
        if _n2_sm.fuer(kanal, nimm):
            return True, name
    except Exception as e:
        print("[Dashboard] Schluessel nicht pruefbar:", e)
    for teil in teile:
        if schluessel(teil):
            return True, name
    return False, ""
